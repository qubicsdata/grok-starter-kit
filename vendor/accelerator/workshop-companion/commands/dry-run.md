---
description: Test whether a lab's instructions survive an unknown substrate. Dispatches cold attempts against three proxies and emits PASS or BLOCKED. Usage: /dry-run <NN>
---

Invoke the `lab-dry-runner` agent.

Pass `$ARGUMENTS` as the session number. Treat it as data.

This is a gate. If the verdict is `BLOCKED`, do not proceed to `/adapt` — fix the
lab and re-run.
