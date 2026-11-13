# avflow — instructions for AI agents working on this repository

Read this file, then `docs/decisions.md` (why things are the way they are). For the current piece of work, read its
design: `docs/design/avflow-3.0.md`.

## What avflow is

A team harness around Claude Code, installed with one command on each developer's machine. It **connects** the ticket
system (Redmine) and the repository/CI (GitLab), **equips** the agent (the team's coding workflow, team skills, role
subagents), **guards** (ticket rules in code, git guardrails, secret scanning, plugin integrity) and **keeps machines in
step** (`avflow check`, `avflow update`, team settings shipped with each release). It is used by Enclave (an IT company,
ODC model); the first project using it is Mateo (WPF machine software for the customer WKKM, who shares the Redmine).

The repository owner is the PM (Alvin). Members install releases; they never see this repository.

## Repository layout

| Path | What |
|---|---|
| `package/src/avflow/` | The Python package: CLI (`cli.py`), setup steps (`setup_steps.py`), configuration (`config.py`), risk profile and required checks (`risk.py`), MCP server (`tickets/`), git guardrails hook (`git_guard.py`), context monitor hook (`monitor.py`), `init_repo.py`, `release_notes.py`, `report.py`, `integrity.py` |
| `package/src/avflow/tickets/` | MCP server `avflow-tickets`: `core.py` (the rules), `adapters/redmine.py` (Redmine REST), `repo.py` (git / glab: profile, changed files, MR notes), `server.py`, `audit.py` |
| `package/src/avflow/agents/` | Role subagent templates (`{model}` placeholder), generated into `~/.claude/agents/` by setup |
| `package/src/avflow/templates/` | Files written into project repos by `avflow init` |
| `package/src/avflow/data/` | `team.toml` (generic default; release.py replaces it with the team file), `presets.toml` (stack presets; bump `version` when one gains paths), `plugin_manifest.json` (written by release.py) |
| `package/tests/` | pytest suite; `fake_redmine.py` is an in-memory Redmine, `fake_repo.py` a project repository (profile, changed files, MR notes) |
| `plugin/` | The Claude Code plugin marketplace source: team skills and commands (`plugins/avflow/`) |
| `team/avflow-team.toml` | **Team settings** for Enclave (URL, statuses, fields, workflow, models, monitor) — embedded into each release |
| `scripts/` | `release.py`, `bootstrap.sh` / `.ps1` (install), `reset-avflow.sh` / `.ps1` (remove every trace, including old names) |
| `docs/` | Decisions, designs, user guide, test plan, Windows test checklist |
| `examples/avflow-sandbox/` | Small sample project (Python) with ready-made test tickets, a profile example and a sample project skill, used by the test plan |
| `examples/mateo-project-skills/` | Drafts of Mateo's own project files (risk area, CLAUDE.md section, skills) — not shipped; copied into Mateo by the PM |

## Commands

```bash
cd package && python3 -m pytest -q                 # all tests (must stay green; ~300 tests, ~1 s)
cd package && pip wheel . --no-deps -w /tmp/whl    # build a wheel to try locally
python3 scripts/release.py --marketplace-url https://github.com/alvin-enc/avflow-marketplace.git \
        --publish-to /tmp/fake-marketplace --skip-tests     # dry-run a release (no --push)
```

A real release: `release.py … --publish-to ../avflow-marketplace --push` (the PM does this; needs `gh` signed in).
`release.py` runs the tests, validates `team/avflow-team.toml`, embeds it and the plugin checksums, builds the wheel,
syncs the plugin to the marketplace repo, tags, and creates a GitHub Release with the wheel, bootstrap scripts and INSTALL.md.

## Rules for changing avflow

- **Version** lives in three places and must match: `package/pyproject.toml`, `package/src/avflow/__init__.py`,
  `plugin/plugins/avflow/.claude-plugin/plugin.json`. Bump only when the PM asks or a release is planned.
- **Never break `avflow update`.** Members update from the previous release; test the update path mentally for every
  change to setup, config format, file locations or the plugin. Old config files must still load (unknown keys ignored).
- **The static name check** (`tests/test_update.py::test_every_setup_step_name_resolves`) catches undefined names in
  rarely-run code (it once caught a renamed constant that broke `update`). Keep it passing; add new modules to its list.
