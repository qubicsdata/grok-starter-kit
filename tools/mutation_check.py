#!/usr/bin/env python3
"""Mutation check for tools/clean_scan.py: every rule must have a canary.

For each mutant below, one rule of the scanner is disabled in a temporary COPY
of tools/clean_scan.py (the real file is never touched), the scan suite under
tests/scan/ runs against that copy (via the KIT_CLEAN_SCAN environment
variable that tests/scan/support.py honours), and the mutant counts as
"killed" when at least one test fails. A surviving mutant means a rule has no
test that would notice its loss.

Usage:
    python3 tools/mutation_check.py [--jobs N] [--only LABEL ...]

Output: one line per mutant, `KILLED <label> (<n> failing tests: <names>)` or
`SURVIVED <label>`, then a summary. Exit 0 when every mutant was killed, 1 when
one survived or a mutant pattern no longer matches the source (the scanner
changed: update MUTANTS), 2 on a bad command line. Stdlib only, Python 3.9+.
"""

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
CLEAN_SCAN = os.path.join(TOOLS, "clean_scan.py")
SUITE = [sys.executable, "-m", "unittest", "discover", "-s", "tests/scan", "-p", "test_*.py"]
SUITE_TIMEOUT = 900

NEVER = 're.compile(r"(?!x)x"),'

