# Mateo — project files that carry what avflow 3.0 no longer says

avflow's team skills use generic words since 3.0 (design principle 6: *generic words in avflow, project words in the
project*). The Mateo-specific text that was in the 2.x skills (`qa-agent`, `release`, `incident`, `ticket-writer`,
`glossary`, `triage`, `zoom-out`) moves into Mateo's own repository. These are drafts to copy there — they are **not**
shipped with avflow and are not read by it.

| File here | Copy to (Mateo repository) | What it carries |
|---|---|---|
| `CLAUDE.section.md` | Paste into `CLAUDE.md`, replacing the section *Test environments and languages* | Simulator, test bench, languages zh / en, the project skills |
| `project.toml.area` | Add to `.avflow/project.toml` (after the preset areas) | The *Machine control* risk area (paths, owner, checks) |
| `skills/mateo-machine-review/SKILL.md` | `.claude/skills/mateo-machine-review/SKILL.md` | Test design, review and release checks for machine-side changes: simulator with camera replay vs test bench |
| `skills/mateo-logs/SKILL.md` | `.claude/skills/mateo-logs/SKILL.md` | Field evidence for incidents and bug reproduction: alarm / event logs, SPC data, recipe, panel photos |
| `CONTEXT.example.md` | Merge into `docs/CONTEXT.md` if the term is missing | The *Nulling* glossary entry (was the example in avflow's `glossary` skill) |

Then, in Mateo: `avflow risk check`, `avflow risk sync` (CODEOWNERS), and merge it all in one merge request. The team
setting `machine_side_area = "Machine control"` keeps old tickets with `Machine-side: yes` in that area.

Lines marked **TODO** need someone who knows Mateo (paths, owners, log locations) — do not guess them.
