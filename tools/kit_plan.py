#!/usr/bin/env python3
"""kit_plan.py: the reference planner behind every AGENTS.md checkpoint.

    python3 tools/kit_plan.py [--dry-run] [--json] [OPTIONS]
    python3 tools/kit_plan.py --apply --approved <sha256> [--choose GROUP=ITEM ...]
                              [--json] [OPTIONS]

Options:
    --kit DIR        the kit folder (default: $KIT_HOME, else the folder above tools/)
    --config PATH    your kit.config.yaml (default: $KIT_CONFIG, then
                     $KIT_HOME/kit.config.yaml, else the built-in defaults of
                     kit.config.example.yaml)
    --state PATH     the existing-setup description: a tests/fixtures/existing-setup
                     case YAML or a discovered-state JSON with the same keys
                     (agents, skills, routines, memory, files, kit_facts); an
                     `expect` block is ignored (default: an empty setup)
    --setup-dir DIR  where your Grok Bot's items are mirrored as files:
                     agents/<n>/AGENT.md, skills/<n>/SKILL.md, routines/<n>.md,
                     memory/<slug>.md (default: $KIT_SETUP_DIR, else $HOME/grok-setup)
    --home DIR       the root of the state's `files` and of the relative keys of
                     second_brain.marketing_links (default: $HOME)
    --dry-run        compute and print the plan, write nothing (the default)
    --apply          write the add and link items of the approved plan, only
                     where nothing exists yet; needs --approved
    --approved SHA   the `plan sha256` of the dry run you approved
    --choose G=ID    pick option ID of choice group G (repeatable); without a
                     choice the options of a group are never applied
    --json           print the plan (or the apply result) as one JSON document

The contract is tools/KIT-PLAN-SPEC.md; the harness in tests/overwrite/ tests
exactly that. The planner reads kit.config.yaml, the state, the setup dir, the
home and the second-brain home; it never reads dot files, *.env, credential
files or anything outside those places, and it never writes into the kit.

Exit codes: 0 = done; 2 = usage error (bad flags, --dry-run with --apply,
--apply without --approved, unreadable config or state, a bad --choose,
`existing_setup.mode: fresh` on a non-empty setup); 3 = the plan changed since
the approval; 4 = a planned target already exists (nothing was written).
Stdlib only, Python 3.9+.
"""

import argparse
import fnmatch
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import sys

sys.dont_write_bytecode = True  # loading sb must never leave bytecode in the kit

SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PLAN_CHANGED = 3
EXIT_TARGET_EXISTS = 4

CHECKPOINT_RE = re.compile(r"\*\*CHECKPOINT (\d+[a-z]?)")
PHASE_RE = re.compile(r"^## Phase (\d+): (.+?)\s*$", re.MULTILINE)
STEP_RE = re.compile(r"^\d+\.\s+(.*\S)\s*$")
BULLET_RE = re.compile(r"^- (?:\*\*)?([^:*]+?)(?:\*\*)?(?::|$)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# config key -> template folder under grok-skills/
SKILL_KEYS = (
    ("sb_lookup", "sb-lookup"),
    ("content_calendar", "content-calendar-planner"),
    ("comms_template", "comms-template-writer"),
)
REVIEW_SKILLS = ("pr-review", "repo-health-check")
SIZING_ROUTINE = "dev-lead-sizing"
DEV_LEAD_TEMPLATE = os.path.join("agents", "dev-lead", "AGENT.md")
DEV_LEAD_SKILLS_DIR = os.path.join("agents", "dev-lead", "skills")
MORNING_BRIEF_TEMPLATE = os.path.join("routines", "morning-brief.md")
SB_TEMPLATE_DIR = "second-brain"
SB_TEMPLATE_SKIP_DIRS = ("bin", "tests", "__pycache__")
SB_TEMPLATE_SKIP_FILES = ("DOCTOR-SPEC.md",)
DENY_NAME_GLOBS = ("*.env", ".env*", "*secret*", "*token*", "*credential*")
NEGATIONS = frozenset(("never", "not", "no", "dont", "doesnt", "don", "doesn"))
CODING_WORDS = ("code", "dev", "website", "site", "repo", "programm")
BRIEF_WORDS = ("daily", "morning", "brief", "summar")
NOT_BRIEF_GLOBS = ("*sizing*", "*keep-alive*")
DEFAULT_SUFFIX = "-kit"
DEFAULT_PLUGINS = ("ai-baseline",)


class UsageError(Exception):
    """Exit 2: nothing was written."""


# ---------------------------------------------------------------- small YAML reader (state files)

class YamlError(UsageError):
    pass


_TRUE, _FALSE, _NULL = ("true", "True", "TRUE"), ("false", "False", "FALSE"), ("null", "Null", "NULL", "~", "")
_INT_RE = re.compile(r"^-?(0|[1-9][0-9]*)$")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "0": "\0"}


def _plain(token):
    token = token.strip()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    if token in _NULL:
        return None
    if _INT_RE.match(token):
        return int(token)
    return token


