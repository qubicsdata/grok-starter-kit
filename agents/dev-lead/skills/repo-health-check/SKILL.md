---
name: repo-health-check
description: >-
  Use this when asked for a read-only health review of a GitHub repo or org
  (activity, PRs, issues, CI, stale branches).
---
# Steps
1. Confirm the target repo(s)/org. Read-only: never comment, label, merge, or delete.
2. Recent commits on the default branch (last 14-30 days): cadence, authors, notable changes.
3. Open PRs: age, review state, CI status, conflicts; flag PRs idle >14 days.
4. Open issues: count, oldest, unlabeled/unassigned, recent bugs.
5. CI: latest workflow runs on the default branch; failure rate, flaky or long-red jobs.
6. Branches: list stale branches (no commits >90 days, merged-but-not-deleted).
7. Report: summary, then findings by severity. Every finding cites repo, commit SHA, PR/issue #, or run URL. End with suggested actions (not taken).
