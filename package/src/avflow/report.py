"""avflow report: weekly PM metrics from the ticket system (and GitLab, when glab works in the repository).

Read-only. Metrics follow the team's working model: progress per release, tickets over estimate,
reopened tickets, merge-request flow and first-pipeline success, and (3.0) the risk of the reviewed changes —
taken from the private '[avflow] required' notes that start_ticket, assess_plan and review_requirements write.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import risk
from . import setup_steps as st

BUCKETS = ["New / Ready", "In progress", "In review", "Ready for test", "Done"]


def bucket(status: str, cfg) -> str:
    s = status.lower()
    if s == cfg.status_in_progress.lower():
        return "In progress"
    if s == cfg.status_in_review.lower():
        return "In review"
    if s == cfg.status_ready_for_test.lower():
        return "Ready for test"
    if s in ("resolved", "closed", "rejected"):
        return "Done"
    return "New / Ready"


def progress_by_version(issues: list[dict], cfg) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for i in issues:
        v = (i.get("fixed_version") or {}).get("name") or "(no version)"
        out[v][bucket(i["status"]["name"], cfg)] += 1
    return dict(out)


def over_estimate(issues: list[dict], spent: dict[int, float], threshold: float = 0.5) -> list[dict]:
    rows = []
    for i in issues:
        est = i.get("estimated_hours")
        if est and spent.get(i["id"], 0) > est * (1 + threshold):
            rows.append({"id": i["id"], "subject": i["subject"], "estimated": est, "spent": round(spent[i["id"]], 1)})
    return sorted(rows, key=lambda r: r["spent"] / r["estimated"], reverse=True)


def reopened(journals_by_issue: dict[int, list[dict]], done_ids: set[str], since: datetime) -> list[int]:
    out = []
    for iid, journals in journals_by_issue.items():
        for j in journals:
            when = _dt(j.get("created_on"))
            if when and when < since:
                continue
            for d in j.get("details", []) or []:
                if d.get("name") == "status_id" and str(d.get("old_value")) in done_ids and str(d.get("new_value")) not in done_ids:
                    out.append(iid)
                    break
    return sorted(set(out))


def mr_metrics(mrs: list[dict], first_pipeline: dict[int, str]) -> dict:
    hours = [(_dt(m["merged_at"]) - _dt(m["created_at"])).total_seconds() / 3600
             for m in mrs if m.get("merged_at") and m.get("created_at")]
    known = [s for s in first_pipeline.values() if s]
    return {"merged": len(mrs),
            "median_hours_to_merge": round(statistics.median(hours), 1) if hours else None,
            "first_pipeline_green": f"{sum(s == 'success' for s in known)}/{len(known)}" if known else None}


def risk_summary(journals_by_issue: dict[int, list[dict]], since: datetime) -> dict:
    """Tickets whose review_requirements ran in the period, from their PRIVATE '[avflow] required' notes.

    Public notes are ignored (anyone, including the customer, can write one). Each area keeps where it was first found:
    "ticket" (the ticket named it), "plan" (planned files) or "review" (only in the diff — the plan missed it).
    """
    out: dict = {"reviewed": [], "high_risk": [], "default_only": [], "areas": {}, "missed_at_plan": {}, "gaps": {}}
    for iid in sorted(journals_by_issue):
        private = [j for j in journals_by_issue[iid] if j.get("private_notes")]
        reviewed = any((j.get("notes") or "").startswith(risk.REQUIRED) and '"stage": "review"' in (j.get("notes") or "")
                       and (_dt(j.get("created_on")) or since) >= since for j in private)
        if not reviewed:
            continue
        req = risk.required_from_notes([j.get("notes") or "" for j in private])
        out["reviewed"].append(iid)
        if req["areas"]:
            out["high_risk"].append(iid)
        elif req["checks"]:
            out["default_only"].append(iid)
        for area, src in req["areas"].items():
            row = out["areas"].setdefault(area, {"ticket": [], "plan": [], "review": []})
            row[src if src in row else "ticket"].append(iid)
        missed = [a for a, src in req["areas"].items() if src == "review"]
        if missed:
            out["missed_at_plan"][iid] = missed
        if req["gaps"]:
            out["gaps"][iid] = req["gaps"]
    return out


def risk_section(s: dict) -> list[str]:
    n = len(s["reviewed"])
    lines = [f"## Risk ({n} ticket{'' if n == 1 else 's'} reviewed in the period)", ""]
    if not n:
        return lines + ["- No ticket reached review_requirements in the period.", ""]
    hr = len(s["high_risk"])
    lines.append(f"- High-risk changes: {hr} of {n} ({round(100 * hr / n)}%)"
                 + (f" · strict default only: {len(s['default_only'])}" if s["default_only"] else ""))
    if s["areas"]:
        lines += ["", "| Risk area | Tickets | From the ticket | Found at plan | Found only at review |", "|---|---|---|---|---|"]
        for area, row in sorted(s["areas"].items(), key=lambda kv: (-sum(map(len, kv[1].values())), kv[0])):
            lines.append(f"| {area} | {sum(map(len, row.values()))} | {len(row['ticket'])} | {len(row['plan'])} | {len(row['review'])} |")
    lines += ["", f"### Found only at review — the ticket and the plan missed them ({len(s['missed_at_plan'])})", ""]
    lines += [f"- #{i}: {', '.join(a)}" for i, a in s["missed_at_plan"].items()] or ["- none"]
    lines += ["", f"### Profile gaps — files of high-risk tickets outside every area ({len(s['gaps'])})", ""]
    lines += [f"- #{i}: " + ", ".join(f"`{g}`" for g in gs) for i, gs in s["gaps"].items()] or ["- none"]
    if s["gaps"]:
        lines.append("- Run `avflow risk suggest` in the project repository for the paths to add.")
    lines.append("")
    return lines


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------- collection
def gitlab_mrs(since: datetime, cwd: str | None, runner=st.run) -> tuple[list[dict], dict[int, str]] | None:
    code, out = runner(["glab", "api", f"projects/:fullpath/merge_requests?state=merged&updated_after={since.isoformat()}&per_page=100"])
    if code != 0:
        return None
    try:
        mrs = [m for m in json.loads(out) if _dt(m.get("merged_at")) and _dt(m["merged_at"]) >= since]
    except ValueError:
        return None
    first = {}
    for m in mrs[:50]:
        c, o = runner(["glab", "api", f"projects/:fullpath/merge_requests/{m['iid']}/pipelines"])
        try:
            pipes = json.loads(o) if c == 0 else []
            first[m["iid"]] = pipes[-1]["status"] if pipes else None
        except (ValueError, KeyError, IndexError):
            first[m["iid"]] = None
    return mrs, first


def build_report(adapter, cfg, project: str, days: int = 7, runner=st.run, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    t = cfg
    issues = adapter.list_issues(project_id=project, status_id="*")
    spent: dict[int, float] = defaultdict(float)
    for e in adapter.time_entries(project_id=project):
        if e.get("issue"):
            spent[e["issue"]["id"]] += float(e.get("hours") or 0)
    statuses = adapter.statuses()
    done_names = {n.lower() for n in t.blocker_done} | {s["name"].lower() for s in statuses if s.get("is_closed")}
    done_ids = {str(s["id"]) for s in statuses if s["name"].lower() in done_names}
    recent = [i for i in issues if _dt(i.get("updated_on")) and _dt(i["updated_on"]) >= since][:200]
    journals = {i["id"]: adapter.issue_raw(i["id"], include="journals").get("journals", []) for i in recent}

    lines = [f"# Weekly report — {project}", f"Period: last {days} days (to {now.date()})", ""]
    lines += ["## Progress by release", "", "| Version | " + " | ".join(BUCKETS) + " | Total |", "|---" * (len(BUCKETS) + 2) + "|"]
    for v, c in sorted(progress_by_version(issues, t).items()):
        lines.append(f"| {v} | " + " | ".join(str(c.get(b, 0)) for b in BUCKETS) + f" | {sum(c.values())} |")
    over = over_estimate(issues, spent)
    lines += ["", f"## Tickets over estimate by more than 50% ({len(over)})", ""]
    lines += [f"- #{r['id']} {r['subject']} — estimated {r['estimated']} h, spent {r['spent']} h" for r in over] or ["- none"]
    re_ids = reopened(journals, done_ids, since)
    lines += ["", f"## Reopened in the period ({len(re_ids)})", ""]
    lines += [f"- #{i}" for i in re_ids] or ["- none"]
    lines += ["", *risk_section(risk_summary(journals, since))][:-1]
    g = gitlab_mrs(since, None, runner)
    lines += ["", "## Merge requests (GitLab)", ""]
    if g is None:
        lines.append("- not available (run in the project repository with glab signed in)")
    else:
        m = mr_metrics(*g)
        lines += [f"- Merged: {m['merged']}",
                  f"- Median time from open to merge: {m['median_hours_to_merge']} h" if m["median_hours_to_merge"] is not None else "- Median time from open to merge: —",
                  f"- First pipeline green: {m['first_pipeline_green']}" if m["first_pipeline_green"] else "- First pipeline green: —"]
    lines.append("")
    return "\n".join(lines)
