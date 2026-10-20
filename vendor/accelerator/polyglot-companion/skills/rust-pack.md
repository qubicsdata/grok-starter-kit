---
name: rust-pack
description: Rust language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls including unsafe justification, testing, build with Cargo, and lint with Clippy/rustfmt. Import when reviewing Rust code or enriching Rust specs.
---

# Rust Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-RS-1 `?` operator for error propagation: Use `?` to propagate errors up the call stack instead of `unwrap()` or manual `match` on `Result`.
  Prefer: `let data = fs::read_to_string(path)?;`
  Avoid:  `let data = fs::read_to_string(path).unwrap();` (panics on failure in production).

- IDIOM-RS-2 Pattern matching with `match` and `if let`: Use exhaustive `match` for all arms; use `if let` for single-arm matching without a fallthrough.
  Prefer: `if let Some(value) = optional { ... }` / `match result { Ok(v) => ..., Err(e) => ... }`
  Avoid:  `.unwrap()` or `.expect()` in production paths where the value might be absent.

- IDIOM-RS-3 Ownership and borrowing over cloning: Prefer passing references (`&T`, `&mut T`) over cloning to avoid unnecessary heap allocations.
  Prefer: `fn process(data: &[u8]) -> usize { data.len() }`
  Avoid:  `fn process(data: Vec<u8>) -> usize { data.len() }` (takes ownership when a borrow suffices).

- IDIOM-RS-4 Iterators over index-based loops: Use iterator combinators (`map`, `filter`, `fold`, `chain`) instead of `for i in 0..len` with index access.
  Prefer: `let sum: u64 = values.iter().filter(|&&x| x > 0).sum();`
  Avoid:  `let mut sum = 0u64; for i in 0..values.len() { if values[i] > 0 { sum += values[i]; } }`

- IDIOM-RS-5 Newtype pattern for type safety: Wrap primitive types in newtypes to prevent mix-up of semantically different values.
  Prefer: `struct UserId(u64); struct OrderId(u64);` — prevents passing an `OrderId` where a `UserId` is expected.
  Avoid:  Using bare `u64` for all entity IDs.

- IDIOM-RS-6 `thiserror` for library errors, `anyhow` for application errors: Use `thiserror::Error` derive for typed library error enums; use `anyhow::Result` for application-level error propagation where the exact type is not part of the public API.
  Prefer: Library: `#[derive(Debug, thiserror::Error)] enum MyError { ... }` / Application: `fn run() -> anyhow::Result<()>`
  Avoid:  `Box<dyn std::error::Error>` in library public APIs; bare `String` as error type.

---

## Section 2 — Anti-Patterns to Flag

- AP-RS-1 `.unwrap()` on `Result` or `Option` in non-test production code: Panics at runtime when the value is `Err` or `None`; not recoverable from the caller's perspective.
  Why harmful: Causes process termination; not surfaced at compile time; hides error handling debt.
  Reviewer action: FLAG and cite AP-RS-1. Require `?`, `unwrap_or`, `unwrap_or_else`, or an explicit `match`. `.unwrap()` is acceptable only in tests and in `main` where a panic is acceptable.

- AP-RS-2 `unsafe` block without a safety comment: Any `unsafe` block that lacks a `// SAFETY:` comment explaining why the invariants are upheld is a maintenance and security hazard.
  Why harmful: Future readers cannot determine whether the `unsafe` usage is correct; refactoring may silently violate the invariant.
  Reviewer action: FLAG and cite AP-RS-2. Require a `// SAFETY:` comment immediately preceding the `unsafe` block, explaining the specific invariant being relied upon.

- AP-RS-3 Mutex poisoning ignored with `.unwrap()` on `lock()`: `mutex.lock().unwrap()` panics if the previous holder panicked while holding the lock (poison).
  Why harmful: Can cause a cascading panic in multi-threaded code when a worker thread panics.
  Reviewer action: FLAG and cite AP-RS-3. Require `mutex.lock().unwrap_or_else(|e| e.into_inner())` or explicit poisoning handling.

- AP-RS-4 Blocking I/O in an async function: Calling synchronous blocking functions (`std::fs::read`, `std::thread::sleep`) inside `async fn` blocks the async runtime thread.
  Why harmful: Starves the runtime of threads; reduces concurrency to near-zero under load.
  Reviewer action: FLAG and cite AP-RS-4. Require `tokio::fs`, `tokio::time::sleep`, or `tokio::task::spawn_blocking` for blocking work.

- AP-RS-5 Integer overflow in release builds: Rust panics on overflow in debug builds but wraps silently in release builds (unless `overflow-checks = true` in `Cargo.toml`).
  Why harmful: Silent integer wraparound in release builds causes logical errors and security vulnerabilities.
  Reviewer action: FLAG and cite AP-RS-5. Require `checked_add`, `saturating_add`, or `wrapping_add` for arithmetic that could overflow, or enable `overflow-checks = true` in the release profile.

---

## Section 3 — Security Pitfalls

