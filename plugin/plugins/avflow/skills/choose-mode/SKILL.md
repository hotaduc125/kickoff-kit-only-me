---
name: choose-mode
description: Use at the start of every ticket, before any design, plan or code, to choose the working mode (DIRECT, PLAN, FULL or SPIKE) by risk and size, and again whenever the work reaches a sensitive path or grows beyond its estimate.
---

# Choose the working mode

Pick how much process a ticket needs. **Risk beats size**: a one-line change on a sensitive path is FULL; a large screen that never touches the machine is PLAN.

## Modes

| Mode | In short |
|---|---|
| DIRECT | No design step, no plan. Implement with tests, then the merge request. |
| PLAN | Short plan as a private note, then work in batches with a stop for the person after each. |
| FULL | Design with the person, plan, tests first, independent two-stage review (qa-agent), code-owner review. |
| SPIKE | Time-boxed investigation that answers a question. No production code; findings as a private note. |

What each mode requires in detail, and which skill to use with Superpowers or with Matt Pocock's skills: see the `workflow` skill.

## Step 1 — Read the ticket

Read the ticket with `get_ticket` (tickets skill): requirement, acceptance criteria, estimate, target version, fields, `blocked_by`. If the Definition of Ready is not met, or an unfinished ticket blocks it, stop and say so with `add_private_note`.

## Step 2 — Apply the hard rules (no judgement)

Check these in order and stop at the first match:

1. The ticket has Machine-side = yes, **or** the files you expect to change match a **sensitive path** of the project (listed in its CLAUDE.md / `CODEOWNERS`) → **FULL**.
2. The way to solve the task is unknown (choice between options, missing facts about the machine) → **SPIKE**.
3. Expected effort ≤ 4 hours **and** ≤ 3 files **and** no sensitive path → **DIRECT**.
4. Expected effort > 2 days **or** several components → do not start. Propose a split into smaller tickets in a private note; a person creates them, then run this skill again for each.

## Step 3 — Otherwise, propose PLAN or FULL

List the files and components you expect to change and why. Choose FULL if any of these is true: the change affects what the machine does (motion, IO, punching, alignment, installation), the code has no tests and is hard to characterise, or a mistake would only show up on a real machine. Otherwise choose PLAN.

## Step 4 — Ask for confirmation

Add one private note with `add_private_note`:

```
Proposed mode: <MODE>
Reason: <one or two sentences>
Expected files / components: <list>
Rule applied: <hard rule number, or "judgement">
```

Set **Mode** (and Machine-side / Hotspot when they apply) with `set_fields`, and **wait for the assignee to confirm** before calling `start_ticket`. If the assignee changes the mode, follow theirs.

## Step 5 — While working: escalate, never de-escalate

Stop and raise the mode (`set_fields` + `add_private_note`) when:

- you are about to change a file on a sensitive path that was not expected, or
- the work clearly exceeds the estimate or touches more components than planned.

Never lower the mode during a ticket. If a lower mode would have been enough, note it in the handoff so the rules can be calibrated.

## Notes

- Tests and human review are required in every mode, including DIRECT.
- TDD exceptions: legacy code without tests → characterisation tests first; XAML / UI → verify by review and running the app.
- Record the mode used and any usage-limit hits in the handoff note; the team uses this to calibrate the 4-hour and 2-day thresholds after the pilot.
