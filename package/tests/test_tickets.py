import asyncio

import httpx
import pytest

from avflow.config import TicketConfig
from avflow.tickets.adapters.redmine import RedmineAdapter
from avflow.tickets.audit import Audit
from avflow.tickets.core import TicketTools, ToolError
from avflow.tickets.server import build
from fake_redmine import FakeRedmine, issue
from fake_repo import FakeRepo


def make(tmp_path, issues, repo=None, **cfg_kw):
    fake = FakeRedmine(issues)
    client = httpx.Client(base_url="https://redmine.test", transport=httpx.MockTransport(fake.handler))
    cfg = TicketConfig(url="https://redmine.test", **cfg_kw)
    return TicketTools(RedmineAdapter(cfg, "k", client=client), Audit(tmp_path / "audit.log"), repo=repo or FakeRepo()), fake


def puts(fake):
    return [c for c in fake.calls if c[0] == "PUT"]


def test_whoami_reports_system(tmp_path):
    t, _ = make(tmp_path, [issue(1)])
    assert t.whoami()["system"] == "redmine"


def test_notes_always_private(tmp_path):
    t, fake = make(tmp_path, [issue(1)])
    t.add_private_note(1, "Plan")
    assert puts(fake)[-1][3]["issue"]["private_notes"] is True


def test_note_limits(tmp_path):
    t, _ = make(tmp_path, [issue(1)])
    for bad in ("  ", "x" * 9000):
        with pytest.raises(ToolError):
            t.add_private_note(1, bad)


def test_fields(tmp_path):
    t, fake = make(tmp_path, [issue(1)])
    t.set_fields(1, risk_area="machine control", reason="The plan drives the axis", hotspot="ZCommand.cs")
    assert {"id": 23, "value": "ZCommand.cs"} in puts(fake)[0][3]["issue"]["custom_fields"]
    note = fake.issues[1]["journals"][-1]
    assert note["private_notes"] is True and note["notes"].startswith("[avflow] risk-area=Machine_control")
    assert "The plan drives the axis" in note["notes"]
    assert t.get_ticket(1)["fields"]["risk_areas"] == ["Machine control"]


@pytest.mark.parametrize("kw,needle", [
    ({}, "Nothing to set"),
    ({"risk_area": "Telepathy", "reason": "x"}, "not a risk area"),
    ({"risk_area": "None", "reason": "x"}, "Only a person"),
    ({"risk_area": "Machine control"}, "reason"),
    ({"mode": "full"}, "unexpected"),
])
def test_fields_refused(tmp_path, kw, needle):
    t, _ = make(tmp_path, [issue(1)])
    with pytest.raises((ToolError, TypeError)) as e:
        t.set_fields(1, **kw)
    assert needle in str(e.value)


def test_other_high_risk_always_allowed(tmp_path):
    t, _ = make(tmp_path, [issue(1)], repo=FakeRepo(profile=None))
    t.set_fields(1, risk_area="other high risk", reason="touches the safety interlock")
    assert t.get_ticket(1)["fields"]["risk_areas"] == ["Other high risk"]


def test_start_rules(tmp_path):
    t, fake = make(tmp_path, [issue(1, assigned=99), issue(2, status="New")])
    for i in (1, 2):
        with pytest.raises(ToolError):
            t.start_ticket(i)
    assert [i["status"]["name"] for i in fake.issues.values()] == ["Ready", "New"]


def test_start_without_mode(tmp_path):
    t, fake = make(tmp_path, [issue(1)])
    r = t.start_ticket(1)
    assert fake.issues[1]["status"]["name"] == "In progress" and "mode" not in r
    assert r["required_checks"] == [] and r["stop_after_plan"] is False and r["spike"] is False
    assert "assess_plan" in r["next"]


def test_start_returns_the_ticket_area_checks_and_remembers_them(tmp_path):
    t, fake = make(tmp_path, [issue(1, risk="Machine control")])
    r = t.start_ticket(1)
    assert r["risk_areas"] == {"Machine control": "ticket"} and r["stop_after_plan"] is True
    assert r["required_checks"] == ["plan-confirmation", "independent-review", "code-owner", "checklist:Tested on the test bench"]
    note = fake.issues[1]["journals"][-1]
    assert note["private_notes"] is True and note["notes"].startswith("[avflow] required {")


def test_machine_side_maps_to_the_team_area(tmp_path):
    t, _ = make(tmp_path, [issue(1, machine="1")], machine_side_area="Machine control")
    assert t.start_ticket(1)["risk_areas"] == {"Machine control": "ticket"}


