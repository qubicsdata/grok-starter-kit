---
name: java-pack
description: Java language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls (including deserialization), testing, build, and lint. Import when reviewing Java code or enriching Java specs.
---

# Java Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-JV-1 Prefer records for plain data carriers (Java 16+): `record Point(double x, double y) {}` gives immutable value types with auto-generated `equals`, `hashCode`, and `toString` with no boilerplate.
  Prefer: `public record UserId(UUID value) {}`
  Avoid:  A POJO with manual getters, `equals`, `hashCode`, `toString`.

- IDIOM-JV-2 Use `Optional<T>` for nullable return values: Signals to callers that absence is possible; prevents `NullPointerException` at call sites.
  Prefer: `Optional<User> findById(UUID id)`
  Avoid:  `User findById(UUID id)` returning `null`.

- IDIOM-JV-3 Try-with-resources for `AutoCloseable`: Guarantees close() on streams, connections, and readers even when exceptions occur.
  Prefer: `try (var conn = dataSource.getConnection()) { ... }`
  Avoid:  Manual `finally { conn.close(); }` blocks.

- IDIOM-JV-4 Stream API for collection transformations: Replace imperative loops with `stream().filter().map().collect()` for clarity.
  Prefer: `list.stream().filter(u -> u.active()).map(User::name).toList()`
  Avoid:  Imperative `for` loop with conditional accumulation into a new list.

- IDIOM-JV-5 `var` for local type inference (Java 10+): Use `var` for local variables where the type is obvious from the right-hand side.
  Prefer: `var users = new ArrayList<User>();`
  Avoid:  `ArrayList<User> users = new ArrayList<User>();`

- IDIOM-JV-6 Sealed interfaces / pattern matching (Java 17+): Use sealed hierarchies and `instanceof` pattern matching to model exhaustive type sets without casting.
  Prefer: `if (shape instanceof Circle c) { return Math.PI * c.radius() * c.radius(); }`
  Avoid:  `if (shape instanceof Circle) { Circle c = (Circle) shape; ... }`

---

## Section 2 — Anti-Patterns to Flag

- AP-JV-1 Catching `Exception` or `Throwable` without rethrowing: Swallows `OutOfMemoryError`, `StackOverflowError`, and unexpected runtime failures.
  Why harmful: Masks fatal errors; makes post-mortem debugging impossible.
  Reviewer action: FLAG and cite AP-JV-1. Require specific exception types or rethrow after logging.

- AP-JV-2 `String` concatenation in a loop with `+`: Creates O(n) intermediate `String` objects.
  Why harmful: Quadratic memory and time; use `StringBuilder` or `String.join`.
  Reviewer action: FLAG and cite AP-JV-2. Require `StringBuilder.append()` or `String.join()`.

- AP-JV-3 Calling `.equals()` on a potentially-null left operand: Throws `NullPointerException` at runtime.
  Why harmful: Silent assumption that the receiver is non-null.
  Reviewer action: FLAG and cite AP-JV-3. Require `Objects.equals(a, b)` or null-guarded form `"literal".equals(variable)`.

- AP-JV-4 Mutable `static` field without synchronisation: Shared mutable state accessed from multiple threads without a lock or `AtomicXxx`.
  Why harmful: Data races; undefined behavior under the Java Memory Model.
  Reviewer action: FLAG and cite AP-JV-4. Require `AtomicReference`, `volatile`, or a synchronized accessor.

- AP-JV-5 Raw type usage: Using `List`, `Map`, etc. without generic parameters disables compile-time type checking.
  Why harmful: `ClassCastException` at runtime; defeats generics.
  Reviewer action: FLAG and cite AP-JV-5. Require parameterized types.

---

## Section 3 — Security Pitfalls

- SEC-JV-1 Java deserialization of untrusted data: `ObjectInputStream.readObject()` on attacker-controlled bytes executes arbitrary code via gadget chains (Apache Commons Collections, Spring, etc.).
  Mitigation: Never deserialize untrusted Java serialization streams. Implement a `SerialFilter` (`ObjectInputFilter`) with an explicit allowlist of permitted classes. Prefer JSON (Jackson) or Protocol Buffers for data interchange. If `ObjectInputStream` is required, apply `jdk.serialFilter` and deny unknown classes.
  Severity: CRITICAL

