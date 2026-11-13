---
description: Pick my next ready ticket, start it and assess the plan — stops before coding when the plan needs my confirmation.
---

Use the `tickets` skill.

1. Call `list_my_ready_tickets` and pick the highest-priority ticket (or ticket $ARGUMENTS if given).
2. Call `get_ticket`. If the Definition of Ready is not met or a blocker is unfinished, add a private note explaining why and stop.
3. Call `find_hotspot_conflicts` and report any conflict; if there is one, stop and ask me before starting.
4. Call `start_ticket` and tell me the risk areas and required checks it returns.
5. Write a short plan (approach, files, tests) and call `assess_plan` with it and every file it names.
6. Show me the plan, the required checks and the decision. Stop before writing code — always, even on *continue*, so I
   can look at the plan first.
