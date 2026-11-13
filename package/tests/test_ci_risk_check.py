"""CI job avflow-risk-check (templates/ci/avflow_risk_check.py) with fake git, GitLab and Redmine."""
import importlib.util
import subprocess
import urllib.error
from pathlib import Path

import pytest

from avflow import risk

SCRIPT = Path(__file__).parents[1] / "src/avflow/templates/ci/avflow_risk_check.py"
spec = importlib.util.spec_from_file_location("avflow_risk_check", SCRIPT)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

PROFILE = """
[ci]
gate = "{gate}"

[[risk.area]]
name   = "Machine control"
paths  = ["source/Motion/**"]
owners = ["@q", "@leads"]
checks = ["independent-review", "code-owner", "checklist:Tested on the test bench"]

[[risk.area]]
name   = "Payments"
paths  = []
checks = ["plan-confirmation"]
"""
API = "https://gitlab.enclave.vn/api/v4"
MR_PATH = f"{API}/projects/7/merge_requests/87"
APPROVE = "### avflow — independent review\nStage 1: OK\n**Verdict:** approve"


class World:
    def __init__(self, gate="report", files=("source/Motion/Z.cs",), title="Add pause. Refs #12", profile=True,
                 token="t", description="", notes=(), approved=(), issue=None, groups=None):
        self.env = {"CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "develop", "CI_MERGE_REQUEST_DIFF_BASE_SHA": "b",
                    "CI_COMMIT_SHA": "h", "CI_MERGE_REQUEST_TITLE": title, "CI_API_V4_URL": API, "CI_PROJECT_ID": "7",
                    "CI_MERGE_REQUEST_IID": "87", "REDMINE_URL": "https://redmine.test", "REDMINE_CI_API_KEY": "k"}
        if token:
            self.env["AVFLOW_GITLAB_TOKEN"] = token
        self.profile = PROFILE.format(gate=gate) if profile else None
        self.files, self.description, self.notes, self.approved = list(files), description, list(notes), list(approved)
        self.issue = issue if issue is not None else {"custom_fields": [], "description": "", "journals": []}
        self.groups = groups or {}
        self.git_calls, self.out = [], []

    def git(self, *args):
        self.git_calls.append(args)
        if args[0] == "show":
            assert args[1] == "origin/develop:.avflow/project.toml"       # always the TARGET branch
            if self.profile is None:
                raise subprocess.CalledProcessError(128, "git")
            return self.profile
        if args[0] == "diff":
            return "\n".join(self.files)
        return ""

    def http(self, url, headers):
        if url.startswith("https://redmine.test/issues/12.json"):
            assert headers == {"X-Redmine-API-Key": "k"}
            return {"issue": self.issue}
        assert headers == {"PRIVATE-TOKEN": "t"}
        if url == MR_PATH:
            return {"description": self.description}
        if url.startswith(MR_PATH + "/notes"):
            return [{"body": b, "system": False, "author": {"username": "reviewer"}} for b in self.notes]
        if url == MR_PATH + "/approvals":
            return {"approved_by": [{"user": {"username": u}} for u in self.approved]}
        if "/groups/" in url:
            name = url.split("/groups/")[1].split("/")[0]
            if name in self.groups:
                return [{"username": u} for u in self.groups[name]]
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        raise AssertionError(url)

    def run(self):
        code = ci.main(ci.Sources(self.env, self.git, self.http), out=self.out.append)
        return code, "\n".join(self.out)


def done_description():
    return risk.update_mr_description("Refs #12", ["checklist:Tested on the test bench"]).replace("- [ ]", "- [x]")


def test_all_checks_done_passes_even_in_fail_mode():
    code, out = World(gate="fail", description=done_description(), notes=[APPROVE], approved=["q"]).run()
    assert code == 0 and "❌" not in out and "approved by @q" in out and "ticked" in out


def test_report_mode_lists_missing_checks_and_passes():
    code, out = World().run()
    assert code == 0 and out.count("❌") == 3 and "gate = report: not blocking" in out
    assert "re-run this job after approving" in out


def test_fail_mode_blocks():
    code, out = World(gate="fail").run()
    assert code == 1 and "merge is blocked" in out


