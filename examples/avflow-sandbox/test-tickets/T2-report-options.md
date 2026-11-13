Subject: Report options: filter by status and sort by due date
Tracker: Task · Status: Ready (Enclave: New) · Target version: Release 1 · Estimated time: 8 · Assignee: you

## Context
Planners use the order report every morning. They want to see only the orders that matter (for example open ones) and see the most urgent first. Today the report lists every order in creation order.

## Scope
In scope:
- A new module `src/sandbox/report_options.py` with a `ReportOptions` dataclass: `status` (optional) and `sort` ("due" or "number", default "number"), validated on creation.
- `by_status(orders, status)` in `src/sandbox/orders.py`.
- `render(orders, options=None)` in `src/sandbox/report.py` applies the filter, then the sort; without options the output is unchanged.
- A short "Report options" section in `README.md`.
Out of scope:
- Totals (ticket T4), new columns, export formats.
- Any change to `src/sandbox/machine.py`.

## Acceptance criteria
- [ ] AC1 — Given the sample orders and options status="open", when rendered, then only WO-1001 is listed (plus the header line).
- [ ] AC2 — Given options sort="due", when rendered, then the rows are ordered WO-1002, WO-1001, WO-1003.
- [ ] AC3 — Given status="in_production" and sort="due", when rendered, then only WO-1002 is listed.
- [ ] AC4 — Given no options, when rendered, then the output is exactly the same as today.
- [ ] AC5 — Given an unknown status or an unknown sort key, when creating ReportOptions, then a ValueError names the bad value.

## Constraints
- No new dependencies. Existing tests must keep passing without changes.

## Technical notes
- Files: new `src/sandbox/report_options.py`; change `src/sandbox/orders.py`, `src/sandbox/report.py`, `README.md`; tests in `tests/test_report_options.py`, `tests/test_orders.py`, `tests/test_report.py`.
- Suggested order: options and validation → filter → sort → render → README.

## Test approach
- Unit tests for AC1–AC5, written before the code; AC4 compares against the current output.

## Dependencies
Blocked by (tickets): none
Waiting for (external): none
Open questions: none

## Size and mode
Estimate: 1 day · Proposed mode: (agent proposes) · Machine-side: no · Hotspot: src/sandbox/report.py
