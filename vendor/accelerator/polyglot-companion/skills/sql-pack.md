---
name: sql-pack
description: SQL best-practice pack for polyglot-companion. Covers idioms, anti-patterns, security pitfalls (SQL injection first), testing, migration norms, and lint. Import when reviewing SQL code, schema migrations, or enriching specs that include database access.
---

# SQL Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below. This pack covers ANSI SQL and common dialects (PostgreSQL, MySQL/MariaDB, SQLite, SQL Server). Dialect-specific notes are marked `[PG]`, `[MY]`, `[SS]`.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-SQL-1 Explicit column lists in `SELECT`: Always name the columns returned; never use `SELECT *` in production queries.
  Prefer: `SELECT id, name, created_at FROM users WHERE active = TRUE`
  Avoid:  `SELECT * FROM users WHERE active = TRUE`

- IDIOM-SQL-2 `JOIN` over correlated subqueries for set operations: Correlated subqueries execute once per row; a JOIN with a derived table or CTE executes once.
  Prefer: `SELECT u.id, o.total FROM users u JOIN orders o ON o.user_id = u.id`
  Avoid:  `SELECT id, (SELECT SUM(total) FROM orders WHERE user_id = u.id) FROM users u`

- IDIOM-SQL-3 CTEs (`WITH`) for readable multi-step queries: Common Table Expressions name intermediate result sets, making complex queries readable and maintainable.
  Prefer: `WITH active_users AS (SELECT id FROM users WHERE active) SELECT * FROM active_users JOIN ...`
  Avoid:  Deeply nested subqueries that repeat the same filter logic multiple times.

- IDIOM-SQL-4 `COALESCE` for null substitution: Use `COALESCE(value, default)` to replace NULLs with a defined fallback.
  Prefer: `COALESCE(phone, 'N/A')`
  Avoid:  `CASE WHEN phone IS NULL THEN 'N/A' ELSE phone END`

- IDIOM-SQL-5 `EXISTS` over `COUNT(*)` for existence checks: `EXISTS` short-circuits on the first match; `COUNT(*)` scans the entire result set.
  Prefer: `WHERE EXISTS (SELECT 1 FROM orders WHERE user_id = u.id)`
  Avoid:  `WHERE (SELECT COUNT(*) FROM orders WHERE user_id = u.id) > 0`

- IDIOM-SQL-6 Explicit transaction boundaries for multi-statement DML: Wrap related `INSERT`/`UPDATE`/`DELETE` statements in `BEGIN` / `COMMIT` with a `ROLLBACK` on failure.
  Prefer: `BEGIN; UPDATE accounts SET balance = balance - 100 WHERE id = 1; UPDATE accounts SET balance = balance + 100 WHERE id = 2; COMMIT;`
  Avoid:  Separate DML statements outside a transaction where partial failure leaves data inconsistent.

---

## Section 2 — Anti-Patterns to Flag

- AP-SQL-1 `SELECT *` in production queries: Fetches all columns including future schema additions; breaks application code when columns are added or reordered.
  Why harmful: Fragile; wastes network bandwidth; prevents index-only scans.
  Reviewer action: FLAG and cite AP-SQL-1. Require explicit column list.

- AP-SQL-2 Non-SARGable predicates: Wrapping an indexed column in a function (`WHERE YEAR(created_at) = 2024`) prevents index use.
  Why harmful: Forces full table scans; severe performance degradation on large tables.
  Reviewer action: FLAG and cite AP-SQL-2. Require range predicate on the raw column (`WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'`).

- AP-SQL-3 `NOT IN` with a subquery that may return NULL: `NOT IN (SELECT ...)` returns no rows if the subquery returns any NULL value.
  Why harmful: Silent data loss — the query returns zero rows when a NULL is present in the subquery result.
  Reviewer action: FLAG and cite AP-SQL-3. Require `NOT EXISTS` or add `WHERE col IS NOT NULL` inside the subquery.

- AP-SQL-4 `ORDER BY` with column position numbers: `ORDER BY 2, 3` is fragile — column positions shift when the `SELECT` list is modified.
  Why harmful: Silent reordering bugs after refactoring.
  Reviewer action: FLAG and cite AP-SQL-4. Require named column references.

- AP-SQL-5 Missing `WHERE` clause on `UPDATE` or `DELETE`: An unqualified `UPDATE`/`DELETE` modifies or removes every row in the table.
  Why harmful: Catastrophic data loss; irreversible without a backup.
  Reviewer action: FLAG and cite AP-SQL-5. Require a `WHERE` clause, or explicit comment that the intent is a full-table operation.

