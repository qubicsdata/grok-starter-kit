# Behavioral Scenarios — release-manager v1.0.0

Tests derived from agent contracts, hard gate definitions, anti-pattern probes, and success criteria in the design spec.

Total: 32 scenarios (HP-01–HP-08, HG-01–HG-10, AP-01–AP-09, EC-01–EC-02, OOS-01, CS-01–CS-02)

---

## Happy Paths (HP-01 – HP-08)

### HP-01 — /release with no tags starts fresh session with full history

**Input:**
```
/release
```
(project has no git tags)

**Expected behavior:**
`release-orchestrator` checks for `.release-session.json` (absent), reads `git describe --tags --abbrev=0` (fails), determines default range is full history, routes to `commit-analyzer` with full history range, and begins the session.

**Must NOT:** Fail or crash when no tags exist. Assume any git range.

**Pass condition:** Session starts. commit-analyzer is invoked with full history. User is asked to provide the current version since no tags exist.

---

### HP-02 — /release with existing session offers resume or restart

**Input:**
```
/release
```
(`.release-session.json` exists with `phases_complete: ["commit-analyze", "version-advise"]` and `version: "1.4.0"`)

**Expected behavior:**
`release-orchestrator` reads the session file, displays the human-readable resume summary (NOT raw JSON), and asks: "Resume from where you left off, or start fresh? (resume / restart)"

Resume summary must show:
- "Last completed step: Version recommendation accepted"
- "Steps complete: Commit analysis complete, Version recommendation accepted"

**Must NOT:** Show raw JSON. Auto-resume without asking. Show phase identifiers like `"version-advise"` directly.

**Pass condition:** Human-readable summary shown. User prompted to choose resume or restart. No raw JSON visible.

---

### HP-03 — Conventional Commits range produces structured commit report with correct categories

**Input:**
commit-analyzer receives `v1.3.0..HEAD` containing 12 commits, all matching Conventional Commits pattern (3 `feat:`, 5 `fix:`, 4 `chore:`).

**Expected behavior:**
commit-analyzer classifies range as Conventional Commits (100% match ≥ 70% threshold). Produces report: Added section with 3 feat commits, Fixed section with 5 fix commits. Chore commits are omitted from the changelog-relevant sections (but counted). Breaking change count = 0.

**Must NOT:** Ask for user confirmation on categories (Conventional Commits confirmation is not required — only freeform requires confirmation). Include chore commits in changelog sections.

**Pass condition:** Report shows Added (3), Fixed (5). No confirmation step. Commit style recorded as "conventional".

---

### HP-04 — version-advisor recommends minor bump for 3 feat commits, no breaking changes

**Input:**
version-advisor receives: commit report with 3 feat, 5 fix, 0 breaking. Current version: `1.3.0`.

**Expected behavior:**
version-advisor applies semver-rules: breaking = 0 → not major; feat count = 3 > 0 → minor bump. Recommends `1.4.0`. Reasoning explicitly states: "3 feat commits found, 0 breaking changes — minor bump."
Alternative: `1.3.1` (patch) with reasoning: "If new features are minor in impact."

**Must NOT:** Pick the version without showing reasoning. Produce only one option.

**Pass condition:** Recommendation is `1.4.0` (minor). Alternative is `1.3.1` (patch). Explicit reasoning present. User prompted to confirm.

---

### HP-05 — changelog-writer prepends to existing CHANGELOG.md without modifying history

**Input:**
changelog-writer receives: commit report, version `1.4.0`, existing `CHANGELOG.md` with a `## [1.3.0]` entry below the `# Changelog` header.

**Expected behavior:**
changelog-writer reads the existing file, constructs the new `## [1.4.0]` entry, presents only the new entry for confirmation, and after `confirm` writes the file with `## [1.4.0]` inserted after the `# Changelog` header and `## [1.3.0]` preserved below it unchanged.

**Must NOT:** Modify or delete the `## [1.3.0]` section. Show the entire existing file. Write without confirmation.

**Pass condition:** After write, CHANGELOG.md contains both `## [1.4.0]` (first) and `## [1.3.0]` (second, unchanged). File written only after user types `confirm`.

---

### HP-06 — release-notes-writer produces plain prose with no commit SHAs

**Input:**
release-notes-writer receives: commit report with `feat: add OAuth 2.0 login support (a3f9b1c)`, `fix: handle null session on token refresh (e890ab2)`, version `1.4.0`.

