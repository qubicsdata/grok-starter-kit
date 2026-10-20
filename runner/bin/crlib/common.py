import fcntl, json, os, re, time
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the kit's runner/ dir (bin/..)
DEFAULT_CONFIG = os.path.join(HERE, "router.json")  # = ${KIT_HOME}/runner/router.json in the kit layout
PLACEHOLDER_RE = re.compile(r"\$\{([^}]*)\}")


def default_config_path():
    """CR_CONFIG, else ${KIT_HOME}/runner/router.json (env KIT_HOME), else router.json next to bin/."""
    if os.environ.get("CR_CONFIG"):
        return os.environ["CR_CONFIG"]
    if os.environ.get("KIT_HOME"):
        return os.path.join(os.environ["KIT_HOME"], "runner", "router.json")
    return DEFAULT_CONFIG


def read_kit_config(path):
    """The `kit:` section of a kit.config.yaml as {key: str} (stdlib only: flat `key: value` lines, comments and
    quotes stripped). Missing file -> {}."""
    out, in_kit = {}, False
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return out
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[0].isspace():
            in_kit = raw.split("#", 1)[0].strip() == "kit:"
            continue
        if in_kit and ":" in raw:
            k, v = raw.strip().split(":", 1)
            v = _yaml_value(v)
            if v is not None:
                out[k.strip()] = v
    return out


def _yaml_value(v):
    v = v.strip()
    if v[:1] in ("'", '"'):
        end = v.find(v[0], 1)
        return v[1:end] if end > 0 else None
    v = re.split(r"\s#", v, maxsplit=1)[0].strip()
    return v or None


def kit_values(config_path):
    """(KIT_HOME or None, KIT_TZ). Env first (an empty value counts as unset), then the `kit:` section of the
    kit.config.yaml next to the config (${KIT_HOME}/runner/router.json -> ${KIT_HOME}/kit.config.yaml).
    KIT_HOME must be absolute; ${HOME} and ~ are expanded in kit.config.yaml only; env values are used literally."""
    kc = read_kit_config(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(config_path))),
                                      "kit.config.yaml"))
    home = os.environ.get("KIT_HOME") or None
    if home is None and kc.get("home"):
        home = os.path.expanduser(kc["home"].replace("${HOME}", os.environ.get("HOME", "~")))
    if home is not None:
        if not os.path.isabs(home):
            raise ValueError("KIT_HOME must be an absolute path (env KIT_HOME or kit.home in kit.config.yaml)")
        home = os.path.normpath(home)
    tz = os.environ.get("KIT_TZ") or kc.get("timezone") or "UTC"
    return home, tz


def expand_placeholders(cfg, config_path):
    """Fill ${KIT_HOME} / ${KIT_TZ} in every config value (keys starting with `_` are comments and stay as they
    are). Any other placeholder, or ${KIT_HOME} without a value, raises a ValueError naming the key."""
    vals = {}

    def value(name, key):
        if not vals:
            vals["KIT_HOME"], vals["KIT_TZ"] = kit_values(config_path)
        if name not in vals:
            raise ValueError("%s: unknown placeholder ${%s} (only ${KIT_HOME} and ${KIT_TZ})" % (key, name))
        if vals[name] is None:
            raise ValueError("%s: ${KIT_HOME} has no value: set KIT_HOME or kit.home in kit.config.yaml" % key)
        return vals[name]

    def walk(o, key):
        if isinstance(o, dict):
            return {k: (v if str(k).startswith("_") else walk(v, key + (str(k),))) for k, v in o.items()}
        if isinstance(o, list):
            return [walk(v, key + (str(i),)) for i, v in enumerate(o)]
        if isinstance(o, str) and "${" in o:
            name = ".".join(key)
            if "${" in PLACEHOLDER_RE.sub("", o):
                raise ValueError("%s: unterminated placeholder" % name)
            return PLACEHOLDER_RE.sub(lambda m: value(m.group(1), name), o)
        return o
    return walk(cfg, ())


def load_config(path=None):
    """The config with ${KIT_HOME} / ${KIT_TZ} filled in, the safe-limit defaults added where a key is missing
    (policy.DEFAULTS; a value you set is never changed) and the CR_* overrides applied."""
    from . import policy
    path = path or default_config_path()
    with open(path) as f:
        cfg = policy.fill_defaults(expand_placeholders(json.load(f), path))
    p = cfg.setdefault("paths", {})
    if os.environ.get("CR_LOG_DIR"):
        p["logs"] = os.environ["CR_LOG_DIR"]
    if os.environ.get("CR_QUEUE_DIR"):
        p["queue"] = os.environ["CR_QUEUE_DIR"]
    if os.environ.get("CR_RUNNER"):
        p["runner"] = os.environ["CR_RUNNER"]
    b = cfg.setdefault("backlog", {})
    if os.environ.get("CR_BACKLOG_DISABLE") == "1":  # tests
        b["enabled"] = False
    if os.environ.get("CR_BACKLOG_STATE"):
        b["state_file"] = os.environ["CR_BACKLOG_STATE"]
    u = cfg.setdefault("usage", {})
    if os.environ.get("CR_PROJECTS_DIR"):
        u["projects_dir"] = os.environ["CR_PROJECTS_DIR"]
    return cfg


def log_path(cfg, name):
    return os.path.join(cfg["paths"]["logs"], name)


def now_ts():
    if os.environ.get("CR_NOW"):  # tests only
        return parse_ts(os.environ["CR_NOW"]).timestamp()
    return time.time()


def local_tz():
    return datetime.now().astimezone().tzinfo


def iso(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(local_tz()).isoformat(timespec="seconds")


def parse_ts(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s, tz=timezone.utc)
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=local_tz())
    return d


def to_epoch(s):
    d = parse_ts(s)
    return None if d is None else d.timestamp()


def append_jsonl(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(obj, separators=(",", ":"), sort_keys=False) + "\n"
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_jsonl(path):
    out = []
    try:
        with open(path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except FileNotFoundError:
        pass
    return out


def model_family(name):
    n = (name or "").lower()
    for fam in ("fable", "opus", "sonnet", "haiku"):
        if fam in n:
            return fam
    return "other"
