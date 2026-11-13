# avflow — Windows test checklist (3.0)

Run on a Windows 10/11 PC that has never had avflow, ideally a team member's machine, with the PM watching
(screen share). Write the result of every step: ✅, ❌ (copy the exact message), or ➖ (skipped).

Use **PowerShell** (not Command Prompt). Never paste tokens into chat or into this file. Sections 1–7 check the
installation; section 8 checks the 3.0 project commands in a clone of `avflow-sandbox`; section 9 the update from 2.x.
The functional tests (tickets, risk areas, CI) are in `docs/test-plan.md` and are the same on every OS.

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
| 0.8 | Redmine API key ready | Redmine → *My account* → *API access key* | you can copy it (do not paste it anywhere but setup) |

## 1. Install (first time)

| # | Check | Command / action | Expected |
|---|---|---|---|
| 1.1 | Get the files | `gh release download v3.0.0 --repo alvin-enc/avflow-marketplace` | the wheel, `bootstrap.ps1`, `bootstrap.sh` and `INSTALL.md` in one folder |
| 1.2 | Run bootstrap | `powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 .\avflow-3.0.0-py3-none-any.whl` | uv installed if missing, then `avflow 3.0.0 — setup` |
| 1.3 | Team settings | — | setup prints the **Team settings** (Redmine URL, GitLab host, statuses, workflow, models, monitor) and does **not** ask for the URL, the workflow, the models or the guardrails |
| 1.4 | Redmine API key | paste your **own** key (input hidden) | `✅ Connected as <your name>` |
| 1.5 | Token storage | Control Panel → Credential Manager → Windows Credentials | an entry containing `avflow` |
| 1.6 | GitLab | — | `✅ GitLab login (gitlab.enclave.vn)`, or a hint how to sign in with `glab auth login` (then run `avflow setup` again) |
| 1.7 | Claude Code steps | — | ✅ MCP registered, permissions, Superpowers, avflow plugin, handoff, three role subagents, git guardrails hook, context monitor hook |
| 1.8 | Final check | printed at the end | all ✅ (➖ lines are fine), including `Workflow:`, `Git guardrails hook`, `Context monitor`, the three subagents with models opus / sonnet / opus and `Plugin integrity: v3.0.0` |

## 2. After install

| # | Check | Command | Expected |
|---|---|---|---|
| 2.1 | Commands on PATH (new window) | `avflow --version` | `3.0.0` |
| 2.2 | Check again | `avflow check` | all ✅, symbols display correctly (no `?` or crash) |
| 2.3 | Configuration | `avflow config` | `[tickets]`, `[repo]`, `[workflow]`, `[models]`, `[monitor]`; *"Token stored in the OS keyring … : yes"*; **no** token value |
| 2.4 | MCP list | `claude mcp list` | `avflow-tickets` connected |
| 2.5 | Plugin list | `claude plugin list` | avflow and superpowers |
| 2.6 | Role subagents | `dir $env:USERPROFILE\.claude\agents` | `avflow-planner.md`, `avflow-implementer.md`, `avflow-reviewer.md` |
| 2.7 | Context monitor | after a short Claude Code session: `avflow usage` | the session listed with its peak context and model; subagent calls listed if any ran |
| 2.8 | Files | `dir $env:USERPROFILE\.claude\skills\handoff` and `dir $env:USERPROFILE\.avflow` | both exist; no token in `config.toml` |

## 3. In Claude Code (CLI, new session)

| # | Check | Type | Expected |
|---|---|---|---|
| 3.1 | MCP tools | `/mcp` | avflow-tickets, **11 tools** (including `assess_plan` and `review_requirements`) |
| 3.2 | Read tool | "call the whoami tool of avflow-tickets" | runs without asking; returns your account |
| 3.3 | Write tool | ask to add a private note on a **test** ticket | Claude Code asks permission first |
| 3.4 | Commands | `/avflow:check` and `/avflow:next-ticket` | both listed and work; `next-ticket` does **not** ask for a Mode |
| 3.5 | Check output via Claude | `/avflow:check` | output readable (no encoding error) |
| 3.6 | No 2.x skill | type `/` and look for `choose-mode` | not listed |

## 3b. Git guardrails (in Claude Code)

| # | Check | Ask Claude to run | Expected |
|---|---|---|---|
| 3b.1 | Protected branch | `git push origin develop` | blocked with a "avflow git guardrails" message |
| 3b.2 | Destructive command | `git reset --hard` | blocked |
| 3b.3 | Feature branch | on a test feature branch: `git push -u origin <branch>` | allowed |
| 3b.4 | Secret in a commit | add a file containing `token: ghp_` + 36 letters, stage it, ask Claude to commit | blocked; message names the file and line, never the value |

