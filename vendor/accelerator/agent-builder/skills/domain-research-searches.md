---
name: domain-research-searches
description: Query derivation rules, stakes-tiered search depth, and domain brief format for domain-researcher
---

## Domain Extraction Rule

Extract the domain noun phrase from the plugin description:
- "A GDPR compliance checker" → domain = `GDPR compliance`
- "A Rust code reviewer" → domain = `Rust code review`
- "An OWASP security auditor" → domain = `OWASP security audit`

If extraction is ambiguous or the description is fewer than 5 words, use the full description as the domain phrase.

## Stakes-Tiered Query Sets

Use the stakes score from the task-scoring output to select the appropriate query set.

### Stakes 1 — Personal use (max 3 WebSearch queries, 2 WebFetch calls)

1. `[domain] best practices`
2. `[domain] common mistakes`
3. `[domain] authoritative reference`

### Stakes 2 — Private marketplace (max 6 WebSearch queries, 4 WebFetch calls)

1. `[domain] agent best practices`
2. `[domain] common failure modes`
3. `[domain] authoritative standards OR official specification`
4. `[domain] anti-patterns`
5. `[domain] examples OR case studies`
6. `site:github.com [domain] agent`

### Stakes 3 — Public marketplace / infrastructure (max 10 WebSearch queries, 6 WebFetch calls)

All Stakes 2 queries, plus:

7. `[domain] security considerations`
8. `[domain] edge cases`
9. `[domain] testing strategies`
10. `[specific framework or standard from description] reference`

## Domain Brief Format

Produce the brief in this exact structure. Every section must be present, even if blank.

```
## Domain Brief — [plugin-name] — [ISO timestamp]

### Core Domain Knowledge
[Key concepts, frameworks, standards, and principles the generated agent must embody.
Write as directives: "The agent must know that X", "The agent should apply Y when Z".]

### Anti-Patterns to Avoid
[Known failure modes of similar agents and domain-specific pitfalls.
Write as prohibitions: "Do not X", "Avoid Y because Z".]

### Authoritative Sources Consulted
| URL | Contribution |
|---|---|
| [url] | [one-line summary of what this source contributed] |

### Recommended Runtime References
[Sources the generated agent itself should WebFetch at runtime for up-to-date information
if the domain changes frequently. Leave blank if the domain is stable.]

### Research Gaps
[Topics searched but not found, or searches that failed.
Write: "No authoritative source found for X — design-agent should note this as a limitation."]
```

## STOP

DO NOT exceed the WebSearch and WebFetch limits for the stakes tier. Stakes-1 plugins must not trigger more than 3 WebSearch queries and 2 WebFetch calls total. Exceeding this wastes the user's resources and violates the scope constraint.
