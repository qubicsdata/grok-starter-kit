---
name: release-readiness
description: |
  Apply before producing tag guidance. Defines the 6-item release readiness gate with verification method and owning agent per item. Used by readiness-checker. Each item is PASS or FAIL with reason and remediation.
---

# Release Readiness Gate

## Purpose

The release readiness gate ensures a project is in a deployable state before tag commands are produced. Every item must PASS before `tag-advisor` is invoked in a full `/release` session.

In standalone `/release-tag` mode, a FAIL on any item surfaces as a warning and requires explicit user acknowledgement before proceeding.

---

## 6-Item Gate

Evaluate every item. Report PASS or FAIL. Never skip an item.

---

### Item 1 — No uncommitted changes

**Verification:** Run `git status --porcelain`

**PASS condition:** Command returns empty (no output).

**FAIL condition:** Any output is present (staged, unstaged, or untracked files exist).

**FAIL message format:**
```
FAIL — Item 1: Uncommitted changes detected.
Files: <list output of git status --porcelain>
Remediation: Commit or stash all changes before tagging. Run: git status
Owning party: User
```

---

### Item 2 — CI is passing on the current HEAD

**Verification:** Check for CI configuration files:
1. Look for `.github/workflows/*.yml` or `.github/workflows/*.yaml`
2. Look for `.circleci/config.yml`, `Jenkinsfile`, `.travis.yml`, `.gitlab-ci.yml`
3. If CI config found: display the CI provider name and ask the user to confirm CI is passing on the current HEAD SHA (run `git rev-parse HEAD` and show the SHA)
4. If no CI config found: report as INFO — "No CI configuration detected. Skipping automated CI check."

**PASS condition:** User explicitly confirms CI is passing. Or no CI config is present (report INFO, not FAIL).

**FAIL condition:** User reports CI is failing or has not run.

**FAIL message format:**
```
FAIL — Item 2: CI is not passing on HEAD <SHA>.
CI provider: <provider>
Remediation: Fix the failing CI checks before tagging.
Owning party: User
```

---

### Item 3 — All tests pass locally

**Verification:** Detect the test command:
1. Check `package.json` for `scripts.test`
2. Check `Makefile` for a `test` target (`grep -n "^test:" Makefile`)
3. Check for `pytest.ini`, `setup.cfg [tool:pytest]`, or `pyproject.toml [tool.pytest]`
4. Check for `go.mod` (use `go test ./...`)
5. If test command found: run it and capture exit code
6. If no test command found: report as INFO — "No test command detected. Skipping automated test check."

**PASS condition:** Test command exits 0. Or no test command detected (INFO).

**FAIL condition:** Test command exits non-zero.

**FAIL message format:**
```
FAIL — Item 3: Tests failed locally.
Command run: <command>
Exit code: <code>
Remediation: Fix failing tests before tagging.
Owning party: User
```

---

### Item 4 — Target version does not already exist as a tag

**Verification:** Run `git tag --list <version>` where `<version>` is the confirmed version string (with or without `v` prefix, check both).

**PASS condition:** Both `git tag --list <version>` and `git tag --list v<version>` return empty.

**FAIL condition:** Either command returns a match.

**FAIL message format:**
```
FAIL — Item 4: Tag <version> already exists in this repository.
Remediation: Choose a different version. Re-run version-advisor to get a new recommendation.
Owning party: version-advisor
```

---

### Item 5 — CHANGELOG.md contains an entry for this version

**Verification:**
- In single-package mode: `grep -n "\[<version>\]" CHANGELOG.md`
- In monorepo mode: `grep -n "\[<version>\]" <scope-path>/CHANGELOG.md`

**PASS condition:** At least one matching line is found.

**FAIL condition:** No match found, or CHANGELOG.md does not exist.

**FAIL message format:**
```
FAIL — Item 5: No CHANGELOG.md entry found for version <version>.
Remediation: Run /changelog to generate the entry.
Owning agent: changelog-writer
```

---

### Item 6 — Release notes document exists and is non-empty

**Verification:**
- In single-package mode: check `docs/releases/v<version>.md` exists and `wc -c` > 0
- In monorepo mode: check `<scope-path>/docs/releases/v<version>.md`
- Also try the version without `v` prefix: `docs/releases/<version>.md`

**PASS condition:** File exists and contains at least 1 byte.

**FAIL condition:** File does not exist, or is empty.

**FAIL message format:**
```
FAIL — Item 6: Release notes not found at docs/releases/v<version>.md.
Remediation: Run /release-notes to generate the document.
Owning agent: release-notes-writer
```

---

## Gate Result Format

After evaluating all 6 items, produce the gate result:

**If all 6 PASS:**
```
CLEARED — tag guidance may proceed.

Gate result:
✓ Item 1: No uncommitted changes
✓ Item 2: CI passing (confirmed by user)
✓ Item 3: Tests passing
✓ Item 4: Version X.Y.Z is unique
✓ Item 5: CHANGELOG.md entry present
✓ Item 6: Release notes present at docs/releases/vX.Y.Z.md
```

**If any FAIL:**
```
BLOCKED — N item(s) failed. Resolve before tagging.

Gate result:
✓ Item 1: No uncommitted changes
✗ Item 2: CI not confirmed passing
✓ Item 3: Tests passing
✓ Item 4: Version unique
✗ Item 5: No CHANGELOG.md entry for X.Y.Z
✓ Item 6: Release notes present

Failed items and remediation:
[List each FAIL item with its full FAIL message]
```

---

## Standalone Mode Warning

When readiness-checker is invoked via `/release-tag` (not a full `/release` session), gate failures are reported as warnings. The tag-advisor will still produce commands, but the user must type `acknowledge` before tag commands are shown.

Warning format:
```
WARNING — Readiness gate has N failure(s). Proceeding to tag guidance in standalone mode.
Type 'acknowledge' to see tag commands despite these failures, or resolve the issues first.
```
