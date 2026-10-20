# api-designer

A Claude Code plugin for design-first API development. Takes a team from "I need to build an API" to a confirmed OpenAPI 3.1 contract — before a line of implementation is written.

## Modes

| Mode | Entry command | Description |
|------|--------------|-------------|
| Full lifecycle | `/api-design` | Guided intent → resources → schemas → security → spec → review |
| Standalone intent | `/api-intent` | Elicit API description only |
| Standalone resources | `/api-resources` | Model resources from existing intent doc |
| Standalone schemas | `/api-schemas` | Define schemas from existing resource model |
| Standalone security | `/api-security` | Capture security contract from existing intent doc |
| Standalone spec | `/api-spec` | Generate OpenAPI spec from all three design docs |
| Standalone review | `/api-review [spec-path]` | Review an existing spec for REST quality and completeness |
| Breaking changes | `/api-breaking-changes [old] [new]` | Diff two spec versions, classify every change |
| Versioning advice | `/api-version` | Get a versioning strategy recommendation |

## Artifacts Produced

| Artifact | Path |
|----------|------|
| API intent document | `docs/api-design/api-design-intent.md` |
| Resource model | `docs/api-design/api-design-resources.md` |
| Schema inventory | `docs/api-design/api-design-schemas.md` |
| OpenAPI 3.1 specification | `openapi.yaml` (project root) |
| Contract review report | `docs/api-design/api-review-report.md` |
| Breaking change report | `docs/api-design/breaking-changes-[old]-to-[new].md` |
| Session state | `.api-design-state.json` (project root) |

## Phase Order (full lifecycle)

1. **Intent** — `intent-agent` asks 6 questions; produces `api-design-intent.md`
2. **Resources** — `resource-modeler` maps nouns to REST paths; produces `api-design-resources.md`
3. **Schemas** — `schema-agent` defines request/response/error shapes; produces `api-design-schemas.md`
4. **Security** — `security-contract-agent` asks 5 security questions; appends `## Security Contract` to `api-design-intent.md`
5. **Gate** — `api-readiness-checklist` (all 7 items must PASS; blocks spec generation if any fail)
6. **Spec** — `spec-generator` writes `openapi.yaml` atomically after user confirmation
7. **Review** — `contract-reviewer` produces findings report; user confirms save

## Out of Scope (v1)

- Server stub generation
- Client SDK generation
- Mock server startup
- AsyncAPI YAML generation (extension point declared; full support is v2)
- GraphQL, gRPC, protobuf design
- Deployment or API gateway configuration

---

**Author:** <your-name> — you@example.com

## Dependencies

- requires: ai-baseline
