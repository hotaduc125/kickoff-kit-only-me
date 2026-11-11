"""avflow on a Redmine without custom fields (no admin rights): fields from the description and private notes."""
import httpx
import pytest

from avflow import cli
from avflow.config import TicketConfig
from avflow.tickets.adapters.redmine import RedmineAdapter
from avflow.tickets.audit import Audit
from avflow.tickets.core import TicketTools, ToolError
from fake_redmine import FakeRedmine, issue

SIZE = "## Size and mode\nEstimate: 1–2 h · Proposed mode: (agent proposes) · Machine-side: {ms} · Hotspot: {hs}\n"


def plain(i, status="Ready", assigned=10, ms="no", hs="none", extra=""):
    t = issue(i, status=status, assigned=assigned)
    t["custom_fields"] = []                       # no custom fields in this Redmine
    t["description"] = "## Context\nSomething.\n\n" + SIZE.format(ms=ms, hs=hs) + extra
    return t


def make(tmp_path, issues):
    fake = FakeRedmine(issues)
    client = httpx.Client(base_url="https://redmine.test", transport=httpx.MockTransport(fake.handler))
    return TicketTools(RedmineAdapter(TicketConfig(url="https://redmine.test"), "k", client=client), Audit(tmp_path / "a.log")), fake


@pytest.mark.parametrize("text,expected", [
    ("Machine-side: yes · Hotspot: src/Settings.cs", {"machine_side": True, "hotspot": "src/Settings.cs"}),
    ("**Machine-side:** no · **Hotspot:** none", {"machine_side": False, "hotspot": None}),
    ("machine side: YES | hotspot: `ZCommand.cs`", {"machine_side": True, "hotspot": "ZCommand.cs"}),
    ("Hotspot: TODO before Ready", {"hotspot": None}),
    ("Proposed mode: plan · Machine-side: no", {"mode": "plan", "machine_side": False}),
    ("Proposed mode: (agent proposes)", {}),
])
def test_description_parsing(text, expected):
    got = RedmineAdapter._desc_fields(text)
    assert {k: got[k] for k in expected} == expected
    if not expected:
        assert "mode" not in got


def test_fields_from_description(tmp_path):
    t, _ = make(tmp_path, [plain(1, ms="yes", hs="src/Settings.cs")])
    f = t.get_ticket(1)["fields"]
    assert f["machine_side"] is True and f["hotspot"] == "src/Settings.cs" and f["mode"] is None
    assert f["source"] == "description and private notes"


def test_set_mode_writes_private_marker_and_start_works(tmp_path):
    t, fake = make(tmp_path, [plain(1)])
    with pytest.raises(ToolError):
        t.start_ticket(1)                          # no mode yet
    t.set_fields(1, mode="plan")
    note = fake.issues[1]["journals"][-1]
    assert note["private_notes"] is True and note["notes"].startswith("[avflow] mode=plan")
    assert not [c for c in fake.calls if c[0] == "PUT" and "custom_fields" in (c[3] or {}).get("issue", {})]
    r = t.start_ticket(1)
    assert r["mode"] == "plan" and fake.issues[1]["status"]["name"] == "In progress"


def test_latest_marker_wins(tmp_path):
    t, fake = make(tmp_path, [plain(1)])
    t.set_fields(1, mode="plan")
    t.set_fields(1, mode="full")
    assert t.get_ticket(1)["fields"]["mode"] == "full"


def test_public_note_with_marker_is_ignored(tmp_path):
    x = plain(1)
    x["journals"] = [{"notes": "[avflow] mode=direct", "private_notes": False}]
    t, _ = make(tmp_path, [x])
    assert t.get_ticket(1)["fields"]["mode"] is None


def test_machine_side_only_raised(tmp_path):
    t, _ = make(tmp_path, [plain(1, ms="no")])
    t.set_fields(1, machine_side=True)
    assert t.get_ticket(1)["fields"]["machine_side"] is True
    with pytest.raises(ToolError):
        t.set_fields(1, machine_side=False)


def test_description_yes_cannot_be_lowered_by_marker(tmp_path):
    x = plain(1, ms="yes")
    x["journals"] = [{"notes": "[avflow] machine-side=no", "private_notes": True}]
    t, _ = make(tmp_path, [x])
    assert t.get_ticket(1)["fields"]["machine_side"] is True


def test_hotspot_conflict_without_custom_fields(tmp_path):
    t, _ = make(tmp_path, [plain(1, hs="src/Settings.cs"),
                           plain(2, status="In progress", assigned=11, hs="src/Settings.cs"),
                           plain(3, status="In progress", assigned=11, hs="src/Other.cs")])
    t.set_fields(1, mode="plan")
    r = t.start_ticket(1)
    assert [c["id"] for c in r["hotspot_conflicts"]] == [2] and r["warning"]


def test_custom_fields_still_preferred(tmp_path):
    x = issue(1, mode="full", hotspot="A.cs", machine="1")
    x["description"] = SIZE.format(ms="no", hs="B.cs")
    t, _ = make(tmp_path, [x])
    f = t.get_ticket(1)["fields"]
    assert (f["mode"], f["machine_side"], f["hotspot"], f["source"]) == ("full", True, "A.cs", "custom fields")


# ---------- status mapping in setup
def test_status_plan_detects_redmine_defaults():
    t = TicketConfig()
    p = cli.status_plan(["New", "In Progress", "Resolved", "Feedback", "Closed", "Rejected"], t)
    assert set(p["missing"]) == {"Ready", "In review"} and p["preset"]  # "In progress" matches "In Progress"
    cli.apply_status_preset(t, p["preset"])
    assert (t.status_ready, t.status_in_progress, t.status_in_review, t.blocker_done) == ("New", "In Progress", "Feedback", ["Resolved", "Closed"])


def test_status_plan_nothing_missing():
    p = cli.status_plan(["New", "Ready", "In progress", "In review", "Ready for test", "Closed"], TicketConfig())
    assert p["missing"] == []
