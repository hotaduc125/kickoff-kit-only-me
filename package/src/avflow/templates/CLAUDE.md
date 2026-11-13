# {project} — instructions for AI agents

Read this file first, then `docs/CONTEXT.md` (the project's domain glossary).

## Tools and skills (installed by `avflow setup`, not stored in this repository)

- Tickets: **only** through the `avflow-tickets` MCP server (skill `avflow:tickets`). Notes are always private.
- How every ticket runs and how to satisfy its required checks: `avflow:workflow`.
- Customer tickets: `avflow:triage`. Field problems: `avflow:incident`. Releases: `avflow:release`.
- Domain terms: `avflow:glossary`. Hard-to-reverse decisions: `avflow:adr`.
- Git guardrails block pushes to protected branches, force pushes, destructive commands and commits with secrets. If a command is blocked, tell the person; do not work around it.

## Build and test

<!-- TODO: the exact commands, e.g. `dotnet build`, `dotnet test`, `npm test` -->
- Build: `TODO`
- Test: `TODO`

## Risk areas

The files where a mistake reaches production, hardware or customers are the risk areas in `.avflow/project.toml`
(paths, owners, extra checks). The ticket tools apply them; `avflow risk check` validates the file and
`avflow risk files <paths>` shows which checks a change needs.

## Branches and commits

- Branch from `develop`: `feature/<ticket-id>-<short-name>` (or `fix/`, `hotfix/`).
- Commits and the merge request title contain `Refs #<ticket-id>` (CI checks it).
- Never push to `develop` or `main`; never merge your own merge request.
- Change only files in the ticket's scope; do not reformat unrelated code.

## Definition of done

Tests for each acceptance criterion · CI green · reviewed by a person (code owner for sensitive paths) · docs, `docs/CONTEXT.md` or an ADR updated when the design changed · handoff as a private note on the ticket.
