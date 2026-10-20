---
name: perl-pack
description: Perl language best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls including taint mode, testing with Test::More/Test2, build with CPAN/Dist::Zilla, and lint with Perl::Critic. Import when reviewing Perl code or enriching Perl specs.
---

# Perl Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-PL-1 `use strict; use warnings;` at the top of every file: Enforces lexical variable declarations and surfaces common bugs (undefined values, deprecated constructs) at compile time.
  Prefer: First two executable lines after shebang are `use strict; use warnings;`
  Avoid:  Any Perl file that omits either pragma.

- IDIOM-PL-2 Lexical variables with `my`: Declare all variables with `my` to limit scope and prevent accidental global mutation.
  Prefer: `my $count = 0;`
  Avoid:  `$count = 0;` (package global without `our` or `local`).

- IDIOM-PL-3 Three-argument `open` with explicit mode: The two-argument form merges mode and filename, enabling shell injection.
  Prefer: `open(my $fh, '<', $filename) or die "Cannot open $filename: $!";`
  Avoid:  `open(FH, $filename)` or `open(FH, "<$filename")`.

- IDIOM-PL-4 `chomp` before processing line input: Remove trailing newlines from `<STDIN>` or file input before using the value.
  Prefer: `chomp(my $line = <$fh>);`
  Avoid:  Processing `<$fh>` values without `chomp` when the newline is not meaningful.

- IDIOM-PL-5 Regular expression named captures: Use `(?<name>...)` syntax in regexes for self-documenting capture groups.
  Prefer: `/(?<year>\d{4})-(?<month>\d{2})-(?<day>\d{2})/; my $y = $+{year};`
  Avoid:  `/(\d{4})-(\d{2})-(\d{2})/; my $y = $1;`

- IDIOM-PL-6 `use Carp qw(croak confess)` for library errors: Libraries SHOULD die with caller context using `croak`, not `die`.
  Prefer: `croak "Invalid argument: expected string, got undef"` inside library code.
  Avoid:  `die "Invalid argument"` inside a library (reports the library's line, not the caller's).

---

## Section 2 — Anti-Patterns to Flag

- AP-PL-1 Interpolating user input into shell commands via backticks or `system(string)`: Passes user-controlled data to the shell without escaping.
  Why harmful: Shell command injection — arbitrary OS commands can be executed.
  Reviewer action: FLAG and cite AP-PL-1. Require list-form `system()` (`system("ls", "-l", $dir)`) or `IPC::Run`. Enable taint mode.

- AP-PL-2 Using two-argument `open`: Merges mode and filename, allowing shell metacharacters in filenames to alter behavior.
  Why harmful: Filename `">evil"` truncates a file; `"| cmd"` spawns a command.
  Reviewer action: FLAG and cite AP-PL-2. Require three-argument `open` (IDIOM-PL-3).

- AP-PL-3 `eval BLOCK` swallowing errors without checking `$@`: Ignoring `$@` after `eval` silently continues on failure.
  Why harmful: Errors vanish; downstream code operates on undefined state.
  Reviewer action: FLAG and cite AP-PL-3. Require `die $@ if $@;` or use `Try::Tiny`.

- AP-PL-4 Package globals as function output channels: Writing results to package globals (`$main::result`) instead of returning values makes functions non-reentrant and hard to test.
  Why harmful: Not thread-safe; not reentrant; impossible to call concurrently.
  Reviewer action: FLAG and cite AP-PL-4. Require returning values from subroutines.

- AP-PL-5 Regex without `/x` on complex patterns: Long regexes without `/x` (extended mode) are unreadable and unmaintainable.
  Why harmful: Maintenance burden; subtle errors from unintended whitespace.
  Reviewer action: FLAG and cite AP-PL-5. Require `/x` flag with inline comments for any regex longer than 40 characters.

---

## Section 3 — Security Pitfalls

- SEC-PL-1 Missing taint mode for CGI / network-facing scripts: Without `-T` (taint mode), Perl will use user-supplied data in system calls, file operations, and `eval` without flagging it.
  Mitigation: Add `-T` to the shebang: `#!/usr/bin/perl -T`. Untaint values explicitly with a validation regex before use: `($clean) = ($dirty =~ /^([a-z0-9_]+)$/i) or die "Invalid input";`. Never use `die` to bypass taint.
  Severity: CRITICAL

