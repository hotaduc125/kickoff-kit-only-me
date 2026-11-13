"""The project's risk profile (.avflow/project.toml): validation, path matching, required checks."""
from datetime import date

import pytest

from avflow import risk

SAMPLE = """
[project]
name = "Shop_v2"

[[risk.area]]
name   = "Machine control"
paths  = ["source/Motion/**", "source/Modes/**"]
owners = ["@q"]
checks = ["plan-confirmation", "independent-review", "code-owner",
          "checklist:Tested on the test bench by someone other than the author"]

[[risk.area]]
name   = "Build and CI"
paths  = [".gitlab-ci.yml", "build/**"]
owners = ["@alvin"]
checks = ["code-owner"]

[[risk.area]]
name   = "Payments"
paths  = []
checks = ["independent-review"]

[risk.other]
checks = ["plan-confirmation", "independent-review"]
"""


def prof(text=SAMPLE):
    return risk.parse(text)


# ---------- glob matching
@pytest.mark.parametrize("pattern,path,hit", [
    ("source/Motion/**", "source/Motion/MotionCommand.cs", True),
    ("source/Motion/**", "source/Motion/sub/deep/A.cs", True),
    ("source/Motion/**", "source/MotionX/A.cs", False),
    ("source/Motion/**", "other/source/Motion/A.cs", False),
    (".gitlab-ci.yml", ".gitlab-ci.yml", True),
    (".gitlab-ci.yml", "sub/.gitlab-ci.yml", False),
    ("**/*.csproj", "App.csproj", True),
    ("**/*.csproj", "src/a/App.csproj", True),
    ("**/Migrations/**", "Migrations/001.cs", True),
    ("**/Migrations/**", "src/Data/Migrations/001.cs", True),
    ("src/middleware/session*", "src/middleware/session_store.ts", True),
    ("src/middleware/session*", "src/middleware/sub/session.ts", False),
    ("build/", "build/out/x.dll", True),
    ("**/appsettings*.json", "api/appsettings.Development.json", True),
    ("Dockerfile*", "Dockerfile.prod", True),
    ("a?c.txt", "abc.txt", True),
])
def test_glob(pattern, path, hit):
    assert risk.glob_match(pattern, path) is hit


def test_windows_and_dot_paths_normalised():
    assert risk.glob_match("source/Motion/**", "source\\Motion\\A.cs")
    assert risk.glob_match("source/Motion/**", "./source/Motion/A.cs")


# ---------- validation
def test_valid_profile_has_no_problems():
    p = prof()
    assert p.problems == [] and [a.name for a in p.areas] == ["Machine control", "Build and CI", "Payments"]


@pytest.mark.parametrize("bad,needle", [
    ('[[risk.area]]\nname = "A"\npaths = ["x/**"]\nchecks = ["telepathy"]', "unknown check"),
    ('[[risk.area]]\nname = "A"\npaths = ["x/**"]\nchecks = ["code-owner"]', "owners"),
    ('[[risk.area]]\nname = "A"\nchecks = ["independent-review"]\n[[risk.area]]\nname = "a"\nchecks = ["independent-review"]', "twice"),
    ('[[risk.area]]\nname = "Other high risk"\nchecks = ["independent-review"]', "reserved"),
    ('[[risk.area]]\nname = "None"\nchecks = ["independent-review"]', "reserved"),
    ('[[risk.area]]\nname = ""\nchecks = ["independent-review"]', "name"),
    ('[[risk.area]]\nname = "A"\nchecks = []', "at least one check"),
    ('[[risk.area]]\nname = "A"\nchecks = ["checklist:"]', "checklist"),
    ('[[risk.area]]\nname = "A"\npaths = ["/abs/**"]\nchecks = ["independent-review"]', "relative"),
    ('[[risk.area]]\nname = "A"\npaths = ["../up/**"]\nchecks = ["independent-review"]', "relative"),
    ('[[risk.area]]\nname = "A"\npaths = "x/**"\nchecks = ["independent-review"]', "list"),
    ('[risk.default]\nchecks = ["plan-confirmation"]\nuntil = "someday"', "until"),
    ('[risk.other]\nchecks = ["nope"]', "unknown check"),
    ('this is = = not toml', "TOML"),
])
def test_problems(bad, needle):
    p = risk.parse(bad)
    assert any(needle in x for x in p.problems), p.problems


def test_unknown_keys_are_warnings_not_problems():
    p = risk.parse('[[risk.area]]\nname = "A"\nchecks = ["independent-review"]\ncolour = "red"')
    assert p.problems == [] and any("colour" in w for w in p.warnings)


