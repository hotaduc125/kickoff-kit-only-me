# Changelog

What changed in each avflow release, newest first. Why things changed is in `docs/decisions.md`; releases before
3.0.0 are described there by version.

## 3.0.2 — unreleased

Upgrading from 3.0.x: `avflow update`, then open a new Claude Code session — no setup needed. The first `avflow check`
after the update applies the new team settings on its own.

### Changed

- **Update applies the team settings without questions:** the first `avflow check` after an update regenerates the
  role subagents and re-registers permissions and hooks for the new version, without touching the token, then says
  to open a new Claude Code session. `avflow setup --apply` does the same on demand. No more *"edited by hand"* after a
  release that changes the subagents.
- **Cheaper models by default:** the planner now uses **Sonnet** (it runs for every ticket); the implementer stays on
  Sonnet and the reviewer on Opus. Personal overrides are kept.
- **Smaller context thresholds:** warn at 150k tokens, limit at 250k (were 300k / 400k).

### Added

- **One ticket per session:** starting a second ticket in the same Claude Code session is refused — *"This session is
  working on #12. Type /clear or open a new session to work on #15."* Reading other tickets still works; a refused start
  does not count. The `tickets` skill ends each ticket with "/clear before the next ticket".
- **No large files read whole:** the agent may not read a file over 200 KB without a range; it searches with Grep and
  reads only the part it needs. Images, PDFs and notebooks are exempt.
- Both rules are team settings (`[guards]`, on by default) in a new hook, `avflow-session-guard`.
- **`avflow usage` daily totals** for this machine (sessions, turns, subagent calls, context carried — an estimate).
  `avflow check` reminds you that `/usage` in Claude Code shows the plan's 5-hour and weekly limits.
- **User guide: "When you hit a limit"** — what to do for the Opus, 5-hour and weekly limits.

### Fixed

