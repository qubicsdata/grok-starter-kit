#!/usr/bin/env python3
"""Check downloaded artifacts against the kit's pinned checksums.

Usage: python3 tools/verify_pins.py [--pins PATH] [--release] [--list]
       python3 tools/verify_pins.py [--pins PATH] [--release] NAME FILE

Without NAME FILE the pins file (default: tools/pins.json next to this script)
is checked: every entry well formed, every digest well formed for its algo.
A placeholder (empty, null, `<...>`, TODO/TBD) on a required pin is a warning
in dev mode and an error with --release; optional pins may have no digest.
With NAME FILE the pins file is checked the same way, then FILE is hashed and
compared with pin NAME. Digests are hex (`<64 or 128 hex digits>`) or SRI
(`sha256-<base64>` / `sha512-<base64>`), as written in the pins file.

Nothing is downloaded: the script only reads the pins file and FILE.

Output: `WARN <pin>: ...` / `ERROR <pin>: ...` lines, then either
`RESULT: PASS|FAIL (<n> pins, <n> required, <n> warnings, <n> errors)` or,
with NAME FILE, `OK <pin> ...` / `MISMATCH <pin> ...`.
Exit codes: 0 = all good; 1 = errors in the pins file, a mismatch, or a pin
with no digest to compare; 2 = bad command line, unreadable pins file or
FILE, unknown pin. Stdlib only, Python 3.9+.
"""

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import sys
from collections import namedtuple

DEFAULT_PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pins.json")

SCHEMA_VERSION = 1
FIELDS = ("name", "version", "platform", "url", "algo", "digest", "required")
# Fields a required pin must carry as real values (not placeholders).
PINNED_FIELDS = ("version", "platform", "url", "algo", "digest")
ALGOS = {"sha256": 32, "sha512": 64}
FORMS = ("hex", "sri")

NAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")
HEX_RE = re.compile(r"[0-9a-fA-F]+")
BASE64_RE = re.compile(r"[A-Za-z0-9+/]+={0,2}")
PLACEHOLDER_RE = re.compile(r"<[^<>]*>")
PLACEHOLDER_WORDS = ("todo", "tbd", "fixme", "placeholder", "pinned-at-build")

READ_CHUNK = 1 << 20

Report = namedtuple("Report", "pins required warnings errors")


