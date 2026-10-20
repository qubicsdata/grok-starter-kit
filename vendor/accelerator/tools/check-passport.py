#!/usr/bin/env python3
"""
check-passport.py — deterministic validator for product-companion backlog trees.

Validates a project (or fixture) root's docs/product/ artifacts against the
canonical backlog schema (product-companion/skills/backlog-schema.md). The
DoR/DoD predicates here MIRROR that schema exactly — the two may never disagree.

Checks (rule tag in brackets):
  1. [PASSPORT]    passport.json parses; schema_version known; required keys
                   present; stage in enum; stage_history non-empty, timestamps
                   monotonic, evidence strings non-empty.
  2. [ID-GRAMMAR]  every artifact file matches <[EFSP]-NNN>-<kebab>.md, sits in
                   its type's directory, and frontmatter `id` matches the filename.
  3. [COUNTER]     counters.<type> >= max existing numeric ID per type.
  4. [XLINK]       story `parent` -> existing non-dropped feature/epic; feature
                   `epic` -> existing non-dropped epic; story `persona` ->
                   existing persona; every `blocked_by` ID exists.
  5. [ENUM]        every `status` in its type's enum; wsjf fields in {1,2,3,5,8};
                   `priority` cache = round((bv+tc+rr)/job_size, 2) when present.
  6. [DOR-n]       every `status: ready` story passes DOR-1..7.
  7. [DOD-n]       every `status: done` story passes DOD-1..3 (DOD-4 is advisory).
  8. [READY-COUNT] passport `ready_count` == count of `status: ready` stories.
  9. [DUP-ID]      no two artifacts share an ID; [HISTORY] stage regressions in
                   stage_history are annotated "user-declared".
 10. [PERSONA]     every persona body has the four required sections — `## Goals`
                   (>=2 bullets), `## Pains` (>=2 bullets), `## Context` and
                   `## Success looks like` (both non-empty).

Output: one line per violation — `file: [RULE] message`. Exit 0 when clean, 1 on
any violation. A root without docs/product/ has nothing to validate and passes.

Python 3 stdlib only. Frontmatter is parsed with a minimal deterministic parser
covering exactly the shapes the backlog schema defines (scalars, inline lists,
inline dicts, one nested block for `wsjf`).

Usage:
    python3 tools/check-passport.py [--root <path>]   # validate a project tree
    python3 tools/check-passport.py --selftest        # run the bundled fixtures
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tools" / "tests" / "fixtures" / "passport"

# ---------------------------------------------------------------- canonical constants

KNOWN_SCHEMA_VERSIONS = {"1.0.0"}
REQUIRED_PASSPORT_KEYS = (
    "schema_version",
    "project",
    "one_liner",
    "stage",
    "stage_history",
    "backlog_root",
    "backlog_scheme",
    "counters",
    "ready_count",
    "last_built",
    "release_nudge",
    "created",
    "updated",
)
STAGES = ["idea", "scaffolded", "building", "hardening", "released", "operating"]

TYPE_DIRS = {"persona": "personas", "epic": "epics", "feature": "features", "story": "stories"}
DIR_LETTER = {"personas": "P", "epics": "E", "features": "F", "stories": "S"}

ID_RE = re.compile(r"^[EFSP]-\d{3}$")
FILENAME_RE = re.compile(r"^([EFSP]-\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")

STATUS_ENUM = {
    "personas": {"active", "retired"},
    "epics": {"proposed", "committed", "in-progress", "done", "dropped"},
    "features": {"proposed", "in-progress", "done", "dropped"},
    "stories": {"draft", "ready", "in-progress", "in-review", "blocked", "done", "dropped"},
}
WSJF_ALLOWED = {1, 2, 3, 5, 8}
STORY_WSJF_FIELDS = ("business_value", "time_criticality", "risk_reduction", "job_size")

# DoR / DoD regexes — mirror backlog-schema.md verbatim; they may never disagree.
AC_UNTICKED_RE = re.compile(r"^- \[ \] AC-\d+:")            # DOR-2 line shape
AC_ANY_RE = re.compile(r"^- \[[ xX]\] AC-\d+:")             # DOD-2 line universe
AC_TICKED_RE = re.compile(r"^- \[x\] AC-\d+:")              # DOD-2 tick shape
EVIDENCE_SUFFIX = " — evidence: "                            # DOD-2 evidence marker
REVIEW_VERDICT_RE = re.compile(r"review:\s*\S.*—\s*\S")      # DOD-3 `review: <tier> — <verdict>`
COMMIT_RANGE_RE = re.compile(r"\b[0-9a-fA-F]{7,40}\.\.\.?[0-9a-fA-F]{7,40}\b")  # DOD-3


# ---------------------------------------------------------------- frontmatter parsing

def _strip_comment(value: str) -> str:
    """Drop a trailing `# comment` that is not inside quotes."""
    out: List[str] = []
    in_quote: Optional[str] = None
    for idx, ch in enumerate(value):
        if in_quote:
            if ch == in_quote:
                in_quote = None
            out.append(ch)
        elif ch in "\"'":
            in_quote = ch
            out.append(ch)
        elif ch == "#" and (idx == 0 or value[idx - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).strip()


def _parse_scalar(tok: str):
    if tok in ("null", "~", ""):
        return None
    if tok in ("true", "false"):
        return tok == "true"
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def _parse_value(rest: str):
    if rest.startswith("[") and rest.endswith("]"):
        inner = rest[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(x.strip()) for x in inner.split(",")]
    if rest.startswith("{") and rest.endswith("}"):
        inner = rest[1:-1].strip()
        d: Dict[str, object] = {}
        if inner:
            for pair in inner.split(","):
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    d[k.strip()] = _parse_scalar(v.strip())
        return d
    return _parse_scalar(rest)


def parse_frontmatter(text: str) -> Tuple[Optional[Dict[str, object]], str]:
    """Return (frontmatter dict or None, body). Deterministic, schema-shaped only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text
    fm: Dict[str, object] = {}
    i = 1
    while i < end:
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or raw.startswith((" ", "\t")):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if m is None:
            i += 1
            continue
        key, rest = m.group(1), _strip_comment(m.group(2))
        if rest == "":
            # one-level nested block (the `wsjf:` shape)
            block: Dict[str, object] = {}
            j = i + 1
            while j < end and lines[j].startswith((" ", "\t")):
                sm = re.match(r"^\s+([A-Za-z_][\w-]*):\s*(.*)$", lines[j])
                if sm:
                    block[sm.group(1)] = _parse_scalar(_strip_comment(sm.group(2)))
                j += 1
            fm[key] = block if block else None
            i = j
            continue
        fm[key] = _parse_value(rest)
        i += 1
    body = "\n".join(lines[end + 1:])
    return fm, body