class _Flow:
    """One flow value (scalar, {..} or [..], nested) from `text` at `pos`."""

    def __init__(self, text, lineno):
        self.text, self.lineno = text, lineno

    def error(self, reason):
        return YamlError("state line %d: %s" % (self.lineno, reason))

    def ws(self, i):
        while i < len(self.text) and self.text[i] in " \t":
            i += 1
        return i

    def value(self, i, stops):
        i = self.ws(i)
        if i >= len(self.text):
            raise self.error("value expected")
        ch = self.text[i]
        if ch == "{":
            return self.mapping(i + 1)
        if ch == "[":
            return self.sequence(i + 1)
        if ch in "\"'":
            return self.quoted(i)
        j = i
        while j < len(self.text) and self.text[j] not in stops:
            if self.text[j] == "#" and self.text[j - 1] in " \t":
                break
            j += 1
        return _plain(self.text[i:j]), j

    def quoted(self, i):
        quote, out, i = self.text[i], [], i + 1
        while i < len(self.text):
            ch = self.text[i]
            if ch == quote:
                if quote == "'" and self.text[i + 1:i + 2] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), i + 1
            if ch == "\\" and quote == '"':
                esc = self.text[i + 1:i + 2]
                if esc not in _ESCAPES:
                    raise self.error("unsupported escape")
                out.append(_ESCAPES[esc])
                i += 2
                continue
            out.append(ch)
            i += 1
        raise self.error("unterminated quoted string")

    def key(self, i):
        i = self.ws(i)
        if i < len(self.text) and self.text[i] in "\"'":
            key, i = self.quoted(i)
        else:
            j = i
            while j < len(self.text) and self.text[j] not in ":,}":
                j += 1
            key, i = self.text[i:j].strip(), j
        i = self.ws(i)
        if i >= len(self.text) or self.text[i] != ":" or not key:
            raise self.error("'key:' expected")
        return key, i + 1

    def mapping(self, i):
        out = {}
        i = self.ws(i)
        if self.text[i:i + 1] == "}":
            return out, i + 1
        while True:
            key, i = self.key(i)
            if key in out:
                raise self.error("duplicate key")
            out[key], i = self.value(i, ",}")
            i = self.ws(i)
            if self.text[i:i + 1] == ",":
                i = self.ws(i + 1)
                if self.text[i:i + 1] == "}":
                    return out, i + 1
                continue
            if self.text[i:i + 1] == "}":
                return out, i + 1
            raise self.error("',' or '}' expected")

    def sequence(self, i):
        out = []
        i = self.ws(i)
        if self.text[i:i + 1] == "]":
            return out, i + 1
        while True:
            value, i = self.value(i, ",]")
            out.append(value)
            i = self.ws(i)
            if self.text[i:i + 1] == ",":
                i = self.ws(i + 1)
                if self.text[i:i + 1] == "]":
                    return out, i + 1
                continue
            if self.text[i:i + 1] == "]":
                return out, i + 1
            raise self.error("',' or ']' expected")

    def whole(self):
        value, i = self.value(0, "")
        i = self.ws(i)
        if i < len(self.text) and self.text[i] != "#":
            raise self.error("trailing text after the value")
        return value


def _yaml_lines(text):
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        if n == 1 and raw.startswith("---"):
            continue
        quote, cut = None, len(raw)
        for i, ch in enumerate(raw):
            if quote:
                quote = None if ch == quote else quote
            elif ch in "\"'":
                quote = ch
            elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
                cut = i
                break
        line = raw[:cut].rstrip()
        if not line.strip():
            continue
        lead = line[:len(line) - len(line.lstrip())]
        if "\t" in lead:
            raise YamlError("state line %d: tabs in indentation" % n)
        out.append((n, len(lead), line.strip()))
    return out


def _yaml_block(lines, i, indent):
    if i >= len(lines):
        raise YamlError("state: block expected at end of file")
    if lines[i][2] == "-" or lines[i][2].startswith("- "):
        return _yaml_list(lines, i, indent)
    return _yaml_mapping(lines, i, indent)


def _yaml_list(lines, i, indent):
    out = []
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent or not (text == "-" or text.startswith("- ")):
            raise YamlError("state line %d: list item expected" % lineno)
        rest = text[1:].strip()
        if not rest:
            raise YamlError("state line %d: empty list item" % lineno)
        if re.match(r"^[A-Za-z_][^:{}\[\],]*:(\s|$)", rest):
            raise YamlError("state line %d: block mappings inside a list are not supported" % lineno)
        out.append(_Flow(rest, lineno).whole())
        i += 1
    return out, i


def _yaml_mapping(lines, i, indent):
    out = {}
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError("state line %d: unexpected indentation" % lineno)
        if text.startswith("- "):
            raise YamlError("state line %d: list item where a key was expected" % lineno)
        key, j = _Flow(text, lineno).key(0)
        rest = text[j:].strip()
        if key in out:
            raise YamlError("state line %d: duplicate key" % lineno)
        if rest:
            out[key] = _Flow(rest, lineno).whole()
            i += 1
        elif i + 1 < len(lines) and lines[i + 1][1] > ind:
            out[key], i = _yaml_block(lines, i + 1, lines[i + 1][1])
        elif i + 1 < len(lines) and lines[i + 1][1] == ind and lines[i + 1][2].startswith("- "):
            out[key], i = _yaml_list(lines, i + 1, ind)
        else:
            out[key] = None
            i += 1
    return out, i


def load_yaml(text):
    lines = _yaml_lines(text)
    if not lines:
        return {}
    value, i = _yaml_block(lines, 0, lines[0][1])
    if i < len(lines):
        raise YamlError("state line %d: unexpected indentation" % lines[i][0])
    return value


# ---------------------------------------------------------------- helpers

def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def fact_slug(fact):
    return re.sub(r"[^a-z0-9]+", "-", fact.lower()).strip("-")


def fact_tokens(fact):
    """Folded tokens: lower case, apostrophes dropped, other punctuation split."""
    return tuple(t.replace("'", "") for t in re.findall(r"[0-9a-z']+", fact.lower()) if t.replace("'", ""))


def fact_core(tokens):
    return tuple(t for t in tokens if t not in NEGATIONS)


def is_brief_like(name, schedule):
    """Her routine reads as a daily summary: a brief word in its name or
    schedule, and it is not a sizing or keep-alive routine. A bare HH:MM time
    is not enough."""
    if any(fnmatch.fnmatchcase(name.lower(), g) for g in NOT_BRIEF_GLOBS):
        return False
    for token in re.findall(r"[0-9a-z]+", ("%s %s" % (name, schedule or "")).lower()):
        if token.startswith(BRIEF_WORDS):
            return True
    return False


