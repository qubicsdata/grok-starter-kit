"""Resolve human or agent references (names, IDs, ID prefixes) to workspace items."""

import re


class ResolveError(Exception):
    def __init__(self, code, message, candidates=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.candidates = candidates or []


def _candidates(items, label):
    result = []
    for item in items:
        candidate = {"id": item["id"], "name": item.get(label, "")}
        if "project" in item:
            candidate["project"] = item["project"]
        result.append(candidate)
    return result


def resolve(items, ref, kind, label="name"):
    ref = (ref or "").strip()
    for item in items:
        if item["id"] == ref:
            return item
    folded = ref.casefold()
    named = [item for item in items if str(item.get(label, "")).casefold() == folded]
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        raise ResolveError("AMBIGUOUS_REFERENCE", f"More than one {kind} is named '{ref}'. Use an ID.", _candidates(named, label))
    if len(ref) >= 4 and re.fullmatch(r"[a-f0-9]+", ref):
        prefixed = [item for item in items if item["id"].startswith(ref)]
        if len(prefixed) == 1:
            return prefixed[0]
        if len(prefixed) > 1:
            raise ResolveError("AMBIGUOUS_REFERENCE", f"More than one {kind} ID starts with '{ref}'.", _candidates(prefixed, label))
    raise ResolveError("NOT_FOUND", f"No {kind} matches '{ref}'.")
