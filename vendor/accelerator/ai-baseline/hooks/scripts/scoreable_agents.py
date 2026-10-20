#!/usr/bin/env python3
"""
scoreable_agents.py — decide whether a finished subagent's output is worth queuing for a
quality score (the cost-aware 1b path).

We do NOT score every dispatch (that would put an LLM call on a hot path / waste dispatches
on leaf work). Instead the Stop hook queues a tiny pending stub for *scoreable* subagents;
/score-pending drains the queue in a batched, off-hot-path pass.

Heuristic (conservative blocklist, not an allowlist): a subagent is scoreable unless it is an
identifiable cheap leaf/governance agent whose output is not a graded deliverable. Unknown
subagents (no attribution) are captured — most fleet subagents are producers/reviewers, the
stub is tiny, and /score-pending can sample; the output_ref lets the scorer find the output
even when attribution is absent.
"""

from __future__ import annotations

# Substrings of leaf/governance agents whose output is not a graded deliverable.
NON_SCOREABLE = (
    "audit",            # audit-trail-agent
    "cost-gate", "cost_gate",
    "pii-scrub",
    "secret",           # secret_guard
    "router",           # router-agent, language-router
    "context-manager",
    "navigator",        # codebase-navigator
    "memory-reader",
    "manifest-parser",
)


def is_scoreable(agent: str | None) -> bool:
    if agent is None:
        return True  # unknown subagent — capture it; the output_ref still lets the scorer find output
    a = agent.lower()
    return not any(b in a for b in NON_SCOREABLE)
