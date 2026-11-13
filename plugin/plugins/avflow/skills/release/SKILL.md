---
name: release
description: Use when preparing a release candidate or a production release — collect what is in it from the merged tickets, write release notes and the acceptance checklist for the customer's engineer, confirm the pre-release checks and the rollback plan. Uses the avflow release-notes command.
---

# Release

A release is accepted in the customer's environment by the customer's engineer, so everything they need must be
written down: what changed, what to check, and how to go back. If the project has its own release skill
(`<project>-…`) or lists release checks in its `CLAUDE.md`, follow them as well.

## Rules

- You prepare; a **person** tags, builds and installs the release, and moves tickets to Resolved after acceptance.
- Never push tags or to protected branches (the git guardrails block it anyway).

## Steps

1. **Range.** Find the previous release tag and the commit to release (for a release candidate, the head of `develop`; for production, the accepted release-candidate commit).
2. **Notes.** Run `avflow release-notes --from <previous-tag> --to <commit>`. It lists every ticket referenced by the commits (`Refs #id`), grouped by type, with the risk areas of each ticket marked (for example **[Payments]**), and warns about commits without a ticket and tickets not yet *Ready for test*.
3. **Review the warnings.** A commit without a ticket, or a ticket still *In progress*, must be explained or removed before the release.
4. **Acceptance checklist.** For each ticket, turn its acceptance criteria into checks the customer's engineer can run in their environment. Tickets with a risk area come first and need the most precise checks.
5. **Pre-release checks.** Confirm and record: CI green on the release commit; regression tests green (including the project's own test environments listed in its `CLAUDE.md`); every required check of the high-risk changes done on their merge requests (`checklist:` items ticked by a person); translations reviewed if the UI changed.
6. **Rollback.** Write how to return to the previous version (one step) and what data or configuration, if any, does not roll back.
7. **Post.** Put the release notes and checklist in the merge request or release ticket, and a short private note on each included ticket with the release version.

## Release notes template

```markdown
# <Product> <version> — release notes
Date · previous version · release type (candidate / production)

## Changes
<from avflow release-notes>

## Acceptance checklist (customer engineer)
- [ ] …

## Pre-release checks
- [ ] CI green · [ ] regression tests · [ ] high-risk changes: required checks done · [ ] translations

## Rollback
…
```
