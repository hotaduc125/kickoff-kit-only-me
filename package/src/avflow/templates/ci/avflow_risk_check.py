"""CI job avflow-risk-check: the checks a merge request needs, from facts the MR cannot change, and whether they are done.

Facts: the risk profile on the TARGET branch (an MR cannot loosen its own checks), the files the MR changes, and the
ticket in the MR title (its risk area; the checks recorded at start and plan in private [avflow] notes, when the CI
account may read private notes). `[ci] gate = "report"` lists what is missing and passes; `"fail"` fails the job.
Standard library only; the matching logic is ci/avflow_risk.py, a copy of avflow's risk.py (`avflow risk sync`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    import avflow_risk as risk          # the copy next to this script, in the project repository
except ImportError:                     # avflow's own tests
    from avflow import risk

REF = re.compile(r"(?:refs|closes|fixes)\s+#(\d+)", re.IGNORECASE)
REVIEW_HEAD = "### avflow — independent review"
VERDICT = re.compile(r"(?im)^\W*verdict\W*:\W*approve\b")


# ---------- I/O (replaced in tests)
def git(*args: str) -> str:
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], capture_output=True, text=True, check=True).stdout


def http_json(url: str, headers: dict) -> object:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


class Sources:
    def __init__(self, env=None, git_fn=git, http=http_json):
        self.env, self.git, self.http = env if env is not None else os.environ, git_fn, http

    def gitlab(self, path: str):
        tok = self.env.get("AVFLOW_GITLAB_TOKEN")
        if not tok:
            raise PermissionError("AVFLOW_GITLAB_TOKEN is not set")
        return self.http(self.env["CI_API_V4_URL"].rstrip("/") + path, {"PRIVATE-TOKEN": tok})

    def mr(self, suffix: str = ""):
        return self.gitlab(f"/projects/{self.env['CI_PROJECT_ID']}/merge_requests/{self.env['CI_MERGE_REQUEST_IID']}{suffix}")

    def redmine(self, path: str):
        url, key = self.env.get("REDMINE_URL"), self.env.get("REDMINE_CI_API_KEY")
        if not url or not key:
            raise PermissionError("REDMINE_URL / REDMINE_CI_API_KEY not set")
        return self.http(url.rstrip("/") + path, {"X-Redmine-API-Key": key})


# ---------- facts
def target_profile(src: Sources):
    t = src.env.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "")
    try:
        src.git("fetch", "-q", "origin", f"+refs/heads/{t}:refs/remotes/origin/{t}")
    except (subprocess.CalledProcessError, OSError):
        pass
    try:
        text = src.git("show", f"origin/{t}:{risk.PROFILE.as_posix()}")
    except (subprocess.CalledProcessError, OSError):
        return None
    return risk.parse(text)


def changed_files(src: Sources) -> list[str]:
    base = src.env.get("CI_MERGE_REQUEST_DIFF_BASE_SHA", "")
    out = src.git("diff", "--name-only", "--no-renames", base, src.env.get("CI_COMMIT_SHA", "HEAD"))
    return [l.strip() for l in out.splitlines() if l.strip()]


def ticket_facts(src: Sources, ids: list[int], notes: list[str]) -> tuple[list[str], dict]:
    """The tickets' risk areas and the checks recorded on them; `notes` collects what could not be read."""
    env, areas, private = src.env, [], []
    for i in ids:
        try:
            issue = src.redmine(f"/issues/{i}.json?include=journals")["issue"]
        except (PermissionError, urllib.error.URLError, KeyError, ValueError, OSError) as e:
            notes.append(f"Ticket #{i} could not be read ({e}); only the diff counts for it.")
            continue
        cf = {(f.get("name") or "").lower(): f.get("value") for f in issue.get("custom_fields") or []}
        desc = risk.description_fields(issue.get("description") or "")
        field_area = env.get("AVFLOW_FIELD_RISK_AREA", "Risk area").lower()
        field_ms = env.get("AVFLOW_FIELD_MACHINE_SIDE", "Machine-side").lower()
        areas += risk.split_areas(cf[field_area]) if field_area in cf else desc.get("risk_areas", [])
        if (cf.get(field_ms) == "1") if field_ms in cf else desc.get("machine_side"):
            areas.append(env.get("AVFLOW_MACHINE_SIDE_AREA") or risk.OTHER)
        private += [j.get("notes") or "" for j in issue.get("journals") or [] if j.get("private_notes")]
    marks = risk.marker_fields(private)
    areas += marks["risk_areas"]
    if marks.get("machine_side"):
        areas.append(env.get("AVFLOW_MACHINE_SIDE_AREA") or risk.OTHER)
    prior = risk.required_from_notes(private)
    if ids and not private:
        notes.append("No private [avflow] notes visible: checks recorded at start and plan are not known to CI "
                     "(the Redmine CI account needs permission to view private notes).")
    return risk.unique_areas(areas), prior


