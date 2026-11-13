"""Redmine adapter (REST API). Private notes, custom fields, statuses and relations are native."""
from __future__ import annotations

import re
from typing import Any

import httpx

from ... import risk
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

    # ---------- Risk area / Hotspot
    # Preferred: Redmine custom fields (created by an admin). Without them (no admin rights), avflow reads the risk area
    # and Hotspot from the "Size and mode" line of the description, written by the person. The agent never
    # writes the description or the risk-area field: it adds a risk area (and sets Hotspot without a field) in private
    # notes starting with MARKER. Risk areas are a union: nothing the agent writes can remove one.
    MARKER = risk.MARKER
    OTHER = risk.OTHER

    def _has_cf(self, issue: dict, name: str) -> bool:
        return self._cf(issue, name) is not None

    @staticmethod
    def _desc_fields(description: str) -> dict:
        return risk.description_fields(description)

    @classmethod
    def _marker_fields(cls, journals: list[dict]) -> dict:
        return risk.marker_fields([j.get("notes") or "" for j in journals or [] if j.get("private_notes")])

    def _fields(self, issue: dict) -> dict:
        cfg = self.cfg
        has_area_cf = self._has_cf(issue, cfg.field_risk_area)
        has_hs_cf = self._has_cf(issue, cfg.field_hotspot)
        desc = self._desc_fields(issue.get("description") or "")
        notes = self._marker_fields(issue.get("journals") or [])
        areas = risk.split_areas((self._cf(issue, cfg.field_risk_area) or {}).get("value")) if has_area_cf \
            else list(desc.get("risk_areas", []))
        areas += notes["risk_areas"]
        uniq = risk.unique_areas(areas)
        if has_hs_cf:
            hotspot = (self._cf(issue, cfg.field_hotspot) or {}).get("value") or None
        else:
            hotspot = notes["hotspot"] if "hotspot" in notes else desc.get("hotspot")
        spike = (issue.get("tracker") or {}).get("name", "").lower() == "spike" or bool(desc.get("spike"))
        return {"risk_areas": uniq, "hotspot": hotspot, "spike": spike,
                "source": "custom fields" if (has_area_cf or has_hs_cf) else "description and private notes"}

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
                        "risk_areas": self._fields(i)["risk_areas"]})
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

    def set_fields(self, ticket_id: int, risk_area: str | None, hotspot: str | None, reason: str | None = None) -> None:
        i = self._issue(ticket_id, include="")
        marker = []
        if risk_area:
            marker.append("risk-area=" + re.sub(r"\s+", "_", risk_area.strip()))
        if hotspot is not None:
            if self._has_cf(i, self.cfg.field_hotspot):
                self._req("PUT", f"/issues/{ticket_id}.json",
                          json={"issue": {"custom_fields": [{"id": self._cf_id(i, self.cfg.field_hotspot), "value": hotspot}]}})
            else:
                marker.append(f"hotspot={(hotspot or 'none').replace(' ', '_')}")
        if marker:
            note = f"{self.MARKER} " + " · ".join(marker)
            note += f"\nRisk area added by the coding agent: {reason}" if risk_area else \
                "\n(avflow fields kept in this private note: no custom field in this Redmine)"
            self._req("PUT", f"/issues/{ticket_id}.json", json={"issue": {"notes": note, "private_notes": True}})

    def avflow_notes(self, ticket_id: int) -> list[str]:
        """Full text of every PRIVATE note that contains the avflow marker, oldest first (public ones never count)."""
        return [j["notes"] for j in self._issue(ticket_id, include="journals").get("journals", []) or []
                if j.get("private_notes") and self.MARKER in (j.get("notes") or "")]

    def set_status(self, ticket_id: int, logical: str, note: str) -> None:
        name = {"in_progress": self.cfg.status_in_progress, "in_review": self.cfg.status_in_review}[logical]
        self._req("PUT", f"/issues/{ticket_id}.json",
                  json={"issue": {"status_id": self._status_id(name), "notes": note, "private_notes": True}})

    def in_progress_with_hotspot(self, ticket_id: int, hotspot: str) -> list[dict]:
        i = self._issue(ticket_id, include="")
        status = self._status_id(self.cfg.status_in_progress)
        if self._has_cf(i, self.cfg.field_hotspot):
            fid = self._cf_id(i, self.cfg.field_hotspot)
            res = self._req("GET", "/issues.json", params={"status_id": status, f"cf_{fid}": hotspot, "limit": 100})["issues"]
        else:
            res = []
            candidates = self._req("GET", "/issues.json", params={"status_id": status, "limit": 100})["issues"]
            for o in candidates[:50]:
                if o["id"] == ticket_id:
                    continue
                h = self._desc_fields(o.get("description") or "").get("hotspot")
                if h is None:
                    h = self._marker_fields(self._issue(o["id"], include="journals").get("journals") or []).get("hotspot")
                if h and h == hotspot:
                    res.append(o)
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


    # ---------- read-only helpers for PM tools (not exposed through MCP)
    def list_issues(self, max_items: int = 2000, **params) -> list[dict]:
        out, offset = [], 0
        while len(out) < max_items:
            page = self._req("GET", "/issues.json", params={**params, "limit": 100, "offset": offset})
            items = page.get("issues", [])
            out += items
            if len(items) < 100 or offset + 100 >= page.get("total_count", 0):
                break
            offset += 100
        return out[:max_items]

    def issue_raw(self, issue_id: int, include: str = "journals") -> dict:
        return self._issue(issue_id, include=include)

    def time_entries(self, max_items: int = 5000, **params) -> list[dict]:
        out, offset = [], 0
        while len(out) < max_items:
            page = self._req("GET", "/time_entries.json", params={**params, "limit": 100, "offset": offset})
            items = page.get("time_entries", [])
            out += items
            if len(items) < 100 or offset + 100 >= page.get("total_count", 0):
                break
            offset += 100
        return out[:max_items]

    def statuses(self) -> list[dict]:
        return self._status_list()
