"""WP-12 doc-test harness, part 1 (static): the promoted docs and the command inventory agree.

README.md, docs/local-security.md, docs/migration-runbook.md and docs/trial-note.md (promoted from the
WP-12a drafts in WP12b-2) use the spellings this tree and the landed branches accept: every fenced command must be a row of tests/wp12_support.py ROWS (so it is exercised), every
required row must be shown, every `folio` command must parse with this tree's parser or with the parser of
the pending WP that owns it, and the Backlog.md web board appears only as a warning. The checks are proven
against planted text, including the spellings of the WP-12a drafts that the landed code refuses.
"""

import re
import tempfile
import unittest
from pathlib import Path

import test_wp12_docs_run  # noqa: F401  (registers every @exercises row)
import wp12_support as support
from wp12_support import (BOARD, BOARD_RULE_DOCS, CUT, DOCS, EXERCISED, KINDS, PENDING_SPECS, PLACEHOLDERS, README, REPO_ROOT,
                          ROWS, ROWS_BY_KEY, check_backlog_argv, check_folio_argv, cut_by, doc_commands, doc_text,
                          fenced_commands, inline_commands, key, placeholders, subcommands, tree_parser, without_fences)
from wp6_support import LOCAL_PATH_RULES, bidi_counts

PREPUB = REPO_ROOT / "tools" / "prepub"
RELEASE_BUILD_WORDS = ("brew", "curl", "wget", "install.sh", "releases/download", ".tar.gz", ".tgz", ".whl", ".pkg", ".dmg",
                       ".zip", "homebrew")
BOARD_RULE = "Never run `backlog %s`" % BOARD


def problems_for(root, docs=DOCS):
    """Every inventory problem of the docs under root: (fence problems, unlisted, bad placeholders, bad argv)."""
    found, fence_problems = doc_commands(root, docs)
    unlisted, bad_placeholders, bad_argv = [], [], []
    parser = tree_parser()
    for doc, (fenced, inline) in found.items():
        for command in fenced:
            label = "%s:%d: %s" % (command.doc, command.line, " ".join(command.argv))
            if command.argv not in ROWS_BY_KEY:
                unlisted.append(label)
            unknown = [name for name in placeholders(command.argv) if name not in PLACEHOLDERS]
            if unknown:
                bad_placeholders.append("%s (unknown %s)" % (label, ", ".join(unknown)))
        for command in fenced + inline:
            label = "%s:%d: %s" % (command.doc, command.line, " ".join(command.argv))
            if command.argv[0] == "folio" and cut_by(command.argv):
                problem = None if command.where == "inline" else "cut by %s: prose may name it, a fence never" % cut_by(command.argv)
            elif command.argv[0] == "folio":
                _owner, problem = check_folio_argv(command.argv, parser, whole=command.where == "fence")
            elif command.argv[0] == "backlog":
                problem = check_backlog_argv(command.argv, command.where)
            else:
                problem = None
            if problem:
                bad_argv.append("%s -> %s" % (label, problem))
    return fence_problems, unlisted, bad_placeholders, bad_argv


