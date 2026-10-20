---
schema_version: "1.0.0"
id: S-002
type: story
parent: F-001
title: "Rate limiting on checkout API"
status: done
persona: P-001
wsjf:
  business_value: 5
  time_criticality: 5
  risk_reduction: 2
  job_size: 3
priority: 4.0
pin: null
blocked_by: []
spec: docs/specs/0001-rate-limiting.md
context_feature: F-001-guest-checkout
builds: []
created: 2026-07-01
updated: 2026-07-02
closed: 2026-07-02
shipped: "Checkout API rate-limited at 10 req/min per IP"
---
# S-002 — Rate limiting on checkout API

## Story
As **Maya the Maintainer** (P-001), I want the checkout API rate-limited, so that abuse cannot exhaust the payment-provider quota.

## Acceptance criteria
- [x] AC-1: Given 10 requests within a minute, when an 11th arrives, then it receives HTTP 429. — evidence: test_rate_limit_429
- [x] AC-2: Given a throttled client, when the window resets, then requests succeed again. — evidence: test_rate_limit_window_reset

## Out of scope
- Per-account quotas

## Notes

## Build record
- spec: docs/specs/0001-rate-limiting.md
- commits: 1a2b3c4..5d6e7f8
- review: standard — approved
- date: 2026-07-02