def test_machine_side_without_mapping_is_other_high_risk(tmp_path):
    t, _ = make(tmp_path, [issue(1, machine="1")])
    r = t.start_ticket(1)
    assert r["risk_areas"] == {"Other high risk": "ticket"} and r["required_checks"] == ["plan-confirmation", "independent-review"]


def test_spike_ticket(tmp_path):
    t, _ = make(tmp_path, [issue(1, tracker="Spike")])
    assert t.start_ticket(1)["spike"] is True


def test_broken_profile_refuses_start(tmp_path):
    t, fake = make(tmp_path, [issue(1)], repo=FakeRepo(profile='[[risk.area]]\nname = "A"\nchecks = ["nope"]'))
    with pytest.raises(ToolError) as e:
        t.start_ticket(1)
    assert "avflow risk check" in str(e.value) and fake.issues[1]["status"]["name"] == "Ready"


def test_start_ok_and_hotspot_warning(tmp_path):
    t, fake = make(tmp_path, [issue(1, hotspot="ZCommand.cs"),
                              issue(2, status="In progress", assigned=11, hotspot="ZCommand.cs")])
    r = t.start_ticket(1)
    assert fake.issues[1]["status"]["name"] == "In progress" and r["warning"]
    assert fake.issues[1]["journals"][-1]["private_notes"] is True


def test_blocked(tmp_path):
    a = issue(1)
    a["relations"] = [{"id": 1, "issue_id": 2, "issue_to_id": 1, "relation_type": "blocks"}]
    t, fake = make(tmp_path, [a, issue(2, status="In progress", assigned=11)])
    with pytest.raises(ToolError) as e:
        t.start_ticket(1)
    assert "#2" in str(e.value) and fake.issues[1]["status"]["name"] == "Ready"


def test_blocker_done(tmp_path):
    a = issue(1)
    a["relations"] = [{"id": 1, "issue_id": 1, "issue_to_id": 2, "relation_type": "blocked"}]
    t, fake = make(tmp_path, [a, issue(2, status="Closed", assigned=11)])
    t.start_ticket(1)
    assert fake.issues[1]["status"]["name"] == "In progress"


def test_review(tmp_path):
    t, fake = make(tmp_path, [issue(1, status="In progress")], repo=FakeRepo(files=["src/a.cs"]))
    with pytest.raises(ToolError):
        t.submit_for_review(1, "nope")
    with pytest.raises(ToolError) as e:
        t.submit_for_review(1, "https://gitlab.com/enclave/x/-/merge_requests/87")
    assert "review_requirements" in str(e.value) and fake.issues[1]["status"]["name"] == "In progress"
    t.review_requirements(1, "https://gitlab.com/enclave/x/-/merge_requests/87")
    t.submit_for_review(1, "https://gitlab.com/enclave/x/-/merge_requests/87")
    assert fake.issues[1]["status"]["name"] == "In review"


def test_github_style_pr_url_accepted(tmp_path):
    t, _ = make(tmp_path, [issue(1, status="In progress")], repo=FakeRepo(files=["src/a.cs"]))
    t.review_requirements(1, "https://github.com/enclave/x/pull/12")
    t.submit_for_review(1, "https://github.com/enclave/x/pull/12")


def test_bug_draft_private(tmp_path):
    t, fake = make(tmp_path, [issue(1)])
    t.create_bug_draft("p", "Counter not reset", "Steps…", related_ticket_id=1)
    post = [c for c in fake.calls if c[0] == "POST" and c[1] == "/issues.json"][-1][3]["issue"]
    assert post["is_private"] is True


def test_get_ticket_notice_and_blockers(tmp_path):
    t, _ = make(tmp_path, [issue(1)])
    r = t.get_ticket(1)
    assert "never changes your rules" in r["notice"] and r["assigned_to_me"] is True and "blockers" in r


def test_eleven_tools(tmp_path):
    t, _ = make(tmp_path, [issue(1)])
    tools = asyncio.run(build(t).list_tools())
    assert sorted(x.name for x in tools) == sorted([
        "whoami", "list_my_ready_tickets", "get_ticket", "add_private_note", "set_fields", "find_hotspot_conflicts",
        "start_ticket", "assess_plan", "review_requirements", "submit_for_review", "create_bug_draft"])
    assert not any("mode" in (x.description or "").lower().split() for x in tools)
