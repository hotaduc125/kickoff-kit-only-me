"""GitRepo: changed files from real git (temporary repository), MR target and notes through a fake glab."""
import json
import shutil
import subprocess

import pytest

from avflow import setup_steps as st
from avflow.tickets.repo import GitRepo, RepoError

needs_git = pytest.mark.skipif(not shutil.which("git"), reason="git not installed")


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "develop")
    git(tmp_path, "config", "user.email", "t@example.invalid")
    git(tmp_path, "config", "user.name", "T")
    (tmp_path / "README.md").write_text("x")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "switch", "-qc", "feature")
    (tmp_path / "source" / "Zmotion").mkdir(parents=True)
    (tmp_path / "source" / "Zmotion" / "Zé.cs").write_text("y")
    (tmp_path / "README.md").write_text("z")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "work")
    (tmp_path / "uncommitted.txt").write_text("not in the MR")
    return tmp_path


@needs_git
def test_changed_files_since_the_target_branch(repo):
    files, base = GitRepo(str(repo)).changed_files("develop")
    assert sorted(files) == ["README.md", "source/Zmotion/Zé.cs"] and base == "develop"


@needs_git
def test_base_must_be_a_branch_not_any_revision(repo):
    with pytest.raises(RepoError) as e:
        GitRepo(str(repo)).changed_files("HEAD~1")
    assert "branch" in str(e.value)


@needs_git
def test_profile_loaded_from_repo_root(repo):
    (repo / ".avflow").mkdir()
    (repo / ".avflow" / "project.toml").write_text('[[risk.area]]\nname = "A"\npaths = ["x/**"]\nchecks = ["independent-review"]\n')
    (repo / "source" / "Zmotion").mkdir(exist_ok=True)
    assert GitRepo(str(repo / "source" / "Zmotion")).profile().areas[0].name == "A"


def test_not_a_repository(tmp_path):
    r = GitRepo(str(tmp_path), runner=lambda c, interactive=False: (128, "fatal: not a git repository"))
    assert r.profile() is None
    with pytest.raises(RepoError):
        r.changed_files("develop")


def test_mr_target_and_note_use_glab_with_the_mr_host_and_project():
    calls = []

    def runner(cmd, interactive=False):
        calls.append(cmd)
        return 0, json.dumps({"target_branch": "develop"})
    r = GitRepo("/x", runner=runner)
    url = "https://gitlab.enclave.vn/mateo/app/-/merge_requests/87"
    assert r.mr_target(url) == "develop"
    r.post_mr_note(url, "### avflow")
    assert calls[0][:4] == ["glab", "api", "--hostname", "gitlab.enclave.vn"]
    assert calls[0][4] == "projects/mateo%2Fapp/merge_requests/87"
    assert "POST" in calls[1] and calls[1][-1] == "body=### avflow" and calls[1][-3].endswith("/87/notes")


def test_github_pr_is_not_posted():
    r = GitRepo("/x", runner=lambda c, interactive=False: (0, ""))
    assert r.mr_target("https://github.com/a/b/pull/1") is None
    with pytest.raises(RepoError):
        r.post_mr_note("https://github.com/a/b/pull/1", "x")


def test_glab_failure_raises():
    r = GitRepo("/x", runner=lambda c, interactive=False: (1, "401 Unauthorized"))
    with pytest.raises(RepoError) as e:
        r.post_mr_note("https://gitlab.com/a/b/-/merge_requests/2", "x")
    assert "401" in str(e.value)


def test_default_runner_is_the_shared_one():
    assert GitRepo("/x").run is st.run


def test_mr_description_read_and_written_through_glab():
    calls = []

    def runner(cmd, interactive=False):
        calls.append(cmd)
        return 0, json.dumps({"description": "Refs #1"})
    r = GitRepo("/x", runner=runner)
    url = "https://gitlab.enclave.vn/mateo/app/-/merge_requests/87"
    assert r.mr_description(url) == "Refs #1"
    r.set_mr_description(url, "new")
    assert "PUT" in calls[1] and calls[1][-1] == "description=new"
