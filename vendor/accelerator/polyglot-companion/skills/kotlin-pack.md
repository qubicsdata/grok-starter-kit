---
name: kotlin-pack
description: Kotlin language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls, testing with Kotest, build with Gradle Kotlin DSL, and lint with ktlint/Detekt. Import when reviewing Kotlin code or enriching Kotlin specs.
---

# Kotlin Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-KT-1 Data classes for value types: `data class` generates `equals`, `hashCode`, `toString`, `copy`, and `componentN` functions automatically.
  Prefer: `data class User(val id: UUID, val name: String)`
  Avoid:  A plain class with manually written `equals`/`hashCode`/`toString`.

- IDIOM-KT-2 Null safety — use `?.`, `?:`, `let` over null checks: Leverage Kotlin's built-in null safety operators instead of explicit null comparisons.
  Prefer: `val length = str?.length ?: 0`
  Avoid:  `val length = if (str != null) str.length else 0`

- IDIOM-KT-3 Scope functions (`let`, `apply`, `run`, `also`, `with`) for concise object configuration: Use the appropriate scope function for the semantic intent.
  Prefer: `val sb = StringBuilder().apply { append("Hello"); append(", world") }`
  Avoid:  `val sb = StringBuilder(); sb.append("Hello"); sb.append(", world")`

- IDIOM-KT-4 Sealed classes / sealed interfaces for exhaustive hierarchies: Kotlin's `sealed` keyword enables exhaustive `when` expressions at compile time.
  Prefer: `sealed class Result<T>; data class Success<T>(val data: T) : Result<T>(); data class Failure<T>(val error: Throwable) : Result<T>()`
  Avoid:  Open class hierarchies where `when` branches cannot be exhaustively verified.

- IDIOM-KT-5 Extension functions over utility classes: Define extension functions on types rather than static utility classes.
  Prefer: `fun String.toSlug(): String = lowercase().replace(" ", "-")`
  Avoid:  `object StringUtils { @JvmStatic fun toSlug(s: String): String = ... }`

- IDIOM-KT-6 Coroutines for concurrency: Use `kotlinx.coroutines` (`suspend` functions, `Flow`, `Channel`) instead of raw threads or Java `CompletableFuture` for async work.
  Prefer: `suspend fun fetchUser(id: UUID): User = withContext(Dispatchers.IO) { repo.find(id) }`
  Avoid:  `Thread { ... }.start()` or manual `ExecutorService` management.

---

## Section 2 — Anti-Patterns to Flag

- AP-KT-1 Non-null assertion operator (`!!`) without justification: `!!` converts a nullable to non-null by throwing `NullPointerException` if the value is null; it defeats Kotlin's null safety.
  Why harmful: Reintroduces the NPE problem Kotlin was designed to eliminate; often indicates a design issue.
  Reviewer action: FLAG and cite AP-KT-1. Require safe-call chain, `requireNotNull()`, or a redesigned API that avoids nullable in that context.

- AP-KT-2 `lateinit var` on properties that should be injected via constructor: Defers initialization checks to runtime; masks DI configuration errors.
  Why harmful: `UninitializedPropertyAccessException` is harder to debug than a compilation or startup failure.
  Reviewer action: FLAG and cite AP-KT-2. Prefer constructor injection or `by lazy` for read-only lazily initialized values.

- AP-KT-3 `runBlocking` inside a coroutine: Calling `runBlocking` from within a coroutine or `suspend` function blocks the coroutine thread, defeating structured concurrency.
  Why harmful: Thread starvation in coroutine thread pools; potential deadlock.
  Reviewer action: FLAG and cite AP-KT-3. Require `coroutineScope` or `withContext` instead.

- AP-KT-4 Using `companion object` for stateful mutable shared state: `companion object` fields are JVM static; mutable ones are global shared state.
  Why harmful: Thread safety risk; hard to test; violates single-responsibility.
  Reviewer action: FLAG and cite AP-KT-4. Require dependency injection of the shared resource.

- AP-KT-5 Catching `Throwable` or `Exception` in coroutines without a `CoroutineExceptionHandler`: Swallows `CancellationException`, which breaks structured concurrency cancellation.
  Why harmful: A coroutine that catches `CancellationException` silently continues running after its scope is cancelled.
  Reviewer action: FLAG and cite AP-KT-5. Require `catch (e: Exception)` (not `Throwable`) and re-throw `CancellationException` explicitly if caught as `Exception`.

