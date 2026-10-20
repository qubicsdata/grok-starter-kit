# content-companion

Human-sounding content pipeline for docs, READMEs, blog posts, release prose, and marketing copy. Enforces an explicit anti-AI-tell discipline through a rule-based linter and a judgment-based reviewer working in sequence.

## Installation

Install via the accelerator plugin loader:

```bash
claude plugin install content-companion
```

Or symlink into your project's plugin directory:

```bash
ln -s /path/to/accelerator/content-companion .claude/plugins/content-companion
```

## Usage

Draft a README for a CLI tool, lint it for AI tells, and review it for voice and authenticity:

```
/write audience: senior engineers; purpose: README for a CLI tool; length: 400 words; voice: direct peer register, second-person, active voice; topic: how to install and configure the tool
```

Check an existing file for AI tells and surface all violations before publication:

```
/humanize docs/product-overview.md
```

The spec-enricher is invoked automatically by `ai-baseline`'s enrich runner when a spec is submitted. It returns CON-1..CON-3 requirements when the spec defines a user-facing prose or documentation deliverable.

## Commands

- `/write <brief>` — draft content from a brief (audience, purpose, length, voice, topic), run it through the humanizer-linter, then pass to content-reviewer; return the full pipeline result
- `/humanize <file>` — lint an existing file for AI tells, surface all violations with locations; does not rewrite the file

## Dependencies

- requires: ai-baseline

---

<your-name> (you@example.com)
