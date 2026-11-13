Subject: Add a pause command to the machine
Tracker: Task · Status: Ready · Target version: Release 1 · Estimated time: 4 · Assignee: you
(With custom fields: Machine-side = Yes, Hotspot = src/sandbox/machine.py)

## Context
Operators need to pause the machine without losing the current position (stop() returns to the safe position).

## Scope
In scope:
- `Machine.pause()`: running becomes False, the position is kept.
- While paused, `move_to` is refused until `resume()` is called.
Out of scope:
- Changing MAX_SPEED_MM_S, the door check, or stop().

## Acceptance criteria
- [ ] AC1 — Given a machine at 80 mm, when paused, then position is still 80 mm and running is False.
- [ ] AC2 — Given a paused machine, when move_to is called, then it is refused (RuntimeError).
- [ ] AC3 — Given a paused machine, when resume() then move_to(10, 50), then the move succeeds.
- [ ] AC4 — The door check and the speed limit still apply (existing tests unchanged).

## Constraints
- Sensitive path: the safety checks in machine.py must stay as they are. Mode FULL, code-owner review.

## Technical notes
- File: `src/sandbox/machine.py`, tests in `tests/test_machine.py`.

## Test approach
- Unit tests for AC1–AC4 first; run the whole test suite.

## Dependencies
Blocked by (tickets): none
Waiting for (external): none
Open questions: none

## Size and mode
Estimate: 3–4 h · Proposed mode: (agent proposes) · Machine-side: yes · Hotspot: src/sandbox/machine.py
