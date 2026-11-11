import json

import pytest

from avflow import setup_steps as st
from avflow.config import Config, WorkflowConfig
from avflow.git_guard import evaluate

ON_FEATURE = lambda _cwd: "feature/1234-reset"   # noqa: E731
ON_DEVELOP = lambda _cwd: "develop"              # noqa: E731


@pytest.mark.parametrize("cmd", [
    "git push origin main",
    "git push origin develop",
    "git push origin HEAD:develop",
    "git push origin feature/x:main",
    "git push origin release/1.2",
    "git push --force origin feature/x",
    "git push -f",
    "git push --force-with-lease origin feature/x",
    "git push origin +feature/x",
    "git push origin :feature/x",
    "git push --delete origin feature/x",
    "git push --tags",
    "git push origin refs/tags/v1.0",
    "git reset --hard HEAD~1",
    "git clean -fd",
    "git clean -xfd",
    "git branch -D feature/x",
    "git checkout .",
    "git checkout -- src/a.cs",
    "git restore .",
    "git stash drop",
    "git stash clear",
    "cd repo && git push origin main",
    "git status; git reset --hard",
    "git -C ../repo push origin main",
    "GIT_TRACE=1 git push origin develop",
])
def test_blocked(cmd):
    assert evaluate(cmd, current=ON_FEATURE), cmd


@pytest.mark.parametrize("cmd", [
    "git push origin feature/1234-reset",
    "git push -u origin feature/1234-reset",
    "git push",                                  # current branch is a feature branch
    "git push origin HEAD",
    "git status",
    "git commit -m 'Refs #1234'",
    "git checkout -b feature/new",
    "git checkout develop",
    "git restore --staged src/a.cs",
    "git reset HEAD~1",
    "git branch -d merged-branch",
    "git stash",
    "git stash pop",
    "git log --oneline | head",
    "echo git push origin main",                 # not a git command
    "dotnet test",
])
def test_allowed(cmd):
    assert evaluate(cmd, current=ON_FEATURE) is None, cmd


def test_plain_push_on_protected_branch_is_blocked():
    assert evaluate("git push", current=ON_DEVELOP)
    assert evaluate("git push origin HEAD", current=ON_DEVELOP)


def test_unknown_branch_is_blocked_for_plain_push():
    assert evaluate("git push", current=lambda _c: None)


def test_custom_protected_branches():
    assert evaluate("git push origin production", ["production"], current=ON_FEATURE)
    assert evaluate("git push origin main", ["production"], current=ON_FEATURE) is None


def test_hook_add_keeps_other_hooks_and_is_idempotent(tmp_path):
    f = tmp_path / "settings.json"
    other = {"matcher": "Write", "hooks": [{"type": "command", "command": "my-formatter"}]}
    f.write_text(json.dumps({"theme": "dark", "hooks": {"PreToolUse": [other]}}))
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    d = json.loads(f.read_text())
    pre = d["hooks"]["PreToolUse"]
    assert d["theme"] == "dark" and other in pre
    assert sum("avflow-git-guard" in h["command"] for e in pre for h in e["hooks"]) == 1
    assert st.git_guard_installed(f)


def test_hook_remove_leaves_other_hooks(tmp_path):
    f = tmp_path / "settings.json"
    other = {"matcher": "Write", "hooks": [{"type": "command", "command": "my-formatter"}]}
    f.write_text(json.dumps({"hooks": {"PreToolUse": [other]}}))
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    st.set_git_guard(False, f)
    d = json.loads(f.read_text())
    assert d["hooks"]["PreToolUse"] == [other] and not st.git_guard_installed(f)


def test_hook_remove_cleans_empty_sections(tmp_path):
    f = tmp_path / "settings.json"
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    st.set_git_guard(False, f)
    assert "hooks" not in json.loads(f.read_text())


def test_profiles():
    assert st.skills_for("superpowers") == ("handoff",)
    p = st.skills_for("pocock")
    assert "handoff" in p and "tdd" in p and len(p) == 12
    for excluded in ("to-spec", "to-tickets", "triage", "wayfinder", "setup-matt-pocock-skills", "ask-matt"):
        assert excluded not in p


def test_pocock_profile_install_and_record(tmp_path):
    repo = tmp_path / "home" / "cache" / "mattpocock-skills"
    for name in st.POCOCK_PROFILE_SKILLS + ("to-tickets", "triage"):
        (repo / "skills" / "x" / name).mkdir(parents=True)
        (repo / "skills" / "x" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    done, miss = st.install_pocock_skills(tmp_path / "home" / "cache", runner=lambda c, interactive=False: (0, ""),
                                          skills_dir=tmp_path / "skills", names=st.skills_for("pocock"))
    assert sorted(done) == sorted(st.POCOCK_PROFILE_SKILLS) and miss == []
    assert not (tmp_path / "skills" / "to-tickets").exists()
    assert sorted(st.recorded_skills(tmp_path / "home")) == sorted(st.POCOCK_PROFILE_SKILLS)
    removed = st.remove_skills([n for n in st.recorded_skills(tmp_path / "home") if n != "handoff"], tmp_path / "skills")
    assert len(removed) == 11 and (tmp_path / "skills" / "handoff").exists()


def test_workflow_config_roundtrip(tmp_path):
    c = Config(workflow=WorkflowConfig(profile="pocock", git_guardrails=False, protected_branches=["main", "prod/*"]))
    p = tmp_path / "c.toml"
    c.save(p)
    w = Config.load(p).workflow
    assert (w.profile, w.git_guardrails, w.protected_branches) == ("pocock", False, ["main", "prod/*"])
