---
name: voice-guide
description: |
  How to capture and apply a target audience and voice for content generation and review. Import this skill when drafting content (content-writer) or evaluating voice match (content-reviewer).
---

# Voice Guide

This skill defines the process for capturing a target voice and applying it consistently. Without a defined voice, content defaults to a generic "professional" register that reads as impersonal.

---

## Part 1 — Capturing a Voice

### Step 1: Identify the audience

Establish two things before writing a word:

1. **Who reads this?** Name a concrete reader type — not "technical users" but "a backend engineer who already understands REST APIs and wants the specific edge case explained."
2. **What do they know already?** Calibrate terminology and explanation depth to what they can be assumed to know. Do not over-explain to experts; do not skip definitions for newcomers.

### Step 2: Establish register

Choose one register and hold it throughout:

| Register | When to use | What it sounds like |
|----------|-------------|---------------------|
| Direct / peer | Technical docs, internal tools, developer READMEs | Short sentences, active voice, no preamble |
| Conversational | Blog posts, tutorials, onboarding guides | Contractions allowed, rhetorical questions used sparingly |
| Formal / editorial | Press releases, analyst briefs, policy documents | Passive voice acceptable, hedging minimal and deliberate |
| Casual | Social copy, community posts, changelogs | Colloquialisms fine, sentence fragments allowed |

### Step 3: Collect voice samples

If the target voice already exists (a prior README, a blog, a company style guide), collect 3–5 sentences that best represent it. Note:
- Average sentence length
- Ratio of questions to statements
- Use of first person ("we", "I") vs. second person ("you") vs. third person
- Presence or absence of humor / personality markers

### Step 4: Write a voice statement

One sentence that summarizes the voice for use in briefs:

> "Write for a senior engineer audience in a direct peer register — no preamble, active voice, contractions welcome, sentence length 12–20 words on average."

---

## Part 2 — Applying a Voice

### Before drafting

1. Read the voice statement from the brief.
2. If no voice statement is provided, use this default and state the assumption explicitly in the output:
   > Default voice assumed: direct peer register, second-person address, active voice, 12–20 word average sentence length. State this assumption at the top of the draft.

### During drafting

Apply these checks sentence by sentence:

1. **Register consistency** — each sentence should match the declared register. A formal document should not slip into "let's dive in". A casual post should not suddenly adopt passive constructions.

2. **Pronoun stability** — decide "we/our" or "you/your" and do not alternate without a clear reason.

3. **Sentence length target** — vary sentence length within the target range. Include at least one short sentence (under 10 words) per 200 words of output to create rhythm.

4. **Jargon calibration** — use terms the defined audience knows. Define only terms the audience may not know. Never define terms to show comprehensiveness.

### After drafting

Run through this checklist before passing text to `humanizer-linter`:

- [ ] Opening sentence makes a specific claim or states a concrete fact — it does not set the scene.
- [ ] No sentence begins with "In conclusion" or "To summarize" unless this is a formal document requiring it.
- [ ] No paragraph is purely restatement of a prior paragraph.
- [ ] Voice register is consistent from first sentence to last.
- [ ] Every claim in the text can be verified or sourced. Remove claims that cannot.

---

## Part 3 — Voice Mismatch Signals

The `content-reviewer` checks for these voice mismatch signals:

| Signal | What it looks like |
|--------|-------------------|
| Register slip | Casual post that suddenly uses "pursuant to" or "it is evident that" |
| Audience mismatch | Explains basic concepts to an expert audience, or uses unexplained jargon with a beginner audience |
| Pronoun drift | Alternates between "we" and "you" within the same section without rhetorical intent |
| Tone inconsistency | Serious topic with a jokey aside that breaks trust |
| Preamble padding | First 2+ sentences have no informational content |
| Hedging overload | Claims qualified with "might", "could", "may" when the author clearly believes the claim |

---

## Part 4 — Default Voice (when no voice is specified)

When `content-writer` receives a brief with no voice specification:

1. Use the default voice: direct, second-person, active, peer register.
2. Add this notice at the top of the output:

```
NOTE: No voice specified in the brief. Default voice applied: direct peer register, second-person, active voice. Rerun with a voice statement to target a different register.
```

3. Pass this notice through to the user — do not suppress it.