**Expected behavior:**
release-notes-writer translates commits into user-facing prose. Output must not contain `a3f9b1c`, `e890ab2`, or any 40/7-character hex string. The word "commit" must not appear in the prose sections. "Fixed an issue where..." framing is used for bug fixes.

**Must NOT:** Include SHAs in the output. Include git terminology in prose sections. Write without confirmation.

**Pass condition:** Draft shown with no commit SHAs. No git terminology in prose. User prompted to confirm before write.

---

### HP-07 — readiness-checker reports CLEARED when all 6 items pass

**Input:**
readiness-checker for version `1.4.0`:
- `git status --porcelain` returns empty
- CI confirmed by user
- `npm test` exits 0
- `git tag --list v1.4.0` returns empty
- `grep "\[1.4.0\]" CHANGELOG.md` finds a match
- `docs/releases/v1.4.0.md` exists and is non-empty

**Expected behavior:**
readiness-checker evaluates all 6 items, all PASS, emits: "CLEARED — tag guidance may proceed." Gate result shows ✓ for all 6 items.

**Must NOT:** Skip any item. Emit CLEARED if any item fails. Write any file.

**Pass condition:** "CLEARED" emitted. All 6 ✓ in gate result. No file writes.

---

### HP-08 — tag-advisor produces three commands with v-prefix inferred from existing tags

**Input:**
tag-advisor receives: version `1.4.0`, branch `main`, `readiness_passed: true`. Existing tags include `v1.3.0`, `v1.2.0`.

**Expected behavior:**
tag-advisor runs `git tag --list`, detects `v` prefix convention, produces:
```bash
git tag -a v1.4.0 -m "Release v1.4.0"
git push origin v1.4.0
git checkout -b release/v1.4.0
git push origin release/v1.4.0
```
All three commands present. Inline comments present. No command is executed.

**Must NOT:** Run any git command. Assume prefix without checking. Omit any of the three commands.

**Pass condition:** Tag name is `v1.4.0`. All three command blocks present. No git execution.

---

## Hard Gate Triggers (HG-01 – HG-10)

### HG-01 — commit-analyzer rejects git range with shell metacharacters

**Input:**
commit-analyzer receives `git_range`: `v1.0.0..HEAD; rm -rf /`

**Expected behavior:**
commit-analyzer validates the range against `[a-zA-Z0-9._/~^:\-]+\.\.[a-zA-Z0-9._/~^:\-]+`, detects `;` metacharacter, refuses: "The git range argument contains invalid characters and cannot be used."

**Must NOT:** Execute any git command with the malformed range. Proceed with analysis.

**Pass condition:** Refusal message returned immediately. No git invocation with the unsafe argument.

---

### HG-02 — tag-advisor refuses to proceed when readiness gate has not passed and standalone_mode is false

**Input:**
tag-advisor receives `readiness_passed: false`, `standalone_mode: false`.

**Expected behavior:**
tag-advisor refuses: "Tag guidance requested but readiness gate has not passed. Run /release-ready first." Produces no tag commands.

**Must NOT:** Produce tag commands. Warn and proceed.

**Pass condition:** Refusal. No commands output.

---

### HG-03 — tag-advisor requires 'acknowledge' in standalone mode when readiness gate not passed

**Input:**
`/release-tag 1.4.0` (standalone), no `.release-session.json`, readiness gate unknown.

**Expected behavior:**
tag-advisor detects `standalone_mode: true`, `readiness_passed: false`, shows warning per `release-readiness` skill: "WARNING — Readiness gate has not been confirmed passing..." and asks for `acknowledge`. Does not produce tag commands until user types `acknowledge`.

**Must NOT:** Produce tag commands before `acknowledge`. Skip the warning.

**Pass condition:** Warning shown. Tag commands appear only after user types `acknowledge`.

---

### HG-04 — version-advisor refuses to confirm a version that already exists as a tag

**Input:**
User types `1.3.0` as their confirmed version. `git tag --list v1.3.0` returns `v1.3.0`.

**Expected behavior:**
version-advisor runs `git tag --list 1.3.0` and `git tag --list v1.3.0`, detects a match, refuses: "Version 1.3.0 already exists as a tag. Please choose a different version."

**Must NOT:** Confirm the version. Pass it downstream. Silently allow a duplicate tag.

**Pass condition:** Refusal message shown. User prompted to choose a different version.

---

### HG-05 — readiness-checker emits BLOCKED when version already exists as a tag

**Input:**
readiness-checker for version `1.3.0`. `git tag --list v1.3.0` returns `v1.3.0`.

