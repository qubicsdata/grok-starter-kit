"""Shared helpers for the WP-12 doc-test and smoke harness (WP12b-1).

The harness reads the four user docs WP12b-2 promoted from the WP-12a drafts (DOCS below) and holds
them to one inventory, ROWS: every command a doc shows in a fenced `sh` block must be a row, every
required row must be shown by the docs that need it, and every row is exercised by exactly the test
that registers it with @exercises. A row is one of:

  doc-test  run offline in a temporary HOME (a synthetic workspace, tasks clone or git repo), the
            exact documented argv with placeholders filled; `folio` is this tree's bin/folio and
            `backlog` is the pinned 1.53.0 binary from FOLIO_BACKLOG_BIN, via BacklogRunner
  gate      the project's own gate: checked without running the suite inside itself
  external  another tool's command (git, sha256sum, chmod, uv), run on synthetic data where safe,
            else checked against this tree (the uv distribution name)
  pending   the command's code is on a landed branch that is not on this stack: the argv is checked
            against that branch's parser (PENDING_SPECS), then the test skips with a reason naming
            the WP and its branch; a tripwire FAILS once the WP's seam is in the tree
  smoke     needs the network or a published repository (the public install)
  manual    needs a credential, real data or deletes things: never run, checked statically

`folio` commands that are neither in this tree's parser nor owned by a pending WP are failures, so
a command the docs show but nothing provides is red. The Backlog.md web-board subcommand is never
run and never fenced; its name is built from fragments so the static scan in
tests/backlog_contract/test_browser_guard.py does not match this file.
"""

import argparse
import contextlib
import hashlib
import io
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from collections import namedtuple
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = REPO_ROOT / "tests"
FOLIO_BIN = REPO_ROOT / "bin" / "folio"
PYPROJECT = REPO_ROOT / "pyproject.toml"

README = "README.md"
LOCAL_SECURITY = "docs/local-security.md"
RUNBOOK = "docs/migration-runbook.md"
TRIAL_NOTE = "docs/trial-note.md"
DOCS = (README, LOCAL_SECURITY, RUNBOOK, TRIAL_NOTE)
# The docs that must carry the "never run the Backlog.md board" rule (WP-12 content, M-20).
BOARD_RULE_DOCS = (README, LOCAL_SECURITY, TRIAL_NOTE)

COMMAND_FENCES = ("sh",)
OTHER_FENCES = ("text", "json", "yaml", "toml", "markdown", "diff", "python")
BOARD = "brow" + "ser"
BOARD_COMMAND = ("backlog", BOARD)
BACKLOG_FIRST_WORDS = ("init", "task", "doctor", "config", "doc", "draft", "--version")

PUBLIC_INSTALL_URL = "git+https://github.com/example-org/folio-oss@<sha|tag>"
PLACEHOLDERS = ("<sha|tag>", "<path>", "<clone>", "<list>", "<source-id>", "<workspace>", "<date>",
                "<allow-list-sha256>", "<first-migration-commit>", "<last-migration-commit>")
PLACEHOLDER = re.compile(r"<[^<>\s]+>")

Row = namedtuple("Row", "command kind owner required_in")
WP9 = ("WP-9", "wp/9-install")
WP10 = ("WP-10", "wp/10-git-sync")
WP11 = ("WP-11", "wp/11-migration")
WP14 = ("WP-14", "wp/14-usage-counter")

