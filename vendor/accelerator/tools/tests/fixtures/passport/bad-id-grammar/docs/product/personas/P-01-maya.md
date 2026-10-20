---
schema_version: "1.0.0"
id: P-01
type: persona
name: "Maya the Maintainer"
role: data-analyst
status: active
created: 2026-07-01
---

## Goals
- Ship billing features without touching infra
- Keep the monthly close under one hour

## Pains
- Manual invoice reconciliation
- No visibility into usage spikes

## Context
Two-digit ID — violates the ^[EFSP]-\d{3}$ grammar.

## Success looks like
The checker flags this file with [ID-GRAMMAR].
