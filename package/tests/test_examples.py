"""The example profiles shipped in examples/ stay valid for the current risk.py."""
from pathlib import Path

from avflow import risk

ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_example_profile_is_valid():
    p = risk.parse((ROOT / "examples/avflow-sandbox/avflow-profile.example.toml").read_text(encoding="utf-8"))
    assert p.problems == []
    assert [a.name for a in p.areas][-2:] == ["Machine control", "Payments"] and len(p.areas) == 7
    assert p.default_checks == []          # [risk.default] commented out (B8)
    r = risk.requirements(p, [], ["src/sandbox/machine.py"])
    assert "Machine control" in r.areas and "code-owner" in r.checks and "plan-confirmation" in r.checks
    assert risk.requirements(p, [], ["src/sandbox/report.py"]).checks == []


def test_mateo_area_snippet_is_valid():
    snippet = (ROOT / "examples/mateo-project-skills/project.toml.area").read_text(encoding="utf-8")
    p = risk.parse('[project]\nname = "Mateo_v2"\n' + snippet)
    assert p.problems == []
    r = risk.requirements(p, [], ["source/Zmotion/ZCommand.cs"])
    assert list(r.areas) == ["Machine control"] and "checklist:Tested on the test bench by someone other than the author" in r.checks
