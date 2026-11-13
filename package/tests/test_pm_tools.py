import json
from datetime import datetime, timezone

from avflow import release_notes as rn
from avflow import report
from avflow.config import TicketConfig
from avflow.init_repo import init_repo

CFG = TicketConfig(url="https://r.test")


# ---------- init
def test_init_creates_standard_files(tmp_path):
    r = init_repo(tmp_path, project="Shop_v2")
    for f in ("CLAUDE.md", "docs/CONTEXT.md", "docs/adr/0001-record-architecture-decisions.md", "CODEOWNERS",
              ".gitattributes", ".editorconfig", ".gitlab/merge_request_templates/Default.md",
              ".gitlab-ci.avflow.yml", "ci/avflow_redmine_update.py", ".gitlab-ci.yml"):
        assert (tmp_path / f).exists(), f
    text = (tmp_path / "CLAUDE.md").read_text()
    assert "# Shop_v2" in text and "{project}" not in text
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
    tickets = {12: {"id": 12, "subject": "Reset dialog", "type": "Task", "status": "Ready for test",
                    "risk_areas": ["Machine control", "Build and CI"]},
               15: {"id": 15, "subject": "Parts page", "type": "Task", "status": "In progress", "risk_areas": []}}
    text = rn.build(commits, tickets, ["Ready for test", "Resolved", "Closed"], "v1.0", "HEAD")
    assert "#12 Reset dialog **[Machine control]** **[Build and CI]**" in text
    assert "`c3` has no ticket reference" in text and "#15 is 'In progress'" in text
    assert "High-risk changes (Build and CI, Machine control)" in text
    assert "machine-side" not in text.lower() and "simulator" not in text.lower()
    assert "- [ ] Regression tests green" in text
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
    text = report.build_report(FakeAdapter(), CFG, "shop", 7, runner=lambda c, interactive=False: (1, "glab: not a repo"),
                               now=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert "| Release 1 |" in text and "#1 T1 — estimated 4 h, spent 8.0 h" in text and "not available" in text


def test_build_report_with_gitlab():
    mrs = json.dumps([{"iid": 7, "created_at": "2026-11-08T00:00:00Z", "merged_at": "2026-11-08T05:00:00Z"}])

    def runner(cmd, interactive=False):
        return (0, mrs) if "pipelines" not in cmd[-1] else (0, json.dumps([{"status": "success"}]))
    text = report.build_report(FakeAdapter(), CFG, "shop", 7, runner=runner, now=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert "Merged: 1" in text and "First pipeline green: 1/1" in text


# ---------- report: risk section (from the private '[avflow] required' notes)
def _note(stage, areas, checks, gaps=None, when="2026-11-08T00:00:00Z", private=True):
    from avflow import risk
    return {"created_on": when, "private_notes": private, "notes": risk.required_line(stage, areas, checks, gaps) + "\nbody"}


SINCE = datetime(2026, 11, 3, tzinfo=timezone.utc)
MC = ["plan-confirmation", "independent-review", "code-owner"]


def risk_journals():
    return {
        1: [_note("start", {"Machine control": "ticket"}, MC), _note("plan", {"Machine control": "ticket"}, MC),
            _note("review", {"Machine control": "ticket"}, MC, ["src/orders.py"])],
        2: [_note("start", {}, []), _note("plan", {"Machine control": "plan"}, MC),
            _note("review", {"Machine control": "plan", "Build and CI": "review"}, MC)],
        3: [_note("start", {}, []), _note("plan", {}, []), _note("review", {}, [])],
        4: [_note("plan", {}, ["plan-confirmation", "independent-review"]),                  # strict default
            _note("review", {}, ["plan-confirmation", "independent-review"])],
        5: [_note("review", {"Payments": "ticket"}, ["independent-review"], when="2026-10-01T00:00:00Z")],  # too old
        6: [_note("review", {"Payments": "ticket"}, ["independent-review"], private=False)],               # public: ignored
        7: [_note("start", {"Payments": "ticket"}, ["independent-review"])],                               # not reviewed yet
    }


def test_risk_summary_counts_reviewed_tickets_only():
    s = report.risk_summary(risk_journals(), SINCE)
    assert s["reviewed"] == [1, 2, 3, 4]
    assert s["high_risk"] == [1, 2] and s["default_only"] == [4]
    assert s["areas"]["Machine control"] == {"ticket": [1], "plan": [2], "review": []}
    assert s["areas"]["Build and CI"] == {"ticket": [], "plan": [], "review": [2]}
    assert s["missed_at_plan"] == {2: ["Build and CI"]}
    assert s["gaps"] == {1: ["src/orders.py"]}


def test_risk_section_text():
    text = "\n".join(report.risk_section(report.risk_summary(risk_journals(), SINCE)))
    assert "## Risk (4 tickets reviewed in the period)" in text
    assert "High-risk changes: 2 of 4 (50%)" in text and "strict default only: 1" in text
    assert "| Machine control | 2 | 1 | 1 | 0 |" in text and "| Build and CI | 1 | 0 | 0 | 1 |" in text
    assert "#2: Build and CI" in text and "#1: `src/orders.py`" in text and "avflow risk suggest" in text
    assert "Payments" not in text


def test_risk_section_without_reviews():
    text = "\n".join(report.risk_section(report.risk_summary({}, SINCE)))
    assert "No ticket reached review_requirements in the period" in text


def test_build_report_has_risk_section():
    class A(FakeAdapter):
        def issue_raw(self, i, include=""):
            return {"journals": risk_journals().get(i, [])}
    text = report.build_report(A(), CFG, "shop", 7, runner=lambda c, interactive=False: (1, ""),
                               now=datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert "## Risk (2 tickets reviewed in the period)" in text and "Machine control" in text


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


# ---------- init: risk profile, CODEOWNERS, CI gate (3.0 phase 2)
def test_init_writes_a_profile_from_the_detected_stack(tmp_path):
    from datetime import date
    from avflow import risk
    (tmp_path / "App.sln").write_text("")
    r = init_repo(tmp_path, project="Shop_v2", today=date(2026, 11, 13))
    assert r["stacks"] == ["dotnet"] and ".avflow/project.toml" in r["created"]
    p = risk.load(tmp_path)
    assert p.problems == [] and p.name == "Shop_v2" and p.presets == ["dotnet"] and p.gate == "report"
    co = (tmp_path / "CODEOWNERS").read_text()
    assert risk.codeowners_in_sync(co, p) and "TODO" not in co
    assert risk.ci_copy_current((tmp_path / "ci/avflow_risk.py").read_text())
    assert (tmp_path / "ci/avflow_risk_check.py").exists()


def test_init_stack_option_and_unknown_stack(tmp_path):
    import pytest
    assert init_repo(tmp_path, stacks=["node", "python"])["stacks"] == ["node", "python"]
    with pytest.raises(ValueError):
        init_repo(tmp_path / "x", stacks=["cobol"])


def test_init_keeps_an_existing_profile_and_codeowners(tmp_path):
    (tmp_path / ".avflow").mkdir()
    (tmp_path / ".avflow/project.toml").write_text('[[risk.area]]\nname = "A"\nchecks = ["independent-review"]\n')
    (tmp_path / "CODEOWNERS").write_text("/x @y\n")
    r = init_repo(tmp_path)
    assert ".avflow/project.toml" in r["skipped"] and "CODEOWNERS" in r["skipped"]
    assert (tmp_path / "CODEOWNERS").read_text() == "/x @y\n"
    assert "A" in (tmp_path / ".avflow/project.toml").read_text()


def test_init_cli_prints_next_steps(tmp_path, capsys, monkeypatch):
    from avflow import cli
    assert cli.main(["init", "--path", str(tmp_path), "--stack", "go"]) == 0
    out = capsys.readouterr().out
    assert "go" in out and "AVFLOW_GITLAB_TOKEN" in out and "avflow risk sync" in out
    assert cli.main(["init", "--path", str(tmp_path / "y"), "--stack", "cobol"]) == 1
