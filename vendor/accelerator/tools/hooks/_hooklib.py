"""
_hooklib.py — Shared utilities for accelerator hook scripts.

Pure stdlib, Python 3.8+. No third-party dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from typing import Optional


def get_repo_root() -> str:
    """Resolve the repo root: $CLAUDE_PROJECT_DIR → git toplevel (from cwd) → cwd.

    $CLAUDE_PROJECT_DIR wins because it is the harness's authoritative session
    project dir; the process cwd can sit inside a DIFFERENT git repo (a worktree
    or sibling checkout), and a git-first resolution would then read/write the
    wrong repo's state — including silently bypassing an armed budget.json.
    """
    env_root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if env_root:
        return env_root

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return os.getcwd()


def atomic_write_text(path, text: str) -> None:
    """Write text to path atomically: temp file in the same directory + os.replace.

    Readers (e.g. cost_gate.py on budget.json) can never observe a torn or empty
    file mid-write. Raises on failure — callers keep their own fail-open guards.
    """
    target = str(path)
    directory = os.path.dirname(target) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".swap")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextmanager
def file_lock(lock_path):
    """Advisory exclusive lock serializing concurrent hook processes.

    Uses POSIX flock on a dedicated lock file (auto-released on process exit,
    so a crashed holder never wedges the next hook). Fail-open: if fcntl is
    unavailable (non-POSIX) or the lock file cannot be opened, the block runs
    unlocked — degraded, never blocking the session.
    """
    fh = None
    try:
        try:
            import fcntl
            fh = open(lock_path, "a+")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except Exception:
            if fh is not None:
                try:
                    fh.close()
                except Exception:
                    pass
            fh = None
        yield
    finally:
        if fh is not None:
            try:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Model pricing — hook-side USD costing, rates read from the pricing.json data
# file (the suite-root file is the source of truth; tools/sync-shipped-hooks.py
# ships a byte-identical copy beside the installed scripts, so hooks stay
# self-contained). Mirrors cost-monitor/skills/pricing-table.md — keep in sync.
# Rates are USD per token: (input_rate, output_rate).
# Costing follows benchmarks/BENCHMARK-CONVENTIONS.md §1: cost-weighted, and
# cache_read tokens are EXCLUDED — callers must pass a tokens_in that already
# excludes them (transcript_usage.summarize_since guarantees this).
# ---------------------------------------------------------------------------

PRICING_FILE_NAME = "pricing.json"
PRICING_UNIT = "usd_per_token"

_pricing_cache: Optional[dict] = None


class PricingError(RuntimeError):
    """The pricing data file is missing or malformed. Raised when a cost is
    computed, never at import, so hooks that do no costing keep working."""


def pricing_file_candidates() -> list:
    """pricing.json beside this file (installed ai-baseline), then at the
    suite root two levels up (canonical tools/hooks/)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return [os.path.join(here, PRICING_FILE_NAME),
            os.path.join(os.path.dirname(os.path.dirname(here)), PRICING_FILE_NAME)]


def _rates(entry) -> tuple:
    rates = (entry["input"], entry["output"])
    for rate in rates:
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or rate < 0:
            raise ValueError("rates must be non-negative numbers")
    return tuple(float(rate) for rate in rates)


def _read_pricing() -> dict:
    candidates = pricing_file_candidates()
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if path is None:
        raise PricingError(f"{PRICING_FILE_NAME} not found (looked in: {', '.join(candidates)})")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("unit") != PRICING_UNIT:
            raise ValueError(f"unit must be {PRICING_UNIT!r}")
        models = {model: _rates(entry) for model, entry in data["models"].items()}
        # Tier fallback for model ids not listed verbatim (new snapshots, bare aliases).
        tiers = {tier: models[model] for tier, model in data.get("tiers", {}).items()}
        # Unknown model -> the default (Sonnet) rates as a conservative estimate.
        default = models[data["default"]]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise PricingError(f"{path}: malformed pricing data ({type(exc).__name__}: {exc})") from exc
    return {"models": models, "tiers": tiers, "default": default}


def load_pricing() -> dict:
    """{"models": {id: rates}, "tiers": {tier: rates}, "default": rates}, read
    once per process. Raises PricingError if the data file is missing or bad."""
    global _pricing_cache
    if _pricing_cache is None:
        _pricing_cache = _read_pricing()
    return _pricing_cache


def model_pricing(model: Optional[str]) -> tuple:
    """(input_rate, output_rate) in USD/token: exact match -> tier substring -> default."""
    pricing = load_pricing()
    if model in pricing["models"]:
        return pricing["models"][model]
    m = (model or "").lower()
    for tier, rates in pricing["tiers"].items():
        if tier in m:
            return rates
    return pricing["default"]


def cost_usd(model: Optional[str], tokens_in: Optional[int], tokens_out: Optional[int]) -> float:
    """USD cost of one dispatch. tokens_in must already EXCLUDE cache_read tokens
    (BENCHMARK-CONVENTIONS §1). Null/zero tokens cost 0.0."""
    ti = tokens_in or 0
    to = tokens_out or 0
    if not ti and not to:
        return 0.0
    in_rate, out_rate = model_pricing(model)
    return ti * in_rate + to * out_rate


def git_output(args: list, cwd: Optional[str] = None) -> Optional[str]:
    """Run `git <args>`; return stripped non-empty stdout, or None on any failure (fail-open)."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            if out:
                return out
    except Exception:
        pass
    return None


def read_stdin_json() -> Optional[dict]:
    """Read and parse JSON from stdin. Returns None on error (caller handles)."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw)
    except Exception as exc:
        sys.stderr.write(f"[hooklib] warning: failed to parse stdin JSON: {exc}\n")
        return None


def deny_response(event_name: str, decision_reason: str, system_message: str) -> str:
    """Build a deny JSON response string."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": "deny",
            "permissionDecisionReason": decision_reason,
        },
        "systemMessage": system_message,
    }
    return json.dumps(payload, separators=(",", ":"))
