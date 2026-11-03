"""Redmine adapter (REST API). Private notes, custom fields, statuses and relations are native."""
from __future__ import annotations

from typing import Any

import httpx

from .base import AdapterError, Ticket


class RedmineAdapter:
    name = "redmine"
    capabilities = {"private_notes": "native", "fields": "custom_fields", "blockers": "relations"}

    def __init__(self, cfg, token: str, client: httpx.Client | None = None, timeout: float = 20.0):
        self.cfg = cfg
        self._http = client or httpx.Client(base_url=cfg.url, timeout=timeout)
        self._h = {"X-Redmine-API-Key": token, "Content-Type": "application/json"}
        self._statuses: list[dict] | None = None
        self._me: dict | None = None

    # ---------- http
    def _req(self, method: str, path: str, **kw: Any) -> Any:
        try:
            r = self._http.request(method, path, headers=self._h, **kw)
        except httpx.HTTPError as e:
            raise AdapterError(f"Cannot reach Redmine: {e}") from e
        if r.status_code in (401, 403):
            raise AdapterError(f"Redmine refused the request ({r.status_code}). Check the API key and role permissions.")
        if r.status_code == 404:
            raise AdapterError("Not found in Redmine (wrong URL, or not visible to your account).")
        if r.status_code == 422:
            try:
                errs = r.json().get("errors", [])
            except ValueError:
                errs = [r.text]
            raise AdapterError("Redmine rejected the change: " + "; ".join(map(str, errs)))
        if r.status_code >= 400:
            raise AdapterError(f"Redmine error {r.status_code}: {r.text[:200]}")
        return r.json() if r.content and r.status_code != 204 else None

    def _issue(self, i: int, include: str = "journals,relations,attachments") -> dict:
        return self._req("GET", f"/issues/{i}.json", params={"include": include})["issue"]

    def _status_list(self) -> list[dict]:
        if self._statuses is None:
            self._statuses = self._req("GET", "/issue_statuses.json")["issue_statuses"]
        return self._statuses

    def _status_id(self, name: str) -> int:
        for s in self._status_list():
            if s["name"].lower() == name.lower():
                return s["id"]
        raise AdapterError(f"Status '{name}' does not exist in Redmine.")

    @staticmethod
    def _cf(issue: dict, name: str) -> dict | None:
        for f in issue.get("custom_fields", []) or []:
            if f.get("name", "").lower() == name.lower():
                return f
        return None

    def _cf_id(self, issue: dict, name: str) -> int:
        f = self._cf(issue, name)
        if f is None:
            raise AdapterError(f"Custom field '{name}' is not enabled for ticket #{issue['id']} (project/tracker).")
        return f["id"]

    def _fields(self, issue: dict) -> dict:
        ms = (self._cf(issue, self.cfg.field_machine_side) or {}).get("value")
        return {"mode": (self._cf(issue, self.cfg.field_mode) or {}).get("value") or None,
                "machine_side": None if ms in (None, "") else ms == "1",
                "hotspot": (self._cf(issue, self.cfg.field_hotspot) or {}).get("value") or None}

    def _blockers(self, issue: dict) -> list[dict]:
        me, ids = issue["id"], []
        for r in issue.get("relations", []) or []:
            if r.get("relation_type") == "blocks" and r.get("issue_to_id") == me:
                ids.append(r["issue_id"])
            elif r.get("relation_type") == "blocked" and r.get("issue_id") == me:
                ids.append(r["issue_to_id"])
        done = {s["name"].lower() for s in self._status_list() if s.get("is_closed")} | {n.lower() for n in self.cfg.blocker_done}
        out = []
        for b in ids:
            try:
                bi = self._issue(b, include="")
                out.append({"id": b, "subject": bi["subject"], "status": bi["status"]["name"],
                            "done": bi["status"]["name"].lower() in done})
            except AdapterError:
                out.append({"id": b, "subject": None, "status": "not visible", "done": False})
        return out

    # ---------- adapter interface
    def whoami(self) -> dict:
        if self._me is None:
            u = self._req("GET", "/users/current.json")["user"]
            self._me = {"id": u["id"], "login": u.get("login"),
                        "name": f"{u.get('firstname', '')} {u.get('lastname', '')}".strip()}
        return self._me

    def list_ready(self, project: str | None, limit: int) -> list[dict]:
        params: dict[str, Any] = {"assigned_to_id": "me", "status_id": self._status_id(self.cfg.status_ready),
                                  "sort": "priority:desc,id:asc", "limit": max(1, min(limit, 100))}
        if project:
            params["project_id"] = project
        out = []
        for i in self._req("GET", "/issues.json", params=params)["issues"]:
            out.append({"id": i["id"], "subject": i["subject"], "type": i["tracker"]["name"],
                        "priority": i["priority"]["name"], "target_version": (i.get("fixed_version") or {}).get("name"),
                        "mode": self._fields(i)["mode"]})
        return out

    def get(self, ticket_id: int) -> Ticket:
        i = self._issue(ticket_id)
        notes = [{"by": (j.get("user") or {}).get("name"), "on": j.get("created_on"),
                  "private": bool(j.get("private_notes")), "text": j["notes"][:4000]}
                 for j in i.get("journals", []) or [] if j.get("notes")]
        return Ticket(
            id=i["id"], project=i["project"]["name"], type=i["tracker"]["name"], status=i["status"]["name"],
            priority=i["priority"]["name"], subject=i["subject"],
            assignee_id=(i.get("assigned_to") or {}).get("id"), assignee=(i.get("assigned_to") or {}).get("name"),
            target_version=(i.get("fixed_version") or {}).get("name"), category=(i.get("category") or {}).get("name"),
            estimate_hours=i.get("estimated_hours"), is_private=i.get("is_private", False),
            fields=self._fields(i), description=(i.get("description") or "")[:20000], notes=notes[-30:],
            relations=[{"type": r["relation_type"], "issue": r["issue_to_id"] if r["issue_id"] == i["id"] else r["issue_id"]}
                       for r in i.get("relations", []) or []],
            blockers=self._blockers(i),
            attachments=[{"name": a["filename"], "size": a.get("filesize")} for a in i.get("attachments", []) or []],
        )

    def add_private_note(self, ticket_id: int, text: str) -> None:
        self._req("PUT", f"/issues/{ticket_id}.json", json={"issue": {"notes": text, "private_notes": True}})

    def set_fields(self, ticket_id: int, mode, machine_side, hotspot) -> None:
        i = self._issue(ticket_id, include="")
        cf = []
        if mode is not None:
            cf.append({"id": self._cf_id(i, self.cfg.field_mode), "value": mode})
        if machine_side is not None:
            cf.append({"id": self._cf_id(i, self.cfg.field_machine_side), "value": "1" if machine_side else "0"})
        if hotspot is not None:
            cf.append({"id": self._cf_id(i, self.cfg.field_hotspot), "value": hotspot})
        self._req("PUT", f"/issues/{ticket_id}.json", json={"issue": {"custom_fields": cf}})

    def set_status(self, ticket_id: int, logical: str, note: str) -> None:
        name = {"in_progress": self.cfg.status_in_progress, "in_review": self.cfg.status_in_review}[logical]
        self._req("PUT", f"/issues/{ticket_id}.json",
                  json={"issue": {"status_id": self._status_id(name), "notes": note, "private_notes": True}})

    def in_progress_with_hotspot(self, ticket_id: int, hotspot: str) -> list[dict]:
        i = self._issue(ticket_id, include="")
        fid = self._cf_id(i, self.cfg.field_hotspot)
        res = self._req("GET", "/issues.json", params={"status_id": self._status_id(self.cfg.status_in_progress),
                                                        f"cf_{fid}": hotspot, "limit": 100})["issues"]
        return [{"id": o["id"], "subject": o["subject"], "assignee": (o.get("assigned_to") or {}).get("name")}
                for o in res if o["id"] != ticket_id]

    def create_bug_draft(self, project: str, subject: str, description: str, related_id: int | None) -> int:
        trackers = {t["name"].lower(): t["id"] for t in self._req("GET", "/trackers.json")["trackers"]}
        tid = trackers.get(self.cfg.tracker_bug.lower())
        if tid is None:
            raise AdapterError(f"Tracker '{self.cfg.tracker_bug}' does not exist.")
        new = self._req("POST", "/issues.json", json={"issue": {"project_id": project, "tracker_id": tid, "subject": subject,
                                                                 "description": description, "is_private": True}})["issue"]
        if related_id:
            self._req("POST", f"/issues/{new['id']}/relations.json",
                      json={"relation": {"issue_to_id": related_id, "relation_type": "relates"}})
        return new["id"]