def test_group_owner_members_count():
    code, out = World(gate="fail", description=done_description(), notes=[APPROVE], approved=["dana"],
                      groups={"leads": ["dana"]}).run()
    assert code == 0 and "approved by @dana" in out


def test_review_not_approved_is_missing():
    w = World(gate="fail", description=done_description(), approved=["q"],
              notes=["### avflow — independent review\nVerdict: changes requested"])
    code, out = w.run()
    assert code == 1 and "not approved" in out


def test_review_note_must_start_with_the_heading():
    code, out = World(gate="fail", description=done_description(), approved=["q"],
                      notes=["I think the avflow independent review is fine. Verdict: approve"]).run()
    assert code == 1


def test_ticks_outside_the_avflow_section_do_not_count():
    code, out = World(gate="fail", notes=[APPROVE], approved=["q"],
                      description="- [x] Tested on the test bench").run()
    assert code == 1 and "tick '- [x] Tested on the test bench'" in out


def test_no_token_cannot_verify_and_fail_mode_blocks():
    w = World(gate="fail", token=None, description="x")
    w.env["CI_MERGE_REQUEST_DESCRIPTION"] = done_description()
    code, out = w.run()
    assert code == 1 and "AVFLOW_GITLAB_TOKEN" in out and "ticked" in out      # description from the CI variable


def test_ticket_area_counts_without_matching_files():
    issue = {"custom_fields": [], "description": "Risk area: Payments", "journals": []}
    code, out = World(files=["src/billing/x.cs"], issue=issue).run()
    assert "Payments (ticket)" in out and "Plan confirmation" in out and "Profile gaps" in out


def test_risk_area_field_of_the_ticket_counts():
    issue = {"custom_fields": [{"name": "Risk area", "value": ["Payments"]}], "description": "", "journals": []}
    code, out = World(files=["README.md"], issue=issue).run()
    assert "Payments (ticket)" in out


def test_checks_from_the_plan_stage_stay_required():
    note = risk.required_line("plan", {"Payments": "plan"}, ["plan-confirmation"])
    issue = {"custom_fields": [], "description": "", "journals": [{"notes": note, "private_notes": True}]}
    code, out = World(files=["README.md"], issue=issue).run()
    assert "Payments (plan)" in out and "Plan confirmation" in out


def test_public_notes_are_ignored():
    note = risk.required_line("plan", {"Payments": "plan"}, ["plan-confirmation"])
    issue = {"custom_fields": [], "description": "", "journals": [{"notes": note, "private_notes": False}]}
    code, out = World(files=["README.md"], issue=issue).run()
    assert "Payments" not in out and "view private notes" in out


def test_profile_is_read_from_the_target_branch_only():
    w = World(files=[".avflow/project.toml"])
    code, out = w.run()
    assert ("show", "origin/develop:.avflow/project.toml") in w.git_calls and "applies after the merge" in out


def test_no_profile_on_target_passes():
    code, out = World(gate="fail", profile=False).run()
    assert code == 0 and "nothing to check" in out


def test_unreadable_ticket_falls_back_to_the_diff():
    w = World(files=["README.md"])
    del w.env["REDMINE_CI_API_KEY"]
    code, out = w.run()
    assert code == 0 and "could not be read" in out and "standard flow" in out


@pytest.mark.parametrize("title", ["No ticket", "Refs #12"])
def test_standard_flow_passes(title):
    code, out = World(gate="fail", files=["README.md"], title=title).run()
    assert code == 0 and "No extra checks" in out


def test_the_copy_written_by_init_runs_standalone(tmp_path):
    """In a project, the job runs `python ci/avflow_risk_check.py` with only the standard library and the copy."""
    import subprocess as sp
    import sys
    from avflow.init_repo import init_repo
    init_repo(tmp_path, stacks=["python"])
    code = ("import sys; sys.path.insert(0, 'ci'); import avflow_risk_check as c; "
            "assert c.risk.__name__ == 'avflow_risk', c.risk.__name__; print(c.risk.preset_names.__name__)")
    r = sp.run([sys.executable, "-I", "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
