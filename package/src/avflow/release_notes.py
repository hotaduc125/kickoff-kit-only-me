"""avflow release-notes: tickets referenced by the commits in a range, as Markdown release notes."""
from __future__ import annotations

import re

from . import setup_steps as st

REF = re.compile(r"(?:refs|closes|fixes)\s+#(\d+)", re.IGNORECASE)
SEP_FIELD, SEP_COMMIT = "\x1f", "\x1e"


def commits_in_range(frm: str, to: str = "HEAD", cwd: str | None = None, runner=st.run) -> list[dict]:
    code, out = runner(["git", "-C", cwd or ".", "log", "--no-merges", f"--format=%h{SEP_FIELD}%s{SEP_FIELD}%b{SEP_COMMIT}", f"{frm}..{to}"])
    if code != 0:
        raise SystemExit(f"git log {frm}..{to} failed: {out.strip()[:200]}")
    commits = []
    for chunk in out.split(SEP_COMMIT):
        chunk = chunk.strip()
        if not chunk:
            continue
        sha, subject, body = (chunk.split(SEP_FIELD) + ["", ""])[:3]
        ids = sorted({int(m) for m in REF.findall(subject + "\n" + body)})
        commits.append({"sha": sha, "subject": subject, "ids": ids})
    return commits


def build(commits: list[dict], tickets: dict[int, dict], done_statuses: list[str], frm: str, to: str) -> str:
    done = {d.lower() for d in done_statuses}
    by_type: dict[str, list[dict]] = {}
    for t in tickets.values():
        by_type.setdefault(t.get("type") or "Other", []).append(t)
    lines = [f"## Changes ({frm}..{to})", ""]
    for typ in sorted(by_type):
        lines.append(f"### {typ}")
        for t in sorted(by_type[typ], key=lambda x: (not x.get("risk_areas"), x["id"])):
            mark = "".join(f" **[{a}]**" for a in t.get("risk_areas") or [])
            lines.append(f"- #{t['id']} {t['subject']}{mark}")
        lines.append("")
    warn = []
    for c in commits:
        if not c["ids"]:
            warn.append(f"- Commit `{c['sha']}` has no ticket reference: {c['subject']}")
    for t in tickets.values():
        if t.get("error"):
            warn.append(f"- #{t['id']}: {t['error']}")
        elif t.get("status", "").lower() not in done:
            warn.append(f"- #{t['id']} is '{t.get('status')}', not yet Ready for test")
    if warn:
        lines += ["## Warnings — resolve before releasing", "", *warn, ""]
    areas = sorted({a for t in tickets.values() for a in t.get("risk_areas") or []})
    lines += ["## Acceptance checklist (customer engineer) — to complete from each ticket's acceptance criteria", ""]
    for t in sorted(tickets.values(), key=lambda x: (not x.get("risk_areas"), x["id"])):
        lines.append(f"- [ ] #{t['id']} {t['subject']}")
    lines += ["", "## Pre-release checks", "", "- [ ] CI green on the release commit", "- [ ] Regression tests green (and the project's own test environments)"]
    if areas:
        lines.append(f"- [ ] High-risk changes ({', '.join(areas)}): every required check done on their merge requests")
    lines += ["- [ ] Translations reviewed (if the UI changed)", "", "## Rollback", "", "- …", ""]
    return "\n".join(lines)


def collect(adapter, commits: list[dict]) -> dict[int, dict]:
    tickets = {}
    for tid in sorted({i for c in commits for i in c["ids"]}):
        try:
            t = adapter.get(tid)
            tickets[tid] = {"id": tid, "subject": t["subject"], "type": t.get("type"), "status": t.get("status"),
                            "risk_areas": list((t.get("fields") or {}).get("risk_areas") or [])}
        except Exception as e:  # noqa: BLE001 — report any lookup problem as a warning
            tickets[tid] = {"id": tid, "subject": "(not readable)", "type": "Other", "error": str(e)}
    return tickets
