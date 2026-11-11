# Ticket adapters — agreed handling

The MCP server `avflow-tickets` exposes the same nine tools for every ticket system. Each adapter maps them onto its
system. Where systems differ, the handling below is **agreed in advance** — adapters do not decide on their own.

| Concept | Redmine (v1) | Jira (planned) | GitLab Issues (planned) | GitHub Issues (planned) |
|---|---|---|---|---|
| Private note | Private note (`private_notes`) | Comment restricted to a role / group | Internal note | **No private comments → the note is written on the pull request** linked to the issue |
| Statuses Ready / In progress / In review | Workflow statuses | Workflow transitions | Work-item status or scoped labels `status::…` | Labels `status:…` (open/closed only natively) |
| Mode / Machine-side / Hotspot | Custom fields | Custom fields | Scoped labels `mode::…`, `machine-side`, `hotspot::…` | Labels `mode:…`, `machine-side`, `hotspot:…` |
| Blocked by | Relation blocks / blocked | Issue link "is blocked by" | Relation blocked by | Relationship where available, otherwise "Blocked by #n" in the body |
| Bug draft | Private issue, status New | Issue with restricted security level, status New | Confidential issue | Issue in the private repository with label `draft` |

## Adding an adapter
1. Implement the `Adapter` protocol in `src/avflow/tickets/adapters/<system>.py`.
2. Register it in `adapters/__init__.py` (`make_adapter`) and enable it in `cli.py` (`TICKET_CHOICES`) with its setup questions.
3. Add tests against an in-memory fake of the system's API (see `tests/fake_redmine.py`).
4. The core rules (`tickets/core.py`) stay unchanged — every adapter gets them for free.
