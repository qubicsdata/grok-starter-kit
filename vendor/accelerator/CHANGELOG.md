# Changelog

All notable changes to this repository are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- `scripts/ci-local.sh` no longer overwrites tracked files: every stage runs in a throwaway
  `git clone --no-hardlinks` of HEAD, so `tools/validate.sh`, `gen-readme.py` and `gen-registry.py`
  can no longer destroy an uncommitted `README.md` or `registry.json` edit (post-merge review A-1).
- `scripts/ci-local.sh` hardening (A-2..A-6): a bad, empty or missing `--root` exits 2 instead of
  testing `$PWD`; the clean-tree stage is absolute (untracked files, `git status` errors, HEAD moves)
  in both profiles; the JSON summary is written with `json.dumps`; the log dir must not be a symlink
  (trailing slashes stripped), foreign-owned or group/other-writable, and logs are 0600 files renamed
  into place; setup errors exit 2; `PYTHONDONTWRITEBYTECODE=1`, `GIT_OPTIONAL_LOCKS=0` and the trusted
  `/usr/bin/python3` (`CI_LOCAL_PYTHON` is no longer honoured).

### Added
- `tools/tests/test_ci_local.py`: harness tests that run the real `scripts/ci-local.sh` against
  throwaway fake repos (31 tests, including "an uncommitted README.md edit survives a run").
- `scripts/ci-local.sh`: the fleet gate as one command (tools/run-unit-tests.py, tools/validate.sh,
  README idempotency, clean-tree check) with a log and a JSON summary at a fixed path; offline;
  exits non-zero on failure. `CONTRIBUTING.md` documents it.