def mentions_code(text):
    for token in re.findall(r"[0-9a-z]+", str(text or "").lower()):
        if token.startswith(CODING_WORDS):
            return True
    return False


def denied_name(name):
    return name.startswith(".") or any(fnmatch.fnmatchcase(name.lower(), g) for g in DENY_NAME_GLOBS)


def listdir_safe(path):
    try:
        return sorted(n for n in os.listdir(path) if not denied_name(n))
    except OSError:
        return []


def first_line(path):
    try:
        for line in read_text(path).splitlines():
            if line.strip():
                return line.strip()
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def field_of(path, label):
    """The value of a `Label: value` line in one of her mirrored files."""
    try:
        for line in read_text(path).splitlines():
            if line.lower().startswith(label.lower() + ":"):
                return line.split(":", 1)[1].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def free_name(name, taken, suffix):
    if name not in taken:
        return name
    candidate = name + suffix
    n = 2
    while candidate in taken:
        candidate = "%s%s-%d" % (name, suffix, n)
        n += 1
    return candidate


def cfg(config, *keys, **kw):
    node = config
    for key in keys:
        if not isinstance(node, dict) or node.get(key) is None:
            return kw.get("default")
        node = node[key]
    return node


def deep_merge(base, over):
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        elif value is not None:
            out[key] = value
    return out


def relative_to(path, root):
    """`path` relative to `root` when it lies inside it, else its file name:
    the plan never shows an absolute path."""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = None
    if rel is None or rel.startswith(".."):
        return os.path.basename(path.rstrip("/")) or path
    return rel.replace(os.sep, "/")


def load_sb(kit):
    path = os.path.join(kit, "second-brain", "bin", "sb")
    if not os.path.isfile(path):
        raise UsageError("the kit has no second-brain/bin/sb")
    loader = importlib.machinery.SourceFileLoader("kit_plan_sb", path)
    spec = importlib.util.spec_from_loader("kit_plan_sb", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# ---------------------------------------------------------------- the existing setup

class Existing:
    """What she already has: the state plus the files mirrored in the setup
    dir. An item exists when either names it."""

    def __init__(self, state, setup, home):
        self.agents = {}      # name -> {"role": str, "skills": [..]}
        self.skills = set()
        self.routines = {}    # name -> schedule
        self.facts = []       # her memory facts (text)
        self.files = []       # her files, home-relative
        self.kit_facts = []
        for agent in state.get("agents") or []:
            if isinstance(agent, dict) and agent.get("name"):
                self.agents[str(agent["name"])] = {
                    "role": str(agent.get("role") or ""),
                    "skills": [str(s) for s in (agent.get("skills") or [])],
                }
                self.skills.update(self.agents[str(agent["name"])]["skills"])
        for skill in state.get("skills") or []:
            if isinstance(skill, dict) and skill.get("name"):
                self.skills.add(str(skill["name"]))
            elif isinstance(skill, str):
                self.skills.add(skill)
        for routine in state.get("routines") or []:
            if isinstance(routine, dict) and routine.get("name"):
                self.routines[str(routine["name"])] = str(routine.get("schedule") or "")
        for fact in state.get("memory") or []:
            if isinstance(fact, str) and fact.strip():
                self.facts.append(fact.strip())
        for entry in state.get("files") or []:
            rel = entry.get("path") if isinstance(entry, dict) else entry
            if isinstance(rel, str) and rel:
                self.files.append(rel.replace(os.sep, "/"))
        for fact in state.get("kit_facts") or []:
            if isinstance(fact, str) and fact.strip():
                self.kit_facts.append(fact.strip())
        self.setup, self.home = setup, home
        self.read_setup_dir()

    def read_setup_dir(self):
        agents = os.path.join(self.setup, "agents")
        for name in listdir_safe(agents):
            path = os.path.join(agents, name, "AGENT.md")
            if os.path.isfile(path) and name not in self.agents:
                skills = [s.strip() for s in field_of(path, "Skills").split(",") if s.strip()]
                self.agents[name] = {"role": field_of(path, "Role"), "skills": skills}
                self.skills.update(skills)
        skills = os.path.join(self.setup, "skills")
        for name in listdir_safe(skills):
            if os.path.isfile(os.path.join(skills, name, "SKILL.md")):
                self.skills.add(name)
        routines = os.path.join(self.setup, "routines")
        for name in listdir_safe(routines):
            if name.endswith(".md") and os.path.isfile(os.path.join(routines, name)):
                self.routines.setdefault(name[:-3], field_of(os.path.join(routines, name), "Schedule"))
        memory = os.path.join(self.setup, "memory")
        known = {fact_tokens(f) for f in self.facts}
        for name in listdir_safe(memory):
            if name.endswith(".md") and os.path.isfile(os.path.join(memory, name)):
                fact = first_line(os.path.join(memory, name))
                if fact and fact_tokens(fact) not in known:
                    self.facts.append(fact)
                    known.add(fact_tokens(fact))

    def is_empty(self):
        return not (self.agents or self.skills or self.routines or self.facts or self.files)

    def files_under(self, folder):
        """Her files under a home-relative folder: the state's entries plus
        what is on disk (names only; contents are never read)."""
        folder = folder.strip("/")
        found = [f for f in self.files if f.startswith(folder + "/")]
        root = os.path.join(self.home, folder)
        if os.path.isdir(root) and not os.path.islink(root):
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if not denied_name(d)
                                     and not os.path.islink(os.path.join(dirpath, d)))
                for name in sorted(filenames):
                    if denied_name(name):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, name), self.home).replace(os.sep, "/")
                    found.append(rel)
        return sorted(set(found))


# ---------------------------------------------------------------- the planner