# The command inventory of the promoted docs, in the WP-12a drafts' order (their COMMANDS.md), with
# the spellings settled against this tree and the landed branches (WP12b-1 report). `required_in` names
# the docs that must show the row (fenced, or as an inline code span); a row may appear in any doc.
ROWS = (
    # README: install (WP-9) and the deploy key (WP-10)
    Row('uv tool install "%s"' % PUBLIC_INSTALL_URL, "smoke", WP9, (README,)),
    Row('pipx install "%s"' % PUBLIC_INSTALL_URL, "smoke", WP9, ()),
    Row("folio --version", "doc-test", None, ()),
    Row("folio tools ensure", "pending", WP9, (README,)),
    Row("folio tools verify", "pending", WP9, ()),
    Row("folio doctor", "doc-test", None, (README, RUNBOOK)),
    Row("folio ui", "doc-test", None, (README, LOCAL_SECURITY)),
    Row("uv tool upgrade folio-workspace", "external", WP9, ()),
    Row("uv tool uninstall folio-workspace", "external", WP9, (README, TRIAL_NOTE)),
    Row('ssh-keygen -t ed25519 -f ~/.ssh/folio_tasks_example_channel -C "folio tasks-example-channel"', "manual", WP10, (README,)),
    Row("cat ~/.ssh/folio_tasks_example_channel.pub", "manual", WP10, ()),
    Row("git clone git@tasks-example-channel:example-org/tasks-example-channel.git", "manual", WP10, (README,)),
    Row("folio repos add <path> --channel example-channel", "pending", WP10, (README,)),
    # README: views and the brief (the flat-model brief is WP-4's; the argv is this tree's)
    Row('folio brief <list> --query "release plan"', "doc-test", None, (README,)),
    Row("folio source <source-id> --project <list>", "doc-test", None, ()),
    # README: sync (WP-10)
    Row("folio sync --repo <path>", "pending", WP10, (README, TRIAL_NOTE)),
    Row("folio repair-ids --repo <path>", "pending", WP10, (README,)),
    Row("folio repair-ids --repo <path> --yes", "pending", WP10, ()),
    # README: command line, security model and development
    # local-security.md names `--no-open` alone inside the KEEP-SEC-pinned paragraph, so it is not required there.
    Row("folio ui --no-open", "doc-test", None, (README,)),
    Row("folio server-stop", "doc-test", None, (README, LOCAL_SECURITY, TRIAL_NOTE)),
    Row("folio usage report", "pending", WP14, (TRIAL_NOTE,)),
    Row("backlog task list --plain", "doc-test", None, (README, LOCAL_SECURITY, TRIAL_NOTE)),
    Row("python3 -m unittest discover -s tests -v", "gate", None, (README,)),
    Row("node --check folio/static/app.js", "gate", None, ()),
    Row("scripts/ci-local.sh", "gate", None, ()),
    # Migration runbook (WP-11)
    Row("folio migrate --from <workspace> --inventory", "pending", WP11, (RUNBOOK,)),
    Row("sha256sum example-channel-allow-list.json", "external", None, (RUNBOOK,)),
    Row("folio-1.1.2 server-stop", "manual", None, ()),
    Row("folio-1.1.2 backup --output folio-final-backup.json", "manual", None, ()),
    Row("sha256sum folio-final-backup.json", "external", None, ()),
    Row("chmod -R a-w <workspace>", "external", None, (RUNBOOK,)),
    Row("folio migrate --from <workspace> --dry-run --allow-list example-channel-allow-list.json --report dry-run-report.json",
        "pending", WP11, (RUNBOOK,)),
    Row("sha256sum dry-run-report.json", "external", None, ()),
    Row("folio migrate --from <workspace> --apply --allow-list example-channel-allow-list.json --reviewed <allow-list-sha256> --to <clone>",
        "pending", WP11, (RUNBOOK,)),
    Row("cd <clone>", "external", None, ()),
    Row("backlog task list --json --project <list>", "doc-test", None, ()),
    Row("backlog doctor", "doc-test", None, (RUNBOOK,)),
    Row("git checkout main", "external", None, ()),
    Row("git branch -D folio-migration/<date>", "external", WP11, (RUNBOOK,)),
    Row("git revert --no-edit <first-migration-commit>^..<last-migration-commit>", "external", WP11, ()),
    Row("chmod -R u+w <workspace>", "external", None, ()),
    Row("folio-1.1.2 ui", "manual", None, ()),
    # Trial and retirement note
    Row('rm -r "${XDG_STATE_HOME:-$HOME/.local/state}/folio"', "manual", None, ()),
)
KINDS = ("doc-test", "gate", "external", "pending", "smoke", "manual")


