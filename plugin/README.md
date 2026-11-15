# avflow marketplace

Claude Code plugin marketplace for the Enclave team workflow. Install everything with `avflow setup` — see INSTALL.md in each release.

## Why avflow

**avflow is the team's harness around the coding agent.** One command **connects** the tools (ticket system,
repository), **equips** the agent (the member's coding workflow and the team skills), **puts guardrails in place**
(team rules enforced in code), and **keeps every machine in step** (check and update).

| Layer | What avflow does |
|---|---|
| **Connect** | Ticket system through the `avflow-tickets` MCP server (token in the OS keyring); repository and CI through the official CLI (`glab`) |
| **Equip** | The coding workflow each member chooses — **Superpowers** *or* a curated set of **Matt Pocock's** skills — plus the team skills (`tickets`, `workflow`, `qa-agent`, …) and three role subagents — planner, implementer, reviewer — each on the model the member chooses (for example Opus to plan and review, Sonnet to implement) |
| **Guard** | Ticket rules inside the MCP server (notes always private, only two status changes, …); git guardrails (also `gh` / `glab`: no merge, approve or delete), including blocking commits that contain secrets (and a GitLab CI secret scan as the server-side backup); merge requests go to review only with a green pipeline; integrity check of the installed skills |
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

**Generic team skills, project skills in the project.** avflow's skills use generic words (risk area, test environment,
the customer's environment) and a test keeps project words out of them. Each project keeps its own specifics: risk areas
in `.avflow/project.toml`, test environments and languages in its `CLAUDE.md`, and its own skills in
`.claude/skills/<project>-…/`.

**What avflow is not**

- **Not an agent.** It writes no code; Claude Code is the agent.
- **Not a replacement for CI or human review.** CI still judges quality, and merging is always a person's decision.
- **Not a ticket system.** Redmine (Jira later) still holds the tickets; avflow is the controlled door through which the agent works with them.

**Today and next**

| | Today (3.x) | Planned |
|---|---|---|
| Ticket system | Redmine | Jira, GitLab Issues, GitHub Issues (adapter architecture and handling rules are ready) |
| Repository and CI | GitLab | GitHub (`gh`, GitHub Actions) |
| Coding agent | Claude Code (CLI and the Code tab of Claude Desktop) | Other agents such as Codex — the MCP server already works with any MCP client; skills, hooks and setup would need an agent adapter |

## Plugin

| Plugin | Contents |
|---|---|
| `avflow` | Skills: `tickets`, `workflow`, `qa-agent`, `ticket-writer`, `zoom-out`, `triage`, `incident`, `release`, `glossary`, `adr` · Commands: `/avflow:next-ticket`, `/avflow:check` |

Installed automatically by `avflow setup`. Manual install in Claude Code:

```
/plugin marketplace add <git URL of this repository>
/plugin install avflow@avflow
```

The plugin expects the `avflow-tickets` MCP server, registered by `avflow setup` (tokens are stored in the OS keyring, never in this repository).

To release a new version: change the skills, bump `version` in `plugins/avflow/.claude-plugin/plugin.json`, merge. Team members update with `/plugin update` (or reinstall).
