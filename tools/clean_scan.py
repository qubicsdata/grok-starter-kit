#!/usr/bin/env python3
"""Kit clean-data scan: counts owner-data findings in a tree, never shows them.

Usage:
    python3 tools/clean_scan.py FOLDER [FOLDER ...]
        [--terms-file PATH] [--history --allowed-identity "Name <email>"]
        [--gitleaks PATH] [--trufflehog PATH]

Output (stdout): ONLY these line shapes, nothing else, ever:
    <CODE> <count>      one per finding code with a non-zero count (counts are
                        matches; BIDI and CTRL count decoded characters, never
                        bytes or lines)
    BINARY <n>          image files known by their magic bytes (PNG, JPEG,
                        GIF, WebP) that were not content-scanned; not a
                        finding, not part of TOTAL; absent when 0
    SKIP <what>         a check that did not run: gitleaks, trufflehog, terms
                        (no --terms-file) and binary (a NUL-bearing file that
                        is not a known image was not content-scanned; path
                        rules still apply)
    TOTAL <n>           sum of every finding code line; always the last line
No matched text, file name, path, line number or commit sha is printed, on
stdout or stderr, on any exit path. Error messages are generic.

Exit codes: 0 = TOTAL 0, 1 = findings, 2 = usage error (no folder, unreadable
folder or file, --terms-file missing, malformed or inside a scanned tree,
--history without a git repo or without --allowed-identity, malformed
--allowed-identity, a scanner binary missing or failing, git missing when
history or a scanner needs it). On exit 2 no count line is printed.

Finding codes (tree mode; every object of every commit too with --history):
    SECRET      private-key blocks, common token prefixes, JWT-looking
                strings, HTTP bearer credentials and secret-looking
                assignments: a password, passphrase, api-key, secret or token
                key, then a colon or equals sign, then a value of 8+
                characters that is quoted or holds a digit and is not a
                placeholder (angle brackets, ${...}, your-..., changeme ...)
    EMAIL       any address outside example.com/.org/.net and *.invalid
    NOREPLY     any address at the GitHub noreply domain (not also EMAIL)
    BIDI        U+202A-U+202E and U+2066-U+2069, per character
    CTRL        other C0/C1 controls except TAB, LF and CR, per character
    HOMEPATH    absolute home roots: the container workspace root, Linux
                homes other than /home/user, macOS homes, the macOS per-user
                temp folder root (every owner-specific root is assembled
                from fragments in this file, so the kit holds none of them)
    OPSPATH     the owner's operations-folder name (assembled from fragments)
    ALIAS       whole-token alias codes of the owner's shorthand: a two-letter
                prefix, a hyphen, then one lowercase letter or a token (the
                prefixes are assembled from fragments)
    UUID        any UUID that is not all zeros
    CAPTURE     real-capture markers: a file name matching *_real_*; a
                /usage screen whose Email/Org/Organization/Plan field or
                status-header plan segment is not an example address or does
                not start with "Example"
    SUPERPOWERS any path under the dot-superpowers folder, in the tree or
                mentioned in a file
    STRUCT      .gitmodules, a gitlink entry (mode 160000, in the index or
                in any historical tree), a nested .git (dir or file); the
                scanned root's own .git is skipped
    TERMS       hits of the external term list (--terms-file), in file
                contents and in path names
    HDR         --history: an author, committer or tagger header (one per
                header) other than the exact --allowed-identity string
    MSG         --history: any rule above or a term hitting a commit or tag
                message, trailers such as Co-authored-by included
    GITLEAKS    --gitleaks: findings of gitleaks over the full history
    TRUFFLEHOG  --trufflehog: findings of trufflehog over the full history

Paths: every file and directory name is checked by the text rules too, once
per name. Symlinks are never followed (their names are still checked). Files
are decoded as UTF-8 (BOM-aware; UTF-16/UTF-32 with a BOM are decoded as
such), undecodable bytes are replaced. Binary files (a NUL byte in the first
8000 bytes, no BOM) are content-skipped. One that starts with the magic bytes
of a PNG (89 50 4E 47 0D 0A 1A 0A), JPEG (FF D8 FF), GIF (GIF87a, GIF89a) or
WebP (RIFF, 4 size bytes, WEBP) image is counted under `BINARY <n>`; any other
is reported as `SKIP binary`. The file name never decides, and there is no
allow-list.

Term list (--terms-file, refused with exit 2 if it lies inside a scanned
tree): one `term<TAB>flags` per line, `#` comments and blank lines ignored,
flags separated by whitespace. No flags = case-insensitive substring match.
`cs` = case-sensitive whole word (letters and digits are word characters;
hyphens and underscores are boundaries); a term of exactly 4 characters is
always matched as `cs`. `allow=<glob>[,<glob>]` = relative
paths (fnmatch, relative to the scanned folder; a folder also matches with a
trailing slash) where the term is allowed. Terms are matched literally.

History (--history): every object reachable from any ref of the git repo
that holds the folder. Blobs count under their tree codes (once per distinct
blob, also when the same content is still in the work tree), tree entry
names under the path rules (once per distinct path), messages under MSG,
author/committer/tagger headers under HDR. The allowed identity comes from
the command line only, never from a file in the tree.

Scanners (--gitleaks / --trufflehog PATH): run with a fixed argv list, never
a shell, over the full history of the repo that holds each folder; absent ->
`SKIP gitleaks` / `SKIP trufflehog`. An unexpected scanner exit code or an
unreadable result fails closed with exit 2.

Stdlib only, Python 3.9+.
"""