def key(command):
    """The argv tuple of one command line (shell quoting and `#` comments removed)."""
    return tuple(shlex.split(command, comments=True))


ROWS_BY_KEY = {key(row.command): row for row in ROWS}

# --- the docs ----------------------------------------------------------------------------------------

Command = namedtuple("Command", "doc line argv where")
FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
CODE_SPAN = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
INLINE_TOOLS = ("folio", "backlog")


def doc_text(doc, root=REPO_ROOT):
    path = Path(root) / doc
    return path.read_text(encoding="utf-8") if path.is_file() else None


def fences(text):
    """([(first line number, info string, [(line number, line)])], [problems]) for every fenced block."""
    blocks, problems = [], []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        match = FENCE.match(lines[index])
        if not match:
            index += 1
            continue
        indent, marker, info = match.groups()
        start, body = index + 1, []
        index += 1
        while index < len(lines):
            close = FENCE.match(lines[index])
            if close and close.group(2)[0] == marker[0] and len(close.group(2)) >= len(marker) and not close.group(3).strip():
                break
            line = lines[index]
            body.append((index + 1, line[len(indent):] if line.startswith(indent) else line.lstrip()))
            index += 1
        else:
            problems.append("line %d: unterminated fence" % start)
        blocks.append((start, info.strip(), body))
        index += 1
    return blocks, problems


def logical_lines(body):
    """[(line number, text)] with backslash continuations joined and blank or comment-only lines dropped."""
    joined, pending, first = [], "", None
    for number, line in body:
        if first is None:
            first = number
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        text = (pending + stripped).strip()
        pending, start, first = "", first, None
        if text.startswith("$ "):
            text = text[2:]
        if text and not text.startswith("#"):
            joined.append((start, text))
    if pending.strip():
        joined.append((first, pending.strip()))
    return joined


def fenced_commands(doc, text):
    """([Command], [problems]) for the command fences of one doc; problems name doc:line, never a value."""
    commands, problems = [], []
    blocks, fence_problems = fences(text)
    problems += ["%s %s" % (doc, problem) for problem in fence_problems]
    for start, info, body in blocks:
        language = info.split()[0].lower() if info else ""
        if language in OTHER_FENCES:
            continue
        if language not in COMMAND_FENCES:
            problems.append("%s:%d: fence language %r is neither a command fence (%s) nor a known text fence (%s)"
                            % (doc, start, language, ", ".join(COMMAND_FENCES), ", ".join(OTHER_FENCES)))
            continue
        for number, line in logical_lines(body):
            try:
                argv = key(line)
            except ValueError as error:
                problems.append("%s:%d: cannot split the command line (%s)" % (doc, number, error))
                continue
            if argv:
                commands.append(Command(doc, number, argv, "fence"))
    return commands, problems


def without_fences(text):
    """The text with every fenced block blanked (line numbers kept), for prose and inline-span scans."""
    lines = text.split("\n")
    blocks, _problems = fences(text)
    for start, _info, body in blocks:
        for number in range(start, (body[-1][0] if body else start) + 2):
            if number - 1 < len(lines):
                lines[number - 1] = ""
    return "\n".join(lines)


def inline_commands(doc, text):
    """[Command] for the inline code spans of the prose that start with `folio` or `backlog` plus a word."""
    commands = []
    for number, line in enumerate(without_fences(text).split("\n"), 1):
        for match in CODE_SPAN.finditer(line):
            try:
                argv = key(match.group(1))
            except ValueError:
                continue
            if len(argv) >= 2 and argv[0] in INLINE_TOOLS:
                commands.append(Command(doc, number, argv, "inline"))
    return commands


