---
name: service-graph-spec
description: How to compute reachability and blast radius over the workspace service graph defined in the manifest. Read before answering impact queries.
---

# Service Graph Spec

The manifest's services + `depends_on` edges form a directed graph: an edge A → B means "A depends on B" (B is a provider, A is a consumer).

## Definitions
- **Dependents of S** = all services that transitively depend on S (follow edges backward). These are affected if S changes.
- **Dependencies of S** = all services S transitively depends on (follow edges forward).
- **Blast radius of changing S** = the set of dependents of S, plus S itself.

## Rules
- Traverse confirmed `depends_on` edges only; list `depends_on_candidates` separately as "possible additional impact (unconfirmed)".
- Detect and report cycles rather than looping forever.
