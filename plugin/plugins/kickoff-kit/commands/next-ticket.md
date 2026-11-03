---
description: Pick my next ready ticket and prepare it (read, check blockers, propose a mode) — stops before coding.
---

Use the `tickets` skill.

1. Call `list_my_ready_tickets` and pick the highest-priority ticket (or ticket $ARGUMENTS if given).
2. Call `get_ticket`. If the Definition of Ready is not met or a blocker is unfinished, add a private note explaining why and stop.
3. Run the `choose-mode` skill: set Mode (and Machine-side / Hotspot when they apply), add a private note with the proposal.
4. Call `find_hotspot_conflicts` and report any conflict.
5. Stop and ask me to confirm the mode. Do not call `start_ticket` until I confirm.
