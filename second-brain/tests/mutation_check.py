#!/usr/bin/env python3
"""Mutation check for second-brain/bin/sb: the search tests must notice when
the python engine, the rg engine or the shared ranking is broken.

For each mutant below, one rule of sb is broken in a temporary COPY of bin/sb
(the real file is never touched), the search suites run against that copy
(via the KIT_SB environment variable that sbsupport.py honours), and the
mutant counts as "killed" when at least one test fails. The unmutated copy
runs first and must pass (else the check stops: a red suite kills every
mutant for free). Mutants marked rg need ripgrep on PATH; without it they are
reported as SKIPPED.

Usage:
    python3 second-brain/tests/mutation_check.py [--jobs N] [--only LABEL ...]

Output: one line per mutant, `KILLED <label> (<n> failing tests: <names>)`,
`SURVIVED <label>` or `SKIPPED <label> (rg not installed)`, then a summary.
Exit 0 when every mutant that ran was killed, 1 when one survived, a pattern
no longer matches the source (sb changed: update MUTANTS) or the baseline is
red. Stdlib only, Python 3.9+.
"""

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(os.path.dirname(HERE), "bin", "sb")
SUITES = ["test_config", "test_search", "test_parity", "test_parity_edges", "test_readonly", "test_doctor",
          "test_scan_key"]
SUITE_TIMEOUT = 900

