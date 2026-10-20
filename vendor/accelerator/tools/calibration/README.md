# Reviewer Calibration Set

This directory contains two minimal plugin fixtures for calibrating the static checker (`check-calibration.py`) and reviewer judgment.

## Fixtures

### `clean-plugin/`
A minimal **conformant** plugin. Expected verdict: **0 findings**.

Files:
- `.claude-plugin/plugin.json` — canonical fields only (name, version, description, category, author, keywords, requires)
- `agents/primary-agent.md` — imports baseline-enforcer, uses `$ARGUMENTS` (no brackets), has `## Tools` section and hard gates
- `agents/spec-enricher.md` — conformant spec-enricher with concrete triggers and MUST/SHALL/NEVER language

### `buggy-plugin/`
The same structure but with **two seeded defects**. Expected verdict: **≥2 findings**.

Defects:
1. **PIT-2** (`[$ARGUMENTS]` brackets): `agents/primary-agent.md` uses `[$ARGUMENTS]` instead of `$ARGUMENTS` in three places.
2. **PIT-6** (phantom plugin.json field): `.claude-plugin/plugin.json` contains a `"tags"` field that is not in the canonical field set.
3. **PIT-1** (missing baseline import): `agents/primary-agent.md` does NOT import `baseline-enforcer`.

## Expected results

```
clean-plugin  → PASS  (0 findings)
buggy-plugin  → FAIL  (≥2 findings: PIT-2 bracket defect + PIT-6 phantom field [+ PIT-1 missing import])
```

Run with:
```
python3 tools/check-calibration.py
```

---

## Output-hygiene fixtures (`check-output-hygiene.py`)

A separate fixture pair calibrates the static **pre-review gate** that scans
generated *project* code (not plugin markdown) for the mechanical defect class —
so the LLM reviewer never spends tokens on it. See
`ai-baseline/skills/risk-tier-spec.md`: this gate runs at **every** tier and is
what makes cutting review depth safe.

### `hygiene-clean/`
A minimal hygienic project. Expected verdict: **0 findings**.
- `config.py` — config from `os.environ`, no hardcoded values
- `app.py` — HTTP handler with a single shared error builder (`_send_error`)
- `dashboard.js` — every `innerHTML` interpolation wrapped in `escHtml()`
- `test_app.py` — a test exists (not flagged for zero tests)

### `hygiene-buggy/`
Same shape with **five seeded defects**. Expected verdict: **≥4 findings**.
1. **H1 (xss)** — `dashboard.js` writes `innerHTML` from unescaped data interpolation
2. **H3 (secret)** — `server.py` hardcodes an `API_KEY` literal
3. **H4 (hostport)** — `server.py` hardcodes `http://localhost:8000`
4. **H5 (errschema)** — `server.py` HTTP handlers emit ad-hoc 4xx with no shared error builder
5. **H6 (notests)** — the project ships zero test files

```
hygiene-clean  → 0 findings
hygiene-buggy  → ≥4 findings
```

Run the self-test (also wired into `tools/validate.sh`):
```
python3 tools/check-output-hygiene.py --calibrate
```
Scan real generated code:
```
python3 tools/check-output-hygiene.py <target-dir>
```
