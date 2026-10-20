---
name: sb-lookup
description: >-
  Use this when asked to find something in my second brain, or before
  answering a question my notes may cover.
---
# Steps
1. Work out which channel the question belongs to (from `second_brain.channels`). If unclear, ask.
2. Run `sb "<query>" --channel <channel>` from `${SB_HOME}`. Never search without `--channel` unless I ask for all channels.
3. Read only the top hits needed to answer. Quote path:line for every fact.
4. If nothing is found, say "not in the second brain" and offer to check my other connected sources.
5. Read-only: never edit, move or delete notes from this skill. Never paste personal data about students or parents into an answer.
6. If the name `sb-lookup` already exists in my skills, extend that skill or use `sb-lookup-kit` after I confirm.