def doc_commands(root=REPO_ROOT, docs=DOCS):
    """({doc: ([fenced Command], [inline Command])}, [problems]) for the docs that exist."""
    found, problems = {}, []
    for doc in docs:
        text = doc_text(doc, root)
        if text is None:
            continue
        fenced, fence_problems = fenced_commands(doc, text)
        found[doc] = (fenced, inline_commands(doc, text))
        problems += fence_problems
    return found, problems


def placeholders(argv):
    return [found for token in argv for found in PLACEHOLDER.findall(token)]


# --- folio argv: this tree's parser, or the parser of the landed branch that owns the command ---------

class SpecError(Exception):
    pass


class SpecParser(argparse.ArgumentParser):
    def error(self, message):
        raise SpecError(message)


def _pending_specs():
    """{subcommand: (wp, branch, parser)} mirroring the landed branches' folio/cli.py (read-only, WP12b-1)."""
    specs = {}

    def parser_for(name, wp):
        parser = SpecParser(prog="folio %s" % name, add_help=False)
        specs[name] = wp + (parser,)
        return parser

    tools = parser_for("tools", WP9).add_subparsers(dest="action", required=True, parser_class=SpecParser)
    tools.add_parser("ensure", add_help=False)
    tools.add_parser("verify", add_help=False)
    sync = parser_for("sync", WP10)
    # wp/10-git-sync: `--repo` is the tasks-clone sync; bare `folio sync` was the Switchboard refresh,
    # removed by the WP-7 freeze on this stack, so the docs must always name the clone.
    sync.add_argument("--repo", required=True)
    repair = parser_for("repair-ids", WP10)
    repair.add_argument("--repo", required=True)
    repair.add_argument("--yes", action="store_true")
    repos = parser_for("repos", WP10).add_subparsers(dest="action", required=True, parser_class=SpecParser)
    add = repos.add_parser("add", add_help=False)
    add.add_argument("path")
    add.add_argument("--channel", required=True)
    migrate = parser_for("migrate", WP11)
    migrate.add_argument("--from", dest="source", required=True)
    migrate.add_argument("--inventory", action="store_true")
    migrate.add_argument("--dry-run", dest="dry_run", action="store_true")
    migrate.add_argument("--apply", action="store_true")
    migrate.add_argument("--allow-list", dest="allow_list")
    migrate.add_argument("--reviewed")
    migrate.add_argument("--to", dest="destination")
    migrate.add_argument("--report")
    usage = parser_for("usage", WP14).add_subparsers(dest="action", required=True, parser_class=SpecParser)
    usage.add_parser("report", add_help=False).add_argument("--since")
    return specs


PENDING_SPECS = _pending_specs()


def _migrate_rules(args):
    """wp/11-migration cmd_migrate: exactly one mode; dry-run and apply need the allow-list; apply needs --reviewed and --to."""
    modes = [mode for mode in ("inventory", "dry_run", "apply") if getattr(args, mode)]
    if len(modes) != 1:
        raise SpecError("exactly one of --inventory, --dry-run or --apply")
    if modes[0] in ("dry_run", "apply") and not args.allow_list:
        raise SpecError("--allow-list is required for --%s" % modes[0].replace("_", "-"))
    if modes[0] == "apply" and not (args.reviewed and args.destination):
        raise SpecError("--apply needs --reviewed <allow-list sha256> and --to <clone>")
    if modes[0] != "apply" and (args.reviewed or args.destination):
        raise SpecError("--reviewed and --to belong to --apply only")


def tree_parser():
    from folio.cli import build_parser
    return build_parser()


