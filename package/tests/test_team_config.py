from avflow import cli
from avflow.config import Config, merge, sources, team_defaults

TEAM = {"team_version": "9.9.9", "marketplace": "https://github.com/o/m.git",
        "tickets": {"url": "https://redmine.team/redmine", "status_ready": "New", "status_in_review": "Feedback"},
        "repo": {"host": "gitlab.team"},
        "workflow": {"profile": "superpowers", "git_guardrails": True},
        "models": {"plan": "opus", "implement": "sonnet", "review": "opus"},
        "monitor": {"warn_tokens": 300000, "critical_tokens": 400000}}


def test_shipped_team_file_loads():
    d = team_defaults()
    assert d["tickets"]["provider"] == "redmine" and "models" in d


def test_team_values_apply_without_personal_overrides(tmp_path):
    p = tmp_path / "config.toml"
    Config.team(TEAM).save(p, team=TEAM)
    body = [l for l in p.read_text().splitlines() if l and not l.startswith("#")]
    assert body == []                                    # nothing personal written
    c = Config.load(p, team=TEAM)
    assert (c.tickets.url, c.tickets.status_ready, c.repo.host, c.marketplace) == \
           ("https://redmine.team/redmine", "New", "gitlab.team", "https://github.com/o/m.git")


def test_personal_override_wins_and_only_it_is_saved(tmp_path):
    p = tmp_path / "config.toml"
    c = Config.team(TEAM)
    c.models.review = "sonnet"
    c.save(p, team=TEAM)
    assert "[models]" in p.read_text() and 'review = "sonnet"' in p.read_text() and "[tickets]" not in p.read_text()
    loaded = Config.load(p, team=TEAM)
    assert loaded.models.review == "sonnet" and loaded.models.plan == "opus" and loaded.tickets.url == TEAM["tickets"]["url"]
    s = sources(p, team=TEAM)
    assert s["models.review"] == "personal" and s["models.plan"] == "team"


def test_team_change_reaches_members_without_overrides(tmp_path):
    p = tmp_path / "config.toml"
    Config.team(TEAM).save(p, team=TEAM)
    newer = merge(TEAM, {"monitor": {"warn_tokens": 250000}})
    assert Config.load(p, team=newer).monitor.warn_tokens == 250000


def test_merge_is_per_key():
    assert merge({"a": {"x": 1, "y": 2}, "b": 1}, {"a": {"y": 3}}) == {"a": {"x": 1, "y": 3}, "b": 1}


def test_default_setup_asks_only_for_the_token(monkeypatch, capsys):
    from avflow.config import TicketConfig
    asked = []
    monkeypatch.setattr("builtins.input", lambda prompt="": asked.append(prompt) or "")
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: "key")

    class A:
        def whoami(self):
            return {"name": "Alvin", "login": "alvin"}

        def statuses(self):
            return [{"name": n} for n in ("New", "In progress", "Feedback", "Resolved", "Closed")]
    monkeypatch.setattr(cli, "make_adapter", lambda t, tok: A())
    stored = []
    monkeypatch.setattr(cli, "set_secret", lambda p, u, tok: stored.append(u))
    monkeypatch.setattr(cli, "delete_secret", lambda p, u: None)
    t = cli.setup_redmine_token(TicketConfig(url="https://redmine.team/redmine", status_ready="New", status_in_review="Feedback"))
    assert asked == [] and stored == ["https://redmine.team/redmine"] and t.url == "https://redmine.team/redmine"


def test_default_setup_warns_when_team_statuses_missing(monkeypatch, capsys):
    from avflow.config import TicketConfig
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: "key")

    class A:
        def whoami(self):
            return {"name": "A", "login": "a"}

        def statuses(self):
            return [{"name": "New"}, {"name": "Closed"}]
    monkeypatch.setattr(cli, "make_adapter", lambda t, tok: A())
    monkeypatch.setattr(cli, "set_secret", lambda *a: None)
    cli.setup_redmine_token(TicketConfig(url="https://r"))
    assert "Tell the PM" in capsys.readouterr().out


