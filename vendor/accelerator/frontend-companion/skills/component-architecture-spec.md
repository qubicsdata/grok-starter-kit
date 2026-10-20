---
name: component-architecture-spec
description: Component boundary and state ownership rules for frontend-companion. Import when reviewing component architecture, state management, or container/presentation patterns.
---

# Component Architecture Spec

Import this skill when reviewing UI component architecture. All findings must cite the rule ID.

---

## 1. Component Boundaries

- ARCH-1 Single Responsibility: each component renders one coherent concept. A component that renders a user card AND handles pagination is two components.
  Flag when: a component has more than one distinct visual section that could be independently reused, or more than two unrelated event handlers.

- ARCH-2 Size limit: functional components should not exceed ~150 lines of JSX/template. Beyond this, extract child components or custom hooks.
  Flag when: component body (excluding imports and type definitions) exceeds 150 lines.

- ARCH-3 Co-location: a component's styles, tests, and private sub-components live in the same directory as the component file.
  Prefer: `UserCard/UserCard.tsx`, `UserCard/UserCard.test.tsx`, `UserCard/UserCard.module.css`
  Avoid: all styles in a global `styles/` folder, all tests in a root `__tests__/` folder separated from components.

---

## 2. State Ownership

- STATE-1 Single source of truth: each piece of UI state is owned by exactly one component or one store slice. Derived values are computed, not stored.
  Flag when: the same logical value is stored in two different `useState` calls or two different store slices.

- STATE-2 Lift only as high as needed: state is placed in the lowest common ancestor of the components that read it. Pushing state to a global store when it is only used by two siblings is premature.
  Flag when: global state is used by only one subtree of the component tree.

- STATE-3 Local UI state stays local: ephemeral UI state (is-open, hover, focus) belongs in `useState` or `useReducer`, not in a global store.
  Flag when: `isDropdownOpen`, `isTooltipVisible`, or similar transient UI booleans appear in a global store.

- STATE-4 Async state: server data cached by a data-fetching library (React Query, SWR, RTK Query) is never duplicated into component-local state. Only `status`, `data`, and `error` from the library are consumed.
  Flag when: `const [data, setData] = useState(null)` is used alongside a data-fetching hook for the same resource.

---

## 3. Container / Presentation Pattern

- CP-1 Separate data-fetching from rendering: container components own data-fetching and state; presentation components receive all data via props and emit events via callback props.
  Container: fetches data, handles loading/error, passes data to presentation component.
  Presentation: renders props only; has no direct API calls or store subscriptions.

- CP-2 Presentation components are independently testable: a presentation component must be renderable in a test with mock props alone — no store provider, no router, no API mock required.
  Flag when: a component that is described as "presentational" uses `useContext`, `useSelector`, or direct API calls internally.

- CP-3 Custom hooks for shared logic: logic reused across more than one component is extracted into a `use<Name>` custom hook. The hook is unit-tested independently of any component.
  Flag when: the same stateful logic (fetch + transform + error-handle) appears in two or more components without a shared hook.

---

## 4. Prop Drilling

- PD-1 Two-level maximum: passing a prop through more than two intermediate components that do not use it is prop drilling. Extract to context or a state manager.
  Flag when: a prop appears in a component's signature but is only passed down, never accessed.

- PD-2 Context for cross-cutting concerns: auth, theme, locale, and feature flags are delivered via React Context or equivalent. They are never threaded as explicit props.

- PD-3 Avoid over-contextualizing: high-frequency UI state (scroll position, animation values) must not go through React Context — Context re-renders all consumers on every change.
  Flag when: animated values or scroll offsets are stored in Context.

---

## 5. Re-Render Hygiene

- RR-1 Memoize expensive renders: `React.memo` on presentation components that receive stable props prevents re-renders from parent state changes.
  Apply when: a presentation component renders a list of 50+ items or performs expensive layout work.

- RR-2 Stable callback references: callbacks passed as props to memoized children must be wrapped in `useCallback` with accurate dependency arrays.
  Flag when: an inline arrow function is passed to a `React.memo`-wrapped component.

- RR-3 Key prop stability: list keys must be stable unique IDs, not array indices.
  Flag when: `key={index}` is used in a list that can be reordered, filtered, or has items added/removed.
