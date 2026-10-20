---
name: jsts-pack
description: JS/TS language best-practice pack for frontend-companion. Covers idioms, anti-patterns, security pitfalls (XSS, unsafe innerHTML, prototype pollution), testing with Jest/Vitest/Testing Library, and build norms. Import when reviewing JS/TS code or enriching UI specs.
---

# JS/TS Best-Practice Pack

Follows `best-practice-pack-schema.md`. All six sections are required; all findings cite the rule ID below.

---

## Section 1 — Idioms & Preferred Constructs

- IDIOM-JS-1 Prefer `const` over `let`; never use `var`: `const` prevents reassignment and `var` has function scope that surprises across blocks and closures.
  Prefer: `const items = getItems();`
  Avoid: `var items = getItems();`

- IDIOM-JS-2 Destructuring for multi-value extraction: Destructuring is idiomatic, reduces temporary variable clutter, and works for both arrays and objects.
  Prefer: `const { id, name } = user;` / `const [first, ...rest] = items;`
  Avoid: `const id = user.id; const name = user.name;`

- IDIOM-JS-3 Optional chaining (`?.`) and nullish coalescing (`??`): Eliminates verbose null guards and avoids falsy-coercion bugs from `||`.
  Prefer: `const label = user?.profile?.displayName ?? 'Anonymous';`
  Avoid: `const label = (user && user.profile && user.profile.displayName) || 'Anonymous';`

- IDIOM-JS-4 `async/await` over raw Promise chains: `async/await` yields linear, debuggable flow; `.then().catch()` chains obscure control flow.
  Prefer: `const data = await fetchUser(id); return data.name;`
  Avoid: `return fetchUser(id).then(data => data.name).catch(err => null);`

- IDIOM-JS-5 Template literals for string interpolation: Cleaner than concatenation and supports multi-line strings.
  Prefer: `` const msg = `Hello, ${name}!`; ``
  Avoid: `const msg = 'Hello, ' + name + '!';`

- IDIOM-JS-6 Explicit TypeScript return types on public functions: Prevents accidental `any` inference and makes contracts explicit.
  Prefer: `function getUser(id: string): Promise<User> { ... }`
  Avoid: `function getUser(id) { ... }`

- IDIOM-JS-7 Array methods (`map`, `filter`, `reduce`) over imperative loops for transformations: Functional transforms are more readable and less error-prone for data pipelines.
  Prefer: `const names = users.filter(u => u.active).map(u => u.name);`
  Avoid: `const names = []; for (let i = 0; i < users.length; i++) { if (users[i].active) names.push(users[i].name); }`

---

## Section 2 — Anti-Patterns to Flag

- AP-JS-1 `any` type in TypeScript: Disables type checking and negates the value of TypeScript entirely.
  Why harmful: Propagates silently; runtime errors that TS should have caught appear in production.
  Reviewer action: FLAG and cite AP-JS-1. Require a specific type, union, or at minimum `unknown`.

- AP-JS-2 Implicit `== null` checks (loose equality): `== null` is ambiguous and inconsistent across teams; `=== null` and `=== undefined` are explicit.
  Why harmful: Confuses intent; `==` can match unexpected types.
  Reviewer action: FLAG and cite AP-JS-2. Require `=== null`, `=== undefined`, or `?? / ?.`.

- AP-JS-3 Duplicated client state (two sources of truth for same data): Keeping the same data in multiple state atoms/stores causes divergence bugs.
  Why harmful: State falls out of sync; UI shows stale data; debugging becomes non-deterministic.
  Reviewer action: FLAG and cite AP-JS-3. Require deriving secondary state from a single source.

- AP-JS-4 Prop drilling beyond two levels: Passing props through intermediate components that don't use them creates tight coupling.
  Why harmful: Refactoring a leaf component requires updating every ancestor; violates encapsulation.
  Reviewer action: FLAG and cite AP-JS-4. Require context, a state manager, or component composition.

- AP-JS-5 Inline object/array literals as React props without memoization: Creates a new reference every render, invalidating `React.memo` and `useMemo` dependencies.
  Why harmful: Causes cascading unnecessary re-renders.
  Reviewer action: FLAG and cite AP-JS-5. Require `useMemo`, `useCallback`, or moving the value outside the component.

- AP-JS-6 Missing error and loading states on async data: Rendering `data.map(...)` without handling loading/error states throws on undefined.
  Why harmful: Crashes on slow/failed network; blank screens in production.
  Reviewer action: FLAG and cite AP-JS-6. Require all three states: loading, error, and empty/data.

- AP-JS-7 `console.log` left in production code: Debug logs expose internal state and can leak PII.
  Why harmful: Information disclosure; noisy production logs.
  Reviewer action: FLAG and cite AP-JS-7. Remove or replace with a structured logger.

---

## Section 3 — Security Pitfalls

- SEC-JS-1 Unsafe `innerHTML` / `dangerouslySetInnerHTML` with user input: Injects attacker HTML into the DOM, enabling stored or reflected XSS.
  Mitigation: Never pass user-controlled strings to `innerHTML` or `dangerouslySetInnerHTML`. Use `textContent` for plain text. If HTML rendering is required, sanitize with DOMPurify first: `el.innerHTML = DOMPurify.sanitize(userHtml)`.
  Severity: CRITICAL

