---
name: migration-patterns
description: Import when planning a schema migration on a live table — expand-contract (parallel-change), zero-downtime online DDL by engine, backfill strategy, and rollback/point-of-no-return analysis. Consumed by migration-planner.
---

# Migration Patterns

## Section 1 — The expand-contract (parallel-change) pattern

Never change a live schema in one destructive step. Split every migration into phases that are each independently deployable, backward-compatible, and (until the contract phase) reversible:

1. **Expand** — add the new shape *additively* (new nullable column, new table, new index built CONCURRENTLY). The old shape still works; old and new app code both run against it.
2. **Migrate/backfill** — copy/transform existing rows into the new shape in batches; keep new writes flowing to both shapes (dual-write) if the column is being replaced.
3. **Transition reads/writes** — deploy app code that reads the new shape; once verified, stop writing the old shape.
4. **Contract** — remove the old shape (drop column/table/constraint). This is the **point of no return** — reversible only by restore.

Golden rule: **expand before the deploy that needs it; contract at least one deploy after the last code that used the old shape.** A migration and the code that depends on it never ship in the same atomic step.

## Section 2 — Zero-downtime online DDL, by engine

| Change | Postgres | MySQL |
|---|---|---|
| Add column | Instant if no volatile default (PG11+ safe for constant default) | Instant (INSTANT algorithm, MySQL 8.0.12+) or gh-ost/pt-osc |
| Add index | `CREATE INDEX CONCURRENTLY` (no table lock; can't run in a txn) | `ALTER … ADD INDEX, ALGORITHM=INPLACE` or gh-ost/pt-osc |
| Drop column | Fast metadata op; do it in the contract phase | INSTANT (8.0.29+) or gh-ost/pt-osc |
| Add NOT NULL | `ADD CONSTRAINT … CHECK (col IS NOT NULL) NOT VALID` → backfill → `VALIDATE CONSTRAINT` (no long lock) | gh-ost/pt-osc; avoid a blocking full-table rewrite |
| Rename column | **Never rename in place** — expand (add new) + backfill + contract | Same — add-new, backfill, drop-old |
| Change type | Add new column of the new type, backfill, switch, drop old | Same — never `MODIFY COLUMN` in place on a large table |

**Tools:** for MySQL large-table changes use **gh-ost** (triggerless, pausable, low-lag) or **pt-online-schema-change**. Orchestrate versioned, reversible migrations with **Flyway** or **Liquibase** (one change per file, an explicit `undo`/`rollback` for every forward step).

## Section 3 — Backfill discipline

- **Batched**: update in bounded ranges (e.g. 1–10k rows by PK), never one unbounded `UPDATE`.
- **Throttled**: sleep between batches; watch replica lag and stop if it exceeds a threshold.
- **Idempotent + resumable**: a re-run must not double-apply; track a high-water mark so a killed backfill restarts cleanly.
- **Non-blocking**: backfill must not hold locks that block live traffic.

## Section 4 — Rollback & point-of-no-return

- Phases 1–3 (expand, backfill, transition) are **reversible**: revert the deploy, drop the additive object.
- The **contract** phase (drop old column/table) is **irreversible without a restore** — flag it as a CAUTION requiring explicit acknowledgement, and never schedule it in the same window as the expand.
- Every forward migration file must ship with a paired rollback (Flyway `undo` / Liquibase `rollback`); a migration with no rollback path is a finding.

## Section 5 — Output contract

A migration plan MUST present the change as ordered phases; for each phase state: the DDL sketch, the **lock/downtime risk** (none / brief / blocking-avoid), **reversibility** (reversible / point-of-no-return), the **app-code coordination** (what must deploy before/after), and the **backfill** approach where rows move. Irreversible steps carry an explicit CAUTION. Lead with the recommended online-DDL path for the detected engine; name the tool alternative (gh-ost/pt-osc/native) and an override hook. Cite `data-modeling-craft` for modeling trade-offs and this skill for the migration mechanics.
