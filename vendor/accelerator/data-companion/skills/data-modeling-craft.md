---
name: data-modeling-craft
description: |
  Data-modeling selection expertise — store type, normalization strategy, primary-key design, indexing, partitioning, and consistency model. Consumed by data-critic and data-companion spec-enrichers when advising on schema or storage decisions for a given workload.
---

# Data Modeling Craft

## Section 1 — Decision Domains

- DATAMODEL-1 Store type (relational / document / key-value / wide-column / search / time-series)
- DATAMODEL-2 Normalization vs. denormalization (3NF normalized / star-schema / fully denormalized flat)
- DATAMODEL-3 Primary-key strategy (surrogate UUID / surrogate auto-increment / composite natural / content-hash)
- DATAMODEL-4 Indexing strategy (B-tree covering indexes / partial indexes / composite indexes / full-text / columnar)
- DATAMODEL-5 Partitioning and sharding (range partition / hash shard / list partition / no partition)
- DATAMODEL-6 Consistency model (strong / read-your-writes / eventual / causal)

## Section 2 — Constraint Inputs

- Access pattern (OLTP vs. OLAP vs. mixed) → DATAMODEL-1, DATAMODEL-2, DATAMODEL-4
- Write-to-read ratio → DATAMODEL-2, DATAMODEL-4, DATAMODEL-5
- Schema evolution frequency → DATAMODEL-1, DATAMODEL-3
- Entity relationship cardinality (normalized entities vs. nested documents) → DATAMODEL-2, DATAMODEL-3
- Data volume at 1x and 10x projected scale → DATAMODEL-4, DATAMODEL-5
- Read latency SLA (sub-millisecond / low-second / batch-tolerant) → DATAMODEL-1, DATAMODEL-6
- Audit, compliance, or strict-ordering requirement → DATAMODEL-3, DATAMODEL-6
- Multi-region or cross-datacenter deployment → DATAMODEL-5, DATAMODEL-6
- Query shape (point lookups / range scans / full-text / aggregations) → DATAMODEL-1, DATAMODEL-4

## Section 3 — Opinionated Defaults

- DATAMODEL-1: PostgreSQL relational store for new workloads — mature, transactional, extensible, and handles OLTP + light analytics without introducing operational complexity.
- DATAMODEL-2: Third-normal-form (3NF) normalization — eliminates update anomalies and preserves referential integrity; denormalize only for explicitly measured read-performance gaps.
- DATAMODEL-3: Surrogate auto-increment integer primary key (BIGSERIAL in Postgres, AUTO_INCREMENT in MySQL) — compact, monotonic, predictable join cost, no external key-generation service required.
- DATAMODEL-4: Selective B-tree indexes on foreign keys and high-selectivity filter columns — index every foreign key and every column appearing in WHERE or JOIN ON; avoid over-indexing write-heavy tables.
- DATAMODEL-5: No partitioning below 50M rows — partitioning adds operational complexity with no measurable query benefit at moderate scale; apply range partitioning on a time column when the table crosses 50M rows or requires partition-based expiry.
- DATAMODEL-6: Strong consistency (serializable isolation) — correctness is the default; relax to read-committed or eventual only when benchmarked throughput requirements cannot be met at strong consistency.

## Section 4 — Derivation Rules

