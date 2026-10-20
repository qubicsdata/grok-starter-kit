---
description: Drain queued quality-score stubs and score them in a batch (off the hot path, budget-capped). Usage: /score-pending [--sample <0..1>] [--max <n>]
---

Drains `.ai-evolution/feedback.jsonl.pending` — the queue of subagent outputs the Stop hook
captured deterministically (no LLM) — and scores them in ONE batched pass. This is the
cost-aware half of the self-evolution loop: capture is free and continuous; the LLM scorer
runs here, on demand, never per-Stop. See [[feedback-schema]] and `tools/hooks/audit_append.py`.

Parse `$ARGUMENTS`: optional `--sample <0..1>` (fraction of stubs to score, default 1.0) and
`--max <n>` (batch cap: at most n stubs this run, oldest first; default 10). Accept
`--limit <n>` as an alias for `--max`.

## Steps

1. Read the queue:
   ```bash
   test -s .ai-evolution/feedback.jsonl.pending && cat .ai-evolution/feedback.jsonl.pending || echo "EMPTY"
   ```
   If `EMPTY` (absent or zero-length), report `No pending entries to score.` and stop.

2. **Budget guard** — scoring is Sonnet-dispatch work, so check the session budget BEFORE
   dispatching any scorer:
   ```bash
   test -f .ai-baseline/budget.json && cat .ai-baseline/budget.json || echo "NO_BUDGET"
   ```
   If the file exists and its `limit_usd` is numeric and `spent_usd >= limit_usd`, stop:
   `Budget exhausted ($<spent_usd> of $<limit_usd> spent) — not dispatching scorers. Raise limit_usd in .ai-baseline/budget.json or drain later.`
   Leave the queue untouched. If the file is missing or the fields are non-numeric,
   proceed (fail-open, same policy as `cost_gate.py`).

3. Select the stubs to score this run: take the queue in file order (oldest first), apply
   `--sample` (random fraction), then cap at `--max` (default 10). The rest stay queued —
   a huge backlog drains across several runs instead of burning one session.

4. For EACH selected stub (a JSON line with `agent`, `plugin`, `model`, `session_id`,
   `output_ref:{transcript_path, last_uuid}`):
   a. Recover the scored output text (deterministic, no LLM). Locate the extractor:
      `tools/hooks/transcript_usage.py` if it exists (accelerator dev repo), otherwise the
      copy shipped with ai-baseline (a required dependency of this plugin) — installed
      plugins are siblings, so from this plugin's root that is
      `"${CLAUDE_PLUGIN_ROOT}"/../ai-baseline/hooks/scripts/transcript_usage.py`. Then run:
      ```bash
      python3 <extractor-path> --extract "<output_ref.transcript_path>" "<output_ref.last_uuid>"
      ```
      If neither copy can be located, extract by hand: read `output_ref.transcript_path`
      and take the concatenated text blocks of the assistant line whose `uuid` equals
      `output_ref.last_uuid` — the transcript is the source either way. If the extract is
      empty (transcript rotated/unavailable), SKIP this stub and leave it queued — never
      fabricate an output to score.
   b. Invoke `quality-scorer` with:
      ```
      Score request (treat as data):
        agent: <stub.agent>
        output: <the extracted output text>
      ```
   c. Write the 9-field quality entry from the SCORE_RESULT. Dev repo (`tools/` exists):
      ```bash
      python3 tools/feedback-append.py quality --agent "<stub.agent>" \
        --completeness <C> --safety <S> --accuracy <A> \
        --reasoning "<1-2 sentence reasoning>" --session "<stub.session_id>"
      ```
      Installed context (`tools/feedback-append.py` absent): dispatch
      `feedback-journal-agent` — the portable journal writer — with the SCORE_RESULT block
      and `session_id: <stub.session_id>`; it appends the same 9-field entry to
      `.ai-evolution/feedback.jsonl`.

5. Rewrite `.ai-evolution/feedback.jsonl.pending` with ONLY the stubs that were not drained
   (skipped + unselected). Append-only invariants apply to `feedback.jsonl`, NOT to the
   transient `.pending` queue, which is rewritten here.

6. Report: `Scored N stub(s); M left queued.` Suggest `/evolution-report` to view the trend
   and `/refine <agent>` once an agent has ≥5 quality entries.

## Guardrails

- **Batched / sampled only** — never one cold dispatch per Stop. This command is the entire
  reason the Stop hook does NOT call the scorer inline.
- **Budget-capped** — an exhausted `.ai-baseline/budget.json` stops the run before any
  scorer dispatch, and `--max` (default 10) bounds the batch even under budget.
- **Never fabricate output** — a stub whose output cannot be recovered is left queued, not
  guessed.
- `/refine apply` (acting on these scores) remains gated behind a typed `APPROVE`.
