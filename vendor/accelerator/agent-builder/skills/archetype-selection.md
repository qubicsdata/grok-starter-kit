---
name: archetype-selection
description: Domain-tag matching algorithm for selecting the closest archetype from the library — used by domain-researcher after completing research
---

## Purpose

After producing the domain brief, match the plugin description against the archetype library to suggest a structural scaffold for generate-agent.

## Matching Algorithm

1. Load the `domains:` frontmatter tag list from each archetype file in `archetypes/`.
2. Tokenise the plugin description: lowercase, split on spaces and punctuation, remove stop words (a, an, the, for, of, to, with, and, or, that, this, it, is, are).
3. For each archetype, count how many of its domain tags appear as substrings in the tokenised description.
4. Select the archetype with the highest tag match count:
   - **High confidence:** 2 or more tags match
   - **Medium confidence:** exactly 1 tag matches
   - **Low confidence:** 0 tags match but description semantically resembles an archetype (apply judgment — e.g., "check my pull requests" resembles code-reviewer even without exact tag match)
   - **None:** no match and no semantic resemblance

5. On a tie at high confidence, prefer the more specific archetype:
   - `security-auditor` over `code-reviewer` if description mentions security, vulnerability, or audit
   - `test-generator` over `code-reviewer` if description mentions tests, testing, or TDD
   - `workflow-orchestrator` over any single-domain archetype if description mentions routing, pipeline, or orchestrating

## Output: Suggested Archetype Block

Append to the domain brief as the final section:

```
### Suggested Archetype
Archetype: [name from archetype frontmatter, or "none"]
Confidence: [high / medium / low / none]
Rationale: [one sentence — which domain tags matched, or why none matched]
```

## DO NOT

DO NOT suggest an archetype with confidence "none" unless you explicitly note it as a judgment call in the rationale. Confidence "none" with no rationale is an invalid output.