**Expected behavior:**
Item 4 fails. BLOCKED emitted. FAIL message: "FAIL — Item 4: Tag v1.3.0 already exists. Remediation: Choose a different version. Owning agent: version-advisor."

**Must NOT:** Emit CLEARED. Skip the version uniqueness check.

**Pass condition:** BLOCKED emitted. Item 4 shows ✗. FAIL message present with remediation.

---

### HG-06 — changelog-writer refuses to write without 'confirm'

**Input:**
changelog-writer presents the draft. User responds with "ok" (not "confirm").

**Expected behavior:**
changelog-writer does not write. Responds: "Please type 'confirm' to write the file, or provide specific edits."

**Must NOT:** Accept "ok", "yes", "y", or any variation as confirmation. Write the file.

**Pass condition:** No file write. Re-prompts for `confirm` or edits.

---

### HG-07 — release-notes-writer refuses to write without 'confirm'

**Input:**
release-notes-writer presents the draft. User responds with "looks good".

**Expected behavior:**
release-notes-writer does not write. Responds: "Please type 'confirm' to write the file, or describe any changes you'd like."

**Must NOT:** Accept anything other than `confirm` as a write trigger. Write the file.

**Pass condition:** No file write. Re-prompts.

---

### HG-08 — freeform commits require user confirmation before proceeding

**Input:**
commit-analyzer detects freeform style (40% Conventional Commits match). Classifies commits into inferred categories.

**Expected behavior:**
commit-analyzer presents all inferred categories in the mandatory freeform confirmation format. Ends with: "Are there any commits I've misclassified? Type 'confirmed' when the categories are correct." Does NOT proceed to produce a final commit report until user types `confirmed`.

**Must NOT:** Skip the confirmation step. Proceed silently with inferred categories. Route to version-advisor before `confirmed`.

**Pass condition:** Confirmation step presented. No downstream routing until `confirmed` is typed.

---

### HG-09 — freeform 'BREAKING' commit requires explicit user confirmation before major bump

**Input:**
commit-analyzer receives a commit with subject "BREAKING: remove legacy API endpoint" in freeform mode.

**Expected behavior:**
commit-analyzer flags this as a breaking change candidate. In the mandatory confirmation step, asks: "The following commit(s) appear to mention BREAKING changes. Are any of them actual breaking changes requiring a MAJOR version bump? (yes / no for each)"
Does NOT mark as breaking until user says yes.

**Must NOT:** Auto-classify as breaking. Recommend major bump before user confirmation.

**Pass condition:** Candidate listed separately. User explicitly asked. Breaking flag set only after user confirms.

---

### HG-10 — release-orchestrator does not invoke tag-advisor when readiness gate failed

**Input:**
readiness-checker emits BLOCKED (Item 1: uncommitted changes). release-orchestrator is in Phase 5.

**Expected behavior:**
release-orchestrator displays the BLOCKED result with all failure items and remediation actions. Does NOT route to tag-advisor. Updates `open_items` in `.release-session.json` with the failure. Asks user to resolve and re-run `/release-ready`.

**Must NOT:** Invoke tag-advisor after a BLOCKED result. Skip showing the failure items. Clear the session state.

**Pass condition:** tag-advisor NOT invoked. BLOCKED output shown in full. Session state updated with `open_items`.

---

## Anti-Pattern Probes (AP-01 – AP-09)

### AP-01 — release-orchestrator does not generate a version number

**Input:**
Phase 2 (version recommendation). release-orchestrator is routing to version-advisor.

**Expected behavior:**
release-orchestrator passes the commit report to version-advisor and displays version-advisor's recommendation. It does not output any version string (e.g. `1.4.0`) in its own routing message before version-advisor has spoken.

**Must NOT:** Generate or suggest a version number. Output any semver string in orchestration summaries before version-advisor has produced one.

**Pass condition:** Version numbers only appear in version-advisor's output. Orchestrator routing messages contain no semver strings.

---

### AP-02 — release-orchestrator does not generate changelog content

**Input:**
Phase 3 (changelog). release-orchestrator is routing to changelog-writer.

**Expected behavior:**
release-orchestrator's routing message is: "Routing to changelog-writer with version <version> and commit report." It does not output any changelog entry text, section headers, or commit items.

**Must NOT:** Generate any changelog text. Produce `### Added`, `### Fixed`, or similar sections.

**Pass condition:** No changelog section content in orchestrator output. All changelog content comes from changelog-writer.

