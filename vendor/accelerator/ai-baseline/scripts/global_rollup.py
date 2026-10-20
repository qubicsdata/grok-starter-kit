#!/usr/bin/env python3
"""
global_rollup.py — roll per-repo Accelerator telemetry up to the fleet-global brain.

Every state file the fleet writes today resolves to the consumer's git root, so two
projects share nothing. This script copies each repo's audit + feedback journals into
a global home (~/.accelerator/ by default, ACCELERATOR_HOME to override) so
/fleet-status can see the whole fleet at once.

Pure stdlib, Python 3.8+. Fail-open: any runtime error writes a warning to stderr and
exits 0 — a broken rollup never blocks a session. cwd-independent: the repo root is
resolved $CLAUDE_PROJECT_DIR → git → cwd (same 3-step resolution as
tools/hooks/_hooklib.py; replicated here because this script ships inside the
ai-baseline plugin, where tools/ does not exist).

Usage:
    python3 global_rollup.py --sync [--repo PATH]   # merge this repo's telemetry up
    python3 global_rollup.py --report [--json]      # fleet table across all repos
    python3 global_rollup.py --sync --report        # both, in that order

--sync merges append-only (dedupe on full-line identity, never delete) into
~/.accelerator/repos/<slug>/ and rewrites that repo's summary.json. --repo overrides
repo-root resolution (used by tests and multi-checkout syncs).
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Relative price weights (x Sonnet), blended input+output. Source of truth:
# tools/cost-units.py TIER_WEIGHTS (per BENCHMARK-CONVENTIONS.md §1) — duplicated
# here because the shipped plugin cannot import tools/. tokens_in already excludes
# cheap cache-read tokens (see tools/hooks/transcript_usage.py), so the sum below
# follows the fleet's cache_read-excluding cost convention.
TIER_WEIGHTS = {"opus": 5.0, "sonnet": 1.0, "haiku": 0.25}


def accelerator_home() -> Path:
    """Global brain root: $ACCELERATOR_HOME override (tests), else ~/.accelerator."""
    override = os.environ.get("ACCELERATOR_HOME", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".accelerator"


def get_repo_root() -> str:
    """Resolve the repo root: $CLAUDE_PROJECT_DIR → git → cwd.

    Replicates tools/hooks/_hooklib.get_repo_root() — keep the two in step.
    $CLAUDE_PROJECT_DIR wins: the process cwd can sit in a different git repo
    (worktree/sibling checkout), and git-first would sync the wrong repo.
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


def repo_slug(repo_root: Path) -> str:
    """Stable per-repo slug: origin-URL basename if available, else dirname."""
    name = ""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip().rstrip("/")
            name = url.split("/")[-1].split(":")[-1]
            if name.endswith(".git"):
                name = name[: -len(".git")]
    except Exception:
        pass
    if not name:
        name = repo_root.resolve().name
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-.")
    return slug or "unnamed-repo"


