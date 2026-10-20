---
name: pr-review
description: >-
  Use this when asked to review a pull request for correctness, security, tests,
  and clarity.
---
# Steps
1. Fetch PR metadata, description, diff, changed files, and CI checks.
2. Read surrounding code where needed to understand intent.
3. Review for: correctness (logic, edge cases, error handling, concurrency), security (injection, authz, secrets, unsafe deps), tests (coverage of new behavior, quality), clarity (naming, structure, docs).
4. Output findings grouped by severity (Critical, High, Medium, Low, Nit), each with file:line, the problem, and a suggested fix. Add a short overall verdict.
5. Post nothing (comments, reviews, approvals) without explicit user approval; present drafted comments for approval instead.
