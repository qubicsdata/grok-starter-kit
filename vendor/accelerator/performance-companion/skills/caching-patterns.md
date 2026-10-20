---
# <!-- perf-provenance: performance-companion v1.0.0 2026-07-03 -->
name: caching-patterns
description: Import when designing a caching layer, selecting a cache store, defining TTL/invalidation strategy, or protecting against stampede — covers pattern taxonomy, store selection, and invalidation completeness gate.
---

# Caching Patterns

## Pattern Taxonomy

| Pattern | Description | Default for | Drawback |
|---|---|---|---|
| **Cache-aside** (lazy population) | Application checks cache first; on miss, loads from source and populates cache | General read-heavy workloads | First-request miss; stale-on-write risk |
| **Read-through** | Cache layer loads from source transparently on miss | When cache and source share an interface (e.g. DAL abstraction) | Cache must implement read logic |
| **Write-through** | Every write goes to cache AND source synchronously | Consistency-critical reads where miss is expensive | Higher write latency |
| **Write-behind** (write-back) | Write to cache first; async flush to source | Write-heavy workloads where source is slow | Data loss risk on crash before flush |
| **Refresh-ahead** | Cache proactively refreshes keys before expiry | Predictable, high-value, expensive-to-load keys | Over-fetching keys that won't be read again |

**Default: cache-aside.** Override only with explicit workload evidence.

## Cache Store Selection

| Use case | Default store | Alternative | Key factor |
|---|---|---|---|
| Session, distributed lock, pub/sub | Redis (cluster) | Valkey (Redis-compatible OSS fork) | Atomic operations, TTL, pub/sub |
| Coarse object cache, high throughput simple values | Memcached | Redis | Simpler operationally; no persistence needed |
| CDN / static asset caching | CloudFront / Fastly / Nginx | Varnish | Geographic distribution |
| In-process hot path (sub-ms requirement) | Local LRU (ristretto/Go, caffeine/JVM, lru-cache/Python) | — | Zero network hop |
| Write-behind / durable | Redis with AOF persistence | PostgreSQL LISTEN/NOTIFY + materialized view | Durability vs simplicity trade-off |

## TTL Guidance

- **Default TTL**: 5 minutes for most API-level caches (backstop for invalidation failures).
- **Short TTL** (30 s – 2 min): high-write-rate keys where staleness is costly.
- **Long TTL** (1 h – 24 h): expensive-to-compute, rarely-changed aggregates (e.g. reporting queries).
- **No TTL (permanent)**: immutable objects only (content-addressed hashes, archived blobs). Never for mutable data.
- Always set a TTL — never leave a mutable cache key without an expiry.

## Invalidation Strategies

**Default: event-driven invalidation with TTL backstop.**

| Strategy | How | When to use |
|---|---|---|
| **Event-driven** | On write/delete in source, publish an event; consumers delete/update cache key | Correct invalidation when write events are observable |
| **TTL-only** | Key expires automatically; accept eventual consistency window | Acceptable staleness window exists; writes are unpredictable |
| **Write-through invalidation** | Write to source and cache atomically (two-phase or transactional) | Strong consistency requirement |
| **Versioned keys** | Append version to key; old keys expire naturally by TTL | Immutable-style caching; zero-downtime invalidation |

**Never use TTL-only invalidation on write-heavy keys** — causes unbounded staleness windows.

## Stampede (Cache Thundering Herd) Protection

A cache stampede occurs when many concurrent requests find the same key missing (cold start or expiry) and simultaneously re-compute the value, overloading the source.

| Mechanism | How | Default? |
|---|---|---|
| **Probabilistic early expiry** (XFetch) | Recompute slightly before expiry; probability increases as expiry approaches | Yes — for expensive-to-compute keys |
| **Mutex / distributed lock** | First request acquires lock, recomputes; others wait and read populated value | For very expensive recomputation or external API calls |
| **Background refresh** | Stale value served while a background job refreshes asynchronously | When staleness is acceptable; never for auth tokens |
| **Micro-TTL jitter** | Add ±10–20% random jitter to TTL to desynchronize simultaneous expiries | Always — reduces thundering-herd probability on shared TTLs |

**Default: TTL jitter (always) + probabilistic early expiry (for expensive keys) + distributed lock (for external API calls).**

## Hard Gates

**STOP before recommending caching without specifying all three: invalidation strategy, TTL, and stampede protection.** An incomplete caching recommendation is a defect.
**DO NOT recommend TTL-only invalidation for write-heavy or consistency-critical keys.**
**DO NOT recommend caching without identifying the cache layer** (CDN, application, in-process) and its position in the request path.
**NEVER recommend caching auth tokens or session secrets without confirming encryption-at-rest and secure transport.**