- SEC-JV-2 SQL injection via `Statement.execute(String)` with user input: String-concatenated SQL allows arbitrary query modification.
  Mitigation: Use `PreparedStatement` with `?` placeholders for all user-supplied values. Never concatenate user data into SQL strings.
  Severity: CRITICAL

- SEC-JV-3 XML External Entity (XXE): Default `DocumentBuilderFactory` and `SAXParserFactory` resolve external DTDs and entities.
  Mitigation: Disable external entities: `factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)` and `factory.setFeature("http://xml.org/sax/features/external-general-entities", false)`.
  Severity: HIGH

- SEC-JV-4 Path traversal via `new File(baseDir, userInput)`: If `userInput` contains `../`, the resulting path escapes `baseDir`.
  Mitigation: Canonicalize the resolved path and assert it starts with the canonical base directory: `Paths.get(base).resolve(input).normalize().startsWith(Paths.get(base).normalize())`.
  Severity: HIGH

- SEC-JV-5 Hard-coded credentials in source: Passwords, API keys, or JWTs embedded in `.java` or property files are exposed via version control.
  Mitigation: Inject secrets via environment variables, `System.getenv()`, or a secrets manager (HashiCorp Vault, AWS Secrets Manager). Never commit credentials.
  Severity: HIGH

- SEC-JV-6 SSRF via unvalidated `URL`/`URI` construction: Constructing a URL from user input and fetching it allows internal network access.
  Mitigation: Validate the host against an explicit allowlist before opening a connection. Reject private IP ranges and `localhost`.
  Severity: HIGH

---

## Section 4 — Testing Framework & Convention

Framework: JUnit 5 (Jupiter, >=5.9)
Convention:
- Test classes named `<ClassUnderTest>Test.java` in `src/test/java/<package>/`.
- Test methods annotated `@Test`; use `@DisplayName` for human-readable names.
- Use `@ParameterizedTest` with `@ValueSource` / `@CsvSource` / `@MethodSource` for data-driven cases.
- Assertions via `org.junit.jupiter.api.Assertions.*` (static import); prefer AssertJ (`assertThat(...)`) for fluent assertions.
- Mocking with Mockito (`@ExtendWith(MockitoExtension.class)`); inject mocks via `@Mock` and `@InjectMocks`.
- Use `@Nested` test classes to group related scenarios under a descriptive inner class.
- Integration tests annotated `@Tag("integration")` and run in a separate Maven/Gradle phase.
Coverage tool: JaCoCo (`mvn test jacoco:report` or `./gradlew jacocoTestReport`)

---

## Section 5 — Build / Dependency Norms

Build tool: Maven (`pom.xml`) or Gradle Kotlin DSL (`build.gradle.kts`). Both are acceptable; choose one per project.
Dependency manifest: `pom.xml` (`<dependencies>`) or `build.gradle.kts` (`dependencies { }`)
Lock file: Gradle dependency locking (`./gradlew dependencies --write-locks`) or Maven's `versions:lock-snapshots`. Lock file required for CI reproducibility.
Norms:
- Dependency versions centralized in `pom.xml` `<dependencyManagement>` or Gradle's `libs.versions.toml` (version catalog).
- SNAPSHOT versions MUST NOT appear in release artifacts.
- Use the Maven Enforcer Plugin or Gradle's `dependencyInsight` to detect duplicate classpath entries.
- Multi-module projects declare the parent POM / root `settings.gradle.kts` with explicit submodule inclusion.
- Compiler target and source compatibility declared explicitly (`<source>17</source>` / `<target>17</target>`).

---

## Section 6 — Lint / Format Tool of Record

Linter: Checkstyle (`checkstyle.xml`, Google or Sun style; enforced via `maven-checkstyle-plugin` or `checkstyle` Gradle plugin). SpotBugs for bug-pattern analysis (`spotbugs-maven-plugin`).
Formatter: google-java-format (`google-java-format-*.jar`) — enforced via `fmt-maven-plugin` or `spotless` Gradle plugin.
Enforcement: CI step runs `mvn checkstyle:check spotbugs:check` (or `./gradlew checkstyleMain spotbugsMain`). PRs MUST NOT merge with checkstyle or SpotBugs violations.