class Planner:
    def __init__(self, args, environ):
        self.environ = environ
        self.kit = os.path.abspath(args.kit or environ.get("KIT_HOME")
                                   or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if not os.path.isfile(os.path.join(self.kit, "AGENTS.md")):
            raise UsageError("not a kit folder (no AGENTS.md): --kit")
        home = args.home or environ.get("HOME")
        if not home:
            raise UsageError("no --home and no $HOME")
        self.home = os.path.abspath(home)
        self.setup = os.path.abspath(args.setup_dir or environ.get("KIT_SETUP_DIR")
                                     or os.path.join(self.home, "grok-setup"))
        self.sb = load_sb(self.kit)
        self.config_path = self.find_config(args.config)
        self.config = self.load_config()
        self.settings = self.load_settings()
        self.sb_home = self.settings["home"]
        self.state = self.load_state(args.state)
        self.existing = Existing(self.state, self.setup, self.home)
        mode = cfg(self.config, "existing_setup", "mode", default="integrate")
        if mode not in ("integrate", "fresh"):
            raise UsageError("existing_setup.mode must be integrate or fresh")
        if mode == "fresh" and not self.existing.is_empty():
            raise UsageError("existing_setup.mode is fresh but the setup is not empty: use integrate")
        self.suffix = str(cfg(self.config, "kit", "collision_suffix", default=DEFAULT_SUFFIX))
        agents_text = read_text(os.path.join(self.kit, "AGENTS.md"))
        self.checkpoints = CHECKPOINT_RE.findall(agents_text)
        self.phase_titles = dict((n, t) for n, t in PHASE_RE.findall(agents_text))
        self.items = []
        self.ids = set()

    # -- inputs

    def find_config(self, flag):
        if flag:
            if not os.path.isfile(flag):
                raise UsageError("config file not found (--config)")
            return os.path.abspath(flag)
        if self.environ.get("KIT_CONFIG"):
            if not os.path.isfile(self.environ["KIT_CONFIG"]):
                raise UsageError("config file not found ($KIT_CONFIG)")
            return os.path.abspath(self.environ["KIT_CONFIG"])
        for candidate in (os.path.join(self.kit, "kit.config.yaml"),
                          os.path.join(self.home, "grok-kit", "kit.config.yaml")):
            if os.path.isfile(candidate):
                return candidate
        return None

    def load_config(self):
        try:
            defaults = self.sb.parse_config_text(read_text(os.path.join(self.kit, "kit.config.example.yaml")))
            if self.config_path is None:
                return defaults
            return deep_merge(defaults, self.sb.parse_config_text(read_text(self.config_path)))
        except (OSError, UnicodeDecodeError, self.sb.ConfigError) as exc:
            raise UsageError("config cannot be read: %s" % exc)

    def sb_environ(self):
        environ = dict(self.environ)
        environ.setdefault("KIT_HOME", self.kit)
        environ.setdefault("HOME", self.home)
        return environ

    def load_settings(self):
        try:
            return self.sb.load_settings(self.config_path, self.sb_environ())
        except self.sb.ConfigError as exc:
            raise UsageError("second_brain config: %s" % exc)

    def load_state(self, path):
        if not path:
            return {}
        if not os.path.isfile(path):
            raise UsageError("state file not found (--state)")
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError):
            raise UsageError("state file cannot be read as UTF-8 text")
        try:
            if path.endswith(".json") or text.lstrip().startswith("{"):
                data = json.loads(text)
            else:
                data = load_yaml(text)
        except ValueError as exc:
            raise UsageError("state file is malformed: %s" % exc)
        if not isinstance(data, dict):
            raise UsageError("state file must hold a mapping")
        data.pop("expect", None)
        return data

    def expand(self, value):
        def sub(m):
            name = m.group(1)
            if name == "KIT_HOME":
                return self.environ.get("KIT_HOME") or self.kit
            return self.environ.get(name, m.group(0))
        path = VAR_RE.sub(sub, str(value))
        if path == "~" or path.startswith("~/"):
            path = self.home + path[1:]
        return path

    # -- items

    def add_item(self, item):
        for key in ("id", "type", "kind", "root", "target", "reason", "checkpoint"):
            if not item.get(key):
                raise RuntimeError("planner bug: item without %s" % key)
        if item["id"] in self.ids:
            raise RuntimeError("planner bug: duplicate item id %s" % item["id"])
        if item["checkpoint"] not in self.checkpoints:
            raise RuntimeError("planner bug: unknown checkpoint %s" % item["checkpoint"])
        self.ids.add(item["id"])
        self.items.append(item)
        return item

    def item(self, type_, kind, root, target, reason, checkpoint, **extra):
        item = {"id": "%s.%s.%s" % (kind, type_, extra.pop("id_tail", target.rstrip("/"))),
                "type": type_, "kind": kind, "root": root, "target": target,
                "reason": reason, "checkpoint": checkpoint}
        item.update(extra)
        return self.add_item(item)

    def root_path(self, root):
        return {"sb": self.sb_home, "setup": self.setup, "home": self.home, "kit": self.kit}[root]

    def target_path(self, item):
        return os.path.join(self.root_path(item["root"]), item["target"].rstrip("/"))

    def exists(self, root, target):
        return os.path.lexists(os.path.join(self.root_path(root), target.rstrip("/")))

    def kit_rel(self, path):
        return relative_to(path, self.kit)

    # -- phases

    def build(self):
        self.phase_1_state_note()
        self.phase_2_config()
        self.phase_3_second_brain()
        self.phase_4_skills_and_memory()
        self.phase_5_morning_brief()
        self.phase_6_plugins()
        self.phase_7_folio()
        self.phase_8_dev_lead()
        self.phase_9_runner()
        self.phase_10_verify()
        return {
            "kit_plan": SCHEMA_VERSION,
            "mode": "dry-run",
            "checkpoints": list(self.checkpoints),
            "items": self.items,
            "sha256": plan_sha256(self.items),
        }

    def phase_1_state_note(self):
        note = self.expand(cfg(self.config, "existing_setup", "current_state_note",
                               default="${KIT_HOME}/onboarding/current-state.md"))
        target = self.kit_rel(note)
        if os.path.isfile(note):
            self.item("skip", "state_note", "kit", target, "the current-state note exists; nothing to write", "1",
                      id_tail="current")
        else:
            self.item("report", "state_note", "kit", target,
                      "after your OK your Grok Bot saves the confirmed current-state note here", "1",
                      id_tail="current")

    def phase_2_config(self):
        if self.config_path:
            self.item("skip", "config", "kit", "kit.config.yaml", "kit.config.yaml exists; the kit never overwrites it", "2")
        else:
            self.item("report", "config", "kit", "kit.config.yaml",
                      "no kit.config.yaml yet: after your OK your Grok Bot writes it from kit.config.example.yaml", "2")

    def template_tree(self):
        """(folders, files) of the second-brain template, sb-relative, limited
        to the configured channels."""
        root = os.path.join(self.kit, SB_TEMPLATE_DIR)
        channels = list(self.settings["channels"])
        template_channels = [n for n in listdir_safe(root)
                             if os.path.isdir(os.path.join(root, n)) and n not in SB_TEMPLATE_SKIP_DIRS]
        folders, files = [], []
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
            dirnames[:] = sorted(d for d in dirnames if not denied_name(d) and d not in SB_TEMPLATE_SKIP_DIRS)
            if rel == ".":
                dirnames[:] = [d for d in dirnames if d not in template_channels or d in channels]
            else:
                folders.append(rel + "/")
            for name in sorted(filenames):
                if denied_name(name) or (rel == "." and name in SB_TEMPLATE_SKIP_FILES) or not name.endswith(".md"):
                    continue
                files.append(name if rel == "." else rel + "/" + name)
        for channel in channels:
            if channel not in template_channels:
                folders.append(channel + "/")
        return sorted(folders), files

    def folder_channel(self, folder):
        best, best_len = None, -1
        for prefix, channel in self.settings["path_defaults"].items():
            prefix = prefix.strip("/") + "/"
            if (folder.rstrip("/") + "/").startswith(prefix) and len(prefix) > best_len:
                best, best_len = channel, len(prefix)
        return best or folder.strip("/").split("/")[0]

    def phase_3_second_brain(self):
        folders, files = self.template_tree()
        router = self.settings["router_file"].replace(os.sep, "/")
        for folder in folders:
            if self.exists("sb", folder):
                self.item("skip", "folder", "sb", folder, "you already have this folder; nothing is renamed", "3")
            else:
                self.item("add", "folder", "sb", folder, "missing channel folder from the second-brain template", "3",
                          source=SB_TEMPLATE_DIR + "/" + folder)
        for rel in files:
            kind, target = "note", rel
            if rel == "ROUTER.md":
                kind, target = "router", router
            if self.exists("sb", target):
                self.item("skip", kind, "sb", target, "exists in your second brain; your file wins", "3")
            else:
                self.item("add", kind, "sb", target, "seed note from the second-brain template (synthetic example)"
                          if kind == "note" else "the ROUTER.md template; your rows replace the synthetic ones", "3",
                          name=os.path.basename(rel)[:-3], source=SB_TEMPLATE_DIR + "/" + rel)
        self.marketing_links()
        self.doctor_report()

    def marketing_links(self):
        links = cfg(self.config, "second_brain", "marketing_links", default={})
        if not isinstance(links, dict):
            raise UsageError("second_brain.marketing_links must be a mapping")
        for her_folder in sorted(links):
            kit_folder = str(links[her_folder]).strip("/")
            if not kit_folder:
                raise UsageError("second_brain.marketing_links maps to an empty folder")
            channel = self.folder_channel(kit_folder)
            for her_file in self.existing.files_under(str(her_folder)):
                stem = os.path.basename(her_file).rsplit(".", 1)[0] if "." in os.path.basename(her_file) \
                    else os.path.basename(her_file)
                target = "%s/%s.link.md" % (kit_folder, stem)
                if self.exists("sb", target):
                    self.item("skip", "note", "sb", target, "the link note exists already", "3", links_to=her_file)
                else:
                    self.item("link", "note", "sb", target,
                              "links your existing file from the kit's %s folder; it is never copied or moved" % channel,
                              "3", links_to=her_file, channel=channel)

    def doctor_report(self):
        findings = []
        try:
            settings = self.settings
            if settings["name_hashes"]:  # as `sb --doctor`: the scan key, read here and kept out of the plan
                settings = dict(settings, name_key=self.sb.read_scan_key(self.sb_environ()))
            out = io.StringIO()
            self.sb.doctor(settings, out)
            for line in out.getvalue().splitlines():
                m = re.match(r"^FAIL (\d+) (.+)$", line)
                if not m:
                    continue
                path = os.path.join(self.sb_home, m.group(2))
                if os.path.isfile(path) and not os.path.islink(path):
                    findings.append({"path": m.group(2), "check": int(m.group(1))})
        except Exception as exc:  # the doctor never stops the plan
            findings, note = [], " (sb --doctor could not run: %s)" % type(exc).__name__
        else:
            note = ""
        findings.sort(key=lambda f: (f["path"], f["check"]))
        self.item("report", "doctor", "sb", self.settings["router_file"].replace(os.sep, "/"),
                  "sb --doctor on your existing notes: %d finding(s) for you to decide; your files are never edited%s"
                  % (len(findings), note), "3", findings=findings, id_tail="existing-notes")

    def skill_steps(self, path):
        steps, in_steps = [], False
        for line in read_text(path).splitlines():
            if line.startswith("# Steps"):
                in_steps = True
                continue
            if in_steps and line.startswith("#"):
                break
            m = STEP_RE.match(line)
            if in_steps and m:
                steps.append(m.group(1))
        return steps

    def phase_4_skills_and_memory(self):
        skills = self.existing.skills
        for key, template in SKILL_KEYS:
            source = "grok-skills/%s/SKILL.md" % template
            if not os.path.isfile(os.path.join(self.kit, source)):
                continue
            name = str(cfg(self.config, "skills", key, default=template))
            if name in skills:
                group = "skill:" + name
                self.item("extend", "skill", "setup", "skills/%s/SKILL.md" % name,
                          "you already have a skill named %s: yours stays, these steps are proposed as additions" % name,
                          "4", name=name, additions=self.skill_steps(os.path.join(self.kit, source)), choice=group)
                new = free_name(name, skills, self.suffix)
                self.item("add", "skill", "setup", "skills/%s/SKILL.md" % new,
                          "or add the kit's skill next to yours under the collision suffix", "4",
                          name=new, source=source, choice=group)
            else:
                self.item("add", "skill", "setup", "skills/%s/SKILL.md" % name,
                          "you have nothing similar; added from the kit", "4", name=name, source=source)
        self.memory_facts()

    def memory_facts(self):
        hers = {}
        for fact in self.existing.facts:
            hers.setdefault(fact_tokens(fact), fact)
        cores = {}
        for tokens, fact in hers.items():
            cores.setdefault(fact_core(tokens), []).append((tokens, fact))
        seen = set()
        for fact in self.existing.kit_facts:
            tokens = fact_tokens(fact)
            if not tokens or tokens in seen:
                continue
            seen.add(tokens)
            slug = fact_slug(fact)
            target = "memory/%s.md" % slug
            if tokens in hers:
                self.item("skip", "memory", "setup", target, "duplicate: you already have this fact", "4", fact=fact,
                          id_tail=slug)
                continue
            contradiction = [h for t, h in cores.get(fact_core(tokens), []) if t != tokens]
            if contradiction:
                self.item("report", "memory", "setup", target,
                          "contradiction: the kit's fact negates one of yours; yours stays, nothing is added", "4",
                          fact=fact, contradicts=contradiction[0], id_tail=slug)
            elif self.exists("setup", target):
                self.item("skip", "memory", "setup", target, "duplicate: a memory file with this name exists", "4",
                          fact=fact, id_tail=slug)
            else:
                self.item("add", "memory", "setup", target, "a new fact the kit's skills rely on", "4", fact=fact,
                          id_tail=slug)

    def brief_sections(self):
        sections = []
        for line in read_text(os.path.join(self.kit, MORNING_BRIEF_TEMPLATE)).splitlines():
            m = BULLET_RE.match(line)
            if m and m.group(1).strip() not in ("Name", "Enabled", "Schedule"):
                sections.append(m.group(1).strip())
        return sections

    def phase_5_morning_brief(self):
        brief = cfg(self.config, "routines", "morning_brief", default={})
        name = str(brief.get("name") or "morning-brief")
        merge_into = str(brief.get("merge_into") or "")
        routines = self.existing.routines
        daily = [n for n in sorted(routines) if is_brief_like(n, routines[n])]
        target_routine = merge_into if merge_into in routines else (daily[0] if daily else None)
        if target_routine:
            self.item("merge", "routine", "setup", "routines/%s.md" % target_routine,
                      "you already have a daily routine: the kit's sections are merged into it, never a second routine",
                      "5a", into=target_routine, sections=self.brief_sections(), id_tail=target_routine)
            enable_target = "routines/%s.md" % target_routine
        else:
            new = free_name(name, set(routines), self.suffix)
            self.item("add", "routine", "setup", "routines/%s.md" % new,
                      "no daily summary routine found: created disabled at %s %s" % (brief.get("time") or "07:30",
                                                                                     cfg(self.config, "kit", "timezone", default="UTC")),
                      "5a", name=new, source=MORNING_BRIEF_TEMPLATE.replace(os.sep, "/"), enabled=False, id_tail=new)
            enable_target = "routines/%s.md" % new
        self.item("report", "routine", "setup", enable_target,
                  "a separate OK sets routines.morning_brief.enabled: true; until then it never runs", "5b",
                  id_tail="enable-morning-brief")

    def phase_6_plugins(self):
        plugins = cfg(self.config, "accelerator", "plugins", default=list(DEFAULT_PLUGINS))
        if not isinstance(plugins, list):
            raise UsageError("accelerator.plugins must be a list")
        marketplace = self.kit_rel(self.expand(cfg(self.config, "accelerator", "marketplace_path",
                                                   default="${KIT_HOME}/vendor/accelerator")))
        ordered = [p for p in plugins if p == "ai-baseline"] + [p for p in plugins if p != "ai-baseline"]
        for plugin in ordered:
            self.item("report", "plugin", "kit", marketplace.rstrip("/") + "/",
                      "after your OK: /plugin install %s@accelerator from the local marketplace; "
                      "plugins you already have are skipped" % plugin, "6", name=str(plugin), id_tail=str(plugin))

    def phase_7_folio(self):
        source = self.kit_rel(self.expand(cfg(self.config, "folio", "source", default="${KIT_HOME}/vendor/folio")))
        self.item("report", "folio", "kit", source.rstrip("/") + "/",
                  "optional: install Folio with uv, listening on 127.0.0.1 only; an existing install is kept", "7",
                  id_tail="folio")
        self.item("report", "folio", "kit", "EXTERNAL-DEPENDENCIES.md",
                  "optional: Backlog.md %s from npm with the pinned checksum, only if you use task files"
                  % cfg(self.config, "folio", "backlog_version", default="1.53.0"), "7", id_tail="backlog")

    def dev_lead_skill_names(self):
        names, in_table = [], False
        for line in read_text(os.path.join(self.kit, DEV_LEAD_TEMPLATE)).splitlines():
            if line.startswith("## Skills"):
                in_table = True
                continue
            if in_table and line.startswith("## "):
                break
            if in_table and line.startswith("| `"):
                names.append(BACKTICK_RE.search(line).group(1))
        return names

    def phase_8_dev_lead(self):
        dev = cfg(self.config, "agents", "dev_lead", default={})
        wanted = str(dev.get("name") or "dev-lead")
        extend_named = str(dev.get("extend_existing") or "")
        agents = self.existing.agents
        coding = [n for n in sorted(agents) if mentions_code(n) or mentions_code(agents[n]["role"])]
        hers = extend_named if extend_named in agents else (coding[0] if coding else None)
        group = "agent:" + wanted if hers else None
        hours = dev.get("sizing_interval_hours") or 4
        if hers:
            lacking = [s for s in REVIEW_SKILLS if s not in self.existing.skills]
            routines = [SIZING_ROUTINE] if SIZING_ROUTINE not in self.existing.routines else []
            self.item("extend", "agent", "setup", "agents/%s/AGENT.md" % hers,
                      "you already have a coding agent: extend it with the kit's missing skills and the sizing routine; "
                      "its name, persona and memory stay", "8a", name=hers, add_skills=lacking, add_routines=routines,
                      choice=group, id_tail=hers)
        new = free_name(wanted, set(agents), self.suffix)
        create = self.item("add", "agent", "setup", "agents/%s/AGENT.md" % new,
                           ("or create the kit's dev-lead agent next to yours under a free name"
                            if hers else "no dev or coding agent found: created from the template after your OK"),
                           "8a", name=new, source=DEV_LEAD_TEMPLATE.replace(os.sep, "/"), id_tail=new,
                           **({"choice": group} if hers else {}))
        dependant = {"choice": group, "option": create["id"]} if hers else {}
        for skill in self.dev_lead_skill_names():
            source = os.path.join(DEV_LEAD_SKILLS_DIR, skill, "SKILL.md")
            if not os.path.isfile(os.path.join(self.kit, source)):
                continue  # this kit ships no copy of the skill: nothing to add
            if skill in self.existing.skills:
                self.item("skip", "skill", "setup", "skills/%s/SKILL.md" % skill,
                          "you already have this skill; yours is reused", "8a", name=skill, id_tail=skill)
            else:
                self.item("add", "skill", "setup", "skills/%s/SKILL.md" % skill,
                          "a skill the created agent needs", "8a", name=skill,
                          source=source.replace(os.sep, "/"), id_tail=skill, **dependant)
        # Hers when she has it, the kit's otherwise: never a suffixed name.
        sizing = SIZING_ROUTINE
        if SIZING_ROUTINE in self.existing.routines:
            self.item("skip", "routine", "setup", "routines/%s.md" % SIZING_ROUTINE,
                      "you already have the sizing routine", "8a", id_tail=SIZING_ROUTINE)
        else:
            self.item("add", "routine", "setup", "routines/%s.md" % sizing,
                      "the sizing and keep-alive routine, every %s hours, created disabled" % hours, "8a",
                      name=sizing, source=DEV_LEAD_TEMPLATE.replace(os.sep, "/"), enabled=False, id_tail=sizing,
                      **dependant)
        self.item("report", "routine", "setup", "routines/%s.md" % sizing,
                  "a separate OK enables the sizing routine; until then it never runs", "8b",
                  id_tail="enable-" + sizing)

    def phase_9_runner(self):
        config = self.kit_rel(self.expand(cfg(self.config, "runner", "config", default="${KIT_HOME}/runner/router.json")))
        if self.exists("kit", config):
            self.item("skip", "runner", "kit", config, "the runner config exists; it is yours", "9a", id_tail="config")
        else:
            self.item("report", "runner", "kit", config,
                      "after you read runner/TERMS-NOTICE.md and OK 9a, your Grok Bot copies "
                      "runner/runner.config.example.json here with runner.enabled: false; no process starts", "9a",
                      id_tail="config")
        self.item("report", "runner", "kit", config,
                  "a separate, explicit OK sets runner.enabled: true and starts the runner; without it, it never runs",
                  "9b", id_tail="enable")

    def phase_10_verify(self):
        note = self.expand(cfg(self.config, "existing_setup", "current_state_note",
                               default="${KIT_HOME}/onboarding/current-state.md"))
        self.item("report", "state_note", "kit", self.kit_rel(note),
                  "sb --doctor must be clean on the kit files; the summary of what was added, extended, linked "
                  "or skipped and the updated note are shown; after your OK the note is saved", "10", id_tail="updated")

    # -- apply

    def writing_items(self, plan, choices):
        groups = {}
        for item in plan["items"]:
            if item.get("choice"):
                groups.setdefault(item["choice"], []).append(item)
        for group, chosen in choices.items():
            if group not in groups:
                raise UsageError("--choose names an unknown choice group")
            options = [i["id"] for i in groups[group] if "option" not in i]
            if chosen not in options:
                raise UsageError("--choose names an item that is not an option of its group")
        out = []
        for item in plan["items"]:
            if item["type"] not in ("add", "link") or item["root"] not in ("sb", "setup"):
                continue
            group = item.get("choice")
            if group:
                chosen = choices.get(group)
                if not chosen or (item.get("option", item["id"]) != chosen):
                    continue
            out.append(item)
        return out

    def apply(self, plan, choices):
        items = self.writing_items(plan, choices)
        for item in items:
            if os.path.lexists(self.target_path(item)):
                return EXIT_TARGET_EXISTS, []
        written = []
        for item in items:
            path = self.target_path(item)
            if item["kind"] == "folder":
                os.makedirs(path)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "x", encoding="utf-8", newline="") as fh:
                    fh.write(self.content(item))
            written.append(item["id"])
        return EXIT_OK, written

    def content(self, item):
        kind, type_ = item["kind"], item["type"]
        if type_ == "link":
            return self.link_note(item)
        if kind == "memory":
            return item["fact"] + "\n"
        source = read_text(os.path.join(self.kit, item["source"]))
        if kind in ("note", "router"):
            return source
        if kind == "skill":
            return re.sub(r"(?m)^name: .*$", "name: " + item["name"], source, count=1)
        if kind == "agent":
            text = source.replace("${agents.dev_lead.name}", item["name"])
            return re.sub(r"(?m)^# Agent: .*$", "# Agent: " + item["name"], text, count=1)
        if kind == "routine":
            return self.routine_text(item, source)
        raise RuntimeError("planner bug: no content for %s" % item["id"])

    def routine_text(self, item, source):
        head = ["# Routine: %s" % item["name"], "", "enabled: false", "created from: %s (starter kit)" % item["source"]]
        if item["source"] == DEV_LEAD_TEMPLATE.replace(os.sep, "/"):
            body, keep = [], False
            for line in source.splitlines():
                if line.startswith("## Routines"):
                    keep = True
                    continue
                if keep and line.startswith("## "):
                    break
                if keep:
                    body.append(line)
        else:
            brief = cfg(self.config, "routines", "morning_brief", default={})
            head.append("schedule: %s in %s%s" % (brief.get("time") or "07:30",
                                                   cfg(self.config, "kit", "timezone", default="UTC"),
                                                   ", weekdays only" if brief.get("weekdays_only", True) else ""))
            body = source.splitlines()[1:]
        return "\n".join(head + [""] + body).rstrip("\n") + "\n"

    def link_note(self, item):
        stem = os.path.basename(item["target"])[:-len(".link.md")]
        return "\n".join([
            "---",
            'title: "Link: %s"' % stem,
            'type: "link"',
            'status: "active"',
            'channel: "%s"' % item["channel"],
            "tags: [%s, link]" % item["channel"],
            "links: []",
            "---",
            "",
            "# Link: %s" % stem,
            "",
            "This note points at a file you already keep outside the second brain. It is never copied or moved.",
            "",
            "- Path (relative to your home): `%s`" % item["links_to"],
            "",
        ])


