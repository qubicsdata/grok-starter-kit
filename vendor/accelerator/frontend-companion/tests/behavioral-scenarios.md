# Behavioral Scenarios — frontend-companion v1.0.0

Generated from agent contracts, hard gates, and anti-pattern probes defined in the spec and agent files.

Total: 17 scenarios (FR-01–05, AA-01–04, BP-01–03, SE-01–03, CR-STACK-01–02)

---

## frontend-reviewer Scenarios (FR-01 – FR-05)

### FR-01 — Happy path: duplicated state source of truth flagged

**Input:** `/frontend-review src/components`. File contains:
```tsx
const [user, setUser] = useState(null);
const [userName, setUserName] = useState('');
// userName is always user.name — duplicated derived state
```

**Expected behavior:**
- Discovers .tsx files under src/components
- Applies component-architecture-spec STATE-1 and jsts-pack AP-JS-3
- Flags: `[MEDIUM] STATE-1 Derived state duplicated — userName mirrors user.name`
- Produces FRONTEND REVIEW report with finding

**Pass condition:** Finding present citing STATE-1. FRONTEND REVIEW report structure matches spec.

---

### FR-02 — Prop drilling beyond two levels flagged

**Input:** `/frontend-review src`. File chain: App → Layout → Sidebar → UserAvatar, where `userId` prop passed through Layout and Sidebar without use.

**Expected behavior:** Flags prop drilling at Layout and Sidebar using PD-1. Suggests context or composition.

**Pass condition:** Finding cites PD-1. Affected files identified. Suggestion present.

---

### FR-03 — XSS via dangerouslySetInnerHTML flagged

**Input:** `/frontend-review src/pages`. File contains:
```tsx
<div dangerouslySetInnerHTML={{ __html: userInput }} />
```

**Expected behavior:** Flags SEC-JS-1 at CRITICAL severity. Detail explains XSS risk. Fix cites DOMPurify sanitization.

**Pass condition:** SEC-JS-1 finding at CRITICAL. Fix mentions DOMPurify.

---

### FR-04 — No JS/TS files at path: no-UI-surface message

**Input:** `/frontend-review src/server` where only `.py` and `.go` files exist.

**Expected behavior:** Returns `No UI surface found at src/server — no findings.` without attempting a review.

**Pass condition:** Informative message returned. No crash. No findings report.

---

### FR-05 — Path outside project root: error and abort

**Input:** `/frontend-review /etc/passwd`

**Expected behavior:** Agent runs path-safety check. `/etc/passwd` resolves outside project root. Returns `ERROR: path resolves outside project root — review aborted.`

**Pass condition:** Error message returned. No file content read. No findings report.

---

## a11y-auditor Scenarios (AA-01 – AA-04)

### AA-01 — Missing label on form input flagged

**Input:** `/a11y-audit src/components/LoginForm.tsx`. File contains:
```tsx
<input type="email" placeholder="Email address" />
```
No `<label>`, no `aria-label`, no `aria-labelledby`.

**Expected behavior:** Flags A11Y-3.3.2 (labels or instructions) and A11Y-1.3.1 (info and relationships). Severity HIGH. Fix: add `<label htmlFor="email">Email address</label>` or `aria-label`.

**Pass condition:** A11Y-3.3.2 and A11Y-1.3.1 both cited. A11Y AUDIT report structure correct.

---

### AA-02 — Missing focus visible (outline:none) flagged

**Input:** `/a11y-audit src/styles`. CSS file contains:
```css
button:focus { outline: none; }
```
No replacement focus style.

**Expected behavior:** Flags A11Y-2.4.7 (focus visible) at HIGH severity. Fix: add custom focus ring before removing default outline.

**Pass condition:** A11Y-2.4.7 cited. Severity HIGH. Fix present.

---

### AA-03 — Modal without focus trap: FM-1 flagged

**Input:** `/a11y-audit src/components/Modal.tsx`. Modal opens but contains no focus-trap logic; Tab key can exit the modal.

**Expected behavior:** Flags FM-1. Detail explains focus must be trapped within modal while open and restored to trigger on close.

**Pass condition:** FM-1 cited. Fix describes focus-trap requirement.

---

### AA-04 — Framework unrecognized: framework-agnostic checks applied

**Input:** `/a11y-audit src/views` where files use a proprietary template syntax (not React/Vue/Svelte/HTML).

**Expected behavior:** Applies all applicable framework-agnostic checks from a11y-checklist. Notes "Framework: Unknown — framework-agnostic checks applied" in report header.

**Pass condition:** Report produced. Framework line reads "Unknown". A11y criteria still checked where possible.

---

