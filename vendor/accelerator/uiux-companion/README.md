# uiux-companion

UI/UX design quality companion — usability heuristics, design-system consistency, and visual hierarchy evaluated from spec and flow descriptions. Works on textual descriptions of flows and screens; does not require front-end code.

Pairs with `frontend-companion`: uiux-companion reviews the design layer (what the experience must be); frontend-companion reviews the code that implements it.

## Installation

Install via the accelerator plugin loader:

```bash
claude plugin install uiux-companion
```

Or symlink into your project's plugin directory:

```bash
ln -s /path/to/accelerator/uiux-companion .claude/plugins/uiux-companion
```

## Usage

Evaluate a described flow against Nielsen's 10 usability heuristics and visual hierarchy principles:

```
/ux-review User opens checkout page. Items are shown in a list. User clicks "Place Order". A spinner appears for 3 seconds. Success message appears.
```

Audit a design description for token consistency:

```
/design-system-check Dashboard uses #3A7BD5 for primary button, 13px margin between cards, font-size 14px for headings
```

The spec-enricher is invoked automatically by `ai-baseline`'s enrich runner when a spec is submitted. It returns UX-1..3 requirements when the spec defines user-facing screens or flows.

## Commands

- `/ux-review <flow description or file>` — heuristic evaluation (H-1 through H-10) and visual hierarchy review for a flow or screen; accepts a free-text description or a file path within the project
- `/design-system-check <screens/tokens>` — design token consistency audit; flags ad-hoc spacing, color, and type values and proposes a conformant token set

## Dependencies

- requires: ai-baseline

---

<your-name> (you@example.com)
