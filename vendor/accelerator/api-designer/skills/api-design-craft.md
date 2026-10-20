---
name: api-design-craft
description: API design decision expertise — API style selection, versioning strategy, pagination, error model, idempotency/safety, and auth pattern. Consumed by intent-agent and versioning-advisor when making opinionated design choices for a new or evolving API.
---

# API Design Craft

## Section 1 — Decision Domains

- APIDESIGN-1 API style (REST / GraphQL / gRPC / event-driven)
- APIDESIGN-2 Versioning strategy (URL path / request header / content negotiation)
- APIDESIGN-3 Pagination model (page+per_page offset / cursor / keyset)
- APIDESIGN-4 Error model (RFC 9457 Problem Details / simple code+message envelope / RPC status)
- APIDESIGN-5 Idempotency and safety (idempotency keys / safe GET guarantee / PUT vs PATCH discipline)
- APIDESIGN-6 Auth pattern (OAuth 2.0 Bearer / API key / mTLS / no-auth with rationale)

## Section 2 — Constraint Inputs

- API type (sync vs event-driven vs hybrid) → APIDESIGN-1 (event-driven favours async style over REST; hybrid favours REST + async extension)
- Consumer set (public/external vs internal/controlled) → APIDESIGN-1 (GraphQL suits product teams building multiple clients; gRPC suits internal microservices; REST suits public consumers), APIDESIGN-2 (external consumers must use URL path versioning), APIDESIGN-6 (public consumers require OAuth 2.0; internal mesh may use mTLS)
- Client diversity (multiple front-end clients with differing data needs) → APIDESIGN-1 (multiple clients with differing field needs favour GraphQL to eliminate over-fetching)
- Performance NFR (latency target, payload size) → APIDESIGN-1 (sub-10 ms p99 or large binary payloads favour gRPC), APIDESIGN-3 (cursor pagination over offset for large datasets — offset degrades at high page numbers)
- Dataset size (number of records in collection endpoints) → APIDESIGN-3 (datasets exceeding 10 000 rows must use cursor or keyset pagination)
- Availability SLA (must support retries, idempotent mutations) → APIDESIGN-5 (any mutation exposed to unreliable networks must carry an idempotency key)
- Network boundary (public internet vs internal service mesh) → APIDESIGN-6 (public internet requires OAuth 2.0 or API key; internal mesh may use mTLS; bare no-auth requires written infrastructure rationale)
- Team familiarity and tooling → APIDESIGN-1 (teams without GraphQL schema tooling should default to REST to avoid resolver and N+1 complexity up front)

## Section 3 — Opinionated Defaults

- APIDESIGN-1: REST over HTTP/1.1 + JSON. REST is universally understood, debuggable with any HTTP tool, supported by every API gateway and CDN, and carries the largest ecosystem of client generators and testing tools. Default unless a specific constraint overrides it.
- APIDESIGN-2: URL path versioning (`/v1/`, `/v2/`). Immediately visible in any log, browser, or curl session. Trivially routable at the load balancer layer without header inspection. Default for all APIs with any external consumer surface.
- APIDESIGN-3: Page + per_page offset pagination with a `meta.total` count in the response envelope. Simple to implement, simple to consume, and adequate for datasets under 10 000 rows. Default for new collection endpoints.
- APIDESIGN-4: RFC 9457 Problem Details (`application/problem+json`) error envelope with `type`, `title`, `status`, `detail`, and `instance` fields. A single canonical error shape across all endpoints eliminates consumer branching logic and is the IETF standard for HTTP APIs.
- APIDESIGN-5: GET and HEAD are unconditionally safe (no side effects). DELETE is idempotent (repeated calls return the same outcome — do not return 404 on a second delete). POST mutations that create resources must accept an `Idempotency-Key` header to allow safe retry. PUT is full replacement only; PATCH is partial update only.
- APIDESIGN-6: OAuth 2.0 Bearer token (Authorization Code flow for user-facing clients; Client Credentials flow for M2M). OAuth 2.0 is the industry standard, supports token rotation, and integrates with every major identity provider. Default for any API accessible over the public internet or with external consumers.

