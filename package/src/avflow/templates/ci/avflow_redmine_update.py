"""CI step (avflow): after a merge into develop, move the referenced Redmine tickets from "In review" to
"Ready for test", with a private note linking the commit and pipeline. Standard library only."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

REF = re.compile(r"(?:refs|closes|fixes)\s+#(\d+)", re.IGNORECASE)


def call(url, key, method, path, body=None):
    req = urllib.request.Request(url.rstrip("/") + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Redmine-API-Key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def main() -> int:
    url, key = os.environ.get("REDMINE_URL"), os.environ.get("REDMINE_CI_API_KEY")
    if not url or not key:
        print("REDMINE_URL / REDMINE_CI_API_KEY not set — skipping.")
        return 0
    frm = os.environ.get("AVFLOW_STATUS_IN_REVIEW", "In review").lower()
    to = os.environ.get("AVFLOW_STATUS_READY_FOR_TEST", "Ready for test").lower()
    before, sha = os.environ.get("CI_COMMIT_BEFORE_SHA", ""), os.environ.get("CI_COMMIT_SHA", "HEAD")
    rng = sha if not before or set(before) == {"0"} else f"{before}..{sha}"
    try:
        log = subprocess.run(["git", "log", "--format=%B", rng], capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        log = os.environ.get("CI_COMMIT_MESSAGE", "")
    ids = sorted({int(m) for m in REF.findall(log)})
    if not ids:
        print("No 'Refs #id' in the merged commits.")
        return 0
    statuses = {s["name"].lower(): s["id"] for s in call(url, key, "GET", "/issue_statuses.json")["issue_statuses"]}
    if to not in statuses:
        print(f"Status '{to}' not found in Redmine.")
        return 1
    link = f"{os.environ.get('CI_PROJECT_URL', '')}/-/commit/{sha} · pipeline {os.environ.get('CI_PIPELINE_URL', '')}"
    for i in ids:
        try:
            current = call(url, key, "GET", f"/issues/{i}.json")["issue"]["status"]["name"]
        except urllib.error.HTTPError as e:
            print(f"#{i}: cannot read ({e.code}) — skipped")
            continue
        if current.lower() == frm:
            call(url, key, "PUT", f"/issues/{i}.json", {"issue": {"status_id": statuses[to], "private_notes": True,
                                                                  "notes": f"Merged into develop ({link}). Ready for test."}})
            print(f"#{i}: {current} → Ready for test")
        else:
            print(f"#{i}: status is '{current}' — unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
