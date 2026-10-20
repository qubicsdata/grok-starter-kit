"""Test harness for the runner: a fail-closed sandbox around every test.

Each TempEnv builds a fresh temp KIT_HOME and writes its config there from runner/runner.config.example.json
(plus tests/fixtures/router_test_overlay.json, which may only ADD keys the example does not have). Every path the
resolved config names (logs, queue, state, pidfile, stop file, probe dir, prompts, runner script, flags, env
file, ...) and every CR_* path override must lie inside that temp dir; if one does not, the whole test run is
aborted (os._exit), on entry and again on exit. Process-wide, at import:
  * CR_TEST_NO_REAL_CLAUDE=1, CLAUDE_BIN = tests/fakebin/claude, and the fake first on PATH;
  * an audit hook refuses to start any `claude` other than the fake, tmux or kill tools, and lets git run only
    inside a sandbox dir. The kit's own bin/cr and bin/run-claude.sh start only with a sandbox environment
    (CR_TEST_NO_REAL_CLAUDE=1, the fake CLAUDE_BIN, the config and every CR_* path inside a sandbox dir).
    Signals are refused except to this process's own children (the processes the hook let start);
  * HOME, TZ (TEST_TZ) and git's global/system config are pinned, so nothing reads the user's own files;
  * a session sandbox sets CR_CONFIG, so no test can fall back to a router.json next to the code."""
import atexit, json, os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER_DIR = os.path.dirname(HERE)
ROOT = RUNNER_DIR  # the router dir: bin/cr (CLAUDE_ROUTER_DIR)
BIN = os.path.join(RUNNER_DIR, "bin")  # cr, run-claude.sh and the crlib package
sys.path.insert(0, BIN)
FIX = os.path.join(HERE, "fixtures")
FAKEBIN = os.path.join(HERE, "fakebin")
FAKE_CLAUDE = os.path.join(FAKEBIN, "claude")
EXAMPLE_CONFIG = os.path.join(RUNNER_DIR, "runner.config.example.json")
TEST_OVERLAY = os.path.join(FIX, "router_test_overlay.json")
TEST_TZ = "Etc/GMT-3"  # fixed UTC+3, no DST: the copied tests' timestamps are written at +03:00
ABORT_EXIT = 70
TEMPLATES = ("claude-run-flags.sh", "claude-bash-env.sh")  # copied into every temp KIT_HOME/runner/

# Every path key of the resolved config: present, non-empty (env_file may be "" = none) and inside the sandbox.
PATH_KEYS = (
    ("paths", "logs"), ("paths", "queue"), ("paths", "runner"),
    ("runner", "pidfile"), ("runner", "stop_file"), ("runner", "out"), ("runner", "script"),
    ("runner", "env_file"), ("runner", "flags_file"), ("runner", "bash_env_file"), ("runner", "prompts_dir"),
    ("usage", "probe_dir"), ("usage", "projects_dir"),
    ("backlog", "queue"), ("backlog", "state_file"), ("backlog", "prompt_dir"),
)
OPTIONAL_EMPTY = {("runner", "env_file")}
RUNNER_KEYS = {("paths", "runner"), ("runner", "script")}  # may also name the kit's own bin/run-claude.sh
PATH_ENV = ("CR_CONFIG", "CR_LOG_DIR", "CR_QUEUE_DIR", "CR_RUNNER", "CR_BACKLOG_STATE", "CR_PROJECTS_DIR",
            "CLAUDE_RUN_LOG_DIR")
BLOCKED_PROGRAMS = ("cr", "run-claude.sh", "tmux", "pkill", "kill", "killall")
KIT_PROGRAMS = ("cr", "run-claude.sh")  # allowed only as the kit's own files, with a sandbox environment


class SandboxEscape(Exception):
    pass


# ---------------- path guard ----------------

def _real(p):
    return os.path.realpath(os.path.expanduser(p))


def _inside(path, root):
    rp, rr = _real(path), _real(root)
    return rp == rr or rp.startswith(rr.rstrip(os.sep) + os.sep)


