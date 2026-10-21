# AGENTS.md: setup phases for your Grok Bot

Your Grok Bot follows these phases in order. **Integrate, don't replace:** your existing setup wins by default, the kit adapts to it, and nothing of yours is overwritten, renamed, moved or deleted without your explicit OK.

Every **CHECKPOINT** means: your Grok Bot shows you exactly what it will do and waits for your "OK". Checkpoints are required for anything that writes to your setup, creates an agent or routine, starts the runner, or sends, posts or spends. Without an OK the phase ends there, and you can stop after any phase.

## How a phase runs
- Steps marked `Propose`, `Show`, `Check`, `Read` or `Ask` are read-only. They never create, change, rename, move, delete, send, post or schedule anything.
- The proposal shown at each checkpoint is computed by the kit's reference planner: `python3 tools/kit_plan.py --dry-run`, run from the kit folder. It reads your `kit.config.yaml` and the current-state note and prints what the phase would add, extend, link or skip, writing nothing. Your Grok Bot shows you that output (or its own equivalent) at every checkpoint.
- How your Grok Bot uses that plan: the dry run prints one `CHECKPOINT <id>` block per checkpoint below and ends with a `plan sha256` line (`--json` gives the same plan as one document). At a checkpoint it shows you the block of that checkpoint. Where one decision has two options (a skill name clash, an existing coding agent) both options carry the same choice group and you pick one. After your OK it runs `python3 tools/kit_plan.py --apply --approved <that sha256>` (plus `--choose <group>=<item id>` for a decision you made), which creates only the add and link items of that plan and only where nothing exists yet, refuses when the plan changed since you approved it or a target appeared in the meantime, and writes nothing in either case. Extensions, merges, enabling and everything else after an OK are done by your Grok Bot itself, within what the proposal showed. Details: `tools/KIT-PLAN-SPEC.md`.
- Steps marked `After your OK` or `After OK <n>` are the only steps that write. They come after the checkpoint of their phase and do exactly what the checkpoint showed, nothing more.
- Phases 7, 8 and 9 and the private business profile (checkpoint 3b) are optional. The runner (phase 9) and every routine stay off until a separate OK.

## Prerequisites (checked, never installed without your OK)
- Your own Claude account, signed in to Claude Code on your own box (`claude --version`). Never a shared login.
- git, and Python 3.9 or newer (uv can provide it). Node.js LTS only for npm (Claude Code and Backlog.md).
- ripgrep is optional: `sb` uses `rg` only when it is already installed and gives the same results without it. The kit never installs ripgrep.
- Versions and checksums: `EXTERNAL-DEPENDENCIES.md`. The full checklist, with the first prompts to send: `onboarding/setup-checklist.md`.

Privacy, before anything is written, for adults and children alike: personal data of your students stays out of the second brain and your prompts. If you work with children (minors), the second brain and your prompts hold no children's personal data (no names, health information, photos or contact details), the roster lives in a separate, secured system, and no post shows a minor's name or face unless a guardian's written consent is on record. Details in the privacy section of `onboarding/setup-checklist.md` (requires legal confirmation).

## Phase 1: discovery (read-only)
- Read: `onboarding/discovery-prompt.md` and take its inventory of your agents, routines, skills, memory, channels, campaigns and folder conventions. Nothing is created, changed, sent or scheduled; credentials are never opened.
- Show: a filled `onboarding/current-state.md` in chat, with "unknown" for anything it could not see, never a guess.
- **CHECKPOINT 1:** you confirm the note is right (correct it in chat first if it is not).
- After your OK: save the note to `existing_setup.current_state_note` (default `${KIT_HOME}/onboarding/current-state.md`). Nothing else is written.

