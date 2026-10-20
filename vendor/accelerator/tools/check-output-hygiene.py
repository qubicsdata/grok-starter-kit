#!/usr/bin/env python3
"""
check-output-hygiene.py — Static pre-review gate for GENERATED PROJECT CODE.

This is the cheap, unconditional safety net that makes risk-tiered review safe
(see ai-baseline/skills/risk-tier-spec.md). It catches the mechanical defect
class that an LLM reviewer should never burn tokens on:

  H1 (xss)        unescaped innerHTML / dangerouslySetInnerHTML interpolation
  H2 (secret)     hardcoded credential literal in non-test source
  H3 (hostport)   hardcoded host:port literal in non-test source (should be env)
  H4 (errschema)  HTTP handlers emitting ad-hoc error statuses with no shared
                  error builder
  H5 (notests)    a code project that ships zero test files

It scans real source trees, not plugin markdown, so it is NOT a fleet validator.
The fleet gate (tools/validate.sh) runs it in --calibrate mode against its own
fixtures to prove the checker itself is correct (0 on clean, >=4 on buggy).

Usage:
    python3 tools/check-output-hygiene.py <target-dir>   # scan generated code
    python3 tools/check-output-hygiene.py --calibrate      # self-test (gate)

Exit codes (scan mode):  0 = clean, 1 = >=1 finding
Exit codes (--calibrate): 0 = clean:0 & buggy:>=4, 1 = false-positive or miss
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_DIR = REPO_ROOT / "tools" / "calibration"

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".mjs"}

# Directories never worth scanning for app hygiene.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

# Sanitizers that make dangerouslySetInnerHTML acceptable (file-level is fine here).
SANITIZE_INDICATORS = ("sanitize", "dompurify")

TEST_NAME_RE = re.compile(r"(^test_.*\.py$|.*_test\.py$|.*\.test\.[jt]sx?$|.*\.spec\.[jt]sx?$)")
SECRET_RE = re.compile(
    r"""(?ix)\b(password|passwd|secret|api[_-]?key|apikey|access[_-]?key|
        auth[_-]?token|private[_-]?key)\b\s*[:=]\s*["'][^"'\s]{6,}["']"""
)
# A literal host:port that should come from config/env.
HOSTPORT_RE = re.compile(r"""["'](?:https?://)?(?:localhost|127\.0\.0\.1)(?::\d{2,5})["']""")
# An innerHTML assignment and its right-hand side (capped), so interpolation is
# judged AT THE ASSIGNMENT SITE — not by whether the file mentions an escaper
# somewhere else. Catches `el.innerHTML = arr.map(x => `...${x}...`).join('')`,
# including dashboards embedded inside Python triple-quoted strings.
INNERHTML_ASSIGN_RE = re.compile(r"\.innerHTML\s*\+?=\s*(.{0,800}?);", re.DOTALL)
INTERP_RE = re.compile(r"\$\{([^}]*)\}")
ESCAPE_CALL_RE = re.compile(r"(?i)\b(esc\w*|escape\w*|sanitize\w*|encodeuri\w*|dompurify)\b")
DANGEROUS_RE = re.compile(r"dangerouslySetInnerHTML")
# Inline error-status emission, e.g. status_code=400, send_response(404), status(500).
ERR_STATUS_RE = re.compile(r"(status(?:_code)?\s*[=(]\s*|send_response\(\s*|\.status\(\s*)[45]\d\d\b")
SHARED_ERR_RE = re.compile(
    r"(?i)(def\s+_?(send_)?error|error_response|make_error|_error\b|HTTPException|error_envelope)"
)
HANDLER_RE = re.compile(
    r"(?i)(@app\.(route|get|post|put|delete|patch)|def\s+do_(GET|POST|PUT|DELETE)|"
    r"BaseHTTPRequestHandler|FastAPI\(|Flask\()"
)


BARE_IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")


def _risky_interp(expr: str) -> bool:
    """A template interpolation is risky if it injects DATA into innerHTML without
    escaping. Escaped expressions and bare local identifiers (composed, already-
    escaped HTML fragments like ${rows}) are safe by construction; member access
    or calls on data (${d.type}, ${JSON.stringify(e.payload)}) must be escaped."""
    e = expr.strip()
    if ESCAPE_CALL_RE.search(e):
        return False
    if BARE_IDENT_RE.match(e):
        return False
    return ("." in e) or ("(" in e)


def _iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def _is_test_file(p: Path) -> bool:
    return bool(TEST_NAME_RE.match(p.name)) or "test" in {part.lower() for part in p.parts}


def check_xss(root: Path) -> list[str]:
    # Scan all code files, not just web files: dashboards are routinely embedded
    # inside Python string literals, which is exactly where XSS hides.
    findings = []
    for p in _iter_files(root):
        if p.suffix not in CODE_EXT:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(root)

        # innerHTML assignment with an unescaped interpolation OF DATA at the site.
        for m in INNERHTML_ASSIGN_RE.finditer(text):
            rhs = m.group(1)
            risky = [expr for expr in INTERP_RE.findall(rhs) if _risky_interp(expr)]
            if risky:
                findings.append(
                    f"H1(xss): {rel} writes innerHTML with unescaped interpolation "
                    f"(e.g. ${{{risky[0].strip()[:40]}}})"
                )
                break

        # React dangerouslySetInnerHTML with no sanitizer anywhere in the file.
        if DANGEROUS_RE.search(text) and not any(s in text.lower() for s in SANITIZE_INDICATORS):
            findings.append(f"H2(xss): {rel} uses dangerouslySetInnerHTML with no sanitizer")
    return findings


def check_secrets_and_config(root: Path) -> list[str]:
    findings = []
    for p in _iter_files(root):
        if p.suffix not in CODE_EXT or _is_test_file(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(root)
        for m in SECRET_RE.finditer(text):
            findings.append(f"H3(secret): {rel} hardcodes a credential literal ({m.group(1)})")
            break
        for ln in text.splitlines():
            if HOSTPORT_RE.search(ln) and "env" not in ln.lower() and "getenv" not in ln.lower():
                findings.append(f"H4(hostport): {rel} hardcodes a host:port literal (should come from env/config)")
                break
    return findings


def check_error_schema(root: Path) -> list[str]:
    findings = []
    for p in _iter_files(root):
        if p.suffix not in CODE_EXT or _is_test_file(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if not HANDLER_RE.search(text):
            continue
        err_count = len(ERR_STATUS_RE.findall(text))
        if err_count >= 2 and not SHARED_ERR_RE.search(text):
            rel = p.relative_to(root)
            findings.append(
                f"H5(errschema): {rel} defines HTTP handlers emitting {err_count} ad-hoc error "
                f"statuses with no shared error builder"
            )
    return findings


def check_has_tests(root: Path) -> list[str]:
    has_code = False
    has_test = False
    for p in _iter_files(root):
        if p.suffix in CODE_EXT:
            has_code = True
            if _is_test_file(p):
                has_test = True
    if has_code and not has_test:
        return ["H6(notests): project contains source code but ships zero test files"]
    return []


def scan(root: Path) -> list[str]:
    findings = []
    findings.extend(check_xss(root))
    findings.extend(check_secrets_and_config(root))
    findings.extend(check_error_schema(root))
    findings.extend(check_has_tests(root))
    return findings


def _scan_mode(target: str) -> int:
    root = Path(target).resolve()
    if not root.exists():
        print(f"ERROR: target not found: {root}", file=sys.stderr)
        return 1
    findings = scan(root)
    print("=" * 70)
    print(f"OUTPUT HYGIENE — {root}")
    print("=" * 70)
    if findings:
        for f in findings:
            print(f"  FINDING: {f}")
        print(f"\nFAIL — {len(findings)} hygiene finding(s)")
        return 1
    print("  (no findings)")
    print("\nPASS — output is hygienic")
    return 0


def _calibrate_mode() -> int:
    clean_dir = CALIBRATION_DIR / "hygiene-clean"
    buggy_dir = CALIBRATION_DIR / "hygiene-buggy"
    for d in (clean_dir, buggy_dir):
        if not d.exists():
            print(f"ERROR: hygiene fixture not found: {d}", file=sys.stderr)
            return 1

    print("=" * 70)
    print("OUTPUT-HYGIENE CALIBRATION")
    print("=" * 70)

    print("\n[FIXTURE] hygiene-clean (expected: 0 findings)")
    clean = scan(clean_dir)
    if clean:
        print(f"  RESULT: FAIL — {len(clean)} finding(s) [FALSE POSITIVE]")
        for f in clean:
            print(f"  FINDING: {f}")
    else:
        print("  RESULT: PASS — 0 findings (no false positives)")

    print("\n[FIXTURE] hygiene-buggy (expected: >=4 findings)")
    buggy = scan(buggy_dir)
    for f in buggy:
        print(f"  FINDING: {f}")
    if len(buggy) >= 4:
        print(f"  RESULT: PASS — {len(buggy)} finding(s) caught")
    else:
        print(f"  RESULT: FAIL — only {len(buggy)} finding(s) [MISSED SEEDED DEFECTS]")

    print("\n" + "=" * 70)
    false_positive = len(clean) > 0
    missed = len(buggy) < 4
    if false_positive or missed:
        if false_positive:
            print(f"FAIL — clean fixture got {len(clean)} false finding(s)")
        if missed:
            print(f"FAIL — buggy fixture yielded only {len(buggy)} finding(s) (need >=4)")
        return 1
    print(f"PASS — clean: 0 findings, buggy: {len(buggy)} finding(s) caught")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    if argv[1] == "--calibrate":
        return _calibrate_mode()
    return _scan_mode(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
