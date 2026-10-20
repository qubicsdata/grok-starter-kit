# Setup checklist: your Grok Bot + Claude Code starter kit

You already use Grok Bot with Claude Code and have a few agents, campaigns and posts running. This kit **adds to what you have; it never replaces it.** Your Grok Bot does the work; you confirm every change at a numbered checkpoint. The full phase list it follows is `AGENTS.md` in the kit; this checklist is the short version with the prompts to send.

## Before you start (prerequisites)
- [ ] Your own Claude account and plan, signed in on your own box. Never a shared login.
- [ ] Claude Code installed and signed in (`claude --version` works).
- [ ] git.
- [ ] Python 3.9 or newer; uv provides it if you have none (and installs Folio later).
- [ ] Node.js LTS, only for npm (Claude Code via npm and Backlog.md). Folio itself does not need Node.
- [ ] The kit folder from the handoff, unpacked on your box (for example `${HOME}/grok-kit`; that path becomes `kit.home`). Exact versions and checksums: `EXTERNAL-DEPENDENCIES.md`.

Not required: ripgrep. The `sb` search tool uses it only when it is already installed and gives the same results without it; the kit never installs it.

Your Grok Bot checks which of these you already have and installs only the missing ones, after your OK.

## Step 1: discovery (read-only, nothing is installed)
- [ ] Send your Grok Bot the message in `onboarding/discovery-prompt.md`. It reads the kit starting with `AGENTS.md`, inventories your agents, routines, skills, memory, channels, campaigns and folder conventions, and fills in `onboarding/current-state.md` without saving it.
- [ ] Read the current-state note. Correct anything wrong. Say OK (checkpoint 1) to save it.

## Step 2 onwards: layering onto your current state
Every phase after the first starts from that note, and every proposal is computed read-only (`python3 tools/kit_plan.py --dry-run`) and shown to you before a checkpoint. The rules:
- marketing folders **link to** your existing campaigns and posts; nothing is imported twice;
- new agents, skills and routines get names that do not collide with yours, or they extend yours;
- memory and routines are merged, never replaced;
- no deletes or renames of your things without your explicit OK;
- routines and the runner are created off and enabled only with a separate OK (checkpoints 5b, 8b, 9b).

### Your first prompts (messages to your Grok Bot)
1. **Config (phase 2).**
   > Fill `kit.config.yaml` from `kit.config.example.yaml` and my current-state note: my channels, my timezone, my existing notes folder and the names already taken. Show me the whole file before you save it.
2. **Second brain (phase 3).**
   > Set up my second brain at `${HOME}/second-brain` (or in my existing notes folder if the discovery note found one) with channels `dance-school` and `other-activities`, using the kit's `second-brain/` template. Add only the folders I don't have yet, link my existing campaigns and posts from `dance-school/marketing/` instead of copying them, and run `sb --doctor`. Show me the plan first.
3. **Search skill (phase 4).**
   > Add the kit's `sb-lookup` skill so you search my second brain by channel before answering. If I already have a similar skill, propose extending it instead. Show me the skill first.
4. **Morning brief (phase 5).**
   > Create a morning-brief routine from `routines/morning-brief.md`: weekdays at 07:30 my time, reading my calendar, second-brain notes changed since yesterday, content due today or tomorrow and drafts waiting for my approval; stay quiet when nothing changed. If I already have a daily summary routine, merge these sections into it instead. Keep it off until I confirm.
5. **This term's classes.**
   > Set up this term's class schedule in `dance-school/classes-schedule/` from the template, with these classes: <list>. No student names.
6. **Content and comms.**
   > Draft a recital announcement and plan an Instagram content calendar for next month, linked to my existing campaign <name>. Then create a parent-comms template for term reminders and a monthly finance summary template (totals only). Drafts only; don't post or send anything.

### Seeded starter folders (added only if missing)
- `dance-school/classes-schedule/`, `dance-school/comms/` (templates only), `dance-school/events-recitals/`, `dance-school/marketing/` (campaigns, social, content calendar), `dance-school/finances/` (summaries only), `dance-school/admin/`
- `other-activities/` (admin notes, marketing)

### First-run config (your channels)
```yaml
kit:
  home: "${HOME}/grok-kit"
  timezone: "<your timezone>"
second_brain:
  home: "${HOME}/second-brain"
  channels: ["dance-school", "other-activities"]
existing_setup:
  mode: "integrate"
```
Your Grok Bot fills the full file from `kit.config.example.yaml` and shows it to you first (checkpoint 2). Every setting is explained in `PARAMETERS.md`.

### How the other pieces fit
- **Your Grok Bot** is your primary assistant: it holds your memory, skills and routines and does the setup.
- **Claude Code plugins** (phase 6; the plugin suite in `vendor/accelerator/`): installed from your own copy of the kit:
  `/plugin marketplace add ${HOME}/grok-kit/vendor/accelerator`, then `/plugin install ai-baseline@accelerator` and, for example, `content-companion@accelerator` for writing. Your Grok Bot or you use them inside Claude Code.
- **Folio** (phase 7, optional, `vendor/folio/`): a local planning board on 127.0.0.1, installed with uv from the kit; Backlog.md 1.53.0 from npm if you use task files. Never run `backlog browser`.
- **Dev-lead agent and queue runner** (phases 8 and 9, optional, off): only if you want code work done. If you already have a coding agent, your Grok Bot proposes extending it. The runner never starts without your separate OK (checkpoint 9b) and runs only on your own login and box (`runner/TERMS-NOTICE.md`).
- **Start with one Grok Bot.** Add more agents later only if you want them.

## Conflicts: your setup wins
| If... | Then... |
|---|---|
| a name already exists | yours stays; the kit's item is renamed (suffix `-kit`, `kit.collision_suffix`) or extends yours |
| you already have a morning brief | the kit's sections are merged into it; no second routine |
| your folders are organised differently | the kit follows your layout; nothing of yours is renamed |
| a memory fact already exists | it is not added twice; contradictions are shown to you |
| any change to your things | your Grok Bot asks first, every time |

## Privacy (requires legal confirmation)
- Your students are mostly minors. **The second brain holds no children's personal data**: no names, health information, photos or contact details. The same goes for prompts to Claude or your Grok Bot.
- Keep the class roster and parent contacts in a **separate, secured system** (with access control and backups). Templates in `comms/` use placeholders only.
- **Photos and social posts:** under GDPR Art. 8 and the rules on parental consent, posting images of children needs recorded consent from the parents. Check consent before any post that shows a child.
- Children's data is a special risk under GDPR (Recital 38). A **DPIA** (data protection impact assessment) may be needed for how you handle it.
- Anything you send to Claude is processed by Anthropic. Check your plan's data-use and privacy settings. The same applies to your Grok Bot's provider.
- Keep backups **encrypted**.
- This section is guidance, not legal advice: **requires legal confirmation.**
