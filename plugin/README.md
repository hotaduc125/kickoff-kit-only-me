# kickoff-kit marketplace

Claude Code plugin marketplace for the Enclave team workflow.

| Plugin | Contents |
|---|---|
| `kickoff-kit` | Skills: `tickets`, `choose-mode`, `qa-agent`, `ticket-writer`, `zoom-out` · Commands: `/kickoff-kit:next-ticket`, `/kickoff-kit:doctor` |

Installed automatically by `kickoff-kit setup`. Manual install in Claude Code:

```
/plugin marketplace add <git URL of this repository>
/plugin install kickoff-kit@kickoff-kit
```

The plugin expects the `kickoff-tickets` MCP server, registered by `kickoff-kit setup` (tokens are stored in the OS keyring, never in this repository).

To release a new version: change the skills, bump `version` in `plugins/kickoff-kit/.claude-plugin/plugin.json`, merge. Team members update with `/plugin update` (or reinstall).
