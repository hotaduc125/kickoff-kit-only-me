# Installing avflow (team members)

You need: **git**, **Claude Code**, the **GitHub CLI** (`brew install gh` / `winget install GitHub.cli`, then `gh auth login` and `gh auth setup-git`), read access to the avflow marketplace repository, and your own ticket-system token.

1. Get the release files: `gh release download v<version> --repo <owner>/avflow-marketplace` (or from the PM). You get the wheel `avflow-<version>-py3-none-any.whl`, `bootstrap.sh` (macOS) and `bootstrap.ps1` (Windows).
2. Run:
   - macOS: `./bootstrap.sh ./avflow-<version>-py3-none-any.whl`
   - Windows (PowerShell): `powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 .\avflow-<version>-py3-none-any.whl`
3. Setup shows the **team settings** that come with the release (Redmine, GitLab, workflow, models, monitor) and asks only for what is yours:
   - your own **Redmine API key** (typed hidden, checked at once, stored in the OS keyring);
   - your **GitLab login**, if you are not signed in yet.
   Everything else is decided by the team. `avflow setup --advanced` asks every setting again and saves your answers as personal overrides — use it only when the PM agrees.
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
- **Statuses:** the team settings map avflow's steps to the statuses your Redmine already has (for Enclave: Ready → New, In progress → In Progress, In review → In Code Review, Ready for test → Ready for testing). `avflow init` writes the same names into the CI job, so no CI variables are needed for them.
- **Risk area, Hotspot:** without custom fields, avflow reads them from the "Size and mode" line of the ticket description (`Risk area: …`, `Hotspot: …`); a risk area the agent adds is kept in a private note starting with `[avflow]`. `Machine-side: yes` on older tickets is read as the team's area (Enclave: Machine control). There are no modes any more.
- **Private notes still need the right role permissions** (an admin setting). Check with a customer test account that private notes are not visible before using real data.

## Team settings and personal overrides
The PM keeps the team settings in the development repository; each release carries them, and `avflow update` brings changes to every machine. Your own file (`~/.avflow/config.toml`) holds only what you changed yourself.
- `avflow config` shows every setting and marks your personal ones (← personal).
- `avflow config --reset` removes your personal overrides; then run `avflow setup`.

## Changing your answers
- **Ticket system, URL or token** (for example a mistyped Redmine URL): run `avflow setup` again. Your previous answers are shown in brackets — press Enter to keep them, type to change. The token is always asked again and checked; when the URL changes, the old token is removed from the keyring.
- **See your configuration**: `avflow config` (the token is never shown, only whether one is stored).
- **Other values** (for example the protected branches under `[workflow]`): `avflow config --edit`, then `avflow check`. Do not change the Redmine URL by hand — the token is tied to it.

## Switching workflow
Run `avflow setup` again and choose the other workflow. avflow removes the one you had (Superpowers plugin or the Matt Pocock skills it installed) before installing the new one. Team skills, tickets and checks stay the same.

## If a git command is blocked
The guardrails stop commands such as `git push origin develop` or `git reset --hard` and tell Claude it may not run them. This is intended: merges to protected branches happen through merge requests. If you really need such a command, run it yourself in a terminal.
