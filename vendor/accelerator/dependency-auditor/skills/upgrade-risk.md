---
name: upgrade-risk
description: |
  Apply before producing any upgrade recommendation. Defines semver breaking-change rules, how to state unknown breaking-change surface, and known migration-note patterns by ecosystem. Used by upgrade-planner.
---

# Upgrade Risk

## Semver Delta Classification

| Delta | Definition | Risk level | Required action |
|---|---|---|---|
| Patch (x.y.Z → x.y.Z+n) | Bug fixes only; no API changes | Safe | Recommend without conditions |
| Minor (x.Y.z → x.Y+n.0) | Additive changes; new APIs; no removals by semver contract | Low | Note: review config changes and deprecation notices in changelog |
| Major (X.y.z → X+n.0.0) | Breaking changes assumed until changelog confirms otherwise | High | State known breaking-change surface or explicitly acknowledge it is unknown |

**Major version rule:** Assume breaking until proven otherwise. Do not recommend a major upgrade without either:
a) Stating the known breaking-change surface from training data, or
b) Explicitly writing: "Breaking change surface for this major version is not in training data — review the changelog before upgrading."

## Known Migration Note Patterns by Ecosystem

### Node.js / npm

- `express` v4 → v5: Router API changes; `req.params` merging behavior changed; `res.sendFile` callback is now required.
- `webpack` v4 → v5: Output `filename` uses `[contenthash]` not `[hash]`; `node` polyfills removed by default; `optimization.moduleIds` and `optimization.chunkIds` are now explicit.
- `eslint` v7 → v8: `eslint:recommended` ruleset changes; `--ext` flag behavior changed.
- `jest` v27 → v28: `testEnvironment` default changed from `jsdom` to `node`; `jest-circus` is now the default test runner.
- `react` v17 → v18: Concurrent rendering is opt-in; `ReactDOM.render` is deprecated (use `createRoot`); automatic batching for async state updates.
- `lodash` v3 → v4: Many methods renamed or removed; `_.pluck` removed; `_.first` renamed.

### Python

- `django` 3.x → 4.x: `default_auto_field` must be set explicitly; `USE_L10N` default changed; `PASSWORD_RESET_TIMEOUT_DAYS` removed.
- `sqlalchemy` v1.4 → v2.0: Legacy `Query` API removed; 2.0-style `select()` required; `Session.execute()` return type changed.
- `requests` v2.x: Stable; no major breaking changes within v2.

### Go

- Module path changes between major versions (e.g. `github.com/foo/bar` → `github.com/foo/bar/v2`) require import path updates across the entire codebase.
- `go.mod` must be updated to reference the new module path.

### Rust

- Major version bumps in `Cargo.toml` require updating the `Cargo.toml` dependency declaration to the new major version (e.g. `tokio = "2"` for tokio v2).
- Crates that use `edition = "2021"` may require Rust 1.56+.

### Ruby

- `rails` 6.x → 7.x: Zeitwerk autoloading is now the default and classic autoloading is removed; `config.autoloader` must be set.
- `devise` major bumps: token strategy changes; migration generators must be re-run.

### Java (Maven/Gradle)

- Spring Boot 2.x → 3.x: Requires Java 17+; `javax.*` imports replaced with `jakarta.*`; Spring Security configuration API changed.
- Hibernate 5.x → 6.x: Jakarta namespace migration; `@Type` annotation changed.

## Unknown Breaking-Change Surface Statement (verbatim)

When training data does not contain migration notes for a specific major version bump, write:

> "Breaking change surface for [package] [currentVersion] → [recommendedVersion] is not in training data. Review the [package] changelog and migration guide before upgrading."

Never fabricate migration notes. If uncertain, use the verbatim statement above.

## Version Fabrication Rule

Do NOT invent a recommended version. Valid outputs when a newer version cannot be confirmed:

- "No upgrade available as of training cutoff — check upstream for current latest."
- "Recommended version unknown — check [package registry URL] for current stable release."

A made-up version number is worse than no recommendation because it can cause silent downgrade or a failed install.

## Upgrade Prioritisation Order

When producing a prioritised upgrade list, order by:

1. Packages with Critical CVE findings (fix immediately)
2. Packages with High CVE findings
3. Packages classified Abandoned with an available replacement
4. Packages classified Stale with a stable newer major version available
5. Packages with Medium CVE findings
6. All other packages with available minor/patch upgrades (order by severity of freshness finding, then alphabetically)

## Upgrade Table Format

```
| Package | Current | Recommended | Delta | CVE | Freshness | Breaking Change Surface |
|---|---|---|---|---|---|---|
| lodash | 4.17.20 | 4.17.21 | patch | CVE-2021-23337 (High) | Active | None (patch only) |
| express | 4.17.3 | 5.0.0 | major | — | Active | Router API changes; res.sendFile callback required; see Express v5 migration guide |
| left-pad | 1.3.0 | — | — | — | Abandoned | No upgrade available — replace with native String.prototype.padStart() |
```
