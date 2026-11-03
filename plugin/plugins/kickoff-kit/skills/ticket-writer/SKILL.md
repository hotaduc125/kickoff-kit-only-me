---
name: ticket-writer
description: Use when drafting or reviewing a ticket for the team — turning a customer request, a bug reproduction or a planned task into a ticket an agent can work on without asking questions. Produces the team ticket structure; a person reviews scope and acceptance criteria before the ticket goes to Ready.
---

# Ticket writer

Draft every team ticket in this structure. Mark anything you cannot know as **TODO before Ready** instead of guessing.

```markdown
## Context
Why this ticket exists, in 2–3 sentences. Link to the requirement and the technical design section.

## Scope
In scope:
- …
Out of scope:
- …

## Acceptance criteria
- [ ] AC1 — Given …, when …, then …
- [ ] AC2 — …

## Constraints
- Files / areas that must NOT change: …
- Machine behaviour that must stay identical: …
- Performance, compatibility, languages (zh / en): …

## Technical notes
- Likely files / classes: …
- Similar existing code to follow: …
- Design reference: docs/… section …

## Test approach
- Unit / characterisation: …
- Simulator scenario: …
- Test bench (machine-side only): …
- Test data: …

## Dependencies
Blocked by (tickets): #… (hard → relation "blocked by") · #… (soft → "related to", work against the agreed interface)
Waiting for (external): …
Open questions: … (who answers)

## Size and mode
Estimate: low–high h · Proposed mode: direct / plan / full / spike · Machine-side: yes / no · Hotspot: …
```

## Rules
- **Out of scope** is mandatory: list what must not be added.
- Acceptance criteria are measurable (Given / When / Then); one criterion per behaviour.
- Dependencies: hard → relation "blocked by"; soft → "related to" plus the agreed interface.
- Machine-side = yes when the work touches hardware control, safety or installation.
- Customer tickets are not worked on directly: draft a linked work ticket; a person reviews it and answers the customer.
- You only draft. A person creates or edits the ticket and moves it to Ready.
