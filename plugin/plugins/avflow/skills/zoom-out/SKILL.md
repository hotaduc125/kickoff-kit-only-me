---
name: zoom-out
description: Use before changing code you do not know well — legacy code, a large or unfamiliar module, any sensitive path, or after two fix attempts did not work. Step back and map the surrounding code (entry points, callers, data flow, threads, tests, risks) before planning or editing. Read-only; produces a short map for the ticket.
---

# Zoom out

Before you change unfamiliar code, understand where it sits. Do **not** edit anything during this step.

## When
- Before planning a ticket that touches code you have not read in this session.
- Before changing a **sensitive path** of the project (listed in its CLAUDE.md / CODEOWNERS).
- When a bug fix has failed **twice** — stop guessing and zoom out.
- Before any refactoring.

Time-box it: about 15–30 minutes of reading. If it takes longer, the ticket probably needs a **spike** first.

## Steps
1. **Entry points** — where does the behaviour start (UI action, timer, event, command, API call)? Name the files and methods.
2. **Callers and callees** — search for every caller of the code you will change; list what it calls in turn. Note anything reached through events, reflection or dependency injection (easy to miss with plain search).
3. **Data and state** — which data does it read and write (models, files, configuration, database, shared static state)? Who else writes the same data?
4. **Threads and timing** — which thread does it run on (UI, background, machine / control loop)? Is it on a time-critical path? Are there locks, async calls or polling loops?
5. **Tests** — which tests cover it today? If none, which characterisation tests would capture the current behaviour before you change it?
6. **Risks** — sensitive paths, hotspots shared with other open tickets, behaviour that must stay identical, places where a mistake would only show on real hardware.

## Output
Write the map as a **private note** on the ticket (tickets skill → `add_private_note`) before planning:

```
Zoom-out map
Entry points: …
Callers / callees: …
Data and state: …
Threads / timing: …
Existing tests: … · Characterisation tests needed: …
Risks: …
Proposed approach (1–3 lines): …
```

Then write the plan and call `assess_plan` with every file it names (the `tickets` skill). If the map shows the work is riskier than the ticket says, add the risk area with `set_fields` and a reason.
