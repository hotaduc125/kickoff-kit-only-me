---
name: triage
description: Use when a ticket from the customer (or anyone outside the team) needs to be understood and routed — classify it as defect, change request, question or maintenance, verify it, find what is missing, and draft the work ticket. Adapted from Matt Pocock's triage skill (MIT) so that it works through the avflow-tickets tools only and never writes anything the customer can read.
---

# Triage

Turn an incoming ticket into a clear decision for a person: what it is, whether it holds up, and what work it needs.
Adapted from Matt Pocock's `triage` skill (MIT licence): same discipline — gather, check, verify, then recommend —
but every note is **private**, nothing is published to the customer, and the categories follow the team's contracts.

## Rules

- Read and write tickets **only** with the `tickets` skill (avflow-tickets MCP server). All notes are private notes.
- **Never reply to the customer, never change the customer's ticket, never promise anything.** A person answers the customer.
- Start every triage note with: `> AI-generated during triage — for the team, to be reviewed by a person.`
- You recommend; a person decides the category and whether work starts.

## Categories

| Category | Meaning | What happens next |
|---|---|---|
| **Defect** | Delivered behaviour does not match what was agreed | Severity S1–S3; reproduce; work ticket (bug draft) |
| **Change request** | New or different behaviour — even if the customer calls it a bug ("this screen should also show …") | Estimate and customer approval before any work — **never start it as a defect** |
| **Question** | The customer needs an answer, not a change | A person answers; no work ticket |
| **Maintenance** | Small upkeep of existing software outside the current scope | Maintenance tracker, weekly allowance |

Severity for defects: **S1** production stopped or safety risk · **S2** production impaired, workaround exists · **S3** minor.

## Steps

1. **Gather.** Read the whole ticket with `get_ticket` (description, notes, attachments list). Read the project glossary (`docs/CONTEXT.md`) and the ADRs in the area so you use the project's terms.
2. **Check against the code and history.**
   - *Already there?* Search the code for the requested behaviour by domain concept, not only by the customer's words. Report where you looked.
   - *Agreed before?* Look in the scope documents and earlier tickets: is this in scope, out of scope, or already rejected?
3. **Recommend.** In a private note: category, severity (defects), one-paragraph reasoning, and the relevant code areas. **Stop and wait for the person.**
4. **Verify (defects).** Try to reproduce from the reporter's steps — in a test environment if the project has one (see its `CLAUDE.md`). Report: *reproduced* (with the code path), *not reproduced*, or *not enough information*. A defect that cannot be reproduced is not yet a work ticket.
5. **Find what is missing.** List the exact questions or data needed (logs, versions, steps, screenshots) as a private note — specific and actionable, never "please provide more information". The person decides what to ask the customer.
6. **Draft the work ticket** with the `ticket-writer` skill:
   - defect → `create_bug_draft` (private draft, related to the customer ticket);
   - change request or maintenance → draft the text in a private note; a person creates the ticket after approval.
7. **Resume, do not restart.** If earlier triage notes exist, read them first and present only what changed.

## Triage note template

```markdown
> AI-generated during triage — for the team, to be reviewed by a person.

**Recommendation:** Defect S2 | Change request | Question | Maintenance
**Why:** …
**Already implemented / in scope?** … (where I looked)
**Verification:** reproduced on … / not reproduced / not enough information
**Still needed:** …
**Proposed work ticket:** … (or "none")
```
