from pathlib import Path

import pytest

from kickoff_kit import cli
from kickoff_kit import setup_steps as st
from kickoff_kit.config import Config, TicketConfig


@pytest.mark.parametrize("url,repo", [
    ("https://github.com/alvin-enc/kickoff-kit-marketplace.git", "alvin-enc/kickoff-kit-marketplace"),
    ("https://github.com/alvin-enc/kickoff-kit-marketplace", "alvin-enc/kickoff-kit-marketplace"),
    ("git@github.com:alvin-enc/kickoff-kit-marketplace.git", "alvin-enc/kickoff-kit-marketplace"),
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
    monkeypatch.setattr(st, "latest_release", lambda repo, runner=None: "v0.0.1")
    assert cli.cmd_update(Args()) == 0 and "up to date" in capsys.readouterr().out


def test_update_installs_newer(cfg, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(st, "latest_release", lambda repo, runner=None: "v99.0.0")
    wheel = tmp_path / "kickoff_kit-99.0.0-py3-none-any.whl"
    wheel.write_text("x")
    monkeypatch.setattr(st, "download_wheel", lambda repo, tag, dest, runner=None: wheel)
    monkeypatch.setattr(st, "uv_command", lambda: "/bin/uv")
    calls = []
    monkeypatch.setattr(st, "run", lambda cmd, interactive=False: (calls.append(cmd) or (0, "")))
    monkeypatch.setattr(st, "update_plugin", lambda runner=None: True)
    assert cli.cmd_update(Args()) == 0
    assert ["/bin/uv", "tool", "install", "--force", str(wheel)] in calls
    assert calls[-1] == ["/bin/kickoff-kit", "doctor"]


def test_update_check_only(cfg, monkeypatch, capsys):
    monkeypatch.setattr(st, "latest_release", lambda repo, runner=None: "v99.0.0")
    a = Args(); a.check = True
    assert cli.cmd_update(a) == 0 and "Update available" in capsys.readouterr().out


def test_update_requires_github(cfg, monkeypatch, capsys):
    cfg.marketplace = "https://gitlab.enclave.vn/x/y.git"
    assert cli.cmd_update(Args()) == 1


def test_download_wheel_picks_file(tmp_path):
    def runner(cmd, interactive=False):
        d = Path(cmd[cmd.index("--dir") + 1]); (d / "kickoff_kit-1.2.0-py3-none-any.whl").write_text("w"); return 0, ""
    assert st.download_wheel("o/m", "v1.2.0", tmp_path / "dl", runner=runner).name == "kickoff_kit-1.2.0-py3-none-any.whl"
