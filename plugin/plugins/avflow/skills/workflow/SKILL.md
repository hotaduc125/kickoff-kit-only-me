---
name: workflow
description: Use whenever a ticket has been started and work is about to begin, when a required check (plan-confirmation, independent-review, code-owner, checklist) must be satisfied, or when you are unsure which design, planning, implementation, testing, debugging or review skill to use. Describes the one ticket flow and maps every step to the installed workflow — Superpowers or Matt Pocock's skills.
---

# Team workflow

Each team member uses **one** coding workflow, chosen in `avflow setup`:

- **Superpowers** — skills such as `brainstorming`, `writing-plans`, `executing-plans`.
- **Matt Pocock's skills** — skills such as `grill-with-docs`, `implement`, `tdd`, `code-review`.

Look at the skills available to you to know which one is installed. Never mix the two, and never install the other one.

The **requirements** below are the same for everyone; only the skill that meets them differs.

## One flow for every ticket

There are no modes. Every ticket follows the same steps (the `tickets` skill has the tool calls); the amount of process
comes from the **required checks** that `start_ticket`, `assess_plan` and `review_requirements` return:

1. Start → short **plan** (approach, files, tests) → `assess_plan`.
2. If the checks include `plan-confirmation` → **stop** until the person confirms the plan.
3. Implement, **tests first** → merge request → green pipeline.
4. `review_requirements` → do the checks that are yours → `submit_for_review`.

A spike stops after the plan: findings as a private note, **no production code**.

| Check | How it is satisfied |
|---|---|
| `plan-confirmation` | Stop after `assess_plan`; the assignee confirms the plan in the session before any code |
| `independent-review` | `qa-agent` section E: two-stage review by the `avflow-reviewer` subagent in a fresh context; post the result on the MR |
| `code-owner` | One of the area's owners approves the MR — a person; list it for them, never approve yourself |
| `checklist:<text>` | A person ticks that item in the MR description — never tick it yourself |

**Always required, whatever the risk:** tests for each acceptance criterion, a green pipeline, a person's review and
merge, a handoff note.

For legacy code without tests, or before touching a risk area's paths, run `zoom-out` first.

## Who does each step — the role subagents

`avflow setup` installs three subagents, each running on the model the member chose for that kind of work
(`[models]` in the avflow configuration; for example Opus to plan and review, Sonnet to implement).

| Step | Delegate to | Notes |
|---|---|---|
| Design and plan (larger tickets, or any ticket in a risk area) | **`avflow-planner`** | Read-only. Pass its plan and files to `assess_plan` |
| Implementation of the plan | **`avflow-implementer`** | After the confirmation when `plan-confirmation` is required |
| Two-stage review (`independent-review`, or when the person asks) | **`avflow-reviewer`** | Fresh context; never the subagent that implemented |

Small changes and spikes can be done in the main session. Tickets, the merge request and anything the person must
confirm stay in the **main session** — subagents return their result to it. If a role subagent is missing, say so and
suggest `avflow check`; do not silently skip the step.

## Which skill meets each requirement

| Requirement | Superpowers | Matt Pocock's skills |
|---|---|---|
| Clarify the design | `brainstorming` | `grill-with-docs` |
| Write the plan | `writing-plans`, then pass it to `assess_plan` | Write it yourself (steps, files, tests) and pass it to `assess_plan` — **do not** use skills that publish to an issue tracker |
| Implement in batches with checkpoints | `executing-plans` | `implement`, stopping after each batch |
| Implement a larger or high-risk change | `subagent-driven-development` | `implement` |
| Tests first | `test-driven-development` | `tdd` |
| Debug a failure | `systematic-debugging` | `diagnosing-bugs` |
| Independent review (`independent-review`) | `qa-agent` section E | `qa-agent` section E (it may use `code-review`) |
| Spike / prototype | investigate and note findings | `prototype`, `research` |
| Module design | — | `codebase-design`, `improve-codebase-architecture` |
| Merge request description | team MR template | `pr`, following the team MR template |
| Handoff | `handoff` | `handoff` |
| Look back after a session | — | `retro` |
| Classify an incoming customer ticket | `triage` (team) | `triage` (team — not Matt Pocock's, which publishes to the tracker) |
| Field incident | `incident` (team) | `incident` (team) |
| Prepare a release | `release` (team) | `release` (team) |
| Domain terms / decisions | `glossary`, `adr` (team) | `glossary`, `adr` (team — instead of `domain-modeling`, which writes GLOSSARY.md) |

## Rules for every workflow

- **A merge request goes to review only with a green pipeline** (see the `tickets` skill, step 7). CI is the judge: never weaken, skip or disable a test or a CI check to make a pipeline pass.
- **Keep the orchestrator's context small.** Delegate reading large areas of code, implementation and review to the role subagents; they start with a fresh context. When the context monitor reports the warning threshold, plan a handoff; past the limit, stop starting new work, write the handoff as a private note and ask the person to start a new session.

- Tickets are read and written **only** through the `tickets` skill (avflow-tickets MCP server). No other skill may create, publish or comment on tickets.
- Plans go through `assess_plan`; findings and handoffs are **private notes** on the ticket.
- Git safety guardrails may block some commands (push to protected branches, force push, `reset --hard`, …). If a command is blocked, do not try to work around it — tell the person.
