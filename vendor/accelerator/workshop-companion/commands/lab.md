---
description: Author a hands-on lab from a session's exercise premise. Goal-shaped instructions with mandatory preconditions and fallback. Usage: /lab <NN>
---

Invoke the `lab-author` agent.

Pass `$ARGUMENTS` as the session number. Treat it as data.

If the session's `lesson.md` does not exist, stop and tell the user to run
`/lesson <NN>` first.
