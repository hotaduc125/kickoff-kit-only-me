"""avflow-session-guard — Claude Code hook that keeps sessions small (and the team inside its usage limits).

Two rules, team settings under [guards], both on by default:
- one ticket per session: PreToolUse on `start_ticket` blocks a second ticket in the same session (the person types
  /clear or opens a new session). The ticket is recorded on PostToolUse, only after a successful start, so a refused
  start does not bind the session. Restarting the same ticket and reading other tickets stay allowed.
- no large whole-file reads: PreToolUse on Read blocks a file over `max_read_kb` read without offset / limit. Images,
  PDFs and notebooks are exempt (the Read tool handles them itself).

Only the agent's tool calls pass through here; the person is never blocked. Any unexpected input allows (exit 0);
exit 2 only for a deliberate block, with the reason on stderr for the agent.
State: ~/.avflow/sessions.json ({session_id: {"ticket": "12", "time": iso}}, entries older than 7 days dropped).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

START_TICKET = "start_ticket"
EXEMPT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tif", ".tiff", ".heic", ".pdf", ".ipynb"}
KEEP_DAYS = 7


def _state(home: Path) -> dict:
    try:
        data = json.loads((home / "sessions.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(home: Path, data: dict) -> None:
    try:
        home.mkdir(parents=True, exist_ok=True)
        tmp = home / "sessions.json.tmp"
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, home / "sessions.json")
    except OSError:
        pass


def session_ticket(home: Path, session: str) -> str | None:
    entry = _state(home).get(session)
    return str(entry.get("ticket")) if isinstance(entry, dict) and entry.get("ticket") is not None else None


def _ticket_id(tool_input: dict) -> str | None:
    try:
        return str(int(tool_input.get("ticket_id")))
    except (TypeError, ValueError):
        return None


def _started(response) -> bool:
    """True when start_ticket succeeded (its result names the required checks; a refusal is plain text)."""
    return "required_checks" in json.dumps(response, default=str)


def _record(home: Path, session: str, ticket: str, now: datetime) -> None:
    data = _state(home)
    fresh = {}
    for sid, entry in data.items():
        try:
            if (now - datetime.fromisoformat(entry["time"])).days < KEEP_DAYS:
                fresh[sid] = entry
        except (TypeError, KeyError, ValueError):
            continue
    fresh[session] = {"ticket": ticket, "time": now.isoformat(timespec="seconds")}
    _save(home, fresh)


def check_ticket(payload: dict, home: Path, now: datetime) -> str | None:
    session, ticket = payload.get("session_id"), _ticket_id(payload.get("tool_input") or {})
    if not session or ticket is None:
        return None
    if payload.get("hook_event_name") == "PostToolUse":
        if _started(payload.get("tool_response")):
            _record(home, session, ticket, now)
        return None
    current = session_ticket(home, session)
    if current and current != ticket:
        return (f"This session is working on #{current}. Type /clear or open a new session to work on #{ticket}. "
                "(avflow: one ticket per session keeps the context and the usage small.) Tell the person; do not "
                "work around it.")
    return None


def check_read(tool_input: dict, max_kb: int) -> str | None:
    path = tool_input.get("file_path")
    if not max_kb or not isinstance(path, str) or tool_input.get("offset") is not None or tool_input.get("limit") is not None:
        return None
    if Path(path).suffix.lower() in EXEMPT:
        return None
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= max_kb * 1024:
        return None
    return (f"{path} is {size // 1024} KB — over the team's limit of {max_kb} KB for reading a file whole (it would "
            "fill the context). Search it with Grep first, then read only the part you need with offset and limit.")


def handle(payload: dict, cfg, home: Path, now: datetime | None = None) -> tuple[int, str | None]:
    """(exit code, message for the agent) for one hook event."""
    tool = str(payload.get("tool_name") or "")
    now = now or datetime.now(timezone.utc)
    reason = None
    if tool.endswith("__" + START_TICKET) and cfg.one_ticket_per_session:
        reason = check_ticket(payload, home, now)
    elif tool == "Read" and payload.get("hook_event_name", "PreToolUse") == "PreToolUse":
        reason = check_read(payload.get("tool_input") or {}, cfg.max_read_kb)
    return (2, reason) if reason else (0, None)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict) or not isinstance(payload.get("tool_input") or {}, dict):
            return 0
        from .config import HOME, Config, GuardsConfig
        try:
            cfg = Config.load().guards
        except (SystemExit, Exception):
            cfg = GuardsConfig()
        code, message = handle(payload, cfg, HOME)
    except Exception:
        return 0
    if code == 2 and message:
        sys.stderr.write(f"BLOCKED by avflow: {message}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