- SEC-PL-2 Shell injection via unchecked `system(string)` or backticks with user data: Any scalar interpolated into a string passed to `system()` or backticks is subject to shell metacharacter injection.
  Mitigation: Use list-form `system("cmd", $arg1, $arg2)` — the shell is never invoked. Use `IPC::Run` for pipelines. Enable taint mode so Perl flags tainted values used in shell calls.
  Severity: CRITICAL

- SEC-PL-3 SQL injection via DBI string interpolation: `$dbh->do("SELECT * FROM t WHERE id = $id")` with user-supplied `$id` allows arbitrary SQL.
  Mitigation: Use DBI placeholders exclusively: `$dbh->prepare("SELECT * FROM t WHERE id = ?")->execute($id)`. Never interpolate user data into SQL strings.
  Severity: CRITICAL

- SEC-PL-4 `eval STRING` on user input: `eval "$user_code"` compiles and executes arbitrary Perl.
  Mitigation: Never `eval` strings containing or derived from user input. If dynamic dispatch is required, use a dispatch table (hash of code refs).
  Severity: CRITICAL

- SEC-PL-5 Directory escape through unvalidated file names: handing user-supplied input to `open`, `unlink` or `mkdir` with no checks lets it reach any file on disk.
  Mitigation: Validate the path against an allowlist pattern (e.g. `^[a-z0-9_.-]+$`) before use. Use `File::Spec->rel2abs` and verify the canonical path starts within the expected root. Enable taint mode.
  Severity: HIGH

- SEC-PL-6 `use MIME::Base64; decode_base64` on untrusted YAML/JSON with object tags: YAML parsers that support `!!perl/hash:ClassName` can instantiate arbitrary Perl objects.
  Mitigation: Use `YAML::XS` with `$YAML::XS::LoadBlessed = 0` or prefer JSON (`JSON::XS`) for untrusted data interchange. Never deserialize YAML from untrusted sources without disabling blessed object loading.
  Severity: HIGH

---

## Section 4 — Testing Framework & Convention

Framework: Test::More (core, ships with Perl 5) for unit tests; Test2::Suite (modern replacement) for new projects.
Convention:
- Test files named `t/<name>.t` in the `t/` directory; integration tests in `t/integration/`.
- Use `plan tests => N` or `done_testing()` (preferred — no count to maintain) at the end of each `.t` file.
- Standard assertions: `ok()`, `is()`, `isnt()`, `like()`, `cmp_deeply()` (from Test::Deep for structures).
- Use `Test::Exception` (`throws_ok`, `lives_ok`) for exception testing.
- Mock with `Test::MockObject` or `Test::MockModule` for module-level mocking.
- Run tests with `prove -lv t/` (recursive with `-r`).
- Use `Test::More`'s `subtest` to group related assertions under a named block.
Coverage tool: Devel::Cover (`cover -test`; produces HTML report in `cover_db/`)

---

## Section 5 — Build / Dependency Norms

Build tool: CPAN / `cpanm` for dependency installation; `Dist::Zilla` (`dzil`) for module authoring and release; `Module::Build::Tiny` or `ExtUtils::MakeMaker` for simple distributions.
Dependency manifest: `cpanfile` (lists module dependencies with optional version constraints using `requires`, `on test => sub { ... }`).
Lock file: `cpanfile.snapshot` (generated by `carton install`; use `carton exec` to run in the locked environment). Required for deployable services.
Norms:
- Perl version declared at the top of every module: `use 5.032;` (or the minimum supported version).
- All non-core dependencies listed in `cpanfile`; never rely on system-installed modules without declaring them.
- Use `Carton` for reproducible CI installs (`carton install --deployment`).
- Avoid XS modules unless necessary; if used, test on all target platforms in CI.
- `MANIFEST` and `MANIFEST.SKIP` maintained for `MakeMaker`-based distributions.

---

## Section 6 — Lint / Format Tool of Record

Linter: Perl::Critic (`perlcritic`) — run at severity level 1 (brutal) for new code; configure exceptions in `.perlcriticrc`. Policy `InputOutput::ProhibitTwoArgOpen` and `InputOutput::RequireBriefOpen` are mandatory.
Formatter: `perltidy` — config in `.perltidyrc` (e.g. `-l=100 -i=4 -ci=4 -ce`).
Enforcement: CI step runs `perlcritic --severity 3 lib/ t/` and `perltidy --check-syntax lib/**/*.pm`. PRs MUST NOT merge with Perl::Critic violations at severity 3 or above.
