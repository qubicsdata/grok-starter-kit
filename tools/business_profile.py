#!/usr/bin/env python3
"""business_profile.py: the private business profile (AGENTS.md checkpoint 3b).

The profile holds what your Grok Bot learns about your school from your own
website and social accounts: its name, studios, styles, schedule, prices and
channels. It lives at `<channel>/private/business-profile.yaml` in your second
brain and never goes into git; the keys are documented in
`second-brain/BUSINESS-PROFILE.md`.

Usage:
  python3 tools/business_profile.py draft [--channel NAME] SITE_FOLDER
  python3 tools/business_profile.py fill --profile PATH TEMPLATE
  python3 tools/business_profile.py check [--repo DIR] [--all]

draft   reads pages you saved from your own website (*.html and *.htm under
        SITE_FOLDER; local files only, it never fetches anything), takes what
        they declare (schema.org JSON-LD, the og:site_name meta tag) and prints
        a profile with `unknown` for everything it could not see. Your Grok
        Bot shows it to you; it is saved only after your OK.
fill    prints TEMPLATE with every {{key}} replaced by the profile's value.
        A key that is missing or still `unknown` stays as it is and is named
        on stderr.
check   the refuse-to-commit check: fails when the staged changes (or, with
        --all, the tracked files) hold a file in a `private/` folder, a
        `business-profile*.yaml` file, or any file with the profile's marker
        line. Install it as the pre-commit hook of your notes repo (see
        BUSINESS-PROFILE.md). It prints paths only, never file contents.

None of the commands writes a file. Exit codes: 0 fine; 1 `fill`: a key is
missing or unknown, `check`: a file is refused; 2 usage error (unreadable or
malformed input, a URL where a local path is needed, not a git repository).
Stdlib only, Python 3.9+.
"""

import argparse
import fnmatch
import html.parser
import json
import os
import re
import subprocess
import sys

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
MARKER_RE = re.compile(rb"^[ \t]*profile\.private[ \t]*:[ \t]*[\"']?true[\"']?[ \t]*(#[^\n]*)?\r?$",
                       re.MULTILINE | re.IGNORECASE)
PROFILE_NAME_GLOBS = ("business-profile*.yaml", "business-profile*.yml")
UNKNOWN = "unknown"

# Every key of the profile, in the order `draft` prints them (BUSINESS-PROFILE.md).
KEYS = (
    "profile.private", "channel",
    "school.name", "school.website", "school.local_language", "school.second_language",
    "studios.count",
    "studio.1.name", "studio.1.town", "studio.1.address",
    "studio.2.name", "studio.2.town", "studio.2.address",
    "styles",
    "groups.adults", "groups.seniors", "groups.kids", "groups.teens", "groups.english",
    "term.autumn_start", "term.january_start", "schedule.opening_hours",
    "price.currency", "price.single", "price.couple", "price.pass_4", "price.pass_8", "price.drop_in",
    "price.benefit_platforms",
    "offer.first_month", "offer.refund_guarantee",
    "social.instagram", "social.facebook", "social.whatsapp_broadcast",
)

SCHOOL_TYPES = ("DanceSchool", "SportsActivityLocation", "LocalBusiness", "EducationalOrganization",
                "SportsClub", "Organization")
# Offer name -> price key; the first pattern that matches wins.
OFFER_KEYS = (
    (re.compile(r"drop[\s-]?in", re.I), "price.drop_in"),
    (re.compile(r"couple", re.I), "price.couple"),
    (re.compile(r"\b8\b|\beight\b", re.I), "price.pass_8"),
    (re.compile(r"\b4\b|\bfour\b", re.I), "price.pass_4"),
    (re.compile(r"single|\bone\b|\b1\b", re.I), "price.single"),
)
SOCIAL_KEYS = (("instagram", "social.instagram"), ("facebook", "social.facebook"))
PAGE_SUFFIXES = (".html", ".htm")
MAX_PAGE_BYTES = 5 * 1024 * 1024


class UsageError(Exception):
    pass


def local_path(path, what):
    if URL_RE.match(path):
        raise UsageError("%s must be a local path; this tool never fetches anything" % what)
    return path


# ---------------------------------------------------------------- profile and fill


def parse_profile(text):
    """{key: value} of the flat `key: value` format. Raises UsageError naming
    the line number (never the line) on anything else."""
    values = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, rest = line.partition(":")
        key = key.strip()
        if not sep or not KEY_RE.match(key) or key in values:
            raise UsageError("the profile is malformed at line %d" % number)
        value = rest.strip()
        if value[:1] in ("\"", "'"):
            end = value.find(value[0], 1)
            tail = value[end + 1:].strip() if end > 0 else ""
            if end < 0 or (tail and not tail.startswith("#")):
                raise UsageError("the profile is malformed at line %d" % number)
            value = value[1:end]
        else:
            value = "" if value.startswith("#") else re.split(r"\s#", value, 1)[0].strip()
        values[key] = value
    return values


