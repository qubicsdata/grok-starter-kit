---
name: test-patterns
description: |
  Use when generating or scaffolding a test file. Detects the project's testing framework, assertion style, file organisation, naming convention, and mock library by reading existing test files first. STOP and ask the user if no test files are found.
---

# Test Pattern Detection

## Purpose

Before generating any test file, the test-generator must understand how this project writes tests. This skill defines how to extract that information from the existing test suite. Guessing the framework or inventing a style produces tests that won't run and won't be accepted by the team.

## Detection Process

Run the following commands to locate existing test files:

```bash
find . -type f \( -name "*.test.*" -o -name "*_test.*" -o -name "test_*.*" -o -name "*_spec.*" -o -name "*.spec.*" \) | grep -v '.git' | grep -v 'node_modules' | head -20
```

Also check for framework configuration files:

```bash
find . -maxdepth 3 \( -name "jest.config.*" -o -name "vitest.config.*" -o -name "pytest.ini" -o -name "setup.cfg" -o -name ".rspec" -o -name "go.mod" -o -name "karma.conf.*" -o -name "mocha.*" \) | grep -v '.git'
```

Read 3–5 representative test files from different parts of the codebase. Read the framework config file if found.

---

## Framework Detection

| Language / File pattern | Framework |
|---|---|
| `*.test.ts`, `*.spec.ts` + `jest.config.*` | Jest (TypeScript) |
| `*.test.ts`, `*.spec.ts` + `vitest.config.*` | Vitest |
| `*.test.js`, `*.spec.js` + `jest.config.*` | Jest (JavaScript) |
| `*.test.js` + `mocha.*` or `.mocharc.*` | Mocha |
| `test_*.py` or `*_test.py` + `pytest.ini` or `setup.cfg [tool:pytest]` | pytest |
| `test_*.py` + `import unittest` | unittest (Python) |
| `*_test.go` + `import "testing"` | Go testing package |
| `*_spec.rb` + `require 'rspec'` | RSpec |
| `*.test.kt` | JUnit / Kotlin |

If the framework config is ambiguous (e.g. `jest.config.*` and `vitest.config.*` both exist), read both and determine which one the `package.json` `test` script uses.

---

## Assertion Style Detection

Read the actual assertion calls in test files. Identify which style is used:

| Pattern | Style |
|---|---|
| `expect(x).toBe(y)`, `expect(x).toEqual(y)`, `expect(x).toThrow()` | Jest / Vitest `expect` |
| `assert.equal(x, y)`, `assert.deepEqual(x, y)`, `assert.throws(fn)` | Node assert / Chai assert |
| `x.should.equal(y)`, `x.should.be.an('object')` | Chai should |
| `assert x == y`, `with pytest.raises(Error):` | pytest assert |
| `if !assert.Equal(t, expected, actual)` | Go testify/assert |
| `expect(subject).to eq(value)` | RSpec |
| `t.Errorf("message")`, `t.Fatal("message")` | Go standard testing |

---

## Organisation Pattern Detection

Read the structure of test files:

| Pattern | Organisation |
|---|---|
| `describe('module', () => { it('does X', () => { ... }) })` | Jest / Mocha describe/it |
| `test('does X', () => { ... })` | Jest / Vitest flat test() |
| `class TestMyClass(unittest.TestCase):` | Python unittest class |
| `def test_something():` | pytest function |
| `func TestSomething(t *testing.T)` | Go test function |
| `RSpec.describe MyClass do / it 'does something' do` | RSpec |

---

## File Naming Convention Detection

Look at the names of discovered test files. When running the initial find command to locate test files, use both `*_spec.*` and `*.spec.*` patterns to ensure JavaScript/TypeScript spec files are discovered:

```bash
find . -type f \( -name "*.test.*" -o -name "*_test.*" -o -name "test_*.*" -o -name "*_spec.*" -o -name "*.spec.*" \) | grep -v '.git' | grep -v 'node_modules' | head -20
```

| Example | Convention |
|---|---|
| `userService.test.ts` | `[name].test.[ext]` — place next to source |
| `userService.spec.ts` | `[name].spec.[ext]` — place next to source |
| `__tests__/userService.ts` | `__tests__/[name].[ext]` |
| `test_user_service.py` | `test_[name].[ext]` — in `tests/` directory |
| `user_service_test.go` | `[name]_test.[ext]` — same package, same directory |
| `user_service_spec.rb` | `[name]_spec.[ext]` — in `spec/` directory |

Also check whether test files live alongside source files or in a separate `tests/` / `spec/` / `__tests__/` directory.

---

## Mock Library Detection

Look for mock imports and usage patterns:

| Pattern | Library |
|---|---|
| `jest.fn()`, `jest.spyOn()`, `jest.mock('module')` | Jest built-in mocks |
| `vi.fn()`, `vi.spyOn()`, `vi.mock()` | Vitest built-in mocks |
| `sinon.stub()`, `sinon.spy()` | Sinon.js |
| `from unittest.mock import Mock, patch` | Python unittest.mock |
| `"github.com/stretchr/testify/mock"` | Go testify/mock |
| `allow(subject).to receive(:method)` | RSpec mocks |
| No mock imports — real dependencies only | No mock library |

---

## Output Format

After completing detection, output a summary block for use by test-generator:

```
Detected framework: [name and language]
Assertion style: [example from actual code]
Organisation: [describe/it | test() | class-based | function-based | Go func]
File naming: [convention — e.g. "[name].test.ts" next to source]
Mock library: [name or "none — real dependencies used"]
Test directory: [alongside source | tests/ | spec/ | __tests__/]
```

---

## DO NOT Rules

- STOP and ask the user if no test files are found — do not guess the framework; ask: "No existing tests were found in this project. Please specify: (1) testing framework, (2) assertion style, (3) file naming convention, (4) mock library if any." Do not generate a single line of test code until the user answers.
- DO NOT assume Jest because the project uses JavaScript or TypeScript — verify via config file or existing tests; the project may use Vitest, Mocha, or another framework
- DO NOT invent a mock pattern that differs from what the existing tests use — if the project uses `jest.spyOn()` consistently, new tests use `jest.spyOn()`; introducing a new mock library creates a maintenance split
- DO NOT infer framework from file extension alone — `.test.ts` files can be Jest or Vitest; check the config
