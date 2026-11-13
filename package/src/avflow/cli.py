"""avflow command line: setup · doctor · uninstall."""
from __future__ import annotations

import argparse
import getpass
import sys

from . import __version__
from . import setup_steps as st
from . import integrity
from .config import CONFIG_FILE, HOME, Config, RepoConfig, TicketConfig, delete_secret, get_secret, set_secret
from .tickets.adapters import AdapterError, make_adapter

TICKET_CHOICES = [("redmine", "Redmine", True), ("jira", "Jira", False), ("gitlab", "GitLab Issues", False), ("github", "GitHub Issues", False)]
REPO_CHOICES = [("gitlab", "GitLab", True), ("github", "GitHub", False)]
GITLAB_TOKEN_HINT = ("     Create a personal access token on https://{host}/-/user_settings/personal_access_tokens with scopes\n"
                     "     'api' and 'write_repository' (fine-grained tokens: include User: Read), then run\n"
                     "     `glab auth login --hostname {host}` and `avflow check`.")
DEFAULT_MARKETPLACE = "https://github.com/<owner>/avflow-marketplace.git"  # set at release time


def normalize_host(value: str) -> str:
    """'https://gitlab.example.com/' → 'gitlab.example.com' (glab needs a bare host name)."""
    v = value.strip()
    for prefix in ("https://", "http://"):
        if v.lower().startswith(prefix):
            v = v[len(prefix):]
    return v.split("/")[0]


def ask(prompt: str, default: str = "") -> str:
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def choose(title: str, options) -> str:
    print(f"\n{title}")
    for n, (_, label, ok) in enumerate(options, 1):
        print(f"  {n}. {label}{'' if ok else '  (coming soon)'}")
    while True:
        v = ask("Choose", "1")
        if v.isdigit() and 1 <= int(v) <= len(options):
            key, label, ok = options[int(v) - 1]
            if ok:
                return key
            print(f"  {label} is not available in v{__version__} yet.")
        else:
            print("  Enter a number from the list.")


def ok(msg):
    print(f"  ✅ {msg}")


def bad(msg):
    print(f"  ❌ {msg}")


def setup_tickets_redmine(existing: TicketConfig | None) -> TicketConfig:
    t = existing if existing and existing.provider == "redmine" else TicketConfig(provider="redmine")
    old_url = t.url
    print("\nRedmine — your own account. The API key is under My account → API access key.")
    for attempt in range(3):
        t.url = ask("Redmine URL (base address, e.g. https://redmine.example.com)", t.url).rstrip("/")
        token = getpass.getpass("Redmine API key (hidden): ").strip()
        try:
            me = make_adapter(t, token).whoami()
        except (AdapterError, SystemExit) as e:
            bad(str(e))
            continue
        ok(f"Connected as {me['name']} ({me['login']})")
        adapter = make_adapter(t, token)
        try:
            available = [x["name"] for x in adapter.statuses()]
        except Exception:  # noqa: BLE001 — statuses are optional information here
            available = []
        if available:
            plan = status_plan(available, t)
            if plan["missing"]:
                print(f"  ➖ Statuses in this Redmine: {', '.join(available)}")
                print(f"  ➖ Not found: {', '.join(plan['missing'])}")
                if plan["preset"] and ask("  Use the Redmine default statuses — " + plan["preset_text"] + "? y/n", "y").lower() == "y":
                    apply_status_preset(t, plan["preset"])
                    ok("Status mapping: " + plan["preset_text"])
                else:
                    for attr, label in (("status_ready", "Ready"), ("status_in_progress", "In progress"), ("status_in_review", "In review")):
                        while getattr(t, attr) not in available:
                            setattr(t, attr, ask(f"  Status to use for '{label}'", available[0]))
        print("  ➖ Risk area, Hotspot (and Machine-side during the transition): custom fields are used when they exist;")
        print("     otherwise avflow reads them from the 'Size and mode' line of the ticket description.")
        if ask("Use the default status and field names (Ready, In progress, In review, Risk area, Machine-side, Hotspot)? y/n", "y").lower() != "y":
            t.status_ready = ask("Status: ready", t.status_ready)
            t.status_in_progress = ask("Status: in progress", t.status_in_progress)
            t.status_in_review = ask("Status: in review", t.status_in_review)
            t.field_risk_area = ask("Field: risk area", t.field_risk_area)
            t.field_machine_side = ask("Field: machine-side", t.field_machine_side)
            t.field_hotspot = ask("Field: hotspot", t.field_hotspot)
        set_secret("redmine", t.url, token)
        ok("API key stored in the OS keyring (not in any file)")
        if old_url and old_url.rstrip("/") != t.url:
            delete_secret("redmine", old_url)
            ok(f"Old API key for {old_url} removed from the keyring")
        return t
    raise SystemExit("Could not connect to Redmine after 3 attempts.")