def test_team_summary_lists_the_settings(capsys):
    cli.print_team_summary(Config.team(TEAM))
    out = capsys.readouterr().out
    assert "redmine.team" in out and "gitlab.team" in out and "New" in out and "plan opus" in out


def test_config_reset_drops_overrides(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    c = Config.team()
    c.models.review = "haiku"
    c.save(p)
    monkeypatch.setattr(cli, "CONFIG_FILE", p)

    class Args:
        edit = path = False
        reset = True
    assert cli.cmd_config(Args()) == 0
    assert Config.load(p).models.review == Config.team().models.review


ENCLAVE = {"tickets": {"status_ready": "New", "status_in_progress": "In Progress",
                       "status_in_review": "In Code Review", "status_ready_for_test": "Ready for testing"}}


def test_init_writes_team_status_names_into_ci(tmp_path):
    import yaml
    from avflow.init_repo import init_repo
    init_repo(tmp_path, cfg=Config.team(ENCLAVE))
    job = yaml.safe_load((tmp_path / ".gitlab-ci.avflow.yml").read_text())["avflow-ready-for-test"]
    assert job["variables"] == {"AVFLOW_STATUS_IN_REVIEW": "In Code Review", "AVFLOW_STATUS_READY_FOR_TEST": "Ready for testing"}
    assert "{status_" not in (tmp_path / ".gitlab-ci.avflow.yml").read_text()
    gate = yaml.safe_load((tmp_path / ".gitlab-ci.avflow.yml").read_text())["avflow-risk-check"]
    assert set(gate["variables"]) == {"GIT_DEPTH", "AVFLOW_FIELD_RISK_AREA"}
    assert gate["variables"]["AVFLOW_FIELD_RISK_AREA"] == "Risk area" and gate["variables"]["GIT_DEPTH"] == "0"
    assert gate["rules"] == [{"if": '$CI_PIPELINE_SOURCE == "merge_request_event"', "when": "always"}]
    text = (tmp_path / ".gitlab-ci.avflow.yml").read_text()
    assert "{field_" not in text and "MACHINE" not in text


def test_status_plan_with_enclave_names():
    t = Config.team(ENCLAVE).tickets
    p = cli.status_plan(["New", "In Progress", "In Code Review", "Ready for testing", "Closed"], t)
    assert p["missing"] == []


def test_report_buckets_use_team_names():
    from avflow import report
    t = Config.team(ENCLAVE).tickets
    assert report.bucket("Ready for testing", t) == "Ready for test"
    assert report.bucket("In Code Review", t) == "In review"
    assert report.bucket("In Progress", t) == "In progress"


def test_shipped_enclave_team_file_has_the_mapping():
    import tomllib
    from pathlib import Path
    team = tomllib.loads((Path(__file__).parents[2] / "team" / "avflow-team.toml").read_text())
    tk = team["tickets"]
    assert (tk["status_ready"], tk["status_in_progress"], tk["status_in_review"], tk["status_ready_for_test"]) == \
           ("New", "In Progress", "In Code Review", "Ready for testing")
    assert "Ready for testing" in tk["blocker_done"]


def test_team_files_have_no_project_specific_fields():
    import tomllib
    from pathlib import Path
    for f in (Path(__file__).parents[2] / "team" / "avflow-team.toml", Path(__file__).parents[1] / "src" / "avflow" / "data" / "team.toml"):
        tk = tomllib.loads(f.read_text())["tickets"]
        assert tk["field_risk_area"] == "Risk area"
        assert not [k for k in tk if "machine" in k], f


def test_a_2_6_personal_file_still_loads(tmp_path):
    """Members update from 2.6.x: their personal file may still name the Mode or Machine-side field (no longer read)."""
    f = tmp_path / "config.toml"
    f.write_text('[tickets]\nfield_mode = "Chế độ"\nfield_machine_side = "Machine side"\nsomething_new = 1\n', encoding="utf-8")
    c = Config.load(f, team={"tickets": {"url": "https://r.test"}})
    assert c.tickets.field_risk_area == "Risk area" and not hasattr(c.tickets, "field_machine_side")
