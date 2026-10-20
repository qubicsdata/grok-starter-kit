---
name: license-compatibility
description: |
  Use before judging any package license. Sets out the compatibility matrix by license identifier, the copyleft spread rules, the limits on commercial use, and the severity levels for license findings. Used by license-agent.
---

# License Compatibility

## Compatibility Matrix by License Identifier

| License | Category | Use in MIT/Apache-2.0 project | Use in proprietary commercial project | Severity if used incorrectly |
|---|---|---|---|---|
| MIT | Permissive | PASS | PASS | — |
| ISC | Permissive | PASS | PASS | — |
| BSD-2-Clause | Permissive | PASS | PASS | — |
| BSD-3-Clause | Permissive | PASS | PASS | — |
| Apache-2.0 | Permissive | PASS | PASS | — (patent grant included) |
| MPL-2.0 | Copyleft-Weak | PASS (file-level copyleft only) | PASS with caveat | Medium — modified MPL files must be shared; does not infect the whole project |
| LGPL-2.1 | Copyleft-Weak | PASS if dynamically linked | CONDITIONAL | High — static linking may require source disclosure |
| LGPL-3.0 | Copyleft-Weak | PASS if dynamically linked | CONDITIONAL | High — static linking may require source disclosure |
| GPL-2.0 | Copyleft-Strong | BLOCK | BLOCK | Critical — strong copyleft contaminates the entire project |
| GPL-3.0 | Copyleft-Strong | BLOCK | BLOCK | Critical — strong copyleft contaminates the entire project |
| AGPL-3.0 | Copyleft-Strong | BLOCK | BLOCK | Critical — network-use copyleft; stricter than GPL |
| SSPL-1.0 | Copyleft-Strong | BLOCK | BLOCK | Critical — service-use copyleft; highly restrictive for SaaS |
| CC-BY-4.0 | Content License | Low / Info | Medium | Medium (commercial) / Info (open) — intended for content, not software |
| UNLICENSED | Unknown | High | Critical | High (open) / Critical (commercial) — cannot determine risk |
| UNKNOWN | Unknown | High | Critical | High (open) / Critical (commercial) — cannot determine risk |
| Proprietary | Proprietary | FAIL | Only with explicit permission | Critical without agreement — check upstream license terms |

## GPL Contamination Rule

When any direct or transitive dependency carries GPL-2.0, GPL-3.0, or AGPL-3.0, and the project's own declared license is not GPL-compatible (e.g. MIT, Apache-2.0, proprietary), file a **Critical** finding.

The finding **must** trace the full dependency chain from the project root to the GPL-licensed package. Format:

```
[Critical] GPL contamination detected
Chain: myapp → react-pdf@3.1.4 → pdfkit@0.13.0 → [GPL-3.0-licensed-dep@1.2.0]
Consequence: The entire project is subject to GPL-3.0 terms. The project cannot be distributed under MIT or a proprietary license while this dependency is present.
```

If the GPL-licensed package is only in the transitive graph (not a direct dependency), the chain must show every intermediate node. Do not summarise as "indirect GPL dependency" without the full chain.

## LGPL Linking Rule

LGPL-2.1 and LGPL-3.0 are Copyleft-Weak. The key distinction is linking mode:

- **Dynamic linking** (the LGPL library is a `.so`, `.dll`, or equivalent loaded at runtime): PASS — no source disclosure required for the consuming project.
- **Static linking** (the LGPL library is compiled into the binary): CONDITIONAL — source disclosure of the consuming project may be required under LGPL terms.

When the linking mode cannot be determined from manifest inspection alone (most JavaScript and Python ecosystems), state explicitly:
> "Linking mode cannot be determined from manifest inspection alone. If this library is statically bundled (e.g. via webpack with `externals: false`), LGPL source disclosure may apply. Review your bundler configuration."

Severity: **High** regardless of linking mode when certainty is impossible from files alone.

## Unknown License Rule

Any package with no identifiable SPDX license identifier (field absent, `UNLICENSED`, `SEE LICENSE IN LICENSE.md` with no further resolution) is flagged **High** for open-source projects and **Critical** for proprietary commercial projects.

Rationale: unknown license = cannot assess risk. The unknown license could be more restrictive than any known copyleft license.

## Dev Dependency Downgrade Rule

License findings on packages where `is_dev: true` are downgraded **one severity level** with an explicit annotation:

- Critical → High (annotate: "dev dependency — not shipped in production artifact")
- High → Medium (annotate: "dev dependency — not shipped in production artifact")
- Medium → Low (annotate: "dev dependency — not shipped in production artifact")

Do not downgrade Info findings. Do not downgrade if the dev dependency is also required at runtime (some build tools are both).

## Project License Absent Rule

If the project's own declared license is absent (no `"license"` field in `package.json`, no `license` key in `pyproject.toml` or `Cargo.toml`, no `LICENSE` file detectable from manifest metadata), file a **High** finding:

```
[High] Project license undeclared
The project manifest does not declare a license. This means consumers cannot determine the terms under which this software may be used, modified, or distributed.
```

Treat the project license as `UNKNOWN` for all compatibility checks when absent.

## Categories Reference

- **Permissive**: MIT, ISC, BSD-2, BSD-3, Apache-2.0 — minimal restrictions; no contamination
- **Copyleft-Weak**: MPL-2.0, LGPL-2.1, LGPL-3.0 — file-level or linking-conditional copyleft
- **Copyleft-Strong**: GPL-2.0, GPL-3.0, AGPL-3.0, SSPL-1.0 — project-level copyleft; incompatible with proprietary use
- **Proprietary**: per-package commercial terms; requires explicit permission
- **Unknown**: no identifiable SPDX identifier; treat as highest risk
