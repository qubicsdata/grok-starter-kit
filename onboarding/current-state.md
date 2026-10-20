---
title: "Current state before the starter kit"
type: "note"
id: "N-YYYYMMDD-cur001"
status: "draft"
owner: "<your-name>"
created: "YYYY-MM-DD"
channel: "<one of your channels, e.g. dance-school>"
tags: [<same channel>, onboarding]
links: []
---
<!-- TEMPLATE. The rows below are SYNTHETIC examples showing the shape; your Grok Bot replaces them with what it finds. Saved only after checkpoint 1 of AGENTS.md, to existing_setup.current_state_note. -->

# Current state (read-only discovery, YYYY-MM-DD)

## Agents
| Name | Role | Keep as is? | Kit overlap |
|---|---|---|---|
| example-assistant | primary assistant | yes | none |
| example-social-helper | drafts social posts | yes | overlaps the content-calendar skill: extend, do not replace |

## Routines
| Name | Schedule | Reads | Reports to | Kit overlap |
|---|---|---|---|---|
| example-daily-summary | 08:00 daily | calendar, inbox | chat | overlaps the morning brief: merge |

## Skills
| Name | Purpose | Kit overlap |
|---|---|---|
| example-caption-writer | writes captions | none |

## Memory and preferences (summaries only)
- Example: "prefers British spelling"; "never posts on Sundays".

## Channels and connectors
- Example: calendar, email, one social account (service names only).

## Campaigns, posts and content
| Name | Where it lives | Status | Kit action |
|---|---|---|---|
| example-spring-open-day | `<your existing folder>` | running | link from `dance-school/marketing/campaigns/` |

## File and folder conventions
- Example: drafts in `<your existing folder>/drafts/`, dates as `YYYY-MM-DD`, tags in lower case.

## Unknown / could not see
- <list>

## Proposed kit actions (each needs your OK)
The planner (`python3 tools/kit_plan.py --dry-run`) fills this table from the sections above; every row waits for the checkpoint it names.

| # | Action | Type (add / extend / link / skip) | Checkpoint | Reason |
|---|---|---|---|---|
| 1 | Add `${SB_HOME}` with the two channel folders | add | 3 | none exists |
| 2 | Link example-spring-open-day from `dance-school/marketing/campaigns/` | link | 3 | campaign already lives in your folder |
| 3 | Merge the morning-brief sections into example-daily-summary | extend | 5a | a daily summary routine exists |
