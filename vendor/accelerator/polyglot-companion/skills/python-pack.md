---
name: python-pack
description: Python language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls, testing, build, and lint. Import when reviewing Python code or enriching Python specs.
---

# Python Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-PY-1 Context managers for resource cleanup: Use `with` statements for files, database connections, locks, and network sockets so cleanup is guaranteed even on exceptions.
  Prefer: `with open(path) as f: data = f.read()`
  Avoid:  `f = open(path); data = f.read(); f.close()`

- IDIOM-PY-2 List/dict/set comprehensions over manual loops: Comprehensions are idiomatic, more readable, and often faster for simple transformations.
  Prefer: `squares = [x**2 for x in range(10)]`
  Avoid:  `squares = []; for x in range(10): squares.append(x**2)`

- IDIOM-PY-3 f-strings for interpolation (Python 3.6+): f-strings are the idiomatic interpolation form; they are faster and clearer than `%` or `.format()`.
  Prefer: `msg = f"Hello, {name}!"`
  Avoid:  `msg = "Hello, %s!" % name` or `"Hello, {}!".format(name)`

- IDIOM-PY-4 `enumerate` over manual index counters: When both index and value are needed, use `enumerate`.
  Prefer: `for i, item in enumerate(items):`
  Avoid:  `for i in range(len(items)): item = items[i]`

- IDIOM-PY-5 Dataclasses or named tuples for plain data: Prefer `@dataclass` or `NamedTuple` over bare dicts or positional tuples for structured data.
  Prefer: `@dataclass class Point: x: float; y: float`
  Avoid:  `point = {"x": 1.0, "y": 2.0}` or `point = (1.0, 2.0)`

- IDIOM-PY-6 Type annotations on public APIs: All public functions and methods MUST have parameter and return type annotations.
  Prefer: `def add(a: int, b: int) -> int:`
  Avoid:  `def add(a, b):`

---

## Section 2 — Anti-Patterns to Flag

- AP-PY-1 Bare `except:` clause: Catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit` in addition to application errors, masking fatal signals.
  Why harmful: Hides unexpected failures; makes debugging impossible; can prevent clean shutdown.
  Reviewer action: FLAG and cite AP-PY-1. Require `except Exception:` at minimum, or a named exception type.

- AP-PY-2 Mutable default argument: Default mutable objects (list, dict, set) are shared across all calls.
  Why harmful: Causes silent state accumulation bugs that are hard to reproduce.
  Reviewer action: FLAG and cite AP-PY-2. Require `None` default with guard: `if arg is None: arg = []`.

- AP-PY-3 `import *` from non-`__init__` module: Pollutes the local namespace and hides the origin of names.
  Why harmful: Breaks static analysis; creates name collision risk; makes code harder to read.
  Reviewer action: FLAG and cite AP-PY-3. Require explicit imports.

- AP-PY-4 String concatenation in a loop: Building a large string with `+=` in a loop is O(n²).
  Why harmful: Performance degrades quadratically with string length.
  Reviewer action: FLAG and cite AP-PY-4. Require `"".join(parts)`.

- AP-PY-5 Comparing to `None` with `==`: `== None` may trigger `__eq__` on arbitrary objects.
  Why harmful: Incorrect semantics; `is None` is the only reliable identity check.
  Reviewer action: FLAG and cite AP-PY-5. Require `is None` / `is not None`.

---

## Section 3 — Security Pitfalls

- SEC-PY-1 SQL injection via string formatting: Constructing SQL with f-strings or `%` formatting with user-supplied values allows arbitrary SQL execution.
  Mitigation: Use parameterized queries exclusively: `cursor.execute("SELECT * FROM t WHERE id = %s", (user_id,))`. Never interpolate user data into SQL strings.
  Severity: CRITICAL

- SEC-PY-2 `pickle` deserialization of untrusted data: `pickle.loads()` on attacker-controlled bytes executes arbitrary Python.
  Mitigation: Never deserialize `pickle` data from untrusted sources. Use `json` or `msgpack` for data interchange; if pickle is required, verify an HMAC signature before deserializing.
  Severity: CRITICAL

- SEC-PY-3 `subprocess` shell injection: `subprocess.run(cmd, shell=True)` with user input allows shell command injection.
  Mitigation: Pass commands as lists (`subprocess.run(["ls", "-l", path])`); never use `shell=True` with user-supplied values.
  Severity: CRITICAL

- SEC-PY-4 Hard-coded secrets: Credentials, API keys, or tokens embedded in source code are exposed via version control.
  Mitigation: Load secrets from environment variables or a secrets manager (e.g. `os.environ["SECRET_KEY"]`). Use `python-dotenv` for local development; never commit `.env` files.
  Severity: HIGH

- SEC-PY-5 `eval` / `exec` on user input: Evaluates arbitrary Python code from untrusted input.
  Mitigation: Remove `eval`/`exec` on user-controlled data entirely. Use `ast.literal_eval` for safe value parsing when needed.
  Severity: CRITICAL

- SEC-PY-6 XML external entity (XXE) via `xml.etree` or `lxml`: Default parsers resolve external entities.
  Mitigation: Use `defusedxml` library or disable external entity resolution explicitly before parsing untrusted XML.
  Severity: HIGH

---

## Section 4 — Testing Framework & Convention

Framework: pytest (>=7.0)
Convention:
- Test files named `test_<module>.py` in a top-level `tests/` directory or co-located `tests/` subdirectory.
- Test functions prefixed `test_`; test classes prefixed `Test` (no `__init__.py` in test dirs).
- Use `pytest.mark.parametrize` for data-driven cases instead of loops inside test functions.
- Fixtures defined in `conftest.py`; prefer function-scoped fixtures; use `tmp_path` for temporary files.
- Use `pytest-mock` (`mocker` fixture) for patching; avoid `unittest.mock.patch` as a decorator where pytest fixtures are available.
- Assert with plain `assert` statements — not `self.assertEqual`; pytest rewrites assertions for clear diffs.
- Integration tests marked `@pytest.mark.integration` and excluded from the default run via `pytest.ini` `markers`.
Coverage tool: pytest-cov (`pytest --cov=<package> --cov-report=term-missing`)

---

## Section 5 — Build / Dependency Norms

Build tool: pip / pyproject.toml (PEP 517/518); setuptools or Hatchling as the build backend.
Dependency manifest: `pyproject.toml` (`[project.dependencies]`) or `requirements.txt` for simple scripts.
Lock file: `requirements.txt` (pinned with `pip-compile` from `pip-tools`) or `uv.lock` (if using `uv`). Lock file is required for all deployable services.
Norms:
- All runtime dependencies pinned to exact versions in the lock file for reproducible builds.
- Dev / test dependencies separated into `[project.optional-dependencies] dev = [...]` or `requirements-dev.txt`.
- Never commit a virtual environment directory (`.venv/`, `env/`, `venv/`) — add to `.gitignore`.
- Use a `src/` layout (`src/<package>/__init__.py`) for installable packages to avoid import shadowing.
- Python version constraint declared in `pyproject.toml` under `[project] requires-python`.

---

## Section 6 — Lint / Format Tool of Record

Linter: Ruff (`ruff.toml` or `[tool.ruff]` in `pyproject.toml`) — replaces flake8, isort, pyupgrade in one tool.
Formatter: Ruff format (`ruff format`) or Black (`pyproject.toml [tool.black]`). Both are acceptable; choose one and enforce consistently.
Enforcement: CI step `ruff check . && ruff format --check .` (or `black --check .`). PRs MUST NOT merge with lint or format failures.
