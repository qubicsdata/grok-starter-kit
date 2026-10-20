---
name: product-pulse
description: |
  Use when a session begins, when the user asks "what should I build next" or "where was I", or when starting multi-step work in a repo containing docs/product/passport.json — surfaces the project's lifecycle stage, active story, and the earned next step.
---

# product-pulse

The primary arc-awareness mechanism: one earned line of product context at the moment work starts, then get out of the way. Silence is the earned default.

## HARD SILENCE GATE

**When the passport shows no active story AND an empty ready lane, emit NOTHING.** Not a summary, not a greeting, not a "backlog is empty" notice — zero output from this skill. Only an occupied lane or an in-flight story earns a line.

## Reads

Exactly one read of `docs/product/passport.json` (plus `.product-session.json` if present — the in-flight build pointer). `ready_count` is denormalized in the passport for exactly this one-read need: no directory scans. If the passport does not exist or does not parse, this skill emits nothing (the `/product-init` recovery path is not this skill's job).

## Output — at most ONE line, then point at the command

- Mid-story (`.product-session.json` present) →
  `Mid-story S-004 (execute, 2/5 AC met) — /build-next resumes.`
- No active story, ready lane non-empty, stage=building →
  `Ready lane has 3 stories — /build-next takes S-007.`
- Stage ≠ building with earned evidence → the lifecycle-stages handoff line for that stage (e.g. stage=idea → `/greenfield`; stage=hardening → `/release-ready`). One line, only when the stage's evidence row is present.

Never more than one line. Never repeat the line later in the same session.

## Routing requested work

- If the work the user is asking for matches an existing backlog story, propose entering through `/build-next` so the work is recorded against the story.
- If it matches no story, offer `/story` to capture it.
- **Offer once, never nag.** A declined offer is not repeated.

## Hard gate

**DO NOT modify the passport or any artifact from this skill** — only passport-agent advances stage, on evidence. **DO NOT start building without /build-next's confirmation gate.** This skill reads, emits at most one line, and stops.
