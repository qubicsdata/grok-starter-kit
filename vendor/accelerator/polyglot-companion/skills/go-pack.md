---
name: go-pack
description: Go language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls including nil/error handling, testing with the standard library, build with Go modules, and lint with golangci-lint. Import when reviewing Go code or enriching Go specs.
---

# Go Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-GO-1 Explicit error returns — check every error: Every function that can fail returns an `error` as its last return value. Every call site MUST check it immediately.
  Prefer: `data, err := os.ReadFile(path); if err != nil { return fmt.Errorf("read %s: %w", path, err) }`
  Avoid:  `data, _ := os.ReadFile(path)` (discarding error with blank identifier).

- IDIOM-GO-2 `defer` for resource cleanup: Use `defer` to release resources (close files, cancel contexts, unlock mutexes) immediately after acquisition so cleanup cannot be forgotten.
  Prefer: `f, err := os.Open(path); if err != nil { return err }; defer f.Close()`
  Avoid:  Manual `f.Close()` at the end of a function — easy to miss on early-return paths.

- IDIOM-GO-3 Accept interfaces, return concrete types: Functions and methods SHOULD accept the narrowest interface that satisfies their needs (`io.Reader`, `io.Writer`) and return concrete types to keep callers flexible.
  Prefer: `func Process(r io.Reader) (*Result, error)`
  Avoid:  `func Process(r *os.File) (*Result, error)` — unnecessarily constrains callers.

- IDIOM-GO-4 Table-driven tests with `t.Run`: Structure test cases as a slice of structs and iterate with `for _, tc := range tests { t.Run(tc.name, func(t *testing.T) { ... }) }`.
  Prefer: Table-driven pattern — all cases in one test function, each as a named subtest.
  Avoid:  Separate test functions duplicating setup for each case.

- IDIOM-GO-5 `errors.Is` / `errors.As` for error inspection: Do not compare errors with `==` (breaks wrapped errors); use `errors.Is` for sentinel values and `errors.As` for type assertion.
  Prefer: `if errors.Is(err, ErrNotFound) { ... }` / `var e *PathError; if errors.As(err, &e) { ... }`
  Avoid:  `if err == ErrNotFound { ... }` (breaks when error is wrapped with `%w`).

- IDIOM-GO-6 `context.Context` as the first parameter: All functions that perform I/O or may block MUST accept `ctx context.Context` as their first parameter and propagate it to downstream calls.
  Prefer: `func FetchUser(ctx context.Context, id string) (*User, error)`
  Avoid:  Functions that store a `context.Context` in a struct field or use `context.Background()` internally instead of propagating the caller's context.

---

## Section 2 — Anti-Patterns to Flag

- AP-GO-1 Ignoring errors with `_`: Silently discarding error return values allows failures to propagate invisibly as zero values.
  Why harmful: The zero value of the non-error return is used as if the call succeeded; downstream operations on invalid data cause unpredictable failures far from the root cause.
  Reviewer action: FLAG and cite AP-GO-1. Require explicit error handling on every call that can fail.

- AP-GO-2 Nil pointer dereference from unguarded struct access: Accessing a field or method on a pointer that may be nil without an explicit nil check.
  Why harmful: Panics at runtime with no stack context if recovered; crashes the goroutine or the process.
  Reviewer action: FLAG and cite AP-GO-2. Require nil guards (`if ptr == nil { return ErrXxx }`) before pointer dereference.

- AP-GO-3 Goroutine leak — no cancellation or join: Starting a goroutine without a mechanism to stop it (context cancellation, channel close, or WaitGroup) means it runs forever.
  Why harmful: Memory and CPU leak; accumulates under load; prevents clean shutdown.
  Reviewer action: FLAG and cite AP-GO-3. Require a `ctx.Done()` select case or `sync.WaitGroup` to bound goroutine lifetime.

- AP-GO-4 Race condition on shared map without synchronisation: Concurrent reads and writes to a Go `map` without a `sync.RWMutex` or `sync.Map` cause a race condition.
  Why harmful: when map reads and writes overlap without a lock, the Go runtime notices it and stops the program with `concurrent map read and map write`.
  Reviewer action: FLAG and cite AP-GO-4. Require `sync.RWMutex` wrapping or use `sync.Map` for concurrent access.

- AP-GO-5 `panic` in library code for expected error conditions: Libraries SHOULD return errors; `panic` is for truly unrecoverable programmer errors (e.g. assertion violations in init).
  Why harmful: Forces callers to use `recover`; untestable; breaks the Go error handling contract.
  Reviewer action: FLAG and cite AP-GO-5. Require returning an `error` instead.

---

## Section 3 — Security Pitfalls

