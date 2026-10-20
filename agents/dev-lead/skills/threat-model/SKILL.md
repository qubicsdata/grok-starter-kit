---
name: threat-model
description: >-
  Use this when asked for a STRIDE threat model of a system, service, or
  feature.
---
# Steps
1. Describe scope: components, data flows, actors, external dependencies (a simple DFD in text/mermaid).
2. List assets (data, credentials, availability, reputation) with sensitivity.
3. Mark trust boundaries and entry points.
4. For each component/flow, enumerate threats per STRIDE: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege.
5. Rate each threat (likelihood x impact) and list existing and recommended mitigations.
6. State residual risk per threat and overall; note assumptions and open questions.
7. Output a table: ID, component, STRIDE category, threat, rating, mitigation, residual risk.
