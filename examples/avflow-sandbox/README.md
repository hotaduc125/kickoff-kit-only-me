# avflow-sandbox

A small sample project for testing the avflow workflow end to end — Redmine tickets, Claude Code with avflow,
GitLab merge requests and CI. Follow `avflow-test-plan.md`.

## What is in it

| Path | Purpose in the tests |
|---|---|
| `src/sandbox/orders.py` | Orders data — T2 adds a status filter |
| `src/sandbox/report.py` | Order report — T2, T4, T7, C1, C2 |
| `src/sandbox/machine.py` | Simulated machine control: the **sensitive path** (mode FULL) — T3 |
| `tests/` | Passing tests (`pytest`) |
| `.gitlab-ci.yml` | Lint (ruff) and test (pytest) on `python:3.12-slim` |
| `test-tickets/` | Paste-ready ticket descriptions for T1–T7, C1, C2 (not code — keep or delete after creating the tickets) |

## Push to GitLab

1. Create an empty project `avflow-sandbox` on Enclave's GitLab (no README).
2. From this folder:

   ```bash
   git init -b main
   git add .
   git commit -m "Initial sample project"
   git remote add origin https://gitlab.enclave.vn/<group>/avflow-sandbox.git
   git push -u origin main
   git checkout -b develop
   git push -u origin develop
   ```

3. In GitLab: **Settings → Repository → Default branch: develop**; **Protected branches**: `main` and `develop`, *Allowed to push: No one*; **Settings → Merge requests**: *Pipelines must succeed*.
4. Check that the first pipeline (lint, test) is green.

## Run locally

```bash
uv run pytest        # or: python -m pytest
uv run ruff check .
```

## After `avflow init` (test B1)

`avflow init` adds the team files and `.gitlab-ci.avflow.yml`. Because `.gitlab-ci.yml` already exists, it is kept;
add this at the top of `.gitlab-ci.yml`:

```yaml
include:
  - local: .gitlab-ci.avflow.yml
```

In `CLAUDE.md`, fill in: build `uv run python -c "import sandbox"`, test `uv run pytest`, sensitive path `src/sandbox/machine.py`.