# (label, needs rg, exact source text to replace, replacement). Each `old`
# must occur once in bin/sb.
MUTANTS = [
    # the python engine (parity with rg kills these)
    ("python.rank_input_order", True, "                found.append((n, text))\n",
     "                found.insert(0, (n, text))\n"),
    ("python.case_sensitive", True, "rx = re.compile(pattern, re.IGNORECASE)", "rx = re.compile(pattern)"),
    ("python.reads_binary_and_big_files", False,
     "        data = _read_text_file(os.path.join(brain.home, rel))\n        if data is None:\n            continue\n        found = []",
     "        with open(os.path.join(brain.home, rel), \"rb\") as fh:\n            data = fh.read()\n        found = []"),
    ("python.max_count", True, "                if len(found) >= MAX_COUNT:", "                if len(found) >= MAX_COUNT + 5:"),
    ("eligible.follows_file_symlinks", False, "st = os.lstat(os.path.join(self.home, rel))",
     "st = os.stat(os.path.join(self.home, rel))"),
    # the shared ranking (absolute expectations kill these)
    ("rank.order", False, "scored.sort(key=lambda x: (-x[0], x[1]))", "scored.sort(key=lambda x: (x[0], x[1]))"),
    ("rank.boost_paths", False, "        if _under(f, boost):\n            s += 4", "        if _under(f, boost):\n            s += 0"),
    ("rank.router_bonus", False, "for p in routed):\n            s += 8", "for p in routed):\n            s += 0"),
    ("rank.raw_penalty", False, "            s -= 6", "            s -= 0"),
    ("rank.path_terms", False, "len(pt) * 6", "len(pt) * 0"),
    ("rank.heading_bonus", False, '(3 if text.lstrip().startswith("#") else 0)', "0"),
    # the rg engine (parity with python kills these)
    ("rg.no_eligibility_filter", True, "if rel not in seen and brain.eligible(rel, raw):", "if rel not in seen:"),
    ("rg.no_late_nul_check", True, "        if binary[rel]:\n            continue", "        if False:\n            continue"),
    ("rg.honours_ignore_files", True, '"--no-config", "--no-ignore",', '"--no-config",'),
    ("rg.honours_rg_config", True, '"--no-config", "--no-ignore",', '"--no-ignore",'),
    ("rg.bom_sniffing", True, '"--encoding", "none", ', ""),
    ("rg.no_line_dedupe", True, "if rel not in seen or (rel, n) in lines_seen:", "if rel not in seen:"),
    # engine choice
    ("engine.auto_never_rg", True, 'choice = "rg" if rg else "python"', 'choice = "python"'),
    ("engine.env_ignored", False, 'choice = flag or environ.get("SB_ENGINE") or "auto"', 'choice = flag or "auto"'),
    ("engine.python_calls_rg", True, "    if engine == \"rg\":\n        files, hits = rg_engine",
     "    if rg:\n        files, hits = rg_engine"),
    # channels, deny rules, config
    ("channel.not_strict", False, "return not want or set(c) == {want}", "return not want or want in c"),
    ("channel.token_end", False, '+ r"(?![\\w-])")', '+ r"(?!\\w)")'),
    ("channel.longest_prefix", False, "key=lambda item: -len(item[0])", "key=lambda item: len(item[0])"),
    ("channel.name_hashes", False, "                if hit:\n                    c.add(hit)", "                if False:\n                    c.add(hit)"),
    ("deny.hidden", False, '            if part.startswith("."):\n                return True', '            if False:\n                return True'),
    ("deny.raw_roots", False, "        return not raw and _under(rel, self.s[\"raw_roots\"])", "        return False"),
    ("deny.router_file", False, "if not is_dir and rel.lower() == self.router_rel.lower():", "if False:"),
    ("secret.withheld", False, "        if SECRET_RE.search(text):", "        if False:"),
    ("config.sb_home", False, '    if environ.get("SB_HOME"):', "    if False:"),
    # the doctor (the doctor suite kills these)
    ("doctor.check4_off", False, "        if len(chans) == 1 and brain.folder_channel(f) not in chans:",
     "        if False:"),
    ("doctor.check4_first_folder_only", False,
     "        default = self.path_default(rel)\n        if default:\n            return default\n        first",
     "        first"),
    ("doctor.check4_prefix_not_token", False, '        return self.by_fold.get(fold(first)) or first',
     '        return next((c for c in self.channels if first.startswith(c)), first)'),
    ("doctor.check5_off", False, "            if chans and other and not other <= chans:", "            if False:"),
    ("doctor.check5_no_relative_paths", False,
     "    if src_dir:\n        candidates.append(_relnorm(src_dir + \"/\" + target))", "    if False:\n        pass"),
    ("doctor.check5_no_stems", False, "    return hits[0] if len(hits) == 1 else None", "    return None"),
    ("doctor.check5_ambiguous_stem", False, "    return hits[0] if len(hits) == 1 else None",
     "    return hits[0] if hits else None"),
    ("doctor.check5_no_block_list", False, "        while i < len(head) and LIST_ITEM_RE.match(head[i]):",
     "        while False:"),
    ("doctor.check5_no_wiki_links", False, "    targets.extend(WIKI_LINK_RE.findall(text))", "    pass"),
    ("doctor.check5_untagged_linker", False, "            if chans and other and not other <= chans:",
     "            if other and not other <= chans:"),
    ("doctor.check6_off", False,
     "            if row_channel is None or brain.folder_channel(_relnorm(p)) != row_channel:", "            if False:"),
    ("doctor.check6_two_channels_ok", False, "        row_channel = row_channel[0] if len(row_channel) == 1 else None",
     "        row_channel = row_channel[0] if row_channel else None"),
    ("doctor.check8_off", False, "        if any(personal_data_hint(line) for line in text.splitlines()):",
     "        if False:"),
    ("doctor.check8_no_email", False, "    if EMAIL_HINT_RE.search(line) or IBAN_HINT_RE.search(line):",
     "    if IBAN_HINT_RE.search(line):"),
    ("doctor.check8_no_iban", False, "    if EMAIL_HINT_RE.search(line) or IBAN_HINT_RE.search(line):",
     "    if EMAIL_HINT_RE.search(line):"),
    ("doctor.check8_no_birth_date", False, "    if BIRTH_RE.search(line) and DATE_RE.search(line):", "    if False:"),
    ("doctor.check8_dates_are_phones", False, "        if DATE_RE.search(run):\n            continue",
     "        if False:\n            continue"),
    ("doctor.check8_short_phones", False, "        if 9 <= sum(1 for c in run if c.isdigit()) <= 15:",
     "        if 5 <= sum(1 for c in run if c.isdigit()) <= 15:"),
    ("doctor.check8_is_a_failure", False, '        if any(personal_data_hint(line) for line in text.splitlines()):\n            findings.add(("WARN", 8, f))',
     '        if any(personal_data_hint(line) for line in text.splitlines()):\n            findings.add(("FAIL", 8, f))'),
    ("doctor.check9_off", False, '        if info["unknown"]:\n            add(9, f)', "        if False:\n            add(9, f)"),
    ("doctor.check9_no_labels", False, '                else:\n                    info["unknown"] += 1',
     '                else:\n                    pass'),
    ("doctor.check9_comment_is_a_token", False, '        value = re.split(r"\\s#", value)[0]', "        pass"),
    ("doctor.exit_1_wins", False, "    if any(check != 1 for _, check, _ in fails):\n        return 3",
     "    if any(check != 1 for _, check, _ in fails) and not any(check == 1 for _, check, _ in fails):\n        return 3"),
    ("doctor.top_level_files_are_notes", False, 'if f.endswith(".md") and "/" in f]', 'if f.endswith(".md")]'),
    # the scan key (test_scan_key kills these)
    ("key.unkeyed_hash", False, 'return hmac.new(key, word.encode("utf-8"), hashlib.sha256).hexdigest()[:16]',
     'return hashlib.sha256(word.encode("utf-8")).hexdigest()[:16]'),
    ("key.missing_key_drops_hashes", False,
     '        except ScanKeyError as exc:\n            print("sb: %s" % exc, file=sys.stderr)\n            return 2\n    if opts["doctor"]:',
     '        except ScanKeyError as exc:\n            settings["name_hashes"] = {}\n    if opts["doctor"]:'),
    ("key.mode_unchecked", False, "        if not _private_mode(st):\n            raise ScanKeyError(\"the scan key",
     "        if False:\n            raise ScanKeyError(\"the scan key"),
    ("key.follows_symlinks", False, 'os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |', "os.O_RDONLY |"),
    ("key.size_unchecked", False, "    if len(data) != KEY_BYTES:", "    if not data:"),
    ("key.not_a_regular_file_ok", False, "        if not stat.S_ISREG(st.st_mode):\n            raise ScanKeyError(\"the scan key",
     "        if False:\n            raise ScanKeyError(\"the scan key"),
    ("key.brain_guard_off", False, "        if self.name_hashes and self.name_key is None:\n            raise",
     "        if False:\n            raise"),
    ("key.xdg_ignored", False, '    base = environ.get("XDG_CONFIG_HOME") or ""', '    base = ""'),
    ("key.relative_xdg_used", False, "    if not os.path.isabs(base):\n        home", "    if not base:\n        home"),
    ("init.file_mode_0644", False, "            os.fchmod(fd, 0o600)", "            os.fchmod(fd, 0o644)"),
    ("init.dir_mode_0755", False, "    os.chmod(path, 0o700)  # the umask", "    os.chmod(path, 0o755)  # the umask"),
    ("init.folder_mode_unchecked", False, "    if not _private_mode(st):\n        raise ScanKeyError(\"the key folder",
     "    if False:\n        raise ScanKeyError(\"the key folder"),
    ("init.constant_key", False, "secrets.token_bytes(KEY_BYTES)", "bytes(KEY_BYTES)"),
    ("init.prints_the_key", False, "    return path\n\n\ndef hash_names",
     "    print(open(path, \"rb\").read().hex())\n    return path\n\n\ndef hash_names"),
    ("hash_name.echoes_the_line", False, '"sb: line %d is not one word (letters and digits only); nothing was printed" % n',
     '"sb: line %d (%s) is not one word" % (n, line)'),
    ("hash_name.not_folded", False, "        word = fold(line).strip()", "        word = line.strip()"),
    ("hash_name.several_words_ok", False, "        if not NAME_WORD_RE.fullmatch(word):", "        if not NAME_WORD_RE.search(word):"),
    ("doctor.switches_ignored", False, '        findings.add(("FAIL" if flag is None or flags[flag] else "WARN", check, path))',
     '        findings.add(("FAIL", check, path))'),
]

