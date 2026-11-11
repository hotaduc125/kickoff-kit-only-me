import json

from avflow import cli, integrity
from avflow import setup_steps as st


def make_plugin(root):
    d = root / "plugins" / "x" / "avflow"
    (d / ".claude-plugin").mkdir(parents=True)
    (d / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "avflow", "version": "1.1.0"}))
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


def test_old_cached_version_is_ignored(tmp_path, monkeypatch, capsys):
    new = make_plugin(tmp_path)
    man = integrity.compute_manifest(new, "1.1.0")
    old = tmp_path / "plugins" / "cache" / "avflow" / "1.0.0"
    (old / ".claude-plugin").mkdir(parents=True)
    (old / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "avflow", "version": "1.0.0"}))
    monkeypatch.setattr(st, "CLAUDE_HOME", tmp_path)
    monkeypatch.setattr(integrity, "shipped_manifest", lambda: man)
    assert cli.check_integrity() == 0
    out = capsys.readouterr().out
    assert "Old cached version v1.0.0 ignored" in out and "unchanged" in out


def test_only_old_version_installed_fails(tmp_path, monkeypatch, capsys):
    d = make_plugin(tmp_path)
    man = integrity.compute_manifest(d, "1.2.0")
    monkeypatch.setattr(st, "CLAUDE_HOME", tmp_path)
    monkeypatch.setattr(integrity, "shipped_manifest", lambda: man)
    assert cli.check_integrity() == 1
    assert "v1.2.0 not installed" in capsys.readouterr().out


def test_claude_code_markers_are_ignored(tmp_path):
    d = make_plugin(tmp_path)
    man = integrity.compute_manifest(d, "1.1.0")
    (d / ".in_use").mkdir(); (d / ".in_use" / "82435").write_text("")
    (d / ".orphaned_at").write_text("2026-11-04")
    assert integrity.verify(d, man) == {"modified": [], "missing": [], "extra": []}


def test_plugin_newer_than_command_points_to_command_update(tmp_path, monkeypatch, capsys):
    d = make_plugin(tmp_path)                       # plugin v1.1.0 installed
    man = integrity.compute_manifest(d, "1.0.9")    # command ships v1.0.9
    monkeypatch.setattr(st, "CLAUDE_HOME", tmp_path)
    monkeypatch.setattr(integrity, "shipped_manifest", lambda: man)
    assert cli.check_integrity() == 1
    out = capsys.readouterr().out
    assert "plugin is v1.1.0 but this avflow command is v1.0.9" in out and "avflow update" in out


def test_orphaned_same_version_folder_is_not_current(tmp_path, monkeypatch, capsys):
    d = make_plugin(tmp_path)
    man = integrity.compute_manifest(d, "1.1.0")
    (d / ".orphaned_at").write_text("x")
    monkeypatch.setattr(st, "CLAUDE_HOME", tmp_path)
    monkeypatch.setattr(integrity, "shipped_manifest", lambda: man)
    assert cli.check_integrity() == 1   # only an orphaned copy → plugin v1.1.0 not really installed
