"""Individual setup steps. Every external command goes through `run`, so the steps can be tested."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CLAUDE_HOME = Path.home() / ".claude"
POCOCK_REPO = "https://github.com/mattpocock/skills.git"
POCOCK_REF = "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d"           # pinned commit of mattpocock/skills (update deliberately in a release)
POCOCK_SKILLS = ("handoff",)      # always installed (zoom-out is a avflow team skill)
# Curated Matt Pocock set for the "pocock" workflow profile. Excluded on purpose: skills that publish to an
# issue tracker (setup-matt-pocock-skills, to-spec, to-tickets, triage, wayfinder, implement-spec), the router
# ask-matt, domain-modeling (own GLOSSARY.md), the in-progress group, and TypeScript-only tools.
POCOCK_PROFILE_SKILLS = ("handoff", "grill-with-docs", "implement", "tdd", "diagnosing-bugs", "code-review",
                         "prototype", "research", "codebase-design", "improve-codebase-architecture", "pr", "retro")
PROFILES = {"superpowers": "Superpowers (obra/superpowers)", "pocock": "Matt Pocock's skills (curated set, pinned version)"}
GUARD_MARKER = "avflow-git-guard"
SUPERPOWERS_MARKETPLACE = "obra/superpowers-marketplace"
SUPERPOWERS_PLUGIN = "superpowers@superpowers-marketplace"
AVFLOW_PLUGIN = "avflow@avflow"
MCP_NAME = "avflow-tickets"
READ_TOOLS = ["whoami", "list_my_ready_tickets", "get_ticket", "find_hotspot_conflicts"]
WRITE_TOOLS = ["add_private_note", "set_fields", "start_ticket", "assess_plan", "review_requirements", "submit_for_review",
               "create_bug_draft"]


def run(cmd: list[str], interactive: bool = False) -> tuple[int, str]:
    """Run a command; interactive commands keep the terminal (e.g. glab auth login).

    The program is resolved with shutil.which first: on Windows, tools installed by npm are
    `.cmd` files (e.g. claude.cmd) that CreateProcess does not find from the bare name.
    """
    exe = shutil.which(cmd[0])
    if exe:
        cmd = [exe] + list(cmd[1:])
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
    """Full path of the avflow-ticket-mcp command installed next to this Python."""
    exe = "avflow-ticket-mcp.exe" if sys.platform == "win32" else "avflow-ticket-mcp"
    here = Path(sys.executable).parent / exe
    if here.exists():
        return str(here)
    found = which("avflow-ticket-mcp")
    if found:
        return found
    raise SystemExit("Cannot find the avflow-ticket-mcp command. Install avflow with `uv tool install …` and run setup again.")


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


def skills_for(profile: str) -> tuple[str, ...]:
    return POCOCK_PROFILE_SKILLS if profile == "pocock" else POCOCK_SKILLS


def install_pocock_skills(cache: Path, runner=run, skills_dir: Path = CLAUDE_HOME / "skills",
                          ref: str = POCOCK_REF, names: tuple[str, ...] = POCOCK_SKILLS) -> tuple[list[str], list[str]]:
    """Fetch Matt Pocock's skills at a pinned commit and copy the selected ones into ~/.claude/skills."""
    repo = cache / "mattpocock-skills"
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        runner(["git", "-C", str(repo), "init", "-q"])
        runner(["git", "-C", str(repo), "remote", "add", "origin", POCOCK_REPO])
    code, _ = runner(["git", "-C", str(repo), "fetch", "-q", "--depth", "1", "origin", ref])
    if code == 0:
        code, _ = runner(["git", "-C", str(repo), "checkout", "-q", "--force", "FETCH_HEAD"])
    if code != 0:
        return [], list(names)
    found = find_skill_dirs(repo, names)
    skills_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for name, src in found.items():
        dst = skills_dir / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        done.append(name)
    _record_skills(cache.parent, done)
    return done, [n for n in names if n not in found]


def _record_skills(home: Path, names: list[str]) -> None:
    try:
        (home / "installed_skills.json").write_text(json.dumps(sorted(names)), encoding="utf-8")
    except OSError:
        pass


