# kickoff-kit

One command sets up the team's AI coding workflow on a developer's machine:

- **ticket system** (v1: Redmine; planned: Jira, GitLab Issues, GitHub Issues) through the `kickoff-tickets` MCP server —
  nine tools, the same for every system, with the team rules enforced in code;
- **repository and CI/CD** (v1: GitLab via `glab`; planned: GitHub via `gh`);
- **Claude Code** with **Superpowers**, **Matt Pocock's** `handoff` skill (pinned commit) and the **kickoff-kit plugin**
  (team skills `tickets`, `choose-mode`, `qa-agent`, `ticket-writer`, `zoom-out`, commands `/kickoff-kit:next-ticket`, `/kickoff-kit:doctor`);
- a final **doctor** check (whoami on the ticket system, MCP registration, GitLab login, plugins, skills).

Tokens are asked once, verified, and stored in the **OS keyring** (macOS Keychain, Windows Credential Manager). They are
never written to files and never pass through the AI conversation.

## Install (team members)

macOS:
```bash
./bootstrap.sh <wheel file or registry URL>
```
Windows (PowerShell):
```powershell
.\bootstrap.ps1 <wheel file or registry URL>
```
The script installs uv if needed, installs kickoff-kit, then runs `kickoff-kit setup`.

Manual alternative: `uv tool install <wheel or package>` then `kickoff-kit setup`.

## Commands
| Command | |
|---|---|
| `kickoff-kit setup` | Choose tools, enter tokens, configure everything (safe to run again) |
| `kickoff-kit doctor` | Check that everything works (also tells you when an update is available) |
| `kickoff-kit update` | Install the latest release and update the plugin (`--check` only reports) |
| `kickoff-kit uninstall` | Remove the configuration, token and MCP registration (keeps Superpowers) |

## The nine ticket tools
`whoami` · `list_my_ready_tickets` · `get_ticket` · `add_private_note` (always private) · `set_fields` (Mode,
Machine-side, Hotspot) · `find_hotspot_conflicts` · `start_ticket` (refused if not assigned, blocked, not Ready or no Mode)
· `submit_for_review` (needs the merge / pull request URL) · `create_bug_draft` (private draft).

## Ticket system setup (Redmine)
REST API enabled (Administration → Settings → API); statuses Ready, In progress, In review; custom fields Mode (list),
Machine-side (boolean), Hotspot (text); tracker Bug; the customer role must not view private notes.

## Development
`uv run pytest` · adapters: see `docs/ADAPTERS.md` · release: tag `vX.Y.Z` → CI publishes the package.

Configuration: `~/.kickoff-kit/config.toml` (no secrets) · audit log: `~/.kickoff-kit/audit.log`.
