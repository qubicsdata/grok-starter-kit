#!/usr/bin/env python3
"""Regenerate EVERY runner fixture: runner/tests/fixtures/ (what the copied tests read) and runner/fixtures/
(the documented shapes, see runner/fixtures/FIXTURES.md).

Every value here is invented: user@example.invalid, "Example Org", /home/user/example-project, all-zero UUIDs,
example-* names. The /usage layouts mirror what the parser sees from `claude -p /usage`: 3-space indents, block
bars (U+2580..U+259F) padded to 50 columns, a U+2594 rule under the tab bar, middle dots, em dashes, an empty 0%
bar padded to column 54, time-only / month+day / hour-only reset lines and a "(Fable)" weekly line. The
ANSI/CRLF screen is only built in memory (ANSI below): ESC and CR are control characters, which no file under
runner/ may hold. Never paste a real capture or stream log here: test_fixture_privacy.py fails the build on
non-example emails, non-zero UUIDs, home paths other than /home/user, control/bidi characters and `*_real_*`
names, and test_fixtures_generated.py fails on any fixture this script does not produce.

Run:  python3 runner/tests/make_synthetic_fixtures.py            (writes the fixtures)
      python3 runner/tests/make_synthetic_fixtures.py --check    (exit 1 if a fixture is missing or stale)
      ... [--out DIR]                                            (a runner/-shaped tree elsewhere, for tests)
Stdlib only, Python 3.9+.
"""
import argparse, json, os, sys

RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = "(Etc/GMT-3)"  # label only: the parser reads reset times in the local zone (the tests pin UTC+3)
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
I = "   "
B = "█"


def bar(full, part="", pct="0%"):
    """62-char usage row: 3-space indent, 50-col bar, space, 'NN% used'."""
    return I + (B * full + part).ljust(50) + " " + pct + " used"


EMPTY0 = " " * 54 + "0% used"  # empty bar: the TUI pads the 0% label to column 54

# ---------------- `claude /usage` screens (tests/fixtures) ----------------

HEADER = [
    "  Claude Code v0.0.0-example · example-model · Example Plan · /home/user/example-project",
    "  ~/example-project (example)",
    "▔" * 180 + " ◐ Status · Config · Usage · Stats",
    I + "Settings:  Status   Config   Usage (tab)",
    "",
    I + "Overview",
    "",
]
ACCOUNT = [
    I + "Version: 0.0.0-example",
    I + "Session ID: 00000000-0000",
    I + "Model: example-model",
    I + "cwd: /home/user/example-project/example-subdir",
    I + "Organization: Example Org (example-org-0000) · synthetic",
]
BODY = [
    "",
    "",
    I + "Example usage notice heading",
    I + "This synthetic paragraph stands in for the long notice text that the real screen shows here; "
        + "it carries no account data.",
    "",
    I + "Example line one · synthetic value one example",
    I + "Example line two · synthetic value two example",
    "",
    I + "Plan limits shown below are synthetic",
    "",
    I + "Current session",
    bar(13, "", "26%"),
    I + "Resets 5:49pm " + TZ,
    "",
    I + "Current week (all models)",
    bar(14, "▍", "29%"),
    I + "Resets Oct 16, 5:59pm " + TZ,
    "",
    I + "Current week (Fable)",
    EMPTY0,
    I + "Resets Oct 16, 6pm " + TZ,
    "",
    I + "What's contributing to your limits usage?",
    I + "Synthetic breakdown — example-project sessions account for most example usage",
    "",
    I + "Last 24h · synthetic totals · example-model 100% · no real numbers",
    "",
    I + "Example contributor A (synthetic)",
    "    example-project/session-a · 0 tokens · placeholder row for layout",
    "    example-project/session-b",
    "",
    I + "Example contributor B (synthetic) · subagents",
    "    example-subagent — placeholder row for layout testing",
    "    example-subagent-two · 0 tokens · synthetic",
    "",
    I + "Example contributor C (synthetic) · tools and MCP",
    "    example-tool · 0 tokens · synthetic row for layout",
    "    " + "Scroll for more ↓ " + "synthetic padding " * 10,
]


def screen(with_email=False):
    acct = list(ACCOUNT)
    if with_email:
        acct.insert(0, I + "Email: user@example.invalid")
    return "\n".join(HEADER + acct + BODY)


