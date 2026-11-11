#!/bin/sh
# reset-avflow.sh — remove avflow (and the older kickoff-kit / htkm-kit / redmine-agent installs) from this Mac,
# so that the next install behaves like a first install.
#
# Keeps: git, uv, gh, glab, Claude Code, and your GitHub / GitLab logins (unless --logout-gitlab).
# Usage:
#   ./reset-avflow.sh                     # asks for confirmation
#   ./reset-avflow.sh --yes               # no confirmation
#   ./reset-avflow.sh --keep-superpowers  # keep the Superpowers plugin
#   ./reset-avflow.sh --logout-gitlab=gitlab.enclave.vn   # also sign glab out of that host

YES=0; KEEP_SP=0; GL_HOST=""
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --keep-superpowers) KEEP_SP=1 ;;
    --logout-gitlab=*) GL_HOST="${a#--logout-gitlab=}" ;;
    *) echo "Unknown option: $a"; exit 2 ;;
  esac
done

if [ "$YES" -ne 1 ]; then
  printf "This removes avflow, its token, plugin, MCP server, skills and settings entries. Continue? [y/N] "
  read ans; case "$ans" in y|Y) ;; *) echo "Cancelled."; exit 0 ;; esac
fi

step() { printf "\n== %s\n" "$1"; }
quiet() { "$@" >/dev/null 2>&1 || true; }

step "avflow's own uninstall"
command -v avflow >/dev/null 2>&1 && quiet avflow uninstall
command -v kickoff-kit >/dev/null 2>&1 && quiet kickoff-kit uninstall
command -v htkm-kit    >/dev/null 2>&1 && quiet htkm-kit uninstall

step "Command-line tools (uv)"
for t in avflow kickoff-kit htkm-kit redmine-agent-mcp; do quiet uv tool uninstall "$t"; done

step "Claude Code plugins and marketplaces"
quiet claude plugin uninstall avflow@avflow
quiet claude plugin uninstall kickoff-kit@kickoff-kit
quiet claude plugin uninstall htkm-kit@htkm-kit
quiet claude plugin marketplace remove avflow
quiet claude plugin marketplace remove kickoff-kit
quiet claude plugin marketplace remove htkm-kit
if [ "$KEEP_SP" -ne 1 ]; then
  quiet claude plugin uninstall superpowers@superpowers-marketplace
  quiet claude plugin marketplace remove superpowers-marketplace
fi

step "Claude Code MCP servers"
for m in avflow-tickets kickoff-tickets htkm-tickets redmine-agent; do quiet claude mcp remove "$m" --scope user; done

step "Skills, configuration and caches"
rm -f "$HOME/.claude/agents/avflow-planner.md" "$HOME/.claude/agents/avflow-implementer.md" "$HOME/.claude/agents/avflow-reviewer.md"
for sk in handoff zoom-out grill-with-docs implement tdd diagnosing-bugs code-review prototype research codebase-design improve-codebase-architecture pr retro; do rm -rf "$HOME/.claude/skills/$sk"; done
rm -rf "$HOME/.avflow" "$HOME/.kickoff-kit" "$HOME/.htkm-kit" "$HOME/.redmine-agent-mcp"
rm -rf "$HOME/.claude/plugins/cache/avflow" "$HOME/.claude/plugins/marketplaces/avflow"
rm -rf "$HOME/.claude/plugins/cache/kickoff-kit" "$HOME/.claude/plugins/marketplaces/kickoff-kit"
rm -rf "$HOME/.claude/plugins/cache/htkm-kit" "$HOME/.claude/plugins/marketplaces/htkm-kit"
if [ "$KEEP_SP" -ne 1 ]; then
  rm -rf "$HOME/.claude/plugins/cache/superpowers-marketplace" "$HOME/.claude/plugins/marketplaces/superpowers-marketplace"
fi

step "Permission and hook entries in ~/.claude/settings.json"
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path.home() / ".claude" / "settings.json"
if p.exists():
    try:
        d = json.loads(p.read_text())
    except ValueError:
        print("settings.json is not valid JSON — left unchanged"); raise SystemExit
    markers = ("avflow-git-guard", "kickoff-git-guard", "avflow-monitor")
    hooks = d.get("hooks", {})
    for ev in list(hooks):
        kept = []
        for e in hooks[ev]:
            hs = [h for h in e.get("hooks", []) if not any(m in str(h.get("command", "")) for m in markers)]
            if hs:
                kept.append({**e, "hooks": hs})
        if kept: hooks[ev] = kept
        else: hooks.pop(ev)
    if "hooks" in d and not d["hooks"]:
        d.pop("hooks")
    perms = d.get("permissions", {})
    for k in ("allow", "ask", "deny"):
        if k in perms:
            perms[k] = [x for x in perms[k] if not x.startswith(("mcp__avflow-tickets__", "mcp__kickoff-tickets__", "mcp__htkm-tickets__", "mcp__redmine-agent__"))]
    p.write_text(json.dumps(d, indent=2) + "\n")
    print("cleaned")
else:
    print("no settings.json")
EOF
rm -f "$HOME/.claude/settings.json.avflow-backup" "$HOME/.claude/settings.json.kickoff-backup" "$HOME/.claude/settings.json.htkm-backup"

step "Keychain entries"
for svc in avflow kickoff-kit htkm-kit; do
  n=0
  while security delete-generic-password -s "$svc" >/dev/null 2>&1; do n=$((n+1)); done
  echo "$svc: $n removed"
done

if [ -n "$GL_HOST" ]; then
  step "GitLab sign-out ($GL_HOST)"
  quiet glab auth logout --hostname "$GL_HOST"
fi

step "Check"
fail=0
for c in avflow kickoff-kit htkm-kit redmine-agent-mcp; do
  if command -v "$c" >/dev/null 2>&1; then echo "  still present: $c"; fail=1; fi
done
if claude mcp list 2>/dev/null | grep -Eq "avflow-tickets|kickoff-tickets|htkm-tickets|redmine-agent"; then echo "  MCP server still registered"; fail=1; fi
if claude plugin list 2>/dev/null | grep -Eq "avflow|kickoff-kit|htkm-kit"; then echo "  plugin still installed (remove it with /plugin in Claude Code)"; fail=1; fi
[ -d "$HOME/.claude/skills/handoff" ] && { echo "  skill handoff still present"; fail=1; }
if [ "$fail" -eq 0 ]; then echo "  ✅ Clean — ready for a first install."; else echo "  ❌ Some items remain (see above)."; fi
echo "\nRestart Claude Code before installing again."
