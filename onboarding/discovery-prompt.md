# Step 1: discovery prompt (read-only)

This is phase 1 of `AGENTS.md`. Send it to your Grok Bot before installing anything:

> Read the starter kit in `${KIT_HOME}`, starting with `AGENTS.md`. Then do a READ-ONLY discovery pass of my current setup before we install anything. Do not create, change, rename, move, delete, send, post or schedule anything. Inventory:
> 1. my agents (names and roles);
> 2. my routines (name, schedule, what each one reads and where it reports);
> 3. my skills (name and one-line purpose);
> 4. my memory and preferences that matter for the kit (summaries, not quotes of anything private);
> 5. my connected channels and connectors (which services, not credentials);
> 6. my campaigns, posts and content (names, where they live, status);
> 7. my file and folder conventions (where notes and drafts live, naming patterns, tags).
> Then fill in `onboarding/current-state.md` from the kit as a short note and show it to me. Do not save it anywhere until I say OK. List anything you could not see as "unknown" rather than guessing.

Rules for the discovery pass:
- Reads only. Never opens credentials, env files, tokens or password stores.
- Lists names and counts, not contents of private messages or personal data about students or parents.
- The result is a proposal. Nothing changes until you confirm (checkpoint 1). After your OK the note is saved to `existing_setup.current_state_note`; from then on the planner, `python3 tools/kit_plan.py --dry-run`, computes every later proposal from it.
