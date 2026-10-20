---
schema_version: "1.0.0"
id: S-002
type: story
parent: E-001
title: "Order confirmation"
status: draft
persona: P-001
wsjf:
  business_value: 3
  time_criticality: 2
  risk_reduction: 1
  job_size: 2
priority: null
pin: null
blocked_by: []
spec: null
context_feature: null
builds: []
created: 2026-07-01
updated: 2026-07-01
closed: null
shipped: null
---
# S-002 — Order confirmation

## Story
As **Maya the Maintainer** (P-001), I want an order confirmation page, so that I know the payment went through.

## Acceptance criteria
- [ ] AC-1: Given a completed payment, when the page loads, then the order number is shown.
- [ ] AC-2: Given a failed payment, when the page loads, then a retry option appears.

## Out of scope
- Email receipts

## Notes
counters.story is 1 in the passport but this file makes the max existing story ID 2 — [COUNTER].
