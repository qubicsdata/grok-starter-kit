#!/usr/bin/env python3
"""Local CI entry point for the kit: runs every check in a fixed order.

Usage: python3 tools/ci_local.py [--release] [--with-folio]
                                 [--gitleaks PATH] [--trufflehog PATH]
                                 [--terms-file PATH]

Prints one line per step, `STEP <name>: PASS|FAIL|SKIP (<reason>)`, then a
SUMMARY line. Exit codes: 0 = no step failed (and, with --release, none was
skipped); 1 = at least one step failed; 2 = bad command line.

--terms-file, --gitleaks and --trufflehog are passed through to the scan steps
(clean-scan: tree plus term list; history-scan: history, headers, messages,
term list and the two scanner binaries). A check whose input is absent makes
its step SKIP, which --release turns into a failure.

Steps live in STEPS below, in run order. To add one, write a function that
takes the context (see `build_context`) and returns a StepResult, then append
`Step("<name>", <function>)` to STEPS. Stdlib only, Python 3.9+.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections import namedtuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN_SCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_scan.py")

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
STATUSES = (PASS, FAIL, SKIP)

Step = namedtuple("Step", "name run")
StepResult = namedtuple("StepResult", "status reason", defaults=("",))

# Lines of a failing subprocess's output shown under its STEP line.
OUTPUT_TAIL_LINES = 40
STEP_TIMEOUT_SECONDS = 1800


def run_command(ctx, argv):
    """Run argv from the repo root; return (returncode, combined output).

    No bytecode is written, so the clean-scan step never meets caches CI made.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.run(
            argv,
            cwd=ctx.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=STEP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return None, ""
    return proc.returncode, proc.stdout


def unittest_step(ctx, argv):
    """Run a unittest command; PASS with the test count, FAIL with output."""
    code, output = run_command(ctx, [sys.executable, "-m", "unittest"] + argv)
    if code is None:
        return StepResult(FAIL, "timed out after %ds" % STEP_TIMEOUT_SECONDS)
    match = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    count = int(match.group(1)) if match else 0
    if code != 0:
        ctx.failure_output = output
        return StepResult(FAIL, "unittest exit %d" % code)
    if count == 0:
        return StepResult(FAIL, "no tests ran")
    return StepResult(PASS, "%d tests" % count)


def step_structure(ctx):
    return unittest_step(ctx, ["tests.test_structure"])


def step_kit_tests(ctx):
    return unittest_step(ctx, ["discover", "-s", "tests", "-t", "."])


SCAN_COUNT_RE = re.compile(r"^([A-Z]+) (\d+)$")
SCAN_SKIP_RE = re.compile(r"^SKIP ([a-z]+)$")


HISTORY_ONLY_SKIPS = ("gitleaks", "trufflehog")


def scan_step(ctx, extra, ignored_skips=()):
    """Run tools/clean_scan.py over ctx.root; PASS on TOTAL 0, SKIP if a check
    did not run (no term list, no scanner binary, a binary file), FAIL on findings
    or a usage error. The reason holds codes and counts only."""
    argv = [sys.executable, CLEAN_SCAN, ctx.root] + list(extra)
    if ctx.terms_file:
        argv += ["--terms-file", ctx.terms_file]
    code, output = run_command(ctx, argv)
    if code is None:
        return StepResult(FAIL, "timed out after %ds" % STEP_TIMEOUT_SECONDS)
    if code not in (0, 1):
        ctx.failure_output = output
        return StepResult(FAIL, "scan usage error (exit %d)" % code)
    counts, skips, total = [], [], None
    for line in output.splitlines():
        match = SCAN_COUNT_RE.match(line)
        if match and match.group(1) == "TOTAL":
            total = int(match.group(2))
        elif match:
            counts.append(line)
        else:
            match = SCAN_SKIP_RE.match(line)
            if match and match.group(1) not in ignored_skips:
                skips.append(match.group(1))
    if total is None:
        ctx.failure_output = output
        return StepResult(FAIL, "no TOTAL line from the scan")
    reason = "TOTAL %d" % total
    if counts:
        reason += ": " + ", ".join(counts)
    if skips:
        reason += ", not run: " + ", ".join(skips)
    if code == 1 or total:
        ctx.failure_output = output
        return StepResult(FAIL, reason)
    if skips:
        return StepResult(SKIP, reason)
    return StepResult(PASS, reason)


def step_clean_scan(ctx):
    # The tree step does not run the history scanners; history-scan reports them.
    return scan_step(ctx, [], ignored_skips=HISTORY_ONLY_SKIPS)


def git_config_value(ctx, key):
    code, output = run_command(ctx, ["git", "config", key])
    return output.strip() if code == 0 else ""


def step_history_scan(ctx):
    """The history scan with the allowed identity built at run time from
    `git config user.name` / `user.email`, so the address never lands in a file."""
    if shutil.which("git") is None:
        return StepResult(SKIP, "git not installed")
    code, output = run_command(ctx, ["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0 or output.strip() != "true":
        return StepResult(SKIP, "not a git work tree")
    name = git_config_value(ctx, "user.name")
    email = git_config_value(ctx, "user.email")
    if not name or not email:
        return StepResult(SKIP, "no git identity configured (user.name / user.email)")
    extra = ["--history", "--allowed-identity", "%s <%s>" % (name, email)]
    for flag, value in (("--gitleaks", ctx.gitleaks), ("--trufflehog", ctx.trufflehog)):
        if value:
            extra += [flag, value]
    return scan_step(ctx, extra)


def step_sb(ctx):
    """The sb suite (second-brain/tests): config, search parity on both
    engines, the doctor and packaging; the rg-only tests skip without rg."""
    return unittest_step(ctx, ["discover", "-s", "second-brain/tests", "-p", "test_*.py"])


# --- folio: Folio's own suite, run in place from vendor/folio, only with --with-folio ---
FOLIO_BIN_ENV = "FOLIO_BACKLOG_BIN"
FOLIO_OPT_OUT_ENV = "FOLIO_BACKLOG_CONTRACT"
UNITTEST_SKIPPED_RE = re.compile(r"^(?:OK|FAILED) \(.*?skipped=(\d+)", re.MULTILINE)


def remove_bytecode_caches(top):
    """Folio's CLI tests start `python3 -I` subprocesses, which ignore PYTHONDONTWRITEBYTECODE;
    drop the __pycache__ folders they leave under `top` so the clean-scan step never meets them."""
    for dirpath, dirnames, _ in os.walk(top):
        for name in [d for d in dirnames if d == "__pycache__"]:
            shutil.rmtree(os.path.join(dirpath, name), ignore_errors=True)
            dirnames.remove(name)


def step_folio(ctx):
    """`python3 -m unittest discover -s tests -v` from vendor/folio. The pinned Backlog.md binary comes
    from FOLIO_BACKLOG_BIN at run time (never stored in the kit); without it the suite runs with
    Folio's explicit opt-out FOLIO_BACKLOG_CONTRACT=skip and the step is SKIP, so --release fails."""
    if not ctx.with_folio:
        return StepResult(SKIP, "not requested; run with --with-folio")
    folio = os.path.join(ctx.root, "vendor", "folio")
    if not os.path.isdir(os.path.join(folio, "tests")):
        return StepResult(FAIL, "vendor/folio/tests missing")
    backlog_bin = os.environ.get(FOLIO_BIN_ENV, "")
    if backlog_bin and not (os.path.isfile(backlog_bin) and os.access(backlog_bin, os.X_OK)):
        return StepResult(FAIL, "%s is not an executable file" % FOLIO_BIN_ENV)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.pop(FOLIO_OPT_OUT_ENV, None)
    if not backlog_bin:
        env.pop(FOLIO_BIN_ENV, None)
        env[FOLIO_OPT_OUT_ENV] = "skip"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=folio,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=STEP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return StepResult(FAIL, "timed out after %ds" % STEP_TIMEOUT_SECONDS)
    finally:
        remove_bytecode_caches(folio)
    output = proc.stdout
    match = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    count = int(match.group(1)) if match else 0
    if count == 0 and proc.returncode in (0, 5):  # Python 3.12+ exits 5 when nothing ran
        return StepResult(FAIL, "no tests ran")
    if proc.returncode != 0:
        ctx.failure_output = output
        return StepResult(FAIL, "unittest exit %d" % proc.returncode)
    skipped = UNITTEST_SKIPPED_RE.search(output)
    reason = "%d tests, %d skipped" % (count, int(skipped.group(1)) if skipped else 0)
    if not backlog_bin:
        return StepResult(SKIP, reason + "; Backlog.md contract not run (%s unset)" % FOLIO_BIN_ENV)
    return StepResult(PASS, reason)


# --- overwrite-protection harness
KIT_PLAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit_plan.py")
OVERWRITE_SUITE = os.path.join("tests", "overwrite")


def step_overwrite_harness(ctx):
    """The overwrite-protection harness (tests/overwrite): the six synthetic
    existing-setup fixtures and the contract tests against the reference
    planner tools/kit_plan.py. A missing planner is a failure, not a skip."""
    if not os.path.isdir(os.path.join(ctx.root, OVERWRITE_SUITE)):
        return StepResult(SKIP, "tests/overwrite not present")
    if not os.path.isfile(KIT_PLAN):
        return StepResult(FAIL, "tools/kit_plan.py is missing")
    return unittest_step(ctx, ["discover", "-s", OVERWRITE_SUITE, "-p", "test_*.py"])
# --- end overwrite-protection harness


# --- accelerator ---------------------------------------------------------------
ACCELERATOR_VENDOR = os.path.join("vendor", "accelerator")
ACCELERATOR_TESTS = os.path.join("tests", "accelerator")


def step_accelerator(ctx):
    """The kit-level suite for vendor/accelerator (scrub, identity, builder
    rename, pricing data, and the suite's own gate on a temp copy). It lives
    outside the `tests` package, so kit-tests does not run it twice."""
    if not os.path.isdir(os.path.join(ctx.root, ACCELERATOR_VENDOR)):
        return StepResult(SKIP, "no vendor/accelerator")
    return unittest_step(ctx, ["discover", "-s", ACCELERATOR_TESTS, "-t", ACCELERATOR_TESTS])
# --- end accelerator -----------------------------------------------------------


# --- runner tests (fail-closed sandbox: temp KIT_HOME, fake claude only) ---
def step_runner_tests(ctx):
    return unittest_step(ctx, ["discover", "-s", "runner/tests", "-t", "runner/tests"])
# --- end runner tests ---


# --- runner parameterization suite (runner/tests/k5) and the runner scan ---
K5_SUITE = "runner/tests/k5"


def step_runner_k5(ctx):
    """The runner parameterization suite; a red suite is a FAIL."""
    return unittest_step(ctx, ["discover", "-s", K5_SUITE, "-t", K5_SUITE])


def step_runner(ctx):
    """The clean-data scan on runner/ alone (plus --terms-file when given): the runner ships no owner
    strings. Same PASS / SKIP / FAIL rules and codes-only reason as clean-scan."""
    runner_dir = os.path.join(ctx.root, "runner")
    if not os.path.isdir(runner_dir):
        return StepResult(FAIL, "runner/ missing")
    sub = argparse.Namespace(**vars(ctx))
    sub.root = runner_dir
    sub.terms_file = getattr(ctx, "terms_file", None)
    result = scan_step(sub, [], ignored_skips=HISTORY_ONLY_SKIPS)
    ctx.failure_output = sub.failure_output
    return result
# --- end runner parameterization suite and the runner scan ---


STEPS = [
    Step("structure", step_structure),
    Step("kit-tests", step_kit_tests),
    Step("clean-scan", step_clean_scan),
    Step("history-scan", step_history_scan),
    Step("sb", step_sb),
    Step("accelerator", step_accelerator),
    Step("runner-tests", step_runner_tests),
    Step("runner-k5", step_runner_k5),
    Step("runner", step_runner),
    Step("overwrite-harness", step_overwrite_harness),
]


# --- pins ----------------------------------------------------------------------

VERIFY_PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_pins.py")
PINS_RESULT_RE = re.compile(r"^RESULT: (PASS|FAIL) \((.+)\)$", re.MULTILINE)


def step_pins(ctx):
    """tools/verify_pins.py on <root>/tools/pins.json: a placeholder on a
    required pin warns in dev mode and fails with --release; a malformed or
    missing pins file fails in both modes. Nothing is downloaded."""
    argv = [sys.executable, VERIFY_PINS, "--pins", os.path.join(ctx.root, "tools", "pins.json")]
    if ctx.release:
        argv.append("--release")
    code, output = run_command(ctx, argv)
    if code is None:
        return StepResult(FAIL, "timed out after %ds" % STEP_TIMEOUT_SECONDS)
    match = PINS_RESULT_RE.search(output)
    if code == 0 and match and match.group(1) == PASS:
        return StepResult(PASS, match.group(2))
    ctx.failure_output = output
    if match:
        return StepResult(FAIL, match.group(2))
    return StepResult(FAIL, "verify_pins exit %d" % code)


STEPS.append(Step("pins", step_pins))


# --- placeholders: no build-time sha placeholder left in a release tree ---
# Joined at run time, so this file (and its bytecode) never holds the placeholder itself.
SHA_PLACEHOLDER = "-".join(("<sha", "filled", "at", "build>"))
NOT_RELEASE_TREE = ".git"


def find_placeholders(root):
    """Every `<path>:<line>` under root (relative, in path order) holding SHA_PLACEHOLDER.
    `.git` is not part of the release tree and symlinks are never followed."""
    needle = SHA_PLACEHOLDER.encode()
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != NOT_RELEASE_TREE]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if name == NOT_RELEASE_TREE or os.path.islink(path):
                continue
            with open(path, "rb") as handle:
                data = handle.read()
            if needle not in data:
                continue
            rel = os.path.relpath(path, root)
            for number, line in enumerate(data.split(b"\n"), 1):
                if needle in line:
                    hits.append((rel, number))
    return ["%s:%d" % hit for hit in sorted(hits)]


def step_placeholders(ctx):
    """The release build fills every SHA_PLACEHOLDER (VENDORED.md source shas) before
    `--release` runs, so this step runs after every build and tree step (folio stays last).
    Fast mode PASSes with the count; with --release a leftover FAILs, every
    `<path>:<line>` listed under the STEP line."""
    locations = find_placeholders(ctx.root)
    ctx.failure_output = "\n".join(locations)
    if not locations:
        return StepResult(PASS, "0 left")
    if ctx.release:
        return StepResult(FAIL, "%d left, first at %s" % (len(locations), locations[0]))
    return StepResult(PASS, "%d left; --release fails" % len(locations))


STEPS.append(Step("placeholders", step_placeholders))  # after the build and tree steps
STEPS.append(Step("folio", step_folio))  # last: only with --with-folio


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="ci_local.py",
        description="Run the kit's local CI steps in order.",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="release mode: every SKIP counts as a failure",
    )
    parser.add_argument(
        "--with-folio",
        action="store_true",
        help="also run the Folio steps (vendor/folio)",
    )
    parser.add_argument("--gitleaks", metavar="PATH", help="path to a gitleaks binary")
    parser.add_argument("--trufflehog", metavar="PATH", help="path to a trufflehog binary")
    parser.add_argument(
        "--terms-file",
        metavar="PATH",
        help="term list for the clean-data scan (kept outside the kit)",
    )
    return parser.parse_args(argv)


def build_context(args, out):
    """The object every step receives: parsed flags plus `root` and `out`."""
    return argparse.Namespace(
        root=ROOT,
        out=out,
        release=args.release,
        with_folio=args.with_folio,
        gitleaks=args.gitleaks,
        trufflehog=args.trufflehog,
        terms_file=args.terms_file,
        failure_output="",
    )


def run_step(step, ctx):
    ctx.failure_output = ""
    try:
        result = step.run(ctx)
    except Exception as exc:  # a crashing step is a failed step, not a crashed run
        return StepResult(FAIL, "error: %s" % type(exc).__name__)
    if not isinstance(result, StepResult) or result.status not in STATUSES:
        return StepResult(FAIL, "invalid step result")
    return result


def format_line(name, result):
    line = "STEP %s: %s" % (name, result.status)
    if result.reason:
        line += " (%s)" % result.reason
    return line


def main(argv=None, steps=None, out=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    steps = STEPS if steps is None else steps
    out = sys.stdout if out is None else out
    ctx = build_context(args, out)

    counts = {PASS: 0, FAIL: 0, SKIP: 0}
    for step in steps:
        result = run_step(step, ctx)
        if result.status == SKIP and args.release:
            result = StepResult(FAIL, "release forbids SKIP: %s" % (result.reason or "skipped"))
        counts[result.status] += 1
        print(format_line(step.name, result), file=out)
        if result.status == FAIL and ctx.failure_output:
            for line in ctx.failure_output.rstrip("\n").splitlines()[-OUTPUT_TAIL_LINES:]:
                print("  | " + line, file=out)
        out.flush()

    ok = bool(steps) and counts[FAIL] == 0
    print(
        "SUMMARY: %d passed, %d failed, %d skipped%s -> %s"
        % (
            counts[PASS],
            counts[FAIL],
            counts[SKIP],
            " (release)" if args.release else "",
            "OK" if ok else "FAIL",
        ),
        file=out,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
