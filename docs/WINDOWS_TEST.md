# avflow — Windows test checklist

Run on a Windows 10/11 PC that has never had avflow, ideally a team member's machine, with the PM watching
(screen share). Write the result of every step: ✅, ❌ (copy the exact message), or ➖ (skipped).

Use **PowerShell** (not Command Prompt). Never paste tokens into chat or into this file.

## 0. Prerequisites

| # | Check | Command | Expected |
|---|---|---|---|
| 0.1 | Git | `git --version` | a version |
| 0.2 | Claude Code CLI | `claude --version` | a version (installed with the native installer or npm) |
| 0.3 | Where `claude` comes from | `(Get-Command claude).Source` | note it: `…\claude.exe` or `…\npm\claude.cmd` |
| 0.4 | GitHub CLI signed in | `gh auth status` | logged in to github.com |
| 0.5 | gh used by git | `gh auth setup-git` | no error |
| 0.6 | Access to the release repo | `git ls-remote https://github.com/alvin-enc/avflow-marketplace.git` | branch list, no password prompt |
| 0.7 | GitLab CLI | `glab --version` | a version (if missing: `winget install GLab.GLab`) |

## 1. Install (first time)

| # | Check | Command / action | Expected |
|---|---|---|---|
| 1.1 | Get the files | `gh release download v<version> --repo alvin-enc/avflow-marketplace` | the wheel, `bootstrap.ps1`, `bootstrap.sh` and `INSTALL.md` in one folder |
| 1.2 | Run bootstrap | `powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 .\avflow-<version>-py3-none-any.whl` | uv installed if missing, then the setup questions |
| 1.3 | Ticket system | choose `1` (Redmine), enter URL and **own** API key (hidden) | `✅ Connected as …` |
| 1.4 | Token storage | Control Panel → Credential Manager → Windows Credentials | an entry containing `avflow` |
| 1.5 | GitLab | host `gitlab.enclave.vn` | `✅ GitLab login` (or the login flow opens) |
| 1.6 | Workflow and guardrails | choose a workflow; answer `y` to git guardrails | asked once each |
| 1.7 | Claude Code steps | — | ✅ MCP registered, permissions, workflow (Superpowers **or** Matt Pocock's skills), avflow plugin, handoff, git guardrails enabled |
| 1.8 | Final check | printed at the end | all ✅ (➖ lines are fine), including `Workflow:` and `Git guardrails hook` |

## 2. After install

| # | Check | Command | Expected |
|---|---|---|---|
| 2.1 | Commands on PATH (new window) | `avflow --version` | the version |
| 2.2 | Check again | `avflow check` | all ✅, symbols display correctly (no `?` or crash) |
| 2.3 | MCP list | `claude mcp list` | `avflow-tickets` connected |
| 2.4 | Plugin list | `claude plugin list` | avflow and superpowers |
| 2.4b | Role subagents | `dir $env:USERPROFILE\.claude\agents` | `avflow-planner.md`, `avflow-implementer.md`, `avflow-reviewer.md`; `avflow check` shows each with its model |
| 2.4c | Context monitor | after a short Claude Code session: `avflow usage` | the session listed with its peak context and model; subagent calls listed if any ran |
| 2.5 | Files | `dir $env:USERPROFILE\.claude\skills\handoff` and `dir $env:USERPROFILE\.avflow` | both exist; no token in `config.toml` |

## 3. In Claude Code (CLI, new session)

| # | Check | Type | Expected |
|---|---|---|---|
| 3.1 | MCP tools | `/mcp` | avflow-tickets, 9 tools |
| 3.2 | Read tool | "call the whoami tool of avflow-tickets" | runs without asking; returns your account |
| 3.3 | Write tool | ask to add a private note on a **test** ticket | Claude Code asks permission first |
| 3.4 | Commands | `/avflow:check` and `/avflow:next-ticket` | both listed and work |
| 3.5 | Check output via Claude | `/avflow:check` | output readable (no encoding error) |

## 3b. Git guardrails (in Claude Code)

| # | Check | Ask Claude to run | Expected |
|---|---|---|---|
| 3b.1 | Protected branch | `git push origin develop` | blocked with a "avflow git guardrails" message |
| 3b.2 | Destructive command | `git reset --hard` | blocked |
| 3b.3 | Feature branch | on a test feature branch: `git push -u origin <branch>` | allowed |
| 3b.4 | Secret in a commit | add a file containing `token: ghp_` + 36 letters, stage it, ask Claude to commit | blocked; message names the file and line, never the value |

## 3c. Switch workflow

| # | Check | Action | Expected |
|---|---|---|---|
| 3c.1 | Switch | `avflow setup`, choose the other workflow | the previous one is removed, the new one installed |
| 3c.2 | Check | `avflow check` | `Workflow:` shows the new choice; no "both installed" error |

## 4. Claude Desktop — Code tab (optional)

| # | Check | Expected |
|---|---|---|
| 4.1 | New session, "call whoami of avflow-tickets" | returns your account |
| 4.2 | Type `/avflow:` | commands listed (if not, note it — plugin commands may be CLI-only) |

## 5. Update

| # | Check | Command | Expected |
|---|---|---|---|
| 5.1 | When a newer release exists | `avflow update --check` | "Update available" |
| 5.2 | Update | `avflow update` | download, install, plugin updated, check runs |
| 5.3 | Version | `avflow --version` | the new version |

## 6. Integrity

| # | Check | Action | Expected |
|---|---|---|---|
| 6.1 | Edit a skill | add a line to `…\.claude\plugins\cache\avflow\avflow\<version>\skills\tickets\SKILL.md` | `avflow check` → ❌ modified: skills/tickets/SKILL.md |
| 6.2 | Restore | `/plugin uninstall avflow@avflow`, then `/plugin install avflow@avflow` | check → ✅ |

## 7. Reset

| # | Check | Command | Expected |
|---|---|---|---|
| 7.1 | Reset | `powershell -ExecutionPolicy Bypass -File .\reset-avflow.ps1` | `✅ Clean — ready for a first install.` |
| 7.2 | Credential Manager | open it again | no `avflow` entry |
| 7.3 | Reinstall | repeat section 1 | works as the first time |

## Known Windows points to watch

- **`claude` installed by npm** is `claude.cmd`; avflow 1.2.3+ resolves it (older versions fail with "command not found").
- **Execution policy**: if PowerShell refuses to run the script, use `-ExecutionPolicy Bypass` as above, or `Unblock-File .\bootstrap.ps1`.
- **New window**: after the first install, open a new PowerShell window so PATH includes `%USERPROFILE%\.local\bin`.
- **Antivirus / company policy** may block `uv` or scripts — note the exact message.
- **Proxy**: if downloads hang, note whether the PC is behind a company proxy.
