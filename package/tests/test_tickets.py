import asyncio

import httpx
import pytest

from kickoff_kit.config import TicketConfig
from kickoff_kit.tickets.adapters.redmine import RedmineAdapter
from kickoff_kit.tickets.audit import Audit
from kickoff_kit.tickets.core import TicketTools, ToolError
from kickoff_kit.tickets.server import build
from fake_redmine import FakeRedmine, issue


def make(tmp_path, issues):
    fake = FakeRedmine(issues)
    client = httpx.Client(base_url="https://redmine.test", transport=httpx.MockTransport(fake.handler))
    cfg = TicketConfig(url="https://redmine.test")
    return TicketTools(RedmineAdapter(cfg, "k", client=client), Audit(tmp_path / "audit.log")), fake


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
    with pytest.raises(ToolError):
        t.set_fields(1, mode="yolo")
    t.set_fields(1, mode="FULL", machine_side=True, hotspot="ZCommand.cs")
    sent = puts(fake)[-1][3]["issue"]["custom_fields"]
    assert {"id": 21, "value": "full"} in sent and {"id": 22, "value": "1"} in sent and {"id": 23, "value": "ZCommand.cs"} in sent


def test_machine_side_no_downgrade(tmp_path):
    t, _ = make(tmp_path, [issue(1, machine="1")])
    with pytest.raises(ToolError):
        t.set_fields(1, machine_side=False)


def test_start_rules(tmp_path):
    t, _ = make(tmp_path, [issue(1, assigned=99, mode="plan"), issue(2, status="New", mode="plan"), issue(3)])
    for i in (1, 2, 3):
        with pytest.raises(ToolError):
            t.start_ticket(i)


def test_start_ok_and_hotspot_warning(tmp_path):
    t, fake = make(tmp_path, [issue(1, mode="full", hotspot="ZCommand.cs"),
                              issue(2, status="In progress", assigned=11, hotspot="ZCommand.cs")])
    r = t.start_ticket(1)
    assert fake.issues[1]["status"]["name"] == "In progress" and r["warning"]
    assert fake.issues[1]["journals"][-1]["private_notes"] is True


def test_blocked(tmp_path):
    a = issue(1, mode="plan")
    a["relations"] = [{"id": 1, "issue_id": 2, "issue_to_id": 1, "relation_type": "blocks"}]
    t, fake = make(tmp_path, [a, issue(2, status="In progress", assigned=11)])
    with pytest.raises(ToolError) as e:
        t.start_ticket(1)
    assert "#2" in str(e.value) and fake.issues[1]["status"]["name"] == "Ready"


def test_blocker_done(tmp_path):
    a = issue(1, mode="plan")
    a["relations"] = [{"id": 1, "issue_id": 1, "issue_to_id": 2, "relation_type": "blocked"}]
    t, fake = make(tmp_path, [a, issue(2, status="Closed", assigned=11)])
    t.start_ticket(1)
    assert fake.issues[1]["status"]["name"] == "In progress"


def test_review(tmp_path):
    t, fake = make(tmp_path, [issue(1, status="In progress", mode="plan")])
    with pytest.raises(ToolError):
        t.submit_for_review(1, "nope")
    t.submit_for_review(1, "https://gitlab.com/enclave/x/-/merge_requests/87")
    assert fake.issues[1]["status"]["name"] == "In review"


def test_github_style_pr_url_accepted(tmp_path):
    t, _ = make(tmp_path, [issue(1, status="In progress", mode="plan")])
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


def test_nine_tools(tmp_path):
    t, _ = make(tmp_path, [issue(1)])
    names = sorted(x.name for x in asyncio.run(build(t).list_tools()))
    assert names == sorted(["whoami", "list_my_ready_tickets", "get_ticket", "add_private_note", "set_fields",
                            "find_hotspot_conflicts", "start_ticket", "submit_for_review", "create_bug_draft"])
