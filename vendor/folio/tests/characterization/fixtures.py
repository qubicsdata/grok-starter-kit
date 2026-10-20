"""Synthetic, fully deterministic workspace data (example.com, invented names, fixed IDs and timestamps)."""

import copy

CLIENT_ID = "c0c0c0c0c0c0c0c0"
PROJECT_ID = "a1b2c3d4e5f60718"
ARCHIVED_ID = "a1b2c3d4e5f60719"
STREAM_ID = "5151515151515151"
STAMP = "2026-09-01T09:00:00Z"

NOTES = (
    "Kick-off agreed with the example.com team.\n\n"
    "## Decision: storage\n"
    "Use SQLite WAL for the routing ledger.\n\n"
    "## Risks\n"
    "DNS cut-over for app.example.com may slip.\n\n"
    "```\n# not a heading inside a fence\n```\n\n"
    "### Vendor call <!-- folio-note:0123456789abcdef kind:decision -->\n"
    "Keep retries bounded to three."
)


def task(task_id, title, status, priority="medium", due_date="", blocker="", workstream_id="", owner="", description=""):
    return {"id": task_id, "title": title, "description": description, "owner": owner, "status": status,
            "priority": priority, "due_date": due_date, "workstream_id": workstream_id, "blocker": blocker,
            "created_at": STAMP, "updated_at": STAMP}


# Fixed "today" is 2026-10-17 (see golden.TODAY); each task is one cell of the attention matrix.
TASKS = [
    task("0000000000000001", "Wait for DNS delegation", "blocked", "high", blocker="Waiting on example.com DNS", owner="avery"),
    task("0000000000000002", "Migrate routing ledger", "in_progress", "urgent", due_date="2026-10-01", workstream_id=STREAM_ID,
         description="Move to SQLite WAL."),
    task("0000000000000003", "Archive old ledger", "done", "low", due_date="2026-09-01"),
    task("0000000000000004", "Write runbook", "backlog", "low"),
    task("0000000000000005", "Review dashboards", "backlog", "medium", due_date="2026-10-17"),
    task("0000000000000006", "Load test", "in_progress", "medium", due_date="2026-11-30", workstream_id=STREAM_ID),
    task("0000000000000007", "Blocked with a future date", "blocked", "low", due_date="2026-12-31", blocker="Vendor contract"),
    task("0000000000000008", "Overdue in the backlog", "backlog", "high", due_date="2026-10-16"),
]


def project():
    return copy.deepcopy({
        "schema_version": 1, "id": PROJECT_ID, "client_id": CLIENT_ID, "name": "Example rollout", "status": "active",
        "description": "Synthetic rollout plan for example.com.", "target_date": "2026-12-01", "notes": NOTES,
        "revision": 7, "created_at": STAMP, "updated_at": STAMP,
        "workstreams": [{"id": STREAM_ID, "name": "Platform", "color": "blue"}],
        "tasks": TASKS, "activity": [],
    })


def state():
    archived = project()
    archived.update(id=ARCHIVED_ID, name="Archived pilot", status="archived",
                    tasks=[task("0000000000000009", "Archived blocked task", "blocked")])
    return {"clients": [{"id": CLIENT_ID, "name": "Example Client"}], "projects": [project(), archived]}
