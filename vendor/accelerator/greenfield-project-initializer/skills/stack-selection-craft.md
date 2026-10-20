---
name: stack-selection-craft
description: Opinionated, tiered stack-selection expertise across all eight layers that tech-stack-agent covers. Encodes expert defaults and constraint-driven derivation rules so the agent leads with a recommendation rather than a neutral menu. Consumed by tech-stack-agent.
---

# Stack Selection Craft

## Section 1 — Decision Domains

- STACKSEL-1 Language / runtime (the primary execution environment and language)
- STACKSEL-2 Application framework (the server or fullstack framework that hosts routing, middleware, and request handling)
- STACKSEL-3 Primary data store (relational, document, or wide-column; the source-of-truth database)
- STACKSEL-4 Caching layer (in-process cache, distributed cache, or none)
- STACKSEL-5 API style (REST, GraphQL, gRPC, or event-driven messaging)
- STACKSEL-6 Authentication / authorisation (managed identity provider, self-hosted auth server, or embedded library)
- STACKSEL-7 Infrastructure / hosting (cloud provider, container runtime, IaC tool)
- STACKSEL-8 Observability (logging, metrics, tracing — each as a sub-concern)
- STACKSEL-9 Testing framework (unit, integration, and end-to-end toolchain)

## Section 2 — Constraint Inputs

