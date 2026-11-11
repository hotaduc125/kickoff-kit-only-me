import json
from datetime import datetime, timezone

from avflow import monitor
from avflow import setup_steps as st
from avflow.config import Config, MonitorConfig

NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def transcript(path, *usages, model="claude-opus-x"):
    lines = [json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}})]
    for inp, read, create in usages:
        lines.append(json.dumps({"type": "assistant", "message": {"model": model, "usage": {
            "input_tokens": inp, "cache_read_input_tokens": read, "cache_creation_input_tokens": create, "output_tokens": 50}}}))
    lines.append("not json")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def test_last_usage_reads_latest_reply(tmp_path):
    t = transcript(tmp_path / "t.jsonl", (100, 0, 0), (2000, 300000, 1000))
    assert monitor.last_usage(t) == (303000, "claude-opus-x")
    assert monitor.last_usage(str(tmp_path / "missing.jsonl")) == (None, None)


def test_levels():
    assert monitor.level(None, 300, 400) == "unknown"
    assert monitor.level(299, 300, 400) == "ok"
    assert monitor.level(300, 300, 400) == "warn"
    assert monitor.level(400, 300, 400) == "critical"


def test_prompt_ok_is_silent_and_logged(tmp_path):
    t = transcript(tmp_path / "t.jsonl", (1000, 50000, 0))
    code, out = monitor.handle({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "transcript_path": t},
                               MonitorConfig(), tmp_path, NOW)
    assert (code, out) == (0, None)
    e = json.loads((tmp_path / "usage.log").read_text().splitlines()[-1])
    assert e["agent"] == "main" and e["context_tokens"] == 51000 and e["level"] == "ok"


def test_prompt_warn_and_critical_inform_user_and_agent(tmp_path):
    for usage, word in (((0, 320000, 0), "warning"), ((0, 450000, 0), "limit")):
        t = transcript(tmp_path / f"{word}.jsonl", usage)
        code, out = monitor.handle({"hook_event_name": "UserPromptSubmit", "session_id": "s", "transcript_path": t},
                                   MonitorConfig(), tmp_path, NOW)
        assert code == 0 and word in out["systemMessage"]
        assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert out["hookSpecificOutput"]["additionalContext"]
    assert "handoff" in out["hookSpecificOutput"]["additionalContext"]


def test_enforce_blocks_past_limit(tmp_path):
    t = transcript(tmp_path / "t.jsonl", (0, 450000, 0))
    code, out = monitor.handle({"hook_event_name": "UserPromptSubmit", "transcript_path": t},
                               MonitorConfig(enforce=True), tmp_path, NOW)
    assert code == 2 and out is None


def test_subagent_events_logged_with_type_and_model(tmp_path):
    t = transcript(tmp_path / "agent.jsonl", (500, 20000, 0), model="claude-sonnet-y")
    monitor.handle({"hook_event_name": "SubagentStart", "session_id": "s", "agent_type": "avflow-implementer", "agent_id": "a1"},
                   MonitorConfig(), tmp_path, NOW)
    code, out = monitor.handle({"hook_event_name": "SubagentStop", "session_id": "s", "agent_type": "avflow-implementer",
                                "agent_id": "a1", "agent_transcript_path": t}, MonitorConfig(), tmp_path, NOW)
    assert (code, out) == (0, None)
    last = json.loads((tmp_path / "usage.log").read_text().splitlines()[-1])
    assert last["agent"] == "avflow-implementer" and last["model"] == "claude-sonnet-y" and last["context_tokens"] == 20500


def test_summary(tmp_path):
    log = tmp_path / "usage.log"
    rows = [
        {"time": "2026-11-09T10:00:00+00:00", "event": "UserPromptSubmit", "session": "s1", "agent": "main", "model": "opus", "context_tokens": 100000, "level": "ok"},
        {"time": "2026-11-09T11:00:00+00:00", "event": "UserPromptSubmit", "session": "s1", "agent": "main", "model": "opus", "context_tokens": 350000, "level": "warn"},
        {"time": "2026-11-09T12:00:00+00:00", "event": "SubagentStop", "session": "s1", "agent": "avflow-reviewer", "model": "opus", "context_tokens": 60000},
        {"time": "2026-11-09T12:30:00+00:00", "event": "SubagentStop", "session": "s1", "agent": "avflow-reviewer", "model": "opus", "context_tokens": 80000},
        {"time": "2026-10-01T10:00:00+00:00", "event": "UserPromptSubmit", "session": "old", "agent": "main", "context_tokens": 900000, "level": "critical"},
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    s = monitor.summary(tmp_path, 7, NOW)
    assert s["sessions"]["s1"]["peak"] == 350000 and "old" not in s["sessions"]
    assert s["agents"][("avflow-reviewer", "opus")] == {"calls": 2, "peak": 80000}
    assert s["hits"] == {"warn": 1, "critical": 0}


def test_set_monitor_keeps_other_hooks(tmp_path):
    f = tmp_path / "settings.json"
    other = {"hooks": [{"type": "command", "command": "notify-me"}]}
    f.write_text(json.dumps({"hooks": {"Stop": [other]}, "theme": "dark"}))
    st.set_monitor(True, f, command="/x/avflow-monitor")
    st.set_monitor(True, f, command="/x/avflow-monitor")
    d = json.loads(f.read_text())
    assert other in d["hooks"]["Stop"] and st.monitor_installed(f)
    for ev in st.MONITOR_EVENTS:
        assert sum("avflow-monitor" in h["command"] for e in d["hooks"][ev] for h in e["hooks"]) == 1
    st.set_monitor(False, f)
    d = json.loads(f.read_text())
    assert d["hooks"] == {"Stop": [other]} and d["theme"] == "dark" and not st.monitor_installed(f)


def test_monitor_and_guard_coexist(tmp_path):
    f = tmp_path / "settings.json"
    st.set_git_guard(True, f, command="/x/avflow-git-guard")
    st.set_monitor(True, f, command="/x/avflow-monitor")
    st.set_monitor(False, f)
    assert st.git_guard_installed(f)


def test_monitor_config_roundtrip(tmp_path):
    p = tmp_path / "c.toml"
    Config(monitor=MonitorConfig(enabled=True, warn_tokens=250000, critical_tokens=380000, enforce=True)).save(p)
    m = Config.load(p).monitor
    assert (m.enabled, m.warn_tokens, m.critical_tokens, m.enforce) == (True, 250000, 380000, True)
