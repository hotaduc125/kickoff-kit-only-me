# avflow

One command sets up the team's AI coding workflow on a developer's machine:

- **ticket system** (v1: Redmine; planned: Jira, GitLab Issues, GitHub Issues) through the `avflow-tickets` MCP server —
  nine tools, the same for every system, with the team rules enforced in code;
- **repository and CI/CD** (v1: GitLab via `glab`; planned: GitHub via `gh`);
- **Claude Code** with the member's **coding workflow** — **Superpowers** or a curated set of **Matt Pocock's** skills (pinned commit) — the **git guardrails** hook, Matt Pocock's `handoff` skill and the **avflow plugin**
  (team skills `tickets`, `workflow`, `choose-mode`, `qa-agent`, `ticket-writer`, `zoom-out`, `triage`, `incident`, `release`, `glossary`, `adr`, commands `/avflow:next-ticket`, `/avflow:check`);
- a final **check** (whoami on the ticket system, MCP registration, GitLab login, workflow, guardrails, plugins, skills).

Tokens are asked once, verified, and stored in the **OS keyring** (macOS Keychain, Windows Credential Manager). They are
never written to files and never pass through the AI conversation.

## Why avflow

**avflow is the team's harness around the coding agent.** One command **connects** the tools (ticket system,
repository), **equips** the agent (the member's coding workflow and the team skills), **puts guardrails in place**
(team rules enforced in code), and **keeps every machine in step** (check and update).

| Layer | What avflow does |
|---|---|
| **Connect** | Ticket system through the `avflow-tickets` MCP server (token in the OS keyring); repository and CI through the official CLI (`glab`) |
| **Equip** | The coding workflow each member chooses — **Superpowers** *or* a curated set of **Matt Pocock's** skills — plus the team skills (`tickets`, `workflow`, `choose-mode`, `qa-agent`, …) and three role subagents — planner, implementer, reviewer — each on the model the member chooses (for example Opus to plan and review, Sonnet to implement) |
| **Guard** | Ticket rules inside the MCP server (notes always private, only two status changes, …); git guardrails, including blocking commits that contain secrets (and a GitLab CI secret scan as the server-side backup); merge requests go to review only with a green pipeline; integrity check of the installed skills |
| **Keep in step** | `avflow check` and `avflow update`: everyone runs the same version of the workflow |
| **Observe** | A context monitor records the context size of every session and subagent, warns before it grows past the team's thresholds, and `avflow usage` summarises it |

**More than an installer.** The value is that team standards are enforced by the tools, not by each person or agent
remembering them:

- the agent **cannot** write a public note to the customer, close a ticket or start a blocked one — the tools to do so do not exist;
- the agent **cannot** push to `develop` or force push — the hook blocks it first;
- a skill **cannot** be changed quietly on someone's machine — `avflow check` reports it.

**Members choose their tools; the output standard belongs to the team.**

**Why not just use Matt Pocock's skills?** We use them unchanged wherever we can. We only make a team version when the
original writes directly to a ticket the customer can read, when it differs from team conventions (for example
`docs/CONTEXT.md` instead of `GLOSSARY.md`), or when members on Superpowers need it too. Those versions are adapted from
the originals and credit them (MIT): `triage` from `triage`, `glossary` and `adr` from `domain-modeling`, and the git
guardrails from `git-guardrails-claude-code`.

**CI stays in GitLab.** avflow has no CI of its own: the judge of quality must be independent of the agent's tools. avflow checks early on the developer's machine (guardrails, tests before the merge request) and provides the CI templates; the project's pipeline decides.

**What avflow is not**

- **Not an agent.** It writes no code; Claude Code is the agent.
- **Not a replacement for CI or human review.** CI still judges quality, and merging is always a person's decision.
- **Not a ticket system.** Redmine (Jira later) still holds the tickets; avflow is the controlled door through which the agent works with them.

**Today and next**

| | Today (2.x) | Planned |
|---|---|---|
| Ticket system | Redmine | Jira, GitLab Issues, GitHub Issues (adapter architecture and handling rules are ready) |
| Repository and CI | GitLab | GitHub (`gh`, GitHub Actions) |
| Coding agent | Claude Code (CLI and the Code tab of Claude Desktop) | Other agents such as Codex — the MCP server already works with any MCP client; skills, hooks and setup would need an agent adapter |

## Install (team members)

macOS:
```bash
./bootstrap.sh <wheel file or registry URL>
```
Windows (PowerShell):
```powershell
.\bootstrap.ps1 <wheel file or registry URL>
```
The script installs uv if needed, installs avflow, then runs `avflow setup`.

Manual alternative: `uv tool install <wheel or package>` then `avflow setup`.

## Commands
| Command | |
|---|---|
| `avflow setup` | Enter your tokens and configure Claude Code with the team settings (safe to run again); `--advanced` asks every setting |
| `avflow check` | Check that everything works (also tells you when an update is available) |
| `avflow update` | Install the latest release and update the plugin (`--check` only reports) |
| `avflow config` | Show the settings and which are personal (never the token); `--edit`, `--path`, `--reset` (back to the team settings) |
| `avflow init` | Add the team's standard files to a project repository (CLAUDE.md, docs/CONTEXT.md, ADR, CODEOWNERS, MR template, `.gitattributes`, `.editorconfig`, GitLab CI jobs: MR title check, secret scan with gitleaks, ticket to *Ready for test* after merge); never overwrites without `--force` |
| `avflow release-notes --from <tag>` | Release notes and acceptance checklist from the tickets referenced by the commits |
| `avflow usage` | Context size per session (orchestrator) and subagent calls with their models, from the context monitor |
| `avflow report --project <id>` | Weekly PM report (read-only): progress per release, tickets over estimate, reopened tickets, merge-request flow |
| `avflow uninstall` | Remove the configuration, token and MCP registration (keeps Superpowers) |

## The nine ticket tools
`whoami` · `list_my_ready_tickets` · `get_ticket` · `add_private_note` (always private) · `set_fields` (Mode,
Machine-side, Hotspot) · `find_hotspot_conflicts` · `start_ticket` (refused if not assigned, blocked, not Ready or no Mode)
· `submit_for_review` (needs the merge / pull request URL) · `create_bug_draft` (private draft).

## Ticket system setup (Redmine)
Best: REST API enabled; statuses Ready, In progress, In review, Ready for test; custom fields Mode (list), Machine-side (boolean),
Hotspot (text); tracker Bug; the customer role must not view private notes.

Without admin rights: setup maps the workflow onto Redmine's default statuses, and avflow reads Machine-side and Hotspot
from the "Size and mode" line of the description and keeps the confirmed mode in a private `[avflow]` note.

## Development
`uv run pytest` · adapters: see `docs/ADAPTERS.md` · release: tag `vX.Y.Z` → CI publishes the package.

Configuration: `~/.avflow/config.toml` (no secrets) · audit log: `~/.avflow/audit.log`.
