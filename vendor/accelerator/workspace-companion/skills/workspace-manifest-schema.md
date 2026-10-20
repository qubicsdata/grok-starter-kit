---
name: workspace-manifest-schema
description: The schema for .accelerator-workspace.yaml — the source of truth describing repos, services, and their cross-repo dependencies. Read before writing or interpreting the manifest.
---

# Workspace Manifest Schema

`.accelerator-workspace.yaml` lives at the workspace root (the parent directory holding the repos).

```yaml
workspace: <name>
generated: <ISO 8601>          # set by workspace-mapper on write
repos:
  - name: <repo>
    path: <relative path from workspace root>
    languages: [<lang>, ...]
    services:
      - name: <service>
        kind: api | worker | library | frontend
        exposes: [<contract or endpoint id>, ...]
        depends_on: [<service name>, ...]   # names of services in any repo
        depends_on_candidates: [<service name>, ...]  # inferred-but-unconfirmed edges
```

## Rules
- `name` values for services are unique across the whole workspace (used as edge identifiers).
- `depends_on` holds confirmed edges; `depends_on_candidates` holds inferred edges needing human confirmation — NEVER promote a candidate to a confirmed edge automatically.
- `generated` is set only by workspace-mapper; readers never modify it.