- SEC-JS-2 `eval()` / `new Function(userString)` on user-controlled input: Executes arbitrary JavaScript, enabling remote code execution in the browser.
  Mitigation: Remove `eval` and `new Function` on user-controlled data. Parse structured data with `JSON.parse`; use a template engine for dynamic content.
  Severity: CRITICAL

- SEC-JS-3 Prototype pollution via `Object.assign({}, userInput)` or lodash `merge`: An attacker-controlled object with `__proto__` key can mutate `Object.prototype`, affecting all objects in the runtime.
  Mitigation: Validate and allowlist keys before merging. Use `Object.create(null)` for hash maps. Prefer `structuredClone` for deep copies. Pin lodash >= 4.17.21.
  Severity: HIGH

- SEC-JS-4 Hardcoded secrets in client-side code: API keys, tokens, or secrets in JS bundles are readable by anyone who loads the page.
  Mitigation: Never embed secrets in client code. Use server-side proxies for authenticated API calls. Environment variables prefixed with `NEXT_PUBLIC_` / `VITE_` are public — do not use them for secrets.
  Severity: CRITICAL

- SEC-JS-5 Open redirect via `window.location = userInput`: Allows attackers to redirect users to malicious sites via phishing links.
  Mitigation: Allowlist redirect destinations. Never use a raw user-supplied URL as a redirect target. Validate that the URL's origin matches the application's origin.
  Severity: HIGH

- SEC-JS-6 Clickjacking (missing `X-Frame-Options` / `Content-Security-Policy: frame-ancestors`): Allows the UI to be embedded in a malicious iframe.
  Mitigation: Set `X-Frame-Options: DENY` or `Content-Security-Policy: frame-ancestors 'self'` at the HTTP server level.
  Severity: HIGH

- SEC-JS-7 `postMessage` without origin check: Accepting messages from any origin enables cross-origin data injection.
  Mitigation: Always validate `event.origin` against an allowlist in `window.addEventListener('message', ...)` handlers.
  Severity: HIGH

---

## Section 4 — Testing Framework & Convention

Frameworks: Jest (>=29) or Vitest (>=1.0) — both are acceptable; choose one per project.
Component testing: React Testing Library (>=14), Vue Testing Library, or Svelte Testing Library as appropriate for the framework.

Convention:
- Test files named `<component>.test.ts` or `<component>.spec.ts` co-located with the source file, or under a top-level `__tests__/` directory.
- Describe blocks group related behavior: `describe('UserCard', () => { it('renders name', ...) })`.
- Test names describe observable behavior, not implementation: prefer `it('shows error when fetch fails')` over `it('calls setError')`.
- Use `@testing-library/user-event` for simulating user interactions (not `fireEvent` — `userEvent` more closely mirrors real browser behavior).
- Prefer `screen.getByRole` and `screen.getByLabelText` over `getByTestId` — role/label selectors remain valid after refactoring.
- Mocking: use `vi.mock` (Vitest) or `jest.mock` (Jest) at the module level. Mock only external dependencies and I/O, not internal implementation.
- Snapshot tests: use sparingly for leaf components with no logic; never snapshot entire page trees.
- Coverage tool: `c8` (Vitest) or `jest --coverage`. Minimum 80% branch coverage for business-logic modules.

---

## Section 5 — Build / Dependency Norms

Build tools: Vite (>=5.0) preferred for new projects; Webpack (>=5) acceptable for existing projects; Next.js and SvelteKit include their own bundlers.
Package manager: npm (>=10), pnpm (>=9), or yarn (>=4); lock file (`package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`) MUST be committed.

Norms:
- All production dependencies pinned to exact versions (`"react": "18.3.1"`, not `"^18.0.0"`) for deployable apps. Libraries may use ranges.
- `devDependencies` separated from `dependencies` — bundlers, linters, test tools must not appear in `dependencies`.
- Tree-shaking enabled: use named exports (`export function foo`) over barrel files re-exporting everything (`export * from './foo'`) unless necessary.
- Code splitting: route-level code splitting is mandatory. Dynamic `import()` for components/modules only needed on specific interactions.
- Bundle size budget: no single JS chunk > 250 kB (gzipped) without explicit justification documented in the PR.
- Assets: images served via `<picture>` with WebP/AVIF + fallback; fonts use `font-display: swap`.

---

## Section 6 — Lint / Format Tool of Record

Linter: ESLint (>=9) with `@typescript-eslint` for TS files. `eslint.config.mjs` (flat config) preferred over `.eslintrc`.
Formatter: Prettier (>=3.0) via `prettier.config.mjs`. ESLint and Prettier must not conflict — use `eslint-config-prettier` to disable formatting rules in ESLint.
Accessibility lint: `eslint-plugin-jsx-a11y` (React) or equivalent for Vue/Svelte — enabled at `error` level, not `warn`.
Enforcement: CI step `eslint . && prettier --check .`. PRs MUST NOT merge with lint or format failures.
