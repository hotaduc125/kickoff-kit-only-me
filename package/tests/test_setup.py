import json
from pathlib import Path

import pytest

from avflow import cli
from avflow import setup_steps as st
from avflow.config import Config, TicketConfig


def test_config_roundtrip(tmp_path):
    c = Config(TicketConfig(url='https://r.test/"x"', blocker_done=["Done", "Closed"]), marketplace="https://g/m.git")
    p = tmp_path / "c.toml"
    c.save(p)
    d = Config.load(p)
    assert d.tickets.url == 'https://r.test/"x"' and d.tickets.blocker_done == ["Done", "Closed"] and d.marketplace == "https://g/m.git"
    assert not any(l.split("=")[0].strip() in ("token", "api_key", "password") for l in p.read_text().splitlines())


def test_merge_permissions_keeps_existing(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "theme": "dark"}))
    st.merge_permissions(f)
    st.merge_permissions(f)  # idempotent
    d = json.loads(f.read_text())
    assert d["theme"] == "dark" and "Bash(ls)" in d["permissions"]["allow"]
    assert d["permissions"]["allow"].count("mcp__avflow-tickets__get_ticket") == 1
    assert "mcp__avflow-tickets__start_ticket" in d["permissions"]["ask"]
    assert (tmp_path / "settings.json.avflow-backup").exists()


def test_find_and_install_pocock_skills_pinned(tmp_path):
    repo = tmp_path / "cache" / "mattpocock-skills"
    for group, name in (("productivity", "handoff"), ("engineering", "tdd")):
        (repo / "skills" / group / name).mkdir(parents=True)
        (repo / "skills" / group / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    calls = []
    done, miss = st.install_pocock_skills(tmp_path / "cache", runner=lambda c, interactive=False: (calls.append(c) or (0, "")),
                                          skills_dir=tmp_path / "skills", ref="abc123")
    assert done == ["handoff"] and miss == []
    assert (tmp_path / "skills" / "handoff" / "SKILL.md").exists() and not (tmp_path / "skills" / "tdd").exists()
    assert ["git", "-C", str(repo), "fetch", "-q", "--depth", "1", "origin", "abc123"] in calls


def test_pocock_fetch_failure_reports_missing(tmp_path):
    done, miss = st.install_pocock_skills(tmp_path / "cache", runner=lambda c, interactive=False: (1, "fatal"),
                                          skills_dir=tmp_path / "skills", ref="abc123")
    assert done == [] and miss == ["handoff"]


def test_register_mcp_command_order(monkeypatch):
    monkeypatch.setattr(st, "mcp_command_path", lambda: "/x/avflow-ticket-mcp")
    calls = []
    st.register_mcp(runner=lambda c, interactive=False: (calls.append(c) or (0, "")))
    assert calls[-1] == ["claude", "mcp", "add", "--scope", "user", "avflow-tickets", "--", "/x/avflow-ticket-mcp"]


def test_install_plugin_already_installed_is_ok():
    seq = iter([(0, ""), (1, "Plugin already installed")])
    ok, _ = st.install_plugin("m", "p@m", runner=lambda c, interactive=False: next(seq))
    assert ok


def test_choose_refuses_unavailable(monkeypatch, capsys):
    answers = iter(["2", "1"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    assert cli.choose("Ticket system", cli.TICKET_CHOICES) == "redmine"
    assert "not available" in capsys.readouterr().out


@pytest.mark.parametrize("raw", ["https://gitlab.enclave.vn/", "gitlab.enclave.vn", "http://gitlab.enclave.vn/group", " gitlab.enclave.vn "])
def test_normalize_host(raw):
    assert cli.normalize_host(raw) == "gitlab.enclave.vn"


def test_run_resolves_program_with_which(monkeypatch):
    seen = {}
    monkeypatch.setattr(st.shutil, "which", lambda name: r"C:\Users\x\AppData\Roaming\npm\claude.CMD" if name == "claude" else None)

    class P:
        returncode, stdout, stderr = 0, "ok", ""

    def fake_run(cmd, capture_output, text):
        seen["cmd"] = cmd
        return P()
    monkeypatch.setattr(st.subprocess, "run", fake_run)
    assert st.run(["claude", "mcp", "list"]) == (0, "ok")
    assert seen["cmd"][0].endswith("claude.CMD")


def test_utf8_output_does_not_fail():
    cli._utf8_output()


def test_setup_removes_old_token_when_url_changes(monkeypatch):
    from avflow.config import TicketConfig
    answers = iter(["https://redmine.enclave.vn/redmine", "y"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: "new-key")

    class A:
        def whoami(self):
            return {"name": "Alvin", "login": "alvin"}
    monkeypatch.setattr(cli, "make_adapter", lambda t, tok: A())
    stored, deleted = [], []
    monkeypatch.setattr(cli, "set_secret", lambda p, u, tok: stored.append(u))
    monkeypatch.setattr(cli, "delete_secret", lambda p, u: deleted.append(u))
    t = cli.setup_tickets_redmine(TicketConfig(url="https://redmine.enclave.com"))
    assert t.url == "https://redmine.enclave.vn/redmine"
    assert stored == ["https://redmine.enclave.vn/redmine"] and deleted == ["https://redmine.enclave.com"]


def test_setup_keeps_token_when_url_unchanged(monkeypatch):
    from avflow.config import TicketConfig
    answers = iter(["", "y"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_: "key")

    class A:
        def whoami(self):
            return {"name": "A", "login": "a"}
    monkeypatch.setattr(cli, "make_adapter", lambda t, tok: A())
    deleted = []
    monkeypatch.setattr(cli, "set_secret", lambda *a: None)
    monkeypatch.setattr(cli, "delete_secret", lambda p, u: deleted.append(u))
    cli.setup_tickets_redmine(TicketConfig(url="https://redmine.enclave.vn/redmine"))
    assert deleted == []


def test_config_show_has_no_token(tmp_path, monkeypatch, capsys):
    f = tmp_path / "config.toml"
    Config(TicketConfig(url="https://r.test")).save(f)
    monkeypatch.setattr(cli, "CONFIG_FILE", f)
    monkeypatch.setattr(cli, "get_secret", lambda p, u: "secret-token-value")

    class Args:
        edit = False
        path = False
    assert cli.cmd_config(Args()) == 0
    out = capsys.readouterr().out
    assert "https://r.test" in out and "secret-token-value" not in out and "Token stored in the OS keyring for https://r.test: yes" in out


def test_open_in_editor_uses_env_editor(monkeypatch, tmp_path):
    monkeypatch.setenv("EDITOR", "nano")
    calls = []
    assert cli.open_in_editor(tmp_path / "c.toml", runner=lambda c, interactive=False: (calls.append(c) or (0, ""))) == 0
    assert calls == [["nano", str(tmp_path / "c.toml")]]
