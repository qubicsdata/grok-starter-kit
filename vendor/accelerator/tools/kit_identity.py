#!/usr/bin/env python3
"""
kit_identity.py — author, email and homepage of this suite, from the kit config.

The starter kit keeps this suite at ${KIT_HOME}/vendor/accelerator and its
settings in ${KIT_HOME}/kit.config.yaml. Three keys of the `kit:` section feed
the suite:

  kit.author_name   plugin authors, marketplace owner, maintainer lines
  kit.author_email  same places
  kit.homepage      plugin homepages; empty = no homepage and no release check

A key that is absent or empty falls back to PLACEHOLDERS (the values of
kit.config.example.yaml). KIT_HOME comes from the environment, else it is the
folder two levels above this suite.

Used by tools/gen-registry.py (plugin.json files, .claude-plugin/marketplace.json)
and tools/gen-readme.py (README.md, the identity lines in IDENTITY_REFS, the
release-check block of every skills/version-self-check.md). Edits are made in
place: only the identity values change, the rest of each file keeps its layout,
so regenerating with the same config changes nothing.

Not a module to run. Stdlib only, Python 3.9+.
"""

import json
import os
import re
from pathlib import Path

PLACEHOLDERS = {
    "author_name": "<your-name>",
    "author_email": "you@example.com",
    "homepage": "",
}
CONFIG_NAME = "kit.config.yaml"


class ConfigError(Exception):
    """kit.config.yaml cannot be used. Messages name keys and lines, never values."""


class DocError(Exception):
    """A doc or manifest can no longer be edited safely (identity line missing or
    doubled, release-check block missing, invalid JSON). Names the file only."""


# --------------------------------------------------------------------------- #
# kit.config.yaml: the YAML subset the kit writes                              #
# --------------------------------------------------------------------------- #

_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:(?:\s+(.*))?$")
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t"}


