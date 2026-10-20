---
name: visual-hierarchy-principles
description: Layout, emphasis, grouping, information density, and reading order principles for evaluating screen descriptions. Import when assessing the visual hierarchy of a described screen or layout.
---

# Visual Hierarchy Principles

Visual hierarchy is the arrangement of design elements so that the most important information is noticed first, and supporting information is encountered in logical order. This skill defines the principles to apply when evaluating screen descriptions.

## VH-1: Primary Action Clarity
Every screen MUST have exactly one visually dominant primary action. The user must be able to identify the primary action without scanning the entire screen.

**Criteria:**
- One call-to-action at highest visual weight (largest, most contrast, brand color)
- Secondary actions at lower weight (ghost, secondary variant, or smaller)
- Destructive actions distinguished from primary (destructive variant, separated)

**Flag VH-1 violation if:**
- A screen has no clearly dominant action
- Two or more actions are described at equal visual weight
- A destructive action is visually indistinguishable from the primary action

**Severity:** HIGH — users cannot identify what to do next.

## VH-2: Reading Order
Content must flow in a predictable reading order aligned with user scanning patterns (F-pattern for text-heavy; Z-pattern for action-oriented layouts).

**Criteria for text-heavy layouts (articles, documentation, dashboards):**
- Most important information in top-left (F-pattern entry)
- Descending importance from top to bottom
- Secondary information in right column or below fold

**Criteria for action-oriented layouts (forms, checkout, onboarding):**
- Headline → supporting text → primary action follows Z-pattern
- No orphaned actions requiring users to reverse their reading direction

**Flag VH-2 violation if:**
- The primary action is described at the bottom of a long list of equivalent-weight items
- Critical information (error, required field) is in the bottom-right where the eye lands last
- A form's submit button requires scrolling past unrelated content

**Severity:** MEDIUM — task completion is slowed.

## VH-3: Grouping and Proximity
Related elements MUST be visually grouped; unrelated elements MUST be visually separated.

**Criteria:**
- Fields in the same logical group share a bounding container or consistent spacing
- Distinct groups have more space between them than between their internal elements
- Section headers visually lead their group (spacing above > spacing below)

**Flag VH-3 violation if:**
- Related form fields have the same spacing between them as between unrelated sections
- A heading is described with equal spacing above and below (floating, not leading)
- Action buttons (Save / Cancel) are described far from the form they control

**Severity:** MEDIUM — cognitive load increases; users misread groupings.

## VH-4: Emphasis and Contrast
The most important content must be the most visually prominent. Emphasis is created through size, weight, color, and whitespace.

**Criteria:**
- Heading hierarchy mirrors semantic hierarchy (h1 > h2 > h3 visually)
- Key numbers/metrics at display or h1 scale when they are the screen's primary content
- Supporting metadata at caption/label scale
- At least 3:1 contrast ratio between primary and secondary text levels

**Flag VH-4 violation if:**
- A metric described as the screen's primary content uses body text size
- A heading uses the same visual weight as the body text it introduces
- Critical information (price, deadline, error) is in a de-emphasized style

**Severity:** MEDIUM to HIGH depending on importance of the de-emphasized content.

## VH-5: Information Density
Each screen must balance density against clarity. Dense screens overwhelm; sparse screens waste space and create unnecessary navigation.

**Criteria:**
- Action-oriented screens (forms, wizards): low density — one task per screen, minimal competing information
- Reference screens (dashboards, tables): medium-high density — scannable structure required
- Marketing screens (landing pages): low-to-medium density — breathing room increases trust

**Density anti-patterns:**
- More than 7 ± 2 distinct items without grouping or progressive disclosure (Miller's Law)
- Mixing unrelated information types (navigation + content + settings) without clear section boundaries
- No whitespace between sections — "wall of content"

**Flag VH-5 violation if:**
- A form has more than 7 fields without a section break or step indicator
- A dashboard shows more than 3 levels of navigation in the same visible area
- A screen description mixes primary task content with secondary informational content at equal density

**Severity:** MEDIUM — user cognitive load exceeds capacity.

## VH-6: Empty, Loading, Error, and Success States
Every screen MUST define all four supplementary states. A missing state is a design gap, not a default.

**Empty state requirements:**
- Illustration or icon (optional but recommended)
- Headline explaining why it is empty ("No reports yet")
- CTA or next step ("Create your first report →")

**Loading state requirements:**
- Skeleton screen OR spinner with label
- Estimated time or progress indication for operations > 3 seconds

**Error state requirements:**
- Specific error message (not "Something went wrong")
- Recovery action (retry, contact support, return to previous step)

**Success state requirements:**
- Positive confirmation (checkmark, success message)
- Clear next step or summary of what was accomplished

**Flag VH-6 violation if:**
- A screen description omits any of the four states
- An error state shows no recovery action
- A success state gives no summary or next step
- A loading state is described as a blank screen

**Severity:** HIGH for missing error/empty; MEDIUM for missing success/loading details.

## How to Apply These Principles

1. **Identify the screen type** (form, dashboard, landing, list, detail) — this sets density expectations.
2. **Locate the primary action** (VH-1). If not obvious from the description, flag immediately.
3. **Trace the reading order** (VH-2). Can a new user find the primary task without scanning everything?
4. **Check groupings** (VH-3). Are related elements close? Are unrelated elements separated?
5. **Check emphasis** (VH-4). Does visual weight match semantic importance?
6. **Assess density** (VH-5). Is the amount of content appropriate for the screen type?
7. **Verify four states** (VH-6). Are empty, loading, error, and success states all described?
