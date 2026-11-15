# avflow — overview (3.0)

What avflow is for, what it does, which skill to use when, and why a developer who already likes Claude Code should
use it. For the details, see `docs/user-guide.md`; for why things are the way they are, `docs/decisions.md`.

---

## 1. The philosophy

avflow is a **team harness around Claude Code**. Claude Code is the agent that writes the code; avflow makes the team's
way of working the default way the agent works — on any project, for every member, on every machine.

It rests on a few beliefs:

1. **The agent is a team member with limited rights, not an admin.** It works only on tickets assigned to the person
   running it, in status *Ready* and not blocked. It writes only private notes, makes only the status moves the team
   allows (Ready → In progress → In review), and never merges. People decide; the agent proposes and does the work.

2. **Rules belong in code, not in prompts.** A prompt can be talked around — by a confused agent or by text injected
   into a ticket. So the rules that matter (private notes only, allowed status moves, allowed fields, no push to
   protected branches, no secrets in commits) are enforced by tools and hooks that simply refuse. Ticket text is data,
   never instructions.

3. **Process proportional to risk, decided from facts.** Every ticket follows one flow. A change gets extra checks only
   when it is actually risky — because the ticket names a risk area, or because the plan or the diff touches the files
   of one. Risk is checked three times (start, plan, review) and can only go up.

4. **avflow knows *that* something is risky; the project knows *what* is risky.** Each project describes its own risk
   areas, owners and checks in `.avflow/project.toml`. avflow ships no project's concepts: generic words in avflow,
   project words in the project.

5. **Deterministic core, judgement at the edges.** Anything that can be computed (rules, path matching, required
   checks) is code with tests. Skills describe only judgement — how to plan, test, review — and call the tools.