FRESH = "\n".join([
    I + "Usage (synthetic fresh-window example)",
    "",
    I + "Current session",
    EMPTY0,  # brand-new window: 0% and no Resets line
    "",
    I + "Current week (all models)",
    bar(40, "▌", "81%"),
    I + "Resets Oct 16, 5:59pm " + TZ,
    "",
    I + "Current week (Fable)",
    EMPTY0,
    I + "Resets Oct 16, 6pm " + TZ,
    "",
])

PRINT = "\n".join([
    "Synthetic `claude -p /usage` output for Example Org (example-plan)",
    "",
    "Current session: 5% used · resets Oct 15, 10:50pm " + TZ,
    "Current week (all models): 30% used · resets Oct 16, 6pm " + TZ,
    "Current week (Fable): 0% used · resets Oct 16, 6pm " + TZ,
    "",
    "What's contributing to your limits usage?",
    "Synthetic breakdown — example-project sessions account for most example usage in this made-up window.",
    "",
    "Last 24h · synthetic totals",
    "  example-project/session-a",
    "  example-project/session-b · placeholder",
    "  example-subagent · placeholder row for layout",
    "  Tokens: 0 input · 0 output · 0 cache read (synthetic)",
    "  Models: example-model 100% (synthetic)",
    "  Cost: $0.00 (synthetic)",
    "  Share: 0% (synthetic)",
    "",
    "Last 7d · synthetic totals",
    "  example-project/session-a",
    "  example-project/session-b · placeholder",
    "  example-subagent · placeholder row for layout",
    "  Tokens: 0 input · 0 output · 0 cache read (synthetic)",
    "  Models: example-model 100% (synthetic)",
    "  Cost: $0.00 (synthetic)",
    "  Share: 0% (synthetic)",
])

E = "\x1b["
# Terminal-capture style, IN MEMORY ONLY: SGR colour codes inside body lines, box-drawing frame rules, CRLF line
# ends, full-width 100% bar, decimal percent, hour-only reset. Headings and "Resets" stay at line start because
# the parser keys on line prefixes.
ANSI = "\r\n".join([
    "╭" + "─" * 58 + "╮",
    I + E + "1mEmail:" + E + "22m " + E + "36muser@example.invalid" + E + "39m",
    I + "Organization: Example Org",
    "─" * 60,
    I + "Current session",
    I + E + "38;5;75m" + B * 6 + "▎" + E + "39m" + " " * 43 + " " + E + "1m12.5% used" + E + "22m",
    I + "Resets 11pm " + TZ + E + "0m",
    "",
    I + "Current week (all models)",
    I + E + "38;5;214m" + B * 33 + E + "39m" + " " * 17 + " 66% used",
    I + "Resets Oct 16, 5:59pm " + TZ + E + "0m",
    "",
    I + "Current week (Fable)",
    I + E + "38;5;196m" + B * 50 + E + "39m" + " 100% used",
    I + "Resets Oct 16, 6pm " + TZ,
    "╰" + "─" * 58 + "╯",
    "",
])

# ---------------- Claude Code session transcripts (tests/fixtures/projects) ----------------
# test_usage.LocalTests: 9 assistant lines with usage = 7 messages + 1 duplicate (a resumed session repeats a
# message) + 1 "<synthetic>" message. Blocks (5 h): 10-02 10:00 | 10-10 08:00, 08:30, 12:59 | 10-10 13:05 |
# 10-11 02:00, 02:30 (current at 03:00). Outside the 7-day window: the 999-token message on 10-02.

CWD = "/home/user/example-project"


def _j(obj):
    return json.dumps(obj, separators=(",", ":"))


def assistant(n, ts, model, out, inp=10, cache_read=1000, cache_create=100, dup_of=None):
    mid = "msg_example_%02d" % (dup_of or n)
    return _j({"parentUuid": ZERO_UUID, "isSidechain": False, "type": "assistant", "timestamp": ts,
               "sessionId": ZERO_UUID, "cwd": CWD, "version": "0.0.0-example", "gitBranch": "example-branch",
               "requestId": "req_example_%02d" % (dup_of or n), "uuid": ZERO_UUID,
               "message": {"id": mid, "type": "message", "role": "assistant", "model": model,
                           "content": [{"type": "text", "text": "Example reply %d (synthetic)." % n}],
                           "usage": {"input_tokens": inp, "output_tokens": out,
                                     "cache_read_input_tokens": cache_read,
                                     "cache_creation_input_tokens": cache_create}}})


