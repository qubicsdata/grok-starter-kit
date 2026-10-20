# frontend-companion

Front-end engineering quality for browser UI codebases — component architecture review, accessibility auditing, bundle performance analysis, and JS/TS language depth.

## Installation

Install via the accelerator plugin loader:

```bash
claude plugin install frontend-companion
```

Or symlink into your project's plugin directory:

```bash
ln -s /path/to/accelerator/frontend-companion .claude/plugins/frontend-companion
```

## Usage

Run an architecture and performance review over your UI source:

```
/frontend-review src/components
```

Run a WCAG 2.1 AA accessibility audit:

```
/a11y-audit src/components/UserDashboard
```

The spec-enricher is invoked automatically by `ai-baseline`'s enrich runner when a spec is submitted. It returns FE-1..FE-4 requirements when the spec defines a browser UI.

## Commands

- `/frontend-review <path>` — component architecture, state management, and bundle performance review over a UI file or directory
- `/a11y-audit <path>` — WCAG 2.1 AA accessibility audit over a UI file or directory

## Dependencies

- requires: ai-baseline

---

<your-name> (you@example.com)
