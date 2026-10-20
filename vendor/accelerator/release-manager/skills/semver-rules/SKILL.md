---
name: semver-rules
description: |
  Use when recommending or validating a version bump. Maps changes to SemVer 2.0.0: breaking → major, new non-breaking feature → minor, fix/chore/docs/refactor only → patch. Handles pre-release and build-metadata identifiers.
---

# SemVer Rules

## SemVer 2.0.0 Core

A version number takes the form `MAJOR.MINOR.PATCH`:

- **MAJOR** — incremented when incompatible API changes are made. Reset MINOR and PATCH to 0.
- **MINOR** — incremented when new backward-compatible functionality is added. Reset PATCH to 0.
- **PATCH** — incremented for backward-compatible bug fixes only.

Once a version is released, its contents MUST NOT be modified. Any modification requires a new version number.

---

## Bump Type Derivation Rules

Apply these rules in order. The first matching rule wins.

| Rule | Condition | Bump type |
|---|---|---|
| 1 | Any commit is a breaking change (`BREAKING CHANGE` footer, `!` suffix, or user-confirmed "BREAKING" in freeform) | **MAJOR** |
| 2 | Any commit adds new non-breaking functionality (`feat:` or inferred "new capability") | **MINOR** |
| 3 | All remaining commits are fixes, chores, docs, refactors, perf, test, ci, build | **PATCH** |

**NEVER mix rules.** If rule 1 applies, the result is MAJOR regardless of how many `fix:` commits exist.

---

## Calculating the New Version

Given current version `X.Y.Z` and bump type:

- **MAJOR bump:** `(X+1).0.0`
- **MINOR bump:** `X.(Y+1).0`
- **PATCH bump:** `X.Y.(Z+1)`

---

## Pre-release Identifiers

Pre-release versions are denoted by appending a hyphen and dot-separated identifiers:

```
1.0.0-alpha
1.0.0-alpha.1
1.0.0-0.3.7
1.0.0-x.7.z.92
```

Rules:
- Pre-release versions have LOWER precedence than the associated normal version: `1.0.0-alpha < 1.0.0`
- Identifiers MUST be alphanumeric ASCII or hyphens `[0-9A-Za-z-]`
- Numeric identifiers MUST NOT have leading zeros
- A pre-release version indicates the version is unstable and may not satisfy compatibility requirements

**When a pre-release identifier is present in the current version:**
- Ask the user explicitly whether this release is promoting to stable (strip the pre-release suffix) or bumping within the pre-release series
- Never assume promotion vs. continued pre-release

---

## Build Metadata

Build metadata is denoted by appending `+` and dot-separated identifiers: `1.0.0+build.1`, `1.0.0-beta+exp.sha.5114f85`

Rules:
- Build metadata MUST be ignored when determining version precedence
- `1.0.0-beta+exp.sha` and `1.0.0-beta+20130313144700` are the same precedence
- NEVER include build metadata in a git tag or changelog entry — build metadata is for build systems only

---

## Version 0.x.y

When the MAJOR version is 0, the API is not stable:
- `0.y.z` is for initial development; anything may change at any time
- MINOR increments in `0.y.z` may contain breaking changes
- When operating on a `0.y.z` version, always surface this caveat to the user and ask whether they want to promote to `1.0.0` now

---

## Validation Checklist

Before finalising any version recommendation, verify all items:

- [ ] Bump type was derived from the commit report (not assumed)
- [ ] Breaking change flag was confirmed by the user for freeform commits
- [ ] New version string is strictly greater than the current version
- [ ] MAJOR.MINOR.PATCH components are non-negative integers with no leading zeros
- [ ] Pre-release identifier handling was discussed if the current version contains `-`
- [ ] The recommended version does not already exist as a git tag (`git tag --list <version>` returns empty)