import argparse
import codecs
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CODES = (
    "SECRET", "EMAIL", "NOREPLY", "BIDI", "CTRL", "HOMEPATH", "OPSPATH", "ALIAS",
    "UUID", "CAPTURE", "SUPERPOWERS", "STRUCT", "TERMS", "HDR", "MSG",
    "GITLEAKS", "TRUFFLEHOG",
)
SKIP_ORDER = ("gitleaks", "trufflehog", "terms", "binary")

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2

BINARY_PROBE_BYTES = 8000
# Magic bytes of the image formats counted as BINARY instead of SKIP binary.
IMAGE_MAGIC = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
)
WEBP_RIFF = b"RIFF"  # WebP: RIFF, a 4-byte size, then WEBP
WEBP_TAG = b"WEBP"
SUBPROCESS_TIMEOUT = 1800
GITLEAKS_FINDINGS_EXIT = 1
TRUFFLEHOG_FINDINGS_EXIT = 183


class UsageError(Exception):
    """A generic, value-free message for stderr; the run exits 2."""


def _frag(*parts):
    return "".join(parts)


# Owner-specific roots and prefixes are assembled from fragments: this file is
# scanned too and must hold none of them as a literal.
WORKSPACE_ROOT = _frag("/", "work", "space")
OPS_FOLDER = _frag("forge", "-", "ops")
ALIAS_CH = _frag("ch", "-")
ALIAS_CL = _frag("cl", "-")
SUPERPOWERS_DIR = _frag(".", "super", "powers")
MAC_HOME = _frag("/Us", "ers/")
MAC_TMP = _frag("/var/", "folders/")
LINUX_HOME = "/home/"
ALLOWED_HOME_USER = "user"
NOREPLY_DOMAIN = _frag("noreply.", "github.com")
EXAMPLE_DOMAINS = ("example.com", "example.org", "example.net")
EXAMPLE_TLD = ".invalid"

WORD_L = r"(?<![A-Za-z0-9_\-])"
WORD_R = r"(?![A-Za-z0-9_\-])"
PATH_L = r"(?<![A-Za-z0-9_.~/\-])"

