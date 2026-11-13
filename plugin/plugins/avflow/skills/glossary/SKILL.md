---
name: glossary
description: Use when the project's domain language is unclear, conflicting or new — a term in a ticket, in a discussion or in the code that is not in docs/CONTEXT.md, or that is used with two meanings. Keeps docs/CONTEXT.md sharp. Adapted from Matt Pocock's domain-modeling skill (MIT), using the team's docs/CONTEXT.md instead of GLOSSARY.md.
---

# Glossary

Keep the project's language precise in **`docs/CONTEXT.md`** — the team's glossary. Adapted from Matt Pocock's
`domain-modeling` skill (MIT licence).

## When

- A ticket, a person or the code uses a term that is **not in `docs/CONTEXT.md`**.
- A term is used with **two meanings**, or two words are used for **one concept**.
- The code contradicts what someone says about a concept.

Merely *reading* `docs/CONTEXT.md` for vocabulary is not this skill — every skill should do that.

## During the work

- **Challenge conflicts.** "CONTEXT.md defines *spread* as X, but this ticket seems to mean Y. Which is it?"
- **Sharpen fuzzy terms.** Propose one canonical term and list the others to avoid.
- **Test with concrete scenarios** that probe the edges of a concept.
- **Cross-check with the code** and point out contradictions.

## Writing it down

Propose each resolved term as a change to `docs/CONTEXT.md`, in the same merge request as the work (or its own small one). A person reviews it like any code change.

```markdown
**Settlement**:
The moment an order's payment is final and can no longer be cancelled.
_Avoid_: completion, closing
```

Rules:

- **Opinionated:** one term per concept; others under `_Avoid_`.
- **Tight:** one or two sentences; what it **is**, not how it is implemented.
- **Project-specific only:** no general programming concepts.
- **No implementation details** — CONTEXT.md is a glossary, not a spec.
- Group related terms under subheadings when clusters appear.

When a resolved term reflects a hard-to-reverse decision, use the `adr` skill as well.
