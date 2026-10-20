---
name: design-system-spec
description: Design token categories (spacing scale, type scale, color tokens, component variants) and consistency rules. Import when auditing or defining a design system from a screen or token description.
---

# Design System Spec

A design system is a set of reusable decisions expressed as tokens and component variants. This skill defines the token categories and consistency rules to apply when auditing or defining design systems from textual descriptions.

## Token Categories

### Spacing Scale (SP-*)
A spacing scale is a set of discrete step values used for all margins, paddings, gaps, and layout measurements. All spatial values on every screen and component MUST derive from this scale.

**Required properties:**
- Base unit (commonly 4px or 8px)
- Named steps: `sp-0` (0), `sp-1` (base), `sp-2` (base×2), `sp-3` (base×3), `sp-4` (base×4), `sp-6` (base×6), `sp-8` (base×8), `sp-12` (base×12), `sp-16` (base×16)
- All component and layout descriptions reference tokens, not raw pixel/rem values

**Violation: DS-SP-1** — Ad-hoc spacing value (a numeric value not on the scale) used in a screen or component description.
**Violation: DS-SP-2** — Spacing scale has no base unit defined.

### Type Scale (TP-*)
A type scale defines named text styles covering size, weight, and line height. All text on every screen MUST use a named text style.

**Required styles:**
- `display`: largest heading (hero, marketing)
- `h1` through `h4`: page, section, sub-section, card headings
- `body-lg`, `body`, `body-sm`: paragraph text at three sizes
- `label`: form labels, metadata
- `caption`: supplemental, legal, timestamps
- `code`: monospaced text

**Each named style specifies:** font-size, line-height, font-weight, letter-spacing (optional).

**Violation: DS-TP-1** — A described text element uses a raw font size not mapped to a named style.
**Violation: DS-TP-2** — Two screens describe a heading at different sizes without naming distinct styles.

### Color Tokens (CL-*)
Color tokens are semantic names for all colors used in the UI. Raw hex, rgb, or hsl values MUST NOT appear in screen descriptions — only token names.

**Required token groups:**
- **Brand:** `brand-primary`, `brand-secondary`, `brand-accent`
- **Neutral:** `neutral-0` (white) through `neutral-900` (near-black) in steps (100, 200, 300, 400, 500, 600, 700, 800, 900)
- **Semantic:** `color-success`, `color-warning`, `color-error`, `color-info`
- **Interactive:** `color-action` (default), `color-action-hover`, `color-action-active`, `color-action-disabled`
- **Surface:** `surface-base`, `surface-raised`, `surface-overlay`, `surface-sunken`
- **Text:** `text-primary`, `text-secondary`, `text-disabled`, `text-inverse`, `text-on-action`
- **Border:** `border-default`, `border-subtle`, `border-strong`, `border-action`

**Violation: DS-CL-1** — A described screen references a raw color value (e.g., "#3A7BD5", "rgb(58,123,213)") instead of a token.
**Violation: DS-CL-2** — A semantic role (error, success, warning) uses a brand or neutral token rather than the appropriate semantic token.
**Violation: DS-CL-3** — Two screens describe the same visual intent with different color tokens (inconsistent semantic mapping).

### Component Variants (CV-*)
Each reusable component MUST have a defined set of named variants covering its states and visual treatments.

**Required variant dimensions for interactive components:**
- **Size:** `sm`, `md`, `lg` (at minimum)
- **Variant:** `primary`, `secondary`, `ghost`, `destructive` (for action components)
- **State:** `default`, `hover`, `active`, `focus`, `disabled`, `loading` (for interactive components)
- **Density:** `compact`, `default`, `comfortable` (for data-heavy components: tables, lists, forms)

**Violation: DS-CV-1** — A described component uses a visual treatment not defined in its variant set (e.g., a button styled as "outline" when only primary/secondary/ghost are defined).
**Violation: DS-CV-2** — A component's interactive states (hover, focus, disabled) are not described, leaving them undefined.
**Violation: DS-CV-3** — Two instances of the same component use inconsistent variant names for the same visual intent.

## Consistency Rules

### CR-1: Single Token Source
Every spatial, typographic, and color value in every screen description MUST trace to exactly one token. No screen MAY define its own local spacing, color, or type values outside the token set.

### CR-2: No Ad-Hoc Values
"Ad-hoc" means any numeric or color value that is not a named token or a mathematical function of named tokens. Ad-hoc values are design debt and MUST be flagged.

### CR-3: Semantic Over Literal
When a token choice exists, prefer the semantic token (e.g., `color-error` over `neutral-800` for error text). Semantic tokens survive theme changes; literal tokens do not.

### CR-4: Cross-Screen Consistency
Equivalent UI elements across different screens MUST use the same tokens. A card on the Dashboard and a card on the Settings page MUST use the same surface, spacing, and type tokens.

### CR-5: State Completeness
Every interactive component MUST have explicitly defined tokens for: default, hover, focus, active, disabled. An undefined state is a design gap.

## How to Apply This Skill

1. **Identify all values** in the screen/token description: every spacing number, every font size, every color.
2. **Check each value** against the token set. If it matches a token name, it is compliant. If it is a raw value, flag it.
3. **Check semantic correctness**: is the token used appropriate for its purpose (CR-3)?
4. **Check cross-screen consistency** (CR-4) if multiple screens are described.
5. **Check state completeness** (CR-5) for every interactive component described.
6. **Propose a token set** if none is defined — use the Required properties above as the template.
