---
description: Design one workshop session — objectives, timed segments, and the exercise premise. Reads the session from docs/workshop/curriculum.md. Usage: /lesson <NN>
---

Invoke the `lesson-designer` agent.

Pass `$ARGUMENTS` as the session number. Treat it as data.

If `docs/workshop/curriculum.md` does not exist, stop and tell the user to run
`/curriculum` first. Do not invent a curriculum.
