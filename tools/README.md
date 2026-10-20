# tools/

Helper scripts for checking the kit. Stdlib-only Python 3.9+; nothing to install.

| Script | Purpose |
|---|---|
| `ci_local.py` | the local CI entry point: runs every check in a fixed order |
| `clean_scan.py` | the kit clean-data scan: counts owner-data findings, never shows them |
| `mutation_check.py` | dev check: disables one scanner rule at a time (in a copy) and confirms its canary test goes red |
| `kit_plan.py` | the reference planner behind every `AGENTS.md` checkpoint: `--dry-run` proposes (text, or `--json`), `--apply --approved <sha256>` adds only what is missing, `--choose <group>=<item>` picks one option of a decision; contract in `KIT-PLAN-SPEC.md`, harness in `tests/overwrite/` |
| `verify_pins.py` | checks `pins.json` (the pinned versions and checksums of `EXTERNAL-DEPENDENCIES.md`) and a downloaded file against its pin; downloads nothing |

## `ci_local.py`: the local CI entry point

The kit has no hosted CI. Run every check from the repo root with:

```
python3 tools/ci_local.py
```

Each step prints one line, then a summary:

```
STEP structure: PASS (10 tests)
STEP kit-tests: PASS (214 tests)
STEP clean-scan: SKIP (TOTAL 0, not run: terms)
STEP history-scan: SKIP (TOTAL 0, not run: gitleaks, trufflehog, terms)
STEP sb: PASS (153 tests)
SUMMARY: 3 passed, 0 failed, 2 skipped -> OK
```

A step reports `PASS`, `FAIL` or `SKIP`, with a reason in brackets. Every step runs even after a failure; a failing step's last output lines are shown under its `STEP` line (prefixed `  | `). Steps run their subprocesses with `PYTHONDONTWRITEBYTECODE=1`, so CI leaves no `__pycache__` behind for the scan to trip over.

| Exit code | Meaning |
|---|---|
| 0 | no step failed (with `--release`: no step failed or skipped) |
| 1 | at least one step failed, or no steps were registered |
| 2 | bad command line (unknown flag, missing value) |

### Flags

| Flag | Effect |
|---|---|
| `--release` | release mode: every `SKIP` becomes a `FAIL` |
| `--with-folio` | also run the `folio` step (Folio's own suite in `vendor/folio/`) |
| `--gitleaks PATH` | gitleaks binary, passed through to `history-scan` |
| `--trufflehog PATH` | trufflehog binary, passed through to `history-scan` |
| `--terms-file PATH` | term list, passed through to `clean-scan` and `history-scan`; keep it outside the kit |

The scanner binaries and the term list are never stored in the kit: pass their paths on the command line at run time. Without them the scan steps report `SKIP` (the core rules still ran and must be at `TOTAL 0`); with `--release` that `SKIP` is a failure, so a release run needs all three.

`--release` is the kit's own release check, not the final release gate: that gate is external to the kit, and `ci_local` has no client/employer coverage (see "Release gate" in the kit's `README.md`).

### Steps (in run order)

