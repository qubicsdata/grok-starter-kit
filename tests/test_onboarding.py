"""Onboarding entry point: AGENTS.md phases and checkpoints, parameter
consistency, starter skills, routines, the second-brain template and the
privacy text.

Conventions these tests enforce (documented in AGENTS.md, "How a phase runs"):

* A phase is a `## Phase N: title` section. Inside it every top-level bullet
  is one of: a read-only step (`- Propose:`, `- Show:`, `- Check:`, `- Read:`,
  `- Ask:`), a checkpoint (`- **CHECKPOINT <id>:**`, id = phase number plus an
  optional letter) or a write step (`- After your OK:` or `- After OK <id>:`).
  Anything else is an error, so a write step can never hide in a phase.
* A write step comes after a checkpoint of its phase; `After OK <id>:` comes
  after that exact checkpoint.
* Config keys are the dotted names in backticks (`second_brain.home`,
  `routines.morning_brief.*`). In the Key column of PARAMETERS.md a bare name
  after a key is its sibling (`kit.author_name` / `author_email`), and
  `a.b/c/d` names `a.b`, `a.c` and `a.d`.

`KIT_ONBOARDING_ROOT` points the suite at another copy of the kit; the dev
check `tests/onboarding_mutation_check.py` uses it to break the docs one way
at a time and confirm the suite goes red. `KitPlanTest` runs the real
reference planner `tools/kit_plan.py` (its harness is `tests/overwrite/`).
Stdlib only, Python 3.9+.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.environ.get("KIT_ONBOARDING_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

AGENTS = "AGENTS.md"
PARAMETERS = "PARAMETERS.md"
README = "README.md"
EXAMPLE_YAML = "kit.config.example.yaml"
RUNNER_JSON = os.path.join("runner", "runner.config.example.json")
CHECKLIST = os.path.join("onboarding", "setup-checklist.md")
DISCOVERY = os.path.join("onboarding", "discovery-prompt.md")
CURRENT_STATE = os.path.join("onboarding", "current-state.md")
MORNING_BRIEF = os.path.join("routines", "morning-brief.md")
KIT_PLAN = os.path.join("tools", "kit_plan.py")
PLANNER_COMMAND = "python3 tools/kit_plan.py --dry-run"

SKILLS = ("sb-lookup", "content-calendar-planner", "comms-template-writer")

# The phase order of the design ("How it lands on her side"), as a keyword
# that must appear in each phase title, in this order.
PHASE_ORDER = [
    "discovery", "config", "second brain", "skills", "routines",
    "plugins", "folio", "dev-lead", "runner", "verify",
]

# The folders and files this work package owns; the ripgrep and key checks
# run over these.
DOC_SET = [README, AGENTS, PARAMETERS, "onboarding", "routines", "grok-skills"]
SB_DOCS = [os.path.join("second-brain", "README.md"), os.path.join("second-brain", "bin", "README.md")]

PHASE_RE = re.compile(r"^## Phase (\d+): (.+?)\s*$")
HEADING_RE = re.compile(r"^## ")
BULLET_RE = re.compile(r"^- (.*)$")
CHECKPOINT_RE = re.compile(r"^\*\*CHECKPOINT (\d+[a-z]?):\*\*")
READ_ONLY_RE = re.compile(r"^(Propose|Show|Check|Read|Ask):")
WRITE_RE = re.compile(r"^After (your OK|OK (\d+[a-z]?)):")
CHECKPOINT_ANY_RE = re.compile(r"\*\*CHECKPOINT (\d+[a-z]?)")

TOKEN_RE = re.compile(r"`([^`]+)`")
KEY_PART_RE = re.compile(r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*$")
FILE_SUFFIXES = ("yaml", "yml", "json", "md", "py", "sh", "txt")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def exists(rel):
    return os.path.exists(os.path.join(ROOT, rel))


def md_files(rel):
    """Every .md file under rel (a file or a folder), kit-relative, sorted."""
    path = os.path.join(ROOT, rel)
    if os.path.isfile(path):
        return [rel]
    out = []
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for name in sorted(filenames):
            if name.endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, name), ROOT))
    return out


# ---------------------------------------------------------------- AGENTS.md


def parse_phases(text):
    """[(number, title, [(kind, id_or_None, text)])] for every `## Phase N`
    section; kind is 'checkpoint', 'read', 'write' or 'other'. Indented
    bullets belong to the bullet above and are not classified."""
    phases = []
    current = None
    for line in text.splitlines():
        m = PHASE_RE.match(line)
        if m:
            current = (int(m.group(1)), m.group(2), [])
            phases.append(current)
            continue
        if HEADING_RE.match(line):
            current = None
            continue
        if current is None:
            continue
        m = BULLET_RE.match(line)
        if not m:
            continue
        body = m.group(1)
        c = CHECKPOINT_RE.match(body)
        if c:
            current[2].append(("checkpoint", c.group(1), body))
        elif READ_ONLY_RE.match(body):
            current[2].append(("read", None, body))
        elif WRITE_RE.match(body):
            w = WRITE_RE.match(body)
            current[2].append(("write", w.group(2), body))
        else:
            current[2].append(("other", None, body))
    return phases


def checkpoint_key(cid):
    m = re.match(r"^(\d+)([a-z]?)$", cid)
    return int(m.group(1)), m.group(2)


class AgentsStructureTest(unittest.TestCase):
    def setUp(self):
        self.text = read(AGENTS)
        self.phases = parse_phases(self.text)

    def test_ten_phases_in_design_order(self):
        numbers = [n for n, _, _ in self.phases]
        self.assertEqual(numbers, list(range(1, 11)))
        for (number, title, _), keyword in zip(self.phases, PHASE_ORDER):
            with self.subTest(phase=number):
                self.assertIn(keyword, title.lower())

    def test_checkpoint_ids_unique_and_ordered(self):
        ids = CHECKPOINT_ANY_RE.findall(self.text)
        self.assertTrue(ids, "no checkpoint found")
        self.assertEqual(len(ids), len(set(ids)), "duplicate checkpoint id")
        keys = [checkpoint_key(i) for i in ids]
        self.assertEqual(keys, sorted(keys), "checkpoints out of order")

    def test_checkpoint_number_is_its_phase_number(self):
        for number, _, steps in self.phases:
            for kind, cid, _ in steps:
                if kind == "checkpoint":
                    with self.subTest(checkpoint=cid):
                        self.assertEqual(checkpoint_key(cid)[0], number)

    def test_every_phase_has_a_checkpoint(self):
        for number, _, steps in self.phases:
            with self.subTest(phase=number):
                self.assertTrue(any(k == "checkpoint" for k, _, _ in steps))

    def test_every_phase_has_a_read_only_step(self):
        for number, _, steps in self.phases:
            with self.subTest(phase=number):
                self.assertTrue(any(k == "read" for k, _, _ in steps))

    def test_every_step_is_classified(self):
        for number, _, steps in self.phases:
            others = [text for kind, _, text in steps if kind == "other"]
            with self.subTest(phase=number):
                self.assertEqual(others, [], "unclassified step (not read-only, checkpoint or write)")

    def test_no_write_step_before_a_checkpoint(self):
        for number, _, steps in self.phases:
            seen = []
            for kind, cid, text in steps:
                if kind == "checkpoint":
                    seen.append(cid)
                elif kind == "write":
                    with self.subTest(phase=number, step=text[:40]):
                        self.assertTrue(seen, "write step before any checkpoint of its phase")
                        if cid is not None:
                            self.assertIn(cid, seen, "write step before its own checkpoint")

    def test_read_only_steps_never_claim_to_write_after_ok(self):
        for number, _, steps in self.phases:
            for kind, _, text in steps:
                if kind == "read":
                    with self.subTest(phase=number, step=text[:40]):
                        self.assertNotIn("after your ok", text.lower())

    def test_write_steps_follow_the_checkpoint_of_the_same_phase(self):
        # A checkpoint id in a write step belongs to its own phase.
        for number, _, steps in self.phases:
            for kind, cid, _ in steps:
                if kind == "write" and cid is not None:
                    with self.subTest(phase=number, step=cid):
                        self.assertEqual(checkpoint_key(cid)[0], number)

    def _phase(self, number):
        for n, title, steps in self.phases:
            if n == number:
                return title, steps
        self.fail("phase %d missing" % number)

    def test_phase_9_shows_the_terms_notice_before_9a(self):
        _, steps = self._phase(9)
        kinds = [(k, c, t) for k, c, t in steps]
        shown = [i for i, (k, c, t) in enumerate(kinds) if k == "read" and "runner/TERMS-NOTICE.md" in t]
        self.assertTrue(shown, "phase 9 does not show runner/TERMS-NOTICE.md")
        nine_a = [i for i, (k, c, t) in enumerate(kinds) if k == "checkpoint" and c == "9a"]
        self.assertEqual(len(nine_a), 1)
        self.assertLess(shown[0], nine_a[0])

    def test_phase_9_has_separate_9a_and_9b(self):
        _, steps = self._phase(9)
        ids = [c for k, c, _ in steps if k == "checkpoint"]
        self.assertEqual(ids, ["9a", "9b"])

    def test_phase_9_runner_stays_off_until_9b(self):
        _, steps = self._phase(9)
        writes = {c: t for k, c, t in steps if k == "write"}
        self.assertIn("9a", writes, "no `After OK 9a:` step")
        self.assertIn("9b", writes, "no `After OK 9b:` step")
        self.assertIn("runner.enabled: false", writes["9a"])
        self.assertNotIn("runner.enabled: true", writes["9a"])
        self.assertIn("runner.enabled: true", writes["9b"])
        enabling = [t for k, c, t in steps if "runner.enabled: true" in t and k == "write"]
        self.assertEqual(enabling, [writes["9b"]], "only the 9b step enables the runner")
        self.assertIn("9b", self.text)
        self.assertRegex(self.text, r"Without (OK )?9b it never runs")

    def test_phase_1_is_read_only_until_checkpoint_1(self):
        title, steps = self._phase(1)
        self.assertIn("read-only", title.lower())
        before = [k for k, _, _ in steps[: [k for k, _, _ in steps].index("checkpoint")]]
        self.assertTrue(before and all(k == "read" for k in before))

    def test_phase_5_and_8_keep_routines_off_until_a_separate_ok(self):
        for number in (5, 8):
            _, steps = self._phase(number)
            ids = [c for k, c, _ in steps if k == "checkpoint"]
            with self.subTest(phase=number):
                self.assertEqual(ids, ["%da" % number, "%db" % number])

    def test_names_the_reference_planner(self):
        self.assertIn(PLANNER_COMMAND, self.text)
        intro = self.text.split("## Phase 1")[0]
        self.assertIn(PLANNER_COMMAND, intro, "the planner is introduced before the phases")

    def test_integrate_not_replace_and_conflict_table(self):
        self.assertIn("Integrate, don't replace", self.text)
        table = self.text.split("## Conflict resolution")[1]
        rows = [l for l in table.splitlines() if l.startswith("|") and not l.startswith("|---")]
        self.assertGreaterEqual(len(rows) - 1, 6, "conflict table has six rows or more")
        for cell in ("collision", "routine", "folder", "memory", "campaign", "channel tag"):
            with self.subTest(conflict=cell):
                self.assertTrue(any(cell in r.lower() for r in rows[1:]))

    def test_checkpoint_definition_names_the_four_triggers(self):
        intro = self.text.split("## Phase 1")[0].lower()
        for trigger in ("writes to your setup", "creates an agent or routine", "starts the runner", "sends, posts or spends"):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, intro)


# ---------------------------------------------------------------- config keys


def yaml_keys(text):
    """Dotted key paths (mappings and leaves) and scalar values of the kit's
    YAML subset. Quoted keys are data entries (path defaults), not settings."""
    keys, values, stack = set(), {}, []
    key_re = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):(.*)$")
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw.lstrip().startswith("-"):
            continue
        m = key_re.match(raw)
        if not m:
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([k for _, k in stack] + [key])
        keys.add(path)
        value = rest.split("#", 1)[0].strip() if not rest.strip().startswith(("\"", "'")) else rest.strip()
        if value.startswith("\""):
            value = value[1:].split("\"", 1)[0]
        if value == "":
            stack.append((indent, key))
        else:
            values[path] = value
    return keys, values


def json_keys(obj, prefix=""):
    keys = set()
    for key, value in obj.items():
        if key.startswith("_comment"):
            continue
        path = prefix + key
        keys.add(path)
        if isinstance(value, dict):
            keys |= json_keys(value, path + ".")
    return keys


def leaf_keys(keys):
    return {k for k in keys if not any(o.startswith(k + ".") for o in keys)}


class ConfigKeys:
    def __init__(self):
        ykeys, self.values = yaml_keys(read(EXAMPLE_YAML))
        with open(os.path.join(ROOT, RUNNER_JSON), encoding="utf-8") as fh:
            jkeys = json_keys(json.load(fh))
        self.keys = ykeys | jkeys
        self.top = {k.split(".")[0] for k in self.keys}
        self.leaves = leaf_keys(self.keys)

    def covered(self, leaf, mentions):
        return any(leaf == m or leaf.startswith(m + ".") for m in mentions)


def strip_token(token):
    """`key: value` and `key=value` name the key."""
    for sep in (":", "="):
        if sep in token:
            token = token.split(sep, 1)[0]
    return token.strip()


def key_mentions(text, config, siblings):
    """(mentions, errors): the config keys a text names. A token `a.b.*`
    names the subtree of `a.b`. With `siblings`, a bare name after a key in
    the same line is that key's sibling and `a.b/c` names `a.b` and `a.c`."""
    mentions, errors = [], []
    for line in text.splitlines():
        previous = None
        for token in TOKEN_RE.findall(line):
            token = strip_token(token)
            if not siblings and "/" in token:
                continue
            parts = token.split("/") if siblings else [token]
            for index, part in enumerate(parts):
                wildcard = part.endswith(".*")
                if wildcard:
                    part = part[:-2]
                if not KEY_PART_RE.match(part):
                    continue
                if part.split(".")[-1] in FILE_SUFFIXES:
                    continue
                first = part.split(".")[0]
                if first in config.top and (index == 0 or "." in part):
                    resolved = part
                elif previous is not None and (siblings or index > 0):
                    resolved = previous.rsplit(".", 1)[0] + "." + part
                elif "." in part:
                    errors.append("%s: unknown key root `%s`" % (line.strip()[:60], part))
                    continue
                else:
                    continue
                if resolved not in config.keys:
                    errors.append("%s: `%s` is not in the example configs" % (line.strip()[:60], resolved))
                    continue
                mentions.append(resolved)
                previous = resolved
    return mentions, errors


