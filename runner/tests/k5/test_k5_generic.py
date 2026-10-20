"""The shipped runner is generic: the routes table in runner.config.example.json, a complete example config (the
test overlay only adds synthetic experiments), and no notes from the source setup (approvals, dated rule notes,
work-package jargon, host-specific env names or leftover names) in the runner's code, tests and docs.
Messages name files, lines and rule names, never the matched text."""
import glob, hashlib, io, json, os, re, tokenize, unittest
import k5support as K
import helpers
from helpers import TempEnv, RUNNER_DIR, BIN
from crlib import route as R, sched as S, usage as U
from crlib.common import iso, to_epoch

KIT_ROOT = os.path.dirname(RUNNER_DIR)
NOW = to_epoch("2026-01-06T12:10:00+00:00")
ZERO = {"total": 0, "opus": 0, "external": []}

OPUS_ROUTES = ("security", "implement", "review-fix", "hard-debug", "architecture", "plan", "review", "pre-review",
               "test", "test-hardening")
SONNET_ROUTES = ("docs", "rebase", "rebase-fallout", "rename", "pr-body", "mechanical", "refactor",
                 "test-hardening-nonsecurity")
HAIKU_OPT_IN = {"format", "log-triage", "log-summary"}
FABLE_ROUTES = {"fable-pre-review", "fable-implement", "fable-security", "fable-refactor"}
PROFILES = {"lean", "lean_no_superpowers", "lean_no_superpowers_keep_review"}
REASON_WORDS = {"Opus", "Sonnet", "Haiku", "Fable", "PR", "TDD"}  # the only capitalized words a reason may hold


def example():
    return K.raw_example()


def text_files():
    """Every text file the runner ships, except generated test data (fixtures)."""
    out = []
    for p in sorted(glob.glob(os.path.join(RUNNER_DIR, "**", "*"), recursive=True)):
        rel = os.path.relpath(p, RUNNER_DIR)
        if not os.path.isfile(p) or "__pycache__" in rel or rel.startswith(("fixtures" + os.sep,
                                                                           os.path.join("tests", "fixtures"))):
            continue
        if rel == "LICENSE":
            continue
        out.append(p)
    return out


def comments_and_docs(path):
    """(lineno, text) of the prose in a file: comments and docstrings for Python, comment lines for shell,
    every line for Markdown and the JSON `_comment*` values."""
    text = K.read(path)
    if path.endswith(".md"):
        return list(enumerate(text.splitlines(), 1))
    if path.endswith(".json"):
        out = []
        for n, line in enumerate(text.splitlines(), 1):
            if re.match(r'\s*"_comment\w*"\s*:', line):
                out.append((n, line))
        return out
    if text.startswith("#!/usr/bin/env python3") or path.endswith(".py"):
        out, prev = [], None
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, SyntaxError):
            return list(enumerate(text.splitlines(), 1))
        for tok in toks:
            if tok.type == tokenize.COMMENT:
                out.append((tok.start[0], tok.string))
            elif tok.type == tokenize.STRING and prev in (None, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                                                          tokenize.NL):
                for i, line in enumerate(tok.string.splitlines()):
                    out.append((tok.start[0] + i, line))
            if tok.type not in (tokenize.COMMENT, tokenize.NL):
                prev = tok.type
        return out
    return [(n, line[line.index("#"):]) for n, line in enumerate(text.splitlines(), 1) if "#" in line]


# ---------------- the routes table ----------------

