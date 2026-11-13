"""Stack presets: detection, the profile written by `avflow init`, preset drift."""
from datetime import date

import pytest

from avflow import risk


def touch(root, *names):
    for n in names:
        p = root / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")


@pytest.mark.parametrize("files,stacks", [
    (["App.sln"], ["dotnet"]),
    (["src/Api/Api.csproj"], ["dotnet"]),
    (["package.json"], ["node"]),
    (["pyproject.toml"], ["python"]),
    (["requirements-dev.txt"], ["python"]),
    (["pom.xml"], ["java"]),
    (["build.gradle.kts"], ["java"]),
    (["go.mod"], ["go"]),
    (["backend/App.sln", "frontend/package.json"], ["dotnet", "node"]),
    (["README.md"], []),
    (["node_modules/x/package.json"], []),               # vendored folders do not count
])
def test_detect(tmp_path, files, stacks):
    touch(tmp_path, *files)
    assert risk.detect_stacks(tmp_path) == stacks


def test_known_stacks():
    assert risk.preset_names() == ["dotnet", "go", "java", "node", "python"]


def test_rendered_profile_is_valid_and_has_the_agreed_defaults():
    text = risk.render_profile("Mateo_v2", ["dotnet"], today=date(2026, 11, 13))
    p = risk.parse(text)
    assert p.problems == [], p.problems
    names = [a.name for a in p.areas]
    assert names == ["Dependencies", "Data migrations", "Configuration", "Build and CI", "Infrastructure"]
    a = {x.name: x for x in p.areas}
    assert "**/*.csproj" in a["Dependencies"].paths and "**/Migrations/**" in a["Data migrations"].paths
    assert a["Dependencies"].checks == ["independent-review"]
    assert a["Data migrations"].checks == ["plan-confirmation", "independent-review",
                                           "checklist:Migration and rollback tested on a copy of the data"]
    assert a["Infrastructure"].checks == ["plan-confirmation", "independent-review"]
    assert {".avflow/**", "CODEOWNERS", "ci/avflow_*", ".gitlab-ci.yml"} <= set(a["Build and CI"].paths)
    assert p.default_checks == ["plan-confirmation", "independent-review"] and p.default_until == date(2026, 12, 25)
    assert p.other_checks == ["plan-confirmation", "independent-review"] and p.gate == "report"
    assert p.presets == ["dotnet"] and p.preset_version == risk.load_presets()["version"]
    assert "# name   = \"Native interop\"" in text            # suggested stack areas are commented out
    assert "code-owner" in text and "owners" in text         # explained, not active


def test_two_stacks_merge_paths_into_one_area():
    p = risk.parse(risk.render_profile("x", ["dotnet", "node"], today=date(2026, 1, 1)))
    deps = next(a for a in p.areas if a.name == "Dependencies")
    assert "**/*.csproj" in deps.paths and "package-lock.json" in deps.paths
    assert len(deps.paths) == len(set(deps.paths))


def test_no_stack_still_gives_shared_areas():
    p = risk.parse(risk.render_profile("x", [], today=date(2026, 1, 1)))
    assert [a.name for a in p.areas] == ["Build and CI", "Infrastructure"] and p.problems == []


def test_unknown_stack_refused():
    with pytest.raises(ValueError):
        risk.render_profile("x", ["cobol"])


def test_gate_validated():
    assert risk.parse('[ci]\ngate = "fail"').gate == "fail"
    assert risk.parse("").gate == "report"
    assert any("gate" in x for x in risk.parse('[ci]\ngate = "loud"').problems)


def test_preset_drift_reports_paths_added_to_a_newer_preset():
    text = risk.render_profile("x", ["node"], today=date(2026, 1, 1))
    p = risk.parse(text)
    assert risk.preset_drift(p) == {}
    newer = risk.load_presets()
    newer = {**newer, "version": newer["version"] + 1}
    newer["preset"] = {**newer["preset"], "node": {**newer["preset"]["node"],
                                                  "dependencies": newer["preset"]["node"]["dependencies"] + ["bun.lockb"]}}
    assert risk.preset_drift(p, newer) == {"Dependencies": ["bun.lockb"]}


def test_preset_drift_ignores_areas_the_project_removed():
    p = risk.parse('[project]\npresets = ["node"]\npreset_version = 0\n')
    assert risk.preset_drift(p) == {}