- **`avflow-mr-title` failed on every merge request:** the script line was not quoted, so YAML read ` #` in
  `'refs #[0-9]+'` as a comment and the shell got an unterminated quote. The line is now quoted. Projects set up with
  an earlier version: in `.gitlab-ci.avflow.yml`, replace the `avflow-mr-title` script line with
  `- 'echo "$CI_MERGE_REQUEST_TITLE" | grep -Eiq "refs #[0-9]+" || (echo "MR title must contain Refs #<ticket-id>"; exit 1)'`
  (do not use `avflow init --force` for this: it also overwrites the project's `CLAUDE.md`).
- **No pipeline in a new project:** every avflow CI job is in the `.pre` / `.post` stages, and GitLab creates no
  pipeline whose jobs are all there — so in a project that had no build or test jobs yet, merge requests got no
  pipeline (and *Ready for test* never ran after a merge). `avflow init` now writes `.gitlab-ci.yml` with a placeholder
  job `build-and-test` (stage `test`, on merge requests and pushes to `develop`) to replace with the project's own
  jobs. `avflow init` and `avflow risk check` warn when an existing `.gitlab-ci.yml` has no job outside `.pre` / `.post`.
  Projects set up with 3.0.0–3.0.1 and no build jobs of their own: add one job in a normal stage.

### Security

- **Stored tokens cannot be read by the agent:** setup now denies commands that read the OS keyring or CLI tokens
  (`security find-generic-password`, `dump-keychain`, `cmdkey`, `secret-tool`, `keyring get`, `git credential fill`,
  `gh auth token`, `glab config get token`, …) in Claude Code's permissions, and the guardrails hook blocks them too —
  including keyring access in inline code and any command that sends `X-Redmine-API-Key`.
- **Guardrails see nested commands:** `bash -c`, `sh -c`, `cmd /c`, `pwsh -Command` (also encoded), `python -c`,
  `node -e`, `eval`, `env`, `sudo`, `xargs`, `$( … )`, backticks, subshells, `echo … | sh`, and git / `gh` / `glab`
  aliases (`git p` = `push --force`) are evaluated like the plain command.
- The hooks guard against mistakes and injected instructions; they are not a security boundary (a script written to a
  file and then run is not inspected).

## 3.0.1 — Nov 15, 2026

Upgrading from 3.0.0: `avflow update` — no setup needed. From 2.6.x: follow the 3.0.0 steps below.

### Security

- **Git guardrails cover `gh` and `glab`:** the agent may not merge a merge request (`gh pr merge`, `glab mr merge` /
  `accept`), approve one (`glab mr approve`, `gh pr review --approve`), or delete a repository, release, branch or branch
  protection — also through `gh api` / `glab api`. The agent runs these CLIs as the person, so its approval would count
  as theirs. Viewing, notes, diffs, CI status and creating merge requests still work. Members get it with
  `avflow update`; no setup needed.

## 3.0.0 — Nov 13, 2026

avflow 3.0 replaces the four working modes with **one ticket flow**, and lets **each project define its own risk
areas**. A change gets extra checks only when it is actually risky — judged from the ticket, the plan and the files it
changes.

### Upgrading from 2.6.x

1. `avflow update`
2. `avflow setup` once — the role subagents changed; until then `avflow check` reports them as *"edited by hand"*.
3. Open a new Claude Code session.
4. **Projects** (once, on a feature branch): `avflow init`, describe the project's risk areas in
   `.avflow/project.toml`, `avflow risk check`, `avflow risk sync`, merge.
5. **Open tickets:** set a **Risk area** on any ticket that relied on *Machine-side = yes* — that field is no longer
   read.

### Breaking changes

- **Modes removed:** DIRECT / PLAN / FULL / SPIKE and the `choose-mode` skill are gone. The *Mode* field and old
  `mode=` notes are ignored.
- **Machine-side removed:** the field, the description line and old notes are no longer read. Use **Risk area**.
- `start_ticket` no longer takes or proposes a mode; `submit_for_review` requires `review_requirements` first.

### Added

- **One ticket flow:** start → short plan (every ticket) → confirmation only when risky → implement tests first →
  merge request with a green pipeline → required checks → a person reviews and merges.
- **Risk areas per project** in `.avflow/project.toml`: paths, owners and checks per area; `[risk.other]` for "risky,
  no area yet"; `[risk.default]` as an optional strict default for new projects, with an end date.
- **Four required checks:** `plan-confirmation` (stop after the plan until you confirm), `independent-review` (fresh
  reviewer subagent, verdict posted on the merge request), `code-owner` (an area owner approves), `checklist:<text>`
  (a box a person ticks in the merge request).
- **Risk is checked three times and only goes up:** the ticket's risk area at start, the planned files
  (`assess_plan`), the diff (`review_requirements`).
- **New tools:** `assess_plan` (posts the plan privately, decides whether to stop) and `review_requirements` (final
  checks, writes the checklist into the merge request).
- **CI gate `avflow-risk-check`:** on every merge request, reads the profile from the target branch, matches the
  changed files, verifies the review note, owner approvals and checklist ticks. `report` (pilot default) or `fail`.
  Works on GitLab Free.
- **Commands:** `avflow risk check` (validate), `avflow risk files` (which areas and checks apply to given files),
  `avflow risk sync` (regenerate the CODEOWNERS block), `avflow risk suggest` (propose paths from profile gaps).
- **Stack presets in `avflow init`:** .NET, Node, Python, Java, Go — detected from the repository (or `--stack`),
  written as a starting profile.
- **CODEOWNERS generated from the risk areas**, so checks and owners cannot drift apart.
- **`avflow report` risk section:** share of high-risk changes, areas by where the risk was found, areas found only at
  review, profile gaps.
- **Release notes** mark tickets by risk area, e.g. **[Payments]**.
- **`CLAUDE.md` template:** new section *Test environments and languages*, read by the team skills.
- **Project skills:** a project can add its own skills (`.claude/skills/<project>-…/`); the team skills use them.
- **`REDMINE_READ_API_KEY`:** optional read-only Redmine key so the CI gate can read tickets in merge request pipelines.

### Changed

- **Team skills use generic words** (risk area, test environment, the customer's environment); nothing in avflow names
  a project or customer, enforced by a test.
- **Role subagents** (planner, implementer, reviewer) work from risk areas instead of "sensitive paths".
- **`/avflow:next-ticket`** starts the ticket and posts the plan; it stops only when the plan needs your confirmation.
- **`REDMINE_URL`** no longer needs to be protected in GitLab.

### Security

- The agent cannot forge `[avflow]` lines; only private notes count.
- The review is always compared against the merge request's target branch.
- A risk area can be added but never removed by the agent.
- The CI gate's ticket-reading key can be read-only, so the write key stays protected.

### Known issues

- Not yet run against the real Redmine and GitLab (the pilot covers it).
- Windows: `docs/WINDOWS_TEST.md` is updated but not yet run on a Windows PC.
- `avflow init` does not update CI scripts in projects that already have them.
