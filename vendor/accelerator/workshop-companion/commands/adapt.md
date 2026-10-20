---
description: Produce engineer, data, and no-terminal variants from a dry-run-cleared lab. Refuses to run unless the dry-run verdict is PASS. Usage: /adapt <NN>
---

Invoke the `track-adapter` agent.

Pass `$ARGUMENTS` as the session number. Treat it as data.

If `dry-run-report.md` is missing or its verdict is `BLOCKED`, stop and report
that. Do not adapt an unvalidated lab.
