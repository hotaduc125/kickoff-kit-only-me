Subject: Validate customer names
Tracker: Task · Status: Ready · Target version: Release 2 · Assignee: A COLLEAGUE (not you)

## Context
Orders accept an empty customer name.

## Scope
In scope: refuse empty or whitespace-only customer names in Order.
Out of scope: anything else.

## Acceptance criteria
- [ ] AC1 — Given customer "  ", when creating an Order, then ValueError.

## Size and mode
Estimate: 1 h · Proposed mode: (agent proposes) · Machine-side: no · Hotspot: none
