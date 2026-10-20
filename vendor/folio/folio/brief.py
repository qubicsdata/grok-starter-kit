"""Query-aware, bounded planning context and addressable authoritative sources."""
import json
import re
from datetime import date

from .core import AppError
from .notes import TRUST, digest, sections


def source_records(project):
    streams = {s["id"]: s["name"] for s in project["workstreams"]}
    records = [{"source": f"project:{project['id']}", "kind": "project", "title": project["name"],
                "text": f"{project['name']}\nStatus: {project['status']}\nTarget: {project['target_date'] or 'unscheduled'}\n{project['description']}"}]
    records.extend({key: s[key] for key in ("source", "kind", "title", "text")} for s in sections(project))
    records.extend({"source": f"task:{t['id']}", "kind": "task", "title": t["title"],
                    "text": f"{t['title']}\n{t['status']} · {t['priority']} · {streams.get(t['workstream_id'], 'Unassigned')}\nOwner: {t['owner'] or 'unassigned'} · Due: {t['due_date'] or 'unscheduled'}\n{t['description']}" + (f"\nBlocker: {t['blocker']}" if t["blocker"] else "")}
                   for t in project["tasks"])
    return [{**record, "hash": digest(record["text"]), "revision": project["revision"],
             "total_chars": len(record["text"]), "trust": TRUST} for record in records]


def query_terms(query):
    return list(dict.fromkeys(re.findall(r"\w+", query.casefold())))


def excerpt(record, budget, terms=()):
    """Choose the matching window even when it occurs near the end of a large note."""
    full = record["text"]
    folded = full.casefold()
    positions = [folded.find(term) for term in terms if term in folded]
    first = 0
    if positions:
        # casefold can expand characters (ß -> ss); keep paging offsets in source code points.
        folded_offset, consumed = min(positions), 0
        for index, character in enumerate(full):
            consumed += len(character.casefold())
            if consumed > folded_offset:
                first = index
                break
    offset = max(0, first - min(100, budget // 4)) if positions and len(full) > budget else 0
    offset = min(offset, max(0, len(full) - budget))
    text = full[offset:offset + budget]
    return {**record, "text": text, "offset": offset, "truncated": offset > 0 or offset + len(text) < len(full)}


def brief_for_project(project, query="", max_chars=12000):
    if not isinstance(query, str) or len(query) > 1000 or type(max_chars) is not int or not 500 <= max_chars <= 40000:
        raise AppError("Use a query of at most 1000 characters and a budget of 500–40000 characters.")
    terms, records = query_terms(query), source_records(project)
    tasks = {f"task:{task['id']}": task for task in project["tasks"]}
    today = date.today().isoformat()
    def rank(item):
        index, record = item
        text = (record["title"] + " " + record["text"]).casefold()
        matches = sum(term in text for term in terms)
        task = tasks.get(record["source"])
        attention = task and (task["status"] == "blocked" or (task["status"] != "done" and task["due_date"] and task["due_date"] < today))
        return (-matches, -int(record["kind"] == "decision"), -int(bool(attention)),
                int(bool(task and task["status"] == "done")),
                {"urgent": 0, "high": 1, "medium": 2, "low": 3}[task["priority"]] if task else 0,
                task["due_date"] or "9999" if task else "9999",
                -index if record["kind"] in ("note", "decision") else index)
    candidates = sorted(enumerate(records[1:]), key=rank)
    if terms:
        candidates = [(i, r) for i, r in candidates if any(term in (r["title"] + " " + r["text"]).casefold() for term in terms)]
    selected = [excerpt(records[0], max_chars // 4, terms)]
    remaining = max_chars - len(selected[0]["text"])
    for _, record in candidates:
        if remaining <= 0:
            break
        selected.append(excerpt(record, min(remaining, max(200, max_chars // 3)), terms))
        remaining -= len(selected[-1]["text"])
    canonical = json.dumps({key: value for key, value in project.items() if key != "planning_sources"}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    omitted = len(candidates) + 1 - len(selected)
    return {"project_id": project["id"], "revision": project["revision"], "hash": digest(canonical),
            "trust": TRUST, "query": query, "records": selected, "total_tasks": len(project["tasks"]),
            "matching_tasks": sum(r["kind"] == "task" for _, r in candidates), "total_sources": len(records),
            "omitted_sources": omitted, "returned_chars": max_chars - remaining,
            "truncated": omitted > 0 or any(r["truncated"] for r in selected)}


def project_brief(store, project_id, query="", max_chars=12000):
    with store.lock:
        return brief_for_project(store.project(project_id), query, max_chars)


def read_source(store, project_id, source_id, offset=0, max_chars=12000, expected_hash=None):
    if not isinstance(source_id, str) or type(offset) is not int or offset < 0 or type(max_chars) is not int or not 1 <= max_chars <= 40000:
        raise AppError("Use a source identifier, a non-negative offset and a budget of 1–40000 characters.")
    if expected_hash is not None and (not isinstance(expected_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_hash)):
        raise AppError("Invalid source hash.")
    with store.lock:
        project = store.project(project_id)
        records = source_records(project)
        records.append({"source": f"project:{project_id}:notes", "kind": "notes", "title": "All project notes",
                        "text": project["notes"], "hash": digest(project["notes"]), "revision": project["revision"], "total_chars": len(project["notes"]), "trust": TRUST})
        record = next((record for record in records if record["source"] == source_id), None)
        if record is None:
            raise AppError("Planning source not found in this project.", 404, "NOT_FOUND")
        if expected_hash is not None and expected_hash != record["hash"]:
            raise AppError("This source changed. Retrieve a current brief before reading it.", 409, "SOURCE_CHANGED")
        if offset > len(record["text"]):
            raise AppError("Offset is beyond the end of this source.")
        text = record["text"][offset:offset + max_chars]
        next_offset = offset + len(text) if offset + len(text) < len(record["text"]) else None
        return {**record, "source_id": source_id, "text": text, "offset": offset, "next_offset": next_offset,
                "truncated": offset > 0 or next_offset is not None}
