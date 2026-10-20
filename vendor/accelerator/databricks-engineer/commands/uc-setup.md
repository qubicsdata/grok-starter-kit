---
description: "Set up Unity Catalog catalogs, schemas, grants, and PII tags per the five-catalog layout. Usage: /uc-setup"
---

Dispatch uc-steward with the following instructions:

The user has invoked `/uc-setup`.

**Dispatch:**

Invoke uc-steward with no required initial arguments. uc-steward will guide the user through the setup interactively.

uc-steward will:
1. Check that DATABRICKS_CONFIG_PROFILE is set; stop if absent
2. Ask the user which operations they want to perform:
   - Create catalogs and schemas per the five-catalog layout (landing, bronze, silver, gold, outbound, migration_meta)
   - Issue GRANT statements for service principals or groups
   - Apply PII column tags
   - Query lineage views
   - Validate naming conventions
3. Validate all names against naming conventions before generating DDL
4. Present all generated DDL for user confirmation before executing
5. Require explicit "CONFIRM" before DROP, DELETE, or ALTER on any catalog or schema
