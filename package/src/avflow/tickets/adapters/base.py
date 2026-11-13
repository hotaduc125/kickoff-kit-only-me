"""Adapter interface: what every ticket system must provide to the core."""
from __future__ import annotations

from typing import Any, Protocol, TypedDict


class AdapterError(Exception):
    """The ticket system refused or failed a request."""


class Ticket(TypedDict, total=False):
    id: int
    project: str
    type: str
    status: str
    priority: str
    subject: str
    assignee_id: Any
    assignee: str | None
    target_version: str | None
    category: str | None
    estimate_hours: float | None
    is_private: bool
    fields: dict              # risk_areas (list), hotspot, spike (bool), source
    description: str
    notes: list[dict]         # by, on, private, text
    relations: list[dict]
    blockers: list[dict]      # id, subject, status, done
    attachments: list[dict]


class Adapter(Protocol):
    name: str
    capabilities: dict        # e.g. {"private_notes": "native" | "on_merge_request"}

    def whoami(self) -> dict: ...
    def list_ready(self, project: str | None, limit: int) -> list[dict]: ...
    def get(self, ticket_id: int) -> Ticket: ...
    def add_private_note(self, ticket_id: int, text: str) -> None: ...
    def set_fields(self, ticket_id: int, risk_area: str | None, hotspot: str | None, reason: str | None = None) -> None: ...
    def avflow_notes(self, ticket_id: int) -> list[str]: ...    # full text of private notes with the [avflow] marker
    def set_status(self, ticket_id: int, logical: str, note: str) -> None: ...   # logical: in_progress | in_review
    def in_progress_with_hotspot(self, ticket_id: int, hotspot: str) -> list[dict]: ...
    def create_bug_draft(self, project: str, subject: str, description: str, related_id: int | None) -> int: ...