class PromotedDocsTests(unittest.TestCase):
    def test_the_four_promoted_docs_exist(self):
        missing = [doc for doc in DOCS if doc_text(doc) is None]
        self.assertEqual(missing, [], "the WP-12 user docs live at these paths")

    def test_every_fence_is_labelled_sh_for_commands_or_a_known_text_language(self):
        fence_problems, _unlisted, _placeholders, _argv = problems_for(REPO_ROOT)
        self.assertEqual(fence_problems, [])

    def test_every_fenced_command_is_a_row_of_the_inventory(self):
        """Acceptance: every README command is exercised by a doc-test or smoke script (rows -> @exercises)."""
        _fences, unlisted, _placeholders, _argv = problems_for(REPO_ROOT)
        self.assertEqual(unlisted, [], "%d fenced commands have no doc-test row" % len(unlisted))

    def test_every_required_row_is_shown_by_its_docs(self):
        found, _problems = doc_commands()
        missing = []
        for row in ROWS:
            for doc in row.required_in:
                fenced, inline = found.get(doc, ([], []))
                if key(row.command) not in {command.argv for command in fenced + inline}:
                    missing.append("%s: %s" % (doc, row.command))
        self.assertEqual(missing, [], "%d required commands are not shown" % len(missing))

    def test_fenced_placeholders_are_the_known_ones(self):
        _fences, _unlisted, bad_placeholders, _argv = problems_for(REPO_ROOT)
        self.assertEqual(bad_placeholders, [])

    def test_every_folio_and_backlog_command_in_the_docs_exists_here_or_on_a_pending_branch(self):
        """Red for missing commands: a `folio` command nothing provides, or one a parser refuses, fails."""
        _fences, _unlisted, _placeholders, bad_argv = problems_for(REPO_ROOT)
        self.assertEqual(bad_argv, [])

    def test_the_board_rule_is_stated_and_the_board_is_never_fenced(self):
        missing = [doc for doc in BOARD_RULE_DOCS if BOARD_RULE not in (doc_text(doc) or "")]
        self.assertEqual(missing, [], "these docs must say: %s" % BOARD_RULE)
        found, _problems = doc_commands()
        fenced = ["%s:%d" % (command.doc, command.line) for fenced, _inline in found.values() for command in fenced
                  if BOARD in command.argv]
        self.assertEqual(fenced, [])

    def test_no_homebrew_or_release_build_install_path(self):
        """Acceptance: the git URL through uv or pipx is the only install path."""
        found, _problems = doc_commands()
        hits = []
        for fenced, inline in found.values():
            for command in fenced + inline:
                text = " ".join(command.argv).lower()
                hits += ["%s:%d: %s" % (command.doc, command.line, word) for word in RELEASE_BUILD_WORDS if word in text]
                if command.argv[:2] in (("pip", "install"), ("pip3", "install")):
                    hits.append("%s:%d: pip install" % (command.doc, command.line))
        installs = [command for fenced, _inline in found.values() for command in fenced
                    if command.argv[:3] == ("uv", "tool", "install") or command.argv[:2] == ("pipx", "install")]
        hits += ["%s:%d: install source is not the public git URL" % (command.doc, command.line)
                 for command in installs if command.argv[-1] != support.PUBLIC_INSTALL_URL]
        self.assertEqual(hits, [])


class InventoryTests(unittest.TestCase):
    def test_rows_are_unique_and_well_formed(self):
        self.assertEqual(len(ROWS_BY_KEY), len(ROWS), "duplicate rows")
        for row in ROWS:
            with self.subTest(row=row.command):
                self.assertIn(row.kind, KINDS)
                self.assertTrue(set(row.required_in) <= set(DOCS))
                self.assertEqual([name for name in placeholders(key(row.command)) if name not in PLACEHOLDERS], [])
                if row.kind == "pending":
                    self.assertIsNotNone(row.owner)

    def test_every_row_is_exercised_by_a_registered_test(self):
        unexercised = [row.command for row in ROWS if key(row.command) not in EXERCISED]
        self.assertEqual(unexercised, [])
        strays = [" ".join(argv) for argv in EXERCISED if argv not in ROWS_BY_KEY]
        self.assertEqual(strays, [])

    def test_every_folio_row_parses_here_or_on_its_owning_branch(self):
        parser = tree_parser()
        for row in ROWS:
            argv = key(row.command)
            if argv[0] != "folio":
                continue
            with self.subTest(row=row.command):
                owner, problem = check_folio_argv(argv, parser)
                self.assertIsNone(problem)
                self.assertEqual(owner, "tree" if row.kind != "pending" else row.owner)

    def test_pending_subcommands_are_not_in_this_tree_yet(self):
        """Tripwire: once a pending WP's command is in folio/cli.py, its spec and skip must go."""
        tree = subcommands(tree_parser())
        landed = ["folio %s (%s, %s)" % (name, wp, branch) for name, (wp, branch, _spec) in PENDING_SPECS.items() if name in tree]
        self.assertEqual(landed, [], "replace the pending spec and the skip with the doc-test")

    def test_every_cut_command_is_a_usage_error_in_this_tree(self):
        """CUT lets prose name removed commands; it must not hide a command that still exists."""
        parser = tree_parser()
        for words, wp in sorted(CUT.items()):
            with self.subTest(command=" ".join(words), cut_by=wp):
                owner, problem = check_folio_argv(("folio",) + words + ("x",), parser)
                self.assertIsNotNone(problem, "folio %s still parses: drop it from CUT" % " ".join(words))
                self.assertEqual(cut_by(("folio",) + words), wp)
        self.assertEqual(cut_by(("folio", "projects", "link|unlink")), "WP-7")
        self.assertIsNone(cut_by(("folio", "projects", "list|link")))
        self.assertIsNone(cut_by(("folio", "projects", "list")))

    def test_the_board_subcommand_is_refused_by_the_backlog_runner(self):
        from backlog_contract.support import BacklogRunner, ForbiddenBacklogCommand
        with tempfile.TemporaryDirectory(prefix="folio-doc-board-") as tmp:
            with self.assertRaises(ForbiddenBacklogCommand):
                BacklogRunner("/nonexistent/backlog", tmp).run([BOARD], cwd=tmp)