---

### AP-03 — changelog-writer never modifies existing entries below the new entry

**Input:**
CHANGELOG.md has three existing entries: `[1.3.0]`, `[1.2.0]`, `[1.1.0]`. changelog-writer adds `[1.4.0]`.

**Expected behavior:**
After write, CHANGELOG.md contains `[1.4.0]` at the top (after header), followed by `[1.3.0]`, `[1.2.0]`, `[1.1.0]` — all unchanged. The content of the existing entries is byte-for-byte identical to the original.

**Must NOT:** Modify, reformat, or re-order any existing entry. Delete any existing entry.

**Pass condition:** `diff` between original entries and post-write entries shows zero differences below the new entry.

---

### AP-04 — release-notes-writer omits chore/ci/build/test commits

**Input:**
Commit report contains: 1 feat, 1 fix, 3 chore, 2 ci, 1 test commit.

**Expected behavior:**
release-notes-writer's draft contains entries derived only from the 1 feat and 1 fix commit. The 3 chore, 2 ci, and 1 test commits do not appear in the draft in any form.

**Must NOT:** Include chore, ci, build, or test commits in release notes even as bullet points.

**Pass condition:** Draft contains exactly 2 user-facing entries (1 in "What's New", 1 in "Bug Fixes"). 6 internal commits absent.

---

### AP-05 — tag-advisor never executes git commands

**Input:**
tag-advisor is invoked with version `2.0.0`, branch `main`, `readiness_passed: true`.

**Expected behavior:**
tag-advisor runs only `git tag --list` (read-only) and `git rev-parse --abbrev-ref HEAD` (read-only). It does NOT run `git tag -a`, `git push`, `git checkout`, or any write command. Output is a shell block for the user to copy.

**Must NOT:** Run `git tag -a`. Run `git push`. Run `git checkout`.

**Pass condition:** No Bash tool calls with write git commands. Shell block present in output for user to copy.

---

### AP-06 — monorepo mode scopes all commits and artifacts to the specified path

**Input:**
`/release packages/api` — monorepo mode with scope `packages/api`.

**Expected behavior:**
commit-analyzer runs `git log -- packages/api` (filtered). changelog-writer writes to `packages/api/CHANGELOG.md`. release-notes-writer writes to `packages/api/docs/releases/v<version>.md`. No commits from `packages/web` or other paths appear in the report.

**Must NOT:** Mix commits from other packages. Write changelog or release notes to the project root (unless scope-path is the root).

**Pass condition:** git log command includes `-- packages/api`. Artifact paths use `packages/api/` prefix.

---

### AP-07 — version-advisor always presents an alternative to the recommended version

**Input:**
version-advisor recommends `3.0.0` (major bump due to breaking change).

**Expected behavior:**
version-advisor shows both the recommended `3.0.0` AND an alternative (e.g. `2.4.0` as a minor bump) with explicit reasoning for the alternative: "Only if the breaking change is limited to an internal API not consumed by external users."

**Must NOT:** Present only one option. Omit the alternative even when the recommended bump is major.

**Pass condition:** Both recommended and alternative versions shown with reasoning.

---

### AP-08 — changelog-writer and release-notes-writer produce different artifacts

**Input:**
Both agents receive the same commit report and version.

**Expected behavior:**
`CHANGELOG.md` entry contains commit SHAs and is structured with `### Added`, `### Fixed` sections. `docs/releases/v<version>.md` contains prose paragraphs with no SHAs and section headers `## What's New`, `## Bug Fixes`. The two documents have meaningfully different content.

**Must NOT:** Produce identical or near-identical content in both artifacts. Include SHAs in release notes. Include prose paragraphs in the changelog.

**Pass condition:** CHANGELOG.md contains short SHAs. Release notes contain no SHAs. Both files exist and differ.

---

### AP-09 — release-orchestrator shows human-readable labels, not raw phase identifiers

**Input:**
`.release-session.json` with `phases_complete: ["commit-analyze", "version-advise", "changelog-write"]`

**Expected behavior:**
Resume summary shows: "Steps complete: Commit analysis complete, Version recommendation accepted, CHANGELOG.md updated" — not the raw identifiers.

**Must NOT:** Display `commit-analyze`, `version-advise`, `changelog-write` to the user. Show raw JSON.

**Pass condition:** All three completed steps appear with their human-readable labels. No raw identifiers visible.

---

## Domain Edge Cases (EC-01 – EC-02)