def parameters_key_column(text):
    """The Key column of the PARAMETERS.md table, one string per row."""
    cells = []
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [c.strip() for c in line.strip().strip("|").split("|")]
        if parts and parts[0] != "Key":
            cells.append(parts[0])
    return cells


# Build job ids (a prefix and a number, or a bare `K7`) belong in the git history, not in the user's parameter table.
JOB_ID_RE = re.compile(r"\b(?:KIT|RF|WP|GATE)-(?:[A-Z]+-?)?\d|\bK\d+(?:-\d+)?\b")


def duplicate_cells(cells):
    """Key cells that occur more than once (whitespace-insensitive), in first-seen order."""
    seen, duplicates = set(), []
    for cell in cells:
        cell = " ".join(cell.split())
        if cell in seen and cell not in duplicates:
            duplicates.append(cell)
        seen.add(cell)
    return duplicates


def job_id_lines(text):
    return [line.strip()[:60] for line in text.splitlines() if JOB_ID_RE.search(line)]


class ParameterConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = ConfigKeys()

    def test_example_configs_have_keys(self):
        self.assertIn("second_brain.home", self.config.keys)
        self.assertIn("backlog.quiet_hours.tz", self.config.keys)
        self.assertIn("kit.collision_suffix", self.config.values)

    def test_every_key_in_parameters_exists(self):
        cells = parameters_key_column(read(PARAMETERS))
        self.assertTrue(cells, "no table rows in PARAMETERS.md")
        errors, mentions = [], []
        for cell in cells:
            found, bad = key_mentions(cell, self.config, siblings=True)
            errors += bad
            mentions += found
            if not found:
                errors.append("row names no config key: %s" % cell[:60])
        self.assertEqual(errors, [])

    def test_every_example_config_key_is_in_parameters(self):
        cells = parameters_key_column(read(PARAMETERS))
        mentions = set()
        for cell in cells:
            found, _ = key_mentions(cell, self.config, siblings=True)
            mentions |= set(found)
        missing = sorted(k for k in self.config.leaves if not self.config.covered(k, mentions))
        self.assertEqual(missing, [], "example config keys without a PARAMETERS.md row")

    def test_parameters_key_cells_are_unique(self):
        self.assertEqual(duplicate_cells(parameters_key_column(read(PARAMETERS))), [])

    def test_parameters_carry_no_build_job_ids(self):
        self.assertEqual(job_id_lines(read(PARAMETERS)), [])

    def test_drift_guards_catch_planted_rows(self):
        table = "\n".join((
            "| Key | Default | Note |", "|---|---|---|",
            "| `a.b` / `c` | 1 | first |", "| `a.c` | 2 | (KIT-X9-1) |", "| `a.b`  /  `c` | 3 | again, K4 |", "| `a.d` | 4 | |",
        ))
        self.assertEqual(duplicate_cells(parameters_key_column(table)), ["`a.b` / `c`"])
        self.assertEqual(job_id_lines(table), ["| `a.c` | 2 | (KIT-X9-1) |", "| `a.b`  /  `c` | 3 | again, K4 |"])
        self.assertEqual(job_id_lines("| `kit.home` (KIT_HOME) | `vendor/x/KIT-README.md`, K-pop |"), [])

    def test_every_key_in_agents_exists(self):
        _, errors = key_mentions(read(AGENTS), self.config, siblings=False)
        self.assertEqual(errors, [])

    def test_agents_names_the_keys_it_relies_on(self):
        mentions, _ = key_mentions(read(AGENTS), self.config, siblings=False)
        for key in (
            "existing_setup.current_state_note", "existing_setup.mode", "kit.collision_suffix",
            "second_brain.home", "second_brain.marketing_links", "routines.morning_brief.merge_into",
            "routines.morning_brief.enabled", "agents.dev_lead.extend_existing", "accelerator.plugins",
            "folio.backlog_version", "runner.config", "runner.enabled",
        ):
            with self.subTest(key=key):
                self.assertIn(key, mentions)

    def test_every_key_in_onboarding_and_readme_exists(self):
        for rel in md_files("onboarding") + [README, CHECKLIST]:
            if not exists(rel):
                continue
            with self.subTest(file=rel):
                _, errors = key_mentions(read(rel), self.config, siblings=False)
                self.assertEqual(errors, [])

    def test_collision_suffix_matches_the_docs(self):
        suffix = self.config.values["kit.collision_suffix"]
        self.assertEqual(suffix, "-kit")
        self.assertIn("sb-lookup" + suffix, read(os.path.join("grok-skills", "sb-lookup", "SKILL.md")))
        self.assertIn("sb-lookup" + suffix, read(os.path.join("tests", "fixtures", "existing-setup", "README.md")))