## bundle-perf-agent Scenarios (BP-01 – BP-03)

### BP-01 — Un-split large bundle flagged

**Input:** `/frontend-review src`. Routes statically imported in entry:
```tsx
import Dashboard from './pages/Dashboard';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
```
No dynamic `import()`. No chunk size budget in vite.config.ts.

**Expected behavior:** Flags PERF-1 (route-level code splitting missing) and PERF-3 (no bundle budget configured). Suggests dynamic `import()` per route.

**Pass condition:** PERF-1 and PERF-3 both cited. Suggestion includes `React.lazy(() => import('./pages/Dashboard'))` example.

---

### BP-02 — Lodash full import flagged

**Input:** `import _ from 'lodash'` in a component.

**Expected behavior:** Flags PERF-2 (large dependency loaded eagerly without tree shaking). Suggests `import debounce from 'lodash/debounce'` or `lodash-es` named imports.

**Pass condition:** PERF-2 cited. Fix mentions named/path imports.

---

### BP-03 — Images without lazy loading flagged

**Input:** `/frontend-review src/components`. Component contains:
```tsx
<img src="/images/hero.png" alt="Hero banner" />
```
No `loading="lazy"`.

**Expected behavior:** Flags PERF-4 (images not lazy-loaded) and PERF-9 (non-optimized image format — PNG without WebP variant). Suggests `loading="lazy"` and `<picture>` with WebP.

**Pass condition:** PERF-4 and PERF-9 both cited. Fix mentions both `loading="lazy"` and `<picture>` element.

---

## spec-enricher Scenarios (SE-01 – SE-03)

### SE-01 — React app spec: FE-1 through FE-4 returned

**Input (spec text):**
```
# User Dashboard
Build a React SPA that shows user analytics. Users log in via OAuth.
The dashboard renders charts and data tables. Client-side routing via React Router.
```

**Expected behavior:**
- Detects trigger: "React SPA", "client-side routing"
- Returns:
  ```
  PLUGIN: frontend-companion
  APPLIES_BECAUSE: spec defines a React SPA with user-facing interactive screens and client-side routing
  REQUIREMENTS:
  - [FE-1] Interactive UI MUST meet WCAG 2.1 AA ...
  - [FE-2] Client state MUST have a single source of truth ...
  - [FE-3] JS bundles MUST be code-split at route boundaries ...
  - [FE-4] Every user-facing async surface ... MUST handle loading, error, and empty states.
  ```

**Pass condition:** All four FE requirements returned. APPLIES_BECAUSE names the concrete trigger. No guidance language.

---

### SE-02 — Backend-only spec: NOT_APPLICABLE returned

**Input (spec text):**
```
# Data Ingestion Pipeline
Build a Python service that reads from Kafka, processes events, and writes to PostgreSQL.
No user interface. REST API endpoints for internal service-to-service calls only.
```

**Expected behavior:**
- No browser UI, no client app, no user-facing screens detected
- Returns:
  ```
  NOT_APPLICABLE
  REASON: spec defines a backend data pipeline and internal REST API with no browser UI or client-side code
  ```

**Pass condition:** `NOT_APPLICABLE` returned. REASON is specific. No FE requirements emitted.

---

### SE-FE-03 — Frontend enricher emits a stack RECOMMENDATION
**Input (spec text):** an SEO-critical content site with a tight performance budget.
**Expected behavior:** Returns REQUIREMENTS (FE-1..4) AND a RECOMMENDATIONS block with [REC-STACK] recommending Astro, citing STACK-D-1. No MUST in the recommendation.
**Pass condition:** RECOMMENDATIONS present and separate; [REC-STACK] cites STACK-D-1; no MUST.

---

## frontend-stack-craft Scenarios (CR-STACK-01 – CR-STACK-02)

### CR-STACK-01 — App/dashboard default selects React + RSC

**Input:** brief with content type = app/dashboard, performance budget = normal.

**Expected behavior:** STACK-1 recommends React + RSC citing STACK-D-2; STACK-2 recommends Tailwind/CSS Modules citing defaults apply; ≥1 alternative each (e.g. SvelteKit as STACK-1 alternative); override hook present.

**Pass condition:** Recommendation cites STACK-D-2 and selects React + RSC.

---

### CR-STACK-02 — SEO content + tight budget flips to Astro

**Input:** brief with content type = content/editorial, performance budget = tight, SEO matters.

**Expected behavior:** STACK-1 recommends Astro citing STACK-D-1; STACK-2 avoids runtime CSS-in-JS citing STACK-D-3; ≥1 alternative each; override hook present.

**Pass condition:** Recommendation cites STACK-D-1 and selects Astro, differing from the React + RSC default.

---
