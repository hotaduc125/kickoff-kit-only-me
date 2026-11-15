# avflow user guide (macOS & Windows)

For avflow **3.0.0**. Source of truth for the user guide from now on (it was first written as a Claude Doc); update it in
the same change as any behaviour it describes.

## What avflow is

avflow sets up the team's AI coding workflow with one command and keeps it in step with the latest release.

After installing, your machine has:

- **The `avflow-tickets` MCP server**: 9 tools for the agent to work with Redmine tickets, with the team rules built into the code (notes are always private; the agent may only start a ticket and submit it for review).
- **The avflow plugin**: the team skills — `tickets`, `workflow`, `qa-agent`, `ticket-writer`, `zoom-out`, `triage`, `incident`, `release`, `glossary`, `adr` — and two shortcuts, `/avflow:next-ticket` and `/avflow:check`.
- **The coding workflow** of the team: Superpowers, or a curated set of Matt Pocock's skills. One or the other, never both.
- **Three role subagents** — planner, implementer, reviewer — each on the model chosen for that kind of work.
- **Git guardrails**: dangerous git commands, and commits that contain secrets, are blocked before the agent can run them.
- Your GitLab login, and the `handoff` skill.

**Your Redmine token** is stored in the operating system's secure store (Keychain on macOS, Credential Manager on Windows). It is never written to a file and never passes through the AI conversation.

**Where it works:** Claude Code in a terminal, and the Code tab of Claude Desktop. Installing and updating always happen in a terminal.

## Before you install

You need six things, most of them once; on Windows, run every command in **PowerShell**.

| You need | macOS | Windows | Check |
| --- | --- | --- | --- |
| Git | `brew install git` | `winget install Git.Git` | `git --version` |
| Claude Code CLI | Claude Code install guide | Claude Code install guide | `claude --version` |
| GitHub CLI, signed in | `brew install gh` | `winget install GitHub.cli` | `gh auth login`, then `gh auth setup-git` |
| GitLab CLI | `brew install glab` | `winget install GLab.GLab` | `glab --version` |
| Read access to `avflow-marketplace` | ask the PM | ask the PM | `git ls-remote https://github.com/alvin-enc/avflow-marketplace.git` works without a password prompt |
| Your own token | Redmine: **My account → API access key** | same as macOS | — |

