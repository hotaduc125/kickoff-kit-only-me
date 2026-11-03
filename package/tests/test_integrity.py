import json

from kickoff_kit import cli, integrity
from kickoff_kit import setup_steps as st


def make_plugin(root):
    d = root / "plugins" / "x" / "kickoff-kit"
    (d / ".claude-plugin").mkdir(parents=True)
    (d / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "kickoff-kit", "version": "1.1.0"}))
    (d / "skills" / "tickets").mkdir(parents=True)
    (d / "skills" / "tickets" / "SKILL.md").write_text("line1\nline2\n")
    return d


def test_verify_detects_changes(tmp_path):
    d = make_plugin(tmp_path)
    man = integrity.compute_manifest(d, "1.1.0")
    assert integrity.verify(d, man) == {"modified": [], "missing": [], "extra": []}
    (d / "skills" / "tickets" / "SKILL.md").write_text("edited\n")
    (d / "skills" / "extra.md").write_text("x")
    r = integrity.verify(d, man)
    assert r["modified"] == ["skills/tickets/SKILL.md"] and r["extra"] == ["skills/extra.md"]


def test_crlf_is_not_a_change(tmp_path):
    d = make_plugin(tmp_path)
    man = integrity.compute_manifest(d, "1.1.0")
    p = d / "skills" / "tickets" / "SKILL.md"
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert integrity.verify(d, man)["modified"] == []


def test_find_installed(tmp_path):
    d = make_plugin(tmp_path)
    assert integrity.find_installed(tmp_path) == [d]


def test_doctor_integrity_reports_edit(tmp_path, monkeypatch, capsys):
    d = make_plugin(tmp_path)
    man = integrity.compute_manifest(d, "1.1.0")
    monkeypatch.setattr(st, "CLAUDE_HOME", tmp_path)
    monkeypatch.setattr(integrity, "shipped_manifest", lambda: man)
    assert cli.check_integrity() == 0
    (d / "skills" / "tickets" / "SKILL.md").write_text("tampered\n")
    assert cli.check_integrity() == 1
    assert "modified: skills/tickets/SKILL.md" in capsys.readouterr().out


def test_dev_build_skips(monkeypatch, capsys):
    monkeypatch.setattr(integrity, "shipped_manifest", lambda: {"version": "dev", "files": {}})
    assert cli.check_integrity() == 0 and "skipped" in capsys.readouterr().out


def test_can_read_repo_no_prompt(monkeypatch):
    seen = {}
    def runner(cmd, interactive=False):
        import os
        seen["prompt"] = os.environ.get("GIT_TERMINAL_PROMPT")
        return 128, "fatal"
    assert st.can_read_repo("https://example/x.git", runner=runner) is False
    assert seen["prompt"] == "0"