def subcommands(parser):
    """{name: subparser} of an argparse parser's subcommand action (empty when it has none)."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def fill_dummies(argv):
    return [PLACEHOLDER.sub("x", token) for token in argv]


def check_folio_argv(argv, parser=None, whole=True):
    """(owner, problem): owner is "tree" or the pending (wp, branch); problem is None when the argv parses.

    With whole=False only the subcommand path is checked (an inline span such as `folio sync` is a name,
    not a full command line)."""
    from folio.cli import CliError
    parser = parser or tree_parser()
    words = fill_dummies(argv[1:])
    tree = subcommands(parser)
    name = next((word for word in words if not word.startswith("-")), None)
    if name is None or name in tree:
        if not whole:
            sub = subcommands(tree[name]) if name else {}
            rest = [word for word in words[words.index(name) + 1:] if not word.startswith("-")] if name else []
            if sub and rest and rest[0] not in sub:
                return "tree", "`folio %s %s` is not a subcommand in this tree" % (name, rest[0])
            return "tree", None
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(words)
        except CliError as error:
            return "tree", "this tree's parser refuses it: %s" % error.message
        except SystemExit as stop:
            if stop.code not in (0, None):
                return "tree", "this tree's parser exits %r" % stop.code
        return "tree", None
    if name in PENDING_SPECS:
        wp, branch, spec = PENDING_SPECS[name]
        rest = words[words.index(name) + 1:]
        if not whole:
            sub = subcommands(spec)
            positional = [word for word in rest if not word.startswith("-")]
            if sub and positional and positional[0] not in sub:
                return (wp, branch), "`folio %s %s` is not a subcommand on %s" % (name, positional[0], branch)
            return (wp, branch), None
        try:
            args = spec.parse_args(rest)
            if name == "migrate":
                _migrate_rules(args)
        except SpecError as error:
            return (wp, branch), "%s's parser on %s refuses it: %s" % (wp, branch, error)
        return (wp, branch), None
    return None, "`folio %s` is neither in this tree's parser nor owned by a pending WP" % name


# Commands this stack removed. Prose may name them (as removed); a fence never shows them, and each one
# must still be a usage error here (the inventory tests run them).
CUT = {
    ("tasks",): "WP-6", ("agent-guide",): "WP-6", ("backup",): "WP-6",
    ("projects", "link"): "WP-7", ("projects", "unlink"): "WP-7", ("proposals",): "WP-7", ("decisions",): "WP-7",
}


def cut_by(argv):
    """The WP that cut this `folio` command, or None. `link|unlink` style alternations count as each part."""
    words = [word for word in argv[1:] if not word.startswith("-")]
    for length in (2, 1):
        head = tuple(words[:length])
        if len(head) == length:
            parts = [head[:-1] + (part,) for part in head[-1].split("|")]
            owners = {CUT.get(part) for part in parts}
            if len(owners) == 1 and None not in owners:
                return owners.pop()
    return None


def check_backlog_argv(argv, where):
    if tuple(argv[:2]) == BOARD_COMMAND:
        return None if where == "inline" else "the Backlog.md web board is never run and never fenced"
    if argv[1] not in BACKLOG_FIRST_WORDS:
        return "`backlog %s` is not an allowed first word (%s)" % (argv[1], ", ".join(BACKLOG_FIRST_WORDS))
    return None


# --- running documented commands ----------------------------------------------------------------------

EXERCISED = {}


def exercises(*commands):
    """Register the decorated test as the one that exercises these ROWS (checked by the inventory tests)."""
    def mark(test):
        for command in commands:
            EXERCISED.setdefault(key(command), []).append(test.__qualname__)
        return test
    return mark


def row(command):
    found = ROWS_BY_KEY.get(key(command))
    if found is None:
        raise AssertionError("%r is not a row of the doc-test inventory (tests/wp12_support.py ROWS)" % command)
    return found


def clean_env(home, **extra):
    """A minimal environment: a temporary HOME, no XDG or FOLIO variables, synthetic git identity."""
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Doc Test",
        "GIT_AUTHOR_EMAIL": "doc-test@example.com",
        "GIT_COMMITTER_NAME": "Doc Test",
        "GIT_COMMITTER_EMAIL": "doc-test@example.com",
    }
    if os.environ.get("TMPDIR"):
        env["TMPDIR"] = os.environ["TMPDIR"]
    env.update(extra)
    return env


def tool_argv(argv):
    """The executable argv for a documented command: `folio` is this tree's launcher."""
    if argv[0] == "folio":
        return [sys.executable, str(FOLIO_BIN)] + list(argv[1:])
    if argv[0] == "python3":
        return [sys.executable] + list(argv[1:])
    if argv[0].startswith("scripts/"):
        return [str(REPO_ROOT / argv[0])] + list(argv[1:])
    found = shutil.which(argv[0])
    if found is None:
        raise unittest.SkipTest("%s is not on PATH" % argv[0])
    return [found] + list(argv[1:])


