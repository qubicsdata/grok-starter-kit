#!/usr/bin/env python3
"""
session_gateway.py — SessionStart hook: the Accelerator push gateway.

Injects a short "front door" block at session start so the fleet is PRESENT and
reachable from turn one, instead of summoned by name. Two variants:

  - superpowers present  → deferential (stays out of the process-discipline lane)
  - superpowers absent    → standalone (names /accelerate as the default arc)

After the front door, a single product-passport line is appended ONLY when the
repo carries docs/product/passport.json — a mid-story resume pointer when
.product-session.json exists, else the stage + ready-lane count pointing at
/build-next. An empty ready lane with no active story adds zero output.

Then a single "Maintenance:" line is appended ONLY when deterministic debt
signals exist (queued unscored outputs, budget pressure, durable memory
present). Two or more signals collapse into one /steward pointer; zero signals
add zero output.

Fail-safe: ANY error emits the deferential-light variant and exits 0. A broken
gateway degrades to a minimal note, never to a crashed session. Debt detection
is advisory — its failure never degrades the front door itself.

Usage:
    echo '{}' | python3 tools/hooks/session_gateway.py
    python3 tools/hooks/session_gateway.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _hooklib import get_repo_root  # noqa: E402

# Maintenance-debt thresholds (deterministic; tuned for zero noise below them).
PENDING_THRESHOLD = 5     # queued unscored stubs before we surface /score-pending
BUDGET_RATIO = 0.8        # spent/limit fraction before we surface /budget-status


def plugin_count(repo_root: str) -> int:
    """Count plugins from registry.json. Returns 0 if unavailable."""
    try:
        data = json.loads((Path(repo_root) / "registry.json").read_text())
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data.get("plugins", data))
    except Exception:
        pass
    return 0


def detect_superpowers(repo_root: str) -> bool:
    """Best-effort detection of an installed superpowers toolkit.

    Checks, in order: an explicit env override and the Claude plugin cache.
    Any signal → True. Never raises.
    """
    try:
        override = os.environ.get("ACCELERATOR_SUPERPOWERS")
        if override is not None:
            return override.strip().lower() in {"1", "true", "yes"}

        home = Path(os.path.expanduser("~"))
        cache_hits = list((home / ".claude" / "plugins" / "cache").glob("**/superpowers"))
        if cache_hits:
            return True
    except Exception:
        pass
    return False


def build_message(count: int, superpowers_present: bool) -> str:
    """Construct the front-door block. `count` of 0 → no number is shown."""
    fleet = f"Accelerator fleet active ({count} plugins)." if count else "Accelerator fleet active."
    common = (
        f"{fleet} Governance on: audit-trail, cost-gate, /enrich. "
        "For domain work — APIs, data, ops, security, releases, and more — reach for the "
        "matching companion, or `/accelerator \"<goal>\"` to route to the right command."
    )
    if superpowers_present:
        return (
            common
            + " Use `/accelerate` for multi-step work. "
            "Process discipline (TDD, debugging, planning) → defer to your process toolkit."
        )
    return (
        common
        + " `/accelerate \"<goal>\"` is your default arc for any multi-step task "
        "(route → enrich → plan → execute → review)."
    )


def detect_debt(repo_root: str) -> List[str]:
    """Deterministic maintenance-debt signals — pure file stats, no subprocess.

    Each check is independently fail-open: an unreadable or malformed artifact
    contributes no line. Returns [] when the repo carries no debt (zero-noise rule).
    Budget is well under 10ms: three stat calls plus at most two small file reads.
    """
    root = Path(repo_root)
    lines: List[str] = []

    # (a) unscored feedback stubs queued by the Stop hook
    try:
        pending = root / ".ai-evolution" / "feedback.jsonl.pending"
        if pending.is_file():
            n = sum(
                1
                for ln in pending.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()
            )
            if n >= PENDING_THRESHOLD:
                lines.append(f"{n} unscored outputs pending — /score-pending")
    except Exception:
        pass

    # (b) session budget pressure (same file the Opus cost gate reads)
    try:
        budget_file = root / ".ai-baseline" / "budget.json"
        if budget_file.is_file():
            budget = json.loads(budget_file.read_text(encoding="utf-8"))
            limit = budget.get("limit_usd")
            spent = budget.get("spent_usd", 0)
            if (
                isinstance(limit, (int, float)) and not isinstance(limit, bool) and limit > 0
                and isinstance(spent, (int, float)) and not isinstance(spent, bool)
            ):
                ratio = spent / limit
                if ratio >= BUDGET_RATIO:
                    lines.append(f"budget {round(ratio * 100)}% — /budget-status")
    except Exception:
        pass

    # (c) durable memory exists — make it present so it gets used
    try:
        memory = root / ".ai-memory"
        if memory.is_dir() and any(memory.glob("*/*.json")):
            lines.append("memory present: /recall")
    except Exception:
        pass

    return lines


def detect_passport(repo_root: str) -> Optional[str]:
    """Product-passport presence line — one JSON read, zero directory scans.

    Reads only `stage` + `ready_count` from docs/product/passport.json (both
    denormalized by product-companion for exactly this one-read need). A
    parseable root `.product-session.json` takes precedence with a precise
    mid-story resume pointer. Fail-open: a missing or malformed file
    contributes nothing, and an empty ready lane with no active story stays
    silent (earned-suggestion rule).
    """
    try:
        root = Path(repo_root)
        passport_file = root / "docs" / "product" / "passport.json"
        if not passport_file.is_file():
            return None
        passport = json.loads(passport_file.read_text(encoding="utf-8"))

        session_file = root / ".product-session.json"
        if session_file.is_file():
            try:
                session = json.loads(session_file.read_text(encoding="utf-8"))
                story = session.get("story")
                ac_met = session.get("ac_met")
                ac_total = session.get("ac_total")
                if isinstance(story, str) and story:
                    if (
                        isinstance(ac_met, int) and not isinstance(ac_met, bool)
                        and isinstance(ac_total, int) and not isinstance(ac_total, bool)
                    ):
                        return f"Mid-story {story} ({ac_met}/{ac_total} AC) — /build-next resumes."
                    return f"Mid-story {story} — /build-next resumes."
            except Exception:
                pass  # malformed session file → fall back to the passport line

        stage = passport.get("stage")
        ready = passport.get("ready_count")
        if (
            isinstance(stage, str) and stage
            and isinstance(ready, int) and not isinstance(ready, bool) and ready > 0
        ):
            noun = "story" if ready == 1 else "stories"
            return (
                f"Project passport: stage={stage} — {ready} {noun} ready; "
                "/build-next picks the top one."
            )
    except Exception:
        pass
    return None


def compose_maintenance(lines: List[str]) -> Optional[str]:
    """One Maintenance line, or None. 2+ signals collapse to a single /steward pointer."""
    if not lines:
        return None
    if len(lines) == 1:
        return f"Maintenance: {lines[0]}"
    return f"Maintenance: {len(lines)} upkeep signals — run /steward"


# The minimal block emitted whenever anything goes wrong (matches the deferential shape).
SAFE_FALLBACK = (
    "Accelerator fleet active. Governance on: audit-trail, cost-gate, /enrich. "
    "Use `/accelerator \"<goal>\"` to route to the right command, or `/accelerate` for "
    "multi-step work."
)


def emit(context: str) -> None:
    """Print the SessionStart additionalContext payload."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(payload, separators=(",", ":")))


