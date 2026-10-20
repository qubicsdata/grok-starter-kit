# Behavioral Scenarios — uiux-companion v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 17 scenarios (HR-01–03, DS-01–03, VH-01–03, SE-01–03, CR-COLOR-01–02, CR-TYPE-01, CR-LAYOUT-01, CR-ADV-01)

---

## ux-heuristic-reviewer Scenarios (HR-01 – HR-03)

### HR-01 — Missing status visibility: H-1 flagged

**Input:** `/ux-review User clicks "Submit Order". The order is placed. The user is returned to the home page.`

**Expected behavior:**
- Applies usability-heuristics H-1 (Visibility of System Status)
- Flags: no loading/progress feedback between "Submit Order" and order placement; no confirmation message before returning to home
- Severity: HIGH — user has no confirmation the order succeeded
- HEURISTIC REVIEW report produced with H-1 finding

**Pass condition:** H-1 cited in FINDINGS at HIGH severity. Fix describes a loading indicator and a success confirmation before redirect.

---

### HR-02 — No error recovery path: H-9 flagged

**Input:** `/ux-review User fills out a 5-step registration form. On step 3, an error occurs. The user sees "Error 500". The user is returned to step 1 with the form cleared.`

**Expected behavior:**
- Flags H-9 (Help Users Recognize, Diagnose, and Recover from Errors): "Error 500" is not plain language; no indication of what went wrong on step 3
- Flags H-3 (User Control and Freedom): form cleared on error destroys user's work
- HEURISTIC REVIEW report produced

**Pass condition:** H-9 cited (error code, no fix suggestion). H-3 cited (form data lost). Both findings at HIGH severity.

---

### HR-03 — No findings: all heuristics satisfied

**Input:** `/ux-review User opens the password-reset page. A text field is labeled "Email address". After submitting a valid email, a banner says "Check your email — we sent a reset link." with a "Resend" button. If the email is not in the system, a banner says "If that email is registered, a link is on its way." The field is preserved after submission. A loading spinner appears while the request is in flight.`

**Expected behavior:**
- Applies H-1 through H-10
- H-1 satisfied (spinner described)
- H-9 satisfied (informative messages, recovery via Resend)
- H-6 satisfied (field preserved)
- HEURISTIC REVIEW produced; FINDINGS block is empty or minimal

**Pass condition:** SUMMARY shows 0 HIGH violations. Report structure correct (no crash on zero findings).

---

## design-system-agent Scenarios (DS-01 – DS-03)

### DS-01 — Ad-hoc color value flagged

**Input:** `/design-system-check Login screen: primary button background #3A7BD5, button text white, margin between inputs 13px, heading font-size 22px`

