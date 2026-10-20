"""A stdlib reader for the YAML subset used by the existing-setup case files.

Supported, and nothing more: block mappings (two-space indentation), block
lists of scalars or flow collections (`- x`, `- {a: b}`, `- [a, b]`), flow
mappings and flow sequences (nested; `{}` and `[]`), double- and single-quoted
strings, plain scalars, integers, booleans, null and `#` comments. Keys are
plain or quoted strings. Anchors, tags, multi-line scalars, block mappings
inside a list item and documents other than the first are errors.

The reader is the harness's own: it must not depend on sb's internals.
"""

import re

__all__ = ["CaseYamlError", "load", "load_file"]


class CaseYamlError(ValueError):
    pass


_TRUE = ("true", "True", "TRUE")
_FALSE = ("false", "False", "FALSE")
_NULL = ("null", "Null", "NULL", "~", "")
_INT_RE = re.compile(r"^-?(0|[1-9][0-9]*)$")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "0": "\0"}


def _plain(token):
    token = token.strip()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    if token in _NULL:
        return None
    if _INT_RE.match(token):
        return int(token)
    return token


class _Flow:
    """Parses one flow scalar/collection from `text` starting at `pos`."""

    def __init__(self, text, lineno):
        self.text = text
        self.lineno = lineno

    def error(self, reason):
        return CaseYamlError("line %d: %s" % (self.lineno, reason))

    def skip_ws(self, i):
        while i < len(self.text) and self.text[i] in " \t":
            i += 1
        return i

    def value(self, i, stops):
        i = self.skip_ws(i)
        if i >= len(self.text):
            raise self.error("value expected")
        ch = self.text[i]
        if ch == "{":
            return self.mapping(i + 1)
        if ch == "[":
            return self.sequence(i + 1)
        if ch == '"':
            return self.double(i + 1)
        if ch == "'":
            return self.single(i + 1)
        j = i
        while j < len(self.text) and self.text[j] not in stops:
            if self.text[j] == "#" and (j == 0 or self.text[j - 1] in " \t"):
                break
            j += 1
        return _plain(self.text[i:j]), j

    def double(self, i):
        out = []
        while i < len(self.text):
            ch = self.text[i]
            if ch == '"':
                return "".join(out), i + 1
            if ch == "\\":
                if i + 1 >= len(self.text):
                    break
                esc = self.text[i + 1]
                if esc not in _ESCAPES:
                    raise self.error("unsupported escape")
                out.append(_ESCAPES[esc])
                i += 2
                continue
            out.append(ch)
            i += 1
        raise self.error("unterminated double-quoted string")

    def single(self, i):
        out = []
        while i < len(self.text):
            ch = self.text[i]
            if ch == "'":
                if i + 1 < len(self.text) and self.text[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), i + 1
            out.append(ch)
            i += 1
        raise self.error("unterminated single-quoted string")

    def key(self, i):
        i = self.skip_ws(i)
        if i < len(self.text) and self.text[i] in "\"'":
            if self.text[i] == '"':
                key, i = self.double(i + 1)
            else:
                key, i = self.single(i + 1)
        else:
            j = i
            while j < len(self.text) and self.text[j] not in ":,}":
                j += 1
            key = self.text[i:j].strip()
            i = j
        i = self.skip_ws(i)
        if i >= len(self.text) or self.text[i] != ":":
            raise self.error("':' expected after a flow key")
        if not key:
            raise self.error("empty key")
        return key, i + 1

    def mapping(self, i):
        out = {}
        i = self.skip_ws(i)
        if i < len(self.text) and self.text[i] == "}":
            return out, i + 1
        while True:
            key, i = self.key(i)
            if key in out:
                raise self.error("duplicate key")
            value, i = self.value(i, ",}")
            out[key] = value
            i = self.skip_ws(i)
            if i >= len(self.text):
                raise self.error("unterminated flow mapping")
            if self.text[i] == ",":
                i = self.skip_ws(i + 1)
                if i < len(self.text) and self.text[i] == "}":
                    return out, i + 1
                continue
            if self.text[i] == "}":
                return out, i + 1
            raise self.error("',' or '}' expected")

    def sequence(self, i):
        out = []
        i = self.skip_ws(i)
        if i < len(self.text) and self.text[i] == "]":
            return out, i + 1
        while True:
            value, i = self.value(i, ",]")
            out.append(value)
            i = self.skip_ws(i)
            if i >= len(self.text):
                raise self.error("unterminated flow sequence")
            if self.text[i] == ",":
                i = self.skip_ws(i + 1)
                if i < len(self.text) and self.text[i] == "]":
                    return out, i + 1
                continue
            if self.text[i] == "]":
                return out, i + 1
            raise self.error("',' or ']' expected")

    def whole(self):
        value, i = self.value(0, "")
        i = self.skip_ws(i)
        if i < len(self.text) and not self.text[i] == "#":
            raise self.error("trailing text after the value")
        return value


def _strip_comment(line):
    """Remove a `#` comment that is not inside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _lines(text):
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("---") and n == 1:
            continue
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            raise CaseYamlError("line %d: tabs are not allowed in indentation" % n)
        out.append((n, len(line) - len(line.lstrip(" ")), line.strip()))
    return out


def _split_key(text, lineno):
    flow = _Flow(text, lineno)
    key, i = flow.key(0)
    return key, text[i:].strip()


def _block(lines, i, indent):
    if i >= len(lines):
        raise CaseYamlError("block expected at end of file")
    lineno, ind, text = lines[i]
    if text.startswith("- ") or text == "-":
        return _list(lines, i, ind)
    return _mapping(lines, i, ind)


def _list(lines, i, indent):
    out = []
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent or not (text.startswith("- ") or text == "-"):
            raise CaseYamlError("line %d: list item expected" % lineno)
        rest = text[1:].strip()
        if not rest:
            raise CaseYamlError("line %d: empty list item" % lineno)
        if re.match(r"^[A-Za-z_][^:{}\[\],]*:(\s|$)", rest) and not rest.startswith(("{", "[", '"', "'")):
            raise CaseYamlError("line %d: block mappings inside a list are not supported" % lineno)
        out.append(_Flow(rest, lineno).whole())
        i += 1
    return out, i


def _mapping(lines, i, indent):
    out = {}
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise CaseYamlError("line %d: unexpected indentation" % lineno)
        if text.startswith("- "):
            raise CaseYamlError("line %d: list item where a key was expected" % lineno)
        key, rest = _split_key(text, lineno)
        if key in out:
            raise CaseYamlError("line %d: duplicate key" % lineno)
        if rest:
            out[key] = _Flow(rest, lineno).whole()
            i += 1
            continue
        if i + 1 < len(lines) and lines[i + 1][1] > ind:
            out[key], i = _block(lines, i + 1, lines[i + 1][1])
        elif i + 1 < len(lines) and lines[i + 1][1] == ind and lines[i + 1][2].startswith("- "):
            out[key], i = _list(lines, i + 1, ind)
        else:
            out[key] = None
            i += 1
    return out, i


def load(text):
    """Parse one YAML document (the subset above) into Python data."""
    lines = _lines(text)
    if not lines:
        return {}
    value, i = _block(lines, 0, lines[0][1])
    if i < len(lines):
        raise CaseYamlError("line %d: unexpected indentation" % lines[i][0])
    return value


def load_file(path):
    with open(path, encoding="utf-8") as fh:
        return load(fh.read())