---

## Section 3 — Security Pitfalls

- SEC-SQL-1 SQL injection via string concatenation: Building SQL by concatenating or interpolating user-supplied values allows arbitrary query modification, authentication bypass, and data exfiltration.
  Mitigation: Use parameterized queries (prepared statements with `?` or `$N` placeholders) in every language that calls the database. Never concatenate user input into SQL strings. Apply an ORM's query builder for dynamic queries. Input validation is a defense-in-depth measure, not a replacement for parameterization.
  Severity: CRITICAL

- SEC-SQL-2 Excessive database privileges: Application accounts with DBA or `DROP TABLE` privileges can be exploited via SQL injection or application compromise to destroy or exfiltrate the entire database.
  Mitigation: Grant the application account only the privileges it needs (`SELECT`, `INSERT`, `UPDATE`, `DELETE` on specific tables). Use a read-only account for reporting queries. Never use the database superuser account in application code.
  Severity: HIGH

- SEC-SQL-3 Unencrypted sensitive columns: Storing PII, credentials, or payment data in plaintext exposes it in database dumps, backups, and to insiders with direct DB access.
  Mitigation: Encrypt sensitive columns at the application layer before storage (e.g. AES-256-GCM with a key from a KMS). Use database-level transparent data encryption (TDE) as defense-in-depth, not as the sole protection.
  Severity: HIGH

- SEC-SQL-4 Dynamic DDL from user input: Constructing `ALTER TABLE`, `CREATE TABLE`, or `DROP TABLE` statements from user-supplied table/column names allows structural database manipulation even when DML injection is blocked.
  Mitigation: Never accept table or column names from user input. If schema-level operations are required, validate against an explicit allowlist of known identifiers.
  Severity: CRITICAL

- SEC-SQL-5 Leaking internal schema details in error messages: Propagating raw database errors (`ORA-00942: table or view does not exist`, `relation "users" does not exist`) to API clients reveals schema structure to attackers.
  Mitigation: Catch database exceptions at the service layer; return generic error codes to clients; log full error details internally only.
  Severity: MEDIUM

---

## Section 4 — Testing Framework & Convention

Framework: Integration tests against a real database instance (Docker-based ephemeral containers preferred). Language-specific test framework used for the application layer; SQL itself tested via migration tests and query tests.
Convention:
- Schema migrations tested by applying the full migration sequence on a fresh database in CI; the migration MUST be idempotent or versioned (never run twice).
- Query correctness tests: seed a known fixture dataset, run the query, assert the result set matches expectations row-by-row.
- Use `pgTAP` [PG] or `MyTAP` [MY] for in-database TAP tests when testing stored procedures/functions.
- Rollback tests: every migration that has a rollback (`down`) script is tested by applying and then rolling back.
- Performance regression tests for critical queries: capture `EXPLAIN (ANALYZE, BUFFERS)` [PG] output; assert the plan uses an index scan, not a sequential scan, for large tables.
Coverage tool: Schema coverage (all tables/views touched by at least one test). No standard SQL coverage tool; use application-layer coverage tools.

---

## Section 5 — Build / Dependency Norms

Build tool: Migration tool appropriate to the stack: Flyway (Java), Liquibase (multi-language), Alembic (Python), golang-migrate (Go), Knex (Node.js). Choose one per project and configure it in CI.
Dependency manifest: Migration scripts in a versioned directory (`db/migrations/V<version>__<description>.sql` for Flyway; `migrations/<timestamp>_<name>.sql` for golang-migrate).
Lock file: Not applicable to SQL itself; the migration tool's version is pinned in the application's dependency manifest.
Norms:
- Every schema change is a migration script (never modify the database directly in production).
- Migration scripts are append-only; existing committed migrations are NEVER edited.
- Each migration is atomic: either fully applied or fully rolled back — no partial states.
- Migration scripts use the SQL dialect of the target database; avoid multi-dialect SQL unless using a superset.
- Index creation on large tables uses `CREATE INDEX CONCURRENTLY` [PG] or equivalent to avoid locking.

---

## Section 6 — Lint / Format Tool of Record

Linter: `sqlfluff` (`--dialect postgres|mysql|ansi`; config in `.sqlfluff`). Catches style violations, aliasing issues, and some anti-patterns (e.g. `SELECT *`).
Formatter: `sqlfluff format` — enforces consistent keyword casing, indentation, and comma placement.
Enforcement: CI step runs `sqlfluff lint --dialect <dialect> db/` and `sqlfluff format --check db/`. PRs MUST NOT merge with sqlfluff lint violations.
