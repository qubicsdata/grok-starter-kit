#!/usr/bin/env python3
"""
check-model-ids.py — model-ID single-source-of-truth gate.

tools/model-ids.json is the machine authority for model IDs fleet-wide
(prose rationale: ai-baseline/skills/model-tier-guide.md). Checks:
  1. the guide's tier table carries exactly the canonical IDs
  2. every plugin agents/skills frontmatter model: is allowed, not deprecated
  3. agent-builder non-frontmatter bodies contain NO hardcoded model-ID literal
     (they reference tiers by name; frontmatter is exempt)
  4. the hook pricing data (pricing.json) prices exactly the canonical tiers,
     each tier and the default pointing at a priced model

Usage:
    python3 tools/check-model-ids.py
    python3 tools/check-model-ids.py --calibrate
Exit 0 = clean, 1 = >=1 finding.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_IDS_PATH = REPO_ROOT / "tools" / "model-ids.json"
GUIDE_PATH = REPO_ROOT / "ai-baseline" / "skills" / "model-tier-guide.md"
PRICING_PATH = REPO_ROOT / "pricing.json"
NON_PLUGIN_DIRS = {"docs", "benchmarks", "tools", ".git", ".claude", ".claude-plugin"}
MODEL_FRONT_RE = re.compile(r"^model:\s*(.+?)\s*$", re.MULTILINE)
LITERAL_RE = re.compile(r"(?:claude-)?(?:opus|sonnet|haiku)-[0-9][\w.-]*")


def load_ids(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["canonical"], set(data["allowed"]), set(data["deprecated"])


def split_frontmatter(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[: end + 4], text[end + 4:]
    return "", text


def check_guide(canonical, guide_path):
    findings, text = [], Path(guide_path).read_text(encoding="utf-8")
    for tier, model_id in canonical.items():
        m = re.search(r"\*\*" + tier + r"\*\*\s*\|\s*`([^`]+)`", text)
        if not m:
            findings.append(f"guide: no tier-table row for '{tier}'")
        elif m.group(1) != model_id:
            findings.append(
                f"guide: tier '{tier}' lists `{m.group(1)}` but canonical is `{model_id}`")
    return findings


def check_frontmatter(allowed, deprecated, root):
    findings = []
    for pj in sorted(Path(root).glob("*/.claude-plugin/plugin.json")):
        plugin = pj.parent.parent
        if plugin.name in NON_PLUGIN_DIRS:
            continue
        for sub in ("agents", "skills"):
            d = plugin / sub
            if not d.exists():
                continue
            for f in sorted(d.rglob("*.md")):
                fm, _ = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                for val in MODEL_FRONT_RE.findall(fm):
                    if val in deprecated:
                        findings.append(f"{f.relative_to(root)}: DEPRECATED model id '{val}'")
                    elif val not in allowed:
                        findings.append(f"{f.relative_to(root)}: unknown model id '{val}'")
    return findings


def check_builder_bodies(root):
    findings = []
    for sub in ("agents", "skills", "commands"):
        d = Path(root) / "agent-builder" / sub
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.md")):
            _, body = split_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
            for m in LITERAL_RE.findall(body):
                findings.append(
                    f"{f.relative_to(root)}: hardcoded model literal '{m}' in body — "
                    "name the tier and resolve via tools/model-ids.json")
    return findings


def check_pricing_tiers(canonical, pricing_path):
    try:
        data = json.loads(Path(pricing_path).read_text(encoding="utf-8"))
        models, tiers, default = data["models"], data["tiers"], data["default"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"pricing: {Path(pricing_path).name} unreadable ({type(exc).__name__})"]
    findings = []
    if sorted(tiers) != sorted(canonical):
        findings.append(f"pricing: tiers {sorted(tiers)} differ from canonical {sorted(canonical)}")
    for tier, model_id in sorted(tiers.items()):
        if model_id not in models:
            findings.append(f"pricing: tier '{tier}' points at unpriced model '{model_id}'")
    if default not in models:
        findings.append(f"pricing: default '{default}' is not a priced model")
    return findings


def run_all(root=REPO_ROOT, ids_path=MODEL_IDS_PATH, guide_path=GUIDE_PATH,
            pricing_path=PRICING_PATH):
    canonical, allowed, deprecated = load_ids(ids_path)
    return (check_guide(canonical, guide_path)
            + check_frontmatter(allowed, deprecated, root)
            + check_builder_bodies(root)
            + check_pricing_tiers(canonical, pricing_path))


def calibrate() -> int:
    fx = REPO_ROOT / "tools" / "tests" / "model-ids-fixtures"
    ok = True
    for name, expect_clean in (("clean", True), ("dirty", False)):
        root = fx / name
        canonical, allowed, deprecated = load_ids(root / "model-ids.json")
        findings = (check_guide(canonical, root / "model-tier-guide.md")
                    + check_frontmatter(allowed, deprecated, root))
        good = (len(findings) == 0) if expect_clean else (len(findings) >= 2)
        print(f"{'PASS' if good else 'FAIL'} fixture {name}: {len(findings)} finding(s)")
        ok = ok and good
    print("CALIBRATE " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv) -> int:
    if "--calibrate" in argv:
        return calibrate()
    findings = run_all()
    for f in findings:
        print(f)
    print(f"{'CLEAN' if not findings else 'FINDINGS: ' + str(len(findings))}")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