SESSION_A = "\n".join([
    _j({"type": "summary", "summary": "Example synthetic session", "leafUuid": ZERO_UUID}),
    _j({"type": "user", "timestamp": "2026-10-02T09:59:30Z", "sessionId": ZERO_UUID, "cwd": CWD, "uuid": ZERO_UUID,
        "message": {"role": "user", "content": "Example prompt: summarize the assistant usage for this example"}}),
    assistant(1, "2026-10-02T10:00:00Z", "claude-opus-5-5", 999),
    assistant(2, "2026-10-10T08:00:00Z", "claude-opus-5-5", 100),
    assistant(3, "2026-10-10T08:30:00Z", "claude-opus-5-5", 100),
    _j({"type": "assistant", "timestamp": "2026-10-10T08:31:00Z", "sessionId": ZERO_UUID, "uuid": ZERO_UUID,
        "message": {"id": "msg_example_03b", "role": "assistant", "model": "claude-opus-5-5",
                    "content": [{"type": "text", "text": "Example streamed part without token counts."}]}}),
    assistant(4, "2026-10-10T12:59:00Z", "claude-opus-5-5", 100),
    '{"type": "assistant", "message": {"usage": {"output_tokens": 5',  # truncated line (a crash mid-write)
]) + "\n"

SESSION_B = "\n".join([
    assistant(3, "2026-10-10T08:30:00Z", "claude-opus-5-5", 100),  # resumed session repeats message 3
    assistant(5, "2026-10-10T13:05:00Z", "claude-sonnet-5-5", 50),
    assistant(6, "2026-10-10T13:06:00Z", "<synthetic>", 0, inp=0, cache_read=0, cache_create=0),
    assistant(7, "2026-10-11T02:00:00Z", "claude-opus-5-5", 300),
    assistant(8, "2026-10-11T02:30:00Z", "claude-haiku-5-5", 7),
]) + "\n"

# ---------------- backlog queues (tests/fixtures) ----------------

BACKLOG_QUEUE = """\
# Synthetic backlog queue for test_backlog.py (example data only). {WT} is replaced by a temp worktree.
version: 1
updated: 2026-10-15
jobs:
  - id: X1
    title: "P2 docs job # not a comment"   # a real comment after a quoted value
    priority: P2
    task_type: analysis/docs
    model: sonnet
    channel: direct
    worktree: {WT}
    status: queued
  - id: X2
    title: P1 implementation job
    priority: P1
    task_type: implement
    model: opus
    effort: high
    channel: direct
    worktree: {WT}
    status: queued
  - id: X3
    title: script-channel job (no prompt, never dispatched)
    priority: P1
    task_type: docs
    channel: script
    worktree: {WT}
    status: queued
  - id: X4
    title: follow-up of X2
    priority: P1
    task_type: docs
    model: sonnet
    depends_on: [X2]
    channel: direct
    worktree: {WT}
    status: queued
  - id: X5
    title: low-priority job
    priority: P3
    task_type: docs
    channel: direct
    worktree: {WT}
    status: queued
  - id: X6
    title: worktree not prepared
    priority: P1
    task_type: docs
    channel: direct
    worktree: /home/user/example-missing-worktree
    status: queued
  - id: X7
    title: blocked job
    priority: P1
    task_type: docs
    channel: direct
    worktree: {WT}
    status: blocked
"""