- DATAMODEL-D-1: When access pattern is OLAP with complex aggregations, wide column scans, or analytics queries across billions of rows, choose a columnar store (BigQuery, Snowflake, Redshift, or DuckDB for embedded) because row-oriented storage forces full-row reads for aggregate queries, making columnar layouts 10–100× faster for analytics workloads.
- DATAMODEL-D-2: When write-to-read ratio exceeds 80 % writes or the workload is high-frequency event ingestion (>10k events/sec), choose a wide-column store (Cassandra, ScyllaDB) or append-only time-series store (TimescaleDB, InfluxDB) because relational row locking and B-tree write amplification become throughput bottlenecks before IO is saturated.
- DATAMODEL-D-3: When schema evolution frequency is high (multiple schema changes per sprint) or entity structure is genuinely heterogeneous (variable attributes per entity), choose a document store (MongoDB, Firestore) because column migrations on relational tables block or require multi-step online DDL, while document stores absorb structural variance without downtime.
- DATAMODEL-D-4: When query shape is full-text search or relevance-ranked retrieval, choose a dedicated search store (Elasticsearch, OpenSearch, Typesense) as the read replica because SQL LIKE scans and tsvector full-text indexes degrade at scale and lack relevance scoring and faceting.
- DATAMODEL-D-5: When the read-to-write ratio exceeds 10:1 and query patterns are known, stable, and dominated by multi-table joins, choose a denormalized star schema (fact table + dimension tables) because JOINs across normalized tables at query time add latency that precomputed wide rows eliminate; apply this rule in the analytical layer (dbt mart models), never in the operational layer.
- DATAMODEL-D-6: When the primary-key value must be globally unique across distributed writers or must be stable before database insertion (e.g. event sourcing, distributed ID assignment), choose UUID v4 (or UUID v7 for sortability) as the surrogate key because auto-increment integers require a single sequence authority which becomes a write bottleneck in distributed systems.
- DATAMODEL-D-7: When data volume at 1x exceeds 50 million rows on a time-oriented table (logs, events, timeseries, audits), apply range partitioning on the primary time column because partition pruning eliminates full-table scans on time-bounded queries and enables time-based data expiry without full-table DELETE operations.
- DATAMODEL-D-8: When the workload requires sub-millisecond point lookups by a single key with no complex query requirements, choose a key-value store (Redis, DynamoDB in KV mode) because relational query planning, locking, and WAL overhead add latency that cannot be eliminated at the sub-millisecond SLA target.
- DATAMODEL-D-9: When a multi-region or cross-datacenter deployment is required with no tolerance for cross-region write coordination latency, choose eventual or causal consistency and design around conflict-free replicated data types (CRDTs) or last-write-wins semantics because strong serializable consistency requires synchronous cross-region coordination, which adds 50–200 ms round-trip latency per write.
- DATAMODEL-D-10: When audit, compliance, or strict-ordering requirements are present (financial ledgers, regulatory audit trails), use a monotonically ordered surrogate key (auto-increment or UUIDv7) AND strong serializable consistency because out-of-order inserts or eventual reads can produce audit gaps or double-counting in financial reconciliation.

## Section 5 — Recommendation Output Contract

For each Decision Domain, every recommendation emitted by a consumer of this pack MUST include:

1. **Domain and chosen value** — name the concrete technology or strategy, not an abstract category (e.g. "PostgreSQL with 3NF normalization" not "a relational store").
2. **Rule citation** — list each DATAMODEL-D-N that fired to produce this recommendation; if no derivation rule fired, state "defaults apply (DATAMODEL defaults, no derivation rule fired)".
3. **Rationale summary** — one sentence restating why this choice is correct for this specific workload, derived from the rule's rationale.
4. **Named alternative** — at least one concrete alternative (named technology or strategy) with a brief rationale for when it would be preferred instead.
5. **Override hook** — a concrete instruction to the implementer on how to override (e.g. "override DATAMODEL-1 in the ADR by documenting the workload constraint that makes the default inapplicable and updating the schema design accordingly").

Consumers MUST NOT present a neutral menu of options without designating a recommended choice. The recommended choice must appear first and be explicitly labeled as the recommendation. Alternatives must be labeled as alternatives, not co-equal options.

Consumers MUST NOT omit the rule citation. A recommendation without a rule citation is unverifiable and cannot be audited for correctness.

## Section 6 — Enforcement Handoff

data-modeling-craft output is validated by schema-reviewer. The schema-reviewer audits the structural and type correctness of schemas produced from this pack's recommendations, verifying that chosen store types and normalization strategies are correctly realized in DDL (primary-key NOT NULL, foreign-key constraints present, appropriate data types for the store type, index definitions present for declared index strategy). Findings from schema-reviewer that contradict a DATAMODEL-D-* recommendation must be escalated — the recommendation or the schema is wrong, and both cannot stand.
