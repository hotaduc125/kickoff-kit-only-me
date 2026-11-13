---
name: sandbox-machine-review
description: Use for any avflow-sandbox ticket in the Machine control risk area, or any change to src/sandbox/machine.py — designing its test cases or reviewing it. The project's own rules on top of avflow's qa-agent skill (a sample of a project skill, for the avflow test plan).
---

# avflow-sandbox — machine-control changes

`src/sandbox/machine.py` stands in for code that drives a real machine. Use this together with avflow's `qa-agent`.

## Test cases

Add a group **Machine safety** to the test cases, always with these three cases, whatever the ticket says:

- **MS1 — door open:** a move with the door open is refused (`RuntimeError`), and the position does not change.
- **MS2 — speed limit:** a move above `MAX_SPEED_MM_S` is refused (`ValueError`).
- **MS3 — safe position:** `stop()` still returns to `SAFE_POSITION_MM`.

Level: unit. There is no test hardware for the sandbox; say so instead of inventing one.

## Review

- A change to `MAX_SPEED_MM_S`, the door check or `stop()` that the ticket does not ask for is **Blocking**.
- MS1–MS3 must exist as tests and pass.