class RoutesTableTests(unittest.TestCase):
    def setUp(self):
        self.ex = example()
        self.routes = self.ex.get("routes") or {}

    def test_models_and_fallbacks(self):
        fb = {m: v.get("fallback") for m, v in (self.ex.get("models") or {}).items()}
        self.assertEqual(fb, {"opus": "sonnet", "opusplan": "sonnet", "sonnet": "opus", "haiku": "sonnet",
                              "fable": "opus"})
        self.assertEqual(self.ex.get("default_model"), "opus")

    def test_opus_for_security_architecture_and_core_work(self):
        for tt in OPUS_ROUTES:
            with self.subTest(route=tt):
                self.assertIn(tt, self.routes)
                self.assertEqual((self.routes[tt]["model"], self.routes[tt].get("effort")), ("opus", "high"))

    def test_sonnet_for_routine_edits_and_docs(self):
        for tt in SONNET_ROUTES:
            with self.subTest(route=tt):
                self.assertIn(tt, self.routes)
                self.assertEqual(self.routes[tt]["model"], "sonnet")

    def test_haiku_only_when_opted_in(self):
        self.assertIs(self.ex.get("haiku_opt_in_default"), False)
        self.assertTrue(self.routes)
        self.assertEqual([t for t, r in self.routes.items() if r["model"] == "haiku"], [])
        self.assertEqual({t for t, r in self.routes.items() if r.get("haiku_opt_in")}, HAIKU_OPT_IN)
        cfg = helpers._subst(self.ex, "/home/user/kit")
        for tt in sorted(HAIKU_OPT_IN):
            self.assertEqual(R.route(cfg, task_type=tt)["model"], "sonnet")
            self.assertEqual(R.route(cfg, task_type=tt, allow_haiku=True)["model"], "haiku")

    def test_fable_routes_are_optional_names(self):
        fable = {t for t, r in self.routes.items() if r["model"] == "fable"}
        self.assertEqual(fable, FABLE_ROUTES)
        self.assertEqual([t for t in self.routes if t.startswith("fable-") and t not in fable], [])

    def test_default_route_and_medium(self):
        self.assertEqual(self.routes.get("default", {}).get("model"), "opus")
        self.assertEqual(self.routes.get("medium", {}).get("model"), "opusplan")

    def test_route_names_are_generic(self):
        self.assertTrue(self.routes)
        for tt in self.routes:
            with self.subTest(route=tt):
                self.assertRegex(tt, r"^[a-z][a-z0-9-]*$")
                self.assertNotRegex(tt, r"(?:^|-)w" + r"p(?:-|$)", "work-package jargon in a route name")

    def test_reasons_are_generic(self):
        self.assertTrue(self.routes)
        for tt, r in self.routes.items():
            reason = r.get("reason", "")
            with self.subTest(route=tt):
                self.assertTrue(reason)
                self.assertLessEqual(len(reason), 90)
                self.assertNotRegex(reason, r"\d", "a date or number in the reason")
                self.assertNotRegex(reason, r"(?i)\b(?:via|approved|ruling|experiment|see)\b")
                caps = {w for w in re.findall(r"\b[A-Z]\w*", reason)} - REASON_WORDS
                self.assertEqual(caps, set(), "a name in the reason")

    def test_aliases_point_at_routes(self):
        al = {k: v for k, v in (self.ex.get("task_type_aliases") or {}).items() if not k.startswith("_")}
        self.assertTrue(al)
        for k, v in al.items():
            with self.subTest(alias=k):
                self.assertIn(v, self.routes)
                self.assertNotIn(k, self.routes)

    def test_experiments_are_empty(self):
        self.assertEqual(self.ex.get("experiments"), {})
        self.assertEqual([t for t, r in self.routes.items() if "experiment" in r], [])

    def test_profiles_turn_off_only_public_plugins(self):
        profs = {k: v for k, v in (self.ex.get("profiles") or {}).items() if not k.startswith("_")}
        self.assertEqual(set(profs), PROFILES)
        self.assertIs(self.ex.get("profiles_enabled"), True)
        for name, p in profs.items():
            for plugin in (p.get("settings") or {}).get("enabledPlugins", {}):
                with self.subTest(profile=name):
                    self.assertTrue(plugin.endswith("@claude-plugins-official"), "a non-public plugin in %s" % name)
        self.assertEqual({r.get("profile") for r in self.routes.values()} - PROFILES, set())

    def test_tdd_skill_only_for_security_and_core_logic(self):
        cfg = helpers._subst(self.ex, "/home/user/kit")
        off = lambda tt: {k for k, v in (R.route(cfg, task_type=tt)["settings"] or {}).get("enabledPlugins", {}).items()
                          if v is False}
        for tt in ("security", "implement", "review-fix", "hard-debug", "fable-implement", "fable-security"):
            self.assertNotIn("superpowers@claude-plugins-official", off(tt), tt)
        for tt in ("architecture", "plan", "docs", "rebase", "review", "medium", "log-triage"):
            self.assertIn("superpowers@claude-plugins-official", off(tt), tt)

    def test_every_route_and_alias_resolves_with_the_example_alone(self):
        cfg = helpers._subst(self.ex, "/home/user/kit")
        names = list(self.routes) + [k for k in (self.ex.get("task_type_aliases") or {}) if not k.startswith("_")]
        self.assertTrue(names)
        for tt in names:
            with self.subTest(task_type=tt):
                info = R.route(cfg, task_type=tt)
                self.assertEqual(info["source"], "route")
                self.assertTrue(R.claude_args(info))


