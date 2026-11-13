---
name: mateo-machine-review
description: Use for any Mateo ticket in the Machine control risk area, or any change under source/Zmotion, source/MachineModes or source/NullingModes — designing its test cases, reviewing it, reproducing a machine bug, or preparing its release checks. Adds Mateo's simulator / test bench rules to avflow's qa-agent and release skills.
---

# Mateo — machine-control changes

Mateo drives a real machine at the customer (WKKM). A mistake in machine control can stop production or damage a
panel, so these changes are verified on two levels: the **simulator** (automated, everywhere) and the **test bench**
(the real machine at Enclave, by a person). Use this together with avflow's `qa-agent` and `release` skills.

## Test design (with `qa-agent` part A)

Add a group **Machine-control cases** to the test cases. For each case, say where it is verified:

| Level | Use for |
|---|---|
| unit | Pure logic: calculations, state transitions, command building |
| simulator | Sequences, timing, alarms, nulling with **camera replay** of recorded targets |
| UI | Operator screens, both languages (zh / en) |
| test bench | Motion, speed limits, door and safety interlocks, anything the simulator does not model — by someone other than the author |

A case that only the test bench can verify is listed as such; never mark it as covered by an automated test.

## Review (with `qa-agent` parts B and E)

- The safety checks (speed limits, door / interlock checks, safe position) must be unchanged unless the ticket says
  otherwise — a weakened safety check is **Blocking**.
- The simulator regression must pass in the pipeline.
- The checklist item *Tested on the test bench by someone other than the author* stays unticked until that person
  has done it; the agent never ticks it.
- Flag anything that can only be verified on the customer's machine.

## Bug reproduction (with `qa-agent` part C)

Reproduce on the simulator with camera replay of the customer's recorded data when possible (evidence: `mateo-logs`).
If it does not reproduce there, list what to check on the test bench.

## Release (with the `release` skill)

- Machine-control tickets come first in the acceptance checklist, with the most precise checks for WKKM's engineer.
- Pre-release: simulator regression green on the release commit; every machine-control change tested on the test
  bench by someone other than the author; zh / en texts reviewed.
- TODO: Mateo's other release measures (mutation score, AI evaluation scores when AI features changed) — keep or drop.