- SEC-GO-1 SQL injection via `fmt.Sprintf` in query strings: Building SQL with `fmt.Sprintf("SELECT ... WHERE id = %s", userID)` allows arbitrary query modification.
  Mitigation: Use `database/sql` parameterized queries: `db.QueryContext(ctx, "SELECT ... WHERE id = $1", userID)`. Never interpolate user values into SQL strings. Use an ORM's query builder (GORM, sqlc) for dynamic queries.
  Severity: CRITICAL

- SEC-GO-2 `exec.Command` with user-supplied shell string: Passing a user-controlled string to `exec.Command("sh", "-c", userInput)` allows shell command injection.
  Mitigation: Use `exec.Command` with discrete arguments (`exec.Command("ls", "-l", path)`) and never invoke `sh -c` with user-controlled content. Validate arguments against an allowlist.
  Severity: CRITICAL

- SEC-GO-3 Path traversal via `filepath.Join` without canonical path check: `filepath.Join(base, userInput)` with `userInput = "../../../etc/passwd"` still produces a path outside `base` after normalization.
  Mitigation: After joining, call `filepath.Clean` and verify the result starts with the canonical base using `strings.HasPrefix(clean, base+string(os.PathSeparator))`.
  Severity: HIGH

- SEC-GO-4 Insecure random via `math/rand`: `math/rand` is a deterministic PRNG — do not use it for security-sensitive values (tokens, session IDs, nonces).
  Mitigation: Use `crypto/rand` (`rand.Read(b)` or `rand.Int`) for all security-sensitive random values.
  Severity: HIGH

- SEC-GO-5 `unsafe.Pointer` usage without justification: Bypasses Go's type safety and memory safety guarantees.
  Mitigation: Any use of `unsafe.Pointer` MUST have a documented justification comment citing the specific Go `unsafe` guarantee being relied upon. Flag for security review during code review.
  Severity: HIGH

- SEC-GO-6 Hard-coded secrets: Credentials, API keys, or tokens embedded in `.go` source files are exposed via version control.
  Mitigation: Load secrets from environment variables (`os.Getenv("SECRET_KEY")`) or a secrets manager. Never embed secrets in source; use `envconfig` or `viper` for configuration.
  Severity: HIGH

---

## Section 4 — Testing Framework & Convention

Framework: Standard library `testing` package; `testify` (`github.com/stretchr/testify`) for assertions and mocking (`testify/assert`, `testify/require`, `testify/mock`).
Convention:
- Test files named `<file>_test.go` in the same package (white-box) or `<file>_test.go` in a `<pkg>_test` package (black-box).
- Use table-driven tests (IDIOM-GO-4) for all parameterized cases.
- `require.NoError(t, err)` (from testify) halts the test on first failure; `assert.NoError` continues — use `require` for preconditions.
- Integration tests gated with `testing.Short()`: `if testing.Short() { t.Skip("integration test") }`.
- Benchmarks in `_test.go` files using `func BenchmarkXxx(b *testing.B)`.
- Use `httptest.NewRecorder()` and `httptest.NewServer()` for HTTP handler tests — no live server required.
- Test helpers call `t.Helper()` as their first line so failures report the caller's line, not the helper's.
Coverage tool: `go test -cover -coverprofile=coverage.out ./...` → `go tool cover -html=coverage.out`

---

## Section 5 — Build / Dependency Norms

Build tool: Go toolchain (`go build`, `go test`, `go vet`). No separate build system required for pure Go projects; `Makefile` for multi-step CI tasks.
Dependency manifest: `go.mod` — declares module path and Go version; `go.sum` for cryptographic checksums.
Lock file: `go.sum` IS the lock file — it is commit-required and provides reproducible builds. Never delete or regenerate `go.sum` without a full `go mod tidy`.
Norms:
- Run `go mod tidy` before committing to remove unused dependencies and update `go.sum`.
- Pin dependencies to a specific `vN.N.N` tag; avoid pseudo-versions (`v0.0.0-20240101abc`) in production.
- Use `replace` directives only for local development; never commit a `replace` directive pointing to a local path in a production release.
- Major version upgrades (v2+) require updating the import path (`github.com/foo/bar/v2`).
- `CGO_ENABLED=0` for statically linked Docker images; declare in the build step, not in source.

---

## Section 6 — Lint / Format Tool of Record

Linter: `golangci-lint` (`.golangci.yml`) — aggregates `go vet`, `staticcheck`, `errcheck`, `gosec`, `revive`, and others. Enable `errcheck` and `gosec` at minimum.
Formatter: `gofmt` (built into the Go toolchain) — no config; canonical formatting is fixed. Also run `goimports` to manage import grouping.
Enforcement: CI step runs `golangci-lint run ./...` and `gofmt -l .` (exits non-zero if any file would be reformatted). PRs MUST NOT merge with `golangci-lint` violations or `gofmt` diffs.
