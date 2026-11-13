"""avflow on a Redmine without custom fields (no admin rights): fields from the description and private notes."""
import httpx
import pytest

from avflow import cli
from avflow.config import TicketConfig
from avflow.tickets.adapters.redmine import RedmineAdapter
from avflow.tickets.audit import Audit
from avflow.tickets.core import TicketTools, ToolError
from fake_redmine import FakeRedmine, issue
from fake_repo import FakeRepo

SIZE = "## Size and mode\nEstimate: 1–2 h · Machine-side: {ms} · Hotspot: {hs}\n"


def plain(i, status="Ready", assigned=10, ms="no", hs="none", extra=""):
    t = issue(i, status=status, assigned=assigned)
    t["custom_fields"] = []                       # no custom fields in this Redmine
    t["description"] = "## Context\nSomething.\n\n" + SIZE.format(ms=ms, hs=hs) + extra
    return t


def make(tmp_path, issues, **cfg_kw):
    fake = FakeRedmine(issues)
    client = httpx.Client(base_url="https://redmine.test", transport=httpx.MockTransport(fake.handler))
    cfg = TicketConfig(url="https://redmine.test", **cfg_kw)
    return TicketTools(RedmineAdapter(cfg, "k", client=client), Audit(tmp_path / "a.log"), repo=FakeRepo()), fake


@pytest.mark.parametrize("text,expected", [
    ("Machine-side: yes · Hotspot: src/Settings.cs", {"machine_side": True, "hotspot": "src/Settings.cs"}),
    ("**Machine-side:** no · **Hotspot:** none", {"machine_side": False, "hotspot": None}),
    ("machine side: YES | hotspot: `ZCommand.cs`", {"machine_side": True, "hotspot": "ZCommand.cs"}),
    ("Hotspot: TODO before Ready", {"hotspot": None}),
    ("Estimate: 2 h · Risk area: Machine control · Hotspot: none", {"risk_areas": ["Machine control"]}),
    ("**Risk area:** Payments, Auth", {"risk_areas": ["Payments", "Auth"]}),
    ("Risk area: None", {"risk_areas": []}),
    ("High risk: yes", {"risk_areas": ["Other high risk"]}),
    ("High risk: no", {"risk_areas": []}),
    ("Type: spike · Estimate: 1 d", {"spike": True}),
    ("Proposed mode: plan", {}),
])
def test_description_parsing(text, expected):
    got = RedmineAdapter._desc_fields(text)
    assert {k: got[k] for k in expected} == expected
    assert "mode" not in got


def test_fields_from_description(tmp_path):
    t, _ = make(tmp_path, [plain(1, ms="no", hs="src/Settings.cs", extra="Risk area: Build and CI\n")])
    f = t.get_ticket(1)["fields"]
    assert f["risk_areas"] == ["Build and CI"] and f["hotspot"] == "src/Settings.cs" and "mode" not in f
    assert f["source"] == "description and private notes"


def test_machine_side_line_maps_to_the_team_area(tmp_path):
    t, _ = make(tmp_path, [plain(1, ms="yes")], machine_side_area="Machine control")
    assert t.get_ticket(1)["fields"]["risk_areas"] == ["Machine control"]
    t2, _ = make(tmp_path, [plain(1, ms="yes")])
    assert t2.get_ticket(1)["fields"]["risk_areas"] == ["Other high risk"]


def test_start_works_without_any_mode(tmp_path):
    t, fake = make(tmp_path, [plain(1)])
    t.start_ticket(1)
    assert fake.issues[1]["status"]["name"] == "In progress"


def test_old_mode_notes_are_ignored(tmp_path):
    x = plain(1)
    x["journals"] = [{"notes": "[avflow] mode=full · machine-side=yes", "private_notes": True}]
    t, _ = make(tmp_path, [x])
    f = t.get_ticket(1)["fields"]
    assert "mode" not in f and f["risk_areas"] == ["Other high risk"]       # a 2.x raise of Machine-side still counts


def test_agent_adds_area_in_a_private_note_never_in_the_description(tmp_path):
    t, fake = make(tmp_path, [plain(1, extra="Risk area: Build and CI\n")])
    t.set_fields(1, risk_area="Machine control", reason="plan touches ZCommand")
    assert not [c for c in fake.calls if c[0] == "PUT" and "description" in (c[3] or {}).get("issue", {})]
    assert t.get_ticket(1)["fields"]["risk_areas"] == ["Build and CI", "Machine control"]


def test_public_note_with_marker_is_ignored(tmp_path):
    x = plain(1)
    x["journals"] = [{"notes": "[avflow] risk-area=Machine_control", "private_notes": False}]
    t, _ = make(tmp_path, [x])
    assert t.get_ticket(1)["fields"]["risk_areas"] == []


def test_custom_field_ignores_description_line(tmp_path):
    x = issue(1, risk="Build and CI", hotspot="A.cs")
    x["description"] = "Risk area: Payments · Hotspot: B.cs"
    t, _ = make(tmp_path, [x])
    f = t.get_ticket(1)["fields"]
    assert (f["risk_areas"], f["hotspot"], f["source"]) == (["Build and CI"], "A.cs", "custom fields")


def test_custom_field_plus_private_raise(tmp_path):
    x = issue(1, risk="Build and CI")
    x["journals"] = [{"notes": "[avflow] risk-area=Machine_control\nreason", "private_notes": True}]
    t, _ = make(tmp_path, [x])
    assert t.get_ticket(1)["fields"]["risk_areas"] == ["Build and CI", "Machine control"]


def test_hotspot_conflict_without_custom_fields(tmp_path):
    t, _ = make(tmp_path, [plain(1, hs="src/Settings.cs"),
                           plain(2, status="In progress", assigned=11, hs="src/Settings.cs"),
                           plain(3, status="In progress", assigned=11, hs="src/Other.cs")])
    r = t.start_ticket(1)
    assert [c["id"] for c in r["hotspot_conflicts"]] == [2] and r["warning"]


def test_hotspot_marker_still_written_without_custom_field(tmp_path):
    t, fake = make(tmp_path, [plain(1)])
    t.set_fields(1, hotspot="src/Settings.cs")
    assert fake.issues[1]["journals"][-1]["notes"].startswith("[avflow] hotspot=src/Settings.cs")
    assert t.get_ticket(1)["fields"]["hotspot"] == "src/Settings.cs"


# ---------- status mapping in setup
def test_status_plan_detects_redmine_defaults():
    t = TicketConfig()
    p = cli.status_plan(["New", "In Progress", "Resolved", "Feedback", "Closed", "Rejected"], t)
    assert set(p["missing"]) == {"Ready", "In review", "Ready for test"} and p["preset"]  # "In progress" matches "In Progress"
    cli.apply_status_preset(t, p["preset"])
    assert (t.status_ready, t.status_in_progress, t.status_in_review, t.status_ready_for_test, t.blocker_done) == \
           ("New", "In Progress", "Feedback", "Resolved", ["Resolved", "Closed"])


def test_status_plan_nothing_missing():
    p = cli.status_plan(["New", "Ready", "In progress", "In review", "Ready for test", "Closed"], TicketConfig())
    assert p["missing"] == []