# ---------------- a complete example ----------------

class CompleteExampleTests(unittest.TestCase):
    def test_overlay_adds_only_synthetic_experiments(self):
        with open(helpers.TEST_OVERLAY) as f:
            overlay = json.load(f)
        self.assertEqual({k for k in overlay if not k.startswith("_")}, {"experiments"})

    def test_safe_limit_values_live_in_the_example(self):
        ex = example()
        b, u, p = ex["backlog"], ex["usage"], ex["policy"]
        self.assertEqual((b.get("reserve_slots"), b.get("reserve_opus"), b.get("max_attempts")), (1, 1, 2))
        self.assertEqual(b.get("priorities"), ["P0", "P1", "P2"])
        self.assertIs(b.get("require_soak_window"), False)
        f = b["weekly_pacing"]["fable"]
        self.assertEqual((f.get("near_park_pct"), f.get("fresh_minutes"), f.get("stale_near_cap_minutes"),
                          f.get("stale_block_minutes")), (75, 30, 45, 90))
        self.assertEqual((u.get("near_park_min_probe_spacing_minutes"), u.get("window_hours"), u.get("weekly_days")),
                         (5, 5, 7))
        self.assertEqual(u.get("probe_unset_env"), [])
        self.assertEqual((p["weekly"].get("restricted_noncritical_after_reset_minutes"),
                          p.get("heavy_after_reset_minutes"), p.get("external_default_family")), (60, 60, "opus"))

    def test_no_work_package_reserve_keys(self):
        jargon = "_for_w" + "p"  # split so this file does not match its own scans
        self.assertNotIn("reserve_slots" + jargon, json.dumps(example()))
        self.assertFalse(re.search(jargon + r"\b|\bw" + r"p_waiting\b", K.read(os.path.join(BIN, "crlib", "sched.py"))),
                         "work-package reserve names in crlib/sched.py")

    def test_scheduler_runs_on_the_example_alone(self):
        with TempEnv() as t:
            cfg = helpers._subst(example(), t.d)
            wt = os.path.join(t.d, "wt")
            os.makedirs(wt)
            pd = cfg["backlog"]["prompt_dir"]
            os.makedirs(pd, exist_ok=True)
            with open(os.path.join(pd, "E1.md"), "w") as f:
                f.write("do E1")
            os.makedirs(os.path.dirname(cfg["backlog"]["queue"]), exist_ok=True)
            with open(cfg["backlog"]["queue"], "w") as f:
                f.write("jobs:\n  - id: E1\n    title: example\n    priority: P1\n    task_type: docs\n"
                        "    channel: direct\n    status: queued\n    worktree: %s\n" % wt)
            cfg["backlog"]["enabled"] = True
            helpers.enforce_sandbox(cfg, t.d)
            os.environ["CR_NOW"] = iso(NOW)  # backlog_tick re-checks quiet hours on the clock (TempEnv restores env)
            eff = U.effective(cfg, U.state(cfg, NOW, include_local=False), NOW)
            eff = dict(eff, session={"pct": 5, "basis": "observed", "resets_at": "2026-01-06T15:00:00+00:00"},
                       weekly={"pct": 5, "basis": "observed", "resets_at": "2026-01-09T18:00:00+00:00"},
                       session_elapsed_min=30)
            launched = []
            out = S.backlog_tick(cfg, eff, {"park": None, "local": None}, ZERO, 0, to_epoch("2026-01-06T12:10:00+00:00"),
                                 launcher=lambda c, spec: launched.append(spec) or 4999999,
                                 procs_alive=lambda pid: True)
            self.assertEqual(out.get("started"), ["E1"], out.get("held"))
            self.assertEqual(launched[0]["task_type"], "docs")
            start, info = S.decide(cfg, eff, None, [{"id": "q1", "task_type": "security", "priority": 0}], ZERO, NOW)
            self.assertEqual([j["id"] for j in start], ["q1"], info)