def _scalar(rest, lineno):
    """Value of `key: <rest>`: double- or single-quoted, or plain up to ` #`.
    Empty, `~` and `null` give None."""
    rest = rest.strip()
    if rest[:1] in ('"', "'"):
        quote, out, i = rest[0], [], 1
        while True:
            if i >= len(rest):
                raise ConfigError("line %d: unterminated quoted value" % lineno)
            ch = rest[i]
            if quote == '"' and ch == "\\":
                nxt = rest[i + 1:i + 2]
                if nxt not in _ESCAPES:
                    raise ConfigError("line %d: unsupported escape in a quoted value" % lineno)
                out.append(_ESCAPES[nxt])
                i += 2
            elif ch == quote and quote == "'" and rest[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
            elif ch == quote:
                tail = rest[i + 1:].strip()
                if tail and not tail.startswith("#"):
                    raise ConfigError("line %d: text after a quoted value" % lineno)
                return "".join(out)
            else:
                out.append(ch)
                i += 1
    if rest.startswith("#"):
        rest = ""
    rest = re.split(r"\s+#", rest, maxsplit=1)[0].strip()
    if rest[:1] in ("{", "["):
        return rest  # flow collections are kept as text; the identity keys never use them
    return None if rest in ("", "~", "null", "Null", "NULL") else rest


def parse_section(text, section):
    """{key: value} of the direct children of top-level `section:`. Deeper keys
    are skipped (a key with children has the value None)."""
    values, inside, indent = {}, False, None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lead = line[:len(line) - len(line.lstrip())]
        if "\t" in lead:
            raise ConfigError("line %d: tab indentation is not supported" % lineno)
        if not lead:
            match = _KEY_RE.match(stripped)
            inside = bool(match) and match.group(1) == section
            if inside and _scalar(match.group(2) or "", lineno) is not None:
                raise ConfigError("line %d: '%s:' must be a block of indented keys" % (lineno, section))
            indent = None
            continue
        if not inside:
            continue
        if indent is None:
            indent = len(lead)
        if len(lead) > indent:
            continue
        if len(lead) < indent:
            raise ConfigError("line %d: inconsistent indentation under '%s:'" % (lineno, section))
        match = _KEY_RE.match(stripped)
        if not match:
            raise ConfigError("line %d: expected 'key: value' under '%s:'" % (lineno, section))
        key = match.group(1)
        if key in values:
            raise ConfigError("line %d: duplicate key '%s.%s'" % (lineno, section, key))
        values[key] = _scalar(match.group(2) or "", lineno)
    return values


_EMAIL_RE = re.compile(r"^[^\s@()<>\"'`*\\,;|]+@[^\s@()<>\"'`*\\,;|]+$")
_HOMEPAGE_RE = re.compile(r"^https?://[^\s\"'`<>\\|*()]+$")


def _validate(identity, source):
    name = identity["author_name"]
    if name != name.strip() or any(ord(c) < 32 or ord(c) == 127 for c in name) or "`" in name:
        raise ConfigError("%s: kit.author_name must be one line without backticks, "
                          "tabs or surrounding spaces" % source)
    if not _EMAIL_RE.match(identity["author_email"]):
        raise ConfigError("%s: kit.author_email is not a plain address (name@domain)" % source)
    home = identity["homepage"]
    if home and not _HOMEPAGE_RE.match(home):
        raise ConfigError("%s: kit.homepage must be empty or an http(s) URL without spaces" % source)


def kit_home(suite_root, environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("KIT_HOME"):
        return Path(os.path.expanduser(os.path.expandvars(environ["KIT_HOME"])))
    return Path(suite_root).resolve().parent.parent


def load_identity(suite_root, environ=None):
    """{author_name, author_email, homepage} for the suite at suite_root."""
    path = kit_home(suite_root, environ) / CONFIG_NAME
    identity = dict(PLACEHOLDERS)
    source = CONFIG_NAME
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError("%s: cannot be read (%s)" % (CONFIG_NAME, type(exc).__name__))
        try:
            values = parse_section(text, "kit")
        except ConfigError as exc:
            raise ConfigError("%s: %s" % (CONFIG_NAME, exc))
        for key in PLACEHOLDERS:
            value = values.get(key)
            if value:
                identity[key] = value
    else:
        source = "placeholders"
    _validate(identity, source)
    return identity


# --------------------------------------------------------------------------- #
# JSON manifests, edited in place                                              #
# --------------------------------------------------------------------------- #

_WS = re.compile(r"[ \t\n\r]*")
_DECODER = json.JSONDecoder()


class _Member:
    __slots__ = ("lead", "key_start", "value_start", "value_end", "prev_end")

    def __init__(self, lead, key_start, value_start, value_end, prev_end):
        self.lead = lead                # start of the whitespace before the key
        self.key_start = key_start
        self.value_start = value_start
        self.value_end = value_end
        self.prev_end = prev_end        # end of the previous member's value, or None


def _scan(text, pos, path, objects, members_at):
    """Parse the JSON value at pos. objects[path] = [(key, _Member), ...] for
    every object, members_at[path + (key,)] = _Member. Returns the value's end."""
    pos = _WS.match(text, pos).end()
    ch = text[pos:pos + 1]
    if ch == "{":
        pos, members, prev_end = pos + 1, [], None
        while True:
            lead = pos
            pos = _WS.match(text, pos).end()
            if text[pos:pos + 1] == "}" and not members:
                objects[path] = members
                return pos + 1
            if text[pos:pos + 1] != '"':
                raise ValueError("expected a key at offset %d" % pos)
            key_start = pos
            key, pos = json.decoder.scanstring(text, pos + 1)
            pos = _WS.match(text, pos).end()
            if text[pos:pos + 1] != ":":
                raise ValueError("expected ':' at offset %d" % pos)
            value_start = _WS.match(text, pos + 1).end()
            value_end = _scan(text, value_start, path + (key,), objects, members_at)
            member = _Member(lead, key_start, value_start, value_end, prev_end)
            members.append((key, member))
            members_at[path + (key,)] = member
            prev_end = value_end
            pos = _WS.match(text, value_end).end()
            if text[pos:pos + 1] == ",":
                pos += 1
                continue
            if text[pos:pos + 1] == "}":
                objects[path] = members
                return pos + 1
            raise ValueError("expected ',' or '}' at offset %d" % pos)
    if ch == "[":
        pos, index = pos + 1, 0
        pos = _WS.match(text, pos).end()
        if text[pos:pos + 1] == "]":
            return pos + 1
        while True:
            pos = _scan(text, pos, path + (index,), objects, members_at)
            index += 1
            pos = _WS.match(text, pos).end()
            if text[pos:pos + 1] == ",":
                pos += 1
                continue
            if text[pos:pos + 1] == "]":
                return pos + 1
            raise ValueError("expected ',' or ']' at offset %d" % pos)
    _, end = _DECODER.raw_decode(text, pos)
    return end


def _spans(text):
    """(objects, members_at) of _scan for a whole JSON document."""
    objects, members_at = {}, {}
    end = _scan(text, 0, (), objects, members_at)
    if text[end:].strip():
        raise ValueError("extra data after the JSON value")
    return objects, members_at


def _indent_of(text, member):
    """The whitespace that precedes member's key (newline included)."""
    return text[member.lead:member.key_start]


def _render_object(pairs, sep):
    """A JSON object written like its siblings: sep = newline + sibling indent."""
    inner = sep + "  " if "\n" in sep else " "
    close = sep if "\n" in sep else " "
    body = ",".join(inner + json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False) for k, v in pairs)
    return "{" + body + close + "}"


def _set_member(text, obj_path, key, value, after=()):
    """Set obj[key] = value (a str or a list of (key, str) pairs). An existing
    member keeps its place; a new one goes after the last existing key named in
    `after`, else at the end of the object."""
    objects, spans = _spans(text)
    members = objects[obj_path]
    if not members:
        raise ValueError("cannot add '%s' to an empty object" % key)
    found = spans.get(obj_path + (key,))
    if found is not None:
        sep = _indent_of(text, found)
        rendered = (json.dumps(value, ensure_ascii=False) if isinstance(value, str)
                    else _render_object(value, sep))
        return text[:found.value_start] + rendered + text[found.value_end:]
    anchor = members[-1][1]
    for name in after:
        if obj_path + (name,) in spans:
            anchor = spans[obj_path + (name,)]
    sep = _indent_of(text, anchor)
    rendered = (json.dumps(value, ensure_ascii=False) if isinstance(value, str)
                else _render_object(value, sep))
    insert = "," + sep + json.dumps(key) + ": " + rendered
    return text[:anchor.value_end] + insert + text[anchor.value_end:]


def _remove_member(text, obj_path, key):
    objects, spans = _spans(text)
    member = spans.get(obj_path + (key,))
    if member is None:
        return text
    members = objects[obj_path]
    if member.prev_end is not None:
        return text[:member.prev_end] + text[member.value_end:]
    if len(members) > 1:
        return text[:member.key_start] + text[members[1][1].key_start:]
    return text[:member.lead] + text[member.value_end:]


def _set_author(text, obj_path, identity):
    """obj.author.name / .email from identity; other author fields are kept."""
    objects, _ = _spans(text)
    if objects.get(obj_path):
        text = _set_member(text, obj_path, "name", identity["author_name"])
        return _set_member(text, obj_path, "email", identity["author_email"], after=("name",))
    pairs = [("name", identity["author_name"]), ("email", identity["author_email"])]
    return _set_member(text, obj_path[:-1], obj_path[-1], pairs,
                       after=("name", "version", "description"))


def _set_homepage(text, obj_path, homepage):
    if homepage:
        return _set_member(text, obj_path, "homepage", homepage, after=("author",))
    return _remove_member(text, obj_path, "homepage")


def _checked(before, after, expect):
    """Guard: the edited text parses and holds exactly the expected data."""
    data = json.loads(after)
    if data != expect(json.loads(before)):
        raise ValueError("in-place edit did not give the expected manifest")
    return after


def _author_dict(old, identity):
    author = dict(old) if isinstance(old, dict) else {}
    author["name"] = identity["author_name"]
    author["email"] = identity["author_email"]
    return author


def _expect_plugin(data, identity):
    data["author"] = _author_dict(data.get("author"), identity)
    if identity["homepage"]:
        data["homepage"] = identity["homepage"]
    else:
        data.pop("homepage", None)
    return data


def apply_plugin_identity(text, identity):
    """plugin.json text with author and homepage from identity."""
    out = _set_author(text, ("author",), identity)
    out = _set_homepage(out, (), identity["homepage"])
    return _checked(text, out, lambda data: _expect_plugin(data, identity))


def apply_marketplace_identity(text, identity):
    """marketplace.json text: owner, and every plugin entry's author and homepage."""
    count = len(json.loads(text).get("plugins", []))
    out = _set_author(text, ("owner",), identity)
    for index in range(count):
        out = _set_author(out, ("plugins", index, "author"), identity)
        out = _set_homepage(out, ("plugins", index), identity["homepage"])

    def expect(data):
        data["owner"] = _author_dict(data.get("owner"), identity)
        data["plugins"] = [_expect_plugin(entry, identity) for entry in data.get("plugins", [])]
        return data
    return _checked(text, out, expect)


def manifest_updates(suite_root, identity):
    """{path: new text} for every manifest whose text changes."""
    root = Path(suite_root)
    updates = {}
    targets = [(p, apply_plugin_identity) for p in sorted(root.glob("*/.claude-plugin/plugin.json"))]
    market = root / ".claude-plugin" / "marketplace.json"
    if market.is_file():
        targets.append((market, apply_marketplace_identity))
    for path, apply in targets:
        rel = path.relative_to(root).as_posix()
        old = path.read_text(encoding="utf-8")
        try:
            new = apply(old, identity)
        except ValueError as exc:
            raise DocError("%s: %s" % (rel, exc))
        if new != old:
            updates[path] = new
    return updates


# --------------------------------------------------------------------------- #
# Docs: the identity lines and the release-check block                         #
# --------------------------------------------------------------------------- #

_EMAIL = r"[^\s@()<>\"'`*\\,;|]+@[^\s@()<>\"'`*\\,;|]+"
_JSON_STR = r'"(?:[^"\\\n]|\\.)*"'

# Groups named name*/email* take the plain value, jname*/jemail* a JSON string.
IDENTITY_PATTERNS = {
    # "<name> (<email>)" or "[Author: |**Author:** ]<name> — <email>", a whole line
    "maintainer": re.compile(
        r"^(?:(?P<name>[^\n]+) \((?P<email>" + _EMAIL + r")\)"
        r"|(?:\*\*Author:\*\* |Author: )?(?P<name_2>[^\n]+) — (?P<email_2>" + _EMAIL + r"))$",
        re.M),
    # OpenAPI info.contact, named in the rules and shown in the example spec
    "openapi-contact": re.compile(
        r"`contact\.email` \((?P<name>[^\n]+) / (?P<email>" + _EMAIL + r")\)\.$"
        r"|^  contact:\n    name: (?P<name_2>[^\n]+)\n    email: (?P<email_2>" + _EMAIL + r")$",
        re.M),
    # the plugin.json author the converter writes
    "converter-author": re.compile(
        r'^- `author`: `\{"name": (?P<jname>' + _JSON_STR + r'), "email": (?P<jemail>'
        + _JSON_STR + r")\}`\.$",
        re.M),
    # the last line of the audit report
    "report-footer": re.compile(
        r"^\*Generated by [^|\n]+\| (?P<name>[^\n]+) — (?P<email>" + _EMAIL + r")\*$",
        re.M),
}

# (file, pattern, expected matches): the 24 identity refs outside the manifests.
IDENTITY_REFS = [(rel + "/README.md", "maintainer", 1) for rel in (
    "ai-baseline", "api-designer", "compliance-companion", "content-companion",
    "cost-monitor", "data-companion", "dependency-auditor", "frontend-companion",
    "greenfield-project-initializer", "incident-companion", "legacy-modernizer",
    "memory-companion", "observability-companion", "onboarding-guide", "ops-companion",
    "release-manager", "sap-migration-companion", "self-evolution-companion",
    "uiux-companion", "workspace-companion",
)] + [
    ("api-designer/agents/spec-generator.md", "openapi-contact", 2),
    ("assimilator/agents/conformance-converter.md", "converter-author", 1),
    ("dependency-auditor/agents/audit-orchestrator.md", "report-footer", 1),
]


def apply_identity_lines(text, pattern, identity):
    """(new text, number of matches) with every name/email group replaced."""
    values = {
        "name": identity["author_name"],
        "email": identity["author_email"],
        "jname": json.dumps(identity["author_name"], ensure_ascii=False),
        "jemail": json.dumps(identity["author_email"], ensure_ascii=False),
    }
    edits, count = [], 0
    for match in pattern.finditer(text):
        count += 1
        for group, start in ((g, match.start(g)) for g in match.groupdict()):
            if start >= 0:
                edits.append((start, match.end(group), values[group.split("_")[0]]))
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    return text, count


RELEASE_CHECK_BEGIN = "<!-- kit:release-check:begin -->"
RELEASE_CHECK_END = "<!-- kit:release-check:end -->"
RELEASE_CHECK_FILE = "skills/version-self-check.md"
_RELEASE_CHECK_RE = re.compile(re.escape(RELEASE_CHECK_BEGIN) + r"\n.*?" + re.escape(RELEASE_CHECK_END), re.S)
_GITHUB_REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def release_check_body(plugin, homepage):
    """Step 2 of the version self-check, for kit.homepage."""
    if not homepage:
        return (
            "2. **Query for latest version: skipped.** The release check is off: "
            "`kit.homepage` is empty in `kit.config.yaml`, so there is no place to ask. "
            "Do not fetch anything; skip steps 3 and 4 and record `Latest: unknown "
            "(release check off)` and `Status: check disabled` in step 5.\n"
        )
    repo = _GITHUB_REPO_RE.match(homepage)
    if repo:
        fallback = ("`WebFetch https://api.github.com/repos/%s/%s/releases/latest` → extract `tag_name`"
                    % (repo.group(1), repo.group(2)))
    else:
        fallback = "`WebFetch %s` → read the latest published version of `%s`" % (homepage, plugin)
    return (
        "2. **Query for latest version.** Try in order:\n"
        "   - Primary: fetch the accelerator marketplace listing for `%s` "
        "(URL defined in marketplace config — skip if not yet configured)\n"
        "   - Fallback: %s\n" % (plugin, fallback)
    )


def render_release_check(text, plugin, homepage):
    blocks = _RELEASE_CHECK_RE.findall(text)
    if len(blocks) != 1:
        raise DocError("expected one release-check block, found %d" % len(blocks))
    body = RELEASE_CHECK_BEGIN + "\n" + release_check_body(plugin, homepage) + RELEASE_CHECK_END
    return _RELEASE_CHECK_RE.sub(lambda _: body, text)


def identity_doc_updates(suite_root, identity):
    """{path: new text} for every doc whose text changes; DocError if a doc no
    longer has the expected number of identity lines or release-check blocks.
    Refs of a plugin whose folder was removed are skipped."""
    root = Path(suite_root)
    updates, texts = {}, {}
    for rel, key, expected in IDENTITY_REFS:
        path = root / rel
        if not (root / rel.split("/", 1)[0]).is_dir():
            continue
        if not path.is_file():
            raise DocError("%s: file missing" % rel)
        text = texts.get(path, path.read_text(encoding="utf-8"))
        text, count = apply_identity_lines(text, IDENTITY_PATTERNS[key], identity)
        if count != expected:
            raise DocError("%s: expected %d %s line(s), found %d" % (rel, expected, key, count))
        texts[path] = text
    for path in sorted(root.glob("*/" + RELEASE_CHECK_FILE)):
        rel = path.relative_to(root).as_posix()
        text = texts.get(path, path.read_text(encoding="utf-8"))
        try:
            texts[path] = render_release_check(text, rel.split("/", 1)[0], identity["homepage"])
        except DocError as exc:
            raise DocError("%s: %s" % (rel, exc))
    for path, text in texts.items():
        if text != path.read_text(encoding="utf-8"):
            updates[path] = text
    return updates


def write_updates(updates):
    for path, text in sorted(updates.items()):
        Path(path).write_text(text, encoding="utf-8")
