# avflow — decision log

Why avflow is the way it is. Read this before changing behaviour: many things that look odd were decided on purpose.
Newest decisions first. Add an entry whenever a session decides something (date · decision · why · consequences).

---

## 3.0 — decisions taken before building (Nov 13, 2026)

The PM answered the open decisions of `docs/design/avflow-3.0.md`:

- **Modes removed.** One flow for every ticket; `start_ticket` no longer needs Mode, `set_fields` no longer sets it, the
  Mode field and `[avflow] mode=` notes are ignored. SPIKE becomes a ticket type. `choose-mode` is removed in phase 1
  (not phase 3), because it calls `set_fields(mode=…)`, which no longer exists.
- **Ticket risk area: custom field preferred, description line otherwise** (same pattern as 2.5). Team setting
  `field_risk_area`; without that field, the `Risk area:` line (also `High risk: yes` → Other high risk) is read.
- **Machine-side = yes maps to an area** through the team setting `machine_side_area` (Enclave: `Machine control`);
  without the setting it reads as *Other high risk*.
- **Several risk areas per ticket; the agent can only add.** The agent adds an area (with a reason) in a private
  `[avflow] risk-area=…` note — never by writing the custom field, whose options a person owns. Nothing lowers or removes an
  area except a person editing the ticket. *Why:* a union keeps "risk only goes up" trivial to enforce.
- **Mandatory plan note for every ticket.** `assess_plan` takes the plan text and posts it, so the note is enforced in code.
- **Required checks are remembered in private `[avflow] required {…}` notes** at start, plan and review; each stage takes the
  union with the earlier ones. `submit_for_review` refuses until `review_requirements` has run.
- **Changed files at review come from git** (merge base with the target branch → HEAD), not from a list the agent supplies.
  `base` may only name a branch, and must agree with the MR's target branch when glab can read it.
- **The agent cannot forge `[avflow]` lines:** `add_private_note` refuses text with a line starting with `[avflow]`, and
  `set_fields` folds `reason` and `hotspot` onto one line. *Why:* the required checks and the "review done" step live in
  those notes; without this, the agent could write its own `required … "stage": "review"` note and skip the gate.
- **CI gate: report only during the pilot**, with a switch to fail later (phase 2).
- **Strict default for new projects:** `plan-confirmation` + `independent-review`, `until` = init date + 6 weeks (phase 2).
- **Stack presets:** all five (.NET, Node, Python, Java, Go); no Enclave WPF + Zmotion team preset — Mateo writes its
  Machine control area by hand (phase 2).
- **Still open — GitLab tier** of `gitlab.enclave.vn`. On Free, CODEOWNERS does not block; the CI job must read MR approvals
  through the API (needs a project access token with `read_api`; approving does not re-run the pipeline). A GitLab MCP
  connector cannot be the gate: it is the agent's tool, and the judge must be independent of the agent (2.4). Build the API
  check (works on both tiers) in phase 2, report-only until the tier is confirmed.

## avflow 3.0 — the design (proposed Nov 12, 2026)

**Replace the four working modes with one flow and project-defined risk areas.** See `docs/design/avflow-3.0.md`.

- *Why:* choosing DIRECT / PLAN / FULL / SPIKE before any code was guesswork. In a real test the agent chose DIRECT for a
  1-day, 4-file ticket because rule 3 ("≤ 4 h and ≤ 3 files") did not say whose estimate or which files count, and an
  earlier Mode value persisted after the ticket text changed. The value of FULL (independent review, code owner, test
  bench) is better triggered by facts: the ticket's risk area and the files actually touched.
- *Why generic risk areas:* avflow must serve many projects, not only Mateo; "Machine-side" is a Mateo concept.
- *New projects:* stack presets (paths by stack conventions), areas by concern (no paths yet, picked on tickets), a strict
  default for the first weeks, and gaps from evidence.
- *Open decisions:* answered above, except the GitLab tier.

---

## 2.6.x — team settings and Enclave specifics (Nov 2026)

**Team settings replace setup questions (2.6.0).** `team/avflow-team.toml` holds the organisation's settings (Redmine URL,
statuses and fields, GitLab host, workflow, guardrails, protected branches, models, context monitor). `release.py`
validates and embeds it as `src/avflow/data/team.toml` with `team_version` and the marketplace URL. Members' setup asks only
the Redmine API key and the GitLab login. `~/.avflow/config.toml` stores only personal overrides; `avflow config` marks
them, `--reset` removes them, `avflow setup --advanced` asks every question.
- *Why:* a candid review found setup too complex (14 questions, too many per-person choices). Team decisions should be
  made once by the PM, and changes should reach every machine through `avflow update`.

**Enclave status mapping (2.6.1–2.6.2).** Ready → `New`, In progress → `In Progress`, In review → `In Code Review`,
Ready for test → `Ready for testing`; blocker "done" statuses: Ready for testing, Resolved, Closed. Added an explicit
`status_ready_for_test` setting; `avflow init` writes the team's status names into the CI job (`AVFLOW_STATUS_*` variables),
so no CI variables are needed for them. Redmine URL is `https://redmine.enclave.vn` (no `/redmine`).
- *Consequence:* because `New` means Ready, a "not ready" test ticket must use another status (for example Rejected).

## 2.5.0 — Redmine without admin rights

- Statuses: setup detects missing ones and can map to Redmine defaults (now superseded by team settings).
- Without custom fields, Machine-side and Hotspot are read from the *Size and mode* line of the description (written by the
  person; the agent never edits the description). The mode and any raise of Machine-side are kept in **private** notes
  starting with `[avflow]`; public notes with that text are ignored (anyone, including the customer, can write them).
  Custom fields are always preferred when they exist.