REDMINE_DEFAULT_PRESET = {"status_ready": "New", "status_in_progress": "In Progress", "status_in_review": "Feedback",
                          "status_ready_for_test": "Resolved", "blocker_done": ["Resolved", "Closed"]}


def status_plan(available: list[str], t) -> dict:
    """Which configured statuses are missing, and whether Redmine's default statuses can stand in for them."""
    have = {a.lower() for a in available}
    missing = [n for n in (t.status_ready, t.status_in_progress, t.status_in_review, t.status_ready_for_test) if n.lower() not in have]
    preset = None
    if missing and all(v.lower() in have for k, v in REDMINE_DEFAULT_PRESET.items() if k != "blocker_done"):
        preset = REDMINE_DEFAULT_PRESET
    text = "Ready → New · In progress → In Progress · In review → Feedback · Ready for test → Resolved"
    return {"missing": missing, "preset": preset, "preset_text": text}


def apply_status_preset(t, preset: dict) -> None:
    for k, v in preset.items():
        setattr(t, k, list(v) if isinstance(v, list) else v)


def print_team_summary(cfg) -> None:
    from .config import team_version
    v = team_version() or "dev"
    t, w, m, mo = cfg.tickets, cfg.workflow, cfg.models, cfg.monitor
    print(f"Team settings (release {v}) — use `avflow setup --advanced` to change them for yourself")
    print(f"  Redmine {t.url or '(not set)'} · GitLab {cfg.repo.host}")
    print(f"  Statuses: {t.status_ready} → {t.status_in_progress} → {t.status_in_review} → {t.status_ready_for_test}")
    print(f"  Workflow: {st.PROFILES.get(w.profile, w.profile)} · git guardrails {'on' if w.git_guardrails else 'off'}")
    print(f"  Models: plan {m.plan} · implement {m.implement} · review {m.review}")
    print(f"  Context monitor: {'on' if mo.enabled else 'off'} (warn {mo.warn_tokens // 1000}k, limit {mo.critical_tokens // 1000}k)\n")


def setup_redmine_token(t: TicketConfig) -> TicketConfig:
    """Default setup: the team gives the URL and names; the member only enters their own API key."""
    old_url = t.url
    if not t.url:
        t.url = ask("Redmine URL (base address, e.g. https://redmine.example.com)").rstrip("/")
    print(f"Redmine — your own account at {t.url}. The API key is under My account → API access key.")
    for _ in range(3):
        token = getpass.getpass("Redmine API key (hidden): ").strip()
        try:
            me = make_adapter(t, token).whoami()
        except (AdapterError, SystemExit) as e:
            bad(str(e))
            continue
        ok(f"Connected as {me['name']} ({me['login']})")
        try:
            available = [x["name"] for x in make_adapter(t, token).statuses()]
        except Exception:  # noqa: BLE001
            available = []
        missing = status_plan(available, t)["missing"] if available else []
        if missing:
            bad(f"The team's statuses are not all in this Redmine (missing: {', '.join(missing)}). Tell the PM; "
                "until then, `avflow setup --advanced` can map them for you.")
        set_secret("redmine", t.url, token)
        ok("API key stored in the OS keyring (not in any file)")
        if old_url and old_url.rstrip("/") != t.url:
            delete_secret("redmine", old_url)
        return t
    raise SystemExit("Could not connect to Redmine after 3 attempts.")