# (label, exact source text to replace, replacement). Each `old` must occur once.
MUTANTS = [
    ("secret.key_block", 're.compile(r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY(?: BLOCK)?-----"),', NEVER),
    ("secret.github_token", 're.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36,}"),', NEVER),
    ("secret.sk_token", 're.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\\-]{20,}"),', NEVER),
    ("secret.aws_key_id", 're.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Za-z0-9])"),', NEVER),
    ("secret.slack_token", 're.compile(r"(?<![A-Za-z0-9])xox[abeopsr]-[A-Za-z0-9\\-]{10,}"),', NEVER),
    ("secret.jwt", 're.compile(r"(?<![A-Za-z0-9_\\-])eyJ[A-Za-z0-9_\\-]{10,}\\.[A-Za-z0-9_\\-]{6,}(?:\\.[A-Za-z0-9_\\-]+)?"),', NEVER),
    ("secret.assignment", "for regex in (SECRET_ASSIGN_RE, BEARER_RE):", "for regex in (BEARER_RE,):"),
    ("secret.bearer", "for regex in (SECRET_ASSIGN_RE, BEARER_RE):", "for regex in (SECRET_ASSIGN_RE,):"),
    ("secret.no_double_count", 'if _spans_overlap(m.span("v"), spans):', "if False:"),
    ("secret.placeholders", "def _looks_secret(value, quoted):\n", "def _looks_secret(value, quoted):\n    return True\n"),
    ("email", 'add("EMAIL", emails)', 'add("EMAIL", 0)'),
    ("email.lookalike_domain",
     'if d in EXAMPLE_DOMAINS or d.endswith(tuple("." + x for x in EXAMPLE_DOMAINS)):',
     "if d.startswith(EXAMPLE_DOMAINS):"),
    ("email.version_is_not_address", 'if not TLD_RE.fullmatch(d.rsplit(".", 1)[-1]):', "if False:"),
    ("noreply", 'add("NOREPLY", noreply)', 'add("NOREPLY", 0)'),
    ("noreply.not_email", 'return "NOREPLY"', 'return "EMAIL"'),
    ("bidi", 'add("BIDI", len(BIDI_RE.findall(text)))', 'add("BIDI", 0)'),
    ("ctrl", 'add("CTRL", len(CTRL_RE.findall(text)))', 'add("CTRL", 0)'),
    ("homepath.workspace", "re.compile(PATH_L + re.escape(WORKSPACE_ROOT) + WORD_R),", NEVER),
    ("homepath.linux_home",
     're.compile(PATH_L + re.escape(LINUX_HOME) + r"(?!" + ALLOWED_HOME_USER + WORD_R + r")[A-Za-z0-9._\\-]+"),',
     NEVER),
    ("homepath.home_user_allowed",
     'r"(?!" + ALLOWED_HOME_USER + WORD_R + r")[A-Za-z0-9._\\-]+"',
     'r"[A-Za-z0-9._\\-]+"'),
    ("homepath.mac_home", 're.compile(PATH_L + re.escape(MAC_HOME) + r"[A-Za-z0-9._\\-]+"),', NEVER),
    ("homepath.mac_temp", 're.compile(PATH_L + r"(?:/private)?" + re.escape(MAC_TMP)),', NEVER),
    ("homepath.relative_folder_is_not_root", 'PATH_L = r"(?<![A-Za-z0-9_.~/\\-])"', 'PATH_L = r""'),
    ("opspath", 'add("OPSPATH", len(OPSPATH_RE.findall(text)))', 'add("OPSPATH", 0)'),
    ("alias.ch", 're.compile(WORD_L + re.escape(ALIAS_CH) + r"[a-z]" + WORD_R),', NEVER),
    ("alias.cl", 're.compile(WORD_L + re.escape(ALIAS_CL) + r"[a-z0-9]+(?:-[a-z0-9]+)*" + WORD_R),', NEVER),
    ("alias.whole_token", 're.compile(WORD_L + re.escape(ALIAS_CH) + r"[a-z]" + WORD_R),',
     're.compile(re.escape(ALIAS_CH) + r"[a-z]"),'),
    ("uuid", 'add("UUID", count_uuids(text))', 'add("UUID", 0)'),
    ("uuid.zero_allowed", 'if set(m.group(0)) - set("0-")', "if True"),
    ("capture.file_name", "if REAL_NAME_RE.search(name):", "if False:"),
    ("capture.usage_fields", 'self.add("CAPTURE", count_capture_screen(text))', 'self.add("CAPTURE", 0)'),
    ("capture.only_usage_screens", "    if not USAGE_SCREEN_RE.search(text):\n        return 0\n", ""),
    ("capture.status_header", "if len(parts) >= 3 and not parts[2].startswith(EXAMPLE_PREFIX):", "if False:"),
    ("superpowers", 'add("SUPERPOWERS", len(SUPERPOWERS_RE.findall(text)))', 'add("SUPERPOWERS", 0)'),
    ("struct.gitmodules", 'if name == ".gitmodules":', "if False:"),
    ("struct.nested_git", 'if name == ".git":\n                    if rel:\n                        self.add("STRUCT")',
     'if name == ".git":\n                    if False:\n                        self.add("STRUCT")'),
    ("struct.own_git_skipped", 'if name == ".git":\n                    if rel:', 'if name == ".git" and rel:\n                    if rel:'),
    ("struct.gitlink_index", "                continue\n            self.add(\"STRUCT\")", "                continue\n            pass"),
    ("struct.gitlink_history", 'self.seen_gitlinks.add(rel)\n                self.add("STRUCT")',
     'self.seen_gitlinks.add(rel)\n                pass'),
    ("terms.content", 'self.add("TERMS", self.count_terms(text, rel, False))', 'self.add("TERMS", 0)'),
    ("terms.names", 'self.add("TERMS", self.count_terms(name, rel, is_dir))', 'self.add("TERMS", 0)'),
    ("terms.allow_globs", "if term.allowed_at(rel, is_dir):", "if False:"),
    ("terms.case_sensitive_flag", "if case_sensitive or len(term)", "if len(term)"),
    ("terms.short_term_as_cs", "if case_sensitive or len(term) == SHORT_TERM_LEN:", "if case_sensitive:"),
    ("terms.short_term_not_shorter", "len(term) == SHORT_TERM_LEN", "len(term) <= SHORT_TERM_LEN"),
    ("terms.short_term_not_longer", "len(term) == SHORT_TERM_LEN", "len(term) >= SHORT_TERM_LEN"),
    ("terms.refuse_inside_tree",
     "if terms_real == real or terms_real.startswith(real.rstrip(os.sep) + os.sep):", "if False:"),
    ("hdr", "if identity.strip() != self.allowed_identity:", "if False:"),
    ("hdr.identity_required", "if args.history and allowed is None:", "if False:"),
    ("hdr.identity_shape", "if not IDENTITY_RE.match(args.allowed_identity.strip()):", "if False:"),
    ("msg", 'self.add("MSG", hits)', 'self.add("MSG", 0)'),
    ("history.blobs", 'self.scan_bytes(content, paths.get(sha, ""))', "pass"),
    ("history.blob_dedupe", "if top is not None and blob_id(data, self.hash_algorithms[top]) in self.seen_blobs:",
     "if False:"),
    ("history.tree_names", "self.check_name(name, rel, mode == TREE_MODE, rel)", "pass"),
    ("gitleaks", 'self.add("GITLEAKS", findings)', 'self.add("GITLEAKS", 0)'),
    ("trufflehog", 'self.add("TRUFFLEHOG", findings)', 'self.add("TRUFFLEHOG", 0)'),
    ("tool_env.gitleaks_vars", '("GITLEAKS_", "TRUFFLEHOG_")', '("TRUFFLEHOG_",)'),
    ("tool_env.trufflehog_vars", '("GITLEAKS_", "TRUFFLEHOG_")', '("GITLEAKS_",)'),
    ("tool_env.whole_environment",
     'env = {k: v for k, v in os.environ.items() if not k.startswith(("GITLEAKS_", "TRUFFLEHOG_"))}',
     "env = dict(os.environ)"),
    ("tool_env.other_variables_kept",
     'env = {k: v for k, v in os.environ.items() if not k.startswith(("GITLEAKS_", "TRUFFLEHOG_"))}',
     "env = {}"),
    ("binary.content_skip", '    if b"\\x00" in data[:BINARY_PROBE_BYTES]:\n        return None\n', ""),
    ("binary.image_magic", "    if data.startswith(IMAGE_MAGIC):\n        return True\n", ""),
    ("binary.png_full_signature", 'b"\\x89PNG\\r\\n\\x1a\\n",  # PNG', 'b"\\x89PNG",  # PNG'),
    ("binary.webp", "return data[:4] == WEBP_RIFF and data[8:12] == WEBP_TAG", "return False"),
    ("binary.webp_tag", "return data[:4] == WEBP_RIFF and data[8:12] == WEBP_TAG", "return data[:4] == WEBP_RIFF"),
    ("binary.other_still_skips", "            if is_image(data):\n", "            if True:\n"),
    ("binary.images_counted", "self.images += 1", "pass"),
    ("binary.line", 'lines.append("BINARY %d" % self.images)', "pass"),
    ("binary.not_in_total", "return sum(self.counts.values())", "return sum(self.counts.values()) + self.images"),
    ("symlinks.not_followed",
     "                    is_link = entry.is_symlink()\n"
     "                    is_dir = not is_link and entry.is_dir(follow_symlinks=False)\n"
     "                    is_file = not is_link and entry.is_file(follow_symlinks=False)\n",
     "                    is_link = False\n"
     "                    is_dir = entry.is_dir()\n"
     "                    is_file = entry.is_file()\n"),
    ("exit.findings_exit_1", "return EXIT_FINDINGS if scan.total() else EXIT_CLEAN", "return EXIT_CLEAN"),
]