6. **Reuse before invention.** The coding workflow comes from proven open-source skill sets (Superpowers or Matt
   Pocock's skills). avflow adds only what a team needs on top: tickets, risk, guardrails, consistency.

7. **Every machine in step.** One install command, team settings shipped with each release, `avflow check` to see
   that everything works, `avflow update` to move everyone forward together.

8. **The customer may be watching.** The ticket system can be shared with the customer, so everything the agent
   writes there is private, and anything for the customer is published by a person.

---

## 2. Features

### Connect — tickets and repository

| Feature | What it does |
| --- | --- |
| **MCP server `avflow-tickets`** (11 tools) | The agent's only way into Redmine: `whoami`, `list_my_ready_tickets`, `get_ticket`, `add_private_note`, `set_fields`, `find_hotspot_conflicts`, `start_ticket`, `assess_plan`, `review_requirements`, `submit_for_review`, `create_bug_draft` |
| **Personal token in the OS keyring** | Each member's own Redmine key, never in a file, log or output |
| **Works with or without Redmine admin** | Uses custom fields (Risk area, Hotspot) when they exist; otherwise reads the *Size and mode* line of the description and private notes |
| **GitLab integration** | Merge request links, changed files, MR notes and approvals through `glab` and the API |
| **Hotspot conflicts** | Warns when another ticket in progress touches the same hotspot file |

### Equip — the agent's way of working

| Feature | What it does |
| --- | --- |
| **One ticket flow** | Start → short plan → (confirm if risky) → implement tests first → MR with green pipeline → required checks → person reviews and merges |
| **Coding workflow** | The team's choice of Superpowers *or* Matt Pocock's skills (never both), installed and kept in step |
| **avflow team skills** | 10 skills for tickets, QA, triage, releases, incidents, docs — see section 3 |
| **Role subagents** | `avflow-planner` (read-only planning), `avflow-implementer` (tests first, small diffs), `avflow-reviewer` (independent review in a fresh context), each with the team's model |
| **Slash commands** | `/avflow:next-ticket` (pick, start and plan my next ticket), `/avflow:check` |
| **`handoff` skill** | Session handoff posted as a private note, so the next session — or the next person — continues cleanly |
| **Project files** (`avflow init`) | `CLAUDE.md` template (with *Test environments and languages*), `docs/CONTEXT.md`, ADR folder, CODEOWNERS, MR template, `.gitattributes`, `.editorconfig`, CI jobs, risk profile with stack presets (.NET, Node, Python, Java, Go) |

### Guard — safety in code

| Feature | What it does |
| --- | --- |
| **Ticket rules** (`tickets/core.py`) | Private notes only; only the allowed status moves; only the allowed fields; refuses tickets not assigned to you, not Ready or blocked; a risk area can be added, never removed |
| **Risk areas** (`.avflow/project.toml`) | Each project lists its risky areas, their paths, owners and checks; `[risk.other]` for "risky, no area yet"; `[risk.default]` as a strict start for new projects |
| **Required checks** | `plan-confirmation`, `independent-review`, `code-owner`, `checklist:<text>` — computed at start, plan and review, recorded in private notes, posted on the MR |
| **CI gate `avflow-risk-check`** | On every MR: reads the profile from the target branch, matches the changed files, verifies the checks (review note, owner approval, ticked checklist); report-only or fail |
| **CODEOWNERS from the profile** | `avflow risk sync` writes the owners block, so checks and code owners never drift |
| **Git guardrails hook** | Blocks push to protected branches, force push, `reset --hard`, `clean -f`, branch force-delete, commits that contain secrets — and, through `gh` / `glab` (including their `api`), merging, approving and deleting repositories, releases, branches or branch protection |
| **Secret scan in CI** | `avflow-secret-scan` (gitleaks) as the server-side backup of the local hook |
| **Plugin integrity** | Checksums of the shipped skills; `avflow check` reports any skill edited by hand |
| **Context monitor** | Warns when a session's context grows too large (answers get less reliable); `avflow usage` shows sessions and subagent calls |

### Keep machines in step

| Command | What it does |
| --- | --- |
| `avflow setup` | Team settings applied; asks only for your own Redmine key (and GitLab login). `--advanced` for personal overrides |
| `avflow check` | Everything that must work, with ✅ / ❌ and how to fix it |
| `avflow update` | Installs the latest release and updates the plugin |
| `avflow config` | Shows the configuration (never a token); `--edit`, `--reset` |
| `avflow uninstall` / `reset-avflow` scripts | Clean removal (macOS and Windows) |

### For the PM and the project

| Command | What it does |
| --- | --- |
| `avflow init` | Adds the team's standard files and the risk profile to a project |
| `avflow risk check` / `files` / `sync` / `suggest` | Validate the profile; which areas and checks apply to given files; regenerate CODEOWNERS; propose paths from profile gaps |
| `avflow report` | Weekly read-only report: ticket flow, risk (high-risk share, areas, found only at review, profile gaps), GitLab MRs |
| `avflow release-notes` | Release notes from the tickets referenced in a commit range, risk areas marked |

---

## 3. The avflow skills — when to use each

You rarely call a skill by name: Claude Code picks it from what you ask. Knowing them helps you ask well.

| Skill | Use it when… | Example request |
| --- | --- | --- |
| `avflow:tickets` | Anything that starts from, reports to or ends in a ticket: find your ready tickets, read one, start it, post the plan, add a note, list required checks, submit for review, draft a bug | "What are my ready tickets?" · "Start #1234" · "Submit #1234 for review" |
| `avflow:workflow` | A ticket has started and work begins, a required check must be satisfied, or you are unsure which design / planning / TDD / debugging / review skill to use | "Implement #1234 following the plan" |
| `avflow:zoom-out` | Before changing code you do not know: legacy code, a big or unfamiliar module, the paths of a risk area, or after two fix attempts failed | "Zoom out on the export module before we plan" |
| `avflow:qa-agent` | QA without a dedicated tester: test cases from acceptance criteria before coding; an independent review that tries to break the change; reproducing a bug into a private bug draft; release test items | "Design test cases for #1234" · "Review this MR independently" |
| `avflow:triage` | A ticket from the customer (or anyone outside the team) must be understood and routed: defect, change request, question or maintenance; what is missing | "Triage customer ticket #987" |
| `avflow:ticket-writer` | Turning a request, a bug reproduction or a planned task into a ticket an agent can do without questions (a person reviews it before Ready) | "Write a ticket for adding CSV export" |
| `avflow:glossary` | A domain term is unclear, new or used with two meanings — keeps `docs/CONTEXT.md` sharp | "What do we mean by *settlement*? Add it to the glossary" |
| `avflow:adr` | A decision is hard to reverse, would surprise a future reader and came from a real trade-off | "Record why we chose SQLite over files" |
| `avflow:release` | Preparing a release candidate or production release: what is in it, release notes, the customer's acceptance checklist, pre-release checks, rollback plan | "Prepare release 1.8 from develop" |
| `avflow:incident` | Software misbehaves in the customer's environment: severity, logs to collect, timeline, hypotheses from evidence, reproduction, fix with a regression test, blameless review | "The customer reports data loss after the update — start an incident" |

Slash commands: **`/avflow:next-ticket`** at the start of a work session (picks your next ticket, starts it, posts the
plan, and stops for your confirmation when the change is risky); **`/avflow:check`** when something seems off.

Project skills: a project can add its own (`.claude/skills/<project>-…/`, for example a hardware review or the logs to
collect); the team skills use them when they exist.

---

## 4. "I just use Claude Code" — why use avflow

avflow **is** Claude Code. Nothing is taken away: same terminal, same model, same freedom to ask anything. avflow adds
what plain Claude Code does not know — your tickets, your team's rules and your project's risks — so you spend less time
on the parts of the job around the code.

**What you stop doing by hand**

- **Copy-pasting tickets.** Ask "start my next ticket": the agent reads it from Redmine — description, notes, blockers,
  attachments — and refuses tickets that are blocked or not yours, before you waste time on them.
- **Ticket admin.** Status moves, the plan, progress notes, the MR link and the handoff are written for you, as private
  notes, in the right place. After the merge, CI moves the ticket to *Ready for test*.
- **Explaining the team's way of working every session.** Planning, tests first, review and handoff are already the
  default; you get the same good habits on day 1 and on a tired Friday.
- **Setting up your machine.** One command; `avflow check` tells you exactly what is wrong; `avflow update` keeps you in
  step with the team.

**What protects you**

- **The customer can read Redmine.** With plain Claude Code and a Redmine key, one wrong public note is visible to the
  customer. With avflow it cannot happen: the tools only write private notes. That is enforced in code, not trusted to
  the prompt.
- **Mistakes that hurt.** Push to `develop`, force push, `reset --hard`, a token in a commit, merging or approving with
  `gh` / `glab` — blocked before they
  happen, with a clear message. A ticket that says "ignore your rules" stays data.
- **Risky changes.** When your change touches code the project marked risky, avflow tells you *before* you write it
  (plan confirmation) and lists exactly what the MR needs (review, owner, checklist). No surprise rejection at review,
  no "nobody told me this file was sensitive".
- **Long sessions.** The context monitor warns before answers start to degrade.

**What it costs you**

- A short plan note on every ticket (the agent writes it; you read it).
- A stop for your confirmation on risky changes only — most tickets go straight through.
- One install, then `avflow update` when the team releases.

**Honest limits**

- It works with Redmine, GitLab and Claude Code only (today).
- It does not judge your code for you: review and merge stay with people.
- If something does not fit your work, say so — team settings and skills change with each release; that is the point of
  having one shared setup instead of everyone's private prompts.

### "But I already use Matt Pocock's skills / Superpowers — I get the same output"

**For the code, that is true — and you keep them.** avflow does not try to write better code than a good skill set.
Its coding workflow *is* one of the two: **Superpowers** (the team default) or **Matt Pocock's skills** (pinned to a
tested version), chosen in the team settings or personally with `avflow setup --advanced`. It is not "your skills or
avflow"; avflow is the layer around your skills.

