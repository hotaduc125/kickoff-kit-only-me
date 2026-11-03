import json
from pathlib import Path

import pytest

from kickoff_kit import cli
from kickoff_kit import setup_steps as st
from kickoff_kit.config import Config, TicketConfig


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
    assert d["permissions"]["allow"].count("mcp__kickoff-tickets__get_ticket") == 1
    assert "mcp__kickoff-tickets__start_ticket" in d["permissions"]["ask"]
    assert (tmp_path / "settings.json.kickoff-backup").exists()


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
    monkeypatch.setattr(st, "mcp_command_path", lambda: "/x/kickoff-ticket-mcp")
    calls = []
    st.register_mcp(runner=lambda c, interactive=False: (calls.append(c) or (0, "")))
    assert calls[-1] == ["claude", "mcp", "add", "--scope", "user", "kickoff-tickets", "--", "/x/kickoff-ticket-mcp"]


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
