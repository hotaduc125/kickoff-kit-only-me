# avflow — development repository (private)

avflow is the team's harness around the coding agent: it connects the ticket system and repository, equips the agent with the member's chosen workflow and the team skills, enforces team rules in code (MCP server, git guardrails, skill integrity), and keeps every machine on the same version. The full "Why avflow" is in `package/README.md` and in the marketplace README.

| Folder | Content |
|---|---|
| `package/` | Python package: `avflow` (setup, doctor, uninstall) and `avflow-ticket-mcp` (MCP server, adapters) |
| `plugin/` | Source of the Claude Code plugin marketplace (skills, commands) |
| `scripts/` | `release.py`, bootstrap scripts (`.sh` macOS, `.ps1` Windows), reset scripts for testing (`reset-avflow.sh` / `.ps1`) |
| `docs/WINDOWS_TEST.md` | Step-by-step Windows test checklist |
| `INSTALL.md` | Team-facing install guide (copied into each release) |

## Release
1. Bump the version in `package/pyproject.toml`, `package/src/avflow/__init__.py` and `plugin/plugins/avflow/.claude-plugin/plugin.json` (they must match). Commit and push this repository.
2. `python scripts/release.py --marketplace-url <release repo URL> --publish-to <local clone of the release repo> --push`
   — runs the tests, builds the wheel, syncs the plugin, commits, tags, pushes, and creates the GitHub Release with the wheel (needs `gh`).
3. Tell the team: `avflow update`.

First install only: send new members the wheel, the bootstrap script and INSTALL.md (later updates come through `avflow update`).

The **release repository** contains only the released plugin marketplace; team members get read access to it, never to this repository. The wheel embeds the checksums of the released plugin, so `avflow check` reports any locally modified skill.