def _large_queue():
    jobs = [
        ("B01", "Example core module", "P1", "implement", "opus", "", ""),
        ("B02", "Example docs pass", "P2", "analysis/docs", "sonnet", "", "    group: example-docs\n"),
        ("B03", "Example tests for the core module", "P1", "test", "opus", "[B01]", ""),
        ("B04", "Example security review of B01", "P1", "security", "opus", "[B01]", "    effort: high\n"),
        ("B05", "Example refactor, stacked on B01", "P2", "refactor", "sonnet", "[B01]",
         "    stack_on: example/b01-core\n    commit: yes\n"),
        ("B06", "Example metrics digest", "P2", "metrics", "", "", "    trigger: weekly-example\n"),
        ("B07", "Example script-only job", "P1", "docs", "none", "", "    channel_note: \"runs outside the runner\"\n"),
        ("B08", "Example Fable pre-review", "P1", "fable-pre-review", "fable", "[B03, B04]", ""),
        ("B09", "Example rename sweep", "P3", "rename", "sonnet", "", ""),
        ("B10", "Example rebase", "P2", "rebase", "sonnet", "[B05]", "    group: example-docs\n"),
        ("B11", "Example log triage", "P2", "log-triage", "", "", "    experiment: autocompact\n"),
        ("B12", "Example blocked job", "P1", "docs", "sonnet", "", ""),
        ("B13", "Example final gate", "P0", "mechanical", "sonnet", "[B08, B10, B11]", ""),
    ]
    out = ["# Synthetic large backlog queue (example data only): the shape of a long-running queue.",
           "# Read-only test input for B.parse_queue_yaml (comments, quoting, lists, triggers, groups, stacking).",
           "version: 1",
           "owner: example-owner",
           "updated: \"2026-10-15T12:00:00+03:00\"",
           "",
           "jobs:"]
    for jid, title, prio, tt, model, deps, extra in jobs:
        out.append("  - id: %s" % jid)
        out.append("    title: \"%s\"" % title)
        out.append("    priority: %s   # P0-P2 are auto-dispatched" % prio if jid == "B01" else "    priority: %s" % prio)
        out.append("    task_type: %s" % tt)
        if model:
            out.append("    model: %s" % model)
        if deps:
            out.append("    depends_on: %s" % deps)
        out.append("    channel: %s" % ("script" if jid == "B07" else "direct"))
        out.append("    worktree: /home/user/example-worktrees/%s" % jid.lower())
        out.append("    status: %s" % ("blocked" if jid == "B12" else "queued"))
        if extra:
            out.append(extra.rstrip("\n"))
        if jid == "B06":
            out.append("")
            out.append("  # a comment between jobs")
    return "\n".join(out) + "\n"


# ---------------- test config overlay (tests/fixtures) ----------------
# helpers.TempEnv builds each test config from runner/runner.config.example.json plus THIS overlay, which may only
# ADD keys the example lacks (helpers refuses overrides), so every test checks the example's own values. The
# example is complete; the overlay only adds two synthetic experiments (the example ships `experiments: {}`).


def _overlay():
    return {
        "_comment": "TEST OVERLAY (synthetic): only adds test experiments to the example config, never overriding "
                    "a value; generated by tests/make_synthetic_fixtures.py.",
        "experiments": {
            "autocompact": {"enabled": False, "flags": ["--autocompact", "200k"],
                            "apply_to": ["implement", "security", "review-fix"]},
            "prompt_cache_ttl": {"enabled": False, "settings": {"promptCacheTtl": "5m"}, "apply_to": []},
        },
    }


# ---------------- documented shapes (runner/fixtures) ----------------
# 2026-01-09: five-hour window resets 15:00 UTC (1767970800), weekly window 18:00 UTC (1767981600).

RESET5, RESET7 = 1767970800, 1767981600

TREE_SCREEN = "\n".join([
    "  Claude Code v0.0.0-example · example-model · Example Plan · /home/user/example-project",
    "  ~/example-project (example)",
    I + "Settings:  Status   Config   Usage (tab)",
    "",
    I + "Current session",
    bar(21, "", "42%"),
    I + "Resets 3:00pm (UTC)",
    "",
    I + "Current week (all models)",
    bar(31, "", "61%"),
    I + "Resets Jan 9, 6:00pm (UTC)",
    "",
    I + "Current week (Fable)",
    bar(16, "", "33%"),
    I + "Resets Jan 9, 6:00pm (UTC)",
]) + "\n"


def event(status, rtype, util, five, seven):
    return {"type": "rate_limit_event", "session_id": ZERO_UUID,
            "rate_limit_info": {"status": status, "rateLimitType": rtype,
                                "resetsAt": RESET5 if rtype == "five_hour" else RESET7, "utilization": util,
                                "unifiedWindows": {"five_hour": {"utilization": five, "resetsAt": RESET5},
                                                   "seven_day": {"utilization": seven, "resetsAt": RESET7}},
                                "overageStatus": "disabled"}}