# ---------- verification
def owners_usernames(src: Sources, owners: list[str], notes: list[str]) -> set[str]:
    out = set()
    for o in owners:
        name = o.lstrip("@")
        if "@" in name or not name:
            notes.append(f"Owner {o} is an e-mail address: CI cannot match it to an approval; use @username.")
            continue
        out.add(name.lower())
        try:     # a group owner: its members count (users simply are not groups → 404)
            members = src.gitlab(f"/groups/{urllib.parse.quote(name, safe='')}/members/all?per_page=100")
            out |= {m["username"].lower() for m in members or []}
        except (urllib.error.HTTPError, KeyError, TypeError):
            pass
    return out


def verify(src: Sources, profile, areas: dict, checks: list[str], notes: list[str]) -> list[tuple[str, str, str]]:
    """(status, check, detail) per check; status ok | missing | unknown."""
    res, desc = [], None
    try:
        desc = (src.mr() or {}).get("description") or ""
    except (PermissionError, urllib.error.URLError, OSError):
        desc = src.env.get("CI_MERGE_REQUEST_DESCRIPTION")
    for c in checks:
        if c == "plan-confirmation":
            res.append(("unknown", c, "confirmed by the assignee in the session — not visible to CI; the reviewer checks the plan note"))
        elif c == "independent-review":
            try:
                found = [n for n in src.mr("/notes?per_page=100&sort=desc") or []
                         if not n.get("system") and (n.get("body") or "").startswith(REVIEW_HEAD)]
            except PermissionError as e:
                res.append(("unknown", c, f"cannot read MR notes: {e}"))
                continue
            ok = [n for n in found if VERDICT.search(n.get("body") or "")]
            res.append(("ok", c, f"review note by @{ok[0].get('author', {}).get('username', '?')}") if ok else
                       ("missing", c, "no MR note starting with '" + REVIEW_HEAD + "' with 'Verdict: approve'"
                        + (" (a review was posted, but not approved)" if found else "")))
        elif c == "code-owner":
            try:
                approved = {a["user"]["username"].lower() for a in (src.mr("/approvals") or {}).get("approved_by", [])}
            except PermissionError as e:
                res.append(("unknown", c, f"cannot read approvals: {e}"))
                continue
            for name in areas:
                a = profile.area(name) if profile else None
                if a is None or "code-owner" not in a.checks:
                    continue
                who = owners_usernames(src, a.owners, notes)
                hit = sorted(approved & who)
                res.append(("ok", c, f"{a.name}: approved by @{hit[0]}") if hit else
                           ("missing", c, f"{a.name}: needs an approval from {' '.join(a.owners)} (re-run this job after approving)"))
        elif c.startswith(risk.CHECKLIST):
            text = c[len(risk.CHECKLIST):].strip()
            if desc is None:
                res.append(("unknown", c, "cannot read the MR description"))
            else:
                res.append(("ok", c, "ticked") if text in risk.ticked_checklist(desc) else
                           ("missing", c, f"tick '- [x] {text}' in the avflow section of the MR description"))
    return res


def main(src: Sources | None = None, out=print) -> int:
    src = src or Sources()
    env, notes = src.env, []
    profile = target_profile(src)
    target = env.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "?")
    if profile is None:
        out(f"avflow-risk-check: no {risk.PROFILE.as_posix()} on {target} — nothing to check (run `avflow init`).")
        return 0
    if profile.problems:
        out(f"avflow-risk-check: the profile on {target} has problems — fix it (`avflow risk check`): " + "; ".join(profile.problems))
        return 0
    files = changed_files(src)
    ids = sorted({int(m) for m in REF.findall(env.get("CI_MERGE_REQUEST_TITLE", ""))})
    ticket_areas, prior = ticket_facts(src, ids, notes)
    req = risk.requirements(profile, ticket_areas, files)
    checks = risk.grow(prior["checks"], req.checks)
    areas = dict(prior["areas"])
    for k, v in req.areas.items():
        areas.setdefault(k, v)
    out(f"avflow-risk-check · gate: {profile.gate} · profile from {target} · {len(files)} changed files · "
        f"tickets: {', '.join('#' + str(i) for i in ids) or 'none'}")
    out("Risk areas: " + (", ".join(f"{k} ({v})" for k, v in areas.items()) or "none — standard flow"))
    if risk.PROFILE.as_posix() in files:
        out(f"Note: this MR changes {risk.PROFILE.as_posix()}; the new profile applies after the merge.")
    results = verify(src, profile, areas, checks, notes)
    icon = {"ok": "✅", "missing": "❌", "unknown": "⚠️ "}
    for status, c, detail in results:
        out(f"  {icon[status]} {risk.describe(c).split(' — ')[0]}: {detail}")
    if not checks:
        out("  ✅ No extra checks: standard flow.")
    if req.gaps:
        out("Profile gaps (files of a high-risk ticket outside every area): " + ", ".join(req.gaps))
    for n in dict.fromkeys(notes):
        out(f"Note: {n}")
    blocking = [r for r in results if r[0] == "missing" or (r[0] == "unknown" and r[1] != "plan-confirmation")]
    if blocking and profile.gate == "fail":
        out(f"avflow-risk-check: {len(blocking)} required check(s) missing or not verifiable — the merge is blocked.")
        return 1
    if blocking:
        out(f"avflow-risk-check: {len(blocking)} required check(s) missing or not verifiable (gate = report: not blocking).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
