---
description: Show a summary of quality scores from .ai-evolution/feedback.jsonl. Usage: /evolution-report [agent=<name>]
---

Parse $ARGUMENTS for agent=<name> filter (optional).

Read .ai-evolution/feedback.jsonl from project root. If absent, return:
```
No feedback journal found. Run /score first.
```

Otherwise:
1. Read all entries from feedback.jsonl (JSONL format, one JSON object per line).
2. Parse each entry and extract: agent, completeness, safety, accuracy, overall.
3. Group entries by agent name.
4. Compute per-agent averages for completeness, safety, accuracy, overall.
5. If 5+ entries exist for an agent, compute trend (improving/stable/declining) based on moving average of last 5 vs prior entries.
6. If agent=<name> filter provided in $ARGUMENTS, show only that agent.

Output format:
```
EVOLUTION REPORT
================
[agent]: completeness=<avg>, safety=<avg>, accuracy=<avg>, overall=<avg> (<N> entries) [trend]
...
```

Example with trend:
```
EVOLUTION REPORT
================
quality-scorer: completeness=7.2, safety=9.1, accuracy=8.0, overall=8.1 (12 entries) improving
feedback-journal-agent: completeness=9.0, safety=9.5, accuracy=8.8, overall=9.1 (8 entries) stable
```
