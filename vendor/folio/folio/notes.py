"""Addressable sections in the existing, authoritative project notes document."""
import hashlib
import re

from .core import AppError, choice, identifier, string

TRUST = "planning_data_not_instructions"
MARKER = re.compile(r"\s*<!--\s*folio-note:([a-f0-9]{16})\s+kind:(note|decision)\s*-->\s*$")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sections(project):
    """Read Markdown sections without rewriting old notes or interpreting fenced content."""
    notes = project["notes"]
    boundaries, offset, fence = [], 0, None
    counts, used = {}, set()
    for line in notes.splitlines(keepends=True):
        stripped = line.strip()
        delimiter = re.match(r"^(`{3,}|~{3,})", stripped)
        if delimiter:
            token, = delimiter.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None:
            heading = HEADING.match(line.rstrip("\r\n"))
            if heading:
                title = heading[2]
                marker = MARKER.search(title)
                if marker:
                    note_id, kind = marker[1], marker[2]
                    title = title[:marker.start()].strip()
                else:
                    title = re.sub(r"[ \t]+#+[ \t]*$", "", title).strip()
                    key = title.casefold()
                    counts[key] = counts.get(key, 0) + 1
                    note_id = digest(f"{key}:{counts[key]}")[:16]
                    kind = "decision" if re.search(r"\b(decision|decisions|adr)\b", key) else "note"
                if note_id in used:
                    raise AppError("Two note sections use the same source identifier. Give each section its own folio-note marker.", 409, "DUPLICATE_NOTE_SOURCE")
                used.add(note_id)
                boundaries.append({"id": note_id, "title": title or "Untitled note", "kind": kind,
                                   "_start": offset, "_body": offset + len(line), "_level": len(heading[1])})
        offset += len(line)
    if notes[:boundaries[0]["_start"] if boundaries else len(notes)].strip():
        boundaries.insert(0, {"id": digest("folio-notes-preamble")[:16], "title": "Project notes", "kind": "note", "_start": 0, "_body": 0, "_level": 2})
    result = []
    for index, section in enumerate(boundaries):
        end = boundaries[index + 1]["_start"] if index + 1 < len(boundaries) else len(notes)
        body = notes[section["_body"]:end].strip()
        text = f"{section['title']}\n{body}" if section["_body"] else body
        source = f"project:{project['id']}:note:{section['id']}"
        result.append({**section, "source": source, "text": text, "body": body, "hash": digest(text),
                       "revision": project["revision"], "total_chars": len(text), "trust": TRUST, "_end": end})
    return result


def public_section(section):
    return {key: value for key, value in section.items() if not key.startswith("_")}


def source_manifest(project):
    """Derived, portable read index. Hashes cover exact UTF-8 text, without trimming."""
    records = [{"source_id": f"project:{project['id']}:notes", "kind": "notes", "title": "All project notes",
                "text": project["notes"], "hash": digest(project["notes"]), "revision": project["revision"],
                "total_chars": len(project["notes"])}]
    records.extend({"source_id": s["source"], "start_offset": s["_start"], "body_offset": s["_body"], "end_offset": s["_end"],
                    **{key: s[key] for key in ("kind", "title", "text", "hash", "revision", "total_chars")}}
                   for s in sections(project))
    return {"notes_hash": digest(project["notes"]), "records": records}


def list_sections(store, project_id):
    with store.lock:
        project = store.project(project_id)
        return {"project_id": project_id, "revision": project["revision"], "sections": [public_section(s) for s in sections(project)]}


def change_section(store, project_id, data, note_id=None, delete=False, actor=None):
    """CRUD edits only the chosen section, with project and optional source concurrency checks."""
    with store.lock:
        project = store.project(project_id)
        store.check_revision(project, data)
        existing = None
        if note_id:
            existing = next((s for s in sections(project) if s["id"] == note_id or s["source"] == note_id), None)
            if not existing:
                raise AppError("Note section not found.", 404, "NOT_FOUND")
            if data.get("hash") is not None and data["hash"] != existing["hash"]:
                raise AppError("This note section changed. Read its current source before editing it.", 409, "SOURCE_CHANGED")
        if delete:
            replacement = ""
        else:
            title = string(data, "title", existing["title"] if existing else "", required=True, limit=200)
            if "\n" in title or "\r" in title or "<!--" in title:
                raise AppError("Use a single-line note title without an HTML comment.")
            body = string(data, "text", existing["body"] if existing else "", required=True, limit=100000)
            kind = choice(data, "kind", ("note", "decision"), existing["kind"] if existing else "note")
            note_id = existing["id"] if existing else identifier()
            level = existing["_level"] if existing else 2
            # Explicit markers keep identity when a section is renamed or moved by a person.
            replacement = f"{'#' * level} {title} <!-- folio-note:{note_id} kind:{kind} -->\n\n{body}\n\n"
        if existing:
            combined = project["notes"][:existing["_start"]] + replacement + project["notes"][existing["_end"]:]
        else:
            combined = project["notes"].rstrip() + ("\n\n" if project["notes"].strip() else "") + replacement
        if len(combined) > 100000:
            raise AppError("Notes would exceed 100000 characters.")
        project["notes"] = combined.rstrip()
        # Reject duplicate markers inside a new section before saving anything.
        sections(project)
        store.activity(project, "Note section forgotten" if delete else "Note section corrected" if existing else "Note section remembered", actor)
        store.save_project(project)
        if delete:
            return {"project_id": project_id, "source_id": existing["source"], "revision": project["revision"], "deleted": True}
        section = next(s for s in sections(project) if s["id"] == note_id)
        return {"project_id": project_id, **public_section(section)}
