---
name: adr
description: Use when a decision is hard to reverse, would surprise a future reader, and came from a real trade-off — record it as an architecture decision record in docs/adr/. Adapted from the ADR format in Matt Pocock's domain-modeling skill (MIT), available with either workflow.
---

# Architecture decision records

Record **that** a decision was made and **why**, in `docs/adr/`. Adapted from the ADR format in Matt Pocock's
`domain-modeling` skill (MIT licence).

## When to write one — all three must be true

1. **Hard to reverse:** changing your mind later costs real effort.
2. **Surprising without context:** a future reader would ask "why on earth did they do it this way?"
3. **A real trade-off:** there were genuine alternatives and one was chosen for specific reasons.

If one is missing, do not write an ADR.

Typical cases: architectural shape (separate application vs plug-in), integration patterns, technology with lock-in, boundary and scope decisions, deliberate deviations from the obvious path, constraints not visible in the code (customer contract, safety, hardware), and non-obvious rejected alternatives.

## Format

File `docs/adr/NNNN-short-slug.md`: scan `docs/adr/` for the highest number and add one (4 digits).

```markdown
# NNNN — Short title of the decision

Status: proposed | accepted | superseded by NNNN
Date: YYYY-MM-DD

{1–3 sentences: the context, what we decided, and why.}

## Considered options        (only if the rejected ones are worth remembering)
## Consequences              (only if they are not obvious)
```

An ADR can be a single paragraph. Write it as **proposed**; the person (or the team's decision owner) changes it to **accepted**. Link the ticket (`Refs #id`) in the merge request, and mention the ADR number in a private note on the ticket.
