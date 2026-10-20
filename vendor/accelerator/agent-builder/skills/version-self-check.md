---
name: version-self-check
description: Use on every /build-agent invocation, after runtime-knowledge-fetch — checks whether a newer version of agent-builder is available and surfaces a non-blocking upgrade banner if so
---

# Version Self-Check

Check for a newer published version of agent-builder on every invocation. This keeps users aware of updates without blocking their current task.

## Steps

1. **Read current version** from `agent-builder/.claude-plugin/plugin.json` → `version` field.

<!-- kit:release-check:begin -->
2. **Query for latest version: skipped.** The release check is off: `kit.homepage` is empty in `kit.config.yaml`, so there is no place to ask. Do not fetch anything; skip steps 3 and 4 and record `Latest: unknown (release check off)` and `Status: check disabled` in step 5.
<!-- kit:release-check:end -->

3. **Compare versions** using semver ordering (major.minor.patch).

4. **If a newer version exists**, surface this banner to the user (non-blocking — do not pause the session):

```
──────────────────────────────────────────────────
 agent-builder [newer-version] is available.
 You are running [current-version].
 Run: /plugin update agent-builder@accelerator
──────────────────────────────────────────────────
```

5. **Append result to session plan file** under `## Version Check`:

```markdown
## Version Check
Current: [current-version]
Latest:  [latest-version or "unknown (fetch failed)"]
Status:  [up to date / update available / check failed]
```

## STOP

DO NOT block the current task if the version check fails or if a newer version is available. This is an informational step only. Never prompt the user to upgrade before completing their request.