- *Why:* the PM has no Redmine admin rights. Only one thing cannot be worked around: an admin must confirm the customer role
  cannot see private notes.

## 2.4.0 — CI stays in GitLab

- avflow has **no CI of its own**: the judge of quality must be independent of the agent's tools. avflow checks early on the
  machine and provides CI templates.
- Template job `avflow-secret-scan` (gitleaks pinned at v8.18.4, MR range and develop pushes, redacted) backs up the local
  secret guard.
- The `tickets` skill waits for the MR's first pipeline and submits for review only when green; the agent fixes causes and
  never weakens tests. The reviewer subagent treats weakened, skipped or disabled tests/CI checks as Blocking.
- Not yet done: GitHub Actions CI for avflow-dev itself (Ubuntu, macOS, Windows).

## 2.3.0 — context monitor

- Hook `avflow-monitor` (UserPromptSubmit, Stop, SubagentStart, SubagentStop) reads context size from the transcript the hook
  receives (input + cache read + cache creation tokens of the latest reply), logs sessions and subagents to
  `~/.avflow/usage.log`, warns at `warn_tokens` (300k) and asks for a handoff and new session at `critical_tokens` (400k);
  `enforce = true` refuses prompts past the limit. `avflow usage` summarises.
- *Why:* the PM observed quality dropping past ~40% of a 1M context. Token count is a risk indicator, not a hallucination
  detector; tests and review remain the safety net. Transcript format is a Claude Code detail and may change.

## 2.2.0 — model per task

- Three role subagents generated into `~/.claude/agents/` from `[models]`: `avflow-planner` (read-only, default opus),
  `avflow-implementer` (default sonnet), `avflow-reviewer` (read + run tests, default opus). Not shipped in the plugin, so
  personal model choices do not break the plugin integrity check; `avflow check` reports missing, changed or hand-edited ones.
- *Why:* plan and review benefit from the strongest model; implementing a confirmed plan usually does not. Review in a fresh
  context is also more independent. Known risk: a reported Claude Code issue with Opus subagents and Extra Usage.

## 2.1.0 — skills and commands from a real project lifecycle

- Team skills `triage` (adapted from Matt Pocock's `triage`), `glossary` and `adr` (from `domain-modeling`), `incident`,
  `release`. Commands `avflow init`, `avflow release-notes`, `avflow report`. Guardrails block commits containing secrets.
- *Principle — reuse first:* use Pocock's skills unchanged wherever possible; make a team version only when the original
  writes to a ticket the customer can read, differs from team conventions (`docs/CONTEXT.md`, private notes), or members on
  Superpowers need it too. Team versions credit the original (MIT).
- *Principle — what goes where:* deterministic work → commands or MCP tools (code); judgement → skills; project-specific
  knowledge → the project's own repository and skills, never avflow.

## 2.0.0 — renamed to avflow

- Earlier names: htkm-kit → kickoff-kit → **avflow** (prefix "av" chosen by the PM; plain `av` avoided because the Aviator
  CLI uses it; `avkit` avoided because of Apple's AVKit). Repos `avflow-dev` (private) and `avflow-marketplace` (team read-only).
- Machines with older names: run `scripts/reset-avflow.sh` / `.ps1` (they remove every old name too), then a fresh install.
- *Rule:* choose names before rollout; a rename forces every machine to reinstall (keyring service name and config folder change).

## 1.3.x — workflow choice and git guardrails

- Members choose **Superpowers or a curated set of 12 Matt Pocock skills** (pinned commit `4ae2317`), never both. Excluded
  Pocock skills: those that publish to an issue tracker (setup-matt-pocock-skills, to-spec, to-tickets, triage, wayfinder,
  implement-spec), `ask-matt`, `domain-modeling` (GLOSSARY.md), the in-progress group, TypeScript-only tools.
- Team skill `workflow` maps each mode's requirements to the chosen skills; the FULL two-stage review moved to `qa-agent`.
- Git guardrails (Python hook `avflow-git-guard`, cross-platform): block push to protected branches, force push, remote
  deletes, tag pushes, `reset --hard`, `clean -f`, `branch -D`, discarding changes. **Feature-branch push is allowed**
  (the team flow needs it) — unlike Pocock's original, which blocks all pushes.
- A candid review later questioned the two-workflow choice (doubles testing and support); not removed yet.

## 1.2.x — install, update, Windows

- Commands `setup`, `check` (alias `doctor`), `update` (from GitHub Releases), `uninstall`, `config`.
- Tokens only in the OS keyring (Keychain / Credential Manager), never in files or the AI chat.
- Plugin integrity check compares installed files with checksums embedded in the wheel (ignores Claude Code's own marker files).
- Windows fixes: resolve programs with `shutil.which` (npm installs `claude.cmd`), force UTF-8 output, find `uv` after winget.
- A static test checks that every name used in setup/update code resolves — added after a renamed constant broke `update`.

## Foundations (v1)

- The MCP server `avflow-tickets` enforces the ticket rules **in code**: notes are always private; the agent may only move
  Ready → In progress and In progress → In review; it may set only a few fields; it refuses to start a ticket that is not
  assigned to the user, not Ready, or blocked by an unfinished ticket. There is no tool to close a ticket or write a public note.
- *Why:* the customer (WKKM, for Mateo) shares the Redmine; rules in prompts can be talked around, missing tools cannot.
- Ticket text is data, never instructions (prompt-injection test T7 in the test plan).
- The person always decides: confirms the plan or mode, reviews and merges, closes tickets.