FAILING_RE = re.compile(r"^(?:FAIL|ERROR): (\S+)", re.MULTILINE)


def mutate(source, old, new):
    if source.count(old) != 1:
        return None
    return source.replace(old, new)


def run_suite(label, text):
    work = tempfile.mkdtemp(prefix="sb-mutant-")
    try:
        copy = os.path.join(work, "sb")
        with open(copy, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(copy, 0o755)
        env = dict(os.environ, KIT_SB=copy, PYTHONDONTWRITEBYTECODE="1")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest"] + SUITES, cwd=HERE, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                timeout=SUITE_TIMEOUT,
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

    with open(SB, encoding="utf-8") as handle:
        source = handle.read()
    _, red, names = run_suite("baseline", source)
    if red or names:
        print("BASELINE FAILED (%d failing tests): fix the suite first" % len(names))
        return 1
    have_rg = shutil.which("rg") is not None
    selected = [m for m in MUTANTS if not args.only or m[0] in args.only]
    jobs, stale, skipped = [], [], []
    for label, needs_rg, old, new in selected:
        mutated = mutate(source, old, new)
        if mutated is None:
            stale.append(label)
        elif needs_rg and not have_rg:
            skipped.append(label)
        else:
            jobs.append((label, mutated))
    for label in stale:
        print("STALE %s (pattern not found once in the source)" % label)
    for label in skipped:
        print("SKIPPED %s (rg not installed)" % label)

    killed = survived = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for label, dead, names in pool.map(lambda job: run_suite(*job), jobs):
            if dead:
                killed += 1
                shown = ", ".join(n.rsplit(".", 1)[-1] if n.count(".") else n for n in names[:3])
                more = "" if len(names) <= 3 else ", +%d" % (len(names) - 3)
                print("KILLED %s (%d failing tests: %s%s)" % (label, len(names), shown, more))
            else:
                survived += 1
                print("SURVIVED %s" % label)
    print("SUMMARY: %d killed, %d survived, %d stale, %d skipped of %d mutants"
          % (killed, survived, len(stale), len(skipped), len(selected)))
    return 0 if survived == 0 and not stale else 1


if __name__ == "__main__":
    sys.exit(main())
