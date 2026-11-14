# Changelog

What changed in each avflow release, newest first. Why things changed is in `docs/decisions.md`; releases before
3.0.0 are described there by version.

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
