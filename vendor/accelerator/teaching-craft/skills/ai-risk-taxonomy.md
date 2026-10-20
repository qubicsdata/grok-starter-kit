---
name: ai-risk-taxonomy
description: |
  Responsible-AI risks framed for practitioners rather than compliance officers — each risk paired with why a working engineer should care and a short exercise that makes it concrete. Cross-links to compliance-companion for regulatory framing and security-companion for adversarial framing rather than restating either. Consumed by workshop-companion agents when a session teaches responsible AI.
---

# AI Risk Taxonomy

Each entry is: the risk, why a practitioner should care, and a 15-minute exercise.

## RISK-1 — Hallucination

**Why care:** Fluent wrong answers cost more than obvious wrong answers, because
they survive review.

**Exercise:** Have learners ask for something in their own domain where they can
verify the answer cold. Collect how many caught the error and how long it took.
If the answer comes back correct and no error appears, that is not a null
result: ask the room what specifically they checked to be sure, and how they
would have caught it if it had been wrong. The verification habit is the
teaching point whether or not this particular attempt produced a hallucination.

## RISK-2 — Automation bias

**Why care:** Review quality degrades as agent output quality rises. The failure
arrives exactly when trust has been earned.

**Exercise:** Give learners a diff with one subtle planted error, framed as
agent-generated. Compare catch rates against the same diff framed as
human-written.

## RISK-3 — Data leakage

**Why care:** Learners in this series point agents at their own real work. Real
code and real customer data enter prompts during the session.

**Exercise:** Have learners identify, without pasting anything, what in their
current working directory must never leave the machine. Then run
`ai-baseline`'s `pii-scrub-agent` against a sanitised sample and watch it fire.

## RISK-4 — Provenance and IP

**Why care:** Generated code carries no attribution, and licence obligations do
not disappear because the origin is unclear.

**Exercise:** Run `dependency-auditor`'s `/licenses` against a real project and
discuss which obligations were previously invisible.

## RISK-5 — Disclosure norms

**Why care:** Teams disagree about whether agent involvement must be declared in
a commit, a PR, or a customer deliverable, and the disagreement surfaces after
the fact.

**Exercise:** Have the room draft one disclosure rule they would all accept.
Surface where they cannot agree; that gap is the finding.

## RISK-6 — Knowing when not to use an agent

**Why care:** The cost of an inappropriate agent task is usually paid by someone
downstream, not by the person who chose to delegate it.

**Exercise:** Have learners list three tasks from their own week they would not
delegate, and state the property that rules each one out.

## Cross-links

- Regulatory framing (EU AI Act obligations, model cards, oversight gates):
  compliance-companion.
- Adversarial framing (abuse cases, threat surface): security-companion.
- Evaluation and safety testing of model behaviour: ai-eval-companion.

This skill does not restate those. It exists to make the risks teachable.