def merge_file(src: Path, dst: Path) -> int:
    """Append-only merge of src JSONL lines into dst.

    Dedupe on full-line identity; existing dst lines are never rewritten or
    deleted. Returns the number of lines appended.
    """
    src_lines = [l for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    existing_text = ""
    if dst.exists():
        existing_text = dst.read_text(encoding="utf-8")
    seen = {l for l in existing_text.splitlines() if l.strip()}
    new_lines = []
    for line in src_lines:
        if line not in seen:
            seen.add(line)
            new_lines.append(line)
    if not new_lines:
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("a", encoding="utf-8") as fh:
        if existing_text and not existing_text.endswith("\n"):
            fh.write("\n")
        fh.write("\n".join(new_lines) + "\n")
    return len(new_lines)


def _model_tier(model) -> str:
    m = (model or "").lower()
    for tier in ("opus", "sonnet", "haiku"):
        if tier in m:
            return tier
    return ""


def _load_records(path: Path) -> list:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def summarize(slug_dir: Path, slug: str) -> dict:
    """Summary of everything accumulated in the global copy (not just this sync)."""
    audit_files = sorted(slug_dir.glob("audit.*.jsonl"))
    feedback_file = slug_dir / "feedback.jsonl"
    audit_records = []
    for f in audit_files:
        audit_records.extend(_load_records(f))
    feedback_records = _load_records(feedback_file) if feedback_file.exists() else []

    cost = 0.0
    for r in audit_records:
        toks = (r.get("tokens_in") or 0) + (r.get("tokens_out") or 0)
        cost += toks * TIER_WEIGHTS.get(_model_tier(r.get("model")), 0.0)

    # NOTE: despite the field name (kept for summary.json compatibility),
    # last_sync is the NEWEST RECORD timestamp across the merged journals — a
    # repo synced today whose newest record is old reports that old date. The
    # report column is therefore labelled "last record", not "last sync".
    timestamps = [r.get("ts") for r in audit_records + feedback_records
                  if isinstance(r.get("ts"), str) and r.get("ts")]
    last_sync = max(timestamps) if timestamps else datetime.now(
        timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return {
        "slug": slug,
        "records": len(audit_records) + len(feedback_records),
        "audit_records": len(audit_records),
        "feedback_records": len(feedback_records),
        "cost_units": round(cost, 1),
        "last_sync": last_sync,
    }


def sync(repo_override: str = "") -> None:
    repo_root = Path(repo_override) if repo_override else Path(get_repo_root())
    slug = repo_slug(repo_root)
    slug_dir = accelerator_home() / "repos" / slug

    sources = sorted(glob.glob(str(repo_root / ".ai-baseline" / "audit.*.jsonl")))
    feedback = repo_root / ".ai-evolution" / "feedback.jsonl"
    if feedback.exists():
        sources.append(str(feedback))

    appended = 0
    for src in sources:
        appended += merge_file(Path(src), slug_dir / Path(src).name)

    slug_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(slug_dir, slug)
    tmp = slug_dir / "summary.json.tmp"
    tmp.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, slug_dir / "summary.json")
    print(f"synced {slug}: {appended} new record(s), "
          f"{summary['records']} total, cost_units={summary['cost_units']:,.1f}")


def report(as_json: bool = False) -> None:
    rows = []
    for summary_path in sorted(accelerator_home().glob("repos/*/summary.json")):
        try:
            s = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({
            "repo": s.get("slug") or summary_path.parent.name,
            "records": s.get("records", 0),
            "cost_units": s.get("cost_units", 0.0),
            "last_sync": s.get("last_sync", ""),
        })
    rows.sort(key=lambda r: r["cost_units"], reverse=True)

    if as_json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("fleet: no synced repos yet — run --sync from a repo first")
        return
    name_w = max(len("repo"), max(len(r["repo"]) for r in rows))
    print(f"{'repo':<{name_w}}  {'records':>8}  {'est. cost (cu)':>14}  last record")
    for r in rows:
        print(f"{r['repo']:<{name_w}}  {r['records']:>8,}  "
              f"{r['cost_units']:>14,.1f}  {r['last_sync']}")
    total_cost = sum(r["cost_units"] for r in rows)
    total_recs = sum(r["records"] for r in rows)
    print(f"{'TOTAL':<{name_w}}  {total_recs:>8,}  {total_cost:>14,.1f}")


def main(argv: list) -> int:
    do_sync = do_report = as_json = False
    repo_override = ""
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--sync":
            do_sync = True
        elif arg == "--report":
            do_report = True
        elif arg == "--json":
            as_json = True
        elif arg == "--repo" and i + 1 < len(argv):
            repo_override = argv[i + 1]
            i += 1
        else:
            print(__doc__)
            return 2
        i += 1
    if not (do_sync or do_report):
        print(__doc__)
        return 2
    if do_sync:
        sync(repo_override)
    if do_report:
        report(as_json)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # fail-open: never wedge the caller
        sys.stderr.write(f"[global_rollup] warning: {type(exc).__name__}: {exc} (fail-open)\n")
        sys.exit(0)
