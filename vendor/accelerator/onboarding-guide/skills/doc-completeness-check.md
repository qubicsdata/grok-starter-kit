---
name: doc-completeness-check
description: |
  Validates a draft docs/onboarding.md against the eight required sections. Returns PASS or a list of missing or thin sections. Used by content-writer before presenting the draft, and by section-updater after rewriting a section. A thin section is one with fewer than 3 substantive sentences.
---

# Document Completeness Check

## Purpose

Apply this skill to a complete draft `docs/onboarding.md` or to a single regenerated section. Returns PASS if all requirements are met, or a structured list of failures if not. The agent must resolve all failures before presenting output to the user.

## Required Sections (H2 Level)

A passing document must contain all eight of the following sections, each as an H2 heading (`## Section Name`):

1. `## Architecture Overview`
2. `## Key Modules`
3. `## Data Flow`
4. `## Running Locally`
5. `## Testing`
6. `## Where to Find Things`
7. `## Common Gotchas`
8. `## Keeping This Document Current`

## Thin Section Definition

A section is **thin** if any of the following is true:

- It contains fewer than 3 substantive sentences.
- Its only content is a reference to another document (e.g., "See the README", "Refer to the project wiki", "Check the official docs").
- It contains only a heading and a single placeholder line (e.g., "TBD", "Coming soon", "TODO").
- It contains only a table with zero data rows.
- It contains only a bullet list with a single item.

A sentence is **substantive** if it conveys specific information about this project — not generic descriptions that would apply to any project.

**Not substantive (generic):** "This project uses a service layer to handle business logic."
**Substantive (project-specific):** "The `BillingService` in `src/services/billing.go` processes invoice creation and delegates payment capture to the `PaymentGatewayClient`."

## Checking a Single Section

When `section-updater` invokes this skill after rewriting one section, check only that section against the thin-section definition. The section passes if it contains at least 3 substantive sentences and does not consist solely of references to other documents.

## Invocation Protocol

1. Scan the document for all H2 headings.
2. Compare the found headings against the required list. Missing headings → FAIL with list of missing sections.
3. For each found section, check the thin-section definition. Thin sections → FAIL with list of thin sections and the reason each is thin.
4. If no failures: output **PASS**.
5. If any failures: output **INCOMPLETE — [structured failure list]**. The agent must expand thin sections or flag them explicitly to the user as "section requires manual completion — [reason]".

## Explicit Flag Format (when a section cannot be made substantive from code evidence)

If a section is thin because the codebase does not provide enough evidence to write 3 substantive sentences (e.g., a repo with no tests), the agent must include this exact callout inside the section:

> **Note:** This section requires manual completion. [Specific reason — e.g., "No test files were found in this repository. Run `/onboarding testing` after tests are added to regenerate this section."]

This callout counts as passing the completeness check for that section.