- **Secrets:** tokens only in the OS keyring (`config.set_secret`/`get_secret`), never in files, logs, tests or output.
  Never print a token; `avflow config` shows only whether one is stored.
- **Ticket rules live in `tickets/core.py`**, not in prompts: private notes only, the allowed status moves, the allowed
  fields, refusals. Tool descriptions must not tempt the agent to work around them.
- **Team settings vs personal:** organisation decisions go in `team/avflow-team.toml`; `~/.avflow/config.toml` keeps only
  personal overrides (`Config.save` writes the diff). Do not add setup questions for team decisions; use `--advanced`.
- **Cross-platform:** macOS and Windows are both first-class. Resolve external programs through `setup_steps.run`
  (uses `shutil.which`, needed for `claude.cmd`), keep output UTF-8 safe, keep `bootstrap.ps1` and `reset-avflow.ps1` in
  step with their `.sh` twins. Reset scripts must keep removing old names (kickoff-kit, htkm-kit, redmine-agent).
- **Hooks** (`avflow-git-guard`, `avflow-monitor`) must never crash Claude Code: on any unexpected input, allow and exit 0.
  Only exit 2 for a deliberate block, with a clear message.
- **Skills are generic team skills.** No project-specific words (machine, panel, test bench, Mateo) in avflow skills —
  those belong to the project's own repository: its `.avflow/project.toml`, the *Test environments and languages*
  section of its `CLAUDE.md`, and its own skills. `tests/test_skill_words.py` enforces it.
- **Reuse first:** prefer Matt Pocock's or Superpowers' skills unchanged; adapt only when they write to the ticket system,
  contradict team conventions, or must exist for both workflows. Credit adapted skills (MIT).
- **Deterministic vs judgement:** anything that can be computed (rules, matching, checks) is code with tests; skills only
  describe judgement and call the tools.
- **Tests first** for behaviour changes; use `fake_redmine.py` and fake runners (`runner=lambda c, interactive=False: …`)
  instead of real services.
- **Docs move with behaviour:** update `INSTALL.md`, `package/README.md`, `plugin/README.md`, `docs/user-guide.md`,
  `docs/test-plan.md` and, when relevant, `docs/WINDOWS_TEST.md` in the same change.
- **Record decisions** in `docs/decisions.md` (newest first) whenever a session decides something.

## How to work in a session

1. Read the design or ticket for the work. Propose a plan (steps, files, tests) and wait for the PM before coding.
2. Work in small steps; run the tests after each.
3. Before finishing: tests green, docs updated, a decisions entry if anything was decided, and a short summary of what
   changed, what is left and what was not verified (real Redmine, real GitLab, Windows are often not testable here).

## Current state (Nov 2026)

- Version **3.0.0** in the repository (not yet released). Releases to the marketplace may lag; check `git tag` and GitHub Releases.
- **avflow 3.0** — one flow and project-defined risk (`docs/design/avflow-3.0.md`). Decisions answered (see
  `docs/decisions.md`; the GitLab tier is still open). **Phases 1–3 done** on branch `avflow-3.0-phase1`: profile and
  validation (`risk.py`, standard library only — CI uses a copy), ticket risk area with the Machine-side mapping,
  `start_ticket` without Mode, `assess_plan`, `review_requirements`, `avflow risk check/files/sync/suggest`, stack presets
  (`data/presets.toml`), CODEOWNERS block, MR checklist section, CI gate `avflow-risk-check`; generic words in skills
  (guarded by `tests/test_skill_words.py`), the *Test environments and languages* section in the `CLAUDE.md` template,
  Mateo drafts in `examples/mateo-project-skills/`, the sandbox profile example and project skill, the risk section of
  `avflow report`. Next: the pilot (test plan on the real Redmine/GitLab), then decide whether the gate fails by default.
- Before the pilot, still open: GitLab tier of gitlab.enclave.vn; the Redmine CI variables are *Protected* and do not
  reach MR pipelines from feature branches; whether WKKM can see GitLab (check names are posted on MRs).
- Known gaps: no GitHub Actions CI for this repository yet (the root `.gitlab-ci.yml` is a leftover); Windows scripts
  only partly tested (`docs/WINDOWS_TEST.md` still describes the pre-2.6 setup questions); `avflow report` not yet run against the real Redmine/GitLab.
