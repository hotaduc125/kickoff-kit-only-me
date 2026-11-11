"""Redmine adapter (REST API). Private notes, custom fields, statuses and relations are native."""
from __future__ import annotations

import re
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

    # ---------- Mode / Machine-side / Hotspot
    # Preferred: Redmine custom fields (created by an admin). Without them (no admin rights), avflow reads
    # Machine-side and Hotspot from the "Size and mode" line of the description, written by the person, and
    # keeps the confirmed mode (and any raise of Machine-side) in private notes starting with MARKER.
    MARKER = "[avflow]"

    def _has_cf(self, issue: dict, name: str) -> bool:
        return self._cf(issue, name) is not None

    @staticmethod
    def _desc_fields(description: str) -> dict:
        d = description or ""
        out = {}
        m = re.search(r"(?im)machine[- ]side\s*:\s*\**\s*(yes|no)\b", d)
        if m:
            out["machine_side"] = m.group(1).lower() == "yes"
        m = re.search(r"(?im)hotspot\s*:\s*\**\s*`?([^`\n·|*]+?)`?\s*\**\s*(?:[·|]|$)", d)
        if m:
            v = m.group(1).strip()
            out["hotspot"] = None if v.lower() in ("none", "-", "n/a", "") or v.lower().startswith("todo") else v
        m = re.search(r"(?im)(?:proposed\s+)?mode\s*:\s*\**\s*(direct|plan|full|spike)\b", d)
        if m:
            out["mode"] = m.group(1).lower()
        return out

    @classmethod
    def _marker_fields(cls, journals: list[dict]) -> dict:
        """Latest values from private notes like '[avflow] mode=plan · machine-side=yes · hotspot=src/a.cs'."""
        out = {}
        for j in journals or []:
            text = j.get("notes") or ""
            if not j.get("private_notes") or cls.MARKER not in text:
                continue
            line = next((l for l in text.splitlines() if l.strip().startswith(cls.MARKER)), "")
            for k, v in re.findall(r"(mode|machine-side|hotspot)=([^·\s]+)", line):
                if k == "mode" and v in ("direct", "plan", "full", "spike"):
                    out["mode"] = v
                elif k == "machine-side":
                    out["machine_side"] = v.lower() == "yes"
                elif k == "hotspot":
                    out["hotspot"] = None if v in ("none", "-") else v
        return out

    def _fields(self, issue: dict) -> dict:
        cf = {}
        if self._has_cf(issue, self.cfg.field_mode):
            cf["mode"] = (self._cf(issue, self.cfg.field_mode) or {}).get("value") or None
        if self._has_cf(issue, self.cfg.field_machine_side):
            ms = (self._cf(issue, self.cfg.field_machine_side) or {}).get("value")
            cf["machine_side"] = None if ms in (None, "") else ms == "1"
        if self._has_cf(issue, self.cfg.field_hotspot):
            cf["hotspot"] = (self._cf(issue, self.cfg.field_hotspot) or {}).get("value") or None
        desc = self._desc_fields(issue.get("description") or "")
        notes = self._marker_fields(issue.get("journals") or [])
        out = {}
        for k in ("mode", "machine_side", "hotspot"):
            if k in cf:
                out[k] = cf[k]
            elif k == "machine_side":
                vals = [v for v in (desc.get(k), notes.get(k)) if v is not None]
                out[k] = (True in vals) if vals else None      # only ever raised to yes
            elif k == "mode":
                out[k] = notes.get(k) or desc.get(k)            # confirmed in a note wins over the description
            else:
                out[k] = notes.get(k) if k in notes else desc.get(k)
        out["source"] = "custom fields" if cf else "description and private notes"
        return out

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
        cf, marker = [], []
        for value, name, key, render in ((mode, self.cfg.field_mode, "mode", lambda v: v),
                                         (machine_side, self.cfg.field_machine_side, "machine-side", lambda v: "1" if v else "0"),
                                         (hotspot, self.cfg.field_hotspot, "hotspot", lambda v: v)):
            if value is None:
                continue
            if self._has_cf(i, name):
                cf.append({"id": self._cf_id(i, name), "value": render(value)})
            elif key == "machine-side":
                marker.append(f"machine-side={'yes' if value else 'no'}")
            else:
                marker.append(f"{key}={(value or 'none').replace(' ', '_')}")
        if cf:
            self._req("PUT", f"/issues/{ticket_id}.json", json={"issue": {"custom_fields": cf}})
        if marker:
            note = f"{self.MARKER} " + " · ".join(marker) + "\n(avflow fields kept in this private note: no custom fields in this Redmine)"
            self._req("PUT", f"/issues/{ticket_id}.json", json={"issue": {"notes": note, "private_notes": True}})

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
