"""Individual setup steps. Every external command goes through `run`, so the steps can be tested."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

CLAUDE_HOME = Path.home() / ".claude"
POCOCK_REPO = "https://github.com/mattpocock/skills.git"
POCOCK_SKILLS = ("handoff", "zoom-out")
SUPERPOWERS_MARKETPLACE = "obra/superpowers-marketplace"
SUPERPOWERS_PLUGIN = "superpowers@superpowers-marketplace"
KICKOFF_PLUGIN = "kickoff-kit@kickoff-kit"
MCP_NAME = "kickoff-tickets"
READ_TOOLS = ["whoami", "list_my_ready_tickets", "get_ticket", "find_hotspot_conflicts"]
WRITE_TOOLS = ["add_private_note", "set_fields", "start_ticket", "submit_for_review", "create_bug_draft"]


def run(cmd: list[str], interactive: bool = False) -> tuple[int, str]:
    """Run a command; interactive commands keep the terminal (e.g. glab auth login)."""
    try:
        if interactive:
            return subprocess.call(cmd), ""
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"{cmd[0]}: command not found"


def which(name: str) -> str | None:
    return shutil.which(name)


def mcp_command_path() -> str:
    """Full path of the kickoff-ticket-mcp command installed next to this Python."""
    exe = "kickoff-ticket-mcp.exe" if sys.platform == "win32" else "kickoff-ticket-mcp"
    here = Path(sys.executable).parent / exe
    if here.exists():
        return str(here)
    found = which("kickoff-ticket-mcp")
    if found:
        return found
    raise SystemExit("Cannot find the kickoff-ticket-mcp command. Install kickoff-kit with `uv tool install …` and run setup again.")


def register_mcp(runner=run) -> tuple[bool, str]:
    runner(["claude", "mcp", "remove", MCP_NAME, "--scope", "user"])
    code, out = runner(["claude", "mcp", "add", "--scope", "user", MCP_NAME, "--", mcp_command_path()])
    return code == 0, out


def install_plugin(marketplace: str, plugin: str, runner=run) -> tuple[bool, str]:
    runner(["claude", "plugin", "marketplace", "add", marketplace])
    code, out = runner(["claude", "plugin", "install", plugin, "--scope", "user"])
    if code != 0 and "already" in out.lower():
        return True, out
    return code == 0, out


def find_skill_dirs(root: Path, names=POCOCK_SKILLS) -> dict[str, Path]:
    """Skill folders (containing SKILL.md) whose folder name or frontmatter name matches."""
    found: dict[str, Path] = {}
    for md in root.rglob("SKILL.md"):
        folder = md.parent.name
        name = folder
        try:
            for line in md.read_text(encoding="utf-8").splitlines()[:15]:
                if line.lower().startswith("name:"):
                    name = line.split(":", 1)[1].strip().strip("'\"")
                    break
        except OSError:
            pass
        for n in names:
            if n in (folder, name) and n not in found:
                found[n] = md.parent
    return found


def install_pocock_skills(cache: Path, runner=run, skills_dir: Path = CLAUDE_HOME / "skills") -> tuple[list[str], list[str]]:
    repo = cache / "mattpocock-skills"
    if (repo / ".git").exists():
        runner(["git", "-C", str(repo), "pull", "--ff-only"])
    else:
        cache.mkdir(parents=True, exist_ok=True)
        code, out = runner(["git", "clone", "--depth", "1", POCOCK_REPO, str(repo)])
        if code != 0:
            return [], list(POCOCK_SKILLS)
    found = find_skill_dirs(repo)
    skills_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for name, src in found.items():
        dst = skills_dir / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        done.append(name)
    return done, [n for n in POCOCK_SKILLS if n not in found]


def merge_permissions(settings_file: Path = CLAUDE_HOME / "settings.json") -> None:
    """Reads run freely; writes ask first. Existing settings are kept; a backup is written once."""
    data = {}
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        except ValueError:
            raise SystemExit(f"{settings_file} is not valid JSON — fix it and run setup again.")
        bak = settings_file.with_suffix(".json.kickoff-backup")
        if not bak.exists():
            bak.write_text(settings_file.read_text(encoding="utf-8"), encoding="utf-8")
    perms = data.setdefault("permissions", {})
    for key, tools in (("allow", READ_TOOLS), ("ask", WRITE_TOOLS)):
        lst = perms.setdefault(key, [])
        for t in tools:
            name = f"mcp__{MCP_NAME}__{t}"
            if name not in lst:
                lst.append(name)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def can_read_repo(url: str, runner=run) -> bool:
    """True if git can read the repository without asking for a password."""
    import os
    old = os.environ.get("GIT_TERMINAL_PROMPT")
    os.environ["GIT_TERMINAL_PROMPT"] = "0"   # never hang on a credential prompt
    try:
        code, _ = runner(["git", "ls-remote", "--exit-code", "--heads", url])
    finally:
        if old is None:
            os.environ.pop("GIT_TERMINAL_PROMPT", None)
        else:
            os.environ["GIT_TERMINAL_PROMPT"] = old
    return code == 0


def gitlab_login(host: str, runner=run) -> bool:
    code, _ = runner(["glab", "auth", "status", "--hostname", host])
    if code == 0:
        return True
    code, _ = runner(["glab", "auth", "login", "--hostname", host], interactive=True)
    return code == 0
