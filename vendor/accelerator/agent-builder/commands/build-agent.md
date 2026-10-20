---
description: Build, audit, or workshop a Claude Code plugin with a full cognitive review cycle
argument-hint: [path-to-existing-plugin]
---

You are the entry point for agent-builder. Invoke builder-orchestrator to begin the session.

Pass the argument (if provided) to builder-orchestrator — it will be interpreted as the existing plugin path in audit mode, or as an output directory hint in generate mode. If no argument is given, builder-orchestrator will determine the output directory after intake completes.

Invoke builder-orchestrator now. Do not ask the user any questions first — orchestrator handles intake.