def fill(argv, values):
    def one(token):
        for name, value in values.items():
            token = token.replace("<%s>" % name, str(value))
        return token
    filled = [one(token) for token in argv]
    left = placeholders(filled)
    if left:
        raise AssertionError("unfilled placeholders %s in %r" % (left, argv))
    return filled


class DocCase(unittest.TestCase):
    """A temporary HOME per test; documented commands run with exactly their argv (placeholders filled)."""

    TIMEOUT = 60

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="folio-doc-test-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = clean_env(self.home)

    @property
    def workspace(self):
        """The default workspace a fresh HOME resolves to on Linux (folio/paths.py)."""
        return self.home / ".local" / "share" / "folio" / "workspace"

    def argv(self, command, extra=(), **values):
        found = row(command)
        return tool_argv(fill(key(found.command), values)) + list(extra)

    def run_doc(self, command, cwd=None, extra=(), check=True, env=None, **values):
        result = subprocess.run(self.argv(command, extra, **values), cwd=str(cwd or self.root), env=env or self.env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=self.TIMEOUT)
        if check and result.returncode != 0:
            self.fail("%r exited %d\nstdout: %s\nstderr: %s" % (command, result.returncode, result.stdout[-2000:], result.stderr[-2000:]))
        return result

    def start_doc(self, command, extra=(), env=None, **values):
        process = subprocess.Popen(self.argv(command, extra, **values), cwd=str(self.root), env=env or self.env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        def stop():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(10)
            process.stdout.close()
            process.stderr.close()
        self.addCleanup(stop)
        return process

    def wait_for(self, predicate, process=None, what="condition", timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            if process is not None and process.poll() is not None:
                self.fail("process exited %d before %s\nstdout: %s\nstderr: %s"
                          % (process.returncode, what, process.stdout.read()[-2000:], process.stderr.read()[-2000:]))
            time.sleep(0.05)
        self.fail("timed out waiting for %s" % what)

    def folio(self, *args, check=True):
        """A setup call of this tree's CLI (not a documented command) in the same HOME."""
        result = subprocess.run([sys.executable, str(FOLIO_BIN), *args], cwd=str(self.root), env=self.env,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=self.TIMEOUT)
        if check and result.returncode != 0:
            self.fail("folio %r exited %d: %s %s" % (args, result.returncode, result.stdout[-1000:], result.stderr[-1000:]))
        return result

    def git(self, cwd, *args):
        result = subprocess.run(["git", *args], cwd=str(cwd), env=self.env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=self.TIMEOUT)
        if result.returncode != 0:
            self.fail("git %r exited %d: %s" % (args, result.returncode, result.stderr[-1000:]))
        return result.stdout


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project_name():
    """[project].name from pyproject.toml (stdlib only: tomllib is 3.11+)."""
    in_project = False
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_project = stripped == "[project]"
        elif in_project and stripped.startswith("name"):
            return stripped.split("=", 1)[1].strip().strip('"')
    return None


def tripwire(case, seams, wp, item):
    """Fail once the WP's seam is in the tree, so the pending skip cannot outlive it (WP-13's pattern)."""
    present = [seam.relative_to(REPO_ROOT).as_posix() for seam in seams if seam.exists()]
    if present:
        case.fail("%s's seam is in the tree (%s): replace this skip with the doc-test for %s" % (wp, ", ".join(present), item))


def pending_skip(case, owner, item):
    wp, branch = owner
    case.skipTest("%s: the code is on %s (%s), which is not on this stack; %s removes this skip" % (item, branch, wp, wp))