def run() -> str:
    """Build the message for the current environment. Returns the context string."""
    repo_root = get_repo_root()
    context = build_message(plugin_count(repo_root), detect_superpowers(repo_root))
    try:
        passport = detect_passport(repo_root)
        if passport:
            context += "\n" + passport
    except Exception:
        pass  # passport surfacing is advisory — never degrade the front door
    try:
        maintenance = compose_maintenance(detect_debt(repo_root))
        if maintenance:
            context += "\n" + maintenance
    except Exception:
        pass  # debt detection is advisory — never degrade the front door
    return context


def selftest() -> int:
    present = build_message(24, True)
    absent = build_message(24, False)
    zero = build_message(0, False)

    assert "defer" in present, "present variant must defer to process toolkit"
    assert "TDD" not in absent, "absent variant must not mention process discipline"
    assert "/accelerate" in absent and "default arc" in absent, "absent must name the arc"
    assert "/accelerator" in present and "/accelerator" in absent, "both name the router"
    assert "/enrich" in present and "/enrich" in absent, "both name /enrich"
    assert "24 plugins" in present, "count shown when known"
    assert "plugins)" not in zero, "no count shown when unknown"
    assert "Accelerator fleet active." in SAFE_FALLBACK, "fallback well-formed"

    assert compose_maintenance([]) is None, "no debt → no Maintenance line (zero-noise)"
    one = compose_maintenance(["memory present: /recall"])
    assert one == "Maintenance: memory present: /recall", "single signal keeps its command"
    many = compose_maintenance(["a", "b"])
    assert many is not None and "/steward" in many, "2+ signals collapse to /steward"

    # detect_passport fixtures — fail-open + earned-silence discipline
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="gateway-passport-"))
    try:
        assert detect_passport(str(tmp)) is None, "no passport → no line"

        product = tmp / "docs" / "product"
        product.mkdir(parents=True)
        (product / "passport.json").write_text(
            json.dumps({"stage": "building", "ready_count": 4}), encoding="utf-8"
        )
        line = detect_passport(str(tmp))
        assert line == (
            "Project passport: stage=building — 4 stories ready; "
            "/build-next picks the top one."
        ), f"passport line malformed: {line}"

        (product / "passport.json").write_text(
            json.dumps({"stage": "building", "ready_count": 1}), encoding="utf-8"
        )
        line = detect_passport(str(tmp))
        assert line is not None and "1 story ready" in line, f"singular noun: {line}"

        (product / "passport.json").write_text(
            json.dumps({"stage": "idea", "ready_count": 0}), encoding="utf-8"
        )
        assert detect_passport(str(tmp)) is None, "empty ready lane + no active story → silence"

        (tmp / ".product-session.json").write_text(
            json.dumps({"story": "S-004", "phase": "execute", "ac_met": 2, "ac_total": 5}),
            encoding="utf-8",
        )
        line = detect_passport(str(tmp))
        assert line == "Mid-story S-004 (2/5 AC) — /build-next resumes.", (
            f"mid-story line malformed: {line}"
        )

        (tmp / ".product-session.json").write_text("{not json", encoding="utf-8")
        assert detect_passport(str(tmp)) is None, (
            "malformed session + empty ready lane → silence (fail-open)"
        )

        (tmp / ".product-session.json").unlink()
        (product / "passport.json").write_text("{not json", encoding="utf-8")
        assert detect_passport(str(tmp)) is None, "malformed passport → silence (fail-open)"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("session_gateway selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Accelerator SessionStart gateway")
    parser.add_argument("--selftest", action="store_true", help="Run assertions and exit")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    try:
        emit(run())
    except Exception as exc:  # never wedge the session
        sys.stderr.write(f"[session_gateway] warning: {exc}\n")
        emit(SAFE_FALLBACK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