class DocScannerTests(unittest.TestCase):
    """Acceptance: the docs pass the WP-0 scanners (the in-tree ones now; WP-0a's prepub scan when it lands)."""

    def test_no_local_path_or_raw_bidi_character_in_the_docs(self):
        hits = []
        for doc in DOCS:
            text = doc_text(doc) or ""
            for number, line in enumerate(text.splitlines(), 1):
                hits += ["%s:%d: %s" % (doc, number, code) for code, rule in LOCAL_PATH_RULES if rule.search(line)]
            hits += ["%s: U+%04X x%d" % (doc, ord(char), count) for char, count in sorted(bidi_counts(text).items())]
        self.assertEqual(hits, [])

    def test_the_wp0a_prepub_scan_passes_on_the_docs(self):
        if PREPUB.exists():
            self.fail("WP-0a's scanner (tools/prepub) is in the tree: run it over %s here and drop this skip" % ", ".join(DOCS))
        self.skipTest("the WP-0a prepub scanner is on wp/0a-scan-route (WP-0a), which is not on this stack; WP-0a removes this skip")


LOCAL_API = "## Local API"
API_ROW = re.compile(r"^\| `(/api/[^`]+)` \| ([^|]+) \|")
# web.py answers these before the ROUTE_TABLE dispatch (the session exchange and the owner-only shutdown).
WEB_ROUTES = (("POST", "/api/session"), ("POST", "/api/shutdown"))
SAMPLES = {"<decision-id>": "dec_0123456789abcdef"}


def api_rows(text):
    """[(line, method, path)] of the README's Local API table (methods split; `any` rows are prose, not routes)."""
    rows, inside = [], False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            inside = line.strip() == LOCAL_API
            continue
        match = API_ROW.match(line) if inside else None
        if match:
            rows += [(number, method.strip(), match.group(1)) for method in match.group(2).split(",")]
    return rows


def sample(path):
    return re.sub(r"<[^<>]+>", lambda found: SAMPLES.get(found.group(0), "0123456789abcdef"), path)


def route_table_problems(text):
    """Routes the README's Local API table misses, and documented rows no route serves."""
    from folio.api import PLUGIN_PREFIX, ROUTE_TABLE
    core = [(method, pattern) for method, pattern in ROUTE_TABLE if method != "*"] + [(m, re.escape(p)) for m, p in WEB_ROUTES]
    mount = [pattern for method, pattern in ROUTE_TABLE if method == "*"]
    rows = api_rows(text)
    documented = [(number, method, path) for number, method, path in rows if method != "any"]
    problems = ["missing: %s %s" % (method, pattern) for method, pattern in core
                if not any(m == method and re.fullmatch(pattern, sample(path)) for _n, m, path in documented)]
    # A documented plugin route (one plugin's own path) is served by the one method-agnostic plugin mount.
    problems += ["README.md:%d: %s %s is not served" % (number, method, path) for number, method, path in documented
                 if not any(m == method and re.fullmatch(pattern, sample(path)) for m, pattern in core)
                 and not any(re.fullmatch(pattern, sample(path)) for pattern in mount)]
    if not any(method == "any" and path.startswith(PLUGIN_PREFIX + "<name>/") for _n, method, path in rows):
        problems.append("missing: the %s<name>/ plugin mount" % PLUGIN_PREFIX)
    return problems


class ReadmeRouteTableTests(unittest.TestCase):
    """The README's Local API table is the served route table: folio/api.py ROUTE_TABLE plus web.py's own routes."""

    def test_the_local_api_table_matches_the_served_routes(self):
        self.assertEqual(route_table_problems(doc_text(README) or ""), [])

    def test_the_check_catches_a_missing_and_an_unserved_route(self):
        table = ("## Local API\n\n| Route | Method | Purpose |\n| --- | --- | --- |\n"
                 "| `/api/state` | GET | Read |\n| `/api/backup` | GET | Cut |\n| `/api/plugins/<name>/...` | any | Plugins |\n"
                 "| `/api/plugins/ollama/suggest` | POST | One plugin route |\n\n## Next\n"
                 "| `/api/session` | POST | outside the section |\n")
        problems = route_table_problems(table)
        self.assertIn("README.md:6: GET /api/backup is not served", problems)
        self.assertIn("missing: POST /api/session", problems)
        self.assertIn("missing: POST /api/shutdown", problems)
        self.assertFalse(any("/api/state" in problem or "ollama" in problem for problem in problems), problems)
        self.assertIn("missing: the /api/plugins/<name>/ plugin mount", route_table_problems(table.replace("<name>/...", "ollama/x")))


