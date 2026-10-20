"""Checks for the dev-lead agent template (agents/dev-lead/).

- every skill parses: front matter with `name` and `description`, name == folder;
- the template is generic: clean-data scan at zero, no host paths, no hard-coded
  PATH, speaks to "you" (no third-person references copied from design notes);
- collision rules are documented for every skill, the agent and the routine;
- the sizing routine is off by default, reports only on change, never starts work;
- every config key the template names exists in kit.config.example.yaml and
  has a row in PARAMETERS.md.

Owner names themselves are never listed here: the external term list covers
them through `python3 tools/ci_local.py --terms-file PATH` (the clean-scan step
scans the whole tree, agents/ included). Problem messages name the rule, file
and line only, never the matched text. Stdlib only, Python 3.9+.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_DIR = os.path.join(ROOT, "agents", "dev-lead")
AGENT_MD = os.path.join(AGENT_DIR, "AGENT.md")
SKILLS_DIR = os.path.join(AGENT_DIR, "skills")
ROUTINE_MD = os.path.join(AGENT_DIR, "routines", "dev-lead-sizing.md")
CONFIG = os.path.join(ROOT, "kit.config.example.yaml")
PARAMETERS = os.path.join(ROOT, "PARAMETERS.md")
CLEAN_SCAN = os.path.join(ROOT, "tools", "clean_scan.py")
CODING_AGENT_CASE = os.path.join(
    ROOT, "tests", "fixtures", "existing-setup", "case-05-has-coding-agent.yaml"
)

# The five dev-lead skills and the existing-setup rule each one follows
# (PARAMETERS.md vocabulary), as words its collision-rule cell must contain.
SKILLS = {
    "claude-code-dev-task": "extend",            # reuse-or-extend
    "pr-review": "reuse",                        # reuse-or-extend
    "repo-health-check": "only if missing",      # add-only-if-missing
    "adr-writer": "only if missing",
    "threat-model": "only if missing",
}
ROUTINE_NAME = "dev-lead-sizing"
CLAUDE_BIN_KEY = "agents.dev_lead.claude_bin_dir"

# ---------------------------------------------------------------- parsers

FM_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*?))?[ \t]*$")
BLOCK_INDICATORS = (">", ">-", ">+", "|", "|-", "|+")


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_front_matter(text):
    """Return (fields, body) for a `---` front-matter block on line 1.

    Handles `key: value` and block scalars (`>-`, `|`, ...) with indented
    continuation lines. Raises ValueError on a missing or unclosed block, an
    unparsable line or a duplicate key.
    """
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise ValueError("no front matter on line 1")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None:
        raise ValueError("front matter not closed")
    fields = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        match = FM_FIELD_RE.match(line)
        if not match:
            raise ValueError("unparsable front matter line %d" % (i + 1))
        key, value = match.group(1), (match.group(2) or "")
        if key in fields:
            raise ValueError("duplicate key on line %d" % (i + 1))
        i += 1
        if value in BLOCK_INDICATORS or value == "":
            block = []
            while i < end and (lines[i][:1] in (" ", "\t") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            if value.startswith("|"):
                value = "\n".join(block).strip()
            else:
                value = " ".join(part for part in block if part)
        else:
            value = _unquote(value)
        fields[key] = value
    return fields, "\n".join(lines[end + 1:])


CONFIG_KEY_RE = re.compile(r"^( *)([A-Za-z_][A-Za-z0-9_]*):(?:[ \t]+(.*?))?[ \t]*$")


def _config_value(raw):
    raw = raw.strip()
    if raw[:1] in "\"'":
        close = raw.find(raw[0], 1)
        return raw[1:close] if close > 0 else raw[1:]
    return re.split(r"\s+#", raw, maxsplit=1)[0].strip()


def config_scalars(text):
    """Dotted key -> scalar text for a block-style YAML mapping (enough for
    kit.config.example.yaml: nested mappings, scalars, inline lists/maps)."""
    out, stack = {}, []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = CONFIG_KEY_RE.match(line)
        if not match:
            continue
        indent, key = len(match.group(1)), match.group(2)
        raw = match.group(3) or ""
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([k for _, k in stack] + [key])
        if raw == "" or raw.startswith("#"):
            stack.append((indent, key))
            out[path] = None  # a mapping
        else:
            out[path] = _config_value(raw)
    return out


def parameter_keys(text):
    """Every backticked key in the first cell of a PARAMETERS.md table row."""
    keys = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        first = line.split("|")[1]
        keys.update(re.findall(r"`([^`]+)`", first))
    # "`a.b.x` / `y`" rows name a sibling key by its last part only.
    expanded = set(keys)
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cell = re.findall(r"`([^`]+)`", line.split("|")[1])
        if len(cell) > 1 and "." in cell[0]:
            prefix = cell[0].rsplit(".", 1)[0]
            expanded.update(prefix + "." + k for k in cell[1:] if "." not in k)
    return expanded


def section(text, heading_prefix):
    """The lines under the first `## <heading_prefix>...` heading."""
    lines, out, inside = text.splitlines(), [], False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].startswith(heading_prefix)
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


SKILL_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|([^|]*)\|([^|]*)\|\s*$")


def skill_rows(agent_text):
    """{skill: (purpose, collision rule)} from the AGENT.md skills table."""
    rows = {}
    for line in section(agent_text, "Skills").splitlines():
        match = SKILL_ROW_RE.match(line)
        if match:
            rows[match.group(1)] = (match.group(2).strip(), match.group(3).strip())
    return rows


# ---------------------------------------------------------------- lint rules

# An absolute path: a slash right after start/space/quote/backtick/paren/=,
# followed by a path segment. `/dev/null` is the only one a template may name.
ABS_PATH_RE = re.compile(r"(?:^|(?<=[\s`\"'(=]))/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.<>-]*)*")
ALLOWED_ABS_PATHS = ("/dev/null",)
THIRD_PERSON_RE = re.compile(r"\b(?:she|her|hers|herself|he|him|his|himself)\b", re.IGNORECASE)
HOST_PHRASE_RE = re.compile(r"\bon\s+the\s+box\b", re.IGNORECASE)
PATH_HACK_RE = re.compile(r"npm\s+prefix")
CONFIG_REF_RE = re.compile(r"(?<![\w.-])((?:agents|kit|runner|routines|skills)(?:\.[a-z_]+)+)")


def text_problems(text, label):
    """Generic-template lint. Messages hold rule, file and line, never text."""
    problems = []
    for number, line in enumerate(text.splitlines(), 1):
        where = "%s:%d" % (label, number)
        for match in ABS_PATH_RE.finditer(line):
            if match.group(0) not in ALLOWED_ABS_PATHS:
                problems.append("abs-path " + where)
        if THIRD_PERSON_RE.search(line):
            problems.append("third-person " + where)
        if PATH_HACK_RE.search(line):
            problems.append("hard-coded-path " + where)
    # Phrases may wrap across lines (folded descriptions).
    if HOST_PHRASE_RE.search(" ".join(text.split())):
        problems.append("host-phrase " + label)
    return problems


def skill_problems(skill_dir):
    label = os.path.basename(skill_dir)
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(path):
        return ["missing SKILL.md " + label]
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    try:
        fields, body = parse_front_matter(text)
    except ValueError as exc:
        return ["front matter %s: %s" % (label, exc)]
    problems = []
    if fields.get("name") != label:
        problems.append("name != folder " + label)
    if not fields.get("description", "").strip():
        problems.append("no description " + label)
    if not body.strip():
        problems.append("empty body " + label)
    return problems


def routine_problems(path):
    label = os.path.basename(path)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    try:
        fields, body = parse_front_matter(text)
    except ValueError as exc:
        return ["front matter %s: %s" % (label, exc)]
    problems = []
    if fields.get("name") != os.path.splitext(label)[0]:
        problems.append("name != file " + label)
    if not fields.get("description", "").strip():
        problems.append("no description " + label)
    if fields.get("enabled") != "false":
        problems.append("not off by default " + label)
    if fields.get("starts_work") != "false":
        problems.append("may start work " + label)
    if fields.get("report") != "on-change":
        problems.append("reports without a change " + label)
    flat = " ".join(body.split()).lower()
    if "never starts work" not in flat:
        problems.append("body does not say it never starts work " + label)
    if "stay quiet" not in flat:
        problems.append("body has no quiet rule " + label)
    return problems


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def agent_files():
    for dirpath, dirnames, filenames in os.walk(AGENT_DIR):
        dirnames.sort()
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


# ---------------------------------------------------------------- kit tests


class SkillsTest(unittest.TestCase):
    def test_skill_folders_are_the_five(self):
        self.assertTrue(os.path.isdir(SKILLS_DIR), "agents/dev-lead/skills missing")
        found = sorted(n for n in os.listdir(SKILLS_DIR) if not n.startswith("."))
        self.assertEqual(found, sorted(SKILLS))

    def test_skills_parse_and_name_matches_folder(self):
        for name in sorted(SKILLS):
            with self.subTest(skill=name):
                self.assertEqual(skill_problems(os.path.join(SKILLS_DIR, name)), [])

    def test_dev_task_runs_on_your_own_box(self):
        fields, _ = parse_front_matter(read(os.path.join(SKILLS_DIR, "claude-code-dev-task", "SKILL.md")))
        self.assertIn("your own box", fields["description"])

    def test_dev_task_path_comes_from_config(self):
        text = read(os.path.join(SKILLS_DIR, "claude-code-dev-task", "SKILL.md"))
        _, body = parse_front_matter(text)
        first_step = next(l for l in body.splitlines() if l.startswith("1."))
        self.assertIn(CLAUDE_BIN_KEY, first_step)
        self.assertIn("claude --version", first_step)
        self.assertNotIn("npm", first_step)

    def test_dev_task_generalized_lines_keep_their_place(self):
        # The spec names lines 5 and 8; one-line rewrites keep the rest aligned.
        lines = read(os.path.join(SKILLS_DIR, "claude-code-dev-task", "SKILL.md")).splitlines()
        self.assertIn("your own box", lines[4])
        self.assertIn(CLAUDE_BIN_KEY, lines[7])
        self.assertTrue(lines[8].startswith("2. In the target repo"))


class GenericTemplateTest(unittest.TestCase):
    def test_lint_clean(self):
        problems = []
        for path in agent_files():
            problems += text_problems(read(path), os.path.relpath(path, ROOT))
        self.assertEqual(problems, [])

    def test_clean_scan_zero_on_agents(self):
        home = tempfile.mkdtemp(prefix="kit-agents-home-")
        self.addCleanup(shutil.rmtree, home, True)
        proc = subprocess.run(
            [sys.executable, CLEAN_SCAN, os.path.join(ROOT, "agents")],
            cwd=home,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home,
                 "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=300,
        )
        lines = proc.stdout.splitlines()
        self.assertIn("TOTAL 0", lines, "clean scan on agents/ is not zero")
        self.assertEqual(proc.returncode, 0)

    def test_config_refs_exist(self):
        config = config_scalars(read(CONFIG))
        missing = []
        for path in agent_files():
            for ref in CONFIG_REF_RE.findall(read(path)):
                if ref not in config:
                    missing.append("%s %s" % (os.path.relpath(path, ROOT), ref))
        self.assertEqual(missing, [])


class CollisionRulesTest(unittest.TestCase):
    def setUp(self):
        self.agent = read(AGENT_MD)

    def test_table_lists_exactly_the_skill_folders(self):
        self.assertEqual(sorted(skill_rows(self.agent)), sorted(os.listdir(SKILLS_DIR)))

    def test_each_skill_rule_matches_its_existing_setup_mode(self):
        rows = skill_rows(self.agent)
        for name, words in SKILLS.items():
            with self.subTest(skill=name):
                purpose, rule = rows[name]
                self.assertTrue(purpose)
                self.assertIn(words, rule.lower())

    def test_skill_name_clash_gets_collision_suffix(self):
        self.assertIn("kit.collision_suffix", section(self.agent, "Skills"))

    def test_existing_agent_extend_or_create(self):
        text = section(self.agent, "If you already have")
        self.assertIn("**Extend**", text)
        self.assertIn("**Create**", text)
        self.assertIn("kit.collision_suffix", text)
        self.assertIn("waits for your choice", text)

    def test_routine_merges_into_yours(self):
        text = section(read(ROUTINE_MD), "If you already have")
        self.assertIn("merge", text.lower())
        self.assertIn("kit.collision_suffix", text)

    def test_coding_agent_fixture_names_kit_items(self):
        text = read(CODING_AGENT_CASE)
        skills = re.search(r"add_skills: \[([^\]]*)\]", text).group(1)
        routines = re.search(r"add_routines: \[([^\]]*)\]", text).group(1)
        for name in (s.strip() for s in skills.split(",")):
            self.assertIn(name, SKILLS)
        self.assertEqual([r.strip() for r in routines.split(",")], [ROUTINE_NAME])


class SizingRoutineTest(unittest.TestCase):
    def test_routine_definition(self):
        self.assertTrue(os.path.isfile(ROUTINE_MD), "routine definition missing")
        self.assertEqual(routine_problems(ROUTINE_MD), [])

    def test_routine_named_in_agent(self):
        self.assertIn("`%s`" % ROUTINE_NAME, section(read(AGENT_MD), "Routines"))
        self.assertIn("routines/%s.md" % ROUTINE_NAME, read(AGENT_MD))

    def test_config_keeps_agent_and_routine_off(self):
        config = config_scalars(read(CONFIG))
        self.assertEqual(config.get("agents.dev_lead.enabled"), "false")
        self.assertEqual(config.get("agents.dev_lead.sizing_enabled"), "false")
        self.assertEqual(config.get("agents.dev_lead.sizing_interval_hours"), "4")


class ConfigKeysTest(unittest.TestCase):
    def test_claude_bin_dir_defaults_to_empty(self):
        config = config_scalars(read(CONFIG))
        self.assertIn(CLAUDE_BIN_KEY, config)
        self.assertEqual(config[CLAUDE_BIN_KEY], "")

    def test_every_dev_lead_key_has_a_parameters_row(self):
        config = config_scalars(read(CONFIG))
        keys = parameter_keys(read(PARAMETERS))
        dev_keys = [k for k, v in config.items() if k.startswith("agents.dev_lead.") and v is not None]
        self.assertIn(CLAUDE_BIN_KEY, dev_keys)
        self.assertEqual([k for k in dev_keys if k not in keys], [])


# ------------------------------------------- self-tests of the checkers above


class CheckerSelfTest(unittest.TestCase):
    """Each rule above is shown to fire on a synthetic bad input."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kit-agents-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    GOOD_SKILL = "---\nname: example-skill\ndescription: >-\n  Use this when\n  asked.\n---\n# Steps\n1. x\n"

    def test_folded_description(self):
        fields, body = parse_front_matter(self.GOOD_SKILL)
        self.assertEqual(fields, {"name": "example-skill", "description": "Use this when asked."})
        self.assertIn("# Steps", body)

    def test_literal_block_and_quotes(self):
        fields, _ = parse_front_matter("---\na: |\n  one\n  two\nb: 'q'\nc:\n---\n")
        self.assertEqual(fields, {"a": "one\ntwo", "b": "q", "c": ""})

    def test_front_matter_errors(self):
        for bad in ("# no front matter\n", "---\nname: x\n", "---\nname: x\nname: y\n---\n",
                    "---\n  indented: x\n---\n", ""):
            with self.subTest(case=bad[:12]):
                with self.assertRaises(ValueError):
                    parse_front_matter(bad)

    def test_good_skill_passes(self):
        self.write("example-skill/SKILL.md", self.GOOD_SKILL)
        self.assertEqual(skill_problems(os.path.join(self.tmp, "example-skill")), [])

    def test_name_mismatch_and_missing_parts(self):
        self.write("other/SKILL.md", self.GOOD_SKILL)
        self.assertEqual(skill_problems(os.path.join(self.tmp, "other")), ["name != folder other"])
        self.write("example-skill/SKILL.md", "---\nname: example-skill\n---\n")
        self.assertEqual(
            skill_problems(os.path.join(self.tmp, "example-skill")),
            ["no description example-skill", "empty body example-skill"],
        )
        os.makedirs(os.path.join(self.tmp, "empty"))
        self.assertEqual(skill_problems(os.path.join(self.tmp, "empty")), ["missing SKILL.md empty"])

    def test_text_rules_fire(self):
        cases = {
            "abs-path": "run `/opt/example/bin/tool` first",
            "third-person": "extend her coding agent",
            "hard-coded-path": 'export PATH="$(npm prefix -g)/bin:$PATH"',
            "host-phrase": "the CLI on the\n  box and deliver",
        }
        for rule, text in cases.items():
            with self.subTest(rule=rule):
                problems = text_problems(text, "f")
                self.assertTrue(problems and all(p.startswith(rule) for p in problems), problems)

    def test_text_rules_allow_generic_text(self):
        text = ('run `claude -p "<task>" < /dev/null` in `../wt-<slug>` from origin/<default>;\n'
                "a DFD in text/mermaid; sizes S/M/L; here and there; on your own box.\n")
        self.assertEqual(text_problems(text, "f"), [])

    def test_problem_messages_hold_no_text(self):
        secret_ish = "/opt/example-canary"
        self.assertNotIn(secret_ish, " ".join(text_problems(secret_ish, "f")))

    def routine(self, **overrides):
        fields = {"name": "example-routine", "description": "x", "enabled": "false",
                  "starts_work": "false", "report": "on-change"}
        fields.update(overrides)
        head = "".join("%s: %s\n" % kv for kv in fields.items() if kv[1] is not None)
        body = "It never starts work. Otherwise it stays quiet; stay quiet.\n"
        return self.write("example-routine.md", "---\n" + head + "---\n" + body)

    def test_good_routine_passes(self):
        self.assertEqual(routine_problems(self.routine()), [])

    def test_routine_rules_fire(self):
        cases = {
            "not off by default": {"enabled": "true"},
            "may start work": {"starts_work": "true"},
            "reports without a change": {"report": "always"},
            "name != file": {"name": "other"},
        }
        for message, override in cases.items():
            with self.subTest(rule=message):
                problems = routine_problems(self.routine(**override))
                self.assertEqual(len(problems), 1, problems)
                self.assertTrue(problems[0].startswith(message))
        with self.subTest(rule="missing enabled"):
            self.assertTrue(routine_problems(self.routine(enabled=None))[0].startswith("not off"))

    def test_config_scalars(self):
        text = ('a:\n  b:\n    enabled: false   # off\n    name: "x # y"\n    empty: ""\n'
                '    list: ["p", "q"]\n  c: 4\n    "quoted/": "skipped"\nd: 1\n')
        self.assertEqual(config_scalars(text), {
            "a": None, "a.b": None, "a.b.enabled": "false", "a.b.name": "x # y",
            "a.b.empty": "", "a.b.list": '["p", "q"]', "a.c": "4", "d": "1",
        })

    def test_parameter_keys(self):
        text = ("| Key | Default |\n|---|---|\n| `a.b.x` | 1 |\n"
                "| `kit.author_name` / `author_email` | n |\n")
        keys = parameter_keys(text)
        self.assertIn("a.b.x", keys)
        self.assertIn("kit.author_email", keys)


if __name__ == "__main__":
    unittest.main()
