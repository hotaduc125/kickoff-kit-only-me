"""The guardrails see through nested commands, wrappers and aliases, and block reading stored credentials.

A rule the agent can bypass by writing `bash -c "…"` or an alias is not a rule. These tests cover the ways one
command runs another: shells, interpreters (`python -c`, `node -e`), wrappers (`env`, `sudo`, `xargs`, …),
substitutions and subshells, git / gh / glab aliases. And the ways the agent could read a token that avflow keeps in
the OS keyring (then call the ticket system around the avflow-tickets rules).
"""
import base64
import json
import subprocess
import sys

import pytest

from avflow.git_guard import evaluate


def ON_FEATURE(_cwd):
    return "feature/12-x"


ALIASES = {
    ("git", "p"): "push --force",
    ("git", "pm"): "push origin main",
    ("git", "sh"): "!git push origin main",
    ("git", "chain"): "pm",
    ("git", "st"): "status",
    ("gh", "pm"): "pr merge",
    ("gh", "shell"): "!gh pr merge 2",
    ("glab", "ok"): "mr approve",
}


def aliases(prog, name, _cwd):
    return ALIASES.get((prog, name))


def blocked(cmd):
    return evaluate(cmd, current=ON_FEATURE, alias_provider=aliases)


NESTED_BLOCKED = [
    # shells
    'bash -c "git push origin main"',
    "sh -c 'git push --force'",
    "zsh -c 'git reset --hard'",
    'bash -lc "cd x && git push origin main"',
    "/bin/bash -c 'gh pr merge 2'",
    'bash -c "bash -c \'git push origin main\'"',
    "echo 'git push origin main' | bash",
    "printf 'git push origin main' | sh",
    'cmd /c "git push origin main"',
    'cmd.exe /C git push origin main',
    # PowerShell
    'pwsh -c "git push origin main"',
    'pwsh -Command "git push origin main"',
    'powershell -command "& git push origin main"',
    'powershell.exe -NoProfile -Command "git push origin main; exit"',
    "pwsh -EncodedCommand " + base64.b64encode("git push origin main".encode("utf-16-le")).decode(),
    # interpreters
    "python3 -c \"import os; os.system('git push origin main')\"",
    "python -c \"import subprocess; subprocess.run(['git', 'push', 'origin', 'main'])\"",
    "python3.12 -c \"import subprocess as s; s.call('gh pr merge 2', shell=True)\"",
    "node -e \"require('child_process').execSync('git push origin main')\"",
    "node -e \"require('child_process').spawnSync('glab', ['mr', 'merge', '87'])\"",
    "ruby -e 'system(\"git push --force\")'",
    "perl -e 'system(\"git reset --hard\")'",
    "osascript -e 'do shell script \"git push origin main\"'",
    # eval, wrappers
    'eval "git push origin main"',
    "eval git push --force",
    "env git push origin main",
    "env -i PATH=/usr/bin git push origin main",
    "sudo git push origin main",
    "sudo -u build git push --force",
    "command git push origin main",
    "exec git push origin main",
    "nohup git push origin main",
    "time git push origin main",
    "nice -n 10 git push origin main",
    "timeout 30 git push origin main",
    "echo main | xargs git push origin",
    "xargs -I{} git push --force origin {}",
    "echo x | xargs -n 1 gh pr merge",
    # subshells, groups, substitutions, control flow
    "(git push origin main)",
    "( cd repo; git push origin main )",
    "{ git push origin main; }",
    "echo $(git push origin main)",
    'x="$(git push origin main)"',
    "echo `git push origin main`",
    'echo "`gh pr merge 2`"',
    "diff <(git push origin main) x",
    "if git push origin main; then echo ok; fi",
    "true && git push origin main &",
    "git status\ngit push origin main",
    "! git reset --hard",
    # aliases
    "git -c alias.p='push --force' p",
    "git -c alias.x='!git push origin main' x",
    "git -c Alias.X='push --force' x",
    "git p",
    "git pm",
    "git sh",
    "git chain",
    "gh pm 2",
    "gh shell",
    "glab ok 87",
    'bash -c "git p"',
]

NESTED_ALLOWED = [
    'bash -c "git status"',
    "bash -c 'npm test'",
    "bash scripts/build.sh",
    "sh -c 'git push origin feature/12-x'",
    "python3 -c \"print('hello')\"",
    "python3 -c \"import json; print(json.dumps({'a': 1}))\"",
    "node -e \"console.log(1 + 1)\"",
    'pwsh -c "Get-ChildItem"',
    "env FOO=1 npm test",
    "sudo -n true",
    "command -v git",
    "echo main | xargs git log",
    "(cd repo && git status)",
    "echo $(git rev-parse --abbrev-ref HEAD)",
    "git st",
    "git log --oneline -5",
    "git push origin feature/12-x 2>&1",
    "git push -u origin feature/12-x 2>&1 | tail -5",
    "git fetch origin && git rebase origin/develop",
    "time pytest -q",
    "nohup npm run dev > /tmp/x.log 2>&1 &",
    "for f in a b; do echo $f; done",
    "git commit -m \"$(cat <<'EOF'\nFix the build\n\ngit push origin main is blocked by the guard\nEOF\n)\"",
    "cat <<EOF > notes.txt\nrun git push origin main later\nEOF",
    "gh pr view 2",
    "gh unknown-alias 2",
    "echo 'bash -c \"git push origin main\"' >> docs/notes.md",
]


