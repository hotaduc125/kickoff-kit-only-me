"""kickoff-kit command line: setup · doctor · uninstall."""
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
DEFAULT_MARKETPLACE = "https://github.com/<owner>/kickoff-kit-marketplace.git"  # set at release time


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
    print("\nRedmine — your own account. The API key is under My account → API access key.")
    for attempt in range(3):
        t.url = ask("Redmine URL (base address, e.g. https://redmine.example.com/redmine)", t.url).rstrip("/")
        token = getpass.getpass("Redmine API key (hidden): ").strip()
        try:
            me = make_adapter(t, token).whoami()
        except (AdapterError, SystemExit) as e:
            bad(str(e))
            continue
        ok(f"Connected as {me['name']} ({me['login']})")
        if ask("Use the default status and field names (Ready, In progress, In review, Mode, Machine-side, Hotspot)? y/n", "y").lower() != "y":
            t.status_ready = ask("Status: ready", t.status_ready)
            t.status_in_progress = ask("Status: in progress", t.status_in_progress)
            t.status_in_review = ask("Status: in review", t.status_in_review)
            t.field_mode = ask("Field: mode", t.field_mode)
            t.field_machine_side = ask("Field: machine-side", t.field_machine_side)
            t.field_hotspot = ask("Field: hotspot", t.field_hotspot)
        set_secret("redmine", t.url, token)
        ok("API key stored in the OS keyring (not in any file)")
        return t
    raise SystemExit("Could not connect to Redmine after 3 attempts.")


def cmd_setup(_args) -> int:
    print(f"kickoff-kit {__version__} — setup\n")
    try:
        cfg = Config.load()
    except SystemExit:
        cfg = Config()

    print("Prerequisites")
    missing = [n for n in ("git", "claude") if not st.which(n)]
    for n in ("git", "claude"):
        (bad if n in missing else ok)(n)
    if missing:
        print("\nInstall the missing tools first: git (https://git-scm.com), Claude Code (https://docs.claude.com/claude-code).")
        return 1

    tp = choose("Ticket system", TICKET_CHOICES)
    if tp == "redmine":
        cfg.tickets = setup_tickets_redmine(cfg.tickets)

    rp = choose("Repository and CI/CD", REPO_CHOICES)
    cfg.repo = RepoConfig(provider=rp, host=ask("GitLab host", cfg.repo.host or "gitlab.com"))
    if not st.which("glab"):
        bad("glab (GitLab CLI) not found — install: macOS `brew install glab`, Windows `winget install GLab.GLab`; then run setup again.")
        return 1
    (ok if st.gitlab_login(cfg.repo.host) else bad)(f"GitLab login ({cfg.repo.host})")

    cfg.marketplace = ask("\nkickoff-kit plugin marketplace (git URL)", cfg.marketplace or DEFAULT_MARKETPLACE)
    cfg.save()
    ok(f"Configuration saved to {CONFIG_FILE}")

    print("\nClaude Code")
    r, out = st.register_mcp()
    (ok if r else bad)("MCP server kickoff-tickets registered" if r else f"MCP registration failed: {out.strip()[:200]}")
    st.merge_permissions()
    ok("Permissions: read tools allowed, write tools ask first")
    if not st.can_read_repo(cfg.marketplace):
        bad(f"Cannot read the kickoff-kit marketplace: {cfg.marketplace}")
        print("     Ask the PM for read access, then sign in to the git host (GitHub: `gh auth login` and `gh auth setup-git`), and run setup again.")
    for market, plugin, label in ((st.SUPERPOWERS_MARKETPLACE, st.SUPERPOWERS_PLUGIN, "Superpowers"),
                                  (cfg.marketplace, st.KICKOFF_PLUGIN, "kickoff-kit plugin (team skills)")):
        r, out = st.install_plugin(market, plugin)
        if r:
            ok(label)
        else:
            bad(f"{label}: {out.strip()[:200]}")
            print(f"     In Claude Code run: /plugin marketplace add {market}  then  /plugin install {plugin}")
    done, miss = st.install_pocock_skills(HOME / "cache")
    if done:
        ok("Matt Pocock skills: " + ", ".join(done))
    if miss:
        bad("Matt Pocock skills not found: " + ", ".join(miss))

    print()
    return cmd_doctor(_args)


def cmd_doctor(_args) -> int:
    print("kickoff-kit doctor")
    failed = 0
    try:
        cfg = Config.load()
        ok(f"Configuration {CONFIG_FILE}")
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
        ("Claude Code MCP: kickoff-tickets", ["claude", "mcp", "list"], st.MCP_NAME),
        (f"GitLab login ({cfg.repo.host})", ["glab", "auth", "status", "--hostname", cfg.repo.host], None),
        ("Superpowers plugin", ["claude", "plugin", "list"], "superpowers"),
        ("kickoff-kit plugin", ["claude", "plugin", "list"], "kickoff-kit"),
    ]
    for label, cmd, needle in checks:
        code, out = st.run(cmd)
        good = code == 0 and (needle is None or needle in out)
        (ok if good else bad)(label)
        failed += 0 if good else 1
    if cfg.marketplace:
        good = st.can_read_repo(cfg.marketplace)
        (ok if good else bad)("Access to the kickoff-kit marketplace")
        failed += 0 if good else 1
    failed += check_integrity()
    for s in st.POCOCK_SKILLS:
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
    if not dirs:
        bad("Plugin integrity: kickoff-kit plugin not found under ~/.claude/plugins")
        return 1
    failures = 0
    for d in dirs:
        r = integrity.verify(d, man)
        changed = r["modified"] + r["missing"] + r["extra"]
        if not changed:
            ok(f"Plugin integrity: v{man['version']} unchanged ({d})")
        else:
            failures += 1
            bad(f"Plugin integrity: {len(changed)} file(s) differ from release v{man['version']} ({d})")
            for k, label in (("modified", "modified"), ("missing", "missing"), ("extra", "not in release")):
                for f in r[k]:
                    print(f"       {label}: {f}")
            print("       Reinstall the plugin: /plugin uninstall kickoff-kit@kickoff-kit, then /plugin install kickoff-kit@kickoff-kit")
    return failures


def cmd_uninstall(_args) -> int:
    try:
        cfg = Config.load()
        delete_secret(cfg.tickets.provider, cfg.tickets.url)
        ok("Token removed from the keyring")
    except SystemExit:
        pass
    st.run(["claude", "mcp", "remove", st.MCP_NAME, "--scope", "user"])
    ok("MCP server kickoff-tickets removed")
    st.run(["claude", "plugin", "uninstall", st.KICKOFF_PLUGIN])
    ok("kickoff-kit plugin removed (Superpowers and other plugins are kept)")
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        ok(f"{CONFIG_FILE} removed")
    print("Finally: `uv tool uninstall kickoff-kit`.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kickoff-kit", description="Set up the team's AI coding workflow.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="choose tools, enter tokens, configure Claude Code").set_defaults(fn=cmd_setup)
    sub.add_parser("doctor", help="check that everything works").set_defaults(fn=cmd_doctor)
    sub.add_parser("uninstall", help="remove kickoff-kit configuration").set_defaults(fn=cmd_uninstall)
    a = p.parse_args(argv)
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
