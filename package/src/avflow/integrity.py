"""Integrity of the installed avflow plugin: compare its files with the checksums shipped in this package."""
from __future__ import annotations

import hashlib
import json
from importlib import resources
from pathlib import Path

PLUGIN_NAME = "avflow"
SKIP = {".git", "__pycache__", ".DS_Store"}
KEEP_HIDDEN = {".claude-plugin"}   # the only hidden folder that belongs to the release
ORPHAN_MARKER = ".orphaned_at"     # Claude Code marks old version folders with it


def _ignored(rel_parts) -> bool:
    """Files added by Claude Code itself (.in_use/…, .orphaned_at, …) or by the OS are not part of the release."""
    return any(p in SKIP or (p.startswith(".") and p not in KEEP_HIDDEN) for p in rel_parts)


def _files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not _ignored(p.relative_to(root).parts):
            yield p


def sha256(p: Path) -> str:
    # Normalise line endings so a CRLF checkout on Windows does not look modified.
    data = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def compute_manifest(plugin_dir: Path, version: str) -> dict:
    return {"version": version, "files": {p.relative_to(plugin_dir).as_posix(): sha256(p) for p in _files(plugin_dir)}}


def shipped_manifest() -> dict:
    try:
        return json.loads(resources.files("avflow").joinpath("data/plugin_manifest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"version": "dev", "files": {}}


def verify(plugin_dir: Path, manifest: dict) -> dict:
    expected = manifest.get("files", {})
    actual = {p.relative_to(plugin_dir).as_posix(): sha256(p) for p in _files(plugin_dir)}
    return {
        "modified": sorted(k for k in expected if k in actual and actual[k] != expected[k]),
        "missing": sorted(k for k in expected if k not in actual),
        "extra": sorted(k for k in actual if k not in expected),
    }


def is_orphaned(plugin_dir: Path) -> bool:
    return (plugin_dir / ORPHAN_MARKER).exists() or (plugin_dir.parent / ORPHAN_MARKER).exists()


def find_installed(claude_home: Path) -> list[Path]:
    """Every installed copy of the avflow plugin (marketplace clone and/or plugin cache)."""
    out = []
    base = claude_home / "plugins"
    if not base.exists():
        return out
    for pj in base.rglob(".claude-plugin/plugin.json"):
        try:
            if json.loads(pj.read_text(encoding="utf-8")).get("name") == PLUGIN_NAME:
                out.append(pj.parent.parent)
        except (OSError, ValueError):
            continue
    return out


def installed_version(plugin_dir: Path) -> str | None:
    try:
        return json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None
