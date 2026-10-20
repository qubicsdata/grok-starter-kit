#!/usr/bin/env python3
"""
check-builder-session.py — mechanical Gate 1/2 validator for .builder-session.md.

Verifies well-formed, in-order gate records (grammar: agent-builder
skills/checkpoint-gate.md "Checkpoint Grammar"). It cannot verify the
reflection was genuine — it converts "publisher trusts prose" into
"publisher blocked without a well-formed record".

Usage:
    python3 tools/check-builder-session.py <session-file> --require design
    python3 tools/check-builder-session.py <session-file> --require publish
    python3 tools/check-builder-session.py --calibrate
Exit 0 = ok, 1 = findings, 2 = usage.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ["intake complete", "domain-research complete", "gate-1 cleared",
             "critic pass", "gate-2 cleared", "efficacy journaled", "publish complete"]
CHECKPOINT_RE = re.compile(r"^- ([a-z0-9 -]+?)(?:\s+—.*)?$", re.MULTILINE)
GATE2_SUBSECTIONS = ("### Panel blockers", "### API safety", "### Version correctness")


def _tokens(text):
    found = []
    for raw in CHECKPOINT_RE.findall(text):
        tok = raw.strip()
        # 'efficacy skipped' is NO LONGER aliased to 'efficacy journaled' (2026-07-03
        # loop-closure): silent skip is what kept .ai-evolution/feedback.jsonl empty. It
        # is not canonical, so it never satisfies the required 'efficacy journaled' token.
        if tok in CANONICAL:
            found.append(tok)
    return found


def _checkpoints_section(text):
    m = re.search(r"^## Checkpoints\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else ""


def _section_nonempty(text, heading, subsections):
    m = re.search(re.escape(heading) + r".*?(?=\n## |\Z)", text, re.DOTALL)
    if not m:
        return [f"missing section '{heading}'"]
    body, findings = m.group(0), []
    for sub in subsections:
        sm = re.search(re.escape(sub) + r"\n(.*?)(?=\n#|\Z)", body, re.DOTALL)
        if not sm or not sm.group(1).strip():
            findings.append(f"'{heading}': subsection '{sub}' missing or empty")
    return findings


def validate(text, require):
    findings = []
    mode_m = re.search(r"^Mode:\s*(.+)$", text, re.MULTILINE)
    if not mode_m:
        return ["no 'Mode:' line — not a builder session file"]
    if "## Checkpoints" not in text:
        findings.append("no '## Checkpoints' section")
    toks = _tokens(_checkpoints_section(text))
    order = [CANONICAL.index(t) for t in toks]
    if order != sorted(order) or len(set(toks)) != len(toks):
        findings.append(f"checkpoints out of canonical order or duplicated: {toks}")
    need = ["intake complete", "gate-1 cleared"]
    if require == "publish":
        need += ["critic pass", "gate-2 cleared", "efficacy journaled"]
        # Loop-closure enforcement (2026-07-03): in the dev repo the writer
        # (tools/feedback-append.py) always exists, so the review-efficacy record MUST be
        # journaled — 'efficacy skipped' is not a permitted substitute. This is the gate
        # that makes measurement a non-optional byproduct of the build.
        if re.search(r"^- efficacy skipped\b", _checkpoints_section(text), re.MULTILINE):
            findings.append("'efficacy skipped' is not permitted at publish — journal the "
                            "review-efficacy record (tools/feedback-append.py efficacy)")
    for tok in need:
        if tok not in toks:
            findings.append(f"required checkpoint missing: '{tok}'")
    if "gate-1 cleared" in toks and "Gate 1: CLEARED" not in text:
        findings.append("checkpoint 'gate-1 cleared' without 'Gate 1: CLEARED' record")
    if require == "publish":
        findings += _section_nonempty(text, "## Gate 2", GATE2_SUBSECTIONS)
        statuses = re.findall(r"^Gate 2:\s*(CLEARED|BLOCKED[^\n]*)$", text, re.MULTILINE)
        if not statuses:
            findings.append("no 'Gate 2: CLEARED' record")
        elif not statuses[-1].startswith("CLEARED"):
            findings.append("Gate 2 last status is BLOCKED")
        esc = text.rfind("CRITIC REVIEW: ESCALATE")
        last_pass = text.rfind("- critic pass")
        if esc != -1 and esc > last_pass:
            findings.append("unresolved 'CRITIC REVIEW: ESCALATE' after last critic pass")
    return findings


def calibrate() -> int:
    fx = REPO_ROOT / "tools" / "tests" / "builder-session-fixtures"
    expect = {"complete.md": 0, "missing-gate2.md": 1, "blocked.md": 1, "out-of-order.md": 1,
              "missing-efficacy.md": 1, "efficacy-skipped.md": 1}
    ok = True
    for name, minimum in expect.items():
        n = len(validate((fx / name).read_text(encoding="utf-8"), "publish"))
        good = (n == 0) if minimum == 0 else (n >= minimum)
        print(f"{'PASS' if good else 'FAIL'} fixture {name}: {n} finding(s)")
        ok = ok and good
    print("CALIBRATE " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv) -> int:
    if "--calibrate" in argv:
        return calibrate()
    if len(argv) != 3 or argv[1] != "--require" or argv[2] not in ("design", "publish"):
        print(__doc__)
        return 2
    p = Path(argv[0])
    if not p.is_file():
        print(f"ERROR: session file not found: {p}", file=sys.stderr)
        return 1
    findings = validate(p.read_text(encoding="utf-8", errors="replace"), argv[2])
    for f in findings:
        print(f"BLOCK: {f}")
    print("SESSION OK" if not findings else f"SESSION INVALID: {len(findings)} finding(s)")
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