- **Throughput / scale NFR** → STACKSEL-1, STACKSEL-3, STACKSEL-4 (high write throughput may require a runtime with native async I/O and a cache layer)
- **Team language familiarity** → STACKSEL-1, STACKSEL-2 (an unfamiliar language multiplies onboarding cost; default to the team's majority language when stated)
- **Data model shape** (relational/transactional vs document vs analytical) → STACKSEL-3 (drives primary store selection more than any other factor)
- **Real-time or streaming requirement** → STACKSEL-5, STACKSEL-3 (real-time reads push toward event-driven or GraphQL subscriptions; real-time writes push toward a message broker)
- **Multi-tenancy / compliance requirement** (SOC 2, HIPAA, GDPR) → STACKSEL-6, STACKSEL-7 (managed identity and a cloud provider with a compliance programme reduce audit surface)
- **Team size and DevOps maturity** → STACKSEL-7 (small teams with low DevOps maturity should avoid self-managed Kubernetes in favour of managed container services)
- **Latency budget (p99 target)** → STACKSEL-1, STACKSEL-4 (tight p99 SLAs favour a compiled language or a JIT-warmed JVM runtime plus a distributed cache)
- **Monolith vs microservices architecture shape** (from system design) → STACKSEL-2, STACKSEL-5, STACKSEL-7 (microservices demand service mesh, API gateway, and per-service deployability)
- **Budget / cost sensitivity** → STACKSEL-7, STACKSEL-8 (serverless or managed PaaS cuts operational overhead; commercial APM tools add per-seat cost)
- **Public-facing SEO or SSR requirement** → STACKSEL-2 (server-side rendering requires a framework that supports it)

## Section 3 — Opinionated Defaults

These defaults apply when the constraint inputs above are silent. They are defensible first choices, not the only valid choices.

- **STACKSEL-1 (Language / runtime):** Node.js LTS (TypeScript) for backend services and APIs. Rationale: large ecosystem, ubiquitous npm tooling, shared language with most frontend teams, strong async I/O model for network-bound services, and long-term support cadence.
- **STACKSEL-2 (Application framework):** Express.js for REST APIs in a modular monolith; Fastify when throughput matters. For fullstack applications with SSR, Next.js on Node.js. Rationale: Express has the broadest middleware ecosystem; Fastify's schema-based validation and benchmarked throughput make it the upgrade path; Next.js remains the most complete fullstack React framework.
- **STACKSEL-3 (Primary data store):** PostgreSQL (latest stable). Rationale: ACID-compliant, mature, excellent indexing, JSONB support covers semi-structured needs, proven at scale, strong managed-service availability on every major cloud. Relational-first is the safe default unless the data model is explicitly document-shaped or write-throughput is extreme.
- **STACKSEL-4 (Caching layer):** No dedicated cache for projects with low read latency requirements. Redis (managed) when a cache is needed. Rationale: an unnecessary cache adds operational surface; when latency or DB load becomes a constraint, Redis is the default choice due to ubiquitous cloud-managed offerings and broad client library support.
- **STACKSEL-5 (API style):** REST (JSON over HTTPS) with OpenAPI 3.x documentation. Rationale: universally understood, supported by every HTTP client, easy to document, version, and cache. GraphQL is the default when the client data-shape varies widely across consumers and under-fetching or over-fetching is a real cost.
- **STACKSEL-6 (Auth / authz):** A managed identity provider — Auth0 or AWS Cognito depending on cloud choice. Rationale: delegating auth to a managed service eliminates token-rotation, password-hashing, and MFA implementation risk; critical for any user-facing application; self-hosted only when data-residency regulations prohibit third-party identity services.
- **STACKSEL-7 (Infrastructure / hosting):** AWS as cloud provider; ECS Fargate for container workloads; Terraform for IaC. Rationale: AWS has the broadest managed-service catalogue, mature compliance programmes, and the largest talent pool; Fargate removes cluster management overhead vs self-managed EC2 or EKS; Terraform is cloud-agnostic and has first-class provider support.
- **STACKSEL-8 (Observability):** Structured JSON logging via a lightweight library (pino for Node.js); Prometheus + Grafana for metrics; OpenTelemetry SDK for distributed traces exported to a managed backend (AWS X-Ray or Grafana Tempo). Rationale: vendor-agnostic instrumentation via OpenTelemetry avoids lock-in; pino is the fastest Node.js logger; Prometheus is the de-facto open-source metrics standard.
- **STACKSEL-9 (Testing framework):** Vitest (or Jest) for unit and integration tests; Playwright for end-to-end tests. Rationale: Vitest is ESM-native and faster than Jest for TypeScript projects; Playwright has the widest browser coverage and stable auto-waiting API for E2E.

## Section 4 — Derivation Rules

Each rule fires when the stated constraint appears in `docs/requirements.md` or `docs/system-design.md`. Rules override the defaults above; cite the rule ID in the recommendation.

- **STACKSEL-D-1:** When the NFR specifies high write throughput (>5 k writes/s sustained) or extreme low latency (p99 < 10 ms), choose Go or Rust as the runtime because both compile to native binaries with predictable latency and minimal GC pauses — advantages that Node.js cannot match under sustained write pressure.
- **STACKSEL-D-2:** When the requirements state the team's primary language is Python (majority of engineers), choose Python with FastAPI as the application framework because forcing a language switch increases onboarding cost and error rate more than any tooling benefit; FastAPI provides async I/O, automatic OpenAPI generation, and strong type-checking via Pydantic.
- **STACKSEL-D-3:** When the data model is explicitly document-shaped (deeply nested, schema-variable, content-management, or catalog-style) with no strong relational join requirements, choose MongoDB (the vendor's managed cloud service) as the primary data store because a document store avoids the impedance mismatch of normalising variable-schema data into relational tables, reducing query complexity and migration surface.
- **STACKSEL-D-4:** When the architecture shape is microservices (from system design) with ≥3 independently deployed services, choose gRPC for inter-service communication (over REST) because gRPC provides strongly typed contracts via Protobuf, bi-directional streaming, and lower serialisation overhead than JSON — which compounds across many service boundaries.
- **STACKSEL-D-5:** When the system design specifies a real-time feature (live feeds, collaborative editing, push notifications, or event sourcing), choose an event-driven API style with a message broker (AWS SNS/SQS or Kafka) as the primary integration bus because polling-based REST cannot deliver sub-second latency for high-frequency state changes without overwhelming the DB.
- **STACKSEL-D-6:** When a compliance requirement (HIPAA, GDPR data-residency, or PCI DSS) prohibits third-party identity processors outside the project's own infrastructure, choose Keycloak (self-hosted, container-based) for auth instead of a managed SaaS identity provider because Keycloak gives full control over data residency and audit logs while still providing OpenID Connect and RBAC without building auth from scratch.
- **STACKSEL-D-7:** When team DevOps maturity is low (small team, no dedicated SRE, first cloud deployment) or the project budget prohibits managed Kubernetes, choose a managed PaaS (Railway, Render, or AWS App Runner) over ECS/EKS because eliminating cluster management risk is worth the reduced configurability — the operational complexity of Kubernetes for a small team routinely exceeds the engineering cost of the product itself.
- **STACKSEL-D-8:** When the client data-shape varies significantly across consumers (mobile app needs a subset, dashboard needs aggregates, third-party partner needs a different projection), choose GraphQL because it eliminates the over-fetching and under-fetching that leads to bespoke REST endpoints proliferating across the codebase.
- **STACKSEL-D-9:** When the project has a strict cost budget (early-stage startup or internal tooling with low traffic), choose a serverless compute model (AWS Lambda or Vercel Functions) for the application layer because pay-per-invocation pricing eliminates idle compute cost that flat EC2/ECS pricing incurs.
- **STACKSEL-D-10:** When a commercial APM budget is available and the team lacks observability engineering capacity, choose a fully managed observability platform (Datadog or New Relic) over the open-source Prometheus + Grafana stack because it reduces the time-to-first-alert from days to hours and provides pre-built service maps without custom dashboarding effort.

## Section 5 — Recommendation Output Contract

For each decision domain (STACKSEL-1 through STACKSEL-9), tech-stack-agent MUST emit:

1. **Recommended choice** — a named technology, not an abstract category (e.g. "PostgreSQL 16", not "a relational database"). This appears FIRST, before alternatives.
2. **Rule citation** — the `STACKSEL-D-N` rule(s) that fired, or "defaults apply (STACKSEL-3 default)" when no derivation rule fired. The rule citation is mandatory; it makes the recommendation auditable.
3. **At least one named alternative** — with its tech-radar ring (Adopt / Trial / Assess / Hold) and a one-sentence rationale distinguishing it from the recommendation. Hold-rated alternatives must be marked with the standard Hold warning.
4. **Override hook** — a concrete instruction: "To override, state your preference and the agent will record the deviation in the pending ADR."

Every recommendation MUST cite its tech-radar ring. A Hold-rated technology MUST NOT appear as the recommended choice. If a derivation rule would produce a Hold-rated recommendation, fall back to the next-best non-Hold option and note the constraint conflict in the pending ADR.

Agents consuming this pack must not present a neutral "here are options, you decide" table without a leading recommendation. The recommendation is the first thing shown; alternatives and trade-offs follow it.

## Section 6 — Enforcement Handoff

stack-selection-craft output is validated by tech-radar (every recommended technology and every named alternative must carry an Adopt/Trial/Assess/Hold ring classification produced by the tech-radar skill; no Hold-rated technology may appear as the primary recommendation).