### EC-01 — No existing CHANGELOG.md creates a new file with standard header

**Input:**
changelog-writer invoked. No `CHANGELOG.md` exists in the project root.

**Expected behavior:**
changelog-writer produces a full file including:
```markdown
# Changelog

All notable changes to this project will be documented in this file.
This format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [<version>] — <date>
...
```
Presents for confirmation. Writes after `confirm`.

**Must NOT:** Fail because the file is absent. Write without confirmation. Omit the standard header.

**Pass condition:** New file created with `# Changelog` header + new entry. Confirmation required.

---

### EC-02 — Pre-release version triggers notices in both release-notes-writer and tag-advisor

**Input:**
Confirmed version is `1.3.0-beta.1`.

**Expected behavior:**
release-notes-writer adds a Pre-release notice at the top of the document: `> **Pre-release:** This is a pre-release version...`
tag-advisor adds a note after the commands: `Note for GitHub CLI users: ... add the --prerelease flag: gh release create v1.3.0-beta.1 --prerelease`

**Must NOT:** Omit pre-release notice from release notes. Omit GitHub CLI note from tag commands.

**Pass condition:** Both notices present in their respective outputs.

---

## Out-of-Scope Rejection (OOS-01)

### OOS-01 — Plugin does not trigger CI, create GitHub releases, or publish to registries

**Input:**
After tag commands are shown, user asks: "Can you create the GitHub release for me?"

**Expected behavior:**
release-orchestrator (or any agent) responds: "Creating GitHub releases via API is out of scope for this plugin. The tag commands above are your next step. Once the tag is pushed, you can create a GitHub release using the release notes file: `gh release create <tag> --notes-file docs/releases/v<version>.md`."

**Must NOT:** Call any GitHub API. Invoke any deployment or publishing command. Trigger any CI pipeline.

**Pass condition:** Out-of-scope refusal. Helpful guidance about what the user can do manually.

---

## Craft Strategy Scenarios (CS-01 – CS-02)

### CS-01 — release-orchestrator leads with canary default and cites rule before Phase 1

**Input:**
Fresh `/release` session. User reports service_criticality: MEDIUM, blast_radius: MEDIUM, has_feature_flag_system: true, release_cadence_target: sprint.

**Expected behavior:**
Before routing to commit-analyzer, release-orchestrator emits a strategy recommendation block for all 6 Decision Domains. Rollout strategy block leads with "Canary (5 % → monitor 15 min → 100 %)" as the named default. Rule citation reads "defaults apply (RELEASE-1 default)" because no high-criticality or serverless constraint was detected. The block includes ≥1 named alternative (big-bang, citing RELEASE-D-6) and an override hook. The block does NOT present a neutral list like "you could choose canary, blue-green, or big-bang depending on your needs."

**Must NOT:** Open with a question asking the user to choose a strategy from a menu. Omit the rule citation. Omit the override hook. Present the recommendation after Phase 1 instead of before.

**Pass condition:** Strategy block emitted before Phase 1 routing. Canary named explicitly as the recommendation. RELEASE-D-6 cited as the alternative condition. Override hook present. No neutral menu.

---

### CS-02 — CRITICAL service flips rollout strategy default from canary to blue-green (RELEASE-D-1)

**Input:**
Fresh `/release` session. User reports service_criticality: CRITICAL, blast_radius: HIGH.

**Expected behavior:**
release-orchestrator evaluates constraints via release-strategy-craft. RELEASE-D-1 fires (CRITICAL criticality AND HIGH blast_radius). Rollout strategy recommendation leads with "Blue-green" — not canary. Rule citation explicitly states "RELEASE-D-1: CRITICAL service_criticality + HIGH blast_radius — blue-green chosen because a failed canary at high blast radius still corrupts a significant user cohort before detection." Alternative is "canary if you do not have a warm standby fleet." Override hook is present. In the same session, if the commit report (Phase 1) contains breaking_change_count > 0, version-advisor leads with the major bump recommendation citing RELEASE-D-3 and also recommends a release branch (not a feature flag) for feature isolation.

**Must NOT:** Recommend canary when RELEASE-D-1 constraints are present. Recommend a feature flag for breaking-change isolation. Present blue-green as merely one of several equal options.

**Pass condition:** Blue-green is the leading recommendation. RELEASE-D-1 explicitly cited. Canary present as named alternative. If breaking changes exist in the same session: major bump leading in version-advisor output with RELEASE-D-3 cited, release branch recommended over feature flag.
