# {project} — instructions for AI agents

Read this file first, then `docs/CONTEXT.md` (the project's domain glossary).

## Tools and skills (installed by `avflow setup`, not stored in this repository)

- Tickets: **only** through the `avflow-tickets` MCP server (skill `avflow:tickets`). Notes are always private.
- Before any work: `avflow:choose-mode`; what each mode requires: `avflow:workflow`.
- Customer tickets: `avflow:triage`. Field problems: `avflow:incident`. Releases: `avflow:release`.
- Domain terms: `avflow:glossary`. Hard-to-reverse decisions: `avflow:adr`.
- Git guardrails block pushes to protected branches, force pushes, destructive commands and commits with secrets. If a command is blocked, tell the person; do not work around it.

## Build and test

<!-- TODO: the exact commands, e.g. `dotnet build`, `dotnet test`, `npm test` -->
- Build: `TODO`
- Test: `TODO`

## Sensitive paths (always mode FULL, code-owner review)

<!-- TODO: list the files or folders where a mistake reaches production, hardware or customers -->
- `TODO`

## Branches and commits

- Branch from `develop`: `feature/<ticket-id>-<short-name>` (or `fix/`, `hotfix/`).
- Commits and the merge request title contain `Refs #<ticket-id>` (CI checks it).
- Never push to `develop` or `main`; never merge your own merge request.
- Change only files in the ticket's scope; do not reformat unrelated code.

## Definition of done

Tests for each acceptance criterion · CI green · reviewed by a person (code owner for sensitive paths) · docs, `docs/CONTEXT.md` or an ADR updated when the design changed · handoff as a private note on the ticket.