def test_until_accepts_toml_date_and_string():
    assert risk.parse('[risk.default]\nchecks = ["plan-confirmation"]\nuntil = 2026-12-31').default_until == date(2026, 12, 31)
    assert risk.parse('[risk.default]\nchecks = ["plan-confirmation"]\nuntil = "2026-12-31"').default_until == date(2026, 12, 31)


def test_load_missing_file_returns_none(tmp_path):
    assert risk.load(tmp_path) is None


def test_load_reads_profile(tmp_path):
    (tmp_path / ".avflow").mkdir()
    (tmp_path / ".avflow" / "project.toml").write_text(SAMPLE, encoding="utf-8")
    assert risk.load(tmp_path).name == "Shop_v2"


# ---------- requirements
def test_no_area_no_files_is_standard_flow():
    r = risk.requirements(prof(), [], ["source/Views/OrderWindow.xaml"])
    assert r.checks == [] and r.areas == {} and not r.high_risk


def test_ticket_area_brings_its_checks():
    r = risk.requirements(prof(), ["Machine control"], [])
    assert r.checks == ["plan-confirmation", "independent-review", "code-owner",
                        "checklist:Tested on the test bench by someone other than the author"]
    assert r.areas == {"Machine control": "ticket"} and r.high_risk


def test_area_name_matching_is_loose():
    assert risk.requirements(prof(), ["machine_CONTROL"], []).areas == {"Machine control": "ticket"}


def test_files_match_areas_and_union_is_ordered():
    r = risk.requirements(prof(), [], ["build/x.ps1", "source/Motion/A.cs"])
    assert r.areas == {"Machine control": "files", "Build and CI": "files"}
    assert r.checks[:3] == ["plan-confirmation", "independent-review", "code-owner"] and len(r.checks) == 4
    assert r.files == {"Machine control": ["source/Motion/A.cs"], "Build and CI": ["build/x.ps1"]}


def test_area_without_paths_only_from_ticket():
    assert risk.requirements(prof(), [], ["src/billing/x.cs"]).checks == []
    assert risk.requirements(prof(), ["Payments"], []).checks == ["independent-review"]


def test_other_high_risk_uses_risk_other():
    r = risk.requirements(risk.parse('[risk.other]\nchecks = ["independent-review"]'), [risk.OTHER], [])
    assert r.checks == ["independent-review"] and r.areas == {risk.OTHER: "ticket"}


def test_other_high_risk_without_profile_section_uses_builtin():
    assert risk.requirements(risk.parse(""), [risk.OTHER], []).checks == ["plan-confirmation", "independent-review"]


def test_no_profile_at_all():
    r = risk.requirements(None, [risk.OTHER], ["a.py"])
    assert r.checks == ["plan-confirmation", "independent-review"] and r.warnings


def test_unknown_ticket_area_counts_as_other_with_warning():
    r = risk.requirements(prof(), ["Telepathy"], [])
    assert r.areas == {risk.OTHER: "ticket"} and "Telepathy" in r.warnings[0]


def test_none_is_ignored():
    assert risk.requirements(prof(), ["None", ""], []).checks == []


def test_default_applies_only_when_nothing_matches_and_before_until():
    p = risk.parse(SAMPLE + '\n[risk.default]\nchecks = ["plan-confirmation"]\nuntil = "2026-12-31"')
    assert risk.requirements(p, [], ["src/a.cs"], today=date(2026, 12, 31)).checks == ["plan-confirmation"]
    assert risk.requirements(p, [], ["src/a.cs"], today=date(2027, 1, 1)).checks == []
    hit = risk.requirements(p, [], ["build/a"], today=date(2026, 12, 1))
    assert hit.checks == ["code-owner"] and "default" not in hit.areas.values()


def test_default_without_until_is_permanent():
    p = risk.parse('[risk.default]\nchecks = ["independent-review"]')
    assert risk.requirements(p, [], ["x"], today=date(2099, 1, 1)).checks == ["independent-review"]


def test_profile_gaps_are_files_of_a_high_risk_ticket_outside_every_area():
    r = risk.requirements(prof(), ["Machine control"], ["source/Motion/A.cs", "source/Helpers/Timer.cs"])
    assert r.gaps == ["source/Helpers/Timer.cs"]
    assert risk.requirements(prof(), [], ["source/Motion/A.cs", "x.cs"]).gaps == []   # ticket not flagged


def test_grow_only_adds_and_keeps_order():
    assert risk.grow(["code-owner"], ["plan-confirmation", "code-owner", "checklist:X"]) == \
           ["plan-confirmation", "code-owner", "checklist:X"]
    assert risk.grow(["checklist:B", "independent-review"], []) == ["independent-review", "checklist:B"]


def test_describe_check():
    assert "Tested" in risk.describe("checklist:Tested on the bench")
    assert risk.describe("plan-confirmation").startswith("Plan confirmation")
