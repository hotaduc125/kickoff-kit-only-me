Subject: Show totals per status under the report
Tracker: Task · Status: Ready · Target version: Release 1 · Estimated time: 2 · Assignee: you
After creating: Related issues → Add → Blocked by → <number of T2>

## Context
Planners want to see how many units are open, in production and done.

## Scope
In scope:
- A totals line per status under the report (sum of quantity), using `by_status` from T2.
Out of scope:
- Charts, exports.

## Acceptance criteria
- [ ] AC1 — Given the sample orders, then the report ends with: open 120 · in_production 40 · done 75.

## Constraints
- Reuse `orders.by_status` from T2.

## Technical notes
- File: `src/sandbox/report.py`.

## Test approach
- Unit test for AC1.

## Dependencies
Blocked by (tickets): T2 (hard — uses orders.by_status)
Waiting for (external): none
Open questions: none

## Size and mode
Estimate: 1–2 h · Proposed mode: (agent proposes) · Machine-side: no · Hotspot: src/sandbox/report.py
