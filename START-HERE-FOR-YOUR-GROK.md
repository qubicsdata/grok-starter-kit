# Instructions for your Grok Bot: set up the starter kit

Hi Grok. Your user may not be technical, so please do all of the setup yourself, explain each step in plain words, and ask them only simple yes/no questions at the checkpoints.

## 1. Get the kit
Clone the public repo https://github.com/qubicsdata/grok-starter-kit (branch `main`) onto your own computer, not your user's. No GitHub account or login is needed.

## 2. Set it up
- Open `AGENTS.md` and follow its phases in order. Phase 1 only reads what your user already has (agents, campaigns, posts, notes). Don't change anything during phase 1.
- The kit adds to the existing setup and doesn't replace it. Never overwrite, rename or delete anything of your user's without their explicit OK.
- Every phase ends at a numbered checkpoint. Before writing anything, show the proposal from `python3 tools/kit_plan.py --dry-run` in plain words, and wait for a yes.
- Routines and the optional Claude Code queue runner are created switched off. Turn each one on only after a separate yes, and read `runner/TERMS-NOTICE.md` before suggesting the runner.
- Settings and their defaults are in `kit.config.example.yaml` and `PARAMETERS.md`. Prerequisites and the first prompts to send are in `onboarding/setup-checklist.md`.

## 3. Privacy (important)
If your user works with children or other people whose data needs extra care, keep no personal data, health information, photos or contact details about them in the second brain or in prompts. Use a separate, secured system for those. See the privacy section of `onboarding/setup-checklist.md`.

## 4. Before opening anything in Claude Code
`vendor/accelerator/.claude/settings.json` ships Claude Code hooks (SessionStart, Stop, and PreToolUse guards) that run the bundled `tools/hooks` scripts automatically. Open that folder in Claude Code only after you've reviewed those scripts.

## 5. Known gap
`clean_scan` applies `allow=` entries and relaxes matching for terms of 4 characters or fewer, for every terms list. Don't rely on it alone to check client or employer name lists. Use a strict, allow-free check for those until a kit update fixes this. That update is coming.

## 6. When you're done
Tell your user in two or three plain sentences what's now set up, what's still switched off, and what they can ask you to do next.
