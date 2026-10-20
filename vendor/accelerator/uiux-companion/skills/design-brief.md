---
name: design-brief
description: The canonical constraint-input vocabulary for the craft layer. The design-advisor asks these dimensions; the spec-enricher infers them from spec text. Each dimension has a value set and a default so an under-specified brief still yields a tier-1 recommendation.
---

# Design Brief

The tier-2 derivation inputs for all craft packs. Each dimension has a defined value set and a default.

| Dimension | Value set | Default | Drives |
|-----------|-----------|---------|--------|
| Audience / domain | finance, consumer, dev-tool, healthcare, enterprise, public-sector | consumer | conservatism, contrast, hue family |
| Brand personality | trustworthy, playful, premium, utilitarian, bold | trustworthy | saturation, type character, density |
| Content type | marketing, app/dashboard, content/editorial, transactional | app/dashboard | layout, density, stack |
| Performance budget | tight, normal, rich | normal | stack, asset strategy |
| Accessibility target | AA, AAA | AA | contrast floors (ties to [FE-1]) |
| Platform | responsive web, mobile-first, desktop-dense | responsive web | layout, type scale |

## How consumers use this
- **design-advisor**: asks each dimension the user has not already stated; fills defaults for any left blank.
- **spec-enricher**: infers each dimension from spec text; where the text is silent, uses the default.