# ---------------- generic wording ----------------

# Hashes (sha256 of the lowercased text) of names from the source setup that must not come back.
LEFTOVER_DIGESTS = {
    (13, "dfb0dd30c3d32d74e62e1b531f4bbdca9828601e3bedde8309bc6c965c6f4ad5"),
    (6, "afe2a7303a1cd95d2001050307724ba3a3cd7245ac9450a5838f9207c61c0676"),
    (14, "ca3527105c373062eb25e6b645de3c5950f72146a37bb96c95f98648b3ec4ca0"),
}
# Prose rules: approval and rule-change notes, setup dates, work-package jargon, build job ids, people/agent roles.
PROSE_RULES = {
    "approval note": re.compile(r"(?i)\bruling\b|\bapproved\b|\bapproval by\b|\bsigned off\b"),
    "setup date tag": re.compile(r"\(\s*(?:[A-Za-z ,]+)?20\d\d-\d\d-\d\d[^)]*\)|(?i:operating limits,?\s*20\d\d)"),
    "history note": re.compile(r"\(was \d|(?i:\blive config\b)"),
    "work-package jargon": re.compile(r"\bWPs?\b|(?i:\bwp(?=[-_$<\d]|\b))|_w" + r"p\b"),
    "build job id": re.compile(r"\bKIT-[A-Z0-9]|\bK\d+(?:-\d+)?\b"),
}
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
# Env names of one particular host (sandbox and editor sockets); pieces are split so this file never matches.
HOST_ENV = re.compile(r"\b(?:" + "|".join(("SA" + "ND_", "CUR" + "SOR_", "__CUR" + "SOR", "CLAUDE_CODE_MESS" + "AGING_"))
                      + r")\w*")


def contains_digest(text, length, digest):
    low = text.lower()
    return any(hashlib.sha256(low[i:i + length].encode()).hexdigest() == digest for i in range(len(low) - length + 1))