def fill(template, values):
    """(filled text, [missing keys in first-seen order])."""
    missing = []

    def replace(match):
        key = match.group(1)
        value = values.get(key)
        if value is None or value.strip().lower() == UNKNOWN:
            if key not in missing:
                missing.append(key)
            return match.group(0)
        return value

    return PLACEHOLDER_RE.sub(replace, template), missing


def read_local(path, what):
    local_path(path, what)
    if not os.path.isfile(path):
        raise UsageError("%s is not a readable file" % what)
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        raise UsageError("%s is not a readable file" % what)


def cmd_fill(args):
    values = parse_profile(read_local(args.profile, "the profile"))
    text, missing = fill(read_local(args.template, "the template"), values)
    sys.stdout.write(text)
    if missing:
        sys.stderr.write("business_profile fill: missing or unknown in the profile: %s\n" % ", ".join(missing))
        return 1
    return 0


# ---------------------------------------------------------------- draft


class PageParser(html.parser.HTMLParser):
    """Collects JSON-LD blocks and the og:site_name meta tag of one page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.site_name, self._in_ld, self._buf = [], None, False, []

    def handle_starttag(self, tag, attrs):
        attrs = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and attrs.get("type", "").strip().lower() == "application/ld+json":
            self._in_ld, self._buf = True, []
        elif tag == "meta" and attrs.get("property", "").lower() == "og:site_name" and self.site_name is None:
            self.site_name = attrs.get("content", "").strip() or None

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.blocks.append("".join(self._buf))


def site_pages(folder):
    pages = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if name.startswith(".") or not name.lower().endswith(PAGE_SUFFIXES) or os.path.islink(path):
                continue
            if os.path.getsize(path) <= MAX_PAGE_BYTES:
                pages.append(path)
    return pages


def nodes(data):
    """Every JSON object in a JSON-LD document, depth first."""
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from nodes(value)
    elif isinstance(data, list):
        for item in data:
            yield from nodes(item)


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def types_of(node):
    return [t for t in as_list(node.get("@type")) if isinstance(t, str)]


def text_of(value):
    if isinstance(value, dict):
        value = value.get("name")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = " ".join(value.replace("\"", "'").split())
    return value or None


def school_node(found):
    for wanted in SCHOOL_TYPES:
        for node in found:
            if wanted in types_of(node):
                return node
    return None


def studios_of(school):
    studios = []
    for place in as_list(school.get("location")):
        if not isinstance(place, dict):
            continue
        address = place.get("address")
        town = street = None
        if isinstance(address, dict):
            town, street = text_of(address.get("addressLocality")), text_of(address.get("streetAddress"))
        else:
            street = text_of(address)
        studios.append((text_of(place.get("name")), town, street))
    return studios


def offers_of(found):
    offers = []
    for node in found:
        if "Offer" in types_of(node):
            offers.append(node)
    return offers


def draft_values(pages, channel):
    values = {key: UNKNOWN for key in KEYS}
    values["profile.private"] = "true"
    values["channel"] = channel
    found, site_name = [], None
    for path in pages:
        parser = PageParser()
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                parser.feed(fh.read())
            parser.close()
        except (OSError, AssertionError):
            continue
        site_name = site_name or parser.site_name
        for block in parser.blocks:
            try:
                found.extend(nodes(json.loads(block)))
            except ValueError:
                continue
    school = school_node(found)
    if school is not None:
        for key, field in (("school.name", "name"), ("school.website", "url")):
            values[key] = text_of(school.get(field)) or UNKNOWN
        styles = [text_of(s) for s in as_list(school.get("knowsAbout"))]
        if any(styles):
            values["styles"] = ", ".join(s for s in styles if s)
        hours = [text_of(h) for h in as_list(school.get("openingHours"))]
        if any(hours):
            values["schedule.opening_hours"] = "; ".join(h for h in hours if h)
        studios = studios_of(school)
        if studios:
            values["studios.count"] = str(len(studios))
        for index, (name, town, street) in enumerate(studios, 1):
            for field, value in (("name", name), ("town", town), ("address", street)):
                values["studio.%d.%s" % (index, field)] = value or UNKNOWN
        for link in as_list(school.get("sameAs")):
            link = text_of(link) or ""
            host = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", link).split("/", 1)[0].lower()
            for word, key in SOCIAL_KEYS:
                if word in host and values[key] == UNKNOWN:
                    values[key] = link
    if values["school.name"] == UNKNOWN and site_name:
        values["school.name"] = text_of(site_name) or UNKNOWN
    for offer in offers_of(found):
        name, price = text_of(offer.get("name")) or "", text_of(offer.get("price"))
        if price is None:
            continue
        for pattern, key in OFFER_KEYS:
            if pattern.search(name):
                if values[key] == UNKNOWN:
                    values[key] = price
                break
        currency = text_of(offer.get("priceCurrency"))
        if currency and values["price.currency"] == UNKNOWN:
            values["price.currency"] = currency
    return values


def cmd_draft(args):
    folder = local_path(args.site, "the site folder")
    if not os.path.isdir(folder):
        raise UsageError("the site folder is not a readable folder")
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", args.channel):
        raise UsageError("--channel takes one channel name")
    pages = site_pages(folder)
    values = draft_values(pages, args.channel)
    lines = ["profile.private: true",
             "# Draft from %d saved page(s) of your own site. Check every value with your Grok Bot;" % len(pages),
             "# it is saved only after your OK (checkpoint 3b). Never commit this file."]
    extra = sorted(k for k in values if k not in KEYS)
    for key in [k for k in KEYS if k != "profile.private"] + extra:
        lines.append("%s: \"%s\"" % (key, values[key]))
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


# ---------------------------------------------------------------- check


def git(top, env, *args, data=None):
    try:
        proc = subprocess.run(["git"] + list(args), cwd=top, env=env, input=data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        raise UsageError("git is not available")
    return proc


def git_ok(top, env, *args, data=None):
    proc = git(top, env, *args, data=data)
    if proc.returncode != 0:
        raise UsageError("git %s failed" % args[0])
    return proc.stdout


def private_path(rel):
    parts = rel.replace("\\", "/").split("/")
    if any(p.lower() == "private" for p in parts[:-1]):
        return True
    return any(fnmatch.fnmatch(parts[-1].lower(), g) for g in PROFILE_NAME_GLOBS)


def staged_entries(top, env):
    """[(path, blob sha)] of every added, copied, modified or retyped path."""
    base = "HEAD"
    if git(top, env, "rev-parse", "-q", "--verify", "HEAD").returncode != 0:
        base = git_ok(top, env, "hash-object", "-t", "tree", "--stdin", data=b"").decode().strip()
    out = git_ok(top, env, "diff", "--cached", "--raw", "-z", "--no-abbrev", "--no-renames",
                 "--diff-filter=ACMRT", base)
    fields = out.split(b"\0")
    entries = []
    for meta, raw in zip(fields[0::2], fields[1::2]):
        meta = meta.split()
        if len(meta) < 5:
            continue
        entries.append((os.fsdecode(raw), meta[3].decode(), meta[1].decode()))
    return entries


def tracked_entries(top, env):
    entries = []
    for record in git_ok(top, env, "ls-files", "-s", "-z").split(b"\0"):
        if not record:
            continue
        meta, _, raw = record.partition(b"\t")
        mode, sha = meta.split()[:2]
        entries.append((os.fsdecode(raw), sha.decode(), mode.decode()))
    return entries


def blobs(top, env, shas):
    """{sha: content} through one `git cat-file --batch`."""
    shas = sorted(set(shas))
    if not shas:
        return {}
    out = git_ok(top, env, "cat-file", "--batch", data=("\n".join(shas) + "\n").encode())
    contents, pos = {}, 0
    for sha in shas:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        pos = end + 1
        if len(header) != 3:
            continue
        size = int(header[2])
        contents[sha] = out[pos:pos + size]
        pos += size + 1
    return contents


def cmd_check(args):
    env = dict(os.environ)
    start = os.getcwd()
    if args.repo:
        start = local_path(args.repo, "--repo")
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(name, None)
    if not os.path.isdir(start):
        raise UsageError("--repo is not a folder")
    proc = git(start, env, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        raise UsageError("not inside a git repository")
    top = os.fsdecode(proc.stdout.strip())
    entries = tracked_entries(top, env) if args.all else staged_entries(top, env)
    contents = blobs(top, env, [sha for _, sha, mode in entries if mode != "160000"])
    refused = []
    for rel, sha, mode in entries:
        if private_path(rel):
            refused.append((rel, "private path"))
        elif MARKER_RE.search(contents.get(sha, b"")):
            refused.append((rel, "profile marker"))
    if refused:
        for rel, reason in refused:
            sys.stderr.write("business_profile check: refused %s (%s)\n" % (rel, reason))
        sys.stderr.write("business_profile check: %d file(s) refused. The private business profile never goes "
                         "into git; take it out with: git rm --cached -- <path>\n" % len(refused))
        return 1
    sys.stdout.write("business_profile check: OK (%d %s files checked)\n"
                     % (len(entries), "tracked" if args.all else "staged"))
    return 0


# ---------------------------------------------------------------- main


def main(argv=None):
    parser = argparse.ArgumentParser(prog="business_profile.py", description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", metavar="{draft,fill,check}")
    sub.required = True
    draft = sub.add_parser("draft", help="print a profile drafted from pages saved from your own site")
    draft.add_argument("--channel", default="dance-school", help="the profile's channel (default dance-school)")
    draft.add_argument("site", metavar="SITE_FOLDER")
    filler = sub.add_parser("fill", help="print a template with its {{key}} values filled from the profile")
    filler.add_argument("--profile", required=True, metavar="PATH")
    filler.add_argument("template", metavar="TEMPLATE")
    check = sub.add_parser("check", help="refuse a commit that holds the private profile")
    check.add_argument("--repo", metavar="DIR", help="the repository to check (default: the current folder)")
    check.add_argument("--all", action="store_true", help="check every tracked file instead of the staged changes")
    args = parser.parse_args(argv)
    try:
        return {"draft": cmd_draft, "fill": cmd_fill, "check": cmd_check}[args.command](args)
    except UsageError as exc:
        sys.stderr.write("business_profile %s: %s\n" % (args.command, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