def cmd_setup(args) -> int:
    print(f"avflow {__version__} — setup\n")
    try:
        cfg = Config.load()
    except SystemExit:
        cfg = Config.team()
    advanced = bool(getattr(args, "advanced", False))

    print("Prerequisites")
    missing = [n for n in ("git", "claude") if not st.which(n)]
    for n in ("git", "claude"):
        (bad if n in missing else ok)(n)
    if missing:
        print("\nInstall the missing tools first: git (https://git-scm.com), Claude Code (https://docs.claude.com/claude-code).")
        return 1

    if advanced:
        tp = choose("Ticket system", TICKET_CHOICES)
        if tp == "redmine":
            cfg.tickets = setup_tickets_redmine(cfg.tickets)

        rp = choose("Repository and CI/CD", REPO_CHOICES)
        cfg.repo = RepoConfig(provider=rp, host=normalize_host(ask("GitLab host name (e.g. gitlab.com or gitlab.example.com)", normalize_host(cfg.repo.host) or "gitlab.com")))
    else:
        print_team_summary(cfg)
        cfg.tickets = setup_redmine_token(cfg.tickets)
    if not st.which("glab"):
        bad("glab (GitLab CLI) not found — install: macOS `brew install glab`, Windows `winget install GLab.GLab`; then run setup again.")
        return 1
    if st.gitlab_login(cfg.repo.host):
        ok(f"GitLab login ({cfg.repo.host})")
    else:
        bad(f"GitLab login ({cfg.repo.host})")
        print(GITLAB_TOKEN_HINT.format(host=cfg.repo.host))

    if advanced:
        cfg.marketplace = ask("\navflow plugin marketplace (git URL)", cfg.marketplace or DEFAULT_MARKETPLACE)
    else:
        cfg.marketplace = cfg.marketplace or DEFAULT_MARKETPLACE

    if advanced:
        previous = cfg.workflow.profile
        keys = list(st.PROFILES)
        default = str(keys.index(previous) + 1) if previous in keys else "1"
        print("\nCoding workflow (choose one — the two are never installed together)")
        for n, k in enumerate(keys, 1):
            print(f"  {n}. {st.PROFILES[k]}")
        while True:
            v = ask("Choose", default)
            if v.isdigit() and 1 <= int(v) <= len(keys):
                cfg.workflow.profile = keys[int(v) - 1]
                break
            print("  Enter a number from the list.")
        g = ask("Enable git guardrails (block push to protected branches, force push, reset --hard, …)? y/n",
                "y" if cfg.workflow.git_guardrails else "n").lower()
        cfg.workflow.git_guardrails = g != "n"

        from .config import MODEL_CHOICES
        print("\nModels for the role subagents (" + ", ".join(MODEL_CHOICES) + ") — Enter keeps the value shown")
        for role, label in (("plan", "Plan and design"), ("implement", "Implement"), ("review", "Review")):
            while True:
                v = ask(f"  {label}", getattr(cfg.models, role)).strip().lower()
                if v in MODEL_CHOICES:
                    setattr(cfg.models, role, v)
                    break
                print("  Choose one of: " + ", ".join(MODEL_CHOICES))

        print("\nContext monitor — warns when a session's context grows large (answers become less reliable)")
        mon = ask("  Enable the context monitor? y/n", "y" if cfg.monitor.enabled else "n").lower()
        cfg.monitor.enabled = mon != "n"
        if cfg.monitor.enabled:
            for attr, label in (("warn_tokens", "Warn at (thousand tokens)"), ("critical_tokens", "Limit at (thousand tokens)")):
                while True:
                    v = ask(f"  {label}", str(getattr(cfg.monitor, attr) // 1000))
                    if v.isdigit() and int(v) > 0:
                        setattr(cfg.monitor, attr, int(v) * 1000)
                        break
                    print("  Enter a whole number, for example 300.")
            if cfg.monitor.critical_tokens <= cfg.monitor.warn_tokens:
                cfg.monitor.critical_tokens = cfg.monitor.warn_tokens + 100_000
                print(f"  Limit raised to {cfg.monitor.critical_tokens // 1000}k (it must be above the warning).")
        cfg.save()
        ok(f"Configuration saved to {CONFIG_FILE}")

    print("\nClaude Code")
    r, out = st.register_mcp()
    (ok if r else bad)("MCP server avflow-tickets registered" if r else f"MCP registration failed: {out.strip()[:200]}")
    st.merge_permissions()
    ok("Permissions: read tools allowed, write tools ask first")
    if not st.can_read_repo(cfg.marketplace):
        bad(f"Cannot read the avflow marketplace: {cfg.marketplace}")
        print("     Ask the PM for read access, then sign in to the git host (GitHub: `gh auth login` and `gh auth setup-git`), and run setup again.")
    plugins = [(cfg.marketplace, st.AVFLOW_PLUGIN, "avflow plugin (team skills)")]
    if cfg.workflow.profile == "superpowers":
        plugins.insert(0, (st.SUPERPOWERS_MARKETPLACE, st.SUPERPOWERS_PLUGIN, "Superpowers"))
        extra = [n for n in st.recorded_skills(HOME) if n not in st.POCOCK_SKILLS]
        if extra:
            ok("Removed Matt Pocock workflow skills: " + ", ".join(st.remove_skills(extra)))
    else:
        st.remove_superpowers()
        ok("Superpowers removed (workflow: Matt Pocock's skills)")
    for market, plugin, label in plugins:
        r, out = st.install_plugin(market, plugin)
        if r:
            ok(label)
        else:
            bad(f"{label}: {out.strip()[:200]}")
            print(f"     In Claude Code run: /plugin marketplace add {market}  then  /plugin install {plugin}")
    done, miss = st.install_pocock_skills(HOME / "cache", names=st.skills_for(cfg.workflow.profile))
    if done:
        ok("Matt Pocock skills: " + ", ".join(done))
    if miss:
        bad("Matt Pocock skills not found: " + ", ".join(miss))
    ok("Role subagents: " + ", ".join(st.install_agents(cfg.models)))
    try:
        st.set_monitor(cfg.monitor.enabled)
        ok("Context monitor " + (f"enabled (warn {cfg.monitor.warn_tokens // 1000}k, limit {cfg.monitor.critical_tokens // 1000}k)"
                                 if cfg.monitor.enabled else "disabled"))
    except SystemExit as e:
        bad(f"Context monitor: {e}")
    try:
        st.set_git_guard(cfg.workflow.git_guardrails)
        ok("Git guardrails " + ("enabled" if cfg.workflow.git_guardrails else "disabled"))
    except SystemExit as e:
        bad(f"Git guardrails: {e}")
    cfg.save()

    print()
    return cmd_doctor(args)


def cmd_doctor(_args) -> int:
    print("avflow check")
    failed = 0
    try:
        cfg = Config.load()
        from .config import team_version
        n = sum(len(v) if isinstance(v, dict) else 1 for v in cfg.overrides().values())
        ok(f"Configuration {CONFIG_FILE} · team settings {team_version() or 'dev'}"
           + (f" · {n} personal override(s) — see `avflow config`" if n else ""))
    except SystemExit as e:
        bad(str(e))
        return 1
    try:
        t = cfg.tickets
        me = make_adapter(t, get_secret(t.provider, t.url)).whoami()
        ok(f"{t.provider}: whoami → {me['name']} ({me['login']})")
    except (AdapterError, SystemExit) as e:
        bad(f"{cfg.tickets.provider}: {e}")
        failed += 1
    checks = [
        ("Claude Code MCP: avflow-tickets", ["claude", "mcp", "list"], st.MCP_NAME),
        (f"GitLab login ({normalize_host(cfg.repo.host)})", ["glab", "auth", "status", "--hostname", normalize_host(cfg.repo.host)], None),
        *([("Superpowers plugin", ["claude", "plugin", "list"], "superpowers")] if cfg.workflow.profile == "superpowers" else []),
        ("avflow plugin", ["claude", "plugin", "list"], "avflow"),
    ]
    for label, cmd, needle in checks:
        code, out = st.run(cmd)
        good = code == 0 and (needle is None or needle in out)
        (ok if good else bad)(label)
        failed += 0 if good else 1
    if cfg.marketplace:
        good = st.can_read_repo(cfg.marketplace)
        (ok if good else bad)("Access to the avflow marketplace")
        failed += 0 if good else 1
    failed += check_integrity()
    repo = st.github_repo_from_url(cfg.marketplace)
    if repo and st.which("gh"):
        from . import __version__ as current
        tag = st.latest_release(repo)
        if tag and st.parse_version(tag) > st.parse_version(current):
            print(f"  ➖ Update available: {tag} (installed v{current}) — run `avflow update`")
    elif repo:
        print("  ➖ GitHub CLI (gh) not installed — needed for `avflow update`")
    print(f"  ➖ Workflow: {st.PROFILES.get(cfg.workflow.profile, cfg.workflow.profile)}")
    if cfg.workflow.profile == "pocock":
        code, out = st.run(["claude", "plugin", "list"])
        if code == 0 and "superpowers" in out:
            bad("Superpowers is also installed — remove it so the two workflows are not mixed (run setup again)")
            failed += 1
    if cfg.workflow.git_guardrails:
        from .git_guard import evaluate
        good = st.git_guard_installed() and bool(evaluate("git push origin main", current=lambda _c: "feature/x"))
        (ok if good else bad)("Git guardrails hook")
        failed += 0 if good else 1
    if cfg.monitor.enabled:
        good = st.monitor_installed()
        (ok if good else bad)(f"Context monitor (warn {cfg.monitor.warn_tokens // 1000}k, limit {cfg.monitor.critical_tokens // 1000}k)")
        failed += 0 if good else 1
        from .monitor import summary
        h = summary(HOME, 7)["hits"]
        if h["warn"] or h["critical"]:
            print(f"  ➖ Last 7 days: {h['warn']} prompt(s) past the warning, {h['critical']} past the limit — see `avflow usage`")
    for name, good, detail in st.agents_status(cfg.models):
        (ok if good else bad)(f"Subagent {name}: {detail}")
        failed += 0 if good else 1
    for s in st.skills_for(cfg.workflow.profile):
        present = (st.CLAUDE_HOME / "skills" / s / "SKILL.md").exists()
        (ok if present else bad)(f"skill {s}")
        failed += 0 if present else 1
    print("\nAll good." if not failed else f"\n{failed} check(s) failed — see above.")
    return 0 if not failed else 1


def check_integrity() -> int:
    man = integrity.shipped_manifest()
    if not man.get("files"):
        print("  ➖ Plugin integrity: skipped (development build)")
        return 0
    dirs = integrity.find_installed(st.CLAUDE_HOME)
    current = [d for d in dirs if integrity.installed_version(d) == man["version"] and not integrity.is_orphaned(d)]
    stale = [d for d in dirs if d not in current]
    newer = sorted({v for d in stale if (v := integrity.installed_version(d)) and st.parse_version(v) > st.parse_version(man["version"])},
                   key=st.parse_version)
    for d in stale:
        v = integrity.installed_version(d)
        if v not in newer:
            print(f"  ➖ Old cached version v{v} ignored ({d}) — Claude Code cleans it up")
    if not current:
        if newer:
            bad(f"Plugin integrity: the plugin is v{newer[-1]} but this avflow command is v{man['version']}")
            print("       Update the command (not the plugin): avflow update"
                  "  — or, from a release file: uv tool install --force ./avflow-<version>-py3-none-any.whl")
        else:
            bad(f"Plugin integrity: avflow plugin v{man['version']} not installed")
            print("       Update the plugin: /plugin update (or /plugin uninstall avflow@avflow, then /plugin install avflow@avflow)")
        return 1
    failures = 0
    for d in current:
        r = integrity.verify(d, man)
        changed = r["modified"] + r["missing"] + r["extra"]
        if not changed:
            ok(f"Plugin integrity: v{man['version']} unchanged ({d})")
            continue
        failures += 1
        bad(f"Plugin integrity: {len(changed)} file(s) differ from release v{man['version']} ({d})")
        for k, label in (("modified", "modified"), ("missing", "missing"), ("extra", "not in release")):
            for f in r[k]:
                print(f"       {label}: {f}")
        print("       Reinstall the plugin: /plugin uninstall avflow@avflow, then /plugin install avflow@avflow")
    return failures


def cmd_update(args) -> int:
    from . import __version__ as current
    try:
        cfg = Config.load()
    except SystemExit as e:
        bad(str(e)); return 1
    repo = st.github_repo_from_url(cfg.marketplace)
    if not repo:
        bad(f"Updates need the marketplace on GitHub; current marketplace: {cfg.marketplace}")
        return 1
    if not st.which("gh"):
        bad("GitHub CLI (gh) not found — install it (macOS `brew install gh`, Windows `winget install GitHub.cli`), run `gh auth login`, then try again.")
        return 1
    tag, why = st.latest_release_detail(repo)
    if not tag:
        bad(f"Cannot get the latest release of {repo}")
        print(f"     {why}")
        return 1
    print(f"Installed: v{current} · latest release: {tag}")
    if st.parse_version(tag) <= st.parse_version(current) and not args.force:
        ok("Already up to date")
        return 0
    if args.check:
        print(f"  ➖ Update available: {tag} — run `avflow update`")
        return 0
    wheel = st.download_wheel(repo, tag, HOME / "downloads")
    if not wheel:
        bad(f"Could not download the wheel of {tag}")
        return 1
    ok(f"Downloaded {wheel.name}")
    uv = st.uv_command()
    if not uv:
        bad("uv not found — install uv and run again."); return 1
    code, out = st.run([uv, "tool", "install", "--force", str(wheel)])
    if code != 0:
        bad(f"Install failed: {out.strip()[:300]}"); return 1
    ok(f"avflow {tag} installed")
    if st.update_plugin():
        ok("avflow plugin updated")
    else:
        bad("Plugin update: run /plugin update in Claude Code (or reinstall avflow@avflow)")
    print("\nChecking with the new version:\n")
    new_cli = st.which("avflow") or "avflow"
    return st.run([new_cli, "check"], interactive=True)[0]


def cmd_config(args) -> int:
    from .config import sources, team_version
    if not CONFIG_FILE.exists():
        bad(f"{CONFIG_FILE} not found — run `avflow setup` first.")
        return 1
    if args.path:
        print(CONFIG_FILE)
        return 0
    if args.edit:
        return open_in_editor(CONFIG_FILE)
    cfg = Config.load(CONFIG_FILE)
    if args.reset:
        cfg = Config.team()
        cfg.save(CONFIG_FILE)
        ok("Personal overrides removed — the team settings apply. Run `avflow setup` to apply them to Claude Code.")
        return 0
    src = sources(CONFIG_FILE)
    print(f"avflow configuration — team settings from release {team_version() or 'dev'}, personal overrides in {CONFIG_FILE}\n")
    d = cfg.to_dict()
    print(f"marketplace = {d['marketplace']}  ({src['marketplace']})")
    for sec in Config.SECTIONS:
        print(f"\n[{sec}]")
        for k, v in d[sec].items():
            mark = "  ← personal" if src.get(f"{sec}.{k}") == "personal" else ""
            print(f"  {k} = {v}{mark}")
    try:
        get_secret(cfg.tickets.provider, cfg.tickets.url)
        stored = "yes"
    except SystemExit:
        stored = "no — run `avflow setup`"
    print(f"\nToken stored in the OS keyring for {cfg.tickets.url}: {stored}")
    print("\nPersonal values (← personal) override the team settings. `avflow config --edit` to change them,")
    print("`avflow config --reset` to go back to the team settings; then run `avflow setup`.")
    return 0


def open_in_editor(path, runner=None) -> int:
    import os
    runner = runner or st.run
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        cmd = [editor, str(path)]
    elif sys.platform == "win32":
        cmd = ["notepad", str(path)]
    elif sys.platform == "darwin":
        cmd = ["open", "-t", str(path)]
    else:
        cmd = ["xdg-open", str(path)]
    code, _ = runner(cmd, interactive=True)
    if code != 0:
        bad(f"Could not open an editor — edit the file yourself: {path}")
    return code


def cmd_init(args) -> int:
    from pathlib import Path

    from .init_repo import init_repo
    try:
        cfg = Config.load()
    except SystemExit:
        cfg = Config.team()
    r = init_repo(Path(args.path), args.project, args.force, cfg)
    for f in r["created"]:
        ok(f"created {f}")
    for f in r["overwritten"]:
        ok(f"overwritten {f}")
    for f in r["skipped"]:
        print(f"  ➖ kept existing {f}")
    print("\nNext: fill the TODOs in CLAUDE.md and CODEOWNERS, add terms to docs/CONTEXT.md, "
          "and set REDMINE_URL / REDMINE_CI_API_KEY in the GitLab CI/CD variables.")
    return 0


def _risk_root(path: str):
    from pathlib import Path

    from .tickets.repo import GitRepo
    return GitRepo(path).root() or Path(path)


def cmd_risk_check(args) -> int:
    from datetime import date

    from . import risk
    root = _risk_root(args.path)
    p = risk.load(root)
    if p is None:
        bad(f"No {risk.PROFILE.as_posix()} in {root} — `avflow init` adds one with examples.")
        return 1
    for w in p.warnings:
        print(f"  ⚠️  {w}")
    if p.problems:
        for x in p.problems:
            bad(x)
        return 1
    ok(f"{risk.PROFILE.as_posix()}: {len(p.areas)} risk areas" + (f" ({p.name})" if p.name else ""))
    for a in p.areas:
        where = ", ".join(a.paths) if a.paths else "no paths yet — recognised only when a ticket names it"
        print(f"  • {a.name}: {', '.join(a.checks)}" + (f" · owners {', '.join(a.owners)}" if a.owners else ""))
        print(f"      paths: {where}")
    other = risk.BUILTIN_OTHER if p.other_checks is None else p.other_checks
    print(f"  • {risk.OTHER} (ticket): {', '.join(other) or 'standard flow'}"
          + ("  [avflow default]" if p.other_checks is None else ""))
    if p.default_checks:
        if p.default_until and date.today() > p.default_until:
            print(f"  • Strict default ended on {p.default_until.isoformat()} — remove [risk.default] or move its date.")
        else:
            print(f"  • Strict default for changes outside every area: {', '.join(p.default_checks)}"
                  + (f" until {p.default_until.isoformat()}" if p.default_until else ""))
    return 0


def cmd_risk_files(args) -> int:
    from . import risk
    root = _risk_root(args.path)
    p = risk.load(root)
    if p is not None and p.problems:
        bad(f"{risk.PROFILE.as_posix()} has problems — run `avflow risk check`.")
        return 1
    r = risk.requirements(p, args.area or [], args.files)
    for w in r.warnings:
        print(f"  ⚠️  {w}")
    print("Risk areas: " + (", ".join(f"{k} ({v})" for k, v in r.areas.items()) or "none"))
    for a, fs in r.files.items():
        print(f"  {a}: {', '.join(fs)}")
    if r.default_applied:
        print("  (strict default [risk.default] applies: no area matched)")
    if r.checks:
        print("Required checks:")
        for c in r.checks:
            print(f"  - {risk.describe(c)}")
    else:
        print("Required checks: none — standard flow (tests, green pipeline, a person's review).")
    if r.gaps:
        print("Profile gaps (files of a high-risk ticket outside every area):")
        for g in r.gaps:
            print(f"  - {g}")
    return 0


def _ticket_adapter():
    cfg = Config.load()
    t = cfg.tickets
    return cfg, make_adapter(t, get_secret(t.provider, t.url))


def cmd_release_notes(args) -> int:
    from . import release_notes as rn
    cfg, adapter = _ticket_adapter()
    commits = rn.commits_in_range(args.from_ref, args.to_ref, args.repo)
    text = rn.build(commits, rn.collect(adapter, commits), cfg.tickets.blocker_done, args.from_ref, args.to_ref)
    return _emit(text, args.out)


def cmd_report(args) -> int:
    from .report import build_report
    cfg, adapter = _ticket_adapter()
    project = args.project or cfg.tickets.project
    if not project:
        bad("Give the project identifier: avflow report --project <identifier> (or set `project` under [tickets] with avflow config --edit).")
        return 1
    return _emit(build_report(adapter, cfg.tickets, project, args.days), args.out)


def cmd_usage(args) -> int:
    from .monitor import summary
    s = summary(HOME, args.days)
    try:
        mon = Config.load().monitor
        print(f"Context monitor: warn {mon.warn_tokens // 1000}k · limit {mon.critical_tokens // 1000}k · "
              f"{'enabled' if mon.enabled else 'disabled'}\n")
    except SystemExit:
        pass
    print(f"Last {args.days} days\n\nSessions (orchestrator), largest context first:")
    rows = sorted(s["sessions"].items(), key=lambda kv: kv[1]["peak"], reverse=True)[:15]
    for sid, v in rows:
        print(f"  {v['last'][:16]}  peak {v['peak'] // 1000:>5}k  {v['model'] or '?':<28} {sid[:8]}")
    if not rows:
        print("  (no data yet)")
    print("\nSubagents:")
    for (agent, model), v in sorted(s["agents"].items()):
        print(f"  {agent:<22} {model:<28} {v['calls']:>3} call(s)  peak {v['peak'] // 1000}k")
    if not s["agents"]:
        print("  (no data yet)")
    print(f"\nPrompts past the warning: {s['hits']['warn']} · past the limit: {s['hits']['critical']}")
    return 0


def _emit(text: str, out: str | None) -> int:
    if out:
        from pathlib import Path
        Path(out).write_text(text, encoding="utf-8")
        ok(f"written to {out}")
    else:
        print(text)
    return 0


def cmd_uninstall(_args) -> int:
    try:
        cfg = Config.load()
        delete_secret(cfg.tickets.provider, cfg.tickets.url)
        ok("Token removed from the keyring")
    except SystemExit:
        pass
    st.run(["claude", "mcp", "remove", st.MCP_NAME, "--scope", "user"])
    ok("MCP server avflow-tickets removed")
    st.run(["claude", "plugin", "uninstall", st.AVFLOW_PLUGIN])
    removed = st.remove_skills(st.recorded_skills(HOME) or list(st.POCOCK_SKILLS))
    if removed:
        ok("Matt Pocock skills removed: " + ", ".join(removed))
    try:
        st.set_monitor(False)
        ok("Context monitor removed")
    except SystemExit:
        pass
    removed_agents = st.remove_agents()
    if removed_agents:
        ok("Role subagents removed: " + ", ".join(removed_agents))
    try:
        st.set_git_guard(False)
        ok("Git guardrails hook removed")
    except SystemExit:
        pass
    ok("avflow plugin removed (Superpowers and other plugins are kept)")
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        ok(f"{CONFIG_FILE} removed")
    print("Finally: `uv tool uninstall avflow`.")
    return 0


def _utf8_output() -> None:
    """✅/❌ must not crash a Windows console or a captured (cp1252) output stream."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_output()
    p = argparse.ArgumentParser(prog="avflow", description="Set up the team's AI coding workflow.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("setup", help="enter your tokens and configure Claude Code with the team settings")
    sp.add_argument("--advanced", action="store_true", help="also ask every team setting (saved as your personal overrides)")
    sp.set_defaults(fn=cmd_setup)
    sub.add_parser("check", aliases=["doctor"], help="check that everything works (alias: doctor)").set_defaults(fn=cmd_doctor)
    it = sub.add_parser("init", help="add the team's standard files to a project repository")
    it.add_argument("--path", default=".", help="repository folder (default: current folder)")
    it.add_argument("--project", help="project name used in the templates (default: folder name)")
    it.add_argument("--force", action="store_true", help="overwrite existing files")
    it.set_defaults(fn=cmd_init)
    rn = sub.add_parser("release-notes", help="release notes from the tickets referenced in a commit range")
    rn.add_argument("--from", dest="from_ref", required=True, help="previous release tag or commit")
    rn.add_argument("--to", dest="to_ref", default="HEAD", help="commit to release (default: HEAD)")
    rn.add_argument("--repo", default=".", help="repository folder (default: current folder)")
    rn.add_argument("--out", help="write to this file instead of printing")
    rn.set_defaults(fn=cmd_release_notes)
    rp = sub.add_parser("report", help="weekly PM report from the ticket system and GitLab (read-only)")
    rp.add_argument("--project", help="ticket-system project identifier")
    rp.add_argument("--days", type=int, default=7, help="length of the period (default: 7)")
    rp.add_argument("--out", help="write to this file instead of printing")
    rp.set_defaults(fn=cmd_report)
    rk = sub.add_parser("risk", help="the project's risk profile (.avflow/project.toml)")
    rks = rk.add_subparsers(dest="risk_cmd", required=True)
    rc = rks.add_parser("check", help="validate the profile and list its risk areas")
    rc.add_argument("--path", default=".", help="repository folder (default: current folder)")
    rc.set_defaults(fn=cmd_risk_check)
    rf = rks.add_parser("files", help="which risk areas and checks apply to these files")
    rf.add_argument("files", nargs="+", help="paths relative to the repository root")
    rf.add_argument("--area", action="append", help="the ticket's risk area (repeatable; 'Other high risk' allowed)")
    rf.add_argument("--path", default=".", help="repository folder (default: current folder)")
    rf.set_defaults(fn=cmd_risk_files)
    us = sub.add_parser("usage", help="context size per session and subagent calls (from the context monitor)")
    us.add_argument("--days", type=int, default=7)
    us.set_defaults(fn=cmd_usage)
    cf = sub.add_parser("config", help="show the configuration (no token); --edit to open it")
    cf.add_argument("--edit", action="store_true", help="open the configuration file in an editor")
    cf.add_argument("--path", action="store_true", help="print the path of the configuration file")
    cf.add_argument("--reset", action="store_true", help="remove your personal overrides and use the team settings")
    cf.set_defaults(fn=cmd_config)
    up = sub.add_parser("update", help="install the latest release and update the plugin")
    up.add_argument("--check", action="store_true", help="only report whether an update is available")
    up.add_argument("--force", action="store_true", help="reinstall even if already up to date")
    up.set_defaults(fn=cmd_update)
    sub.add_parser("uninstall", help="remove avflow configuration").set_defaults(fn=cmd_uninstall)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