**The difference: skills are advice, avflow is enforcement.** A skill is text the model reads and *usually* follows —
it can skip it, misread it, or be talked out of it by a ticket that says "ignore your rules". What avflow adds works
outside the model:

| | Claude Code + your skill set | + avflow |
|---|---|---|
| A public note on a Redmine the customer reads | Possible: one mistake and the customer sees it | Impossible: the tool only writes private notes |
| Push to `develop`, force push, `reset --hard` | Allowed unless you catch it | Blocked by a hook, whatever the prompt says |
| Merging or approving an MR with `glab` / `gh` (as you) | Possible — its approval counts as yours | Blocked by the same hook |
| A token in a commit | Possible | Blocked before the commit, and again in CI |
| Working on a blocked ticket, or someone else's | Possible | Refused |
| Changing risky code (payments, machine control, …) | You must know it is risky and remember the extra steps | Detected from the ticket, the plan and the diff; checks listed and verified by CI on the MR |
| Ticket status, plan, MR link, handoff | By hand, or by asking each time | Part of the flow, in the right place |

Your skill set makes **your session** good. It does not know your tickets, your customer or which files in this
project are dangerous, and it cannot stop anything.

**"Same output" holds for one person's code, not for what the team needs besides it:**

- **Facts the PM can see** — what is in progress, what was planned, which checks a change needed, what the risk profile
  missed (`avflow report`). Private prompts leave no such trace.