# ---------------------------------------------------------------- output

def plan_sha256(items):
    canonical = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def text_plan(plan, titles):
    lines = ["kit plan (dry-run): %d items, nothing written" % len(plan["items"])]
    for cid in plan["checkpoints"]:
        title = titles.get(re.match(r"\d+", cid).group(0), "")
        lines.append("CHECKPOINT %s: %s" % (cid, title))
        items = [i for i in plan["items"] if i["checkpoint"] == cid]
        if not items:
            lines.append("  (nothing)")
        for item in items:
            extra = ""
            if item.get("choice"):
                extra = "  [choice %s%s]" % (item["choice"], ", with " + item["option"] if item.get("option") else "")
            lines.append("  %-7s %-10s %s:%s%s" % (item["type"], item["kind"], item["root"], item["target"], extra))
            lines.append("          %s" % item["reason"])
    lines.append("plan sha256: %s" % plan["sha256"])
    return "\n".join(lines) + "\n"


def parse_choices(values):
    choices = {}
    for value in values or []:
        group, sep, item_id = value.partition("=")
        if not sep or not group or not item_id:
            raise UsageError("--choose expects GROUP=ITEM_ID")
        choices[group] = item_id
    return choices


def main(argv=None, environ=None):
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(prog="kit_plan.py", description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("Options:", 1)[1] if "Options:" in __doc__ else None)
    parser.add_argument("--dry-run", action="store_true", help="compute and print the plan; write nothing (default)")
    parser.add_argument("--apply", action="store_true", help="write the approved add/link items where nothing exists")
    parser.add_argument("--approved", metavar="SHA256", help="the plan sha256 you approved")
    parser.add_argument("--choose", metavar="GROUP=ITEM", action="append", help="pick one option of a choice group")
    parser.add_argument("--json", action="store_true", help="print one JSON document")
    parser.add_argument("--kit", metavar="DIR")
    parser.add_argument("--config", metavar="PATH")
    parser.add_argument("--state", metavar="PATH")
    parser.add_argument("--setup-dir", metavar="DIR")
    parser.add_argument("--home", metavar="DIR")
    args = parser.parse_args(argv)
    try:
        if args.dry_run and args.apply:
            raise UsageError("--dry-run and --apply exclude each other")
        if args.apply and not args.approved:
            raise UsageError("--apply needs --approved <sha256> from the dry run you approved")
        choices = parse_choices(args.choose)
        planner = Planner(args, environ)
        plan = planner.build()
        if not args.apply:
            if args.json:
                sys.stdout.write(json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
            else:
                sys.stdout.write(text_plan(plan, planner.phase_titles))
            return EXIT_OK
        if args.approved != plan["sha256"]:
            print("kit_plan: the plan changed since the approval; run --dry-run again", file=sys.stderr)
            return EXIT_PLAN_CHANGED
        code, written = planner.apply(plan, choices)
        if code != EXIT_OK:
            print("kit_plan: a planned target already exists; nothing was written", file=sys.stderr)
            return code
        if args.json:
            sys.stdout.write(json.dumps({"mode": "apply", "written": written}) + "\n")
        else:
            sys.stdout.write("applied %d item(s)\n" % len(written) + "".join("written: %s\n" % w for w in written))
        return EXIT_OK
    except UsageError as exc:
        print("kit_plan: %s" % exc, file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
