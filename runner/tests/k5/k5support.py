"""Shared setup for the runner parameterization suite (see README.md).

Every test runs inside the runner test sandbox (../helpers.py): a temp KIT_HOME per TempEnv, CR_CONFIG inside it, the fake
claude only, and the audit hook that refuses a real claude, signals and git outside the sandbox."""
import contextlib, importlib.machinery, importlib.util, io, json, os, re, sys

K5 = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.dirname(K5)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)
import helpers  # noqa: E402  (installs the sandbox on import)
from helpers import TempEnv, BIN, RUNNER_DIR, EXAMPLE_CONFIG, FAKEBIN  # noqa: E402,F401

SCRIPT = os.path.join(BIN, "run-claude.sh")
CR = os.path.join(BIN, "cr")
K5_2_GUARD = "not parameterized yet"  # the refusal run-claude.sh carried before it read router.json
FLAGS_TEMPLATE = os.path.join(RUNNER_DIR, "claude-run-flags.sh")
BASH_ENV_TEMPLATE = os.path.join(RUNNER_DIR, "claude-bash-env.sh")

# The 14 example keys that hold ${KIT_HOME} (the path rows of the parameterization table plus runner.script).
KIT_HOME_KEYS = (
    ("runner", "pidfile"), ("runner", "stop_file"), ("runner", "out"), ("runner", "script"),
    ("runner", "flags_file"), ("runner", "bash_env_file"), ("runner", "prompts_dir"),
    ("paths", "logs"), ("paths", "queue"), ("paths", "runner"),
    ("usage", "probe_dir"),
    ("backlog", "queue"), ("backlog", "state_file"), ("backlog", "prompt_dir"),
)
# CR_* overrides the sandbox sets; the loader tests drop them to see the config's own values.
CR_OVERRIDES = ("CR_LOG_DIR", "CR_QUEUE_DIR", "CR_RUNNER", "CR_BACKLOG_STATE", "CR_PROJECTS_DIR", "CR_BACKLOG_DISABLE")


def read(path, mode="r"):
    with open(path, mode) as f:
        return f.read()


def raw_example():
    """The example config as shipped: placeholders NOT filled in."""
    with open(EXAMPLE_CONFIG) as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def edit_config(t, fn):
    """Change the TempEnv's router.json on disk (and t.cfg, which TempEnv re-checks on exit)."""
    with open(t.config) as f:
        cfg = json.load(f)
    fn(cfg)
    write_json(t.config, cfg)
    fn(t.cfg)
    return cfg


def load_cr():
    """bin/cr imported in-process (the sandbox refuses bin/cr as a process)."""
    loader = importlib.machinery.SourceFileLoader("k5_cr_cli", CR)
    spec = importlib.util.spec_from_loader("k5_cr_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run_cr(argv):
    """(rc, stdout, stderr) of cr.main(argv); SystemExit and ValueError count as a refusal with that code."""
    cr = load_cr()
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = cr.main(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
            if not isinstance(e.code, int) and e.code:
                err.write(str(e.code))
        except ValueError as e:  # a config error raised instead of returned
            rc = "raised"
            err.write(str(e))
    return rc, out.getvalue(), err.getvalue()


def script_guarded():
    return K5_2_GUARD in read(SCRIPT)


def code_lines(text, comment="#"):
    """(lineno, line) for non-comment, non-blank lines (shell and Python comment style)."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s and not s.startswith(comment):
            out.append((i, line))
    return out


ABS_PATH_RE = re.compile(r"(?<![\w.~$}%)/:\-\]])(/[A-Za-z_][\w.@%+-]*(?:/[\w.@%+<>{}$-]*)*)")


def absolute_paths(text):
    """(lineno, path, is_comment_line) for every absolute-path token; `<pid>/x` segments are not new paths."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        is_comment = line.strip().startswith("#")
        for m in ABS_PATH_RE.finditer(line):
            before = line[:m.start()]
            if before.endswith(">") and re.search(r"<\w+>$", before):
                continue
            out.append((i, m.group(1), is_comment))
    return out
