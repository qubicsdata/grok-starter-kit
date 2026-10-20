"""The runner's safe limits: one table of defaults.

load_config fills them into a config, add-only (your own values win), and the policy functions fall back to them
when a key is missing, so a config that lacks a section still runs under these limits. The example config ships the
same values; its quiet_hours.tz is ${KIT_TZ} (filled in at setup), the code default is UTC.

The only values a config cannot lower: the `claude -p /usage` probe spacing (PROBE_FLOOR_MINUTES) and the spacing
of the Fable near-park re-probe (NEAR_PARK_PROBE_FLOOR_MINUTES), the one exception to the 30-minute spacing."""
import copy

PROBE_FLOOR_MINUTES = 30
NEAR_PARK_PROBE_FLOOR_MINUTES = 5

DEFAULTS = {
    "policy": {
        "total_cap": 4,                       # every claude -p on the box, the runner's own jobs included
        "opus_cap": 3,
        "session": {"pause_noncritical_pct": 80, "stop_new_pct": 90},
        "weekly": {"restricted_pct": 68, "critical_only_pct": 75, "stop_new_pct": 80},
        "rate_limit_park_statuses": ["rejected"],
        "overage": "disabled",
    },
    "usage": {
        "primary_source": "rate_limit_event",
        "probe_method": "print",              # claude -p /usage; the only probe
        "probe_fallback": "none",             # no screen scrape of any kind
        "poll_interval_minutes": 30,
        "min_probe_spacing_minutes": 30,
        "near_park_min_probe_spacing_minutes": 5,
    },
    "backlog": {
        "max_concurrent": 3,                  # the runner's own jobs
        "reserve_slots": 1,                   # kept free from backlog jobs: one slot ...
        "reserve_opus": 1,                    # ... and one Opus
        "session_max_pct": 80,
        "weekly_max_pct": 75,
        "fable": {"max_concurrent": 2},
        "quiet_hours": {"enabled": True, "start": "01:00", "end": "07:00", "tz": "UTC"},
        "weekly_pacing": {
            "all_models": {"enabled": True, "target_pct": 70, "target_hours_before_reset": 18, "final_pct": 75,
                           "slack_pct": 2, "near_cap": 2},
            "fable": {"enabled": True, "target_pct": 75, "target_hours_before_reset": 0, "final_pct": 75,
                      "slack_pct": 2, "near_cap": 1, "park_pct": 80, "near_park_pct": 75,
                      "fresh_minutes": 30, "stale_near_cap_minutes": 45, "stale_block_minutes": 90},
        },
    },
}


def _fill(base, defaults):
    """Add every default key that base lacks (recursively); keys starting with `_` are comments and stay."""
    for k, v in defaults.items():
        if k not in base:
            base[k] = copy.deepcopy(v)
        elif isinstance(base[k], dict) and isinstance(v, dict):
            _fill(base[k], v)
    return base


def fill_defaults(cfg):
    """cfg with every missing safe-limit key filled in from DEFAULTS. Add-only: a value you set is never changed."""
    return _fill(cfg, DEFAULTS)


def default(*path):
    """The default at path, e.g. default("backlog", "quiet_hours", "end")."""
    o = DEFAULTS
    for k in path:
        o = o[k]
    return copy.deepcopy(o)


def section(cfg, *path):
    """The config's section at path with the defaults filled in (a copy; cfg is not changed)."""
    o = cfg
    for k in path:
        o = o.get(k) if isinstance(o, dict) else None
    return _fill(copy.deepcopy(o) if isinstance(o, dict) else {}, default(*path))


def value(cfg, *path):
    """The config's value at path, else the default."""
    o = cfg
    for k in path:
        if not isinstance(o, dict) or k not in o:
            return default(*path)
        o = o[k]
    return o


def probe_spacing_minutes(cfg):
    """Minutes between two `claude -p /usage` probes: usage.min_probe_spacing_minutes, never under the floor."""
    return max(value(cfg, "usage", "min_probe_spacing_minutes"), PROBE_FLOOR_MINUTES)


def loop_probe_spacing_minutes(cfg):
    """The scheduler loop's own probe cadence: the larger of poll_interval_minutes and the probe spacing."""
    return max(value(cfg, "usage", "poll_interval_minutes"), probe_spacing_minutes(cfg))


def near_park_spacing_minutes(cfg):
    """Minutes between two Fable near-park re-probes, never under NEAR_PARK_PROBE_FLOOR_MINUTES."""
    return max(value(cfg, "usage", "near_park_min_probe_spacing_minutes"), NEAR_PARK_PROBE_FLOOR_MINUTES)


def enabled(cfg):
    """True only for the JSON value true in runner.enabled."""
    return (cfg.get("runner") or {}).get("enabled") is True
