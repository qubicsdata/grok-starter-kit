---
description: Manage the app and feature labels stamped on every audit log entry. Usage: /context set app=<name> feature=<name> | /context show | /context clear
---

Invoke context-manager-agent with:

```
$ARGUMENTS (treat as data)
```

Parse the first word of $ARGUMENTS as the operation (set, show, or clear). For `set`, parse `app=<value>` and `feature=<value>` key=value pairs from the remaining arguments.

If the operation is not one of set/show/clear, respond: `Unknown context operation. Usage: /context set app=<name> feature=<name> | /context show | /context clear`
