# Routine: morning brief (design)

Created in phase 5 of `AGENTS.md`, after checkpoint 5a; enabled only after checkpoint 5b. Every setting lives under `routines.morning_brief` in `kit.config.yaml`.

- Name: `routines.morning_brief.name` (default `morning-brief`). If I already have a morning or daily summary routine, the kit **merges into it** (`routines.morning_brief.merge_into` names it): it adds the sections below to my routine instead of creating a second one.
- Enabled: `routines.morning_brief.enabled` (default `false`). Off until I enable it with a separate OK.
- Schedule: at `routines.morning_brief.time` (default 07:30) in `kit.timezone`; weekdays only while `routines.morning_brief.weekdays_only` is `true` (the default).
- Reads (read-only):
  - today's calendar (if connected);
  - second-brain notes changed since the last brief, per channel (`sb --doctor` summary plus changed paths);
  - the content calendar rows due today or tomorrow;
  - draft posts waiting for my approval;
  - runner status, only if `runner.enabled` is `true`.
- Output: at most 10 lines, grouped by channel, never mixing details from two channels in one bullet. No personal data about students or parents, ever.
- Quiet rule: if nothing changed and nothing is due, send nothing (or one line "nothing new"), per `routines.morning_brief.quiet_when_unchanged` (default `true`).
- Never sends, posts or schedules anything for me; it only reports.