def section(body: str, header: str) -> Optional[str]:
    """Return the text of `## <header>` up to the next `## ` heading, or None."""
    m = re.search(
        rf"^## {re.escape(header)}\s*$(.*?)(?=^## |\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1) if m else None


# ---------------------------------------------------------------- artifact model

class Finding:
    def __init__(self, file: str, rule: str, message: str):
        self.file = file
        self.rule = rule
        self.message = message

    def __str__(self) -> str:
        return f"{self.file}: [{self.rule}] {self.message}"


class Artifact:
    def __init__(self, rel: str, kind_dir: str, art_id: str, fm: Dict[str, object], body: str):
        self.rel = rel            # path relative to root (posix)
        self.kind_dir = kind_dir  # personas | epics | features | stories
        self.id = art_id
        self.fm = fm
        self.body = body


def load_tree(root: Path) -> Tuple[Optional[dict], List[Artifact], List[Finding]]:
    """Load passport + artifacts; emit [PASSPORT]/[ID-GRAMMAR] findings on the way."""
    findings: List[Finding] = []
    product = root / "docs" / "product"

    passport = None
    passport_rel = "docs/product/passport.json"
    passport_file = product / "passport.json"
    if not passport_file.is_file():
        findings.append(Finding(passport_rel, "PASSPORT", "passport.json missing"))
    else:
        try:
            passport = json.loads(passport_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            findings.append(Finding(passport_rel, "PASSPORT", f"not valid JSON: {e}"))

    artifacts: List[Artifact] = []
    for kind_dir in ("personas", "epics", "features", "stories"):
        d = product / kind_dir
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.md")):
            rel = path.relative_to(root).as_posix()
            m = FILENAME_RE.match(path.name)
            if not m:
                findings.append(Finding(
                    rel, "ID-GRAMMAR",
                    "filename must match <[EFSP]-NNN>-<kebab-slug>.md",
                ))
                continue
            art_id = m.group(1)
            if art_id[0] != DIR_LETTER[kind_dir]:
                findings.append(Finding(
                    rel, "ID-GRAMMAR",
                    f"ID prefix '{art_id[0]}-' does not belong in {kind_dir}/",
                ))
                continue
            fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            if fm is None:
                findings.append(Finding(rel, "ID-GRAMMAR", "no frontmatter block found"))
                continue
            if fm.get("id") != art_id:
                findings.append(Finding(
                    rel, "ID-GRAMMAR",
                    f"frontmatter id '{fm.get('id')}' does not match filename ID '{art_id}'",
                ))
                continue
            artifacts.append(Artifact(rel, kind_dir, art_id, fm, body))
    return passport, artifacts, findings


# ---------------------------------------------------------------- individual checks

def check_passport_doc(passport: Optional[dict], findings: List[Finding]) -> None:
    if passport is None:
        return
    rel = "docs/product/passport.json"
    for key in REQUIRED_PASSPORT_KEYS:
        if key not in passport:
            findings.append(Finding(rel, "PASSPORT", f"required key missing: '{key}'"))
    sv = passport.get("schema_version")
    if sv is not None and sv not in KNOWN_SCHEMA_VERSIONS:
        findings.append(Finding(rel, "PASSPORT", f"unknown schema_version: '{sv}'"))
    stage = passport.get("stage")
    if "stage" in passport and stage not in STAGES:
        findings.append(Finding(rel, "PASSPORT", f"stage '{stage}' not in enum {STAGES}"))

    history = passport.get("stage_history")
    if "stage_history" in passport:
        if not isinstance(history, list) or not history:
            findings.append(Finding(rel, "PASSPORT", "stage_history must be a non-empty list"))
        else:
            prev_ts = None
            prev_stage_idx = None
            for n, entry in enumerate(history):
                if not isinstance(entry, dict):
                    findings.append(Finding(rel, "PASSPORT", f"stage_history[{n}] is not an object"))
                    continue
                if not entry.get("evidence"):
                    findings.append(Finding(
                        rel, "HISTORY", f"stage_history[{n}] has an empty evidence string"))
                ts = entry.get("ts")
                if prev_ts is not None and isinstance(ts, str) and isinstance(prev_ts, str) and ts < prev_ts:
                    findings.append(Finding(
                        rel, "HISTORY",
                        f"stage_history[{n}] ts '{ts}' earlier than previous '{prev_ts}' (must be monotonic)"))
                prev_ts = ts if isinstance(ts, str) else prev_ts
                entry_stage = entry.get("stage")
                idx = STAGES.index(entry_stage) if entry_stage in STAGES else None
                if (
                    idx is not None and prev_stage_idx is not None and idx < prev_stage_idx
                    and "user-declared" not in str(entry.get("evidence", ""))
                ):
                    findings.append(Finding(
                        rel, "HISTORY",
                        f"stage_history[{n}] regresses to '{entry_stage}' without a "
                        "'user-declared' annotation in its evidence"))
                prev_stage_idx = idx if idx is not None else prev_stage_idx


def check_counters(passport: Optional[dict], artifacts: List[Artifact], findings: List[Finding]) -> None:
    if not isinstance(passport, dict) or not isinstance(passport.get("counters"), dict):
        return
    counters = passport["counters"]
    rel = "docs/product/passport.json"
    kind_of_dir = {v: k for k, v in TYPE_DIRS.items()}
    max_seen: Dict[str, int] = {}
    for art in artifacts:
        kind = kind_of_dir[art.kind_dir]
        max_seen[kind] = max(max_seen.get(kind, 0), int(art.id[2:]))
    for kind, seen in sorted(max_seen.items()):
        have = counters.get(kind)
        if not isinstance(have, int) or have < seen:
            findings.append(Finding(
                rel, "COUNTER",
                f"counters.{kind}={have!r} but max existing {kind} ID is {seen} "
                f"(counter must be >= max)"))


def check_crosslinks(index: Dict[str, Artifact], artifacts: List[Artifact], findings: List[Finding]) -> None:
    for art in artifacts:
        if art.kind_dir == "stories":
            parent = art.fm.get("parent")
            target = index.get(parent) if isinstance(parent, str) else None
            if target is None or target.kind_dir not in ("epics", "features"):
                findings.append(Finding(
                    art.rel, "XLINK", f"parent '{parent}' resolves to no epic/feature file"))
            elif target.fm.get("status") == "dropped":
                findings.append(Finding(
                    art.rel, "XLINK", f"parent '{parent}' is dropped"))
            persona = art.fm.get("persona")
            ptarget = index.get(persona) if isinstance(persona, str) else None
            if ptarget is None or ptarget.kind_dir != "personas":
                findings.append(Finding(
                    art.rel, "XLINK", f"persona '{persona}' resolves to no persona file"))
            blocked_by = art.fm.get("blocked_by")
            if isinstance(blocked_by, list):
                for ref in blocked_by:
                    if not isinstance(ref, str) or ref not in index:
                        findings.append(Finding(
                            art.rel, "XLINK", f"blocked_by '{ref}' resolves to no artifact"))
        elif art.kind_dir == "features":
            epic = art.fm.get("epic")
            target = index.get(epic) if isinstance(epic, str) else None
            if target is None or target.kind_dir != "epics":
                findings.append(Finding(
                    art.rel, "XLINK", f"epic '{epic}' resolves to no epic file"))
            elif target.fm.get("status") == "dropped":
                findings.append(Finding(art.rel, "XLINK", f"epic '{epic}' is dropped"))


def check_enums(artifacts: List[Artifact], findings: List[Finding]) -> None:
    for art in artifacts:
        status = art.fm.get("status")
        allowed = STATUS_ENUM[art.kind_dir]
        if status not in allowed:
            findings.append(Finding(
                art.rel, "ENUM", f"status '{status}' not in {sorted(allowed)}"))
        wsjf = art.fm.get("wsjf")
        if isinstance(wsjf, dict):
            for field, value in sorted(wsjf.items()):
                if value is not None and value not in WSJF_ALLOWED:
                    findings.append(Finding(
                        art.rel, "ENUM",
                        f"wsjf.{field}={value!r} not in {sorted(WSJF_ALLOWED)}"))
        if art.kind_dir == "stories":
            priority = art.fm.get("priority")
            if priority is not None and isinstance(wsjf, dict) and all(
                isinstance(wsjf.get(f), int) and wsjf.get(f) in WSJF_ALLOWED
                for f in STORY_WSJF_FIELDS
            ):
                expected = round(
                    (wsjf["business_value"] + wsjf["time_criticality"] + wsjf["risk_reduction"])
                    / wsjf["job_size"],
                    2,
                )
                if not isinstance(priority, (int, float)) or float(priority) != expected:
                    findings.append(Finding(
                        art.rel, "ENUM",
                        f"priority cache {priority!r} != round((bv+tc+rr)/job_size, 2) = {expected}"))


def check_dor(story: Artifact, index: Dict[str, Artifact], findings: List[Finding]) -> None:
    """DOR-1..7 — mirrors backlog-schema.md's DoR table exactly."""
    fm, body = story.fm, story.body

    # DOR-1: persona resolves to an existing personas/P-\d{3}-*.md with status: active
    persona = fm.get("persona")
    ptarget = index.get(persona) if isinstance(persona, str) else None
    if ptarget is None or ptarget.kind_dir != "personas":
        findings.append(Finding(
            story.rel, "DOR-1", f"persona '{persona}' resolves to no persona file"))
    elif ptarget.fm.get("status") != "active":
        findings.append(Finding(
            story.rel, "DOR-1",
            f"persona '{persona}' has status '{ptarget.fm.get('status')}'; need active"))

    # DOR-2: >=2 lines matching `^- \[ \] AC-\d+:` each containing Given/when/then (ci)
    ac_lines = [ln for ln in body.splitlines() if AC_UNTICKED_RE.match(ln)]
    gwt = [
        ln for ln in ac_lines
        if all(word in ln.lower() for word in ("given", "when", "then"))
    ]
    if len(gwt) < 2:
        findings.append(Finding(
            story.rel, "DOR-2",
            f"only {len(gwt)} acceptance criteri{'on' if len(gwt) == 1 else 'a'} found; need >=2"))

    # DOR-3: wsjf block complete; all four fields in {1,2,3,5,8}
    wsjf = fm.get("wsjf")
    complete = isinstance(wsjf, dict) and all(
        wsjf.get(f) in WSJF_ALLOWED for f in STORY_WSJF_FIELDS
    )
    if not complete:
        findings.append(Finding(
            story.rel, "DOR-3",
            f"wsjf block incomplete or out of {sorted(WSJF_ALLOWED)}: {wsjf!r}"))

    # DOR-4: job_size <= 5
    job_size = wsjf.get("job_size") if isinstance(wsjf, dict) else None
    if isinstance(job_size, int) and job_size > 5:
        findings.append(Finding(
            story.rel, "DOR-4", f"job_size={job_size}; split required (must be <= 5)"))

    # DOR-5: parent resolves to an existing epic/feature whose status != dropped
    parent = fm.get("parent")
    target = index.get(parent) if isinstance(parent, str) else None
    if target is None or target.kind_dir not in ("epics", "features"):
        findings.append(Finding(
            story.rel, "DOR-5", f"parent '{parent}' resolves to no epic/feature file"))
    elif target.fm.get("status") == "dropped":
        findings.append(Finding(story.rel, "DOR-5", f"parent '{parent}' is dropped"))

    # DOR-6: blocked_by empty OR every reference resolves to a STORY with status done;
    # own status != blocked
    blocked_by = fm.get("blocked_by")
    if isinstance(blocked_by, list):
        for ref in blocked_by:
            dep = index.get(ref) if isinstance(ref, str) else None
            if dep is None or dep.kind_dir != "stories":
                findings.append(Finding(
                    story.rel, "DOR-6",
                    f"blocked_by '{ref}' does not resolve to a story"
                    f" ({'a ' + dep.kind_dir[:-1] if dep else 'missing'})"))
            elif dep.fm.get("status") != "done":
                findings.append(Finding(
                    story.rel, "DOR-6",
                    f"blocked_by '{ref}' is not done (status: {dep.fm.get('status')})"))
    if fm.get("status") == "blocked":
        findings.append(Finding(story.rel, "DOR-6", "own status is 'blocked'"))

    # DOR-7: ## Story section contains "As ", "I want", "so that" and the persona's ID
    story_section = section(body, "Story")
    if story_section is None:
        findings.append(Finding(story.rel, "DOR-7", "no '## Story' section"))
    else:
        missing = [
            token for token in ("As ", "I want", "so that", str(persona))
            if token not in story_section
        ]
        if missing:
            findings.append(Finding(
                story.rel, "DOR-7", f"'## Story' section missing: {missing}"))


def check_dod(story: Artifact, root: Path, findings: List[Finding]) -> None:
    """DOD-1..3 — mirrors backlog-schema.md's DoD table exactly (DOD-4 is advisory)."""
    fm, body = story.fm, story.body

    # DOD-1: spec points to an existing docs/specs/*.md file
    spec = fm.get("spec")
    if (
        not isinstance(spec, str)
        or not re.match(r"^docs/specs/[^/]+\.md$", spec)
        or not (root / spec).is_file()
    ):
        findings.append(Finding(
            story.rel, "DOD-1", f"spec '{spec}' is not an existing docs/specs/*.md file"))

    # DOD-2: every AC line is `- [x]` AND carries the ` — evidence: ` suffix
    for ln in body.splitlines():
        if not AC_ANY_RE.match(ln):
            continue
        if not AC_TICKED_RE.match(ln):
            findings.append(Finding(
                story.rel, "DOD-2", f"unticked acceptance criterion: '{ln[:60]}...'"))
        elif EVIDENCE_SUFFIX not in ln:
            findings.append(Finding(
                story.rel, "DOD-2",
                f"ticked criterion lacks '{EVIDENCE_SUFFIX.strip()}' suffix: '{ln[:60]}...'"))

    # DOD-3: ## Build record has a review verdict line and a commit range
    build_record = section(body, "Build record") or ""
    if not REVIEW_VERDICT_RE.search(build_record):
        findings.append(Finding(
            story.rel, "DOD-3", "'## Build record' has no 'review: <tier> — <verdict>' line"))
    if not COMMIT_RANGE_RE.search(build_record):
        findings.append(Finding(
            story.rel, "DOD-3", "'## Build record' has no commit range"))


def check_ready_count(passport: Optional[dict], artifacts: List[Artifact], findings: List[Finding]) -> None:
    if not isinstance(passport, dict) or "ready_count" not in passport:
        return
    actual = sum(
        1 for a in artifacts if a.kind_dir == "stories" and a.fm.get("status") == "ready"
    )
    declared = passport.get("ready_count")
    if declared != actual:
        findings.append(Finding(
            "docs/product/passport.json", "READY-COUNT",
            f"ready_count={declared!r} but {actual} story(ies) have status: ready"))


PERSONA_BULLET_SECTIONS = ("Goals", "Pains")          # require >=2 bullets each
PERSONA_TEXT_SECTIONS = ("Context", "Success looks like")  # require non-empty


def check_persona_body(persona: Artifact, findings: List[Finding]) -> None:
    """[PERSONA] — the four required body sections of the persona schema."""
    for header in PERSONA_BULLET_SECTIONS:
        text = section(persona.body, header)
        if text is None:
            findings.append(Finding(
                persona.rel, "PERSONA", f"required section '## {header}' missing"))
            continue
        bullets = [ln for ln in text.splitlines() if ln.startswith("- ")]
        if len(bullets) < 2:
            findings.append(Finding(
                persona.rel, "PERSONA",
                f"'## {header}' has {len(bullets)} bullet(s); need >=2"))
    for header in PERSONA_TEXT_SECTIONS:
        text = section(persona.body, header)
        if text is None:
            findings.append(Finding(
                persona.rel, "PERSONA", f"required section '## {header}' missing"))
        elif not text.strip():
            findings.append(Finding(
                persona.rel, "PERSONA", f"'## {header}' is empty"))


def check_dup_ids(artifacts: List[Artifact], findings: List[Finding]) -> None:
    seen: Dict[str, str] = {}
    for art in artifacts:
        if art.id in seen:
            findings.append(Finding(
                art.rel, "DUP-ID", f"ID '{art.id}' already used by {seen[art.id]}"))
        else:
            seen[art.id] = art.rel


# ---------------------------------------------------------------- tree runner

def check_tree(root: Path) -> List[Finding]:
    """Run every check against `root`. Returns all findings (empty = clean)."""
    if not (root / "docs" / "product").is_dir():
        return []
    passport, artifacts, findings = load_tree(root)
    check_passport_doc(passport, findings)
    check_dup_ids(artifacts, findings)
    index = {a.id: a for a in artifacts}
    check_counters(passport, artifacts, findings)
    check_crosslinks(index, artifacts, findings)
    check_enums(artifacts, findings)
    for art in artifacts:
        if art.kind_dir == "personas":
            check_persona_body(art, findings)
            continue
        if art.kind_dir != "stories":
            continue
        status = art.fm.get("status")
        if status == "ready":
            check_dor(art, index, findings)
        elif status == "done":
            check_dod(art, root, findings)
    check_ready_count(passport, artifacts, findings)
    return findings


# ---------------------------------------------------------------- selftest (fixtures)

EXPECTED_VIOLATIONS = {
    "bad-id-grammar": "ID-GRAMMAR",
    "broken-crosslink": "XLINK",
    "counter-below-max": "COUNTER",
    "ready-fails-dor": "DOR-2",
    "done-missing-evidence": "DOD-2",
    "ready-count-mismatch": "READY-COUNT",
    "history-nonmonotonic": "HISTORY",
    "persona-missing-section": "PERSONA",
}


def selftest() -> int:
    failures: List[str] = []

    valid = FIXTURES / "valid"
    if not valid.is_dir():
        print(f"check-passport selftest: FAIL — fixtures missing at {FIXTURES}")
        return 1
    findings = check_tree(valid)
    if findings:
        failures.append(f"valid/ should pass but produced {len(findings)} finding(s):")
        failures.extend(f"    {f}" for f in findings)
    else:
        print("OK valid/ (0 findings)")

    for dirname, tag in sorted(EXPECTED_VIOLATIONS.items()):
        fixture = FIXTURES / dirname
        if not fixture.is_dir():
            failures.append(f"{dirname}/: fixture dir missing")
            continue
        findings = check_tree(fixture)
        if not findings:
            failures.append(f"{dirname}/: expected a [{tag}] violation, got none")
        elif not any(f.rule == tag for f in findings):
            got = sorted({f.rule for f in findings})
            failures.append(f"{dirname}/: expected [{tag}], got {got}")
        else:
            print(f"OK {dirname}/ (caught [{tag}])")

    if failures:
        for line in failures:
            print(f"  FAIL: {line}")
        print(f"\ncheck-passport selftest: FAIL ({len(failures)} failure(s))")
        return 1
    print(f"\ncheck-passport selftest: PASS (valid + {len(EXPECTED_VIOLATIONS)} violation fixtures)")
    return 0


# ---------------------------------------------------------------- entry point

def main(argv: List[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    root = REPO_ROOT
    if "--root" in argv:
        idx = argv.index("--root")
        if idx + 1 >= len(argv):
            print(__doc__)
            return 2
        root = Path(argv[idx + 1]).resolve()

    if not (root / "docs" / "product").is_dir():
        print(f"check-passport: no docs/product/ under {root} — nothing to validate; PASS")
        return 0

    findings = check_tree(root)
    if findings:
        for f in findings:
            print(str(f))
        print(f"\ncheck-passport: FAIL ({len(findings)} violation(s))")
        return 1
    print("check-passport: PASS (backlog tree conforms to backlog-schema)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