# ---------------------------------------------------------------- skills


def front_matter(text):
    """{key: value} of a `---` block at the top; folded and literal block
    scalars (`>-`, `>`, `|`, `|-`) are joined with spaces."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields, key = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m and not line.startswith(" "):
            key, value = m.group(1), m.group(2).strip()
            fields[key] = "" if value in (">-", ">", "|", "|-") else value.strip("\"'")
        elif key is not None and line.startswith(" "):
            fields[key] = (fields[key] + " " + line.strip()).strip()
        else:
            return None
    return None


class SkillsTest(unittest.TestCase):
    def test_front_matter_parses_and_name_matches_folder(self):
        for name in SKILLS:
            rel = os.path.join("grok-skills", name, "SKILL.md")
            with self.subTest(skill=name):
                fields = front_matter(read(rel))
                self.assertIsNotNone(fields, "no closed front matter block")
                self.assertEqual(fields.get("name"), name)
                self.assertTrue(fields.get("description"), "empty description")
                self.assertRegex(fields["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")

    def test_only_the_three_starter_skills_ship(self):
        folder = os.path.join(ROOT, "grok-skills")
        self.assertEqual(sorted(os.listdir(folder)), sorted(SKILLS))

    def test_skills_never_send_or_post(self):
        for name in SKILLS:
            text = read(os.path.join("grok-skills", name, "SKILL.md")).lower()
            with self.subTest(skill=name):
                self.assertRegex(text, r"never (send|publish|edit)")


# ---------------------------------------------------------------- routines


class RoutinesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = ConfigKeys()

    def test_routine_docs_reference_only_existing_keys(self):
        for rel in md_files("routines"):
            with self.subTest(file=rel):
                mentions, errors = key_mentions(read(rel), self.config, siblings=False)
                self.assertEqual(errors, [])
                self.assertTrue(mentions, "the routine names no config key")

    def test_morning_brief_names_every_morning_brief_key(self):
        mentions, _ = key_mentions(read(MORNING_BRIEF), self.config, siblings=False)
        expected = sorted(k for k in self.config.leaves if k.startswith("routines.morning_brief."))
        self.assertTrue(expected)
        self.assertEqual(sorted(set(mentions) & set(expected)), expected)

    def test_morning_brief_only_reports(self):
        text = read(MORNING_BRIEF).lower()
        self.assertIn("never sends, posts or schedules", text)
        self.assertIn("merges into", text)


# ---------------------------------------------------------------- template


class SecondBrainTemplateTest(unittest.TestCase):
    def test_doctor_is_clean_on_the_template(self):
        tmp = tempfile.mkdtemp(prefix="kit-onboarding-")
        self.addCleanup(shutil.rmtree, tmp, True)
        template = os.path.join(tmp, "second-brain")
        shutil.copytree(
            os.path.join(ROOT, "second-brain"), template,
            ignore=shutil.ignore_patterns("bin", "tests", "__pycache__"),
        )
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        env = {
            "HOME": home, "SB_HOME": template, "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
        }
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "second-brain", "bin", "sb"), "--doctor"],
            cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=120,
        )
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertRegex(proc.stdout.strip().splitlines()[-1], r" 0 failures, 0 warnings$")


# ---------------------------------------------------------------- onboarding


class OnboardingFilesTest(unittest.TestCase):
    def test_setup_checklist_ships(self):
        self.assertTrue(exists(CHECKLIST))
        text = read(CHECKLIST)
        self.assertIn("AGENTS.md", text)
        self.assertIn("## Privacy", text)

    def test_discovery_prompt_is_read_only(self):
        text = read(DISCOVERY)
        self.assertIn("READ-ONLY", text)
        self.assertIn("Do not create, change, rename, move, delete, send, post or schedule anything", text)
        self.assertIn("current-state.md", text)

    def test_current_state_has_a_section_per_inventory_item(self):
        text = read(CURRENT_STATE)
        for heading in ("Agents", "Routines", "Skills", "Memory", "Channels", "Campaigns", "File and folder"):
            with self.subTest(section=heading):
                self.assertRegex(text, r"(?m)^## " + re.escape(heading))
        self.assertIn("Proposed kit actions", text)
        self.assertIn("Checkpoint", text.split("Proposed kit actions")[1])

    def test_current_state_speaks_to_the_reader(self):
        text = read(CURRENT_STATE)
        self.assertNotRegex(text, r"<her ")
        self.assertIn("<your existing folder>", text)

    def test_readme_points_at_the_entry_point_and_planner(self):
        text = read(README)
        self.assertIn("AGENTS.md", text)
        self.assertIn(PLANNER_COMMAND, text)
        self.assertIn("onboarding/setup-checklist.md", text)


class PrivacyTextTest(unittest.TestCase):
    def test_readme_keeps_the_privacy_paragraph(self):
        text = read(README)
        for phrase in ("minors", "separate secured roster", "requires legal confirmation"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_checklist_keeps_the_privacy_section(self):
        text = read(CHECKLIST)
        section = text.split("## Privacy")[1]
        for phrase in ("minors", "roster", "requires legal confirmation", "consent"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section.lower())

    def test_agents_states_the_privacy_rule(self):
        text = read(AGENTS).lower()
        for phrase in ("minors", "roster", "legal confirmation"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_comms_folder_keeps_the_roster_elsewhere_note(self):
        rel = os.path.join("second-brain", "dance-school", "comms", "README-roster-lives-elsewhere.md")
        text = read(rel).lower()
        self.assertIn("templates only", text)
        self.assertIn("roster", text)


# ---------------------------------------------------------------- ripgrep


REQUIREMENT_RE = re.compile(r"\b(required|requirement|prerequisite|needs?|needed|must)\b", re.I)
OPTIONAL_RE = re.compile(r"\b(optional|never installs?)\b", re.I)


class RipgrepOptionalTest(unittest.TestCase):
    def test_no_doc_lists_ripgrep_as_a_requirement(self):
        files = []
        for rel in DOC_SET:
            files += md_files(rel)
        files += [rel for rel in SB_DOCS if exists(rel)]
        offending = []
        for rel in files:
            for number, line in enumerate(read(rel).splitlines(), 1):
                if not re.search(r"ripgrep|\brg\b", line):
                    continue
                if REQUIREMENT_RE.search(line) and not OPTIONAL_RE.search(line):
                    offending.append("%s:%d" % (rel, number))
                if re.search(r"- \[ \] ripgrep", line):
                    offending.append("%s:%d (prerequisite box)" % (rel, number))
        self.assertEqual(offending, [])

    def test_agents_says_ripgrep_is_optional(self):
        text = read(AGENTS)
        self.assertRegex(text, r"ripgrep[^.\n]*optional")
        self.assertIn("never installs", text)


# ---------------------------------------------------------------- kit_plan


def tree_digest(root):
    digest = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                digest[os.path.relpath(path, root)] = fh.read()
    return digest


class KitPlanTest(unittest.TestCase):
    """The reference planner AGENTS.md names; its contract is: a dry run
    writes nothing and reports every checkpoint of AGENTS.md. The full
    contract is tested by tests/overwrite/ (ci_local step overwrite-harness)."""

    def test_planner_ships(self):
        self.assertTrue(exists(KIT_PLAN), "tools/kit_plan.py is missing")

    def _copy_kit(self):
        tmp = tempfile.mkdtemp(prefix="kit-plan-")
        self.addCleanup(shutil.rmtree, tmp, True)
        kit = os.path.join(tmp, "kit")
        shutil.copytree(ROOT, kit, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        return kit, home

    def _run(self, kit, home, args):
        env = {"HOME": home, "KIT_HOME": kit, "PATH": os.environ.get("PATH", ""),
               "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run(
            [sys.executable, os.path.join(kit, KIT_PLAN)] + args, cwd=kit, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=300,
        )

    def test_help_mentions_dry_run(self):
        kit, home = self._copy_kit()
        proc = self._run(kit, home, ["--help"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--dry-run", proc.stdout)

    def test_dry_run_writes_nothing(self):
        kit, home = self._copy_kit()
        before = tree_digest(kit), tree_digest(home)
        self._run(kit, home, ["--dry-run"])
        self.assertEqual((tree_digest(kit), tree_digest(home)), before)

    def test_dry_run_names_every_checkpoint(self):
        kit, home = self._copy_kit()
        proc = self._run(kit, home, ["--dry-run"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for cid in CHECKPOINT_ANY_RE.findall(read(AGENTS)):
            with self.subTest(checkpoint=cid):
                self.assertRegex(proc.stdout, r"CHECKPOINT %s\b" % cid)


if __name__ == "__main__":
    unittest.main()