LINK = re.compile(r"\]\(([^()\s]+)\)")


def slug(heading):
    """GitHub's heading anchor: lowercased, punctuation other than `-` and `_` dropped, spaces to `-`."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(text):
    return {slug(line.lstrip("#")) for line in without_fences(text).splitlines() if re.match(r"#{1,6} ", line)}


def link_problems(root, docs):
    """Relative links of the docs whose file is missing, or whose #anchor names no heading of the target."""
    problems = []
    root = Path(root)
    for doc in docs:
        text = doc_text(doc, root) or ""
        for number, line in enumerate(without_fences(text).splitlines(), 1):
            for target in LINK.findall(line):
                if re.match(r"[a-z]+:", target):
                    continue
                path, _hash, anchor = target.partition("#")
                resolved = (root / doc).parent / path if path else root / doc
                if not resolved.exists():
                    problems.append("%s:%d: %s does not exist" % (doc, number, path))
                elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved.read_text(encoding="utf-8")):
                    problems.append("%s:%d: no heading for #%s in %s" % (doc, number, anchor, resolved.name))
    return problems


def linking_docs(root=REPO_ROOT):
    """README.md and the top-level docs/*.md. Release records, archived plans and docs marked `> **Historical`
    near the top are records of 1.1.x and are not checked (their links may name tools that were cut)."""
    def current(path):
        return not any(line.startswith("> **Historical") for line in path.read_text(encoding="utf-8").splitlines()[:5])
    return ("README.md",) + tuple("docs/" + path.name for path in sorted((Path(root) / "docs").glob("*.md")) if current(path))


class DocLinkTests(unittest.TestCase):
    def test_relative_links_and_anchors_of_the_readme_and_docs_resolve(self):
        docs = linking_docs()
        self.assertTrue(set(support.DOCS) <= set(docs), docs)
        self.assertEqual(link_problems(REPO_ROOT, docs), [])

    def test_the_link_check_catches_a_missing_file_and_a_stale_anchor(self):
        with tempfile.TemporaryDirectory(prefix="folio-doc-links-") as tmp:
            plant(tmp, README, "## Plugins\n\n### Windows (WSL2 only)\n\n```sh\n# Not a heading\n```\n")
            plant(tmp, "docs/a.md", "[ok](../README.md#plugins) [ok](../README.md#windows-wsl2-only) [web](https://example.com/x)\n"
                  "[gone](../README.md#switchboard-freeze) [fenced](../README.md#not-a-heading) [file](missing.md) [self](#nope)\n")
            problems = link_problems(tmp, ("docs/a.md",))
        self.assertEqual(problems, ["docs/a.md:2: no heading for #switchboard-freeze in README.md",
                                    "docs/a.md:2: no heading for #not-a-heading in README.md",
                                    "docs/a.md:2: missing.md does not exist", "docs/a.md:2: no heading for #nope in a.md"])


