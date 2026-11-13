"""`avflow risk check` and `avflow risk files`."""
from avflow import cli

PROFILE = """
[[risk.area]]
name   = "Machine control"
paths  = ["source/Motion/**"]
owners = ["@q"]
checks = ["plan-confirmation", "code-owner"]

[[risk.area]]
name   = "Payments"
checks = ["independent-review"]

[risk.default]
checks = ["plan-confirmation"]
until  = "2020-01-01"
"""


def write(tmp_path, text=PROFILE):
    (tmp_path / ".avflow").mkdir(exist_ok=True)
    (tmp_path / ".avflow" / "project.toml").write_text(text, encoding="utf-8")


def test_check_ok(tmp_path, capsys):
    write(tmp_path)
    assert cli.main(["risk", "check", "--path", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 risk areas" in out and "Machine control" in out
    assert "no paths yet" in out                       # Payments: recognised only from tickets
    assert "ended on 2020-01-01" in out                # the strict default no longer applies


def test_check_problems_fail(tmp_path, capsys):
    write(tmp_path, '[[risk.area]]\nname = "A"\nchecks = ["code-owner"]')
    assert cli.main(["risk", "check", "--path", str(tmp_path)]) == 1
    assert "owners" in capsys.readouterr().out


def test_check_missing_profile(tmp_path, capsys):
    assert cli.main(["risk", "check", "--path", str(tmp_path)]) == 1
    assert "avflow init" in capsys.readouterr().out


def test_files_shows_areas_and_checks(tmp_path, capsys):
    write(tmp_path)
    assert cli.main(["risk", "files", "source/Motion/A.cs", "src/ui.cs", "--path", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Machine control (files)" in out and "source/Motion/A.cs" in out and "Code owner approval" in out


def test_files_with_ticket_area(tmp_path, capsys):
    write(tmp_path)
    assert cli.main(["risk", "files", "src/billing/x.cs", "--area", "Payments", "--path", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Payments (ticket)" in out and "Independent review" in out and "Profile gaps" in out


def test_files_nothing_risky(tmp_path, capsys):
    write(tmp_path)
    assert cli.main(["risk", "files", "src/ui.cs", "--path", str(tmp_path)]) == 0
    assert "standard flow" in capsys.readouterr().out
