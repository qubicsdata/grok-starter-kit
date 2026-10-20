---
name: a11y-checklist
description: WCAG 2.1 AA accessibility checklist for frontend-companion. Imported by a11y-auditor. All findings cite the criterion ID.
---

# Accessibility Checklist — WCAG 2.1 AA

Import this skill when auditing UI code for accessibility. All findings must cite the criterion ID below.

---

## Perceivable

- A11Y-1.1.1 Non-text content: every `<img>` has a non-empty `alt` attribute. Decorative images use `alt=""`. Icon buttons have `aria-label` or a visually-hidden text label.
  Flag when: `<img>` lacks `alt`; icon-only `<button>` lacks `aria-label`; `role="img"` element lacks `aria-label`.

- A11Y-1.3.1 Info and relationships: semantic HTML used for structure (headings, lists, tables). Data tables have `<caption>` and `scope` on `<th>`. Form inputs have explicit `<label for="...">` associations (not just placeholder text).
  Flag when: `<div>` or `<span>` used for heading/list/table structure; form input lacks `<label>` and `aria-label` and `aria-labelledby`.

- A11Y-1.3.2 Meaningful sequence: reading order of DOM matches visual order. CSS `order` and `position: absolute` do not create a sequence that differs from the DOM order.
  Flag when: `order` or absolute positioning creates a visual order that would confuse a screen reader following DOM order.

- A11Y-1.3.3 Sensory characteristics: instructions do not rely solely on shape, color, size, or position ("click the red button", "see the icon on the right"). Text labels accompany sensory cues.
  Flag when: error messages or instructions reference color or position without accompanying text.

- A11Y-1.4.1 Use of color: color is not the only visual means of conveying information (e.g., error states use an icon or text label in addition to red color).
  Flag when: an error state is communicated only by changing an element's color with no icon, pattern, or text change.

- A11Y-1.4.3 Contrast (minimum): text meets 4.5:1 contrast ratio against its background (3:1 for large text ≥ 18pt or ≥ 14pt bold). UI component boundaries meet 3:1 contrast.
  Flag when: foreground/background color pair has a ratio below threshold; check with a contrast tool (Colour Contrast Analyser or browser DevTools).

- A11Y-1.4.4 Resize text: text can be resized up to 200% via browser zoom without loss of content or functionality.
  Flag when: fixed `px` font sizes prevent scaling; viewport-unit font sizes clip overflow.

- A11Y-1.4.10 Reflow: content reflows at 320px viewport width without horizontal scrolling (except for content requiring two-dimensional layout).
  Flag when: component breaks layout or requires horizontal scroll at 320px width.

- A11Y-1.4.11 Non-text contrast: UI components (inputs, buttons, focus indicators, icons) have a 3:1 contrast ratio against adjacent colors.
  Flag when: input border, button outline, or focus ring has < 3:1 contrast against background.

---

## Operable

- A11Y-2.1.1 Keyboard: all interactive elements reachable and operable with keyboard alone (Tab, Shift+Tab, Enter, Space, arrow keys for composites). No keyboard traps.
  Flag when: a custom widget (dropdown, modal, slider) cannot be operated without a mouse.

- A11Y-2.1.2 No keyboard trap: focus can always be moved away from any component using standard keys.
  Flag when: modal or drawer opens and Tab does not stay within it (trap missing) OR focus cannot exit when needed.

- A11Y-2.4.1 Bypass blocks: a skip navigation link is the first focusable element on pages with repeated navigation. The link becomes visible on focus.
  Flag when: page has repeated nav block and no skip link.

- A11Y-2.4.2 Page titled: `<title>` element is present, descriptive, and unique per route (for SPAs, updated on navigation).
  Flag when: `<title>` is missing, empty, or unchanged across route changes.

- A11Y-2.4.3 Focus order: focus traversal order is logical and consistent with visual layout.
  Flag when: `tabindex` values > 0 are used (they hijack natural order); focus jumps unexpectedly.

- A11Y-2.4.4 Link purpose: link text (or `aria-label`) describes the link destination. "Click here" and "Read more" are not sufficient without additional context.
  Flag when: link text is "click here", "read more", "here", or similar without `aria-label` or `aria-describedby`.

- A11Y-2.4.6 Headings and labels: headings describe the topic of the section; form labels describe the purpose of the input.
  Flag when: section lacks heading; heading text is generic ("Section 1", "Content").

- A11Y-2.4.7 Focus visible: keyboard focus indicator is visible on all interactive elements. The default browser outline must not be removed (`outline: none`) without a replacement.
  Flag when: `outline: none` or `outline: 0` appears without a custom focus style.

---

## Understandable

- A11Y-3.1.1 Language of page: `<html lang="en">` (or appropriate language code) is set. SPAs do not clear this attribute.
  Flag when: `<html>` lacks `lang` attribute.

- A11Y-3.2.1 On focus: focusing an element does not automatically trigger a context change (navigation, form submit, popup) unless the user has been warned.
  Flag when: `onFocus` handler triggers navigation or form submission.

- A11Y-3.3.1 Error identification: form errors are identified in text and describe which field has an error and what the error is.
  Flag when: error state shown only via red border with no error message text; error message does not identify the field.

- A11Y-3.3.2 Labels or instructions: all form inputs have visible labels or clear instructions. Placeholder text alone is not a label.
  Flag when: `<input>` has no `<label>` and no `aria-label`; placeholder used as the only label.

---

## Robust

- A11Y-4.1.1 Parsing: HTML is valid. No duplicate IDs. No unclosed tags. (Validate with Nu Html Checker or eslint-plugin-jsx-a11y.)
  Flag when: `id` attribute value appears more than once in the DOM; `<img>` or `<input>` tags unclosed in JSX.

- A11Y-4.1.2 Name, Role, Value: all UI components have an accessible name (`aria-label`, `aria-labelledby`, or label association), correct role (semantic element or explicit `role` attribute), and state communicated via ARIA attributes (`aria-expanded`, `aria-checked`, `aria-disabled`).
  Flag when: custom widget uses `<div role="button">` without `aria-pressed`/`aria-expanded`; toggle button lacks `aria-pressed`.

- A11Y-4.1.3 Status messages: status messages (success toast, error banner, loading indicator) are announced to screen readers via `role="status"` or `role="alert"` or `aria-live`.
  Flag when: success or error feedback appears visually but has no `role="alert"`, `role="status"`, or `aria-live` region.

---

## Focus Management

- FM-1 Modal focus trap: when a modal/dialog opens, focus moves into the dialog and is trapped within it until the dialog closes. When the dialog closes, focus returns to the trigger element.
  Flag when: modal opens and focus remains on the triggering button; Tab exits the modal.

- FM-2 Route change focus: in SPAs, route change moves focus to the main content area or the new page's heading so screen reader users know the page changed.
  Flag when: SPA navigation does not update focus; screen reader users hear no announcement of the new page.

- FM-3 Toast/notification: transient notifications use `role="status"` (polite) for confirmations and `role="alert"` (assertive) for errors. Do not use `role="alert"` for non-critical messages.
  Flag when: success toast uses `role="alert"` (too assertive); error message uses `role="status"` (too polite to announce immediately).
