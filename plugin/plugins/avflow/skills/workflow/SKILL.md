---
name: workflow
description: Use whenever a ticket's mode (DIRECT, PLAN, FULL, SPIKE) has been confirmed and work is about to start, or when you are unsure which design, planning, implementation, testing, debugging or review skill to use. Defines what each mode requires and maps every requirement to the installed workflow — Superpowers or Matt Pocock's skills.
---

# Team workflow

Each team member uses **one** coding workflow, chosen in `avflow setup`:

- **Superpowers** — skills such as `brainstorming`, `writing-plans`, `executing-plans`.
- **Matt Pocock's skills** — skills such as `grill-with-docs`, `implement`, `tdd`, `code-review`.

Look at the skills available to you to know which one is installed. Never mix the two, and never install the other one.

The **requirements** below are the same for everyone; only the skill that meets them differs.

## What each mode requires

| Mode | Requirements, in order |
|---|---|
| **DIRECT** | Implement with tests (test first when practical) → open the merge request |
| **PLAN** | Short design check → **plan** (steps and files, as a private note) → implement in batches, **stop for the person after each batch** → tests first → merge request |
| **FULL** | Design clarified with the person → plan as a private note → implement with tests first → **independent two-stage review** (spec, then code quality) by the `qa-agent` skill → person review (code owner) → merge request |
| **SPIKE** | Time-boxed investigation or prototype → findings as a private note → **no production code** |

For legacy code without tests, or before touching a sensitive path, run `zoom-out` first.

## Who does each step — the role subagents

`avflow setup` installs three subagents, each running on the model the member chose for that kind of work
(`[models]` in the avflow configuration; for example Opus to plan and review, Sonnet to implement).

| Step | Delegate to | Notes |
|---|---|---|
| Design and plan (PLAN, FULL) | **`avflow-planner`** | Read-only. Post its plan with `add_private_note` and wait for the person to confirm |
| Implementation of the confirmed plan (PLAN, FULL) | **`avflow-implementer`** | One batch per call in PLAN mode; stop for the person after each batch |
| Two-stage review (FULL, or when the person asks) | **`avflow-reviewer`** | Fresh context; never the subagent that implemented |

DIRECT tickets and SPIKEs can be done in the main session. Tickets, the merge request and anything the person must
confirm stay in the **main session** — subagents return their result to it. If a role subagent is missing, say so and
suggest `avflow check`; do not silently skip the step.

## Which skill meets each requirement

| Requirement | Superpowers | Matt Pocock's skills |
|---|---|---|
| Clarify the design | `brainstorming` | `grill-with-docs` |
| Write the plan | `writing-plans`, then post it with `add_private_note` | Write it yourself (steps, files, tests) and post it with `add_private_note` — **do not** use skills that publish to an issue tracker |
| Implement in batches with checkpoints | `executing-plans` | `implement`, stopping after each batch |
| Implement a FULL ticket | `subagent-driven-development` | `implement` |
| Tests first | `test-driven-development` | `tdd` |
| Debug a failure | `systematic-debugging` | `diagnosing-bugs` |
| Independent review (FULL) | `qa-agent` section E | `qa-agent` section E (it may use `code-review`) |
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
- Plans, findings and handoffs are **private notes** on the ticket.
- Git safety guardrails may block some commands (push to protected branches, force push, `reset --hard`, …). If a command is blocked, do not try to work around it — tell the person.
