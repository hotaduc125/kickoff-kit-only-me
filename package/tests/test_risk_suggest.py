"""`avflow risk suggest`: profile gaps collected from reviewed tickets, proposed as paths (never written)."""
from avflow import cli, risk

PROFILE = """
[[risk.area]]
name   = "Machine control"
paths  = ["source/Motion/**"]
checks = ["independent-review"]
"""


def entry(tid, areas, gaps):
    return {"ticket": tid, "areas": areas, "gaps": gaps}


def test_gaps_grouped_by_area_and_folder():
    s = risk.suggest_paths([
        entry(12, {"Machine control": "ticket"}, ["source/Helpers/Timer.cs", "source/Helpers/Clock.cs"]),
        entry(15, {"Machine control": "ticket"}, ["source/Helpers/Timer.cs"]),
        entry(20, {"Other high risk": "ticket"}, ["setup.iss"]),
    ], risk.parse(PROFILE))
    assert s[0] == {"area": "Machine control", "path": "source/Helpers/**", "tickets": [12, 15],
                    "examples": ["source/Helpers/Clock.cs", "source/Helpers/Timer.cs"]}
    assert s[1]["area"] == "Other high risk" and s[1]["path"] == "setup.iss"


def test_paths_already_covered_are_dropped():
    s = risk.suggest_paths([entry(12, {"Machine control": "ticket"}, ["source/Motion/new.cs"])], risk.parse(PROFILE))
    assert s == []


def test_only_areas_from_the_ticket_are_blamed():
    s = risk.suggest_paths([entry(12, {"Machine control": "review"}, ["a/b.cs"])], risk.parse(PROFILE))
    assert s == [{"area": "(high-risk ticket)", "path": "a/**", "tickets": [12], "examples": ["a/b.cs"]}]


class FakeAdapter:
    def __init__(self, journals):
        self.journals = journals

    def list_issues(self, **params):
        assert params["project_id"] == "shop"
        return [{"id": i, "updated_on": "2099-01-01T00:00:00Z"} for i in self.journals]

    def issue_raw(self, i, include="journals"):
        return {"journals": self.journals[i]}


def test_cli_reads_private_review_notes_only(tmp_path, capsys, monkeypatch):
    (tmp_path / ".avflow").mkdir()
    (tmp_path / ".avflow/project.toml").write_text(PROFILE)
    review = risk.required_line("review", {"Machine control": "ticket"}, [], ["source/Helpers/Timer.cs"])
    adapter = FakeAdapter({12: [{"notes": review, "private_notes": True}],
                           13: [{"notes": review.replace("Timer", "Evil"), "private_notes": False}]})
    cfg = type("C", (), {"tickets": type("T", (), {"project": "shop"})()})()
    monkeypatch.setattr(cli, "_ticket_adapter", lambda: (cfg, adapter))
    assert cli.main(["risk", "suggest", "--path", str(tmp_path), "--days", "30"]) == 0
    out = capsys.readouterr().out
    assert "source/Helpers/**" in out and "#12" in out and "Evil" not in out and "merge request" in out