def plant(root, doc, text):
    path = Path(root) / doc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ExtractorProofTests(unittest.TestCase):
    """The checks catch what they claim to, on planted docs (never on the real ones)."""

    def test_fences_comments_continuations_prompts_and_indented_fences(self):
        text = ("Intro `folio ui --no-open` and `folio/sync.py` and `backlog task list --plain`.\n\n"
                "```sh\nfolio --version   # prints the version\n$ folio doctor\n\n# a comment line\n"
                "folio migrate --from <workspace> \\\n  --inventory\n```\n\n"
                "1. Step:\n\n   ```sh\n   folio server-stop\n   ```\n\n"
                "```text\nHost tasks-example-channel\n```\n")
        fenced, problems = fenced_commands("README.md", text)
        self.assertEqual(problems, [])
        self.assertEqual([command.argv for command in fenced],
                         [("folio", "--version"), ("folio", "doctor"), ("folio", "migrate", "--from", "<workspace>", "--inventory"),
                          ("folio", "server-stop")])
        self.assertEqual([command.line for command in fenced], [4, 5, 8, 15])
        inline = inline_commands("README.md", text)
        self.assertEqual([command.argv for command in inline], [("folio", "ui", "--no-open"), ("backlog", "task", "list", "--plain")])

    def test_unlabelled_and_unknown_fences_and_unterminated_fences_are_problems(self):
        _fenced, problems = fenced_commands("README.md", "```\nfolio sync\n```\n\n```console\nfolio ui\n```\n\n```sh\nfolio ui\n")
        self.assertEqual(len(problems), 3, problems)
        self.assertEqual(sum("unterminated" in problem for problem in problems), 1, problems)
        self.assertEqual(sum("fence language" in problem for problem in problems), 2, problems)

    def test_the_wp12a_draft_spellings_the_landed_code_refuses_are_caught(self):
        """The drafts' commands that WP12b-1 found wrong against this tree and the landed branches."""
        planted = {
            "uv tool uninstall folio": "unlisted",
            "folio repair-ids": "argv",
            "folio sync": "argv",
            'folio brief --query "release plan"': "argv",
            "folio migrate --inventory --source <workspace>": "argv",
            "folio migrate --dry-run --source <workspace> --allow-list example-channel-allow-list.json --target <clone> --report dry-run-report.json": "argv",
            "folio migrate --apply --reviewed <report-sha256> --allow-list example-channel-allow-list.json --source <workspace> --target <clone>": "argv",
            "folio migrate --from <workspace> --apply --allow-list example-channel-allow-list.json --to <clone>": "argv",
            "folio migrate --from <workspace> --dry-run --report dry-run-report.json": "argv",
            "folio migrate --from <workspace> --inventory --dry-run --allow-list example-channel-allow-list.json": "argv",
            "folio migrate --from <workspace> --dry-run --allow-list example-channel-allow-list.json --to <clone>": "argv",
            "folio tasks list": "argv",
            "folio agent-guide": "argv",
            "folio backup --output backup.json": "argv",
            "folio tools install": "argv",
            "backlog " + BOARD: "argv",
        }
        for command, expected in planted.items():
            with self.subTest(command=command), tempfile.TemporaryDirectory(prefix="folio-doc-plant-") as tmp:
                plant(tmp, README, "```sh\n%s\n```\n" % command)
                _fences, unlisted, _placeholders, bad_argv = problems_for(tmp, (README,))
                self.assertTrue(unlisted, "every planted command is outside the inventory")
                if expected == "argv":
                    self.assertTrue(bad_argv, "the parser check misses %r" % command)

    def test_unknown_placeholders_and_board_spans_are_classified(self):
        with tempfile.TemporaryDirectory(prefix="folio-doc-plant-") as tmp:
            plant(tmp, README, "```sh\nsha256sum <report-sha256>\n```\n\nNever run `backlog %s`; use `backlog task list --plain`.\n"
                  "Also `folio nonsense now` and `folio tools ensure` and `folio usage nope`.\n" % BOARD)
            _fences, _unlisted, bad_placeholders, bad_argv = problems_for(tmp, (README,))
        self.assertEqual(len(bad_placeholders), 1)
        self.assertEqual(len(bad_argv), 2, bad_argv)
        self.assertIn("folio nonsense", bad_argv[0])
        self.assertIn("folio usage nope", bad_argv[1])

    def test_cut_commands_may_be_named_in_prose_but_never_fenced(self):
        with tempfile.TemporaryDirectory(prefix="folio-doc-plant-") as tmp:
            plant(tmp, README, "WP-6 removed `folio tasks …` and `folio backup`; WP-7 removed `folio projects link|unlink`.\n\n"
                  "```sh\nfolio backup --output backup.json\n```\n")
            _fences, _unlisted, _placeholders, bad_argv = problems_for(tmp, (README,))
        self.assertEqual(bad_argv, ["README.md:4: folio backup --output backup.json -> cut by WP-6: prose may name it, a fence never"])

    def test_a_fenced_board_command_and_a_release_build_path_fail_the_doc_checks(self):
        with tempfile.TemporaryDirectory(prefix="folio-doc-plant-") as tmp:
            plant(tmp, README, "```sh\nbrew install folio-workspace\ncurl -fLO https://example.com/releases/download/v1/x.tar.gz\n"
                  "backlog %s\n```\n" % BOARD)
            found, _problems = doc_commands(tmp, (README,))
        fenced = found[README][0]
        self.assertEqual([command.argv[0] for command in fenced], ["brew", "curl", "backlog"])
        self.assertIsNotNone(check_backlog_argv(fenced[2].argv, "fence"))
        self.assertIsNone(check_backlog_argv(fenced[2].argv, "inline"))
        hits = [word for command in fenced for word in RELEASE_BUILD_WORDS if word in " ".join(command.argv).lower()]
        self.assertEqual(sorted(set(hits)), sorted({"brew", "curl", "releases/download", ".tar.gz"}))


if __name__ == "__main__":
    unittest.main()