SECRET_TOKEN_RES = (
    re.compile(r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY(?: BLOCK)?-----"),
    re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])xox[abeopsr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"(?<![A-Za-z0-9])glpat-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_\-]{35}(?![A-Za-z0-9_\-])"),
    re.compile(r"(?<![A-Za-z0-9_\-])eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}(?:\.[A-Za-z0-9_\-]+)?"),
)
SECRET_KEY_WORDS = (
    r"(?:pass(?:word|wd|phrase)|pwd|api[_\-]?key|secret(?:[_\-]?key)?|client[_\-]?secret"
    r"|(?:access|auth|refresh|session|bot|private|api)?[_\-]?token)"
)
SECRET_ASSIGN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])" + SECRET_KEY_WORDS
    + r"[\"']?\s*(?:[:=]|=>)\s*(?P<q>[\"'`]?)(?P<v>[^\s\"'`,;]{8,})(?P=q)"
)
BEARER_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])bearer\s+(?P<q>)(?P<v>[A-Za-z0-9._~+/=\-]{16,})(?![A-Za-z0-9._~+/=\-])"
)
PLACEHOLDER_START = "<$%{*~[("
PLACEHOLDER_WORDS = (
    "your", "example", "changeme", "change-me", "change_me", "placeholder", "redacted",
    "dummy", "sample", "xxx", "todo", "none", "null", "true", "false", "replace", "insert",
)

EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@((?:[A-Za-z0-9\-]+\.)+[A-Za-z0-9\-]+)")
TLD_RE = re.compile(r"[a-z]{2,}")

BIDI_RE = re.compile("[\u202a-\u202e\u2066-\u2069]")
CTRL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]")

HOMEPATH_RES = (
    re.compile(PATH_L + re.escape(WORKSPACE_ROOT) + WORD_R),
    re.compile(PATH_L + re.escape(LINUX_HOME) + r"(?!" + ALLOWED_HOME_USER + WORD_R + r")[A-Za-z0-9._\-]+"),
    re.compile(PATH_L + re.escape(MAC_HOME) + r"[A-Za-z0-9._\-]+"),
    re.compile(PATH_L + r"(?:/private)?" + re.escape(MAC_TMP)),
)
OPSPATH_RE = re.compile(WORD_L + re.escape(OPS_FOLDER) + WORD_R, re.IGNORECASE)
ALIAS_RES = (
    re.compile(WORD_L + re.escape(ALIAS_CH) + r"[a-z]" + WORD_R),
    re.compile(WORD_L + re.escape(ALIAS_CL) + r"[a-z0-9]+(?:-[a-z0-9]+)*" + WORD_R),
)
UUID_RE = re.compile(
    r"(?<![0-9A-Fa-f\-])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?![0-9A-Fa-f\-])"
)
SUPERPOWERS_RE = re.compile(WORD_L + re.escape(SUPERPOWERS_DIR) + WORD_R)

REAL_NAME_RE = re.compile(r"_real_", re.IGNORECASE)
USAGE_SCREEN_RE = re.compile(r"(?m)^\s*/usage\s*$|\d{1,3}% used\s*$")
USAGE_FIELD_RE = re.compile(r"(?mi)^\s*(email|org|organization|plan)\s*:\s*(\S.*?)\s*$")
USAGE_HEADER_PREFIX = "Claude Code v"
USAGE_HEADER_SEP = " " + chr(0xB7) + " "
EXAMPLE_PREFIX = "Example"

IDENTITY_RE = re.compile(r"^[^<>\r\n]+ <[^<>@\s]+@[^<>@\s]+>$")
GITLINK_MODE = b"160000"
TREE_MODE = b"40000"


# --- text rules --------------------------------------------------------------

def _spans_overlap(span, spans):
    for start, end in spans:
        if span[0] < end and start < span[1]:
            return True
    return False


def _looks_secret(value, quoted):
    if value[0] in PLACEHOLDER_START:
        return False
    if len(set(value)) == 1:
        return False
    if value.lower().strip("<>[]{}()*\"'`").startswith(PLACEHOLDER_WORDS):
        return False
    if not quoted and not any(ch.isdigit() for ch in value):
        return False
    return True