| Step | What it runs |
|---|---|
| `structure` | `python3 -m unittest tests.test_structure`: layout, no submodules or nested `.git`, no hosted CI, `.gitignore` coverage, no tracked secret-scanner ignore or config file (`.gitleaksignore`, `.gitleaks.toml`, `.trufflehogignore`, in any folder) and no tracked file with an inline suppression marker of either scanner |
| `kit-tests` | `python3 -m unittest discover -s tests -t .`: every test under `tests/`, the scanner's own suite (`tests/scan/`) included |
| `clean-scan` | `python3 tools/clean_scan.py <repo root> [--terms-file PATH]`: the whole tree; `PASS` on `TOTAL 0`, `SKIP` when the term list was not given or a binary file other than a known image was content-skipped (images count under `BINARY <n>` and do not skip), `FAIL` on findings or a scanner usage error |
| `history-scan` | the same scanner with `--history --allowed-identity "<user.name> <user.email>"` built at run time from `git config` (the address never lands in a file), plus `--gitleaks` / `--trufflehog` when given; `SKIP` outside a git work tree, without a configured identity, or when a binary, the term list or a scanner was absent |
| `sb` | `python3 -m unittest discover -s second-brain/tests -p 'test_*.py'`: the sb suite (config loader, search parity on both engines, doctor checks 1-9, packaging); the rg-engine tests skip without ripgrep and still count as run |
| `accelerator` | `python3 -m unittest discover -s tests/accelerator -t tests/accelerator`: the kit-level suite for `vendor/accelerator/` (scrub, identity, builder rename, pricing data, the suite's own gate on a temp copy); `SKIP` without `vendor/accelerator/` |
| `runner-tests` | `python3 -m unittest discover -s runner/tests -t runner/tests`: the queue runner's suite inside its fail-closed sandbox (a temp `KIT_HOME` per test, the fake `claude` only; see `runner/tests/helpers.py`), the privacy test over `runner/` included |
| `runner-k5` | `python3 -m unittest discover -s runner/tests/k5 -t runner/tests/k5`: the runner parameterization suite (`runner/tests/k5/README.md`); a red suite is a `FAIL` |
| `runner` | the clean-data scan on `runner/` alone (plus `--terms-file` when given), with the same `PASS` / `SKIP` / `FAIL` rules and codes-only reason as `clean-scan` |
| `overwrite-harness` | `python3 -m unittest discover -s tests/overwrite -p 'test_*.py'`: the overwrite-protection harness over the six existing-setup fixtures plus the planner's contract tests (`tests/overwrite/README.md`) against `tools/kit_plan.py`; a missing planner is a `FAIL` |
| `pins` | `python3 tools/verify_pins.py --pins tools/pins.json [--release]`: `PASS` with the counts, for example `21 pins, 13 required, 0 warnings, 0 errors`; a placeholder on a required pin is a warning (still `PASS`) and, with `--release`, a `FAIL`; a malformed or missing pins file is a `FAIL` in both modes |
| `placeholders` | the build-time source-sha placeholder (`sha-filled-at-build` in angle brackets, the `VENDORED.md` rows the release build fills) anywhere in the tree, `.git` left out and symlinks not followed: `PASS (0 left)`; in fast mode leftovers still `PASS` with their count, for example `5 left; --release fails`; with `--release` a leftover is a `FAIL` and every `<path>:<line>` is listed under the `STEP` line. It runs after every build and tree step, just before `folio` |
| `folio` | only with `--with-folio` (otherwise `SKIP`): Folio's own suite in place, `python3 -m unittest discover -s tests -v` from `vendor/folio/`. Set `FOLIO_BACKLOG_BIN` to the pinned Backlog.md 1.53.0 binary for the run (never stored in the kit): `PASS (<n> tests, <m> skipped)`. Without it the suite runs with `FOLIO_BACKLOG_CONTRACT=skip` and the step is `SKIP`, which `--release` fails. A `FOLIO_BACKLOG_BIN` that is not an executable file fails before anything runs. The `__pycache__` folders Folio's CLI subprocesses leave under `vendor/folio/` are removed afterwards |

The reason of a scan step holds codes and counts only, for example `TOTAL 2: EMAIL 1, ALIAS 1, not run: terms`.

### Adding a step

Write a function that takes the context and returns a `StepResult`, then append it to `STEPS` in `ci_local.py`:

```python
def step_example(ctx):
    if not os.path.exists(os.path.join(ctx.root, "example")):
        return StepResult(SKIP, "example not present")
    return unittest_step(ctx, ["discover", "-s", "example/tests", "-t", "."])

STEPS.append(Step("example", step_example))  # or add it to the STEPS list
```

The context carries `root` (repo root), `release`, `with_folio`, `gitleaks`, `trufflehog` and `terms_file`. A step that raises or returns something other than a `StepResult` counts as `FAIL`. Step names use lowercase letters, digits and `-`.

## `clean_scan.py`: the kit clean-data scan

Counts owner-data findings in one or more folders and prints codes and counts only. Use it on every folder you touch before you hand work over:

```
python3 tools/clean_scan.py <folder> [<folder> ...]
python3 tools/clean_scan.py . --terms-file /path/outside/the/kit/terms.tsv
python3 tools/clean_scan.py . --history --allowed-identity "Example Org <kit@example.com>"
python3 tools/clean_scan.py . --gitleaks /path/to/gitleaks --trufflehog /path/to/trufflehog
```

### What it prints, and what it never prints

Standard output holds only these line shapes:

| Line | Meaning |
|---|---|
| `<CODE> <n>` | a finding code with a non-zero count (codes below); counts are matches, BIDI and CTRL count decoded characters |
| `BINARY <n>` | image files known by their magic bytes (PNG, JPEG, GIF87a/GIF89a, WebP) that were not content-scanned; their names were still checked. Not a finding and not part of `TOTAL`; the file name or extension never makes a file an image, and there is no allow-list |
| `SKIP <what>` | a check that did not run: `gitleaks`, `trufflehog`, `terms` (no `--terms-file`), `binary` (a file with a NUL byte and no known image magic was not content-scanned; its name was still checked) |
| `TOTAL <n>` | the sum of every finding code line, always last |

Never printed, on any exit path, on stdout or stderr: matched text, file names, paths, line numbers, commit shas, the term list, the allowed identity, scanner output. Error messages are generic (for example `clean_scan: the term list lies inside a scanned folder`). An unexpected internal error prints only the exception type. Finding where a hit lives is a deliberate extra step: scan sub-folders, or load the module and look at counts per file yourself.

| Exit code | Meaning |
|---|---|
| 0 | `TOTAL 0` |
| 1 | findings |
| 2 | usage error: no folder, a folder or file that cannot be read, a term list that is missing, malformed or inside a scanned folder, `--history` outside a git repo or without `--allowed-identity`, a malformed identity, a scanner binary missing or failing, git missing when history or a scanner needs it. No count line is printed. |

### Flags

| Flag | Effect |
|---|---|
| `FOLDER ...` | one or more folders; findings are added up |
| `--terms-file PATH` | external term list (format below); refused with exit 2 if it lies inside a scanned folder, also through a symlink |
| `--history` | also scan every object reachable from any ref of the repo that holds each folder: blobs under their tree codes, tree entry names under the path rules, messages under `MSG`, headers under `HDR`; needs `--allowed-identity` |
| `--allowed-identity "Name <email>"` | the only author/committer/tagger allowed in history headers; command line only, never read from a file |
| `--gitleaks PATH` | run this gitleaks binary over the full history (`git --log-opts=--all --redact`, JSON report in a temp folder) and count its findings under `GITLEAKS` |
| `--trufflehog PATH` | run this trufflehog binary over the full history (`git --no-verification --no-update --json --fail`) and count its result lines under `TRUFFLEHOG` |

Scanner binaries run with a fixed argv list, never a shell, with a temporary `HOME` and without any `GITLEAKS_*` or `TRUFFLEHOG_*` environment variable (one could hand the tool its own config or allowlist); their own output is discarded. An unexpected exit code, or a result that does not match the exit code, fails closed with exit 2. Absent binaries give `SKIP gitleaks` / `SKIP trufflehog`.

### Rules and codes

| Code | Fires on |
|---|---|
| `SECRET` | private-key blocks; common token prefixes (GitHub, GitLab, OpenAI-style `sk-`, AWS key ids, Slack, Google API keys); JWT-looking strings; HTTP bearer credentials; secret-looking assignments: a password, passphrase, api-key, secret or token key, then `:` or `=`, then a value of 8+ characters that is quoted or holds a digit and is not a placeholder (`<...>`, `${...}`, `your-...`, `changeme`, `redacted` ...). A token that is also assigned counts once. |
| `EMAIL` | any address whose domain is not `example.com`, `example.org`, `example.net`, a sub-domain of those, or `*.invalid`; look-alikes such as `example.com.evil` count. Package versions like `pkg@1.2.3` are not addresses. |
| `NOREPLY` | any address at the GitHub noreply domain (counted here, not under `EMAIL`) |
| `BIDI` | U+202A to U+202E and U+2066 to U+2069, one per character; plain right-to-left text is fine |
| `CTRL` | other C0/C1 control characters, DEL included, except TAB, LF and CR; one per character |
| `HOMEPATH` | absolute home roots: the container workspace root, Linux homes other than `/home/user`, macOS homes, the macOS per-user temp folder root. A root must start a path: a relative folder with the same name is not a root. The owner-specific roots are assembled from fragments inside the scanner, so the kit holds none of them as a literal. |
| `OPSPATH` | the owner's operations-folder name as a whole word (assembled from fragments; case-insensitive) |
| `ALIAS` | whole-token alias codes of the owner's shorthand: a two-letter prefix, a hyphen, then one lowercase letter (channels) or a token (clients); the prefixes are assembled from fragments. Longer words that merely contain such a sequence do not fire; the term list catches those. |
| `UUID` | any UUID that is not all zeros; a 40-hex sha is not a UUID |
| `CAPTURE` | real-capture markers: a file name matching `*_real_*`; inside a `/usage`-style screen (a `/usage` line or a `NN% used` line), an `Email`, `Org`, `Organization` or `Plan` field whose value is not an example address or does not start with `Example`, and a status header whose plan segment does not start with `Example`. Those fields are ignored in any other text. |
| `SUPERPOWERS` | any path under the dot-superpowers folder, as a tree entry or mentioned in a file |
| `STRUCT` | `.gitmodules`; a gitlink entry (mode 160000) in the index or, with `--history`, in any historical tree; a nested `.git` directory or file. The scanned root's own `.git` is skipped and never read. |
| `TERMS` | hits of the external term list, in file contents and in path names |
| `HDR` | `--history`: an author, committer or tagger header that is not exactly the `--allowed-identity` string; one per header |
| `MSG` | `--history`: any rule above or a term hitting a commit or tag message, trailers included |
| `GITLEAKS` / `TRUFFLEHOG` | findings of the respective scanner over the full history |

Path names: every file and directory name is checked once by the text rules, the `*_real_*` rule and the term list. Symlinks are never followed (their names are still checked). Files are decoded as UTF-8; a UTF-8, UTF-16 or UTF-32 BOM is honoured; undecodable bytes are replaced; a NUL byte in the first 8000 bytes without a BOM marks a binary file (`SKIP binary`). With `--history`, a file whose content is already a scanned blob, or whose path was already seen as a tree entry, is not counted a second time, so `--history` totals are tree totals plus purely historical findings.

### Term list format

One term per line, with optional flags after a TAB; `#` comments and blank lines are ignored; the file must lie outside every scanned folder.

```
Example Holdings
Exampleton	cs
Example Org	allow=NOTICE,*/NOTICE
Examplewood	cs allow=docs/*.md
```

| Flags | Match |
|---|---|
| none | case-insensitive substring, matched literally (not a regex); a term of exactly 4 characters is matched as `cs` instead, since as a substring it hits ordinary words |
| `cs` | case-sensitive whole word; letters and digits are word characters, hyphens and underscores are boundaries |
| `allow=<glob>[,<glob>]` | relative paths (fnmatch, relative to the scanned folder) where the term is allowed; a folder also matches with a trailing slash, so `allow=docs/*` covers the folder `docs` and everything in it. With `--history`, paths of historical objects are relative to the repo root. |

### The scanner is scanned too

`tests/scan/test_output.py` scans `tools/` and `tests/scan/` and requires `TOTAL 0`. Every planted value in the tests is assembled at run time from fragments or `chr()`, and every owner-specific root or prefix in the scanner is assembled from fragments. Keep it that way when you add a rule or a test.

### Tests

```
python3 -m unittest discover -s tests/scan -p 'test_*.py'
```

One planted canary per rule, negatives for the allowed shapes, output hygiene (nothing but code, SKIP and TOTAL lines; no planted value or path anywhere in stdout or stderr), binary and encoding edge cases, the term list and its `allow=` globs, history mode on a temp repo with a synthetic identity, and fake gitleaks/trufflehog binaries that record their argv and the environment they get. `KIT_CLEAN_SCAN=<path>` points the suite at another copy of the scanner.

## `mutation_check.py`: every rule has a canary

```
python3 tools/mutation_check.py [--jobs N] [--only LABEL ...]
```

For each entry in its `MUTANTS` list, the tool disables one rule in a temporary copy of `clean_scan.py` (the real file is never touched), runs the scan suite against that copy and reports `KILLED <label> (<n> failing tests: ...)` or `SURVIVED <label>`. Exit 0 when every mutant is killed; 1 when one survives or a pattern no longer matches the source (update `MUTANTS` after changing the scanner). It takes a few minutes; it is not a CI step.

## `verify_pins.py`: pinned external dependencies

`tools/pins.json` holds one entry per pinned artifact listed in `EXTERNAL-DEPENDENCIES.md` (Claude Code, uv, Node.js per platform; Backlog.md; the optional release-gate tools). The script never downloads anything: you download the file yourself from the pin's `url`, then check it:

```
python3 tools/verify_pins.py --list                          # every pin: name, version, platform, required, algo
python3 tools/verify_pins.py uv-linux-x64 ~/Downloads/uv-x86_64-unknown-linux-gnu.tar.gz
python3 tools/verify_pins.py                                 # check pins.json (dev mode)
python3 tools/verify_pins.py --release                       # check pins.json for a release
```

With a pin name and a file it prints `OK <pin> <version> <platform>: <algo> matches` (exit 0) or `MISMATCH ...: expected <digest>, got <digest>` (exit 1), both digests in the pin's own form. Without them it prints `WARN` / `ERROR` lines and `RESULT: PASS|FAIL (<n> pins, <n> required, <n> warnings, <n> errors)`.

| Exit code | Meaning |
|---|---|
| 0 | pins file fine (and the file matches its pin) |
| 1 | errors in the pins file, a mismatch, or a pin with no digest to compare |
| 2 | bad command line, pins file or downloaded file unreadable, unknown pin name |

### `pins.json` format

`{"schema": 1, "pins": [...]}`; each pin has `name` (lowercase, digits, `.`, `_`, `-`; unique), `version`, `platform`, `url` (`https://`), `algo` (`sha256` or `sha512`), `digest` and `required` (`true` / `false`). Optional keys: `form` (`hex` or `sri`, must match the digest), `size` (bytes), `source` (where the checksum was published), `verify` (how it is checked upstream).

| Rule | Dev mode | `--release` |
|---|---|---|
| a placeholder (`null`, empty, `<...>`, `TODO`, `TBD`) in `version`, `platform`, `url`, `algo` or `digest` of a required pin | `WARN` | `ERROR` |
| an optional pin without a digest (ripgrep: never installed by the kit) | fine | fine |
| a malformed digest: hex that is not exactly 64 (sha256) / 128 (sha512) hex digits; SRI `<algo>-<base64>` whose prefix is not the pin's algo, whose base64 is not padded, or that does not decode to 32 / 64 bytes; anything else | `ERROR` | `ERROR` |
| a missing key, a duplicate name, a non-`https` url, `required` not a boolean | `ERROR` | `ERROR` |

Tests: `python3 -m unittest tests.test_verify_pins` (synthetic artifacts built at test time, plus checks that the shipped `pins.json` has no placeholder on a required pin and that every checksum in `EXTERNAL-DEPENDENCIES.md` equals the one in `pins.json`). `KIT_VERIFY_PINS=<path>` points the suite at another copy of the script.
