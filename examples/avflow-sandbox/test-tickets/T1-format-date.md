Subject: Add a date formatting helper
Tracker: Task · Status: Ready (Enclave: New) · Target version: Release 1 · Estimated time: 2 · Assignee: you

## Context
Dates are formatted in several places with str(date). We want one helper so every screen shows dates the same way (YYYY-MM-DD).

## Scope
In scope:
- A function `format_date(value)` in a new module `src/sandbox/formatting.py`.
Out of scope:
- Changing `report.py` or any other module to use it (a later ticket).
- Time zones and times of day.

## Acceptance criteria
- [ ] AC1 — Given date(2026, 11, 5), when formatted, then the result is "2026-11-05".
- [ ] AC2 — Given None, when formatted, then the result is "" (no error).

## Constraints
- No new dependencies. Do not change existing modules.

## Technical notes
- New file `src/sandbox/formatting.py`; tests in `tests/test_formatting.py`.

## Test approach
- Unit tests for AC1 and AC2, written first.

## Dependencies
Blocked by (tickets): none
Waiting for (external): none
Open questions: none

## Size and mode
Estimate: 1–2 h · Risk area: None · Hotspot: none