def _looks_like_path(v):
    return isinstance(v, str) and v.startswith(("/", "~", "${", "./", "../"))


def _kit_script(v):
    """The kit's own bin/run-claude.sh (real path): the one file outside the sandbox the runner keys may name."""
    return isinstance(v, str) and os.path.isabs(v) and _real(v) == _real(os.path.join(BIN, "run-claude.sh"))


def check_sandbox(cfg, root, env=None):
    """Names (never values) of config keys / env vars that are missing, unresolved or resolve outside root."""
    bad = []
    for sect, key in PATH_KEYS:
        name = "%s.%s" % (sect, key)
        v = (cfg.get(sect) or {}).get(key)
        if v == "" and (sect, key) in OPTIONAL_EMPTY:
            continue
        if (sect, key) in RUNNER_KEYS and _kit_script(v):
            continue
        if not isinstance(v, str) or not v:
            bad.append(name + " (missing)")
        elif "${" in v or not os.path.isabs(os.path.expanduser(v)) or not _inside(v, root):
            bad.append(name)

    def walk(o, pre):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, pre + (str(k),))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, pre + (str(i),))
        elif _looks_like_path(o) and ("${" in o or not _inside(o, root)):
            if pre in RUNNER_KEYS and _kit_script(o):
                return
            n = ".".join(pre)
            if n not in bad:
                bad.append(n)
    walk(cfg, ())
    env = os.environ if env is None else env
    for k in PATH_ENV:
        if k == "CR_RUNNER" and _kit_script(env.get(k)):
            continue
        if env.get(k) and not _inside(env[k], root):
            bad.append("env " + k)
    if env.get("CLAUDE_BIN") and _real(env["CLAUDE_BIN"]) != _real(FAKE_CLAUDE):
        bad.append("env CLAUDE_BIN")
    if env.get("CR_TEST_NO_REAL_CLAUDE") != "1":
        bad.append("env CR_TEST_NO_REAL_CLAUDE")
    return bad


def abort(msg):
    sys.stderr.write("RUNNER TEST SANDBOX: %s; aborting the test run\n" % msg)
    sys.stderr.flush()
    _cleanup_roots()  # only the temp dirs this process made (os._exit skips atexit)
    os._exit(ABORT_EXIT)


def enforce_sandbox(cfg, root, env=None):
    bad = check_sandbox(cfg, root, env)
    if bad:
        abort("outside the test KIT_HOME: " + ", ".join(bad))


# ---------------- process guard (audit hook) ----------------

_ROOTS = []  # active sandbox roots (session + every open TempEnv)


def _in_any_root(p):
    return any(_inside(p, r) for r in _ROOTS)


def _argv_of(args):
    """argv as a list of str; a single command string (shell form) is split on whitespace."""
    if isinstance(args, (str, bytes, os.PathLike)):
        return os.fsdecode(args).split()
    return [os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a) for a in args or ()]


def sandboxed_env(env):
    """True only if env pins the sandbox: CR_TEST_NO_REAL_CLAUDE=1, the fake CLAUDE_BIN, the config (CR_CONFIG,
    else ${KIT_HOME}/runner/router.json) inside an active sandbox dir, and every CR_* path override inside one."""
    if not env or env.get("CR_TEST_NO_REAL_CLAUDE") != "1":
        return False
    if not env.get("CLAUDE_BIN") or _real(env["CLAUDE_BIN"]) != _real(FAKE_CLAUDE):
        return False
    conf = env.get("CR_CONFIG") or (os.path.join(env["KIT_HOME"], "runner", "router.json")
                                    if env.get("KIT_HOME") else None)
    if not conf or not _in_any_root(conf):
        return False
    return all(_in_any_root(env[k]) or (k == "CR_RUNNER" and _kit_script(env[k])) for k in PATH_ENV if env.get(k))


def _kit_program(a, n):
    return n in KIT_PROGRAMS and _real(a) == _real(os.path.join(BIN, n))


