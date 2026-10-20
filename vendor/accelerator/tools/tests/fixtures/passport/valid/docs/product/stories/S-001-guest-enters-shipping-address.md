---
schema_version: "1.0.0"
id: S-001
type: story
parent: F-001
title: "Guest enters shipping address"
status: ready
persona: P-001
wsjf:
  business_value: 5
  time_criticality: 3
  risk_reduction: 1
  job_size: 3
priority: 3.0
pin: null
blocked_by: []
spec: null
context_feature: null
builds: []
created: 2026-07-01
updated: 2026-07-02
closed: null
shipped: null
---
# S-001 — Guest enters shipping address

## Story
As **Maya the Maintainer** (P-001), I want to enter a shipping address without creating an account, so that I can complete checkout in one sitting.

## Acceptance criteria
- [ ] AC-1: Given an empty address form, when I submit a valid address, then the form advances to payment.
- [ ] AC-2: Given an invalid postcode, when I submit the form, then a field-level error names the postcode.

## Out of scope
- Address book persistence

## Notes