def count_secrets(text):
    spans = []
    for regex in SECRET_TOKEN_RES:
        spans.extend(m.span() for m in regex.finditer(text))
    count = len(spans)
    for regex in (SECRET_ASSIGN_RE, BEARER_RE):
        for m in regex.finditer(text):
            if _spans_overlap(m.span("v"), spans):
                continue
            if _looks_secret(m.group("v"), bool(m.group("q"))):
                count += 1
    return count


def address_kind(domain):
    """None for an allowed example address or a non-address, else EMAIL or NOREPLY."""
    d = domain.lower().rstrip(".")
    if not TLD_RE.fullmatch(d.rsplit(".", 1)[-1]):
        return None
    if d == NOREPLY_DOMAIN or d.endswith("." + NOREPLY_DOMAIN):
        return "NOREPLY"
    if d in EXAMPLE_DOMAINS or d.endswith(tuple("." + x for x in EXAMPLE_DOMAINS)):
        return None
    if d.endswith(EXAMPLE_TLD):
        return None
    return "EMAIL"


def count_addresses(text):
    emails = noreply = 0
    for m in EMAIL_RE.finditer(text):
        kind = address_kind(m.group(1))
        if kind == "EMAIL":
            emails += 1
        elif kind == "NOREPLY":
            noreply += 1
    return emails, noreply


def count_uuids(text):
    return sum(1 for m in UUID_RE.finditer(text) if set(m.group(0)) - set("0-"))


def text_findings(text):
    """Counts of the content rules in one decoded text (TERMS and the CAPTURE screen rule aside)."""
    counts = {}

    def add(code, n):
        if n:
            counts[code] = counts.get(code, 0) + n

    emails, noreply = count_addresses(text)
    add("SECRET", count_secrets(text))
    add("EMAIL", emails)
    add("NOREPLY", noreply)
    add("BIDI", len(BIDI_RE.findall(text)))
    add("CTRL", len(CTRL_RE.findall(text)))
    add("HOMEPATH", sum(len(r.findall(text)) for r in HOMEPATH_RES))
    add("OPSPATH", len(OPSPATH_RE.findall(text)))
    add("ALIAS", sum(len(r.findall(text)) for r in ALIAS_RES))
    add("UUID", count_uuids(text))
    add("SUPERPOWERS", len(SUPERPOWERS_RE.findall(text)))
    return counts


def _is_example_address(value):
    m = EMAIL_RE.fullmatch(value.strip())
    return bool(m) and address_kind(m.group(1)) is None


def count_capture_screen(text):
    """CAPTURE hits of a /usage-style screen; 0 for any other text."""
    if not USAGE_SCREEN_RE.search(text):
        return 0
    count = 0
    for m in USAGE_FIELD_RE.finditer(text):
        key, value = m.group(1).lower(), m.group(2)
        ok = _is_example_address(value) if key == "email" else value.startswith(EXAMPLE_PREFIX)
        if not ok:
            count += 1
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(USAGE_HEADER_PREFIX):
            parts = [p.strip() for p in line.split(USAGE_HEADER_SEP)]
            if len(parts) >= 3 and not parts[2].startswith(EXAMPLE_PREFIX):
                count += 1
    return count


def decode(data):
    """Text of a file's bytes, or None for a binary file."""
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return data.decode("utf-32", "replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", "replace")
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8", "replace")
    if b"\x00" in data[:BINARY_PROBE_BYTES]:
        return None
    return data.decode("utf-8", "replace")


def is_image(data):
    """True when the bytes start with PNG, JPEG, GIF or WebP magic (never the file name)."""
    if data.startswith(IMAGE_MAGIC):
        return True
    return data[:4] == WEBP_RIFF and data[8:12] == WEBP_TAG


# --- term list ---------------------------------------------------------------

# A term of exactly this many characters is matched as if it carried `cs`:
# as a case-insensitive substring it hits ordinary words.
SHORT_TERM_LEN = 4


