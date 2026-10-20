# compliance-companion

Optional plugin — EU AI Act high-risk regime tooling for customer-facing deployments.

## Scope

Provides tooling scaffolding for EU AI Act compliance. Does NOT certify conformity — Art. 43 conformity assessment requires a qualified third-party body.

## Commands

- `/oversight` — mandatory human-in-the-loop approval checkpoint (Art. 14)
- `/explain <agent> <action>` — plain-language explanation of AI decision (Art. 86)
- `/ai-incident` — format and log a serious AI incident (Art. 62)
- `/model-card <agent>` — scaffold a model card for an agent (Art. 13)

## Author

<your-name> (you@example.com)

## Dependencies

- requires: ai-baseline