RESULT_RE = re.compile(r"^(?:FAILED \((.*)\)|OK)\s*$", re.MULTILINE)
FAILING_RE = re.compile(r"^(?:FAIL|ERROR): (\S+)", re.MULTILINE)


def mutate(source, old, new):
    if source.count(old) != 1:
        return None
    return source.replace(old, new)


def run_mutant(label, mutated):
    work = tempfile.mkdtemp(prefix="kit-mutant-")
    try:
        copy = os.path.join(work, "clean_scan.py")
        with open(copy, "w", encoding="utf-8") as handle:
            handle.write(mutated)
        env = dict(os.environ)
        env["KIT_CLEAN_SCAN"] = copy
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            proc = subprocess.run(
                SUITE, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, timeout=SUITE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return label, False, ["<suite timed out>"]
        names = sorted(set(FAILING_RE.findall(proc.stdout)))
        return label, proc.returncode != 0 and bool(names), names
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mutation_check.py", description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1), help="parallel suite runs")
    parser.add_argument("--only", nargs="*", metavar="LABEL", help="run only these mutants")
    args = parser.parse_args(argv)

    with open(CLEAN_SCAN, encoding="utf-8") as handle:
        source = handle.read()
    selected = [m for m in MUTANTS if not args.only or m[0] in args.only]
    jobs = []
    stale = []
    for label, old, new in selected:
        mutated = mutate(source, old, new)
        if mutated is None:
            stale.append(label)
        else:
            jobs.append((label, mutated))
    for label in stale:
        print("STALE %s (pattern not found once in the source)" % label)

    killed = survived = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for label, dead, names in pool.map(lambda job: run_mutant(*job), jobs):
            if dead:
                killed += 1
                shown = ", ".join(n.rsplit(".", 1)[-1] if n.count(".") else n for n in names[:3])
                more = "" if len(names) <= 3 else ", +%d" % (len(names) - 3)
                print("KILLED %s (%d failing tests: %s%s)" % (label, len(names), shown, more))
            else:
                survived += 1
                print("SURVIVED %s" % label)
    print("SUMMARY: %d killed, %d survived, %d stale of %d mutants" % (killed, survived, len(stale), len(selected)))
    return 0 if survived == 0 and not stale else 1


if __name__ == "__main__":
    sys.exit(main())
