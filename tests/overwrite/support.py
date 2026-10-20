"""Shared helpers for the overwrite-protection harness (tests/overwrite).

Every case is materialized in a fresh temp folder at test time: her files
under `home/`, her Grok Bot's agents, skills, routines and memory facts as
files under `setup/`, an empty (or shared) second-brain home, and a synthetic
`kit.config.yaml`. The planner under test is `tools/kit_plan.py`; its contract
is `tools/KIT-PLAN-SPEC.md`. Nothing here reads a path outside the kit, the
case folder and the test's own temp folder. All data is synthetic.

Environment:
    KIT_OVERWRITE_TARGET  folder of `case-*.yaml` files (default: the fixtures)
    KIT_OVERWRITE_KIT     another copy of the kit to test (default: this one)

Run the suite with:
    python3 -m unittest discover -s tests/overwrite -p 'test_*.py'
or, with a target override:
    python3 tests/overwrite/run_harness.py --existing-dir <dir>
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import caseyaml

HERE = os.path.dirname(os.path.abspath(__file__))
KIT_ROOT = os.environ.get("KIT_OVERWRITE_KIT") or os.path.dirname(os.path.dirname(HERE))
DEFAULT_CASES_DIR = os.path.join(KIT_ROOT, "tests", "fixtures", "existing-setup")
KIT_PLAN = os.path.join(KIT_ROOT, "tools", "kit_plan.py")
AGENTS_MD = os.path.join(KIT_ROOT, "AGENTS.md")
KIT_PLAN_MISSING = "tools/kit_plan.py is missing: the overwrite harness needs the reference planner"

# --- the planner contract (tools/KIT-PLAN-SPEC.md) --------------------------

SCHEMA_VERSION = 1
ITEM_TYPES = ("add", "extend", "merge", "link", "skip", "report")
WRITING_TYPES = ("add", "link")
ITEM_KINDS = (
    "folder", "note", "router", "config", "state_note", "skill", "routine",
    "agent", "memory", "doctor", "plugin", "folio", "runner",
)
ROOTS = ("sb", "setup", "home", "kit")
REQUIRED_ITEM_KEYS = ("id", "type", "kind", "root", "target", "reason", "checkpoint")

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PLAN_CHANGED = 3
EXIT_TARGET_EXISTS = 4
REFUSALS = (EXIT_PLAN_CHANGED, EXIT_TARGET_EXISTS)

CHECKPOINT_ANY_RE = re.compile(r"\*\*CHECKPOINT (\d+[a-z]?)")

SETUP_SUBDIRS = ("agents", "skills", "routines", "memory")
DEFAULT_CHANNELS = ["dance-school", "other-activities"]
COLLISION_SUFFIX = "-kit"
# A fixed past mtime for every materialized file: a rewrite with identical
# bytes still shows as a change.
FIXED_MTIME_NS = 1_767_600_000 * 10 ** 9  # 2026-01-05T08:00:00Z


def agents_checkpoints():
    with open(AGENTS_MD, encoding="utf-8") as fh:
        return CHECKPOINT_ANY_RE.findall(fh.read())


def plan_sha256(items):
    """The approval hash: sha256 of the canonical JSON of the items list."""
    canonical = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fact_slug(fact):
    return re.sub(r"[^a-z0-9]+", "-", fact.lower()).strip("-")


# --- case discovery -------------------------------------------------------

def cases_dir():
    return os.environ.get("KIT_OVERWRITE_TARGET") or DEFAULT_CASES_DIR


def discover_cases(folder=None):
    """Sorted `case-*.yaml` paths of the case folder."""
    folder = folder or cases_dir()
    if not os.path.isdir(folder):
        raise RuntimeError("case folder not found: %s" % folder)
    return [
        os.path.join(folder, name)
        for name in sorted(os.listdir(folder))
        if name.startswith("case-") and name.endswith((".yaml", ".yml"))
    ]


def load_case(path):
    data = caseyaml.load_file(path)
    if not isinstance(data, dict) or "expect" not in data:
        raise RuntimeError("case file without an expect block: %s" % os.path.basename(path))
    return data


def case_label(path):
    return os.path.basename(path).rsplit(".", 1)[0]


# --- YAML out (for the synthetic kit.config.yaml) --------------------------

_PLAIN_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _yaml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _yaml_key(key):
    return key if _PLAIN_KEY.match(key) else json.dumps(key, ensure_ascii=False)


def yaml_lines(mapping, indent=0):
    pad = " " * indent
    out = []
    for key, value in mapping.items():
        if isinstance(value, dict) and value:
            out.append("%s%s:" % (pad, _yaml_key(key)))
            out.extend(yaml_lines(value, indent + 2))
        elif isinstance(value, dict):
            out.append("%s%s: {}" % (pad, _yaml_key(key)))
        elif isinstance(value, list):
            out.append("%s%s: [%s]" % (pad, _yaml_key(key), ", ".join(_yaml_scalar(v) for v in value)))
        else:
            out.append("%s%s: %s" % (pad, _yaml_key(key), _yaml_scalar(value)))
    return out


def dump_config(config):
    return "\n".join(["# synthetic harness config"] + yaml_lines(config)) + "\n"


# --- snapshots --------------------------------------------------------------

def snapshot(root, dir_mtime=False):
    """{relative path: descriptor}. Files: ("file", sha256, mtime_ns); folders:
    ("dir",) or ("dir", mtime_ns); symlinks: ("link", target)."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir != ".":
            st = os.stat(dirpath)
            out[rel_dir + "/"] = ("dir", st.st_mtime_ns) if dir_mtime else ("dir",)
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path):
                out[rel] = ("link", os.readlink(path))
                continue
            with open(path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            out[rel] = ("file", digest, os.stat(path).st_mtime_ns)
        for name in dirnames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                out[os.path.relpath(path, root).replace(os.sep, "/")] = ("link", os.readlink(path))
    return out


def under(rel, prefix):
    return rel == prefix or rel.startswith(prefix.rstrip("/") + "/")


# --- the temp world ----------------------------------------------------------

class World:
    """One case materialized under a temp folder.

    tmp/home     her files (`files:` entries)
    tmp/setup    agents/<n>/AGENT.md, skills/<n>/SKILL.md, routines/<n>.md,
                 memory/<slug>.md
    tmp/sb       the second-brain home (tmp/home when the case holds notes
                 with front matter: she already keeps notes there)
    tmp/kit.config.yaml, tmp/state.(yaml|json)
    """

    def __init__(self, tmp, case, case_path=None, config_extra=None):
        self.tmp = tmp
        self.case = case
        self.home = os.path.join(tmp, "home")
        self.setup = os.path.join(tmp, "setup")
        self.config_path = os.path.join(tmp, "kit.config.yaml")
        self.notes_in_home = any(isinstance(f, dict) for f in case.get("files") or [])
        self.sb = self.home if self.notes_in_home else os.path.join(tmp, "sb")
        self.her_files = []
        if case_path is not None:
            self.state_path = os.path.join(tmp, os.path.basename(case_path))
            shutil.copyfile(case_path, self.state_path)
        else:
            self.state_path = os.path.join(tmp, "state.json")
            with open(self.state_path, "w", encoding="utf-8") as fh:
                json.dump({k: v for k, v in case.items() if k != "expect"}, fh, indent=1)
        self.config_extra = config_extra or {}

    # -- paths

    def root_path(self, root):
        return {"sb": self.sb, "setup": self.setup, "home": self.home, "kit": KIT_ROOT}[root]

    def item_path(self, item):
        return os.path.join(self.root_path(item["root"]), item["target"].rstrip("/"))

    def rel(self, path):
        return os.path.relpath(path, self.tmp).replace(os.sep, "/")

    # -- materialization

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def materialize(self):
        os.makedirs(self.home, exist_ok=True)
        os.makedirs(self.sb, exist_ok=True)
        for sub in SETUP_SUBDIRS:
            os.makedirs(os.path.join(self.setup, sub), exist_ok=True)
        case = self.case
        for agent in case.get("agents") or []:
            self.write(
                os.path.join(self.setup, "agents", agent["name"], "AGENT.md"),
                "# Agent: %s\n\nRole: %s\nSkills: %s\n"
                % (agent["name"], agent.get("role", ""), ", ".join(agent.get("skills") or [])),
            )
            for skill in agent.get("skills") or []:
                self.write_skill(skill, "used by %s" % agent["name"])
        for skill in case.get("skills") or []:
            self.write_skill(skill["name"], skill.get("purpose", ""))
        for routine in case.get("routines") or []:
            self.write(
                os.path.join(self.setup, "routines", routine["name"] + ".md"),
                "# Routine: %s\n\nSchedule: %s\nReads: %s\nReports to: %s\n"
                % (routine["name"], routine.get("schedule", ""),
                   ", ".join(routine.get("reads") or []), routine.get("reports_to", "")),
            )
        for fact in case.get("memory") or []:
            self.write(os.path.join(self.setup, "memory", fact_slug(fact) + ".md"), fact + "\n")
        for entry in case.get("files") or []:
            if isinstance(entry, dict):
                rel = entry["path"]
                fm = entry.get("front_matter") or {}
                text = "---\n" + "".join(yaml_lines(fm)) + ("\n" if fm else "") + "---\n\n# Example note\n\nSynthetic body.\n"
            else:
                rel = entry
                text = "# Example\n\nSynthetic content of %s.\n" % rel
            self.write(os.path.join(self.home, rel), text)
            self.her_files.append(rel)
        self.write(self.config_path, dump_config(self.config()))
        self.touch_all()

    def write_skill(self, name, purpose):
        self.write(
            os.path.join(self.setup, "skills", name, "SKILL.md"),
            "---\nname: %s\ndescription: %s\n---\n\n# %s\n\nHer own steps.\n" % (name, purpose, name),
        )

    def touch_all(self):
        for root in (self.home, self.setup, self.sb):
            for dirpath, dirnames, filenames in os.walk(root):
                for name in filenames:
                    os.utime(os.path.join(dirpath, name), ns=(FIXED_MTIME_NS, FIXED_MTIME_NS))
        os.utime(self.config_path, ns=(FIXED_MTIME_NS, FIXED_MTIME_NS))

    def marketing_links(self):
        """`second_brain.marketing_links`: her campaign folders -> the kit's
        campaigns folder; only folders named `campaigns` are mapped."""
        links = {}
        for rel in self.her_files:
            folder = rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""
            if folder.rstrip("/").endswith("campaigns"):
                links[folder] = "dance-school/marketing/campaigns/"
        return links

    def config(self):
        config = {
            "kit": {"home": KIT_ROOT, "timezone": "UTC", "collision_suffix": COLLISION_SUFFIX},
            "existing_setup": {
                "mode": "integrate",
                "current_state_note": os.path.join(self.tmp, "current-state.md"),
            },
            "second_brain": {
                "home": self.sb,
                "channels": list(DEFAULT_CHANNELS),
                "marketing_links": self.marketing_links(),
            },
            "agents": {"dev_lead": {"enabled": False, "name": "dev-lead", "extend_existing": "",
                                    "sizing_interval_hours": 4}},
            "skills": {"sb_lookup": "sb-lookup", "content_calendar": "content-calendar-planner",
                       "comms_template": "comms-template-writer"},
            "routines": {"morning_brief": {"enabled": False, "name": "morning-brief", "merge_into": "",
                                           "time": "07:30"}},
        }
        for key, value in self.config_extra.items():
            config.setdefault(key, {}).update(value)
        return config

    # -- snapshots

    def snap(self, dir_mtime=False):
        return snapshot(self.tmp, dir_mtime=dir_mtime)

    # -- running the planner

    def env(self):
        return {
            "HOME": self.home,
            "KIT_HOME": KIT_ROOT,
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def run(self, *args, timeout=300):
        argv = [
            sys.executable, KIT_PLAN, *args,
            "--kit", KIT_ROOT,
            "--config", self.config_path,
            "--state", self.state_path,
            "--setup-dir", self.setup,
            "--home", self.home,
        ]
        proc = subprocess.run(
            argv, cwd=self.tmp, env=self.env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


# --- plan helpers -------------------------------------------------------------

def items_where(plan, **criteria):
    out = []
    for item in plan["items"]:
        if all(item.get(key) == value for key, value in criteria.items()):
            out.append(item)
    return out


def writing_items(plan):
    """Items `--apply` writes: add and link items outside an undecided choice."""
    return [i for i in plan["items"] if i["type"] in WRITING_TYPES and not i.get("choice")]


def unchanged_targets(world, entries):
    """Resolve an `expect.unchanged` entry to a tmp-relative prefix.

    `my-marketing/`           her folder under home
    `routines/<name>`         setup/routines/<name>.md
    `skills/<n>`, `agents/<n>` setup folders
    `notes/x.md`              her file under home
    "never posts on Sundays"  setup/memory/<slug>.md
    """
    out = []
    for entry in entries:
        if entry.startswith("routines/") and "." not in entry.rsplit("/", 1)[-1]:
            out.append("setup/" + entry + ".md")
        elif entry.startswith(("skills/", "agents/")):
            out.append("setup/" + entry.rstrip("/") + "/")
        elif "/" in entry:
            out.append("home/" + entry)
        else:
            out.append("setup/memory/" + fact_slug(entry) + ".md")
    return out


class HarnessCase(unittest.TestCase):
    """Base: one world per test, removed afterwards; common assertions."""

    maxDiff = None
    CASE_PATH = None  # set by the generated per-case classes
    CONFIG_EXTRA = None

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-overwrite-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def world(self, case=None, case_path=None):
        if case is None:
            case_path = case_path or self.CASE_PATH
            case = load_case(case_path)
        world = World(self.tmp, case, case_path, self.CONFIG_EXTRA)
        world.materialize()
        return world

    def require_planner(self):
        self.assertTrue(os.path.isfile(KIT_PLAN), KIT_PLAN_MISSING)

    def dry_run(self, world):
        """Run `--dry-run --json`, check exit 0 and return the parsed plan."""
        self.require_planner()
        code, out, err = world.run("--dry-run", "--json")
        self.assertEqual(code, EXIT_OK, "dry-run failed: " + err.strip()[-400:])
        try:
            plan = json.loads(out)
        except ValueError:
            self.fail("--json output is not one JSON document")
        self.assertIsInstance(plan, dict)
        return plan

    def apply(self, world, sha, *extra):
        self.require_planner()
        return world.run("--apply", "--approved", sha, "--json", *extra)

    # -- assertions

    def assert_plan_shape(self, plan):
        self.assertEqual(plan.get("kit_plan"), SCHEMA_VERSION, "schema version")
        self.assertEqual(plan.get("mode"), "dry-run")
        self.assertIsInstance(plan.get("items"), list)
        self.assertEqual(plan.get("sha256"), plan_sha256(plan["items"]), "sha256 is the hash of the items")
        valid = agents_checkpoints()
        self.assertEqual(plan.get("checkpoints"), valid,
                         "every checkpoint of AGENTS.md is listed once, in AGENTS.md order")
        ids = set()
        for item in plan["items"]:
            with self.subTest(item=item.get("id")):
                for key in REQUIRED_ITEM_KEYS:
                    self.assertIn(key, item)
                self.assertNotIn(item["id"], ids, "duplicate item id")
                ids.add(item["id"])
                self.assertIn(item["type"], ITEM_TYPES)
                self.assertIn(item["kind"], ITEM_KINDS)
                self.assertIn(item["root"], ROOTS)
                self.assertIn(item["checkpoint"], valid)
                self.assertIsInstance(item["target"], str)
                self.assertTrue(item["target"], "empty target")
                self.assertIsInstance(item["reason"], str)
                self.assertTrue(item["reason"].strip(), "empty reason")

    def assert_never_touches_existing(self, world, plan):
        """No add or link item names an existing path; nothing is written into the kit."""
        for item in plan["items"]:
            if item["type"] not in WRITING_TYPES:
                continue
            with self.subTest(item=item["id"]):
                self.assertNotEqual(item["root"], "kit", "the planner never writes into the kit folder")
                self.assertFalse(os.path.lexists(world.item_path(item)),
                                 "an add/link item targets an existing path: %s" % item["target"])
        for item in plan["items"]:
            if item["type"] in ("extend", "merge"):
                with self.subTest(item=item["id"]):
                    self.assertTrue(os.path.lexists(world.item_path(item)),
                                    "an extend/merge item must name something of hers that exists")

    def assert_unchanged(self, before, after, prefixes):
        """Every entry under each prefix is identical and no entry was added there."""
        for prefix in prefixes:
            with self.subTest(unchanged=prefix):
                old = {k: v for k, v in before.items() if under(k, prefix)}
                new = {k: v for k, v in after.items() if under(k, prefix)}
                self.assertTrue(old, "nothing was materialized under %s" % prefix)
                self.assertEqual(new, old)

    def assert_existing_untouched(self, before, after):
        """Every pre-existing file keeps its bytes and mtime; nothing was removed."""
        for rel, desc in before.items():
            if desc[0] == "dir":
                self.assertIn(rel, after, "a folder was removed: %s" % rel)
                continue
            with self.subTest(path=rel):
                self.assertIn(rel, after, "a file was removed or renamed")
                self.assertEqual(after[rel], desc, "bytes or mtime changed")