**The GitLab token** needs the `api` and `write_repository` scopes (create it under **Preferences → Access tokens** on Enclave's GitLab). Setup opens `glab auth login` if you are not signed in yet.

No `uv`? No problem: the install script installs it.

## First install

Download the release files into one folder, run the install script, enter your token; about 10 minutes.

**1. Download the release files** (replace `<version>` with the version the PM announces, for example `3.0.0`):

```bash
gh release download v<version> --repo alvin-enc/avflow-marketplace
```

You get `avflow-<version>-py3-none-any.whl`, `bootstrap.sh`, `bootstrap.ps1` and `INSTALL.md`.

**2. Run the install script** in that folder:

| macOS (Terminal) | Windows (PowerShell) |
| --- | --- |
| `chmod +x bootstrap.sh` | — |
| `./bootstrap.sh ./avflow-<version>-py3-none-any.whl` | `powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 .\avflow-<version>-py3-none-any.whl` |

**3. Enter what is yours.** Setup first shows the **team settings** that come with the release — Redmine and GitLab addresses, statuses, coding workflow, guardrails, models, context monitor — then asks only:

| Question | Answer |
| --- | --- |
| Redmine API key | **your own** key (Redmine → My account → API access key); nothing shows while you type, and setup checks it at once |
| GitLab login | only if you are not signed in yet: follow `glab auth login` (token with `api` and `write_repository`) |

If setup reports that the team's statuses are missing in Redmine, tell the PM.

**4. Open a new terminal window** (so the `avflow` command is on your PATH), then run `avflow check`: every line should be ✅ (➖ lines are only information).

**5. Start a new Claude Code session** and type `/mcp`: you should see `avflow-tickets` with 11 tools.

The coding workflow, models and thresholds are **team settings**: everyone works the same way unless the PM agrees otherwise. `avflow config` shows them.

## Redmine without admin rights

avflow works best when an admin has added the custom fields (Risk area, Hotspot) and the team's statuses. Without them, avflow still works on a standard Redmine:

| What | With an admin's setup | Without |
| --- | --- | --- |
| Statuses | Ready · In progress · In review · Ready for test | The statuses Redmine already has, mapped in the team settings — for Enclave: Ready → **New** · In progress → **In Progress** · In review → **In Code Review** · Ready for test → **Ready for testing** |
| Risk area, Hotspot | Custom fields (Risk area: a list field) | The **Size and mode** line at the end of the ticket description, written by the person |
| A risk area the agent adds | — (the agent never writes the field) | A private note starting with `[avflow] risk-area=…`, with the agent's reason |

avflow uses the custom fields whenever they exist, so nothing changes on the tickets when an admin adds them later — just run `avflow setup` again.

Two things still matter:

- **Private notes must stay private.** Whether the customer can see private notes is a role permission that only an admin sets. Check it with a customer test account before any real work.
- **Only private `[avflow]` notes count.** A public note with the same text — which anyone, including the customer, could write — is ignored.

`avflow init` writes the team's status names into the CI job, so no CI variables are needed for them; `avflow config` shows the mapping in use.

## Daily use: working a ticket

The agent does most of the work, but three decisions are always yours: **confirming the plan** when a risky change needs it, **reviewing and merging**, and **closing the ticket**. There are no modes to choose: every ticket follows the same flow, and the extra checks come from the ticket's **risk area** and the **files** the change touches (see *Risk areas* below).

Open a terminal in the project repository (latest `develop`), run `claude`, then:

1. **Type `/avflow:next-ticket`.** The agent takes the highest-priority Ready ticket assigned to you, reads it, checks for blocking tickets, moves it to **In progress** and tells you the risk areas and the **required checks**. For a specific ticket: `/avflow:next-ticket 1234`.
2. **The agent writes a short plan** (approach, files, tests) — for every ticket, even a one-line change — and posts it as a private note together with the risk check (`assess_plan`). If the plan names files in a risk area, checks are added.
3. **Confirm the plan** when the agent says it must stop (the `plan-confirmation` check), for example *"Plan OK, go ahead"*. `/avflow:next-ticket` always stops here so you can look at the plan.
4. **The agent implements** with the team's workflow (the `workflow` skill guides each step): the planner subagent plans larger or risky work, the implementer writes the tests first and the code.
5. **The agent opens the merge request** from branch `feature/<id>-<name>`, with `Refs #<id>` in the title, and waits for its first pipeline — fixing the cause until it is green, never weakening a test. Then it lists the **final required checks** from the files the branch really changed (`review_requirements`), posts them on the MR and the ticket, writes the checklist items into an avflow section of the MR description, does its own checks — for `independent-review`, the reviewer subagent's two-stage review (spec, then code quality), posted as an MR note — and only then moves the ticket to **In review**. Owner approvals and checklist items are for people; the agent never ticks them.
6. **A person reviews and merges**, after the required checks are done. The CI job **`avflow-risk-check`** shows on every merge request which checks are done and which are missing (see *The CI gate* below). Code owners: after approving, **re-run that job** — an approval does not start a pipeline. The agent never merges, and cannot push to `develop` or `main`. After the merge, the project's CI job moves the ticket to **Ready for test** with a private note linking the commit and the pipeline — or, in projects without that job, a person does it.
7. **At the end of the session**, ask the agent for a **handoff** (what was done, what is left, how to verify) as a private note.
8. **After testing or acceptance**, a person moves the ticket to **Resolved**, then **Closed**.

Every note the agent writes on a ticket is a **private note**; the customer cannot see it. If the agent refuses to start (the ticket is not assigned to you, is blocked, is not Ready, or the project's `.avflow/project.toml` has errors), read the reason it gives: that is a team rule, not a bug. You can always ask for more care — *"Treat this as Other high risk"* — the agent adds the risk area with a reason. Only a person can remove one, by editing the ticket.

## Risk areas

A change is **high risk** when its ticket names a **risk area**, or when its plan or its diff touches the paths of a
risk area. Each project lists its areas in **`.avflow/project.toml`** (reviewed by merge request like any code):

```toml
[[risk.area]]
name   = "Payments"
paths  = ["src/billing/**", "src/payments/**"]
owners = ["@lead"]
checks = ["plan-confirmation", "independent-review", "code-owner",
          "checklist:Tested on the staging system by someone other than the author"]

[risk.other]                 # the ticket's "Other high risk"
checks = ["plan-confirmation", "independent-review"]

[risk.default]               # optional: every change outside all areas, until a date (new projects)
checks = ["plan-confirmation", "independent-review"]
until  = "2026-12-31"
```

| Check | What it requires |
| --- | --- |
| `plan-confirmation` | The agent stops after the plan until you confirm it |
| `independent-review` | Two-stage review by the reviewer subagent in a fresh context, result on the MR |
| `code-owner` | One of the area's `owners` approves the MR |
| `checklist:<text>` | A person ticks that item in the MR |

Risk is checked three times — the ticket's area when it starts, the planned files, the changed files — and the list
**only grows**. Files of a high-risk ticket that match no area are reported as **profile gaps**: add them to the profile
when they belong. Paths use `*` (within a folder) and `**` (any depth), relative to the repository root; an area can
have no paths yet and still be picked on tickets.

- `avflow risk check` — validates the profile and lists its areas; warns when CODEOWNERS or the CI copy is out of date,
  or when a newer stack preset adds paths.
- `avflow risk files <paths…> [--area "<name>"]` — shows which areas and checks apply, before you merge a profile change.
- `avflow risk sync` — regenerates the avflow block of CODEOWNERS from the areas' `owners` (lines outside the block are
  kept) and refreshes `ci/avflow_risk.py`. Commit the result in a merge request.
- `avflow risk suggest [--days 30]` — read-only: collects the profile gaps of recently reviewed tickets and proposes
  paths per area. A person decides and changes the profile by merge request.

### The CI gate

`avflow init` adds the job **`avflow-risk-check`** to every merge request pipeline. It works out the required checks
from facts the merge request cannot change — the profile **on the target branch**, the changed files, and the ticket in
the title (its risk area; the checks recorded at start and plan, when the Redmine CI account may view private notes) —
and verifies each one:

| Check | Done when |
| --- | --- |
| `independent-review` | An MR note starting `### avflow — independent review` contains `Verdict: approve` |
| `code-owner` | One of the area's owners (a user, or a member of an owner group) approved the MR |
| `checklist:<text>` | The item is ticked in the avflow section of the MR description |
| `plan-confirmation` | Happens in the session; listed, not checkable in CI |

`[ci] gate = "report"` (the default during the pilot) only lists what is missing; `gate = "fail"` fails the job, and
with *Pipelines must succeed* the merge is blocked. The job reads approvals, notes and the description through the
GitLab API with **`AVFLOW_GITLAB_TOKEN`** (below); without it, those checks show as not verifiable. Works on GitLab Free
and Premium; on Premium you can also turn on *Require approval from code owners*.

Limits to know: the review note and the ticks cannot prove who wrote them (the human reviewer still looks), and a profile
change in a merge request applies only after it is merged.

## Writing tickets avflow can work with

The agent cannot ask questions the way a person does, so a ticket must hold everything it needs. Write team tickets in the team structure — Context, Scope (in and **out**), Acceptance criteria, Constraints, Technical notes, Test approach, Dependencies, Size and mode (estimate, risk area, hotspot) — or ask the agent to draft one: *"Use the ticket-writer skill to draft a ticket for: …"*. The agent only drafts; you create or edit the ticket and move it to Ready.

**Keep the last line machine-readable**, because avflow reads it when Redmine has no custom fields:

```text
Estimate: 1–2 h · Risk area: <area>|Other high risk|None · Hotspot: <file or area>|none
```

The risk area is a name from the project's `.avflow/project.toml` (several: separate them with commas). An investigation
without production code is a **spike**: use the *Spike* tracker, or add `Type: spike` to the line. On older
tickets, a proposed mode and a 2.x *Machine-side* field or line are ignored: set the **Risk area** instead.

For a **hard** dependency (the work cannot start), add the Redmine relation **Blocked by**; avflow refuses to start the ticket until the blocking one is done. For a soft one, use **Related to**.

## Tickets from customers

Customers write short tickets that mix defects, questions and new requests. The agent never works on them directly: it turns them into a **work ticket** that a person approves.

1. Ask: *"Triage ticket #<id>. Then use the ticket-writer skill to draft the work ticket for it."*
2. The agent classifies the ticket (`triage`) — **defect** with severity S1–S3, **change request**, **question** or **maintenance** — checks the code, tries to reproduce, and posts its recommendation as a private note. It waits for you.
3. You confirm the category.
4. The agent drafts the work ticket (`ticket-writer`), with **TODO before Ready** wherever it cannot know:
    - a **defect** becomes a **private bug draft** in status New, linked to the customer ticket;
    - for a **change request** or **maintenance**, the agent posts the draft as a private note and **you create the ticket** — change requests need an estimate and the customer's approval before any work.
5. You review **scope and acceptance criteria**, fill the TODOs and the *Size and mode* line, set assignee and version, and move the work ticket to **Ready**.
6. You answer the customer in their ticket. The agent never writes anything the customer can read.

Watch for new requests presented as defects (*"this screen should also show …"*): they are change requests.

## Check, update, switch workflow

These commands are the same on macOS and Windows.

| Task | Command | When |
| --- | --- | --- |
| Check the installation | `avflow check` (in Claude Code: `/avflow:check`) | When something looks wrong, and after every update |
| See whether a new version exists | `avflow update --check` | Any time; `check` also tells you |
| Update (also brings new team settings) | `avflow update` | When the PM announces a new release |
| Switch workflow for yourself (Superpowers ↔ Matt Pocock) | `avflow setup --advanced`, choose the other workflow | Only when the PM agrees |

**`avflow update`** downloads the new release from GitHub, installs it, updates the Claude Code plugin, and runs `check`. Then **start a new Claude Code session** to load the new skills. If `check` then reports a role subagent as *edited by hand*, the release changed the subagents (3.0 did): run `avflow setup` once to regenerate them.

**When the workflow changes** — for the team in a new release, or for you with `--advanced` — setup removes the old one before installing the new one; your token, the MCP server and the team skills stay as they are. Never install both: `check` reports an error if it finds both.

## Team settings and your own settings

The team settings come with each release and apply to everyone; your file `~/.avflow/config.toml` holds only what **you** changed. When the PM changes a team setting, `avflow update` brings it to your machine — unless you overrode it.

| Task | Command |
| --- | --- |
| See every setting, with yours marked *← personal* (the token is never shown, only whether one is stored) | `avflow config` |
| Change a setting for yourself | `avflow setup --advanced` (asks every setting again), or `avflow config --edit` then `avflow setup` |
| Go back to the team settings | `avflow config --reset`, then `avflow setup` |
| Print where your file is | `avflow config --path` |

**Fixing your token** — for example after resetting it in Redmine: run `avflow setup` again and enter the new key. When the Redmine address changes (a team setting), the old key is removed from the keyring automatically.

Override team settings only when the PM agrees; the point of team settings is that everyone works the same way. **Do not change the Redmine URL by hand**: the token is tied to it.

## When something goes wrong

Run `avflow check` first: every ❌ line comes with its fix; if you are still stuck, send the PM the **exact error message**, never your token.

| Symptom | Usual cause | Fix |
| --- | --- | --- |
| `avflow: command not found` | No new terminal window opened after installing | Open a new window; macOS: `~/.local/bin/avflow`, Windows: `%USERPROFILE%\.local\bin\avflow.exe` |
| Windows: PowerShell refuses to run the script | Execution policy | Use `-ExecutionPolicy Bypass` as shown, or run `Unblock-File .\bootstrap.ps1` |
| Redmine returns 401 / 403 | Wrong token, or the REST API is not enabled | Check the token; tell the PM if it still fails |
| Redmine returns 404 | Wrong address | Use exactly `https://redmine.enclave.vn` — no `/redmine` at the end |
| ❌ GitLab login | The GitLab token lacks scopes | Create a token with `api` and `write_repository`, then `glab auth login --hostname gitlab.enclave.vn` |
| ❌ Access to the avflow marketplace | No read access, or git is not signed in to GitHub | Ask the PM for read access; run `gh auth login` and `gh auth setup-git` |
| ❌ Cannot get the latest release | `gh` not signed in, or the wrong account | `gh auth status`; with several accounts, `gh auth switch` |
| ❌ Plugin integrity: files differ | A skill was edited on this machine | In Claude Code: `/plugin uninstall avflow@avflow`, then `/plugin install avflow@avflow` |
| ❌ … plugin is v… but this avflow command is v… | The plugin is newer than the avflow command | `avflow update` |
| No `/avflow:…` commands in the Claude Desktop Code tab | Shortcuts may be CLI-only | Ask in words, for example *"run avflow check"* |

**A git command is blocked by the guardrails** (message *"BLOCKED by avflow git guardrails"*): this is **intended**. The agent may not push to `main`, `master`, `develop` or `release/*`, force push, delete remote branches, push tags, or run `reset --hard`, `clean -f`, `branch -D` or commands that discard changes, and it may not commit anything that looks like a secret (keys, tokens, passwords, `.env` files, private keys) — the message names the file and line, never the value. Through the GitLab and GitHub CLIs (`glab`, `gh`, including their `api` command) it may not **merge** or **approve** a merge request, or delete a repository, release, branch or branch protection: the agent runs them as you, so its approval would count as yours. Pushing **your own feature branch** still works. Changes to protected branches go through merge requests; if you really need a blocked command, **run it yourself** in a terminal.

## Models per task

Planning and review benefit from the strongest model; implementing a confirmed plan usually does not. avflow therefore installs three **role subagents**, each running on the model chosen for it.

| Subagent | Does | Default model | Can it change files? |
| --- | --- | --- | --- |
| `avflow-planner` | Design and plan for larger tickets and any ticket in a risk area | Opus | No — read-only |
| `avflow-implementer` | Implements the confirmed plan, tests first | Sonnet | Yes, only the files in the plan |
| `avflow-reviewer` | Two-stage review (spec, then code quality) when `independent-review` is required | Opus | No — reads and runs tests only |

The main session — the model you pick with `/model` in Claude Code — coordinates: it hands each step to the right subagent, posts the results on the ticket and asks you to confirm. Small changes are usually done in the main session.

**The models are team settings** (default Opus to plan and review, Sonnet to implement). To use other models yourself, run `avflow setup --advanced` or edit `[models]` with `avflow config --edit` and then run `avflow setup`. Allowed values: `opus`, `sonnet`, `haiku`, or `inherit` (same as the main session). `avflow check` shows each subagent with its model and reports any that differ from the configuration.

Opus uses your plan's limits faster than Sonnet. If you hit limits often, keep Opus for review only.

## Context monitoring

Answers tend to become less reliable when a session's context grows very large, even far below the model's maximum. avflow watches the context size of every session and subagent and tells you — and the agent — before it gets there.

| Context size | What happens |
| --- | --- |
| Below the warning (default 300k tokens) | Nothing; the size is only recorded |
| Past the warning | You see a message; the agent is told to stay focused, delegate to the subagents and plan a handoff |
| Past the limit (default 400k tokens) | You see a message; the agent is told to stop starting new work, write the handoff as a private note and ask you to start a new session |

The orchestrator (your main session) is checked before every prompt. Each subagent is recorded when it finishes, with its model and context size. The role subagents start with a fresh context, so delegating to them is the best way to keep the main session small.

**See the history:** `avflow usage` (or `avflow usage --days 30`) lists your sessions with their peak context and model, the subagent calls per subagent and model, and how often the warning and the limit were reached. `avflow check` mentions it when the thresholds were reached recently.

**The thresholds are team settings** (`[monitor]`). For yourself, use `avflow setup --advanced` or `avflow config --edit`. Setting `enforce = true` makes avflow refuse new prompts past the limit instead of only warning. The monitor reads the token counts Claude Code records for each reply; it never sends anything anywhere.

## Skills reference

The agent picks a skill by itself when the situation matches; you can also ask for one by name (for example *"use the triage skill on #512"*). Team skills are installed for everyone, whichever coding workflow is used.

**Team skills (avflow plugin)**

| Skill | What it does | Used when |
| --- | --- | --- |
| `tickets` | The ticket workflow through the `avflow-tickets` tools: find ready tickets, read them, private notes, start, wait for a green pipeline, submit for review, bug drafts, handoff | Every ticket, from `/avflow:next-ticket` to the handoff |
| `workflow` | The one ticket flow, how to satisfy each required check, which subagent does each step, and which skill meets each requirement with Superpowers or Matt Pocock's skills | Once a ticket is started, and whenever the agent is unsure which skill to use |
| `qa-agent` | QA without a dedicated tester: test cases from the acceptance criteria before coding, break-it review, bug reproduction, release checklist, and the two-stage review for `independent-review` (handed to the reviewer subagent) | Before coding, at review, and when a bug is reported |
| `ticket-writer` | Drafts a ticket in the team structure, with TODOs where it cannot know and the machine-readable *Size and mode* line (estimate, risk area, hotspot) | Writing a new ticket, or turning a customer ticket into a work ticket |
| `triage` | Classifies a customer ticket (defect S1–S3, change request, question, maintenance), checks the code, tries to reproduce, lists what is missing — never answers the customer | A ticket arrives from the customer |
| `incident` | Field incidents: severity, the exact evidence to request (collected once), timeline, evidence-based hypotheses, reproduction, fix with a regression test, blameless review | Software misbehaves at a customer site |
| `release` | Release notes from the merged tickets (with `avflow release-notes`), the customer engineer's acceptance checklist, pre-release checks, rollback | Preparing a release candidate or a production release |
| `zoom-out` | Maps the code before changing it — entry points, callers, data, threads, tests, risks — without editing anything | Legacy or unfamiliar code, the paths of a risk area, after two failed fix attempts |
| `glossary` | Keeps `docs/CONTEXT.md` sharp: one term per concept, conflicts resolved, terms to avoid | A domain term is new, unclear or used with two meanings |
| `adr` | Records a decision in `docs/adr/` when it is hard to reverse, surprising without context, and a real trade-off | An architectural or scope decision is made |

**Role subagents (generated by `avflow setup`, model per role)**

| Subagent | What it does | Default model |
| --- | --- | --- |
| `avflow-planner` | Designs and plans larger or risky tickets; read-only | Opus |
| `avflow-implementer` | Implements the confirmed plan, tests first, only the files in the plan | Sonnet |
| `avflow-reviewer` | Independent two-stage review in a fresh context; reads and runs tests only | Opus |

**Installed alongside**

| Skill set | What it brings |
| --- | --- |
| **Superpowers** *or* **Matt Pocock's skills** (team setting) | The coding workflow: design, planning, implementation, tests first, debugging — mapped to the team's requirements by the `workflow` skill |
| `handoff` (Matt Pocock, pinned) | The session handoff note, posted as a private note on the ticket |

**Project skills (in the project's repository)**

The team skills use generic words — *risk area*, *test environment*, *the customer's environment* — because avflow
serves many projects. What only one project knows lives in that project: its risk areas in `.avflow/project.toml`, its
test environments and languages in the *Test environments and languages* section of its `CLAUDE.md`, and its own skills
in `.claude/skills/<project>-…/` (for example `<project>-hardware-review` for checks on test hardware, or
`<project>-logs` for the field evidence to request). The team skills read that section and use a project skill when one
exists.

`triage` is adapted from Matt Pocock's skill of the same name, and `glossary` and `adr` from his `domain-modeling` skill (MIT): the team versions never write anything the customer can read and use the team's files.

## Starting a new project

In the new repository, run:

```bash
avflow init                      # detects the stack; or: avflow init --stack dotnet,node
```

It writes **`.avflow/project.toml`**, the project's risk profile, from **stack presets** (.NET, Node, Python, Java, Go —
detected from `*.sln`, `package.json`, `pyproject.toml`, `pom.xml`, `go.mod`, …): areas for dependencies, data migrations,
configuration, build and CI (including the profile itself and CODEOWNERS) and infrastructure; the stack's own risks as
commented suggestions; a commented example for a domain area; `[risk.other]`; a strict default — plan confirmation and
independent review for every change outside the areas — for the first **6 weeks**; and `[ci] gate = "report"`. The
project owns this file: edit it, add its own areas (payments, machine control, …) and owners.

It also adds the team's standard files: `CLAUDE.md`, `docs/CONTEXT.md`, a first ADR, `CODEOWNERS`, the merge request template, `.gitattributes`, `.editorconfig`, and the GitLab CI jobs that scan the commits for secrets (gitleaks, the server-side backup of the guardrails), check `Refs #id` in merge request titles, move merged tickets to *Ready for test*, and check the risk areas' required checks (`avflow-risk-check`, with its
scripts `ci/avflow_risk_check.py` and `ci/avflow_risk.py`). Existing files are never overwritten (use `--force` to replace them); if the project already has a `.gitlab-ci.yml`, avflow tells you to add `include: - local: .gitlab-ci.avflow.yml` to it.

Then review `.avflow/project.toml` (areas, owners), run `avflow risk check` and `avflow risk sync`, fill in the TODOs in `CLAUDE.md` (build and test commands; test environments, languages and project skills), protect `main` and `develop` in GitLab (no direct push, *Pipelines must succeed*), and set the CI/CD variables:

| Variable | Value |
| --- | --- |
| `REDMINE_URL` | The same Redmine address as in `avflow setup` (not protected: it is not a secret, and merge request pipelines need it) |
| `REDMINE_CI_API_KEY` | The API key of a **dedicated CI account** in Redmine (masked, **protected**) — moves tickets to *Ready for test* after a merge |
| `REDMINE_READ_API_KEY` | The API key of a **read-only CI account** (masked, **not protected**) — lets `avflow-risk-check` read the ticket in merge request pipelines. Its role has only *View issues* and *View private notes* |
| `AVFLOW_GITLAB_TOKEN` | A **project access token** (Settings → Access tokens; role Reporter, scope `read_api`; masked) — lets `avflow-risk-check` read approvals, notes and the description |

**The CI account** is an ordinary Redmine user created only for CI (for example `ci-bot`), member of the project with the team role. Its notes show as written by CI, its key can be reset without affecting anyone, and CI keeps working when people change. Do not use a person's key in a real project: anyone with Maintainer access in GitLab can read CI variables. If there is no CI account yet, remove the `avflow-ready-for-test` job and move tickets to *Ready for test* by hand.

**The read-only account** (for example `ci-reader`) exists because merge request pipelines run on unprotected
branches: anyone who can push a branch — a person or an agent — could change the CI file and read every variable that
pipeline gets. So the key with write rights stays protected, and the merge request pipeline gets a key that can only
read. Without `REDMINE_READ_API_KEY`, `avflow-risk-check` cannot read the ticket and judges by the changed files only
(it says so in its log); the risk areas named on the ticket are still enforced when the agent starts and plans.

## For the PM

Two read-only commands turn tickets and merge requests into the documents a PM needs.

| Command | Produces |
| --- | --- |
| `avflow release-notes --from <previous-tag> [--to <commit>] [--out notes.md]` | Release notes from the tickets referenced by the commits, high-risk tickets first and marked with their risk areas (for example **[Machine control]**), an acceptance checklist skeleton, and warnings for commits without a ticket or tickets not yet *Ready for test* |
| `avflow report --project <identifier> [--days 7] [--out report.md]` | Weekly report: progress per release, tickets over estimate by more than 50%, tickets reopened in the period, the **risk** of the changes reviewed in the period (share of high-risk changes, tickets per risk area and where the area was found — ticket, plan or only at review — and profile gaps), and — when run inside the repository with `glab` signed in — merged merge requests, median time to merge and first-pipeline success |

Set a default project once with `avflow config --edit` (`project` under `[tickets]`).

The risk section reads the private notes avflow writes at start, plan and review, so it covers the tickets that reached
`review_requirements` in the period. Areas found **only at review** mean the ticket and the plan missed a risk: improve
the ticket or the plan habit. **Profile gaps** mean the profile is incomplete: run `avflow risk suggest` and add paths.
After the pilot, these numbers decide whether `gate = "fail"` becomes the default.

### Moving a project from 2.x to 3.0

1. Members: `avflow update`, then `avflow setup` once (new subagents), and a new Claude Code session.
2. In each project, on a feature branch: `avflow init` (adds `.avflow/project.toml`, the `avflow-risk-check` job and its
   scripts; existing files are kept). Add the project's own areas, owners and checks; move the sensitive paths that
   2.x listed in `CLAUDE.md` / `CODEOWNERS` into areas; fill in the *Test environments and languages* section of
   `CLAUDE.md` (copy it from the template if the project's `CLAUDE.md` is older); `avflow risk check`, `avflow risk sync`;
   merge.
3. Move what the 2.x skills said about this project into its own skills (`.claude/skills/<project>-…/`); the sample
   project's `sandbox-machine-review` shows the shape.
4. Open tickets: the Mode field is ignored. A 2.x *Machine-side* field or line is **not** read any more — give every
   open ticket that had *Machine-side = yes* the matching **Risk area** (or *Other high risk*) before it is started.

### Changing the team settings

The team settings live in **`team/avflow-team.toml`** in the avflow development repository: Redmine URL, statuses and field names, GitLab host, coding workflow, guardrails, protected branches, models and context thresholds.

1. Edit `team/avflow-team.toml`.
2. Release: `python3 scripts/release.py --marketplace-url <marketplace git URL> --publish-to <marketplace folder> --push`. The release script checks the file and refuses to release if the Redmine URL or the GitLab host is missing.
3. Tell the team to run `avflow update` and start a new Claude Code session.

Members who overrode a setting keep their value; `avflow config` shows it as *← personal*.

## Uninstall and command list

Two commands remove avflow completely: token, MCP server, plugin, skills, subagents, hooks and configuration.

```bash
avflow uninstall
uv tool uninstall avflow
```

Superpowers is kept; remove it in Claude Code with `/plugin uninstall superpowers@superpowers-marketplace` if you want.

**Commands**

| Command | What it does |
| --- | --- |
| `avflow setup` | Enter your token and configure Claude Code with the team settings; safe to run again. `--advanced` asks every setting |
| `avflow check` | Checks everything and tells you how to fix problems (the old name `doctor` still works) |
| `avflow update` | Installs the latest release — with the latest team settings — and updates the plugin |
| `avflow update --check` | Only tells you whether a new version exists |
| `avflow config` | Shows the settings and which are yours (never the token); `--edit`, `--path`, `--reset` |
| `avflow usage` | Context size per session and subagent calls with their models |
| `avflow init [--stack …]` | Adds the team's standard files and the risk profile to a project repository |
| `avflow risk check` · `files` · `sync` · `suggest` | The project's risk profile: validate, try on files, regenerate CODEOWNERS and the CI copy, propose paths from gaps |
| `avflow release-notes --from <tag>` | Release notes and acceptance checklist from the referenced tickets |
| `avflow report --project <id>` | Weekly PM report (read-only) |
| `avflow uninstall` | Removes configuration, token, MCP server, plugin, skills, subagents and hooks |
| `/avflow:next-ticket` | (Claude Code) prepares the next ticket and stops before coding |
| `/avflow:check` | (Claude Code) runs `avflow check` and explains the result |
