---
name: usability-heuristics
description: Nielsen's 10 usability heuristics with application guidance for evaluating described user flows and screens. Import when evaluating a flow for usability quality.
---

# Usability Heuristics

Nielsen's 10 usability heuristics are the canonical framework for evaluating interaction design quality without user testing. Apply them to textual descriptions of flows, screens, and interactions.

## The 10 Heuristics

### H-1: Visibility of System Status
The system should always keep users informed about what is going on, through appropriate feedback within reasonable time.

**Apply to flows by asking:**
- Does every action have a visible response (loading indicator, confirmation message, progress bar)?
- Are async operations (form submit, data load, file upload) acknowledged immediately with a status indicator?
- Is the current step in a multi-step flow clearly indicated?

**Flag if:** A described flow has no loading/progress indication for operations that take more than 0.1 seconds, or if the current state is ambiguous after an action.

### H-2: Match Between System and the Real World
The system should speak the users' language — words, phrases, and concepts familiar to the user, rather than system-oriented terms.

**Apply to flows by asking:**
- Are labels, button text, and error messages written in plain language?
- Do metaphors match user mental models (e.g., a shopping cart, a trash can)?
- Are technical terms (IDs, codes, internal names) exposed to end users?

**Flag if:** A described screen uses jargon, internal system identifiers, or technical terminology where plain alternatives exist.

### H-3: User Control and Freedom
Users often choose system functions by mistake and will need a clearly marked "emergency exit" to leave the unwanted state without going through an extended dialogue.

**Apply to flows by asking:**
- Can users undo or cancel every destructive action?
- Is there a clear back/cancel option in every multi-step flow?
- Are confirmation dialogs present before irreversible actions (delete, submit final)?

**Flag if:** A described flow has no cancel option, no undo, or no confirmation before a destructive action.

### H-4: Consistency and Standards
Users should not have to wonder whether different words, situations, or actions mean the same thing.

**Apply to flows by asking:**
- Are equivalent actions labeled consistently across screens (e.g., always "Save" vs sometimes "Save", sometimes "Apply")?
- Do primary/secondary button positions match a consistent pattern?
- Are navigation patterns (tabs, breadcrumbs, back links) used consistently?

**Flag if:** The same action is described differently in different parts of the flow, or UI patterns are applied inconsistently.

### H-5: Error Prevention
Even better than good error messages is a careful design which prevents a problem from occurring in the first place.

**Apply to flows by asking:**
- Are form fields validated inline before submission?
- Are irreversible choices confirmed before execution?
- Are likely user mistakes (empty submissions, wrong format) caught at the earliest point?

**Flag if:** A described flow allows submission with invalid or empty required fields without inline validation, or performs irreversible actions without confirmation.

### H-6: Recognition Over Recall
Minimize the user's memory load by making objects, actions, and options visible.

**Apply to flows by asking:**
- Are options visible rather than requiring the user to remember them?
- Are recently used items, previous values, or saved state surfaced?
- Do forms show previously entered data when returning from an error state?

**Flag if:** A described flow requires users to memorize information from a previous step (e.g., an ID shown on one screen needed on the next with no carry-forward).

### H-7: Flexibility and Efficiency of Use
Accelerators — unseen by the novice user — may often speed up the interaction for the expert user.

**Apply to flows by asking:**
- Are keyboard shortcuts, bulk actions, or quick-select options present for power users?
- Can frequently performed flows be abbreviated or saved?
- Are defaults pre-populated with the most common choice?

**Flag if:** A high-frequency flow requires the same long sequence of steps every time with no shortcut or default.

### H-8: Aesthetic and Minimalist Design
Dialogues should not contain irrelevant or rarely needed information. Every extra unit of information in a dialogue competes with the relevant units of information.

**Apply to flows by asking:**
- Does each screen expose only the information needed for the current task?
- Are low-priority options hidden behind progressive disclosure?
- Is secondary information visually de-emphasized relative to primary actions?

**Flag if:** A described screen mixes primary actions with secondary information at equal visual weight, or surfaces rarely-needed options at the same level as frequent tasks.

### H-9: Help Users Recognize, Diagnose, and Recover from Errors
Error messages should be expressed in plain language (no codes), precisely indicate the problem, and constructively suggest a solution.

**Apply to flows by asking:**
- Do error messages describe what went wrong in plain language?
- Does each error message suggest a concrete next step?
- Are errors shown near the source of the problem (field-level vs page-level)?

**Flag if:** A described flow shows generic error messages ("Something went wrong"), error codes without explanation, or page-level errors without identifying the specific field.

### H-10: Help and Documentation
Even though it is better if the system can be used without documentation, it may be necessary to provide help.

**Apply to flows by asking:**
- Is contextual help (tooltips, inline hints, example values) available for complex fields?
- Is help easily searchable and task-focused?
- Are empty states instructive (explaining what to do next) rather than just empty?

**Flag if:** A complex form has no tooltips or examples for non-obvious fields, or an empty state shows nothing rather than an instructive prompt.

## How to Apply Heuristics to a Flow Description

1. **Identify the flow steps** from the description (user opens screen → enters data → submits → sees result).
2. **For each step**, check all 10 heuristics. A step may violate multiple.
3. **For each violation**, identify the heuristic ID (H-1 through H-10), the severity (HIGH = breaks core task, MEDIUM = degrades experience, LOW = polish issue), and a concrete fix.
4. **If a state is not described** (loading, error, success, empty), flag it as a potential H-1 or H-9 violation — missing state descriptions are evidence of missing design decisions.

## Severity Guide

| Severity | Condition |
|----------|-----------|
| HIGH | User cannot complete the primary task; destructive action without safeguard; no error recovery |
| MEDIUM | User is confused or slowed; inconsistent patterns; missing loading state |
| LOW | Polish, efficiency, help, minimalism improvements |
