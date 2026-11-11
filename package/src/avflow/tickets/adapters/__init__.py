"""Ticket-system adapters. Each adapter maps the nine team tools onto one system.

Agreed handling where systems differ (docs/ADAPTERS.md):
- private notes: Redmine private note · GitLab internal note · Jira restricted comment ·
  GitHub Issues has none → notes go to the pull request instead.
- statuses / fields: native where available, otherwise scoped labels (GitLab) or labels (GitHub).
"""
from .base import Adapter, AdapterError, Ticket  # noqa: F401


def make_adapter(cfg, token: str, client=None):
    p = cfg.provider.lower()
    if p == "redmine":
        from .redmine import RedmineAdapter
        return RedmineAdapter(cfg, token, client=client)
    raise SystemExit(f"Ticket provider '{cfg.provider}' is not available in this version (v1 supports: redmine).")