**Expected behavior:**
- Flags DS-CL-1 (raw hex #3A7BD5 used instead of a color token) at HIGH severity
- Flags DS-SP-1 (13px margin is not on an 8px-base spacing scale) at MEDIUM
- Flags DS-TP-1 (22px font-size not mapped to a named type style) at MEDIUM
- Proposes a token set with `color-action` mapped to the described intent, `sp-1` (8px) / `sp-2` (16px) as nearest compliant spacing, `h3` (20px) or `h2` (24px) as nearest type style
- DESIGN SYSTEM REVIEW report produced

**Pass condition:** DS-CL-1, DS-SP-1, DS-TP-1 all cited with correct violation IDs. Proposed token set present. SUMMARY shows 3 findings.

---

### DS-02 — Inconsistent semantic token use flagged

**Input:** `/design-system-check Dashboard: error messages use neutral-800 text on white background. Settings page: error messages use color-error text on surface-base.`

**Expected behavior:**
- Flags DS-CL-2: error text on Dashboard uses neutral-800 (literal) instead of color-error (semantic)
- Flags DS-CL-3: two screens use different tokens for the same semantic role (error text)
- Recommends CR-3: replace neutral-800 with color-error on Dashboard for semantic consistency

**Pass condition:** DS-CL-2 and DS-CL-3 both cited. Fix recommends color-error consistently. No finding against the Settings page (it is correct).

---

### DS-03 — No design surface: informative message returned

**Input:** `/design-system-check POST /api/v1/orders returns 201 Created with order JSON. Authentication via Bearer token.`

**Expected behavior:**
- No screens, tokens, or visual descriptions present
- Returns: `DESIGN SYSTEM REVIEW: No design surface found in input — no findings.`
- No FINDINGS block emitted

**Pass condition:** Informative no-findings message returned. No crash. No fabricated findings.

---

## visual-hierarchy-agent Scenarios (VH-01 – VH-03)

### VH-01 — No primary action: VH-1 flagged

**Input:** `/ux-review Settings page: contains a grid of 12 options — Change Password, Notification Preferences, Privacy Settings, Connected Apps, Billing, Download Data, Delete Account, Language, Theme, Two-Factor Auth, API Keys, Logout — all displayed as equal-weight buttons in a 3×4 grid.`

**Expected behavior:**
- Flags VH-1 (Primary Action Clarity): 12 options at equal visual weight; no dominant primary action; Delete Account and Logout at same prominence as non-destructive options
- Flags VH-5 (Information Density): 12 ungrouped items exceeds 7±2 threshold
- VH-6 flagged: empty/loading/error/success states not described
- VISUAL HIERARCHY REVIEW produced

**Pass condition:** VH-1 cited at HIGH (no primary action, destructive option undifferentiated). VH-5 cited at MEDIUM. VH-6 cited (missing states). Fix describes grouping into sections (Account, Preferences, Data, Danger Zone) and visual distinction for destructive actions.

---

### VH-02 — Missing all four states: VH-6 flagged

**Input:** `/ux-review User Dashboard: shows a table of recent orders. Each row has order ID, date, total, and status badge.`

**Expected behavior:**
- Flags VH-6 at HIGH for all four missing states:
  - Empty: no description of what shows when no orders exist
  - Loading: no spinner/skeleton described for initial data fetch
  - Error: no description of what shows when orders fail to load
  - Success: implicitly the table, but no confirmation state described
- VISUAL HIERARCHY REVIEW produced

**Pass condition:** VH-6 cited. Missing states list shows: empty, loading, error, success. Severity HIGH for empty and error. Fix describes skeleton loading, empty-state CTA, and error-state retry.

---

### VH-03 — Well-structured screen: minimal findings

**Input:** `/ux-review Checkout summary page (form type): Header "Review your order" (h1). Order items list (body). Subtotal and total in bold (h3). Primary button "Place Order" (brand-primary, lg). Secondary link "Edit cart" (ghost, sm). Loading state: skeleton overlaid on items list. Empty state: not applicable (user must have items to reach this page). Error state: inline banner "Payment failed — check your card details" with Retry button. Success state: full-page confirmation with order number and estimated delivery.`

**Expected behavior:**
- VH-1 satisfied: "Place Order" is clearly primary
- VH-2 satisfied: header → items → total → action follows reading order
- VH-6 satisfied: loading, error, success all described (empty not applicable, which is acceptable with justification)
- VISUAL HIERARCHY REVIEW produced; FINDINGS minimal or empty

**Pass condition:** SUMMARY shows 0 HIGH violations. VH-1, VH-2, VH-6 noted as satisfied. Report does not crash on minimal findings.

---

## spec-enricher Scenarios (SE-01 – SE-03)

### SE-01 — Spec with screens: UX-1..3 returned

**Input (spec text):**
```
# E-Commerce Checkout
Build a checkout flow with three steps: cart review, shipping address, payment.
Each step has a progress indicator. The user sees their cart items on step 1,
fills in a shipping form on step 2, and enters card details on step 3.
On success, a confirmation page shows the order number.
```

**Expected behavior:**
- Detects trigger: "checkout flow", "steps", "cart review", "shipping form", "confirmation page" — user-facing screens with described flows
- Returns:
  ```
  PLUGIN: uiux-companion
  APPLIES_BECAUSE: spec defines a multi-step checkout flow with three user-facing screens (cart review, shipping address, payment) and a confirmation page
  REQUIREMENTS:
  - [UX-1] User flows described in this spec MUST be evaluated against Nielsen's 10 usability heuristics before build begins; findings MUST be resolved or explicitly accepted as known tradeoffs.
  - [UX-2] Visual styling for all screens MUST derive exclusively from a defined design-token set covering spacing scale, type scale, and color tokens; ad-hoc numeric or color values MUST NOT appear in implementation.
  - [UX-3] Every screen defined in this spec MUST explicitly describe empty, loading, error, and success states before implementation begins.
  ```

**Pass condition:** All three UX requirements returned. APPLIES_BECAUSE names the concrete trigger. No guidance language in requirements.

---

### SE-02 — Headless API spec: NOT_APPLICABLE returned

**Input (spec text):**
```
# Order Processing API
Build a REST API that accepts order creation requests, validates inventory,
charges the payment provider, and emits an order-created event to Kafka.
No user interface. Internal service-to-service only. Auth via mTLS.
```

**Expected behavior:**
- No user-facing screens, flows, or UI components detected
- Returns:
  ```
  NOT_APPLICABLE
  REASON: spec defines a headless REST API and event pipeline with no user-facing screens or described UI flows
  ```

**Pass condition:** `NOT_APPLICABLE` returned. REASON is specific. No UX requirements emitted. No filesystem tools used.

---

### SE-03 — Enricher emits RECOMMENDATIONS separate from REQUIREMENTS
**Input (spec text):** a marketing landing page for a premium consumer brand.
**Expected behavior:** Returns REQUIREMENTS (UX-1..3) AND a RECOMMENDATIONS block with [REC-COLOR]/[REC-TYPE]/[REC-LAYOUT], each citing a derivation rule or tier-1 default and inferring the brief (personality=premium, content=marketing). No recommendation uses MUST.
**Pass condition:** Both blocks present and clearly separated; REQUIREMENTS unchanged; recommendations cite craft rule IDs and contain no MUST.

---

## color-craft Scenarios (CR-COLOR-01 – CR-COLOR-02)

### CR-COLOR-01 — Default brief yields tier-1 palette
**Input:** brief with all dimensions at default (consumer / trustworthy / app-dashboard / normal / AA / responsive).
**Expected behavior:** Recommends COLOR-1 single brand hue + analogous accent, 11-step slightly-warm neutral ramp, 60-30-10 distribution. Each recommendation cites no derivation rule (defaults apply) and states the override hook.
**Pass condition:** Tier-1 defaults from Section 3 returned for COLOR-1..5; output follows the Section 5 contract.

### CR-COLOR-02 — Finance audience flips hue family
**Input:** brief with audience = finance, personality = trustworthy.
**Expected behavior:** COLOR-1 recommendation shifts to a blue/teal hue family, citing COLOR-D-1; ≥1 alternative offered; contrast floors per AA noted via the a11y-checklist A11Y-1.4.3 handoff.
**Pass condition:** Recommendation cites COLOR-D-1 and selects a blue/teal family, differing from the CR-COLOR-01 default.

---

## type-craft Scenarios (CR-TYPE-01)

### CR-TYPE-01 — Editorial content flips to serif pairing
**Input:** brief with content type = content/editorial.
**Expected behavior:** TYPE-2 recommends a serif body + sans heading, citing TYPE-D-1; ≥1 alternative; override hook stated.
**Pass condition:** Recommendation cites TYPE-D-1 and selects a serif body, differing from the sans default.

---

## layout-craft Scenarios (CR-LAYOUT-01)

### CR-LAYOUT-01 — Marketing content selects single-focus Z-pattern
**Input:** brief with content type = marketing.
**Expected behavior:** LAYOUT-1/LAYOUT-4 recommend a Z-pattern single-focus hero with one dominant CTA, citing LAYOUT-D-1; ≥1 alternative; override hook.
**Pass condition:** Recommendation cites LAYOUT-D-1 and selects a Z-pattern single-CTA layout.

---

## design-advisor Scenarios (CR-ADV-01)

### CR-ADV-01 — Advisor records an override with rationale
**Input:** `/design-advise finance dashboard` then the user overrides the recommended blue hue with green "for brand match".
**Expected behavior:** Advisor recommends blue/teal citing COLOR-D-1; on override, records the green choice with the user's rationale in design-decisions.md; does not re-assert blue.
**Pass condition:** design-decisions.md shows COLOR-1 = green with recorded override rationale; original COLOR-D-1 recommendation noted as overridden.