## Section 4 — Derivation Rules

- APIDESIGN-D-1: When consumer set includes multiple distinct front-end clients (mobile app, web app, third-party integrations) each requiring different field subsets from the same domain, choose GraphQL because a single schema with per-query field selection eliminates REST over-fetching and the proliferation of bespoke endpoint variants per client.
- APIDESIGN-D-2: When the API is an internal microservice-to-microservice interface with a latency NFR under 10 ms p99, or when the payload is binary (images, audio, protobufs), choose gRPC because HTTP/2 multiplexing, binary framing, and generated strongly-typed stubs deliver lower latency and smaller wire payloads than REST+JSON.
- APIDESIGN-D-3: When the API type is event-driven (producers push notifications; consumers subscribe to channels), choose an async event-driven style (e.g. AsyncAPI-described channels over a message broker) and set `asyncapi_mode: true` because request/response REST semantics do not map to push or fire-and-forget communication patterns — forcing them onto REST creates polling anti-patterns.
- APIDESIGN-D-4: When the consumer set is fully internal (all callers are internal services or known partner systems using dedicated client libraries) and the team has header-versioning discipline established in existing services, URL path versioning remains the default; header versioning (`API-Version: YYYY-MM-DD`) is viable as an alternative and may be adopted if the team's API gateway enforces it uniformly.
- APIDESIGN-D-5: When the collection dataset exceeds 10 000 rows or the resource has high write throughput (records inserted or deleted while a consumer is paginating), choose cursor-based pagination over offset/page pagination because offset pagination degrades to O(n) full-table scans at high page numbers, and concurrent writes cause rows to be skipped or duplicated across pages.
- APIDESIGN-D-6: When the API is consumed by a third-party developer ecosystem (public API, developer portal), choose API key authentication over OAuth 2.0 as the primary auth mechanism for M2M callers because API keys have zero OAuth token-exchange friction and are the industry standard for developer-portal integrations; OAuth 2.0 Authorization Code remains required for any flow involving an end-user identity.
- APIDESIGN-D-7: When the API runs exclusively within a mutually-authenticated service mesh (e.g. Istio mTLS enforced at the pod level with no external ingress), no-auth at the application layer is acceptable provided the intent document captures the full infrastructure rationale; OAuth 2.0 is still preferred if any path allows mesh bypass.
- APIDESIGN-D-8: When any mutation (POST, PUT, PATCH, DELETE) is exposed to clients over an unreliable network (mobile, high-latency WAN, or any retry-capable HTTP client), require an `Idempotency-Key: <uuid>` request header for that mutation because network timeouts cause ambiguous partial writes; idempotency keys allow safe client retries without duplicate side effects.

## Section 5 — Recommendation Output Contract

For each Decision Domain, the consuming agent MUST emit:

1. **Domain name and chosen value** — name the concrete choice (e.g. "REST over HTTP/1.1 + JSON", not "a RESTful style").
2. **Rule citation** — list each `APIDESIGN-D-N` rule that fired; if no derivation rule fired, state "defaults apply (no derivation rule fired)".
3. **At least one named alternative** with a one-line rationale for when it would be preferred instead.
4. **Override hook** — a concrete instruction for the user to record a different choice (e.g. "Override APIDESIGN-1 by declaring your preferred style in the API Design Intent document under `## API Style`").

The recommendation must be emitted before asking the user any clarifying question. The user can accept the default, trigger an override, or provide a constraint that fires a derivation rule. Neutral "here are your options, you decide" output without a named recommendation violates PIT-11 and must not appear.

Consumers of this pack MUST NOT omit the rule citation or the override hook. Omitting either makes the recommendation unverifiable and prevents later audits from reconstructing the decision.

## Section 6 — Enforcement Handoff

api-design-craft output is validated by rest-quality-rubric. The rubric's 8 checks verify that the chosen API style and error model have been correctly applied in the final OpenAPI spec — including noun-plural resource paths (Check 1), no verb paths (Check 2), correct 4xx status diversity (Check 7), and pagination parameters on collection endpoints (Check 8). Any recommendation from this pack that results in a spec violating these checks constitutes a craft-pack enforcement failure.
