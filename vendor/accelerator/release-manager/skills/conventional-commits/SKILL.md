---
name: conventional-commits
description: |
  Use when classifying commits from a git range or mapping them to changelog sections. Detects commit style (Conventional Commits or freeform) from the first 20 commits, maps types to Keep-a-Changelog sections, and applies heuristic matching for freeform commits.
---

# Conventional Commits Skill

## Detection

Examine the first 20 commits in the range (or all commits if fewer than 20).

**Conventional Commits pattern:** `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?(!)?:\s.+`

**Threshold:** If ≥70% of commits match the pattern, classify the range as **Conventional Commits**. Otherwise classify as **Freeform**.

Record the detected style in the commit report output: `"commit_style": "conventional"` or `"commit_style": "freeform"`.

---

## Conventional Commits Type Mapping

| Commit type | Keep-a-Changelog section | Bump contribution |
|---|---|---|
| `feat` | `### Added` | minor (or major if breaking) |
| `fix` | `### Fixed` | patch (or major if breaking) |
| `docs` | _(omit from changelog unless scope is user-facing)_ | patch |
| `style` | _(omit)_ | patch |
| `refactor` | `### Changed` | patch |
| `perf` | `### Changed` | patch |
| `test` | _(omit)_ | patch |
| `build` | _(omit)_ | patch |
| `ci` | _(omit)_ | patch |
| `chore` | _(omit from changelog)_ | patch |
| `revert` | `### Changed` (note the revert) | patch |
| any type with `!` or `BREAKING CHANGE` footer | `### Breaking Changes` (custom section) | **major** |

**Breaking change detection (Conventional Commits):**
- `!` appended to type before colon: `feat!: drop support for Node 14`
- Footer line: `BREAKING CHANGE: <description>`

Both forms are definitive — no user confirmation required.

---

## Freeform Heuristics

When commit style is **freeform**, apply these heuristic rules to each commit subject line. Case-insensitive matching.

| Pattern | Inferred type | Keep-a-Changelog section |
|---|---|---|
| Subject starts with: `Add`, `Implement`, `New`, `Support`, `Introduce`, `Create`, `Enable` | `feat` (inferred) | `### Added` |
| Subject starts with: `Fix`, `Resolve`, `Correct`, `Patch`, `Bug`, `Handle`, `Repair` | `fix` (inferred) | `### Fixed` |
| Subject starts with: `Refactor`, `Rename`, `Move`, `Clean`, `Remove`, `Delete`, `Extract`, `Simplify` | `chore` (inferred) | `### Changed` |
| Subject starts with: `Update`, `Upgrade`, `Bump`, `Change`, `Improve`, `Tweak` | `chore` (inferred) | `### Changed` |
| Subject contains `BREAKING` (case-insensitive) | breaking change candidate | requires user confirmation |
| None of the above match | `uncategorized` | listed explicitly under `### Uncategorized` |

**Mandatory confirmation step for freeform:** After applying heuristics, present the full inferred categorization to the user:

```
I've inferred the following categories for your commits. Please review and correct any misclassifications:

### Added (inferred feat)
- Add OAuth 2.0 login support (a3f9b1c) — Example Author
- Implement bulk CSV export (d12cc84) — Example Author

### Fixed (inferred fix)
- Fix session timeout on idle connections (e890ab2) — Example Author

### Changed (inferred chore)
- Refactor database connection pool (b55de21) — Example Author

### Uncategorized (no pattern matched)
- prepare for release (7f3c44a) — Example Author

Are there any commits I've misclassified? If so, tell me which SHA(s) and the correct category. Type 'confirmed' when the categories are correct.
```

**Do NOT proceed to changelog generation or version recommendation before the user types `confirmed`.**

---

## Breaking Change Candidates in Freeform

Commits containing "BREAKING" in freeform mode are **candidates only**, not confirmed breaking changes.

Handling:
1. List them separately with their full subject and SHA
2. Ask: "The following commit(s) appear to mention BREAKING changes. Are any of them actual breaking changes requiring a MAJOR version bump? (yes / no for each)"
3. Only mark as breaking if the user confirms
4. If confirmed breaking: add to `### Breaking Changes` section and set bump contribution to major

---

## Changelog Section Order

When producing a CHANGELOG.md entry, always use this section order (omit empty sections):

1. `### Added`
2. `### Changed`
3. `### Deprecated`
4. `### Removed`
5. `### Fixed`
6. `### Security`
7. `### Breaking Changes` (only if breaking changes exist)
8. `### Uncategorized` (only if freeform uncategorized commits exist)

---

## Entry Format

```markdown
## [X.Y.Z] — YYYY-MM-DD

### Added
- [feat] Description of new capability (shortSHA)
- [feat] Another new capability (shortSHA)

### Fixed
- [fix] Description of bug fix (shortSHA)

### Changed
- [refactor] Description of internal change (shortSHA)
```

Short SHA = first 7 characters of the full commit SHA.
