"""avflow-monitor — Claude Code hook that records context size per session and per subagent, and warns
before the context grows past the team's thresholds (quality tends to drop on very long contexts).

Events: UserPromptSubmit (orchestrator, before each turn), Stop (orchestrator, after each turn),
SubagentStart / SubagentStop (role subagents). Never blocks the agent unless enforce = true.
Log: ~/.avflow/usage.log (one JSON line per event). Token counts are read from the transcript the hook
is given: context = input + cache_read + cache_creation tokens of the latest reply.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TAIL_BYTES = 4 * 1024 * 1024


def last_usage(transcript: str | None) -> tuple[int | None, str | None]:
    """(context tokens, model) of the latest assistant reply in a Claude Code JSONL transcript."""
    if not transcript:
        return None, None
    p = Path(transcript)
    if not p.exists():
        return None, None
    try:
        with p.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None, None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        msg = entry.get("message") if isinstance(entry, dict) else None
        usage = (msg or {}).get("usage") if isinstance(msg, dict) else None
        if usage:
            total = sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            return total, msg.get("model")
    return None, None


def level(tokens: int | None, warn: int, critical: int) -> str:
    if tokens is None:
        return "unknown"
    return "critical" if tokens >= critical else "warn" if tokens >= warn else "ok"


def log(home: Path, entry: dict) -> None:
    try:
        home.mkdir(parents=True, exist_ok=True)
        with (home / "usage.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def handle(payload: dict, cfg, home: Path, now: datetime | None = None) -> tuple[int, dict | None]:
    """(exit code, JSON output or None) for one hook event."""
    event = payload.get("hook_event_name", "")
    now = now or datetime.now(timezone.utc)
    warn, critical = cfg.warn_tokens, cfg.critical_tokens
    base = {"time": now.isoformat(timespec="seconds"), "event": event, "session": payload.get("session_id")}

    if event in ("SubagentStart", "SubagentStop"):
        tokens, model = last_usage(payload.get("agent_transcript_path")) if event == "SubagentStop" else (None, None)
        log(home, {**base, "agent": payload.get("agent_type") or "subagent", "agent_id": payload.get("agent_id"),
                   "model": model, "context_tokens": tokens, "level": level(tokens, warn, critical)})
        return 0, None

    tokens, model = last_usage(payload.get("transcript_path"))
    lv = level(tokens, warn, critical)
    log(home, {**base, "agent": "main", "model": model, "context_tokens": tokens, "level": lv})
    if event != "UserPromptSubmit" or lv in ("ok", "unknown"):
        return 0, None
    k = f"{tokens // 1000}k"
    if lv == "warn":
        user = f"avflow: context is {k} tokens (warning at {warn // 1000}k). Plan a handoff soon."
        agent = (f"Context is now {k} tokens, past the team's warning threshold of {warn // 1000}k. Keep the work focused: "
                 "delegate reading and implementation to the role subagents, avoid loading large files, and plan a handoff.")
    else:
        user = f"avflow: context is {k} tokens — past the {critical // 1000}k limit. Write a handoff and start a new session."
        agent = (f"Context is now {k} tokens, past the team's limit of {critical // 1000}k, where answers become less reliable. "
                 "Do not start new work. Finish or stop the current step, write a handoff as a private note on the ticket "
                 "(what was done, what is left, how to verify), and ask the person to start a new session.")
    if lv == "critical" and cfg.enforce:
        sys.stderr.write(user + "\n")
        return 2, None
    return 0, {"systemMessage": user,
               "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": agent}}


def summary(home: Path, days: int = 7, now: datetime | None = None) -> dict:
    """Aggregate the usage log: peak context per session, subagent calls per type and model, threshold hits."""
    now = now or datetime.now(timezone.utc)
    sessions, agents, hits = {}, {}, {"warn": 0, "critical": 0}
    p = home / "usage.log"
    if not p.exists():
        return {"sessions": {}, "agents": {}, "hits": hits}
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            t = datetime.fromisoformat(e["time"])
        except (ValueError, KeyError):
            continue
        if (now - t).days >= days:
            continue
        tok = e.get("context_tokens") or 0
        if e.get("agent") == "main":
            s = sessions.setdefault(e.get("session") or "?", {"peak": 0, "model": None, "last": e["time"]})
            if tok >= s["peak"]:
                s["peak"], s["model"] = tok, e.get("model") or s["model"]
            s["last"] = e["time"]
            if e.get("event") == "UserPromptSubmit" and e.get("level") in hits:
                hits[e["level"]] += 1
        elif e.get("event") == "SubagentStop":
            key = (e.get("agent") or "subagent", e.get("model") or "?")
            a = agents.setdefault(key, {"calls": 0, "peak": 0})
            a["calls"] += 1
            a["peak"] = max(a["peak"], tok)
    return {"sessions": sessions, "agents": agents, "hits": hits}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    try:
        from .config import HOME, Config
        cfg = Config.load().monitor
    except (SystemExit, Exception):
        from .config import HOME, MonitorConfig
        cfg = MonitorConfig()
    code, out = handle(payload, cfg, HOME)
    if out:
        print(json.dumps(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
