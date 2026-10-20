import os, re
from .common import model_family

MODEL_RE = re.compile(r"^[A-Za-z0-9._:\[\]-]{1,80}$")


class RouteError(Exception):
    pass


def _check(name, what):
    if name is not None and not MODEL_RE.match(name):
        raise RouteError("invalid %s: %r" % (what, name))
    return name


def _alias_of(cfg, model):
    """Map a model name (alias or full id) to a config alias for fallback lookup."""
    models = cfg.get("models", {})
    if model in models:
        return model
    fam = model_family(model)
    return fam if fam in models else None


EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Only these keys may be passed via --settings: no permissions, hooks, env, apiKeyHelper or similar.
ALLOWED_SETTINGS = {"enabledPlugins", "skillListingMaxDescChars", "promptCacheTtl", "bashOutputMaxChars", "autoCompactWindow"}
ALLOWED_EXTRA_FLAGS = {"--strict-mcp-config", "--autocompact"}


def _deep_merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def profile(cfg, name, _seen=()):
    """Resolve a profile (with inherits) -> (settings_dict, extra_flags)."""
    profs = cfg.get("profiles", {})
    if name not in profs or name.startswith("_") or name in _seen:
        raise RouteError("unknown profile %r" % name)
    p = profs[name]
    settings, flags = {}, []
    if p.get("inherits"):
        settings, flags = profile(cfg, p["inherits"], _seen + (name,))
    settings = _deep_merge(settings, p.get("settings", {}))
    flags = flags + [f for f in p.get("extra_flags", []) if f not in flags]
    if "permissions" in settings:
        raise RouteError("profiles must not carry permissions keys")
    return settings, flags


def normalize_task_type(cfg, t):
    return cfg.get("task_type_aliases", {}).get(t, t) if t else t


def route(cfg, task_type=None, model_flag=None, env_model=None, fallback_flag=None,
          allow_haiku=False, env_subagent=None, effort_flag=None, experiments=()):
    """Pick model/effort/profile for a run. Override (flag, then env) always wins and is labelled as one."""
    routes = cfg.get("routes", {})
    task_type = normalize_task_type(cfg, task_type)
    routed = None
    if task_type:
        if task_type not in routes:
            raise RouteError("unknown task type %r (known: %s)" % (task_type, ", ".join(sorted(routes))))
        r = routes[task_type]
        routed = r["model"]
        reason = r.get("reason", "route %s" % task_type)
        if r.get("haiku_opt_in") and (allow_haiku or cfg.get("haiku_opt_in_default")):
            routed, reason = "haiku", "trivial task %s -> Haiku (opted in)" % task_type
    if model_flag:
        model, source = model_flag, "override-flag"
        reason = "--model override" + (" (route would be %s)" % routed if routed else "")
    elif env_model:
        model, source = env_model, "override-env"
        reason = "CLAUDE_ROUTE_MODEL override" + (" (route would be %s)" % routed if routed else "")
    elif task_type:
        model, source = routed, "route"
    else:
        model, source, reason = None, "default", "no routing options: CLI default model (no --model passed)"
    _check(model, "model")

    if fallback_flag:
        fallback = fallback_flag
    elif model is not None:
        alias = _alias_of(cfg, model)
        fallback = cfg.get("models", {}).get(alias, {}).get("fallback") if alias else None
    else:
        fallback = None
    _check(fallback, "fallback model")
    if fallback and model and (fallback == model or (_alias_of(cfg, fallback) == _alias_of(cfg, model)
                                                    and model != "opusplan")):
        fallback = None  # claude refuses fallback == primary

    sub = None
    if env_subagent:
        sub = env_subagent
    elif task_type:
        sub = routes[task_type].get("subagent_model", cfg.get("subagent_model", {}).get("default"))
    else:
        sub = None
    _check(sub, "subagent model")

    r = routes.get(task_type, {}) if task_type else {}
    effort = effort_flag or r.get("effort")
    if effort and effort not in EFFORTS:
        raise RouteError("invalid effort %r" % effort)
    settings, extra, prof = {}, [], None
    if task_type and cfg.get("profiles_enabled", True) and r.get("profile"):
        prof = r["profile"]
        settings, extra = profile(cfg, prof)
    exps = []
    xcfg = cfg.get("experiments", {})
    for name, x in xcfg.items():
        if name.startswith("_"):
            continue
        on = x.get("enabled") or name in experiments
        if on and (not x.get("apply_to") or task_type in x["apply_to"] or name in experiments):
            exps.append(name)
            settings = _deep_merge(settings, x.get("settings", {}))
            extra = extra + list(x.get("flags", []))
    bad = set(settings) - ALLOWED_SETTINGS
    if bad:
        raise RouteError("settings keys not allowed: %s" % ", ".join(sorted(bad)))
    for f in extra:
        if f.startswith("-") and f not in ALLOWED_EXTRA_FLAGS:
            raise RouteError("extra flag not allowed: %s" % f)
    unknown = [e for e in experiments if e not in xcfg]
    if unknown:
        raise RouteError("unknown experiment(s): %s" % ", ".join(unknown))
    return {"task_type": task_type, "model": model, "source": source, "reason": reason,
            "fallback_model": fallback, "subagent_model": sub, "effort": effort, "profile": prof,
            "settings": settings or None, "extra_flags": extra, "experiments": exps}


def claude_args(info):
    """Extra claude argv for a routed run (appended after the existing flags)."""
    a = []
    if info.get("model"):
        a += ["--model", info["model"]]
    if info.get("fallback_model"):
        a += ["--fallback-model", info["fallback_model"]]
    if info.get("effort"):
        a += ["--effort", info["effort"]]
    if info.get("settings"):
        import json
        a += ["--settings", json.dumps(info["settings"], separators=(",", ":"), sort_keys=True)]
    a += info.get("extra_flags") or []
    return a