## Phase 2: config
- Propose: `kit.config.yaml` filled from `kit.config.example.yaml` and the current-state note: your channels (`second_brain.channels`), your timezone (`kit.timezone`), your existing notes folder (`second_brain.home`), names already taken, and `existing_setup.mode: integrate`. `kit.collision_suffix` is applied only on a name clash.
- Show: the whole file in chat, every value explained.
- **CHECKPOINT 2:** you approve the config.
- After your OK: write `${KIT_HOME}/kit.config.yaml`. The file is yours; the kit never overwrites it.

## Phase 3: second brain
- Propose: the folder list. If you already keep notes, `second_brain.home` points there and only the missing channel folders are added; otherwise `${SB_HOME}` is created from `second-brain/`. Your folder layout wins (`second_brain.path_defaults`, `second_brain.roots`); nothing of yours is renamed.
- Propose: links from the marketing folders to your existing campaigns and posts, as a link note or a `second_brain.marketing_links` entry. They are never copied or moved.
- Check: `sb --doctor` over the proposed tree (read-only). Issues in your own files are listed for you to decide; they are never edited.
- Read: the privacy rules of `onboarding/setup-checklist.md`: templates only in `comms/`, no roster data, no photos of children without recorded consent.
- **CHECKPOINT 3:** you approve the folder list and the links.
- After your OK: create the missing folders and seed notes, write the link notes or `marketing_links` entries, run `sb --doctor` and fix kit files only.
- Ask: whether you want a private business profile, and which of your own website and social accounts it may read. It is built only with your OK; without it the templates keep their placeholders.
- Propose: the business profile (name, studios, styles, schedule, prices, channels) from your own website and social accounts: public pages only, never a login or a private message, nothing posted, followed or liked. Pages you saved give a first draft with `python3 tools/business_profile.py draft <folder>` (local files only). The whole profile is shown in chat with "unknown" for anything not found, never a guess; the planner lists checkpoint 3b with nothing to add.
- Propose: its place, `<channel>/private/business-profile.yaml` in your second brain. The profile never goes into git or a public fork: the kit's `.gitignore` covers it, and `python3 tools/business_profile.py check` refuses any commit that holds it, also as the pre-commit hook of your notes repo if you want one. Keys and commands: `second-brain/BUSINESS-PROFILE.md`.
- **CHECKPOINT 3b:** you approve the profile, its place and, if you want it, the pre-commit hook.
- After OK 3b: write the profile to `<channel>/private/business-profile.yaml`, add the `private/` and `business-profile*.yaml` lines to the `.gitignore` of your notes repo if it is a git repo, install the pre-commit hook only if you chose it, and run `python3 tools/business_profile.py check`. From then on the templates read their values from the profile.

