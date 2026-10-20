---
name: csharp-pack
description: C# language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls including disposal and deserialization, testing with xUnit, build with dotnet CLI, and lint with Roslyn analyzers/dotnet-format. Import when reviewing C# code or enriching C# specs.
---

# C# Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-CS-1 `using` declaration or `using` statement for `IDisposable`: Guarantees `Dispose()` is called on `IDisposable` objects (streams, connections, readers) even on exception paths.
  Prefer: `using var conn = new SqlConnection(cs); await conn.OpenAsync();` (C# 8+ declaration form)
  Avoid:  Manual `try { ... } finally { conn.Dispose(); }` or forgetting `Dispose` entirely.

- IDIOM-CS-2 Async all the way — `async Task` methods: Never block on async code with `.Result` or `.Wait()`; propagate `async/await` up the call stack.
  Prefer: `public async Task<User> GetUserAsync(Guid id, CancellationToken ct)`
  Avoid:  `user = GetUserAsync(id).Result;` (deadlocks in ASP.NET synchronization contexts).

- IDIOM-CS-3 Records for immutable value types (C# 9+): `record` generates structural equality, `ToString`, and `with`-expressions.
  Prefer: `public record UserId(Guid Value);`
  Avoid:  A class with manually written `Equals`/`GetHashCode`/`ToString` for a value object.

- IDIOM-CS-4 Pattern matching with `switch` expressions and `is` patterns (C# 8+): Exhaustive pattern matching at compile time with `switch` expression.
  Prefer: `var label = shape switch { Circle c => $"circle r={c.Radius}", Rectangle r => $"rect {r.W}x{r.H}", _ => "unknown" };`
  Avoid:  Long `if/else if` chains with `is` and explicit casts.

- IDIOM-CS-5 Nullable reference types enabled (`#nullable enable`): Enable NRT annotations project-wide to surface potential null dereferences at compile time.
  Prefer: `<Nullable>enable</Nullable>` in `.csproj`; annotate `string?` vs `string` correctly.
  Avoid:  Projects with nullable warnings disabled or partially enabled (inconsistent null safety).

- IDIOM-CS-6 LINQ for collection transformations: Use LINQ query syntax or method syntax for filtering, projecting, and aggregating collections.
  Prefer: `var active = users.Where(u => u.IsActive).Select(u => u.Name).ToList();`
  Avoid:  Imperative `foreach` loops that accumulate into a new list for simple filter/map operations.

---

## Section 2 — Anti-Patterns to Flag

- AP-CS-1 `.Result` or `.Wait()` on `Task` in synchronous context: Blocks the thread and causes deadlock in contexts with a `SynchronizationContext` (ASP.NET classic, UI threads).
  Why harmful: Deadlock under load; thread starvation in thread pool.
  Reviewer action: FLAG and cite AP-CS-1. Require `await` and making the calling method `async Task`.

- AP-CS-2 `IDisposable` not disposed — missing `using`: Creating `SqlConnection`, `HttpClient`, `StreamReader`, or any `IDisposable` without a `using` block leaks the underlying resource (connection pool exhaustion, file handle leak).
  Why harmful: Resource exhaustion; connection pool starvation; file descriptor leak.
  Reviewer action: FLAG and cite AP-CS-2. Require `using var ...` or `using (...)` block.

- AP-CS-3 `catch (Exception e) { }` — swallowing exceptions: An empty catch block or one that only logs and continues silently absorbs unexpected failures.
  Why harmful: Application continues in an undefined state; bugs are invisible.
  Reviewer action: FLAG and cite AP-CS-3. Require rethrowing (`throw;`), returning an error result, or failing fast. Specific exception types are acceptable.

- AP-CS-4 `static HttpClient` field re-used without `IHttpClientFactory`: A single static `HttpClient` does not respect DNS changes (TTL); connections to updated endpoints fail after TTL expiry.
  Why harmful: DNS changes not picked up; connection exhaustion if not managed.
  Reviewer action: FLAG and cite AP-CS-4. Require injecting `IHttpClientFactory` and calling `.CreateClient()` per logical client name.

- AP-CS-5 `string` concatenation with `+` in a loop: Each `+` allocates a new `string`; O(n²) allocations for n iterations.
  Why harmful: GC pressure; quadratic performance on large inputs.
  Reviewer action: FLAG and cite AP-CS-5. Require `StringBuilder.Append()` or `string.Join()` / interpolated `$""` in non-loop contexts.

---

## Section 3 — Security Pitfalls

- SEC-CS-1 Insecure .NET deserialization with `BinaryFormatter` or `SoapFormatter`: These formatters deserialize arbitrary types from the stream and execute finalizers/constructors, enabling remote code execution via gadget chains.
  Mitigation: Remove all uses of `BinaryFormatter` and `SoapFormatter` — they are obsoleted and disabled by default in .NET 5+. Use `System.Text.Json`, `Newtonsoft.Json` with a type discriminator allowlist, or `MessagePack` for data interchange. If `BinaryFormatter` is encountered, flag as CRITICAL and do not enable it.
  Severity: CRITICAL

- SEC-CS-2 SQL injection via string interpolation in ADO.NET or EF raw SQL: `$"SELECT * FROM Users WHERE Id = {userId}"` passed to `ExecuteSqlRaw` or `SqlCommand` allows injection.
  Mitigation: Use parameterized ADO.NET (`new SqlParameter("@id", userId)`) or EF Core's type-safe LINQ queries. For raw SQL in EF Core, use `ExecuteSqlInterpolated` (which is safe) not `ExecuteSqlRaw` with string interpolation.
  Severity: CRITICAL

- SEC-CS-3 `IDisposable` resource not disposed — potential sensitive data in memory: Cryptographic objects (`Aes`, `RSA`, `HashAlgorithm`) that are not disposed may leave key material in memory until GC collection.
  Mitigation: Always wrap cryptographic `IDisposable` objects in `using` to clear key material promptly. Prefer `System.Security.Cryptography.RandomNumberGenerator.Fill(span)` for random bytes.
  Severity: HIGH

- SEC-CS-4 Path traversal via `Path.Combine` with user input: `Path.Combine(baseDir, userInput)` with `userInput = "../../secret"` can escape `baseDir`.
  Mitigation: Use `Path.GetFullPath(Path.Combine(baseDir, userInput))` and assert the result starts with `Path.GetFullPath(baseDir) + Path.DirectorySeparatorChar`.
  Severity: HIGH

- SEC-CS-5 Hard-coded secrets in `appsettings.json` or source: Connection strings, API keys, or JWT signing keys committed to source control are exposed.
  Mitigation: Use `IConfiguration` with `ISecretManager`, Azure Key Vault, AWS Secrets Manager, or `dotnet user-secrets` for local development. Never commit secrets in `appsettings.json` or source files.
  Severity: HIGH

- SEC-CS-6 Open redirect via unvalidated `returnUrl`: Redirecting to a user-supplied URL without validating it is a local URL enables phishing via open redirect.
  Mitigation: Validate redirect URLs with `Url.IsLocalUrl(returnUrl)` (ASP.NET Core) before redirecting. Reject absolute URLs or URLs with different host.
  Severity: MEDIUM

---

## Section 4 — Testing Framework & Convention

Framework: xUnit (>=2.6) — the modern standard for .NET; NUnit is acceptable for legacy projects; MSTest is acceptable but not preferred.
Convention:
- Test projects named `<ProjectName>.Tests` in a `tests/` directory parallel to `src/`.
- Test classes named `<ClassUnderTest>Tests`; test methods named `<Method>_<Scenario>_<Expected>` (e.g. `GetUser_WhenNotFound_ReturnsNotFound`).
- Use xUnit's `[Theory]` with `[InlineData]` / `[MemberData]` / `[ClassData]` for data-driven tests.
- Assertions via `Assert.Equal`, `Assert.True`, or `FluentAssertions` (`result.Should().Be(expected)`); prefer FluentAssertions for readability.
- Mocking with `Moq` (`Mock<T>`, `Setup`, `Verify`) or `NSubstitute`.
- Async tests: test method signature `public async Task TestName_Scenario_Expected()` — never use `.Result` in tests.
- Integration tests in a separate `<ProjectName>.IntegrationTests` project; use `WebApplicationFactory<Program>` for ASP.NET Core integration testing.
Coverage tool: `coverlet` (`dotnet test --collect:"XPlat Code Coverage"`) → reports with `reportgenerator`.

---

## Section 5 — Build / Dependency Norms

Build tool: `dotnet CLI` (`dotnet build`, `dotnet test`, `dotnet publish`). MSBuild targets in `.csproj` files.
Dependency manifest: `.csproj` `<PackageReference>` elements; solution-level `Directory.Packages.props` for centralized version management (Central Package Management).
Lock file: `packages.lock.json` — enable with `<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>` in `.csproj`. Required for CI reproducibility.
Norms:
- Use Central Package Management (`Directory.Packages.props`) for multi-project solutions to enforce consistent versions.
- Specify exact versions in `Directory.Packages.props`; do not use floating versions (`*`, `1.2.*`) in production.
- Run `dotnet list package --vulnerable` in CI to detect packages with known CVEs.
- Target framework declared in `<TargetFramework>net9.0</TargetFramework>` (or the project's minimum supported TFM).
- `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` and `<Nullable>enable</Nullable>` in `Directory.Build.props`.

---

## Section 6 — Lint / Format Tool of Record

Linter: Roslyn analyzers — `Microsoft.CodeAnalysis.NetAnalyzers` (enabled by default in .NET 5+), `StyleCop.Analyzers` for style rules. Configure in `.editorconfig` and `Directory.Build.props`.
Formatter: `dotnet-format` (`dotnet format --verify-no-changes`) — enforces `.editorconfig` style, spacing, and naming rules.
Enforcement: CI step runs `dotnet format --verify-no-changes && dotnet build -warnaserror`. PRs MUST NOT merge with Roslyn analyzer warnings (at error severity) or `dotnet-format` diffs.