EVENTS = [event("allowed", "five_hour", 0.42, 0.42, 0.61),
          event("allowed_warning", "seven_day", 0.76, 0.55, 0.76),
          event("rejected", "five_hour", 1.0, 1.0, 0.79)]


def stream(model, events, result_text, is_error=False):
    """A `claude -p --output-format stream-json --verbose` log: init, assistant turn, events, result line."""
    init = {"type": "system", "subtype": "init", "session_id": ZERO_UUID, "cwd": CWD, "model": model,
            "tools": ["Read", "Edit"], "mcp_servers": [], "permissionMode": "acceptEdits", "uuid": ZERO_UUID}
    turn = {"type": "assistant", "session_id": ZERO_UUID, "uuid": ZERO_UUID,
            "message": {"id": "msg_example_s1", "role": "assistant", "model": model,
                        "content": [{"type": "text", "text": "Example streamed reply (synthetic)."}],
                        "usage": {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 30,
                                  "cache_creation_input_tokens": 40}}}
    res = {"type": "result", "subtype": "error_during_execution" if is_error else "success", "is_error": is_error,
           "result": result_text, "session_id": ZERO_UUID, "num_turns": 1, "duration_ms": 1234,
           "api_error_status": 429 if is_error else None, "total_cost_usd": 0.0,
           "modelUsage": {model: {"inputTokens": 10, "outputTokens": 20, "cacheReadInputTokens": 30,
                                  "cacheCreationInputTokens": 40, "costUSD": 0.0}}}
    return "\n".join([_j(init), _j(turn)] + [_j(e) for e in events] + [_j(res)]) + "\n"


def build_files():
    """{path relative to runner/: text}. Deterministic; the only source of every runner fixture."""
    tf = os.path.join("tests", "fixtures")
    proj = os.path.join(tf, "projects", "-home-user-example-project")
    return {
        os.path.join(tf, "usage_screen_synthetic_1744.txt"): screen() + "\n",
        os.path.join(tf, "usage_screen_with_example_email.txt"): screen(with_email=True) + "\n",
        os.path.join(tf, "usage_screen_fresh_window.txt"): FRESH,
        os.path.join(tf, "usage_print_synthetic_1801.txt"): PRINT,
        os.path.join(proj, "example-session-a.jsonl"): SESSION_A,
        os.path.join(proj, "example-session-b.jsonl"): SESSION_B,
        os.path.join(tf, "backlog_queue.yaml"): BACKLOG_QUEUE,
        os.path.join(tf, "backlog_queue_large.yaml"): _large_queue(),
        os.path.join(tf, "router_test_overlay.json"): json.dumps(_overlay(), indent=1) + "\n",
        os.path.join("fixtures", "usage_screen_synthetic.txt"): TREE_SCREEN,
        os.path.join("fixtures", "rate_limit_events_synthetic.jsonl"): "".join(_j(e) + "\n" for e in EVENTS),
        os.path.join("fixtures", "stream_allowed_synthetic.jsonl"):
            stream("claude-sonnet-5-5", [EVENTS[0], EVENTS[0]], "OK (synthetic)"),
        os.path.join("fixtures", "stream_rejected_synthetic.jsonl"):
            stream("claude-sonnet-5-5", [EVENTS[1], EVENTS[2]], "You've hit your limit · resets 3pm (UTC)",
                   is_error=True),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="make_synthetic_fixtures.py", description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=RUNNER_DIR, help="runner/-shaped output root (default: this kit's runner/)")
    ap.add_argument("--check", action="store_true", help="compare only; exit 1 on a missing or stale fixture")
    a = ap.parse_args(argv)
    bad = 0
    for rel, text in sorted(build_files().items()):
        p = os.path.join(a.out, rel)
        data = text.encode("utf-8")
        if a.check:
            try:
                with open(p, "rb") as f:
                    same = f.read() == data
            except FileNotFoundError:
                same = False
            if not same:
                bad += 1
                print("stale or missing:", rel)
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        print("wrote", rel, len(data), "bytes")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