class Term:
    __slots__ = ("regex", "allow")

    def __init__(self, regex, allow):
        self.regex = regex
        self.allow = allow

    def allowed_at(self, rel, is_dir):
        if rel is None:
            return False
        for glob in self.allow:
            if fnmatch.fnmatchcase(rel, glob):
                return True
            if is_dir and fnmatch.fnmatchcase(rel + "/", glob):
                return True
        return False


def load_terms(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        raise UsageError("the term list could not be read")
    terms = []
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        term, _, flags = line.partition("\t")
        term = term.strip()
        if not term:
            raise UsageError("the term list has a malformed line")
        case_sensitive = False
        allow = []
        for flag in flags.split():
            if flag == "cs":
                case_sensitive = True
            elif flag.startswith("allow="):
                allow.extend(g for g in flag[len("allow="):].split(",") if g)
            else:
                raise UsageError("the term list has an unknown flag")
        if case_sensitive or len(term) == SHORT_TERM_LEN:
            regex = re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])")
        else:
            regex = re.compile(re.escape(term), re.IGNORECASE)
        terms.append(Term(regex, allow))
    return terms


# --- git helpers -------------------------------------------------------------

def _git(args, cwd, stdin=None):
    """(returncode, stdout bytes); (None, b"") when git cannot run. stderr is discarded."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            env=env,
            input=stdin if stdin is not None else b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, b""
    return proc.returncode, proc.stdout


def repo_toplevel(folder):
    code, out = _git(["rev-parse", "--show-toplevel"], folder)
    if code != 0 or not out.strip():
        return None
    return os.path.realpath(os.fsdecode(out.strip()))


def repo_hash_algorithm(top):
    code, out = _git(["rev-parse", "--show-object-format"], top)
    name = out.decode("ascii", "replace").strip() if code == 0 else ""
    return "sha256" if name == "sha256" else "sha1"


def blob_id(data, algorithm):
    digest = hashlib.new(algorithm)
    digest.update(b"blob %d\0" % len(data))
    digest.update(data)
    return digest.hexdigest()


# --- the scan ----------------------------------------------------------------

class Scan:
    def __init__(self, folders, terms, allowed_identity, tools, tops, history):
        self.folders = folders
        self.terms = terms
        self.allowed_identity = allowed_identity
        self.tools = tools
        self.tops = tops
        self.history = history
        self.counts = dict((code, 0) for code in CODES)
        self.images = 0
        self.skips = set()
        self.seen_blobs = set()
        self.seen_paths = set()
        self.seen_gitlinks = set()
        self.hash_algorithms = {}

    def add(self, code, n=1):
        if n:
            self.counts[code] += n

    def total(self):
        return sum(self.counts.values())

    def report_lines(self):
        lines = ["%s %d" % (code, self.counts[code]) for code in CODES if self.counts[code]]
        if self.images:
            lines.append("BINARY %d" % self.images)
        lines.extend("SKIP " + what for what in SKIP_ORDER if what in self.skips)
        lines.append("TOTAL %d" % self.total())
        return lines

    def run(self):
        unique_tops = []
        for top in self.tops.values():
            if top not in unique_tops:
                unique_tops.append(top)
        if self.history:
            for top in unique_tops:
                self.scan_history(top)
        for folder in self.folders:
            self.scan_folder(folder)
            self.scan_index_gitlinks(folder)
        for top in unique_tops:
            if "gitleaks" in self.tools:
                self.run_gitleaks(self.tools["gitleaks"], top)
            if "trufflehog" in self.tools:
                self.run_trufflehog(self.tools["trufflehog"], top)
        for name in ("gitleaks", "trufflehog"):
            if name not in self.tools:
                self.skips.add(name)
        if self.terms is None:
            self.skips.add("terms")

    # text and names

    def count_terms(self, text, rel, is_dir):
        if not self.terms:
            return 0
        count = 0
        for term in self.terms:
            if term.allowed_at(rel, is_dir):
                continue
            count += len(term.regex.findall(text))
        return count

    def check_name(self, name, rel, is_dir, dedupe_key=None):
        if dedupe_key is not None:
            if dedupe_key in self.seen_paths:
                return
            self.seen_paths.add(dedupe_key)
        if name == ".gitmodules":
            self.add("STRUCT")
        for code, n in text_findings(name).items():
            self.add(code, n)
        if REAL_NAME_RE.search(name):
            self.add("CAPTURE")
        self.add("TERMS", self.count_terms(name, rel, is_dir))

    def scan_bytes(self, data, rel):
        text = decode(data)
        if text is None:
            if is_image(data):
                self.images += 1
            else:
                self.skips.add("binary")
            return
        for code, n in text_findings(text).items():
            self.add(code, n)
        self.add("CAPTURE", count_capture_screen(text))
        self.add("TERMS", self.count_terms(text, rel, False))

    # work tree

    def scan_folder(self, folder):
        root = os.path.abspath(folder)
        top = self.tops.get(folder) if self.history else None
        prefix = None
        if top is not None:
            prefix = os.path.relpath(os.path.realpath(root), top)
            prefix = "" if prefix == "." else prefix
        stack = [(root, "")]
        while stack:
            directory, rel = stack.pop()
            try:
                with os.scandir(directory) as it:
                    entries = sorted(it, key=lambda e: e.name)
            except OSError:
                raise UsageError("a folder could not be read")
            for entry in entries:
                name = entry.name
                erel = name if not rel else rel + "/" + name
                if name == ".git":
                    if rel:
                        self.add("STRUCT")
                    continue
                try:
                    is_link = entry.is_symlink()
                    is_dir = not is_link and entry.is_dir(follow_symlinks=False)
                    is_file = not is_link and entry.is_file(follow_symlinks=False)
                except OSError:
                    raise UsageError("a folder entry could not be read")
                key = None
                if prefix is not None:
                    key = erel if not prefix else prefix + "/" + erel
                self.check_name(name, erel, is_dir, key)
                if is_link:
                    continue
                if is_dir:
                    stack.append((entry.path, erel))
                elif is_file:
                    self.scan_work_file(entry.path, erel, top)

    def scan_work_file(self, path, rel, top):
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError:
            raise UsageError("a file could not be read")
        if top is not None and blob_id(data, self.hash_algorithms[top]) in self.seen_blobs:
            return
        self.scan_bytes(data, rel)

    def scan_index_gitlinks(self, folder):
        code, out = _git(["ls-files", "-s", "-z"], folder)
        if code != 0:
            return
        top = self.tops.get(folder) if self.history else None
        prefix = ""
        if top is not None:
            prefix = os.path.relpath(os.path.realpath(os.path.abspath(folder)), top)
            prefix = "" if prefix == "." else prefix + "/"
        for entry in out.split(b"\0"):
            meta, _, path = entry.partition(b"\t")
            if not meta.startswith(GITLINK_MODE + b" "):
                continue
            key = prefix + os.fsdecode(path)
            if top is not None and key in self.seen_gitlinks:
                continue
            self.add("STRUCT")

    # history

    def scan_history(self, top):
        self.hash_algorithms[top] = repo_hash_algorithm(top)
        hash_len = 32 if self.hash_algorithms[top] == "sha256" else 20
        code, out = _git(["rev-list", "--all", "--objects"], top)
        if code != 0:
            raise UsageError("the git history could not be listed")
        order = []
        paths = {}
        for raw in out.split(b"\n"):
            if not raw:
                continue
            sha, _, path = raw.partition(b" ")
            sha = sha.decode("ascii", "replace")
            if sha not in paths:
                order.append(sha)
                paths[sha] = os.fsdecode(path)
        code, out = _git(["for-each-ref", "--format=%(objectname) %(objecttype)", "refs/tags"], top)
        if code == 0:
            for raw in out.decode("ascii", "replace").splitlines():
                parts = raw.split()
                if len(parts) == 2 and parts[1] == "tag" and parts[0] not in paths:
                    order.append(parts[0])
                    paths[parts[0]] = ""
        if not order:
            return
        code, batch = _git(["cat-file", "--batch"], top, stdin=("\n".join(order) + "\n").encode("ascii"))
        if code != 0:
            raise UsageError("the git objects could not be read")
        pos = 0
        while pos < len(batch):
            newline = batch.find(b"\n", pos)
            if newline < 0:
                break
            header = batch[pos:newline].decode("ascii", "replace").split()
            pos = newline + 1
            if len(header) < 3:
                continue
            sha, kind, size = header[0], header[1], int(header[2])
            content = batch[pos:pos + size]
            pos += size + 1
            if kind in ("commit", "tag"):
                self.scan_commitish(content)
            elif kind == "tree":
                self.scan_tree_object(content, paths.get(sha, ""), hash_len)
            elif kind == "blob":
                self.seen_blobs.add(sha)
                self.scan_bytes(content, paths.get(sha, ""))

    def scan_commitish(self, content):
        head, _, message = content.partition(b"\n\n")
        for line in head.decode("utf-8", "replace").split("\n"):
            for kind in ("author ", "committer ", "tagger "):
                if line.startswith(kind):
                    identity = line[len(kind):]
                    end = identity.rfind(">")
                    if end >= 0:
                        identity = identity[:end + 1]
                    if identity.strip() != self.allowed_identity:
                        self.add("HDR")
        text = message.decode("utf-8", "replace")
        hits = sum(text_findings(text).values())
        hits += self.count_terms(text, None, False)
        self.add("MSG", hits)

    def scan_tree_object(self, content, tree_path, hash_len):
        pos = 0
        while pos < len(content):
            space = content.find(b" ", pos)
            nul = content.find(b"\x00", space)
            if space < 0 or nul < 0:
                break
            mode = content[pos:space]
            name = os.fsdecode(content[space + 1:nul])
            pos = nul + 1 + hash_len
            rel = name if not tree_path else tree_path + "/" + name
            if mode == GITLINK_MODE and rel not in self.seen_gitlinks:
                self.seen_gitlinks.add(rel)
                self.add("STRUCT")
            self.check_name(name, rel, mode == TREE_MODE, rel)

    # external scanners

    def _run_tool(self, argv, work):
        # No GITLEAKS_* / TRUFFLEHOG_* variable: one could hand the tool a config or allowlist.
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GITLEAKS_", "TRUFFLEHOG_"))}
        env["HOME"] = work
        env["GIT_TERMINAL_PROMPT"] = "0"
        try:
            proc = subprocess.run(
                argv,
                cwd=work,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=SUBPROCESS_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise UsageError("a scanner could not be run")
        return proc.returncode, proc.stdout

    def run_gitleaks(self, binary, top):
        work = tempfile.mkdtemp(prefix="clean-scan-")
        try:
            report = os.path.join(work, "report.json")
            argv = [
                binary, "git", "--log-opts=--all", "--redact", "--no-banner",
                "--log-level", "error", "--report-format", "json", "--report-path", report,
                "--exit-code", str(GITLEAKS_FINDINGS_EXIT), top,
            ]
            code, _ = self._run_tool(argv, work)
            if code not in (0, GITLEAKS_FINDINGS_EXIT):
                raise UsageError("gitleaks failed")
            findings = None
            if os.path.isfile(report):
                try:
                    with open(report, "rb") as handle:
                        raw = json.loads(handle.read().decode("utf-8", "replace"))
                    if isinstance(raw, list):
                        findings = len(raw)
                except ValueError:
                    findings = None
            if findings is None:
                if code != 0:
                    raise UsageError("gitleaks wrote no readable report")
                findings = 0
            if code == GITLEAKS_FINDINGS_EXIT and findings == 0:
                raise UsageError("the gitleaks report does not match its exit code")
            self.add("GITLEAKS", findings)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def run_trufflehog(self, binary, top):
        work = tempfile.mkdtemp(prefix="clean-scan-")
        try:
            argv = [binary, "git", "--no-verification", "--no-update", "--json", "--fail", "file://" + top]
            code, out = self._run_tool(argv, work)
            if code not in (0, TRUFFLEHOG_FINDINGS_EXIT):
                raise UsageError("trufflehog failed")
            findings = 0
            for line in out.decode("utf-8", "replace").splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict) and ("DetectorName" in item or "SourceMetadata" in item):
                    findings += 1
            if code == TRUFFLEHOG_FINDINGS_EXIT and findings == 0:
                raise UsageError("the trufflehog results do not match its exit code")
            self.add("TRUFFLEHOG", findings)
        finally:
            shutil.rmtree(work, ignore_errors=True)


# --- command line ------------------------------------------------------------

class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Generic on purpose: argparse's own text would echo the offending argument.
        self.exit(EXIT_USAGE, "clean_scan: usage error (see --help)\n")


def parse_args(argv):
    parser = Parser(
        prog="clean_scan.py",
        description="Count owner-data findings in folders; print codes and counts only.",
    )
    parser.add_argument("folders", nargs="+", metavar="FOLDER", help="folder to scan")
    parser.add_argument("--terms-file", metavar="PATH", help="external term list (must lie outside every scanned folder)")
    parser.add_argument("--history", action="store_true", help="also scan every object, message and header of the git history")
    parser.add_argument("--allowed-identity", metavar="IDENTITY", help='the only allowed author/committer, as "Name <email>"')
    parser.add_argument("--gitleaks", metavar="PATH", help="gitleaks binary to run over the history")
    parser.add_argument("--trufflehog", metavar="PATH", help="trufflehog binary to run over the history")
    return parser.parse_args(argv)


def prepare(args):
    folders = [os.path.abspath(f) for f in args.folders]
    for folder in folders:
        if not os.path.isdir(folder):
            raise UsageError("a folder does not exist or is not a directory")
    allowed = None
    if args.allowed_identity is not None:
        if not IDENTITY_RE.match(args.allowed_identity.strip()):
            raise UsageError('--allowed-identity must look like "Name <user@example.com>"')
        allowed = args.allowed_identity.strip()
    if args.history and allowed is None:
        raise UsageError("--history needs --allowed-identity")
    terms = None
    if args.terms_file is not None:
        terms_real = os.path.realpath(args.terms_file)
        if not os.path.isfile(terms_real):
            raise UsageError("the term list does not exist")
        for folder in folders:
            real = os.path.realpath(folder)
            if terms_real == real or terms_real.startswith(real.rstrip(os.sep) + os.sep):
                raise UsageError("the term list lies inside a scanned folder; keep it outside the kit")
        terms = load_terms(terms_real)
    tools = {}
    for name in ("gitleaks", "trufflehog"):
        path = getattr(args, name)
        if path is None:
            continue
        path = os.path.abspath(path)
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            raise UsageError("the --%s binary is missing or not executable" % name)
        tools[name] = path
    tops = {}
    if args.history or tools:
        for folder in folders:
            top = repo_toplevel(folder)
            if top is None:
                raise UsageError("a folder is not inside a git repository (needed for --history and the scanners)")
            tops[folder] = top
    return Scan(folders, terms, allowed if args.history else None, tools, tops, args.history)


def main(argv=None):
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    try:
        scan = prepare(args)
        scan.run()
    except UsageError as exc:
        print("clean_scan: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # never let a traceback echo a path or a value
        print("clean_scan: internal error (%s)" % type(exc).__name__, file=sys.stderr)
        return EXIT_USAGE
    for line in scan.report_lines():
        print(line)
    return EXIT_FINDINGS if scan.total() else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
