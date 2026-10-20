#!/usr/bin/env python3
"""check-craft-packs.py — validate craft packs against craft-pack-schema.

For every */skills/*-craft.md (or files passed as args), assert:
  - all six canonical schema sections are present and non-empty
  - no placeholder tokens
  - Section 6 references at least one skill name that exists in the repo
Exit non-zero if any pack fails.
"""
import glob
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SECTIONS = [
    "## Section 1 — Decision Domains",
    "## Section 2 — Constraint Inputs",
    "## Section 3 — Opinionated Defaults",
    "## Section 4 — Derivation Rules",
    "## Section 5 — Recommendation Output Contract",
    "## Section 6 — Enforcement Handoff",
]
PLACEHOLDERS = ["TBD", "TODO", "FIXME", "fill in"]
MIN_BODY = 20


def existing_skill_slugs():
    slugs = set()
    for path in REPO_ROOT.glob("*/skills/*.md"):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^name:\s*(\S+)", text, re.MULTILINE)
        if m:
            slugs.add(m.group(1))
    return slugs


def skill_corpus():
    """Return concatenated text of all skill files."""
    parts = []
    for path in REPO_ROOT.glob("*/skills/*.md"):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def violation_id_families(text):
    """Extract violation-ID families referenced in text.

    A violation-ID token looks like DS-CL-1, DS-CL-*, VH-1, A11Y-1.4.3.
    The FAMILY is the leading segments before the first purely-numeric segment:
      DS-CL-1  -> DS-CL
      VH-1     -> VH
      A11Y-1   -> A11Y  (A11Y-1.4.3 also yields A11Y from the matched token A11Y-1)
      DS-CL-*  -> DS-CL
    """
    pattern = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\*?")
    families = set()
    for token in pattern.findall(text):
        token_stripped = token.rstrip("*")
        segments = token_stripped.split("-")
        family_parts = []
        for seg in segments:
            if re.search(r"[A-Za-z]", seg):
                family_parts.append(seg)
            else:
                break
        if family_parts:
            families.add("-".join(family_parts))
    return families


def section_body(text, header):
    start = text.find(header)
    if start == -1:
        return None
    start += len(header)
    end = len(text)
    for other in SECTIONS:
        if other == header:
            continue
        oidx = text.find(other)
        if start <= oidx < end:
            end = oidx
    return text[start:end].strip()


def check_pack(path, slugs, corpus):
    errors = []
    text = path.read_text(encoding="utf-8")
    for header in SECTIONS:
        body = section_body(text, header)
        if body is None:
            errors.append(f"missing section: '{header}'")
        elif len(body) < MIN_BODY:
            errors.append(f"section too short/empty: '{header}'")
    for token in PLACEHOLDERS:
        if token in text:
            errors.append(f"placeholder token found: '{token}'")
    sec6 = section_body(text, SECTIONS[5])
    if sec6:
        if not any(slug in sec6 for slug in slugs):
            errors.append("Section 6 references no existing skill slug")
        for family in sorted(violation_id_families(sec6)):
            needle = f"{family}-"
            if needle not in corpus:
                errors.append(
                    f"Section 6 cites violation-ID family '{needle}' that exists in no skill"
                )
    return errors


def main(argv):
    args = argv[1:]
    if args:
        files = [Path(a) for a in args]
    else:
        files = sorted(Path(p) for p in glob.glob(str(REPO_ROOT / "*/skills/*-craft.md")))
    slugs = existing_skill_slugs()
    corpus = skill_corpus()
    total = 0
    for path in files:
        errs = check_pack(path, slugs, corpus)
        label = path.name
        if errs:
            total += len(errs)
            print(f"FAIL: {label}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK: {label}")
    if total:
        print(f"\ncraft-pack check FAILED with {total} error(s)")
        return 1
    print(f"\ncraft-pack check passed ({len(files)} pack(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
