"""CODEOWNERS generated from the risk profile (one source per fact), and the CI copy of risk.py."""
from avflow import cli, risk

PROFILE = """
[[risk.area]]
name   = "Machine control"
paths  = ["source/Zmotion/**", "**/NativeMethods*.cs"]
owners = ["@q", "@lead"]
checks = ["code-owner"]

[[risk.area]]
name   = "Payments"
paths  = []
owners = ["@pay"]
checks = ["code-owner"]

[[risk.area]]
name   = "Dependencies"
paths  = ["**/*.csproj"]
checks = ["independent-review"]
"""


def test_block_lists_areas_with_paths_and_owners():
    block = risk.codeowners_block(risk.parse(PROFILE))
    lines = block.splitlines()
    assert lines[0].startswith(risk.CODEOWNERS_BEGIN) and lines[-1] == risk.CODEOWNERS_END
    assert "/source/Zmotion/** @q @lead" in lines and "**/NativeMethods*.cs @q @lead" in lines
    assert not any("csproj" in l and not l.startswith("#") for l in lines)      # no owners → not listed
    assert any("Payments" in l and "no paths" in l for l in lines)


def test_sync_keeps_hand_written_lines_and_is_idempotent():
    p = risk.parse(PROFILE)
    original = "# team rules\n/docs/ @writer\n"
    once = risk.sync_codeowners(original, p)
    assert once.startswith(original) and risk.CODEOWNERS_BEGIN in once
    assert risk.sync_codeowners(once, p) == once and risk.codeowners_in_sync(once, p)
    changed = risk.parse(PROFILE.replace('"@q", "@lead"', '"@q"'))
    assert not risk.codeowners_in_sync(once, changed)
    again = risk.sync_codeowners(once, changed)
    assert "/docs/ @writer" in again and again.count(risk.CODEOWNERS_BEGIN) == 1 and "@lead" not in again


def write(tmp_path, text=PROFILE):
    (tmp_path / ".avflow").mkdir(exist_ok=True)
    (tmp_path / ".avflow" / "project.toml").write_text(text, encoding="utf-8")


def test_risk_sync_writes_codeowners_and_ci_copy(tmp_path, capsys):
    write(tmp_path)
    (tmp_path / ".gitlab").mkdir()
    (tmp_path / ".gitlab" / "CODEOWNERS").write_text("/docs/ @writer\n")     # GitLab also reads it here
    assert cli.main(["risk", "sync", "--path", str(tmp_path)]) == 0
    co = (tmp_path / ".gitlab" / "CODEOWNERS").read_text()
    assert "/docs/ @writer" in co and "/source/Zmotion/** @q @lead" in co and not (tmp_path / "CODEOWNERS").exists()
    assert risk.ci_copy_current((tmp_path / "ci" / "avflow_risk.py").read_text())
    assert cli.main(["risk", "check", "--path", str(tmp_path)]) == 0
    assert "out of date" not in capsys.readouterr().out


def test_risk_check_warns_when_generated_files_are_stale(tmp_path, capsys):
    write(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("/x @y\n")
    (tmp_path / "ci").mkdir()
    (tmp_path / "ci" / "avflow_risk.py").write_text("# avflow 0.1 — old copy\n")
    assert cli.main(["risk", "check", "--path", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "CODEOWNERS is out of date" in out and "ci/avflow_risk.py is out of date" in out and "avflow risk sync" in out


def test_ci_copy_is_risk_py_with_a_header():
    text = risk.ci_copy()
    assert text.splitlines()[0].startswith("# avflow ") and risk.ci_copy_current(text)
    assert not risk.ci_copy_current(text.replace("def grow", "def grow_"))
