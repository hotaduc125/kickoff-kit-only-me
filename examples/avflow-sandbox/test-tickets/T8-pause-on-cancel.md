Subject: Pause the machine when an order is cancelled
Tracker: Task · Status: Ready (Enclave: New) · Target version: Release 1 · Estimated time: 3 · Assignee: you
After creating: Related issues → Add → Related to → <number of T3>

## Context
When a planner cancels an order that is in production, the machine keeps working on it. It should stop moving at
once, without returning to the safe position, so the operator can take the part out.

## Scope
In scope:
- `cancel_order(order, machine)` in a new module `src/sandbox/production.py`: returns the order with status
  "cancelled"; if the machine is working on that order, it is paused (position kept, moves refused until resumed).
- The machine knows which order it is working on (`current_order`, the order number or None).
Out of scope:
- Changing MAX_SPEED_MM_S, the door check, or stop().
- Cancelling from the report or any user interface.

## Acceptance criteria
- [ ] AC1 — Given an open order WO-1001, when cancelled, then the returned order has status "cancelled".
- [ ] AC2 — Given a machine at 80 mm working on WO-1002, when WO-1002 is cancelled, then running is False, the position is still 80 mm and current_order is None.
- [ ] AC3 — Given a machine working on WO-1002, when WO-1001 is cancelled, then the machine is unchanged.
- [ ] AC4 — The door check and the speed limit still apply (existing tests unchanged).

## Constraints
- No new dependencies. Existing tests must keep passing without changes.

## Technical notes
- New module `src/sandbox/production.py`; tests in `tests/test_production.py`.
- If T3 is merged, reuse its pause / resume behaviour.

## Test approach
- Unit tests for AC1–AC4 first; run the whole test suite.

## Dependencies
Blocked by (tickets): none (related to T3 — reuse pause() if it is merged)
Waiting for (external): none
Open questions: none

## Size and mode
Estimate: 2–3 h · Risk area: None · Hotspot: none