- SEC-RS-1 Unchecked `unsafe` code — memory safety violations: `unsafe` blocks that violate Rust's invariants (dangling pointers, data races, invalid slice construction) can cause undefined behavior, memory corruption, and arbitrary code execution.
  Mitigation: Every `unsafe` block MUST have a `// SAFETY:` comment. Use `cargo audit` and `cargo geiger` to track unsafe usage. Minimize `unsafe` surface area; encapsulate behind a safe abstraction. Prefer `bytemuck`, `zerocopy`, or other audited crates over hand-rolled `unsafe` transmutes.
  Severity: CRITICAL

- SEC-RS-2 Deserializing untrusted data with `serde` without validation: `serde_json::from_str::<T>(user_input)` with a type that has unbounded `Vec` or `String` fields allows a malicious input to cause excessive memory allocation (OOM).
  Mitigation: Validate input size before deserializing (`if input.len() > MAX_INPUT_SIZE { return Err(...) }`). Use `serde` with bounded types or `serde_with` for length limits. Apply resource limits at the HTTP/transport layer.
  Severity: HIGH

- SEC-RS-3 SQL injection via string formatting: Constructing SQL with `format!("SELECT ... WHERE id = {}", user_id)` in `sqlx`, `diesel`, or raw `rusqlite` allows injection.
  Mitigation: Use parameterized queries: `sqlx::query!("SELECT ... WHERE id = $1", user_id)` or Diesel's type-safe query builder. Never interpolate user values into SQL strings.
  Severity: CRITICAL

- SEC-RS-4 Path traversal: `PathBuf::from(base).join(user_input)` with `user_input = "../secret"` can escape the intended directory.
  Mitigation: Canonicalize the path after joining (`fs::canonicalize(path)?`) and assert it starts with the canonical base directory. Reject paths containing `..` components before joining.
  Severity: HIGH

- SEC-RS-5 Hard-coded secrets: API keys or passwords in `const` or `static` declarations are compiled into the binary and extractable by disassembly.
  Mitigation: Read secrets from environment variables (`std::env::var("SECRET_KEY")`) or a secrets manager at runtime. Use `dotenvy` for local development. Never commit credentials.
  Severity: HIGH

- SEC-RS-6 `transmute` between incompatible types: `std::mem::transmute::<A, B>` between types with different size, alignment, or validity invariants is instant undefined behavior.
  Mitigation: Replace `transmute` with safe alternatives (`From`/`Into`, `bytemuck::cast`, `zerocopy`). If `transmute` is truly required, it MUST be inside an `unsafe` block with a `// SAFETY:` comment proving size and alignment compatibility.
  Severity: CRITICAL

---

## Section 4 — Testing Framework & Convention

Framework: Rust's built-in `#[test]` attribute with the standard test harness (`cargo test`). `rstest` for parametrized/fixture-based tests; `proptest` or `quickcheck` for property-based testing.
Convention:
- Unit tests in the same file as the code under test, inside a `#[cfg(test)] mod tests { ... }` module.
- Integration tests in `tests/<name>.rs` files at the crate root — they test the public API only.
- Test functions named `test_<scenario>` or descriptively named using full sentences (`test_returns_error_when_file_missing`).
- Use `assert_eq!`, `assert_ne!`, `assert!(...)` from std; use `pretty_assertions` crate for readable diffs on struct comparisons.
- `rstest` for parametrized cases: `#[rstest] #[case(1, 2, 3)] fn test_add(#[case] a: i32, #[case] b: i32, #[case] expected: i32)`.
- Mock with `mockall` (`#[automock]` on trait); async mocks with `mockall` + `tokio`.
- `#[ignore]` tag for slow integration tests; run separately with `cargo test -- --ignored`.
Coverage tool: `cargo-tarpaulin` (`cargo tarpaulin --out Html`) or `cargo-llvm-cov` (`cargo llvm-cov --html`)

---

## Section 5 — Build / Dependency Norms

Build tool: Cargo (`cargo build`, `cargo test`, `cargo clippy`, `cargo fmt`). No separate build system required for pure Rust.
Dependency manifest: `Cargo.toml` (`[dependencies]`, `[dev-dependencies]`, `[build-dependencies]`).
Lock file: `Cargo.lock` — commit for binaries/applications; do NOT commit for libraries (allow dependents to choose compatible versions). `Cargo.lock` is the lock file for binaries and provides reproducible builds.
Norms:
- Specify crate versions with `=` (exact) for security-sensitive dependencies; use `^` (caret) for flexible libraries.
- Run `cargo audit` in CI to detect known vulnerabilities in the dependency tree.
- Use a workspace (`[workspace]` in root `Cargo.toml`) for multi-crate projects.
- Feature flags documented in `Cargo.toml` `[features]` section; default features minimal.
- `RUSTFLAGS="-D warnings"` in CI to treat all warnings as errors.

---

## Section 6 — Lint / Format Tool of Record

Linter: `clippy` (`cargo clippy -- -D warnings`; config in `clippy.toml` or `#[allow(...)]` with justification comment). Enable `clippy::pedantic` for new code.
Formatter: `rustfmt` (`cargo fmt`; config in `rustfmt.toml`). Canonical formatting is enforced by `cargo fmt --check` in CI.
Enforcement: CI step runs `cargo fmt --check && cargo clippy -- -D warnings`. PRs MUST NOT merge with Clippy warnings or rustfmt diffs.