def is_placeholder(value):
    """True for a value that is not pinned yet: None, blank, `<...>`, TODO and kin."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip()
    return not text or bool(PLACEHOLDER_RE.search(text)) or text.lower() in PLACEHOLDER_WORDS


def digest_form(digest):
    return "sri" if "-" in digest else "hex"


def parse_digest(algo, digest):
    """Return the raw digest bytes of a hex or SRI digest; ValueError if malformed."""
    if algo not in ALGOS:
        raise ValueError("unsupported algo (use %s)" % " or ".join(sorted(ALGOS)))
    if not isinstance(digest, str):
        raise ValueError("digest is not a string")
    size = ALGOS[algo]
    if digest_form(digest) == "sri":
        prefix, encoded = digest.split("-", 1)
        if prefix != algo:
            raise ValueError("SRI prefix %r does not match algo %s" % (prefix, algo))
        if not BASE64_RE.fullmatch(encoded) or len(encoded) % 4:
            raise ValueError("SRI digest is not padded base64")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("SRI digest is not padded base64")
        if len(raw) != size:
            raise ValueError("%s SRI digest decodes to %d bytes, not %d" % (algo, len(raw), size))
        return raw
    if not HEX_RE.fullmatch(digest) or len(digest) != 2 * size:
        raise ValueError("%s hex digest needs exactly %d hex digits" % (algo, 2 * size))
    return bytes.fromhex(digest)


def format_digest(algo, raw, form):
    if form == "sri":
        return "%s-%s" % (algo, base64.b64encode(raw).decode("ascii"))
    return raw.hex()


def _check_entry(entry, label, release, warn, error):
    for field in FIELDS:
        if field not in entry:
            error(label, "missing key %r" % field)
    if any(field not in entry for field in FIELDS):
        return
    required = entry["required"]
    if not isinstance(required, bool):
        error(label, "required must be true or false")
        return
    if required:
        for field in PINNED_FIELDS:
            if is_placeholder(entry[field]):
                if release:
                    error(label, "placeholder %s on a required pin" % field)
                else:
                    warn(label, "placeholder %s on a required pin (--release fails)" % field)
    for field in ("version", "platform"):
        value = entry[field]
        if not is_placeholder(value) and not isinstance(value, str):
            error(label, "%s must be a string" % field)
    url = entry["url"]
    if not is_placeholder(url) and not (isinstance(url, str) and url.startswith("https://")):
        error(label, "url must start with https://")
    algo, digest = entry["algo"], entry["digest"]
    if not is_placeholder(algo) and algo not in ALGOS:
        error(label, "unsupported algo (use %s)" % " or ".join(sorted(ALGOS)))
        return
    if is_placeholder(digest):
        return
    if is_placeholder(algo):
        error(label, "digest given without an algo")
        return
    try:
        parse_digest(algo, digest)
    except ValueError as exc:
        error(label, "malformed digest: %s" % exc)
        return
    form = entry.get("form")
    if form is not None and form != digest_form(digest):
        error(label, "form %r does not match the digest (%s)" % (form, digest_form(digest)))
    size = entry.get("size")
    if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
        error(label, "size must be a non-negative integer")


def check_pins(data, release=False):
    """Validate a loaded pins file; return a Report of (label, message) lists."""
    warnings, errors = [], []

    def warn(label, message):
        warnings.append((label, message))

    def error(label, message):
        errors.append((label, message))

    if not isinstance(data, dict):
        error("pins file", "top level must be an object")
        return Report(0, 0, warnings, errors)
    if data.get("schema") != SCHEMA_VERSION:
        error("pins file", "schema must be %d" % SCHEMA_VERSION)
    pins = data.get("pins")
    if not isinstance(pins, list) or not pins:
        error("pins file", "pins must be a non-empty list")
        return Report(0, 0, warnings, errors)

    seen = set()
    required = 0
    for index, entry in enumerate(pins):
        label = "#%d" % (index + 1)
        if not isinstance(entry, dict):
            error(label, "entry is not an object")
            continue
        name = entry.get("name")
        if isinstance(name, str) and NAME_RE.fullmatch(name):
            label = name
            if name in seen:
                error(label, "duplicate pin name")
            seen.add(name)
        elif "name" in entry:
            error(label, "name must be lowercase letters, digits, '.', '_' or '-'")
        if entry.get("required") is True:
            required += 1
        _check_entry(entry, label, release, warn, error)
    return Report(len(pins), required, warnings, errors)


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def result_line(report):
    return "RESULT: %s (%s, %d required, %s, %s)" % (
        "FAIL" if report.errors else "PASS",
        _plural(report.pins, "pin"),
        report.required,
        _plural(len(report.warnings), "warning"),
        _plural(len(report.errors), "error"),
    )


def hash_file(path, algo):
    digest = hashlib.new(algo)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(READ_CHUNK), b""):
            digest.update(chunk)
    return digest.digest()


def find_pin(data, name):
    pins = data.get("pins") if isinstance(data, dict) else None
    for entry in pins if isinstance(pins, list) else []:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def verify_artifact(entry, path, out):
    """Compare the file at path with the pin; return the exit code."""
    label = " ".join(str(entry[key] or "-") for key in ("name", "version", "platform"))
    if is_placeholder(entry["digest"]):
        print("NODIGEST %s: the pin has no digest to compare against" % label, file=out)
        return 1
    algo, digest = entry["algo"], entry["digest"]
    expected = parse_digest(algo, digest)
    actual = hash_file(path, algo)
    if hmac.compare_digest(expected, actual):
        print("OK %s: %s matches" % (label, algo), file=out)
        return 0
    form = digest_form(digest)
    print(
        "MISMATCH %s: expected %s, got %s"
        % (label, format_digest(algo, expected, form), format_digest(algo, actual, form)),
        file=out,
    )
    return 1


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="verify_pins.py",
        description="Check the kit's pinned checksums, or a downloaded file against its pin. "
        "Nothing is downloaded.",
    )
    parser.add_argument("name", nargs="?", metavar="NAME", help="pin name (see --list)")
    parser.add_argument("file", nargs="?", metavar="FILE", help="downloaded file to check against pin NAME")
    parser.add_argument("--pins", metavar="PATH", default=DEFAULT_PINS, help="pins file (default: tools/pins.json)")
    parser.add_argument(
        "--release",
        action="store_true",
        help="release mode: a placeholder on a required pin is an error, not a warning",
    )
    parser.add_argument("--list", action="store_true", help="list the pins")
    args = parser.parse_args(argv)
    if args.name is not None and args.file is None:
        parser.error("NAME needs a FILE to check")
    if args.file is not None and args.list:
        parser.error("--list takes no NAME FILE")
    return args


def load_pins(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def print_list(data, out):
    for entry in data.get("pins", []):
        if not isinstance(entry, dict):
            continue
        print(
            "%-34s %-10s %-18s %-8s %s"
            % (
                entry.get("name"),
                entry.get("version") or "-",
                entry.get("platform") or "-",
                "required" if entry.get("required") is True else "optional",
                entry.get("algo") if not is_placeholder(entry.get("digest")) else "no digest",
            ),
            file=out,
        )


def main(argv=None, out=None, err=None):
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        data = load_pins(args.pins)
    except OSError as exc:
        print("verify_pins: cannot read the pins file: %s" % (exc.strerror or type(exc).__name__), file=err)
        return 2
    except ValueError as exc:
        print("verify_pins: the pins file is not valid JSON: %s" % exc, file=err)
        return 2

    entry = None
    if args.name is not None:
        entry = find_pin(data, args.name)
        if entry is None:
            print("verify_pins: unknown pin %r (see --list)" % args.name, file=err)
            return 2
        if not os.path.isfile(args.file):
            print("verify_pins: not a file: %s" % args.file, file=err)
            return 2

    report = check_pins(data, release=args.release)
    for label, message in report.warnings:
        print("WARN %s: %s" % (label, message), file=out)
    for label, message in report.errors:
        print("ERROR %s: %s" % (label, message), file=out)

    if entry is None:
        if args.list:
            print_list(data, out)
        print(result_line(report), file=out)
        return 1 if report.errors else 0

    if report.errors:
        print(result_line(report), file=out)
        print("verify_pins: fix the pins file before checking a file against it", file=err)
        return 1
    try:
        return verify_artifact(entry, args.file, out)
    except OSError as exc:
        print("verify_pins: cannot read %s: %s" % (args.file, exc.strerror or type(exc).__name__), file=err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