## Phase 4: skills
- Propose: `sb-lookup`, `content-calendar-planner` and `comms-template-writer` from `grok-skills/` (names in `skills.sb_lookup`, `skills.content_calendar`, `skills.comms_template`), each marked add (you have nothing similar), extend (you have a similar skill: yours stays, the kit's steps are proposed as additions) or rename with `kit.collision_suffix` (the name is taken).
- Show: the full text of every skill before it is added.
- Propose: the memory facts the kit's skills rely on (`kit_facts` of the current-state note), only those you do not have: a fact you already hold is skipped as a duplicate, a fact that contradicts one of yours is flagged for you and never added.
- **CHECKPOINT 4:** you approve the list, one decision per skill.
- After your OK: add or extend exactly those skills and add the new facts. Your existing skills and facts are never replaced.

## Phase 5: routines
- Propose: the morning brief from `routines/morning-brief.md`. If you have a daily summary routine, the proposal adds the kit's sections to it (`routines.morning_brief.merge_into`); otherwise it creates `routines.morning_brief.name` (default `morning-brief`) at `routines.morning_brief.time` in your timezone. Either way it starts with `routines.morning_brief.enabled: false`.
- **CHECKPOINT 5a:** creating or changing a routine needs your OK.
- After OK 5a: create or extend the routine, still disabled. It never sends, posts or schedules anything; it only reports.
- **CHECKPOINT 5b:** a separate OK to enable it (`routines.morning_brief.enabled: true`). Until then it never runs.
- After OK 5b: enable the routine.

## Phase 6: Claude Code plugins
- Check: Claude Code is installed and signed in with **your** account (`claude --version`). Plugins you already have are skipped.
- Propose: the local marketplace from `accelerator.marketplace_path` (`vendor/accelerator/` in your copy of the kit), `ai-baseline` first, then the plugins you choose (`accelerator.plugins`).
- **CHECKPOINT 6:** you approve the plugin list.
- After your OK: `/plugin marketplace add <path>` and `/plugin install <plugin>@accelerator` for each approved plugin, then `accelerator.enabled: true` in your config.

## Phase 7: Folio and Backlog.md (optional)
- Check: an existing Folio install or its data (`folio.data_dir`) is kept as it is.
- Propose: Folio from `vendor/folio/` (`folio.source`) installed with uv, listening on 127.0.0.1 only; Backlog.md `folio.backlog_version` (1.53.0) from npm with the checksum in `EXTERNAL-DEPENDENCIES.md`, only if you use task files. Never `backlog browser`: its web UI has no authentication.
- **CHECKPOINT 7:** you approve the installs.
- After your OK: install exactly those and set `folio.enabled: true`.

## Phase 8: dev-lead agent (optional)
- Read: `agents/dev-lead/AGENT.md`.
- Propose: if the current-state note lists a dev or coding agent, two options and you choose: **extend** it (add the missing skills and the sizing routine; its name, persona and memory stay; `agents.dev_lead.extend_existing` names it) or **create** `agents.dev_lead.name` under a non-colliding name. Otherwise create `dev-lead` from the template.
- **CHECKPOINT 8a:** creating or extending an agent needs your explicit OK.
- After OK 8a: create or extend the agent and set `agents.dev_lead.enabled: true`. Its sizing routine (every `agents.dev_lead.sizing_interval_hours` hours) is created disabled.
- **CHECKPOINT 8b:** a separate OK to enable the sizing routine.
- After OK 8b: enable the sizing routine.

## Phase 9: queue runner (optional, stays off)
- Show: `runner/TERMS-NOTICE.md` (requires legal confirmation) and the limits in `runner/DESIGN.md`: your own login and box only, no API key, quiet hours in `kit.timezone`.
- Propose: `runner/runner.config.example.json` copied to `runner.config` (default `${KIT_HOME}/runner/router.json`) with `runner.enabled: false` and every path under `${KIT_HOME}/runner/`.
- **CHECKPOINT 9a:** OK to write the config. The runner stays off.
- After OK 9a: write the config file with `runner.enabled: false`. No process is started.
- **CHECKPOINT 9b:** a separate, explicit OK to enable and start it, given only after you have read the terms notice. Without 9b it never runs.
- After OK 9b: set `runner.enabled: true` and start the runner.

## Phase 10: verify
- Check: `sb --doctor` is clean on the kit files; every phase you skipped is listed as skipped.
- Show: a summary of what was added, extended, linked or skipped, and the updated current-state note.
- **CHECKPOINT 10:** you confirm the summary.
- After your OK: save the updated current-state note.

## Conflict resolution (your setup wins)
| Conflict | Default action | Needs your OK to change |
|---|---|---|
| Name collision (agent, skill, routine, folder) | keep yours; the kit's item gets `kit.collision_suffix` or extends yours | yes |
| Overlapping routine (e.g. you already have a morning brief) | merge the kit's sections into yours; never a second routine doing the same job | yes |
| Different folder conventions | the kit adopts yours (paths become config); no renames of your folders | yes |
| Duplicate memory fact | keep yours; add only facts that are new; flag contradictions for you | yes |
| Existing campaign or post | link it from the second brain; never copy or move it | yes |
| Your file has no channel tag | report it; do not edit your file unless you ask | yes |