## 3c. Personal settings (advanced setup)

| # | Check | Action | Expected |
|---|---|---|---|
| 3c.1 | Switch workflow | `avflow setup --advanced`, choose **2 (Matt Pocock's skills)** | *"Superpowers removed"*, the Pocock skills installed under `…\.claude\skills` |
| 3c.2 | Check | `avflow check`; `avflow config` | `Workflow: Matt Pocock's skills`, no "both installed" error; `profile` marked *← personal* |
| 3c.3 | Back to the team settings | `avflow config --reset`, then `avflow setup` | *"Removed Matt Pocock workflow skills: …"*, Superpowers back; no *← personal* line |

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
| 6.1 | Edit a skill | add a line to `…\.claude\plugins\cache\avflow\avflow\3.0.0\skills\tickets\SKILL.md` | `avflow check` → ❌ modified: skills/tickets/SKILL.md |
| 6.2 | Restore | `/plugin uninstall avflow@avflow`, then `/plugin install avflow@avflow` | check → ✅ |
| 6.3 | Edit a subagent | add a line to `$env:USERPROFILE\.claude\agents\avflow-reviewer.md` | `avflow check` → ❌ *edited by hand — run avflow setup*; after `avflow setup` → ✅ |

## 7. Reset

| # | Check | Command | Expected |
|---|---|---|---|
| 7.1 | Reset | `powershell -ExecutionPolicy Bypass -File .\reset-avflow.ps1` | `✅ Clean — ready for a first install.` |
| 7.2 | Credential Manager | open it again | no `avflow` entry |
| 7.3 | Agents | `dir $env:USERPROFILE\.claude\agents` | no `avflow-*.md` |
| 7.4 | Reinstall | repeat section 1 | works as the first time |

## 8. Project commands (3.0)

In a clone of `avflow-sandbox` on a new feature branch (`git switch -c windows-test`). Do not push this branch.

| # | Check | Command | Expected |
|---|---|---|---|
| 8.1 | Init | `avflow init --project avflow-sandbox` | `Stack presets: python`; the files of test-plan B1 created, including `.avflow\project.toml`, `ci\avflow_risk.py`, `ci\avflow_risk_check.py`; no crash on paths |
| 8.2 | Line endings | `git diff --stat`; `git ls-files --eol .avflow/project.toml CODEOWNERS` | no CRLF warnings; files listed as `i/lf` |
| 8.3 | Profile | copy `avflow-profile.example.toml` over `.avflow\project.toml`, then `avflow risk check` | `✅ .avflow/project.toml: 7 risk areas (avflow-sandbox)` (forward slashes in the message) |
| 8.4 | Files, Windows path | `avflow risk files src\sandbox\machine.py` | `Risk areas: Machine control (files)`; required checks include plan confirmation and code owner approval — the backslash path matches |
| 8.5 | Files, no area | `avflow risk files src\sandbox\report.py` | `Required checks: none — standard flow …` |
| 8.6 | Sync | `avflow risk sync` | `CODEOWNERS updated from the profile`; the avflow block lists `/src/sandbox/machine.py @colleague` (or the paths in the profile) with forward slashes |
| 8.7 | Sync again | `avflow risk sync` | `already up to date` |
| 8.8 | Report | `avflow report --days 7` | prints without an encoding error; a `## Risk` section if any ticket was reviewed in the period |
| 8.9 | Clean up | `git switch develop`; `git branch -D windows-test` | — |

## 9. Update from 2.x (only on a PC that still has 2.6.x)

| # | Check | Command | Expected |
|---|---|---|---|
| 9.1 | Update | `avflow update` | installs 3.0.0, plugin updated |
| 9.2 | Check | `avflow check` | the three subagents ❌ *edited by hand — run avflow setup* (3.0 changed them) |
| 9.3 | Setup once | `avflow setup` | asks nothing new; `check` all ✅ |
| 9.4 | New session | `/avflow:next-ticket` | no Mode question; `choose-mode` no longer listed |

## Known Windows points to watch

- **`claude` installed by npm** is `claude.cmd`; avflow resolves it through `shutil.which`.
- **Execution policy**: if PowerShell refuses to run the script, use `-ExecutionPolicy Bypass` as above, or `Unblock-File .\bootstrap.ps1`.
- **New window**: after the first install, open a new PowerShell window so PATH includes `%USERPROFILE%\.local\bin`.
- **Paths**: avflow accepts `src\a.py` and `src/a.py`; the profile, CODEOWNERS and messages always use `/`.
- **Antivirus / company policy** may block `uv` or scripts — note the exact message.
- **Proxy**: if downloads hang, note whether the PC is behind a company proxy.
