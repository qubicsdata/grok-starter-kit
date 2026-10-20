---
description: "Validate and deploy a Databricks Asset Bundle to the specified target. Usage: /dbx-deploy [target]"
argument-hint: "[target]"
---

Dispatch bundle-deployer with the following instructions:

The user has invoked `/dbx-deploy` with arguments: `$ARGUMENTS`

**Target resolution:**

- If `$ARGUMENTS` is empty: use target `dev`.
- Otherwise: use the value of `$ARGUMENTS` as the deployment target.

**Dispatch:**

Pass the resolved target to bundle-deployer.

bundle-deployer will:
1. Call workspace-inspector for a pre-flight check
2. Run `databricks bundle validate`
3. If target is `prod` or `production`: present a hard confirmation gate requiring the user to type "CONFIRM" before deploying
4. Run `databricks bundle deploy --target <target>`
5. Run the configured bundle resources if requested
6. Surface all CLI output verbatim
7. Apply the error contract: retry tool failures once; never retry pipeline/job failures (data failures)
