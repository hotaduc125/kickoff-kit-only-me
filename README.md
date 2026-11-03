# kickoff-kit — development repository (private)

| Folder | Content |
|---|---|
| `package/` | Python package: `kickoff-kit` (setup, doctor, uninstall) and `kickoff-ticket-mcp` (MCP server, adapters) |
| `plugin/` | Source of the Claude Code plugin marketplace (skills, commands) |
| `scripts/` | `release.py`, bootstrap scripts |
| `INSTALL.md` | Team-facing install guide (copied into each release) |

## Release
1. Bump the version in `package/pyproject.toml`, `package/src/kickoff_kit/__init__.py` and `plugin/plugins/kickoff-kit/.claude-plugin/plugin.json` (they must match). Commit and push this repository.
2. `python scripts/release.py --marketplace-url <release repo URL> --publish-to <local clone of the release repo> --push`
   — runs the tests, builds the wheel, syncs the plugin, commits, tags, pushes, and creates the GitHub Release with the wheel (needs `gh`).
3. Tell the team: `kickoff-kit update`.

First install only: send new members the wheel, the bootstrap script and INSTALL.md (later updates come through `kickoff-kit update`).

The **release repository** contains only the released plugin marketplace; team members get read access to it, never to this repository. The wheel embeds the checksums of the released plugin, so `kickoff-kit doctor` reports any locally modified skill.