@pytest.mark.parametrize("cmd", NESTED_BLOCKED)
def test_nested_blocked(cmd):
    assert blocked(cmd), cmd


@pytest.mark.parametrize("cmd", NESTED_ALLOWED)
def test_nested_allowed(cmd):
    assert blocked(cmd) is None, cmd


def test_nested_reason_names_the_inner_rule():
    assert "protected branch 'main'" in blocked('bash -c "git push origin main"')
    assert "--force" in blocked("git -c alias.p='push --force' p")


def nest(cmd, levels):
    for _ in range(levels):
        cmd = "bash -c " + json.dumps(cmd)
    return cmd


def test_four_levels_deep_is_still_seen():
    assert blocked(nest("git push origin main", 4))


def test_deep_nesting_stops_without_crashing():
    assert evaluate(nest("git status", 8), current=ON_FEATURE, alias_provider=aliases) is None


def test_alias_loop_stops():
    loop = {("git", "a"): "b", ("git", "b"): "a"}
    assert evaluate("git a", current=ON_FEATURE, alias_provider=lambda p, n, c: loop.get((p, n))) is None


def test_builtin_commands_never_look_up_aliases():
    asked = []
    evaluate("git status && git push origin feature/x && gh pr view 2", current=ON_FEATURE,
             alias_provider=lambda p, n, c: asked.append((p, n)))
    assert asked == []


def test_unknown_subcommand_looks_up_alias_in_the_repository():
    asked = []
    evaluate("git -C repo fancy", cwd="/w", current=ON_FEATURE, alias_provider=lambda p, n, c: asked.append((p, n, c)))
    assert asked == [("git", "fancy", "/w/repo")]


def test_real_git_alias_is_resolved(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "alias.pf", "push --force"], check=True)
    assert evaluate("git pf", cwd=str(tmp_path), current=ON_FEATURE)
    assert evaluate("git nosuchalias", cwd=str(tmp_path), current=ON_FEATURE) is None


# ---------- stored credentials (item 7)
KEYRING_BLOCKED = [
    "security find-generic-password -s avflow -w",
    "security find-generic-password -a x -g",
    "/usr/bin/security find-internet-password -s redmine.example",
    "security dump-keychain",
    "security dump-keychain -d login.keychain",
    "security export -k login.keychain -t identities",
    "cmdkey /list",
    "cmdkey.exe /list:avflow*",
    "vaultcmd /listcreds:\"Windows Credentials\"",
    "secret-tool lookup service avflow",
    "secret-tool search --all service avflow",
    "keyring get avflow redmine:https://r.example",
    "python3 -m keyring get avflow x",
    "python3 -c \"import keyring; print(keyring.get_password('avflow', 'x'))\"",
    "python -c 'from avflow.config import get_secret; print(get_secret(\"redmine\", \"u\"))'",
    "node -e \"require('keytar').getPassword('avflow', 'x')\"",
    'pwsh -c "Get-StoredCredential -Target avflow"',
    'powershell -Command "[Windows.Security.Credentials.PasswordVault]::new().RetrieveAll()"',
    "Get-StoredCredential -Target avflow",
    "git credential fill",
    "printf 'host=gitlab.example\\n' | git credential fill",
    "git credential-osxkeychain get",
    "gh auth token",
    "gh auth status --show-token",
    "glab auth status -t",
    "glab config get token --host gitlab.example",
    'bash -c "security find-generic-password -s avflow -w"',
    "TOKEN=$(security find-generic-password -s avflow -w) && curl -H \"X-Redmine-API-Key: $TOKEN\" https://r.example/issues/1.json",
    "curl -H 'X-Redmine-API-Key: abc' -X PUT https://r.example/issues/1.json -d @x.json",
    "Invoke-RestMethod -Headers @{'X-Redmine-API-Key'=$k} -Uri https://r.example/issues.json",
]

KEYRING_ALLOWED = [
    "security list-keychains",
    "security find-certificate -a",
    "gh auth status",
    "glab auth status",
    "glab config get host",
    "git credential-cache exit",
    "grep -rn keyring src/",
    "pip install keyring",
    "curl -s https://r.example/projects.json",
    "python3 -c \"import json; print(1)\"",
]


@pytest.mark.parametrize("cmd", KEYRING_BLOCKED)
def test_credential_reads_blocked(cmd):
    reason = blocked(cmd)
    assert reason and ("credential" in reason or "API key" in reason), cmd


@pytest.mark.parametrize("cmd", KEYRING_ALLOWED)
def test_credential_harmless_allowed(cmd):
    assert blocked(cmd) is None, cmd


# ---------- the hook itself never crashes Claude Code
@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_input": null}', '{"tool_input": {"command": 5}}',
                                   json.dumps({"tool_input": {"command": "bash -c 'git status"}})])
def test_hook_allows_unexpected_input(stdin):
    p = subprocess.run([sys.executable, "-m", "avflow.git_guard"], input=stdin, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_hook_blocks_nested_push():
    stdin = json.dumps({"tool_input": {"command": "bash -c 'git push --force'"}})
    p = subprocess.run([sys.executable, "-m", "avflow.git_guard"], input=stdin, capture_output=True, text=True)
    assert p.returncode == 2 and "BLOCKED" in p.stderr
