from pathlib import Path

import pytest

from avflow import cli
from avflow import setup_steps as st
from avflow.config import Config, TicketConfig


@pytest.mark.parametrize("url,repo", [
    ("https://github.com/alvin-enc/avflow-marketplace.git", "alvin-enc/avflow-marketplace"),
    ("https://github.com/alvin-enc/avflow-marketplace", "alvin-enc/avflow-marketplace"),
    ("git@github.com:alvin-enc/avflow-marketplace.git", "alvin-enc/avflow-marketplace"),
    ("https://gitlab.enclave.vn/x/y.git", None),
])
def test_github_repo_from_url(url, repo):
    assert st.github_repo_from_url(url) == repo


def test_parse_version():
    assert st.parse_version("v1.2.0") > st.parse_version("1.1.3")
    assert st.parse_version("1.10.0") > st.parse_version("1.9.9")


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    c = Config(TicketConfig(url="https://r.test"), marketplace="https://github.com/o/m.git")
    monkeypatch.setattr(Config, "load", staticmethod(lambda *a, **k: c))
    monkeypatch.setattr(cli, "HOME", tmp_path)
    monkeypatch.setattr(st, "which", lambda n: f"/bin/{n}")
    return c


class Args:
    check = False
    force = False


def test_update_up_to_date(cfg, monkeypatch, capsys):
    monkeypatch.setattr(st, "latest_release_detail", lambda repo, runner=None: ("v0.0.1", ""))
    assert cli.cmd_update(Args()) == 0 and "up to date" in capsys.readouterr().out


def test_update_installs_newer(cfg, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(st, "latest_release_detail", lambda repo, runner=None: ("v99.0.0", ""))
    wheel = tmp_path / "avflow-99.0.0-py3-none-any.whl"
    wheel.write_text("x")
    monkeypatch.setattr(st, "download_wheel", lambda repo, tag, dest, runner=None: wheel)
    monkeypatch.setattr(st, "uv_command", lambda: "/bin/uv")
    calls = []
    monkeypatch.setattr(st, "run", lambda cmd, interactive=False: (calls.append(cmd) or (0, "")))
    monkeypatch.setattr(st, "update_plugin", lambda runner=None: True)
    assert cli.cmd_update(Args()) == 0
    assert ["/bin/uv", "tool", "install", "--force", str(wheel)] in calls
    assert calls[-1] == ["/bin/avflow", "check"]


def test_update_check_only(cfg, monkeypatch, capsys):
    monkeypatch.setattr(st, "latest_release_detail", lambda repo, runner=None: ("v99.0.0", ""))
    a = Args(); a.check = True
    assert cli.cmd_update(a) == 0 and "Update available" in capsys.readouterr().out


def test_update_requires_github(cfg, monkeypatch, capsys):
    cfg.marketplace = "https://gitlab.enclave.vn/x/y.git"
    assert cli.cmd_update(Args()) == 1


def test_download_wheel_picks_file(tmp_path):
    def runner(cmd, interactive=False):
        d = Path(cmd[cmd.index("--dir") + 1]); (d / "avflow-1.2.0-py3-none-any.whl").write_text("w"); return 0, ""
    assert st.download_wheel("o/m", "v1.2.0", tmp_path / "dl", runner=runner).name == "avflow-1.2.0-py3-none-any.whl"


@pytest.mark.parametrize("gh_out,expected", [
    ("release not found", "no published release yet"),
    ("To get started with GitHub CLI, please run:  gh auth login", "not signed in"),
    ("GraphQL: Could not resolve to a Repository with the name 'o/m'.", "not visible"),
])
def test_latest_release_explains(gh_out, expected):
    tag, why = st.latest_release_detail("o/m", runner=lambda c, interactive=False: (1, gh_out))
    assert tag is None and expected in why and "gh said:" in why


def test_update_plugin_runs_without_mocks():
    """Calls the real function with a fake runner — catches undefined names that mocks would hide."""
    calls = []
    assert st.update_plugin(runner=lambda c, interactive=False: (calls.append(c) or (0, ""))) is True
    assert calls[-1] == ["claude", "plugin", "update", st.AVFLOW_PLUGIN]


def test_every_setup_step_name_resolves():
    """Static check: no function in setup_steps or cli refers to a name that does not exist."""
    import ast, builtins, inspect
    from avflow import cli as cli_mod, git_guard, init_repo, monitor, release_notes, report as report_mod, risk
    from avflow.tickets import core, repo
    for mod in (st, cli_mod, git_guard, init_repo, monitor, release_notes, report_mod, risk, core, repo):
        tree = ast.parse(inspect.getsource(mod))
        defined = set(dir(mod)) | set(dir(builtins))
        tops = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
        tops += [m for c in tree.body if isinstance(c, ast.ClassDef) for m in c.body if isinstance(m, ast.FunctionDef)]
        for node in tops:  # nested functions are checked inside their parent, so closures resolve
            if True:
                args = {a.arg for a in ast.walk(node) if isinstance(a, ast.arg)}
                assigned = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
                imported = {a.asname or a.name.split(".")[0] for n in ast.walk(node) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
                comp = {n.id for c in ast.walk(node) if isinstance(c, (ast.comprehension,)) for n in ast.walk(c.target) if isinstance(n, ast.Name)}
                comp |= {h.name for h in ast.walk(node) if isinstance(h, ast.ExceptHandler) and h.name}
                comp |= {f.name for f in ast.walk(node) if isinstance(f, ast.FunctionDef)}
                for n in ast.walk(node):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                        assert n.id in defined | args | assigned | imported | comp, f"{mod.__name__}: undefined name {n.id}"


@pytest.mark.parametrize("name", ["check", "doctor"])
def test_check_and_doctor_both_work(name, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "cmd_doctor", lambda a: seen.setdefault("ran", 0) or 0)
    import argparse
    assert cli.main([name]) == 0 and "ran" in seen
