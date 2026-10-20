# Starter kit for a Grok Bot + Claude Code setup

A self-contained kit that your Grok Bot layers onto your existing setup: a second brain with channel isolation, a marketing starter, three skills, a morning-brief routine, an optional dev-lead agent, an optional Claude Code queue runner, a Claude Code plugin suite and a local planning UI.

**Grok Bot: start with `START-HERE-FOR-YOUR-GROK.md`.**

**Integrate, don't replace.** Start with `AGENTS.md`: phase 1 is a read-only look at what you already have. Nothing of yours is overwritten, renamed or deleted without your OK.

| Path | What |
|---|---|
| `AGENTS.md` | the setup phases and checkpoints your Grok Bot follows |
| `onboarding/` | the read-only discovery prompt and the current-state template |
| `onboarding/setup-checklist.md` | prerequisites, the first prompts to send, the privacy section |
| `kit.config.example.yaml`, `PARAMETERS.md` | every setting and its default |
| `second-brain/` | notes template (`dance-school`, `other-activities`), ROUTER.md, doctor rules, `sb` |
| `grok-skills/`, `routines/` | starter skills and the morning brief |
| `agents/dev-lead/` | optional dev-lead agent |
| `runner/` | optional queue runner (off by default; read `TERMS-NOTICE.md`) |
| `vendor/` | the plugin suite and the planning UI |
| `EXTERNAL-DEPENDENCIES.md`, `VENDORED.md`, `LICENSE`, `NOTICE` | what is downloaded, what is included, licenses |
| `tests/fixtures/existing-setup/` | synthetic "already set up" cases the kit must not overwrite |
| `tests/overwrite/`, `tools/KIT-PLAN-SPEC.md` | the harness that applies the planner to those cases and proves nothing of yours changes; the planner's contract |

How setup runs: ten phases, each with a numbered checkpoint before anything is written (`AGENTS.md`). The proposal shown at a checkpoint is computed read-only by `python3 tools/kit_plan.py --dry-run`; routines and the runner are created off and enabled only with a separate OK. Python 3.9 or newer and git are all the second brain needs; ripgrep is optional and never installed by the kit.

Privacy: students are mostly minors. Keep no children's personal data, health information, photos or contact details in the second brain or in prompts; use a separate secured roster. See the privacy section of the setup checklist (requires legal confirmation).

## Release gate

The kit's own checks (`python3 tools/ci_local.py --release`, see `tools/README.md`) are not the final release gate. The final release gate is external to the kit: the client/employer check is the signed `name_scan_counts` run on the release candidate. The kit has no internal client/employer coverage: `ci_local` does not check that class, and none of its steps stands in for that run.

## Known gaps

**Known gap (name scanner).** `clean_scan` applies `allow=` entries and relaxes matching for terms of 4 characters or fewer, for every terms list. Do not rely on it alone to check client or employer name lists; use a strict, allow-free check for those until a kit update fixes this.
