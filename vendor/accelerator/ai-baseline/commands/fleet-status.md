---
description: Fleet-global telemetry rollup — use when asking "how much has each project spent", "which repo is busiest", or "show me the whole fleet". Syncs this repo's audit + feedback journals to ~/.accelerator/ and prints the cross-repo table. Usage: /fleet-status
---

Run the global rollup, then present the fleet table.

1. **Locate the script.** If `ai-baseline/scripts/global_rollup.py` exists under the
   project root (you are in the accelerator dev repo), use that path. Otherwise use the
   installed copy: `"${CLAUDE_PLUGIN_ROOT}"/scripts/global_rollup.py`.

2. **Sync this repo up, then report across all repos** (two invocations, in order):

   ```bash
   python3 <script-path> --sync
   python3 <script-path> --report
   ```

   The script is fail-open — if it prints a `[global_rollup] warning:` line, show the
   warning verbatim and stop; do not fabricate a table.

3. **Present the table exactly as printed** (repo, records, est. cost in cost-units,
   last record — the newest journal timestamp, not the last sync time). Do not
   re-derive or reformat the numbers.

4. **Add at most one earned insight**, and only if the data supports it — e.g. "repo X
   accounts for N% of fleet cost" or "repo Y has no recorded activity since <date>". One sentence,
   grounded in the table. No recommendations, no advice spam. If nothing stands out,
   add nothing.

If the report says no repos are synced yet, say so plainly and note that running
`/fleet-status` from each project registers it — nothing else.
