# Installing avflow (team members)

You need: **git**, **Claude Code**, the **GitHub CLI** (`brew install gh` / `winget install GitHub.cli`, then `gh auth login` and `gh auth setup-git`), read access to the avflow marketplace repository, and your own ticket-system token.

1. Get the release files: `gh release download v<version> --repo <owner>/avflow-marketplace` (or from the PM). You get the wheel `avflow-<version>-py3-none-any.whl`, `bootstrap.sh` (macOS) and `bootstrap.ps1` (Windows).
2. Run:
   - macOS: `./bootstrap.sh ./avflow-<version>-py3-none-any.whl`
   - Windows (PowerShell): `powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 .\avflow-<version>-py3-none-any.whl`
3. Answer the questions:
   - ticket system, URL and **your own** token (typed hidden, stored in the OS keyring);
   - GitLab host and login;
   - **coding workflow**: *Superpowers* or *Matt Pocock's skills* — one or the other, never both (you can switch later by running setup again);
   - **git guardrails** (recommended: yes) — blocks push to protected branches, force push, `reset --hard`, commits with secrets and similar; pushing your own feature branch still works;
   - **models for the role subagents** — plan, implement, review (`opus`, `sonnet`, `haiku` or `inherit`); press Enter to keep the defaults (Opus, Sonnet, Opus). Change them later with `avflow setup` or `avflow config --edit` followed by `avflow setup`;
   - **context monitor** (recommended: yes) and its thresholds in thousands of tokens (defaults: warn at 300, limit at 400). Past the warning you and the agent are told to plan a handoff; past the limit, to write the handoff and start a new session. `avflow usage` shows the history.
4. At the end, `avflow check` shows a ✅/❌ table. Run it again any time.
5. Open a **new** terminal window (so the `avflow` command is on your PATH), then start a new Claude Code session.

## Where it works
- **Claude Code CLI**: everything.
- **Claude Desktop, Code tab**: uses the same MCP server, skills and plugins. Install and update are always done in a terminal; if `/avflow:…` commands do not appear in the Code tab, ask in words (for example "run avflow check").
- **Claude Desktop, Chat tab**: not used for this workflow.

## Windows notes
- If PowerShell refuses to run the script, use `-ExecutionPolicy Bypass` as above, or run `Unblock-File .\bootstrap.ps1` first.
- The token is stored in **Credential Manager** (Windows Credentials, entry containing `avflow`).
- Company antivirus or proxy settings can block downloads; send the exact message to the PM.

If the marketplace check fails: ask the PM for read access, then sign in to the git host (GitHub: `gh auth login` and `gh auth setup-git`) and run `avflow setup` again.

## Updating
When the PM announces a new release, run:

```
avflow update
```

It downloads the latest release, installs it, updates the Claude Code plugin and runs the doctor. `avflow update --check` only tells you whether an update is available.

Do not edit the installed skills: `avflow check` reports changed files.

## Redmine without admin rights
avflow works on a standard Redmine:
- **Statuses:** if Ready / In progress / In review do not exist, setup offers Redmine's default statuses (Ready → New, In progress → In Progress, In review → Feedback, Ready for test → Resolved). In GitLab, set the CI/CD variables `AVFLOW_STATUS_IN_REVIEW=Feedback` and `AVFLOW_STATUS_READY_FOR_TEST=Resolved` so the CI job uses the same names.
- **Mode, Machine-side, Hotspot:** without custom fields, avflow reads Machine-side and Hotspot from the "Size and mode" line of the ticket description and keeps the confirmed mode in a private note starting with `[avflow]`.
- **Private notes still need the right role permissions** (an admin setting). Check with a customer test account that private notes are not visible before using real data.

## Changing your answers
- **Ticket system, URL or token** (for example a mistyped Redmine URL): run `avflow setup` again. Your previous answers are shown in brackets — press Enter to keep them, type to change. The token is always asked again and checked; when the URL changes, the old token is removed from the keyring.
- **See your configuration**: `avflow config` (the token is never shown, only whether one is stored).
- **Other values** (for example the protected branches under `[workflow]`): `avflow config --edit`, then `avflow check`. Do not change the Redmine URL by hand — the token is tied to it.

## Switching workflow
Run `avflow setup` again and choose the other workflow. avflow removes the one you had (Superpowers plugin or the Matt Pocock skills it installed) before installing the new one. Team skills, tickets and checks stay the same.

## If a git command is blocked
The guardrails stop commands such as `git push origin develop` or `git reset --hard` and tell Claude it may not run them. This is intended: merges to protected branches happen through merge requests. If you really need such a command, run it yourself in a terminal.
