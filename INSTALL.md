# Installing kickoff-kit (team members)

You need: **git**, **Claude Code**, read access to the kickoff-kit marketplace repository, and your own ticket-system token.

1. Get the release files from the PM: `kickoff_kit-<version>-py3-none-any.whl` and `bootstrap.sh` (macOS) or `bootstrap.ps1` (Windows).
2. Run:
   - macOS: `./bootstrap.sh ./kickoff_kit-<version>-py3-none-any.whl`
   - Windows (PowerShell): `.\bootstrap.ps1 .\kickoff_kit-<version>-py3-none-any.whl`
3. Answer the questions (ticket system, URL, your token — typed hidden and stored in the OS keyring; GitLab login).
4. At the end, `kickoff-kit doctor` shows a ✅/❌ table. Run it again any time.

If the marketplace check fails: ask the PM for read access, then sign in to the git host (GitHub: `gh auth login` and `gh auth setup-git`) and run `kickoff-kit setup` again.

Do not edit the installed skills: `kickoff-kit doctor` reports changed files. Updates come as new releases.
