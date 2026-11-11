"""Local audit log: one JSON line per tool call."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class Audit:
    def __init__(self, path: Path):
        self.path = path

    def write(self, tool: str, ticket_id, ok: bool, detail: str = "") -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": tool,
                     "ticket": ticket_id, "ok": ok, "detail": detail[:300]}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
