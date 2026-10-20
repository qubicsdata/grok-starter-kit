# release-manager

A Claude Code plugin that bridges "code is merged" and "release is shipped." Automates the six steps of release preparation: commit analysis, semantic version recommendation, changelog generation, human-readable release notes drafting, release readiness gate checking, and tag/branch guidance.

Works with any project that has a git history. No specific commit message convention required — Conventional Commits unlock richer automation, but freeform projects are fully supported.

---

## Installation

```bash
# From your project root, install the plugin:
claude plugin install release-manager

# Or reference locally during development:
claude plugin install /path/to/release-manager
```

---

## Commands

| Command | Description | Example |
|---|---|---|
| `/release [git-range]` | Start or resume a full release preparation session. Runs all six phases in order with confirmation gates. | `/release` |
| `/release-analyze [git-range]` | Standalone commit analysis only. Produces the structured commit report. | `/release-analyze v2.0.0..HEAD` |
| `/release-version [version]` | Standalone version recommendation. Reads session state if present; otherwise runs commit analysis first. | `/release-version 0.9.0` |
| `/changelog [git-range]` | Standalone changelog entry generation. Asks for version if not in session state. | `/changelog v1.0.0..HEAD` |
| `/release-notes [git-range]` | Standalone release notes drafting in plain prose for users. Asks for version if not in session state. | `/release-notes` |
| `/release-ready [version]` | Standalone readiness gate check (6 items). Reads session state if present. | `/release-ready 3.0.0` |
| `/release-tag [version]` | Standalone tag command generation. Prints copy-paste shell commands. Never runs git commands. | `/release-tag 1.5.0` |

---

## Agents

### release-orchestrator

Routes across all six release phases and maintains session state in `.release-session.json`. Reads the session file at start and offers resume or restart. Enforces phase order. Never generates content — only orchestrates and gates. Writes `.release-session.json` only.

Use when: running a full end-to-end release preparation session via `/release`.

### commit-analyzer

Reads the git log for a given range, detects commit style (Conventional Commits or freeform), categorises every commit, and produces a structured commit report. Flags breaking changes. Never writes files.

Use when: you need a structured breakdown of what changed since the last tag.

### version-advisor

Receives the commit report and the current version, applies the semver-rules skill, and produces a recommended version bump with explicit reasoning plus an alternative. Never decides unilaterally — user must confirm.

Use when: you need a defensible, reasoned semver recommendation.

### changelog-writer

Produces a CHANGELOG.md entry in Keep a Changelog 1.1.0 format. Reads the existing file before writing. Prepends only — never modifies history below the new entry. Presents the full proposed entry before writing.

Use when: generating the developer-facing changelog for a release.

### release-notes-writer

Produces a human-readable release notes document in plain prose. Translates technical commit subjects into language suitable for end users and product stakeholders. Separate from the changelog — no commit SHAs, no author names. Writes `docs/releases/vX.Y.Z.md`.

Use when: drafting user-facing release notes.

### readiness-checker

Evaluates the 6-item release readiness gate: uncommitted changes, CI passing, tests passing, version uniqueness, CHANGELOG entry, and release notes present. Reports PASS/FAIL per item with remediation. Never writes files.

Use when: verifying a project is ready to tag.

### tag-advisor

Produces annotated git tag creation, push, and optional release branch commands formatted for copy-paste. Infers whether the project uses a `v` prefix from existing tags. Never runs any git command itself.

Use when: generating the exact shell commands to create and push the release tag.

---

## Session State

Session state is stored in `.release-session.json` in the project root. It is safe to add to `.gitignore`. The file tracks which phases have completed and what artifacts have been written.

**Schema:**
```json
{
  "version": "2.4.0",
  "base_ref": "v2.3.1",
  "head_ref": "HEAD",
  "commit_report_available": true,
  "phases_complete": ["commit-analyze", "version-advise"],
  "changelog_written": false,
  "release_notes_written": false,
  "readiness_passed": false,
  "tag_commands_shown": false,
  "open_items": []
}
```

Phase identifiers: `commit-analyze`, `version-advise`, `changelog-write`, `release-notes-write`, `readiness-check`, `tag-advise`.

---

## Artifacts Produced

| Artifact | Agent | Location | Notes |
|---|---|---|---|
| `CHANGELOG.md` | `changelog-writer` | Project root (or `<scope>/CHANGELOG.md` in monorepo mode) | Prepended entry in Keep a Changelog 1.1.0 format |
| `docs/releases/vX.Y.Z.md` | `release-notes-writer` | `docs/releases/` (or `<scope>/docs/releases/`) | Human-readable prose, no commit SHAs |
| `.release-session.json` | `release-orchestrator` | Project root | Orchestration state; gitignore-able |
| Tag commands | `tag-advisor` | Terminal only | Copy-paste shell commands, never auto-executed |

---

## Monorepo Support

Pass a package scope path to restrict analysis to one package. In monorepo mode, `commit-analyzer` filters commits by changed paths under the scope, and artifacts are written under `<scope>/`.

```
/release packages/api
/release-analyze packages/web v2.0.0..HEAD
```

---

## Anti-Patterns This Plugin Prevents

1. **Auto-running git commands:** `tag-advisor` prints commands for the user to run. It never calls `git tag`, `git push`, or any destructive git operation.
2. **Silent version decisions:** `version-advisor` recommends with explicit reasoning. User must confirm or override before any downstream agent receives the version string.
3. **Changelog history overwritten:** `changelog-writer` prepends only. It reads the existing file before writing and never modifies any entry below the new one.
4. **Developer changelog confused with user release notes:** These are always separate artifacts. The changelog contains commit SHAs for developers; release notes contain plain prose for stakeholders.
5. **Tag before readiness:** In a full `/release` session, the 6-item gate must PASS before `tag-advisor` is invoked. In standalone `/release-tag` mode, the gate is surfaced as a warning — user must explicitly acknowledge before proceeding.
6. **Silent freeform misclassification:** When commit style is freeform, every inferred category is presented to the user for correction before changelog or release notes are generated.
7. **Hardcoded version prefix assumption:** The plugin infers the `v` prefix convention from existing tags. If no prior tags exist, it asks the user.
8. **Monorepo version bleed:** In monorepo mode, commits and artifacts are always scoped to the specified package path.
9. **Ambiguous breaking change detection:** Commits containing "BREAKING" in freeform mode are flagged as breaking change candidates and require explicit user confirmation before a major bump is recommended.

---

## Author

<your-name> — you@example.com

## Dependencies

- requires: ai-baseline