def recorded_skills(home: Path) -> list[str]:
    try:
        return json.loads((home / "installed_skills.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def remove_skills(names, skills_dir: Path = CLAUDE_HOME / "skills") -> list[str]:
    removed = []
    for n in names:
        d = skills_dir / n
        if d.is_dir():
            shutil.rmtree(d)
            removed.append(n)
    return removed


def remove_superpowers(runner=run) -> None:
    runner(["claude", "plugin", "uninstall", SUPERPOWERS_PLUGIN])


# ---------- git guardrails (PreToolUse hook)
def guard_command_path() -> str:
    exe = "avflow-git-guard.exe" if sys.platform == "win32" else "avflow-git-guard"
    here = Path(sys.executable).parent / exe
    if here.exists():
        return str(here)
    found = which("avflow-git-guard")
    if found:
        return found
    raise SystemExit("Cannot find the avflow-git-guard command. Reinstall avflow and run setup again.")


def _load_settings(settings_file: Path) -> dict:
    if not settings_file.exists():
        return {}
    try:
        return json.loads(settings_file.read_text(encoding="utf-8"))
    except ValueError:
        raise SystemExit(f"{settings_file} is not valid JSON — fix it and run setup again.")


def _without_guard(pre: list) -> list:
    out = []
    for entry in pre:
        hooks = [h for h in entry.get("hooks", []) if GUARD_MARKER not in str(h.get("command", ""))]
        if hooks:
            out.append({**entry, "hooks": hooks})
    return out


def set_git_guard(enabled: bool, settings_file: Path = CLAUDE_HOME / "settings.json", command: str | None = None) -> None:
    """Add (or remove) the avflow PreToolUse hook for the Bash tool; other hooks are kept."""
    data = _load_settings(settings_file)
    hooks = data.setdefault("hooks", {})
    pre = _without_guard(hooks.get("PreToolUse", []))
    if enabled:
        cmd = command or guard_command_path()
        pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": f'"{cmd}"'}]})
    if pre:
        hooks["PreToolUse"] = pre
    else:
        hooks.pop("PreToolUse", None)
    if not hooks:
        data.pop("hooks", None)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def git_guard_installed(settings_file: Path = CLAUDE_HOME / "settings.json") -> bool:
    try:
        data = _load_settings(settings_file)
    except SystemExit:
        return False
    return any(GUARD_MARKER in str(h.get("command", "")) for e in data.get("hooks", {}).get("PreToolUse", []) for h in e.get("hooks", []))


def merge_permissions(settings_file: Path = CLAUDE_HOME / "settings.json") -> None:
    """Reads run freely; writes ask first. Existing settings are kept; a backup is written once."""
    data = {}
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        except ValueError:
            raise SystemExit(f"{settings_file} is not valid JSON — fix it and run setup again.")
        bak = settings_file.with_suffix(".json.avflow-backup")
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


# ---------- updates from GitHub Releases of the marketplace repository
def github_repo_from_url(url: str) -> str | None:
    """'https://github.com/owner/repo.git' or 'git@github.com:owner/repo.git' → 'owner/repo'."""
    import re
    m = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", (url or "").strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def parse_version(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def latest_release(repo: str, runner=run) -> str | None:
    tag, _ = latest_release_detail(repo, runner)
    return tag


def latest_release_detail(repo: str, runner=run) -> tuple[str | None, str]:
    """(tag, explanation). The explanation says why there is no tag, in plain words, with gh's own message."""
    code, out = runner(["gh", "release", "view", "--repo", repo, "--json", "tagName", "--jq", ".tagName"])
    text = out.strip()
    if code == 0 and text:
        return text, ""
    low = text.lower()
    if "release not found" in low or "no releases" in low:
        why = f"{repo} has no published release yet (drafts and pre-releases do not count). Publish one with release.py --push."
    elif "auth" in low and ("login" in low or "not logged" in low or "token" in low):
        why = "gh is not signed in — run `gh auth login` (and `gh auth switch` if you use several accounts)."
    elif "could not resolve" in low or "404" in low or "not found" in low:
        why = f"{repo} is not visible to the GitHub account gh uses — check `gh auth status` and your access to the repository."
    else:
        why = "gh could not read the releases."
    return None, why + (f"\n     gh said: {text[:300]}" if text else "")


def download_wheel(repo: str, tag: str, dest: Path, runner=run) -> Path | None:
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("avflow-*.whl"):
        old.unlink()
    code, _ = runner(["gh", "release", "download", tag, "--repo", repo, "--pattern", "avflow-*.whl", "--dir", str(dest), "--clobber"])
    wheels = sorted(dest.glob("avflow-*.whl"))
    return wheels[-1] if code == 0 and wheels else None


def uv_command() -> str | None:
    found = which("uv")
    if found:
        return found
    home_uv = Path.home() / ".local" / "bin" / ("uv.exe" if sys.platform == "win32" else "uv")
    return str(home_uv) if home_uv.exists() else None


def update_plugin(runner=run) -> bool:
    runner(["claude", "plugin", "marketplace", "update", "avflow"])
    code, out = runner(["claude", "plugin", "update", AVFLOW_PLUGIN])
    return code == 0 or "up to date" in out.lower() or "already" in out.lower()


# ---------- role subagents (model per task)
AGENT_ROLES = {"plan": "avflow-planner", "implement": "avflow-implementer", "review": "avflow-reviewer"}


def agent_text(role: str, model: str) -> str:
    from importlib import resources
    name = AGENT_ROLES[role]
    return resources.files("avflow").joinpath(f"agents/{name}.md").read_text(encoding="utf-8").replace("{model}", model)


def install_agents(models, agents_dir: Path = CLAUDE_HOME / "agents") -> list[str]:
    """Write ~/.claude/agents/avflow-*.md from the member's model choices (not part of the plugin, so the
    integrity check of the plugin is not affected by personal model settings)."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for role, name in AGENT_ROLES.items():
        (agents_dir / f"{name}.md").write_text(agent_text(role, getattr(models, role)), encoding="utf-8", newline="\n")
        done.append(f"{name} ({getattr(models, role)})")
    return done


def agents_status(models, agents_dir: Path = CLAUDE_HOME / "agents") -> list[tuple[str, bool, str]]:
    """(agent, ok, detail) for each role subagent."""
    out = []
    for role, name in AGENT_ROLES.items():
        f = agents_dir / f"{name}.md"
        want = getattr(models, role)
        if not f.exists():
            out.append((name, False, "missing — run avflow setup"))
            continue
        text = f.read_text(encoding="utf-8").replace("\r\n", "\n")
        if text == agent_text(role, want):
            out.append((name, True, want))
        else:
            m = re.search(r"^model:\s*(\S+)", text, re.M)
            have = m.group(1) if m else "?"
            detail = f"model is {have}, configuration says {want}" if have != want else "edited by hand"
            out.append((name, False, detail + " — run avflow setup"))
    return out


def remove_agents(agents_dir: Path = CLAUDE_HOME / "agents") -> list[str]:
    removed = []
    for name in AGENT_ROLES.values():
        f = agents_dir / f"{name}.md"
        if f.exists():
            f.unlink()
            removed.append(name)
    return removed


# ---------- context monitor (UserPromptSubmit, Stop, SubagentStart, SubagentStop)
MONITOR_MARKER = "avflow-monitor"
MONITOR_EVENTS = ("UserPromptSubmit", "Stop", "SubagentStart", "SubagentStop")


def monitor_command_path() -> str:
    exe = "avflow-monitor.exe" if sys.platform == "win32" else "avflow-monitor"
    here = Path(sys.executable).parent / exe
    if here.exists():
        return str(here)
    found = which("avflow-monitor")
    if found:
        return found
    raise SystemExit("Cannot find the avflow-monitor command. Reinstall avflow and run setup again.")


def set_monitor(enabled: bool, settings_file: Path = CLAUDE_HOME / "settings.json", command: str | None = None) -> None:
    """Add (or remove) the avflow-monitor hook on its events; other hooks are kept."""
    data = _load_settings(settings_file)
    hooks = data.setdefault("hooks", {})
    cmd = (command or monitor_command_path()) if enabled else None
    for ev in MONITOR_EVENTS:
        entries = []
        for e in hooks.get(ev, []):
            hs = [h for h in e.get("hooks", []) if MONITOR_MARKER not in str(h.get("command", ""))]
            if hs:
                entries.append({**e, "hooks": hs})
        if enabled:
            entries.append({"hooks": [{"type": "command", "command": f'"{cmd}"'}]})
        if entries:
            hooks[ev] = entries
        else:
            hooks.pop(ev, None)
    if not hooks:
        data.pop("hooks", None)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def monitor_installed(settings_file: Path = CLAUDE_HOME / "settings.json") -> bool:
    try:
        data = _load_settings(settings_file)
    except SystemExit:
        return False
    hooks = data.get("hooks", {})
    return all(any(MONITOR_MARKER in str(h.get("command", "")) for e in hooks.get(ev, []) for h in e.get("hooks", []))
               for ev in MONITOR_EVENTS)