---

## Section 3 — Security Pitfalls

- SEC-KT-1 Java deserialization of untrusted data (interop risk): Kotlin code calling `ObjectInputStream.readObject()` on the JVM inherits all Java deserialization vulnerabilities — arbitrary code execution via gadget chains.
  Mitigation: Apply the same Java deserialization mitigations: use `ObjectInputFilter` with an allowlist. Prefer kotlinx.serialization (JSON) or Protocol Buffers for data interchange.
  Severity: CRITICAL

- SEC-KT-2 SQL injection via string templates in JDBC/Exposed: Using `"SELECT ... WHERE id = $userId"` in JDBC or Exposed raw SQL allows injection.
  Mitigation: Use `PreparedStatement` with `?` placeholders or Exposed's type-safe DSL (`Users.select { Users.id eq userId }`). Never interpolate user input into SQL strings.
  Severity: CRITICAL

- SEC-KT-3 Coroutine scope leaks in Android/server contexts: Launching coroutines in `GlobalScope` creates unscoped, uncancellable work that leaks across request lifetimes.
  Mitigation: Use structured concurrency with a scoped `CoroutineScope` tied to the lifecycle (viewModelScope, lifecycleScope, or a request-scoped scope). Never use `GlobalScope` in production code.
  Severity: HIGH

- SEC-KT-4 Hard-coded secrets in Kotlin source or `companion object`: API keys or passwords in `companion object` or `const val` are compiled into bytecode and extractable via decompilation.
  Mitigation: Inject secrets via environment variables or a secrets manager. Never use `const val SECRET = "..."`.
  Severity: HIGH

- SEC-KT-5 Unsafe reflection via KClass / Java reflection on user-supplied class names: Loading or instantiating classes by name from user input allows arbitrary class loading.
  Mitigation: Validate the class name against an explicit allowlist before calling `Class.forName()` or `KClass.createInstance()`.
  Severity: HIGH

---

## Section 4 — Testing Framework & Convention

Framework: Kotest (>=5.8) with the `StringSpec`, `FunSpec`, or `BehaviorSpec` style; JUnit 5 is an acceptable alternative for teams migrating from Java.
Convention:
- Test files named `<ClassUnderTest>Test.kt` or `<ClassUnderTest>Spec.kt` in `src/test/kotlin/<package>/`.
- Prefer `FunSpec` for unit tests; `BehaviorSpec` (Given/When/Then) for acceptance-level scenarios.
- Data-driven tests use Kotest's `forAll` or `withData` — not manual loops inside test functions.
- Assertions via Kotest matchers: `result.shouldBe(expected)`, `list.shouldContain(item)`, etc.
- Mocking with MockK (`mockk<T>()`, `coEvery { }` for suspend functions, `verify { }`).
- Coroutine tests: wrap in `runTest` from `kotlinx-coroutines-test`; do not use `runBlocking` in tests.
- Integration tests annotated `@Tags("integration")` and isolated via a Gradle source set or test tag filter.
Coverage tool: Kover (`./gradlew koverReport`)

---

## Section 5 — Build / Dependency Norms

Build tool: Gradle with Kotlin DSL (`build.gradle.kts`). Maven is acceptable for legacy projects but Gradle Kotlin DSL is the preferred convention.
Dependency manifest: `build.gradle.kts` (`dependencies { implementation(...) }`)
Lock file: Gradle dependency locking (`./gradlew dependencies --write-locks`). Required for services; optional for libraries.
Norms:
- Version catalog (`gradle/libs.versions.toml`) for centralized dependency version management.
- Kotlin version declared in the root `libs.versions.toml` under `[versions]`.
- `kotlin-bom` imported to align Kotlin stdlib / coroutines / serialization versions.
- Avoid `implementation("...") { isTransitive = false }` — prefer explicit dependency declarations instead.
- Multi-module projects declare all submodules in `settings.gradle.kts` with `include(":module-name")`.

---

## Section 6 — Lint / Format Tool of Record

Linter: Detekt (`detekt.yml`; enforced via `detekt` Gradle plugin). Covers code complexity, naming, style, and potential bugs.
Formatter: ktlint (enforced via `ktlint-gradle` plugin or `jlleitschuh/ktlint` Gradle plugin). ktlint config in `.editorconfig`.
Enforcement: CI step runs `./gradlew detekt ktlintCheck`. PRs MUST NOT merge with Detekt rule violations or ktlint formatting failures.