def refused(argv, cwd=None, env=None):
    """Why a process start is refused, or None. Pure, for the tests and the hook. env = the new process's
    environment; without one, the kit's bin/cr and run-claude.sh are refused."""
    argv = _argv_of(argv)
    if not argv:
        return None
    names = [os.path.basename(a) for a in argv]
    for a, n in zip(argv, names):
        if n == "claude" and _real(a) != _real(FAKE_CLAUDE):
            return "a claude other than tests/fakebin/claude"
        if n in KIT_PROGRAMS and _kit_program(a, n) and sandboxed_env(env):
            continue
        if n in BLOCKED_PROGRAMS:
            return "program %s" % n
    if names[0] == "git":
        targets = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-C"]
        if not targets and "init" in argv:
            targets = [a for a in argv[argv.index("init") + 1:] if not a.startswith("-")][-1:]
        if not targets:
            targets = [cwd or os.getcwd()]
        if not all(_in_any_root(t) for t in targets):
            return "git outside the test sandbox"
    return None


def _own_child(pid):
    """True if pid is a direct child of this process (a process the hook let start)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        with open("/proc/%d/stat" % pid) as f:
            return int(f.read().rsplit(")", 1)[1].split()[1]) == os.getpid()
    except (OSError, IndexError, ValueError):
        pass
    import subprocess  # no /proc (macOS): ask ps
    try:
        out = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() == str(os.getpid())
    except (OSError, subprocess.SubprocessError):
        return False


def _env_of(env):
    if env is None:
        return dict(os.environ)
    return {os.fsdecode(k): os.fsdecode(v) for k, v in dict(env).items()}


def _audit(event, args):
    if event == "subprocess.Popen":
        executable, argv, cwd, env = args[0], args[1], args[2], args[3]
        why = refused(([os.fsdecode(executable)] if executable else []) + _argv_of(argv), cwd, _env_of(env))
    elif event in ("os.exec", "os.posix_spawn"):
        why = refused(_argv_of(args[1]), None, _env_of(args[2]))
    elif event == "os.system":
        why = refused(_argv_of(args[0]), None, _env_of(None))
    elif event == "os.kill":
        why = None if args[1] == 0 or _own_child(args[0]) else "signal %s to pid %s" % (args[1], args[0])
    elif event == "os.killpg":
        why = "signal %s to process group %s" % (args[1], args[0]) if args[1] != 0 else None
    else:
        return
    if why:
        raise PermissionError("runner test sandbox refused: " + why)


# ---------------- config ----------------

def _add_only(base, extra, pre=""):
    """Merge `extra` into `base`, refusing to override any value the example config sets."""
    for k, v in extra.items():
        if k.startswith("_"):
            continue
        if k in base:
            if isinstance(base[k], dict) and isinstance(v, dict):
                _add_only(base[k], v, pre + k + ".")
                continue
            raise ValueError("test overlay overrides example key %s%s" % (pre, k))
        base[k] = v
    return base


def _subst(o, kit_home):
    if isinstance(o, dict):
        return {k: _subst(v, kit_home) for k, v in o.items()}
    if isinstance(o, list):
        return [_subst(v, kit_home) for v in o]
    if isinstance(o, str):
        return o.replace("${KIT_HOME}", kit_home).replace("${KIT_TZ}", TEST_TZ)
    return o


def build_config(kit_home):
    """The example config + the add-only test overlay, with ${KIT_HOME} / ${KIT_TZ} filled in."""
    with open(EXAMPLE_CONFIG) as f:
        cfg = json.load(f)
    with open(TEST_OVERLAY) as f:
        overlay = json.load(f)
    return _subst(_add_only(cfg, overlay), kit_home)


def make_kit_home(prefix):
    """A temp KIT_HOME with runner/router.json written from build_config(); returns (dir, config_path)."""
    d = os.path.realpath(tempfile.mkdtemp(prefix=prefix))
    try:
        for sub in ("runner/logs", "runner/queue", "runner/backlog/prompts", "runner/prompts", "home"):
            os.makedirs(os.path.join(d, sub))
        shutil.copytree(os.path.join(FIX, "projects"), os.path.join(d, "home", ".claude", "projects"))
        for name in TEMPLATES:  # runner.flags_file / runner.bash_env_file of the example config
            shutil.copyfile(os.path.join(RUNNER_DIR, name), os.path.join(d, "runner", name))
        path = os.path.join(d, "runner", "router.json")
        with open(path, "w") as f:
            json.dump(build_config(d), f, indent=1)
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return d, path


def _pin_process():
    os.environ["CR_TEST_NO_REAL_CLAUDE"] = "1"
    os.environ["CLAUDE_BIN"] = FAKE_CLAUDE
    os.environ["PATH"] = FAKEBIN + os.pathsep + os.environ.get("PATH", "")
    for k in [k for k in os.environ if k.startswith("GIT_")] + ["ANTHROPIC_API_KEY", "CLAUDE_ROUTE_MODEL"]:
        os.environ.pop(k, None)
    os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ["TZ"] = TEST_TZ
    time.tzset()


def _cleanup_roots():
    for r in list(_ROOTS):  # the session dir and any TempEnv a crashed test never left
        shutil.rmtree(r, ignore_errors=True)


def _session_sandbox():
    d, path = make_kit_home("crtest-session-")
    _ROOTS.append(d)
    atexit.register(_cleanup_roots)
    os.environ["HOME"] = os.path.join(d, "home")
    os.environ["CR_CONFIG"] = path
    os.environ["CR_LOG_DIR"] = os.path.join(d, "runner", "logs")
    os.environ["CR_QUEUE_DIR"] = os.path.join(d, "runner", "queue")
    os.environ["CR_PROJECTS_DIR"] = os.path.join(d, "home", ".claude", "projects")
    os.environ["CR_BACKLOG_DISABLE"] = "1"
    os.environ["CR_BACKLOG_STATE"] = os.path.join(d, "runner", "backlog", "queue-state.json")
    with open(path) as f:
        enforce_sandbox(json.load(f), d)
    return d


_pin_process()
SESSION_HOME = _session_sandbox()
sys.addaudithook(_audit)


class TempEnv:
    """Fresh temp KIT_HOME + its config; restores os.environ and removes the dir afterwards.
    d = the KIT_HOME root (tests put worktrees, prompts and queues under it); logs / queue = the runner dirs."""
    def __enter__(self):
        self.d, self.config = make_kit_home("crtest-")
        _ROOTS.append(self.d)
        self.logs = os.path.join(self.d, "runner", "logs")
        self.queue = os.path.join(self.d, "runner", "queue")
        self.saved = dict(os.environ)
        os.environ["HOME"] = os.path.join(self.d, "home")
        os.environ["CR_CONFIG"] = self.config
        os.environ["CR_LOG_DIR"] = self.logs
        os.environ["CR_QUEUE_DIR"] = self.queue
        os.environ["CR_PROJECTS_DIR"] = os.path.join(self.d, "home", ".claude", "projects")
        os.environ["CR_BACKLOG_DISABLE"] = "1"
        os.environ["CR_BACKLOG_STATE"] = os.path.join(self.d, "runner", "backlog", "queue-state.json")
        from crlib import common
        self.cfg = common.load_config()
        enforce_sandbox(self.cfg, self.d)
        return self

    def write_usage(self, recs):
        with open(os.path.join(self.logs, "usage.jsonl"), "a") as f:
            for r in recs:
                f.write(json.dumps(r) + "\n")

    def read(self, name):
        from crlib.common import read_jsonl
        return read_jsonl(os.path.join(self.logs, name))

    def __exit__(self, *a):
        enforce_sandbox(self.cfg, self.d)  # a test that pointed a path outside aborts the run
        os.environ.clear(); os.environ.update(self.saved)
        if self.d in _ROOTS:
            _ROOTS.remove(self.d)
        shutil.rmtree(self.d, ignore_errors=True)
