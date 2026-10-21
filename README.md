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
| `second-brain/` | notes template (`dance-school`, `other-activities`), ROUTER.md, doctor rules, `sb`; the dance-school templates are placeholders only, and `BUSINESS-PROFILE.md` lists the keys they read from your private business profile |
| `tools/business_profile.py` | the private business profile: a draft from pages saved from your own site, template filling, and the refuse-to-commit check (also as a pre-commit hook) |
| `grok-skills/`, `routines/` | starter skills and the morning brief |
| `agents/dev-lead/` | optional dev-lead agent |
| `runner/` | optional queue runner (off by default; read `TERMS-NOTICE.md`) |
| `vendor/` | the plugin suite and the planning UI |
| `EXTERNAL-DEPENDENCIES.md`, `VENDORED.md`, `LICENSE`, `NOTICE` | what is downloaded, what is included, licenses |
| `tests/fixtures/existing-setup/` | synthetic "already set up" cases the kit must not overwrite |
| `tests/overwrite/`, `tools/KIT-PLAN-SPEC.md` | the harness that applies the planner to those cases and proves nothing of yours changes; the planner's contract |

How setup runs: ten phases, each with a numbered checkpoint before anything is written (`AGENTS.md`). The proposal shown at a checkpoint is computed read-only by `python3 tools/kit_plan.py --dry-run`; routines and the runner are created off and enabled only with a separate OK. Python 3.9 or newer and git are all the second brain needs; ripgrep is optional and never installed by the kit.

Privacy: for adults and children alike, students' personal data stays out of the second brain and prompts. If you work with children (minors), keep no children's personal data, health information, photos or contact details in the second brain or in prompts; use a separate secured roster, and show no names or faces of minors without a guardian's written consent. Marketing is drafts only: a human approves every post. See the privacy section of the setup checklist (requires legal confirmation).

Business profile: at checkpoint 3b, and only with your OK, your Grok Bot can build a private profile of your school (name, studios, styles, schedule, prices, channels) from your own website and social accounts; the templates read their values from it. The profile never goes into git or a public fork: it lives in a `private/` folder of your second brain, the kit's `.gitignore` covers it, and `python3 tools/business_profile.py check` refuses any commit that holds it (`second-brain/BUSINESS-PROFILE.md`).

## Release gate

The kit's own checks (`python3 tools/ci_local.py --release`, see `tools/README.md`) are not the final release gate. The final release gate is external to the kit: the client/employer check is the signed `name_scan_counts` run on the release candidate. The kit has no internal client/employer coverage: `ci_local` does not check that class, and none of its steps stands in for that run.

## Known gaps

The name-scanner gap noted in the first release is fixed: client and employer lists go in `--client-terms-file`, which is strict and ignores `allow=`.