- **Checks a reviewer can trust** — "independent review done, owner approved, checklist ticked" is verified by CI, not
  claimed.
- **Ten machines that behave the same** — same skill versions, rules and models, one `avflow check`.
- **Someone else can continue** — plans and handoffs live on the ticket, not in one terminal's history.

**Where they are right:** for experiments, a spike without a ticket, or a repository that is not a team project, plain
Claude Code with a good skill set is enough. avflow earns its place where there are tickets, a customer, risky code and
more than one developer.

#### If they use Matt Pocock's skills

- Choose the *Matt Pocock's skills* workflow (`avflow setup --advanced`) and you keep `grill-with-docs`, `tdd`,
  `implement`, `diagnosing-bugs`, `code-review`, `prototype`, `research`, `codebase-design`, `pr`, `retro`, `handoff`
  — the same skills, at a version the team tested.
- Some of his skills publish to an issue tracker (`to-spec`, `to-tickets`, `triage`, `wayfinder`, `implement-spec`,
  `setup-matt-pocock-skills`), and `domain-modeling` writes `GLOSSARY.md`. On a Redmine the customer shares, those are
  left out, and avflow's team versions take their place (`triage`, `glossary`, `adr`): same method, but nothing the
  customer can read, and the team's `docs/CONTEXT.md`. Credited and adapted (MIT).
- His planning is "write the plan" — avflow sends it through `assess_plan`, which posts it privately on the ticket and
  decides from the planned files whether the change is risky and needs your confirmation.

> "Keep Pocock's skills — avflow installs them for you. What it adds is what a skill cannot do: it knows your tickets,
> enforces the rules a prompt can be talked out of, and proves risky changes got their checks."

#### If they use Superpowers

- Superpowers is **the team's default workflow**: `brainstorming`, `writing-plans`, `executing-plans`,
  `subagent-driven-development`, `test-driven-development`, `systematic-debugging` — all used as they are. avflow's
  `workflow` skill only says *where* each fits in the ticket flow.
- `writing-plans` writes a good plan — avflow passes it to `assess_plan`, so the plan lands on the ticket as a private
  note (visible to the PM and the next person) and its files are checked against the project's risk areas *before* any
  code. Superpowers alone has no idea that `src/payments/` needs an owner's approval.
- At the end of a branch, Superpowers may offer to merge or push for you. With avflow, pushing a feature branch is fine,
  but merging into or pushing to `develop` / `main` is blocked: the merge goes through an MR, a green pipeline and a
  person — which is what the team wants anyway.
- Superpowers' code review happens in your session and leaves no trace on the MR. avflow's `independent-review` runs
  the review in a fresh subagent and posts the verdict on the MR, where the CI gate can verify it.

> "Keep Superpowers — it is the team's default, avflow installs and updates it. What avflow adds is the ticket, the
> rules and the proof: your plan reaches the ticket, risky files are caught before you code, and the review result is
> on the MR for everyone to see."

**In one sentence:** keep using Claude Code exactly as you like — avflow just makes it know your tickets, follow the
team's rules, and stop you before the mistakes that cost the most.
