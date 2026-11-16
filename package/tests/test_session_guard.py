"""Session guards: one ticket per Claude Code session, and no reading a large file whole.

Both keep the context (and the usage limits) small. They only see the agent's tool calls — the person is never blocked.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from avflow import session_guard as sg
from avflow import setup_steps as st
from avflow.config import GuardsConfig

START = "mcp__avflow-tickets__start_ticket"
OK_RESPONSE = [{"type": "text", "text": json.dumps({"ticket": 12, "status": "In progress", "required_checks": []})}]


def pre(tool, tool_input, session="s1"):
    return {"hook_event_name": "PreToolUse", "session_id": session, "tool_name": tool, "tool_input": tool_input}


def post(tool, tool_input, response, session="s1"):
    return {**pre(tool, tool_input, session), "hook_event_name": "PostToolUse", "tool_response": response}


@pytest.fixture
def cfg():
    return GuardsConfig()


# ---------- one ticket per session
def test_first_ticket_is_allowed_and_recorded_after_success(tmp_path, cfg):
    assert sg.handle(pre(START, {"ticket_id": 12}), cfg, tmp_path) == (0, None)
    assert sg.handle(post(START, {"ticket_id": 12}, OK_RESPONSE), cfg, tmp_path) == (0, None)
    assert sg.session_ticket(tmp_path, "s1") == "12"


def test_second_ticket_in_the_same_session_is_blocked(tmp_path, cfg):
    sg.handle(post(START, {"ticket_id": 12}, OK_RESPONSE), cfg, tmp_path)
    code, msg = sg.handle(pre(START, {"ticket_id": 15}), cfg, tmp_path)
    assert code == 2
    assert "This session is working on #12. Type /clear or open a new session to work on #15." in msg


def test_same_ticket_again_and_other_sessions_are_allowed(tmp_path, cfg):
    sg.handle(post(START, {"ticket_id": 12}, OK_RESPONSE), cfg, tmp_path)
    assert sg.handle(pre(START, {"ticket_id": "12"}), cfg, tmp_path)[0] == 0
    assert sg.handle(pre(START, {"ticket_id": 15}, session="s2"), cfg, tmp_path)[0] == 0


def test_a_refused_start_does_not_bind_the_session(tmp_path, cfg):
    refused = [{"type": "text", "text": "Status is 'Closed', not 'Ready'."}]
    sg.handle(post(START, {"ticket_id": 12}, refused), cfg, tmp_path)
    assert sg.session_ticket(tmp_path, "s1") is None
    assert sg.handle(pre(START, {"ticket_id": 15}), cfg, tmp_path)[0] == 0


def test_reading_other_tickets_stays_allowed(tmp_path, cfg):
    sg.handle(post(START, {"ticket_id": 12}, OK_RESPONSE), cfg, tmp_path)
    assert sg.handle(pre("mcp__avflow-tickets__get_ticket", {"ticket_id": 15}), cfg, tmp_path)[0] == 0


def test_rule_can_be_turned_off(tmp_path):
    off = GuardsConfig(one_ticket_per_session=False)
    sg.handle(post(START, {"ticket_id": 12}, OK_RESPONSE), off, tmp_path)
    assert sg.handle(pre(START, {"ticket_id": 15}), off, tmp_path)[0] == 0


def test_old_sessions_are_forgotten(tmp_path, cfg):
    old = datetime.now(timezone.utc) - timedelta(days=30)
    sg.handle(post(START, {"ticket_id": 12}, OK_RESPONSE), cfg, tmp_path, now=old)
    sg.handle(post(START, {"ticket_id": 3}, OK_RESPONSE, session="s2"), cfg, tmp_path)
    assert sg.session_ticket(tmp_path, "s1") is None and sg.session_ticket(tmp_path, "s2") == "3"


def test_unreadable_state_file_allows(tmp_path, cfg):
    (tmp_path / "sessions.json").write_text("{not json")
    assert sg.handle(pre(START, {"ticket_id": 15}), cfg, tmp_path)[0] == 0


# ---------- no large whole-file reads
def big(tmp_path, kb, name="big.log"):
    f = tmp_path / name
    f.write_bytes(b"x" * kb * 1024)
    return str(f)


def test_large_file_without_range_is_blocked(tmp_path, cfg):
    code, msg = sg.handle(pre("Read", {"file_path": big(tmp_path, 300)}), cfg, tmp_path)
    assert code == 2 and "300 KB" in msg and "200 KB" in msg and "offset" in msg and "Grep" in msg


@pytest.mark.parametrize("extra", [{"offset": 1}, {"limit": 200}, {"offset": 100, "limit": 50}])
def test_large_file_in_parts_is_allowed(tmp_path, cfg, extra):
    assert sg.handle(pre("Read", {"file_path": big(tmp_path, 300), **extra}), cfg, tmp_path)[0] == 0


@pytest.mark.parametrize("name", ["scan.png", "photo.JPG", "spec.pdf", "analysis.ipynb"])
def test_files_the_read_tool_handles_itself_are_exempt(tmp_path, cfg, name):
    assert sg.handle(pre("Read", {"file_path": big(tmp_path, 900, name)}), cfg, tmp_path)[0] == 0


def test_small_and_missing_files_are_allowed(tmp_path, cfg):
    assert sg.handle(pre("Read", {"file_path": big(tmp_path, 10)}), cfg, tmp_path)[0] == 0
    assert sg.handle(pre("Read", {"file_path": str(tmp_path / "nope.txt")}), cfg, tmp_path)[0] == 0


def test_size_limit_is_a_team_setting(tmp_path):
    f = big(tmp_path, 300)
    assert sg.handle(pre("Read", {"file_path": f}), GuardsConfig(max_read_kb=500), tmp_path)[0] == 0
    assert sg.handle(pre("Read", {"file_path": f}), GuardsConfig(max_read_kb=0), tmp_path)[0] == 0


# ---------- the hook never crashes Claude Code
@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_name": "Read", "tool_input": {"file_path": 5}}',
                                   '{"tool_name": "' + START + '", "tool_input": {"ticket_id": "abc"}}',
                                   '{"tool_name": "Read", "tool_input": null}'])
def test_hook_allows_unexpected_input(stdin, tmp_path):
    p = subprocess.run([sys.executable, "-m", "avflow.session_guard"], input=stdin, capture_output=True, text=True,
                       env={"AVFLOW_HOME": str(tmp_path), "PATH": ""})
    assert p.returncode == 0, p.stderr


# ---------- registration in Claude Code settings
def test_set_session_guard_registers_and_removes(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "other"}]}]}}))
    st.set_session_guard(True, f, command="/x/avflow-session-guard")
    d = json.loads(f.read_text())
    pre_m = sorted(e["matcher"] for e in d["hooks"]["PreToolUse"] if "avflow-session-guard" in str(e))
    post_m = [e["matcher"] for e in d["hooks"]["PostToolUse"] if "avflow-session-guard" in str(e)]
    assert pre_m == ["Read", START] and post_m == [START]
    st.set_session_guard(True, f, command="/x/avflow-session-guard")          # idempotent
    assert len(json.loads(f.read_text())["hooks"]["PreToolUse"]) == 3
    assert st.session_guard_installed(f)
    st.set_session_guard(False, f)
    d = json.loads(f.read_text())
    assert d["hooks"] == {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "other"}]}]}
    assert not st.session_guard_installed(f)


def test_session_guard_and_git_guard_coexist(tmp_path):
    f = tmp_path / "settings.json"
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    st.set_session_guard(True, f, command="/x/avflow-session-guard")
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    assert st.git_guard_installed(f) and st.session_guard_installed(f)
