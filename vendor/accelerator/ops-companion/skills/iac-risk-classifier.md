---
name: iac-risk-classifier
description: |
  Classifies each IaC resource change as GLOBAL / ENVIRONMENT / SERVICE / CONFIG by blast radius. Tags irreversible changes (resource deletions, encryption key rotation, DNS cutover). Used by iac-reviewer on every resource change found.
---

# iac-risk-classifier

Apply this classifier to every resource change found in the IaC files under review. Assign a blast-radius label and flag irreversible operations.

---

## Blast-radius labels

### GLOBAL
The change affects all environments simultaneously, or affects shared infrastructure used by multiple environments.

**Examples:**
- Changes to a shared VPC, transit gateway, or network peering used by prod and staging
- IAM policy changes to a role assumed by all environments
- DNS zone changes for the root domain
- Shared secrets manager policy changes
- KMS key policy or key rotation changes

**Required action:** When any GLOBAL change is found, output a hard warning block before the findings list:

```
WARNING: GLOBAL blast-radius changes detected. These affect all environments simultaneously.
Review each item below before applying.
```

### ENVIRONMENT
The change affects a single named environment (production, staging, dev) but not others.

**Examples:**
- RDS instance type change in the `production` environment module
- Auto-scaling policy change scoped to `env = "staging"`
- Environment-specific security group rule change
- ECS task definition update for one environment's service

### SERVICE
The change affects a single service or component within an environment.

**Examples:**
- Lambda function memory or timeout change
- A single S3 bucket policy change for a specific service bucket
- Container image tag update for one service
- SQS queue visibility timeout change for one queue

### CONFIG
A non-destructive configuration change with low blast radius.

**Examples:**
- Adding a tag to a resource
- Changing a description field
- Updating a non-functional comment in a template
- Changing a monitoring threshold that does not affect resource provisioning

---

## Irreversible operation tags

Tag the following operations as `[IRREVERSIBLE]` in the findings report. These require explicit user acknowledgement before being applied.

| Operation type | Examples |
|---|---|
| Resource deletion | `terraform destroy`, removing a resource block, setting `deletion_protection = false` then removing |
| Encryption key rotation | Rotating or deleting a KMS key; changing `kms_key_id` on an encrypted resource |
| DNS cutover | Changing an A/ALIAS record pointing to a load balancer or CloudFront |
| Database engine upgrade | `engine_version` change on an RDS instance or cluster |
| Irreversible schema migration | Applied via IaC (note: this is unusual but possible with Lambda-backed custom resources) |
| Storage class downgrade | Changing `storage_class` in a way that does not support downgrade |
| Security group removal | Removing a security group that is referenced by other resources |

For every `[IRREVERSIBLE]` tag, add a CAUTION block:

```
CAUTION [IRREVERSIBLE]: [resource name/type] — [what makes this irreversible and what the consequence is].
Acknowledge before applying: confirm you have a tested rollback path or accept permanent change.
```

---

## Output format per resource

```
[blast-radius label] [resource type] "[resource name]"
  Change: [brief description of what is changing]
  [IRREVERSIBLE] (if applicable) — [reason]
  Severity: CRITICAL | HIGH | MEDIUM | LOW
```

Severity rules:
- CRITICAL: GLOBAL blast radius, or any IRREVERSIBLE change
- HIGH: ENVIRONMENT blast radius with destructive potential (deletion, encryption change)
- MEDIUM: SERVICE blast radius with non-trivial change
- LOW: CONFIG blast radius
