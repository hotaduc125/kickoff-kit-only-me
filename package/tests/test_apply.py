"""Updating applies the team settings without questions.

`avflow update` from 3.0.1 runs the *old* update code, which installs the new release and then runs `avflow check`
with the new version. So `check` applies the settings that need no question (permissions, role subagents, hooks)
whenever this machine has not applied the installed version yet. Tokens are never touched.
"""
import json

import pytest

from avflow import __version__, cli
from avflow import setup_steps as st
from avflow.config import Config, TicketConfig


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A member's machine: ~/.avflow and ~/.claude in tmp_path, no prompts, no keyring, no external programs."""
    home, claude = tmp_path / "avflow", tmp_path / "claude"
    home.mkdir()
    settings = claude / "settings.json"
    monkeypatch.setattr(cli, "HOME", home)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("no question may be asked"))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: pytest.fail("no token may be asked"))
    monkeypatch.setattr(cli, "set_secret", lambda *a: pytest.fail("the token must not be touched"))
    monkeypatch.setattr(cli, "delete_secret", lambda *a: pytest.fail("the token must not be touched"))
    real = {n: getattr(st, n) for n in ("merge_permissions", "install_agents", "set_monitor", "set_git_guard",
                                        "set_session_guard")}
    monkeypatch.setattr(st, "merge_permissions", lambda: real["merge_permissions"](settings))
    monkeypatch.setattr(st, "install_agents", lambda models: real["install_agents"](models, claude / "agents"))
    monkeypatch.setattr(st, "set_monitor", lambda on: real["set_monitor"](on, settings, command="/x/avflow-monitor"))
    monkeypatch.setattr(st, "set_git_guard", lambda on: real["set_git_guard"](on, settings, command="/x/avflow-git-guard"))
    monkeypatch.setattr(st, "set_session_guard",
                        lambda on: real["set_session_guard"](on, settings, command="/x/avflow-session-guard"))
    return {"home": home, "claude": claude, "settings": settings}


def team_cfg():
    return Config(TicketConfig(url="https://r.test"))


def test_first_check_after_update_applies_the_team_settings(machine, capsys):
    (machine["home"] / "applied_version").write_text("0.0.1")
    (machine["claude"] / "agents").mkdir(parents=True)
    (machine["claude"] / "agents" / "avflow-planner.md").write_text("---\nmodel: opus\n---\nold")
    cfg = team_cfg()
    assert cli.apply_if_new(cfg) is True
    out = capsys.readouterr().out
    assert "open a new claude code session" in out.lower()
    status = {name: (good, detail) for name, good, detail in st.agents_status(cfg.models, machine["claude"] / "agents")}
    assert status == {"avflow-planner": (True, "sonnet"), "avflow-implementer": (True, "sonnet"),
                      "avflow-reviewer": (True, "opus")}
    d = json.loads(machine["settings"].read_text())
    assert set(st.DENY_RULES) <= set(d["permissions"]["deny"])
    assert st.git_guard_installed(machine["settings"]) and st.monitor_installed(machine["settings"])
    assert st.session_guard_installed(machine["settings"])
    assert st.applied_version(machine["home"]) == __version__


def test_second_check_does_not_apply_again(machine):
    cfg = team_cfg()
    assert cli.apply_if_new(cfg) is True
    machine["settings"].write_text("{}")
    assert cli.apply_if_new(cfg) is False
    assert json.loads(machine["settings"].read_text()) == {}


def test_personal_model_override_is_kept(machine):
    cfg = team_cfg()
    cfg.models.plan = "opus"
    cli.apply_if_new(cfg)
    assert "model: opus" in (machine["claude"] / "agents" / "avflow-planner.md").read_text()


def test_switches_turned_off_remove_the_hooks(machine):
    cfg = team_cfg()
    cli.apply_settings(cfg)
    cfg.workflow.git_guardrails = False
    cfg.guards.one_ticket_per_session, cfg.guards.max_read_kb = False, 0
    cli.apply_settings(cfg)
    assert not st.git_guard_installed(machine["settings"]) and not st.session_guard_installed(machine["settings"])


def test_a_failing_step_is_reported_and_the_rest_still_runs(machine, monkeypatch, capsys):
    def broken(on):
        raise SystemExit("Cannot find the avflow-monitor command.")
    monkeypatch.setattr(st, "set_monitor", broken)
    assert cli.apply_settings(team_cfg()) == 1
    assert "avflow-monitor" in capsys.readouterr().out
    assert st.session_guard_installed(machine["settings"])


def test_check_applies_first(machine, monkeypatch):
    order = []
    monkeypatch.setattr(Config, "load", staticmethod(lambda *a, **k: team_cfg()))
    monkeypatch.setattr(cli, "apply_if_new", lambda cfg: order.append("apply"))
    monkeypatch.setattr(cli, "make_adapter", lambda *a: order.append("whoami") or pytest.fail("stop here"))
    monkeypatch.setattr(cli, "get_secret", lambda *a: "t")
    with pytest.raises(BaseException):
        cli.cmd_doctor(None)
    assert order[:1] == ["apply"]


def test_setup_apply_asks_nothing(machine, monkeypatch, capsys):
    monkeypatch.setattr(Config, "load", staticmethod(lambda *a, **k: team_cfg()))
    monkeypatch.setattr(cli, "cmd_doctor", lambda a: 0)
    assert cli.main(["setup", "--apply"]) == 0
    assert st.applied_version(machine["home"]) == __version__
    assert "open a new claude code session" in capsys.readouterr().out.lower()


def test_merge_permissions_denies_credential_reads_once(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"permissions": {"deny": ["Bash(rm -rf:*)"]}}))
    st.merge_permissions(f)
    st.merge_permissions(f)
    deny = json.loads(f.read_text())["permissions"]["deny"]
    assert deny[0] == "Bash(rm -rf:*)" and deny.count("Bash(cmdkey:*)") == 1 and set(st.DENY_RULES) <= set(deny)
    st.remove_deny_rules(f)
    assert json.loads(f.read_text())["permissions"]["deny"] == ["Bash(rm -rf:*)"]


@pytest.mark.parametrize("script", ["reset-avflow.sh", "reset-avflow.ps1"])
def test_reset_scripts_remove_everything_setup_adds(script):
    from pathlib import Path
    text = (Path(__file__).parents[2] / "scripts" / script).read_text(encoding="utf-8")
    assert "avflow-session-guard" in text
    for rule in st.DENY_RULES:
        assert rule in text, f"{script} does not remove {rule}"
