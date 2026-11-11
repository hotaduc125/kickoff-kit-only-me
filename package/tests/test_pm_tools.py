import json
from datetime import datetime, timezone

from avflow import release_notes as rn
from avflow import report
from avflow.config import TicketConfig
from avflow.init_repo import init_repo

CFG = TicketConfig(url="https://r.test")


# ---------- init
def test_init_creates_standard_files(tmp_path):
    r = init_repo(tmp_path, project="Mateo_v2")
    for f in ("CLAUDE.md", "docs/CONTEXT.md", "docs/adr/0001-record-architecture-decisions.md", "CODEOWNERS",
              ".gitattributes", ".editorconfig", ".gitlab/merge_request_templates/Default.md",
              ".gitlab-ci.avflow.yml", "ci/avflow_redmine_update.py", ".gitlab-ci.yml"):
        assert (tmp_path / f).exists(), f
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "# Mateo_v2" in text and "{project}" not in text
    assert "{date}" not in (tmp_path / "docs/adr/0001-record-architecture-decisions.md").read_text()
    assert "include:" in (tmp_path / ".gitlab-ci.yml").read_text()
    assert len(r["created"]) >= 10


def test_init_never_overwrites_without_force(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("mine")
    (tmp_path / ".gitlab-ci.yml").write_text("stages: [build]\n")
    r = init_repo(tmp_path)
    assert (tmp_path / "CLAUDE.md").read_text() == "mine"
    assert "CLAUDE.md" in r["skipped"]
    assert any("include" in s for s in r["skipped"])
    assert (tmp_path / ".gitlab-ci.yml").read_text() == "stages: [build]\n"
    r2 = init_repo(tmp_path, force=True)
    assert "CLAUDE.md" in r2["overwritten"]


def test_ci_script_compiles():
    import py_compile
    from importlib import resources
    py_compile.compile(str(resources.files("avflow").joinpath("templates/ci/avflow_redmine_update.py")), doraise=True)


# ---------- release notes
def test_commits_in_range_parses_refs():
    out = (f"a1\x1fAdd reset dialog · Refs #12\x1f\x1e"
           f"b2\x1fFix typo\x1fRefs #12 and closes #15\x1e"
           f"c3\x1fUpdate readme\x1f\x1e")
    commits = rn.commits_in_range("v1.0", "HEAD", runner=lambda c, interactive=False: (0, out))
    assert [c["ids"] for c in commits] == [[12], [12, 15], []]


def test_build_release_notes_with_warnings():
    commits = [{"sha": "a1", "subject": "x", "ids": [12]}, {"sha": "c3", "subject": "Update readme", "ids": []}]
    tickets = {12: {"id": 12, "subject": "Reset dialog", "type": "Task", "status": "Ready for test", "machine_side": True},
               15: {"id": 15, "subject": "Parts page", "type": "Task", "status": "In progress", "machine_side": False}}
    text = rn.build(commits, tickets, ["Ready for test", "Resolved", "Closed"], "v1.0", "HEAD")
    assert "#12 Reset dialog **[machine-side]**" in text
    assert "`c3` has no ticket reference" in text and "#15 is 'In progress'" in text
    assert "test bench" in text
    assert text.index("#12 Reset dialog") < text.index("#15 Parts page")


# ---------- report metrics
def issue(i, status="New", version="Release 1", est=None, updated="2026-11-09T10:00:00Z"):
    return {"id": i, "subject": f"T{i}", "status": {"name": status}, "fixed_version": {"name": version},
            "estimated_hours": est, "updated_on": updated}


def test_progress_by_version():
    p = report.progress_by_version([issue(1), issue(2, "In progress"), issue(3, "Closed"), issue(4, "Ready for test", "Release 2")], CFG)
    assert p["Release 1"]["New / Ready"] == 1 and p["Release 1"]["In progress"] == 1 and p["Release 1"]["Done"] == 1
    assert p["Release 2"]["Ready for test"] == 1


def test_over_estimate():
    rows = report.over_estimate([issue(1, est=10), issue(2, est=10), issue(3)], {1: 16, 2: 14, 3: 99})
    assert [r["id"] for r in rows] == [1]


def test_reopened():
    since = datetime(2026, 11, 3, tzinfo=timezone.utc)
    journals = {1: [{"created_on": "2026-11-05T00:00:00Z", "details": [{"name": "status_id", "old_value": "5", "new_value": "3"}]}],
                2: [{"created_on": "2026-11-05T00:00:00Z", "details": [{"name": "status_id", "old_value": "2", "new_value": "3"}]}],
                3: [{"created_on": "2026-10-01T00:00:00Z", "details": [{"name": "status_id", "old_value": "5", "new_value": "3"}]}]}
    assert report.reopened(journals, {"5", "6"}, since) == [1]


def test_mr_metrics():
    mrs = [{"iid": 1, "created_at": "2026-11-05T00:00:00Z", "merged_at": "2026-11-05T10:00:00Z"},
           {"iid": 2, "created_at": "2026-11-05T00:00:00Z", "merged_at": "2026-11-06T06:00:00Z"}]
    m = report.mr_metrics(mrs, {1: "success", 2: "failed"})
    assert m == {"merged": 2, "median_hours_to_merge": 20.0, "first_pipeline_green": "1/2"}


class FakeAdapter:
    def list_issues(self, **p):
        return [issue(1, est=4), issue(2, "Closed")]

    def time_entries(self, **p):
        return [{"issue": {"id": 1}, "hours": 8}]

    def statuses(self):
        return [{"id": 1, "name": "New"}, {"id": 5, "name": "Closed", "is_closed": True}]

    def issue_raw(self, i, include=""):
        return {"journals": []}


def test_build_report_end_to_end_without_gitlab():
    text = report.build_report(FakeAdapter(), CFG, "mateo", 7, runner=lambda c, interactive=False: (1, "glab: not a repo"),
                               now=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert "| Release 1 |" in text and "#1 T1 — estimated 4 h, spent 8.0 h" in text and "not available" in text


def test_build_report_with_gitlab():
    mrs = json.dumps([{"iid": 7, "created_at": "2026-11-08T00:00:00Z", "merged_at": "2026-11-08T05:00:00Z"}])

    def runner(cmd, interactive=False):
        return (0, mrs) if "pipelines" not in cmd[-1] else (0, json.dumps([{"status": "success"}]))
    text = report.build_report(FakeAdapter(), CFG, "mateo", 7, runner=runner, now=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert "Merged: 1" in text and "First pipeline green: 1/1" in text


def test_ci_template_has_secret_scan_on_mr_and_develop():
    import yaml
    from importlib import resources
    d = yaml.safe_load(resources.files("avflow").joinpath("templates/.gitlab-ci.avflow.yml").read_text())
    job = d["avflow-secret-scan"]
    assert job["stage"] == ".pre" and job["image"]["name"].startswith("zricethezav/gitleaks:v")
    assert job["variables"]["GIT_DEPTH"] == "0"
    rules = [r["if"] for r in job["rules"]]
    assert any("merge_request_event" in r for r in rules) and any("develop" in r for r in rules)
    assert any("gitleaks detect" in line and "--redact" in line for line in job["script"])
    assert {"avflow-mr-title", "avflow-ready-for-test"} <= set(d)


def test_reviewer_blocks_weakened_tests():
    from importlib import resources
    t = resources.files("avflow").joinpath("agents/avflow-reviewer.md").read_text()
    assert "weakened, skipped or disabled" in t


def test_init_hint_ignores_commented_include(tmp_path):
    (tmp_path / ".gitlab-ci.yml").write_text("# add: include: - local: .gitlab-ci.avflow.yml\nstages: [test]\n")
    r = init_repo(tmp_path)
    assert any("include" in s for s in r["skipped"])


def test_init_no_hint_when_include_present(tmp_path):
    (tmp_path / ".gitlab-ci.yml").write_text("include:\n  - local: .gitlab-ci.avflow.yml\nstages: [test]\n")
    r = init_repo(tmp_path)
    assert not any("include" in s for s in r["skipped"])