class GenericTextTests(unittest.TestCase):
    def test_the_file_list_covers_code_tests_and_docs(self):
        rels = {os.path.relpath(p, RUNNER_DIR) for p in text_files()}
        for must in ("DESIGN.md", "runner.config.example.json", os.path.join("bin", "cr"),
                     os.path.join("bin", "crlib", "sched.py"), os.path.join("tests", "test_sched.py"),
                     os.path.join("tests", "k5", "README.md")):
            self.assertIn(must, rels)
        self.assertFalse([r for r in rels if r.startswith(os.path.join("tests", "fixtures"))])

    def test_no_setup_notes_in_comments_and_docs(self):
        bad = []
        for p in text_files():
            for n, line in comments_and_docs(p):
                for rule, rx in PROSE_RULES.items():
                    if rx.search(line):
                        bad.append("%s:%d %s" % (os.path.relpath(p, KIT_ROOT), n, rule))
        self.assertEqual(bad, [])

    def test_no_dates_in_runner_code_docs_or_config_prose(self):
        files = [p for p in text_files() if not os.path.relpath(p, RUNNER_DIR).startswith("tests" + os.sep)]
        bad = ["%s:%d" % (os.path.relpath(p, KIT_ROOT), n) for p in files for n, line in comments_and_docs(p)
               if DATE_RE.search(line)]
        self.assertEqual(bad, [])

    def test_no_work_package_words_in_code_strings(self):
        bad = []
        for p in text_files():
            for n, line in enumerate(K.read(p).splitlines(), 1):
                if PROSE_RULES["work-package jargon"].search(line):
                    bad.append("%s:%d" % (os.path.relpath(p, KIT_ROOT), n))
        self.assertEqual(bad, [])

    def test_no_host_specific_env_names(self):
        bad = ["%s:%d" % (os.path.relpath(p, KIT_ROOT), n) for p in text_files()
               for n, line in enumerate(K.read(p).splitlines(), 1) if HOST_ENV.search(line)]
        self.assertEqual(bad, [])

    def test_no_leftover_names_from_the_source(self):
        bad = ["%s (leftover of length %d)" % (os.path.relpath(p, KIT_ROOT), n) for p in text_files()
               for n, d in sorted(LEFTOVER_DIGESTS) if contains_digest(K.read(p), n, d)]
        self.assertEqual(bad, [])

    def test_the_rules_have_teeth(self):
        hits = lambda s: sorted(r for r, rx in PROSE_RULES.items() if rx.search(s))
        self.assertEqual(hits("# quiet hours (operating limits 2026-01-02)"), ["setup date tag"])
        self.assertEqual(hits("# see the 2026 ruling"), ["approval note"])
        self.assertEqual(hits("# cap 3 (was 5)"), ["history note"])
        self.assertEqual(hits('hold.append("W' + 'P work wins")'), ["work-package jargon"])
        self.assertEqual(hits("usage: run-claude.sh <w" + "p-number>"), ["work-package jargon"])
        self.assertEqual(hits("reserve_slots_for_w" + "p"), ["work-package jargon"])
        self.assertEqual(hits("# added in KIT-X1"), ["build job id"])
        self.assertEqual(hits("Contract for K9-2: the K9 sandbox"), ["build job id"])
        self.assertEqual(hits("# Resets Jan 9, 6:00pm (UTC); wpt1 is a label"), [])
        self.assertTrue(contains_digest("x CLAUDE-" + "Router y", *sorted(LEFTOVER_DIGESTS)[1]))
        self.assertTrue(HOST_ENV.search("unset SA" + "ND_EXAMPLE"))


# ---------------- the /usage probe environment ----------------

class ProbeEnvTests(unittest.TestCase):
    def unset_targets(self, cfg):
        calls = []

        class Result:
            stdout = json.dumps({"type": "result", "num_turns": 0, "modelUsage": {}, "result": ""})

        U.probe_print(cfg, runner=lambda argv, **kw: calls.append(argv) or Result())
        argv = calls[0]
        return [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-u"]

    def test_probe_unsets_only_generic_names_by_default(self):
        with TempEnv() as t:
            self.assertEqual(sorted(self.unset_targets(t.cfg)), ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"])

    def test_probe_unsets_the_configured_names(self):
        with TempEnv() as t:
            t.cfg["usage"]["probe_unset_env"] = ["EXAMPLE_HOST_TOKEN", "bad name"]
            self.assertEqual(sorted(self.unset_targets(t.cfg)),
                             ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "EXAMPLE_HOST_TOKEN"])


if __name__ == "__main__":
    unittest.main()
