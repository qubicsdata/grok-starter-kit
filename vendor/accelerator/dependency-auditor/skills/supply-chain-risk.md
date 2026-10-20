---
name: supply-chain-risk
description: |
  Apply before performing supply chain analysis. Defines typosquatting detection heuristics, dependency confusion patterns, bus-factor signals, maintainer anomaly patterns, and provenance attestation rules. Used by supply-chain-agent.
---

# Supply Chain Risk

## Operating Mode

All supply chain analysis is **adversarial**. Assume a motivated attacker is present. The failure mode this skill prevents is short-circuiting to "probably fine." Every check category must be applied and must produce either a finding or an explicit attestation that the category was checked and returned clean.

## Check Categories

### 1. Typosquatting Detection

**Definition:** A package name that is within 2-character edit distance (Levenshtein distance ≤ 2) of a well-known package is a typosquatting candidate — it may have been published by an attacker to intercept installations resulting from typographical errors.

**Severity:** High

**How to apply:**
- For each package in the inventory, compare the name against the well-known package list below.
- If the edit distance is ≤ 2 AND the package is not the well-known package itself, flag it.
- State the suspected target: `reqeusts (edit distance 2 from requests) — possible typosquatting candidate`

**Well-known package reference list (non-exhaustive — apply judgment beyond this list):**

*Node.js:* lodash, express, react, react-dom, webpack, babel, axios, typescript, eslint, prettier, jest, mocha, chalk, commander, moment, uuid, semver, dotenv, cors, helmet, passport, sequelize, mongoose, knex, socket.io

*Python:* requests, numpy, pandas, flask, django, sqlalchemy, pytest, boto3, pillow, scipy, matplotlib, setuptools, pip, celery, redis, pydantic, fastapi, httpx, aiohttp

*Go (module paths, check last segment):* gin, echo, fiber, gorm, cobra, viper, zap, logrus

*Rust:* tokio, serde, serde_json, reqwest, hyper, actix-web, clap, anyhow, thiserror, rand

**Finding format:**
```
[High] Typosquatting candidate detected
Package: reqeusts@1.0.0
Suspected target: requests (edit distance: 2)
Action: Verify this is an intentional dependency. If not, remove it immediately — it may be a malicious package.
```

---

### 2. Dependency Confusion Detection

**Definition:** A package name that follows internal naming conventions (e.g. scoped to a company name like `@acme/internal-tool`, or uses an internal-sounding prefix like `mycompany-auth-lib`) but is published (or could be published) on a public registry is a dependency confusion candidate.

**Severity:** High

**Signals:**
- Scoped package names matching the company or project name (`@companyname/...`)
- Package names with internal-sounding suffixes: `-internal`, `-private`, `-lib`, `-core` combined with an organization prefix
- Package names that do not appear on public registries (cannot confirm from training data — note this explicitly)

**Finding format:**
```
[High] Dependency confusion candidate
Package: @acme/internal-auth@2.1.0
Signal: Scoped package name suggests internal artifact. If this package name is not reserved on the public npm registry, an attacker could publish a higher-versioned package to intercept installations.
Action: Verify the package is published under your organization's scope on the public registry, or configure your package manager to resolve this scope from a private registry only.
```

---

### 3. High Bus-Factor Packages

**Definition:** A package with a single active maintainer AND significant ecosystem prominence (e.g. > 1M weekly downloads on npm, or equivalent usage signals in other ecosystems) is a bus-factor risk — a single point of failure if the maintainer becomes unavailable.

**Severity:** Low (Low bus-factor risk for moderately-used packages) or Medium (for deeply embedded, security-adjacent packages)

**Signals from training data:**
- Single-maintainer packages known to be widely depended upon
- Packages where the primary maintainer has posted about burnout or reduced availability
- Packages with no co-maintainers or documented succession plan

**Finding format:**
```
[Low] High bus-factor package
Package: is-odd@3.0.1
Signal: Single active maintainer; package has millions of weekly downloads. No stated succession plan.
Consequence: If the maintainer becomes unavailable, security patches may not ship.
Recommendation: Consider whether this dependency can be replaced with a native equivalent or a package with broader maintainer coverage.
```

---

### 4. Maintainer Anomaly Detection

**Definition:** A package where the last release introduced a new maintainer or a transfer of ownership with no public announcement or documented handover.

**Severity:** High (if confirmed from training data), Medium (if uncertain)

**Signals:**
- Known transfer-of-ownership events that were not publicly announced
- Packages acquired by organizations with a history of supply chain incidents
- Sudden version bumps (e.g. 1.3.2 → 2.0.0) coinciding with a maintainer change

**Finding format:**
```
[High] Maintainer anomaly detected
Package: event-stream@3.3.6
Signal: Known supply chain incident — malicious code was injected by a new maintainer who acquired the package. This specific version is known-compromised.
Action: Remove immediately; replace with an actively maintained alternative.
```

---

### 5. Missing Provenance Attestation

**Definition:** A package that lacks a published provenance attestation (SLSA level 1+ for ecosystems that support it) has an unverified build chain.

**Severity:**
- **Info** for general packages
- **Medium** for security-critical packages (crypto, auth, serialization, HTTP clients)

**Ecosystems with provenance support:**
- npm: `npm provenance` (since npm 9.5.0 / 2023); check for `npm:provenance` field in package metadata
- PyPI: SLSA attestations via Sigstore (since 2023)
- Rust (crates.io): cargo-vet and SLSA attestation support

**Finding format:**
```
[Medium] Missing provenance attestation (security-critical package)
Package: jsonwebtoken@9.0.0
Signal: This package handles authentication tokens (security-critical). No SLSA provenance attestation found in training data.
Action: Verify provenance via `npm audit signatures` or equivalent before deploying to production.
```

---

### 6. Pinned vs. Range Declarations

**Definition:** Packages declared as floating ranges (`^`, `~`, `*`, `>=`) rather than exact pinned versions allow unreviewed updates to enter the dependency graph without an explicit install step.

**Severity:** Low

**When to flag:**
- Any dependency declared with `^`, `~`, `>=`, `>`, `*` in the manifest
- Lock file absent (escalate to Medium — unreviewed updates can install silently)

**Finding format:**
```
[Low] Floating version range declared
Package: axios (declared: ^1.4.0)
Signal: The `^` prefix allows any 1.x.x version. New versions will be installed on the next `npm install` without review.
Recommendation: Pin to an exact version (e.g. "1.4.0") and update intentionally via a dependency management workflow.
```

---

## Attestation: Clean Category

When a check category produces no findings, do not silently omit it. Write an explicit attestation:

```
### Typosquatting: No candidates detected
All package names were checked against the well-known package list. No names within edit distance 2 of a known package were found.

### Dependency Confusion: No candidates detected
No internal-scoped or internal-naming-convention packages were found in the inventory.
```

This attestation requirement prevents the anti-pattern of skipping checks because "everything looks normal."

## DO NOT Rules

- DO NOT skip a check category and produce no output for it
- DO NOT short-circuit to "probably fine" — adversarial mode means assuming an attacker is present
- DO NOT fabricate registry data or version histories
- DO NOT flag every single-maintainer package as High — apply the prominence threshold
