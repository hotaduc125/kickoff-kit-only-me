"""avflow git guardrails — a Claude Code PreToolUse hook for the Bash tool.

Blocks dangerous git commands before they run, while still allowing the team workflow
(the agent pushes its own feature branch and opens a merge request).

Idea from Matt Pocock's git-guardrails-claude-code skill (MIT licence), adapted:
- feature-branch pushes are allowed; pushes to protected branches, force pushes,
  remote deletions and tag pushes are blocked;
- written in Python so it runs on macOS and Windows.

The forge CLIs are covered too (gh, glab — the agent runs them as the person): merging, approving, and deleting a
repository, release, branch or branch protection are blocked, including through `gh api` / `glab api`. An approval
made by the agent would count as the person's own and could satisfy a code-owner check unseen. This is a guard
against mistakes and injected instructions, not a security boundary: the CI gate and GitLab settings enforce.

Protocol: JSON on stdin ({"tool_input": {"command": ...}, "cwd": ...}); exit 2 with a
message on stderr blocks the command and shows the message to Claude; exit 0 allows it.
"""
from __future__ import annotations

import base64
import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

DEFAULT_PROTECTED = ["main", "master", "develop", "release/*"]

# ---- secret scanning for `git commit`
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("hard-coded secret", re.compile(
        r"(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|pwd)[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_\-/+=.]{16,})[\"']")),
    ("secret in .NET config", re.compile(
        r"(?i)key\s*=\s*[\"'][^\"']*(?:key|secret|token|passw(?:or)?d|pwd)[^\"']*[\"']\s+value\s*=\s*[\"']([^\"']{16,})[\"']")),
    ("40-hex API key", re.compile(r"(?i)(?:api[_-]?key|key|token)\W{1,4}([0-9a-f]{40})\b")),
]
SENSITIVE_FILES = re.compile(r"(?i)(^|/)(\.env(\..*)?|id_rsa[^/]*|id_ed25519[^/]*|[^/]*\.(pem|p12|pfx|keystore|jks))$")
SEPARATORS = re.compile(r"&&|\|\||;|\||\n")


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def _program(tokens: list[str], names: tuple[str, ...]) -> tuple[str, list[str]] | None:
    """(program, arguments) when the segment runs one of `names` (after env assignments), else None."""
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    if i >= len(tokens):
        return None
    prog = tokens[i].rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    prog = prog[:-4] if prog.endswith(".exe") else prog
    return (prog, tokens[i + 1:]) if prog in names else None


# ---- forge CLIs (gh, glab)
MERGE = "merging a merge request is a person's decision — leave it to the person"
APPROVE = ("approving a merge request is a person's decision — an approval through gh / glab counts as the person's "
           "own (it could satisfy a code-owner check without them seeing the change)")
DELETE = "deleting a repository, release, branch or branch protection through gh / glab is not allowed"
_API_VALUE_FLAGS = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "-H", "--header", "--input", "-q", "--jq",
                    "-t", "--template", "--hostname", "-p", "--preview", "--cache"}


def _api_call(rest: list[str]) -> tuple[str, str, list[str]]:
    """(method, path, fields) of a `gh api` / `glab api` call; GET by default, POST when fields are given."""
    method, path, fields, j = None, "", [], 0
    while j < len(rest):
        a = rest[j]
        if a.startswith("--method="):
            method = a.split("=", 1)[1]
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:]
        elif a in _API_VALUE_FLAGS and j + 1 < len(rest):
            if a in ("-X", "--method"):
                method = rest[j + 1]
            elif a in ("-f", "-F", "--field", "--raw-field"):
                fields.append(rest[j + 1])
            j += 1
        elif a.startswith(("--field=", "--raw-field=")):
            fields.append(a.split("=", 1)[1])
        elif not a.startswith("-") and not path:
            path = a
        j += 1
    method = (method or ("POST" if fields else "GET")).upper()
    return method, path.lower().lstrip("/").split("?", 1)[0], fields


def check_api(rest: list[str]) -> str | None:
    method, path, fields = _api_call(rest)
    if method in ("PUT", "POST") and re.search(r"(merge_requests|pulls)/[^/]+/merge$", path):
        return MERGE
    if method == "POST" and re.search(r"merge_requests/[^/]+/approve$", path):
        return APPROVE
    if re.search(r"pulls/[^/]+/reviews$", path) and any(f.replace(" ", "").lower() == "event=approve" for f in fields):
        return APPROVE
    if method == "DELETE" and (re.search(r"repository/branches/|protected_branches|branches/.+/protection|git/refs/", path)
                               or re.fullmatch(r"repos/[^/]+/[^/]+|projects/[^/]+", path)):
        return DELETE
    return None


def check_forge(prog: str, args: list[str]) -> str | None:
    out, j = [], 0
    while j < len(args):                                   # global repo flags: -R / --repo <x>
        if args[j] in ("-R", "--repo") and j + 1 < len(args):
            j += 2
            continue
        if args[j].startswith("--repo="):
            j += 1
            continue
        out.append(args[j])
        j += 1
    if not out:
        return None
    sub, act, rest = out[0], (out[1] if len(out) > 1 else ""), out[2:]
    if sub == "api":
        return check_api(out[1:])
    if (prog, sub, act) in (("gh", "pr", "merge"), ("glab", "mr", "merge"), ("glab", "mr", "accept")):
        return MERGE
    if (prog, sub, act) == ("glab", "mr", "approve"):
        return APPROVE
    if (prog, sub, act) == ("gh", "pr", "review") and any(a in ("--approve", "-a") for a in rest):
        return APPROVE
    if sub in ("repo", "release") and act == "delete":
        return DELETE
    return None


def _git_args(tokens: list[str]) -> list[str] | None:
    """Arguments after `git` (skipping -C <dir>, -c k=v and env assignments), or None if not a git command."""
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    if i >= len(tokens) or tokens[i].rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower() not in ("git", "git.exe"):
        return None
    args = tokens[i + 1:]
    out, j = [], 0
    while j < len(args):
        if args[j] in ("-C", "-c") and j + 1 < len(args):
            j += 2
            continue
        out.append(args[j])
        j += 1
    return out


def _is_protected(branch: str, protected: list[str]) -> bool:
    b = branch.removeprefix("refs/heads/")
    return any(fnmatch.fnmatch(b, p) for p in protected)


def _current_branch(cwd: str | None) -> str | None:
    try:
        p = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd or None, capture_output=True, text=True, timeout=5)
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def check_push(args: list[str], protected: list[str], cwd: str | None, current=_current_branch) -> str | None:
    opts = [a for a in args if a.startswith("-")]
    pos = [a for a in args if not a.startswith("-")]
    for o in opts:
        if o in ("-f", "--force", "--mirror", "--all", "--tags", "-d", "--delete", "--prune") or o.startswith("--force-with-lease") or o.startswith("--force-if-includes"):
            return f"git push {o} is not allowed"
    refspecs = pos[1:]  # pos[0] is the remote
    if not refspecs:
        branch = current(cwd)
        if branch is None:
            return "cannot tell which branch would be pushed"
        refspecs = [branch]
    for r in refspecs:
        if r.startswith("+"):
            return "force push (+refspec) is not allowed"
        if r.startswith(":"):
            return "deleting a remote branch is not allowed"
        src, _, dst = r.partition(":")
        target = dst or src
        if target == "HEAD":
            target = current(cwd) or "HEAD"
        if target.startswith("refs/tags/"):
            return "pushing tags is not allowed"
        if _is_protected(target, protected):
            return f"pushing to the protected branch '{target}' is not allowed"
    return None


def _staged_diff(cwd: str | None, include_worktree: bool) -> tuple[list[str], str]:
    """(file names, unified diff with 0 context) of what the commit would contain."""
    def git(*a):
        try:
            p = subprocess.run(["git", *a], cwd=cwd or None, capture_output=True, text=True, timeout=10)
            return p.stdout if p.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""
    rng = ["HEAD"] if include_worktree else ["--cached"]
    names = [n for n in git("diff", *rng, "--name-only").splitlines() if n.strip()]
    return names, git("diff", *rng, "-U0", "--no-color")


def find_secrets(names: list[str], diff: str) -> list[str]:
    """Findings as 'file:line — kind' (values never shown)."""
    findings = [f"{n} — sensitive file type" for n in names if SENSITIVE_FILES.search(n)]
    current, line_no = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            line_no = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            for kind, rx in SECRET_PATTERNS:
                if rx.search(line[1:]):
                    findings.append(f"{current}:{line_no} — {kind}")
                    break
            line_no += 1
    return findings


def check_commit(args: list[str], cwd: str | None, diff_provider=_staged_diff) -> str | None:
    include_worktree = any(a in ("-a", "--all") or (a.startswith("-") and not a.startswith("--") and "a" in a) for a in args)
    names, diff = diff_provider(cwd, include_worktree)
    findings = find_secrets(names, diff)
    if findings:
        shown = "; ".join(findings[:5]) + (f"; and {len(findings) - 5} more" if len(findings) > 5 else "")
        return f"the commit seems to contain secrets ({shown}) — remove them; if this is a false positive, a person must commit it"
    return None


def check_git(args: list[str], protected: list[str], cwd: str | None, current=_current_branch,
              diff_provider=_staged_diff) -> str | None:
    if not args:
        return None
    cmd, rest = args[0], args[1:]
    if cmd == "commit":
        return check_commit(rest, cwd, diff_provider)
    if cmd == "push":
        return check_push(rest, protected, cwd, current)
    if cmd == "reset" and "--hard" in rest:
        return "git reset --hard is not allowed"
    if cmd == "clean" and any(a.startswith("-") and not a.startswith("--") and "f" in a or a == "--force" for a in rest):
        return "git clean -f is not allowed"
    if cmd == "branch" and ("-D" in rest or ("--delete" in rest and ("--force" in rest or "-f" in rest))):
        return "git branch -D is not allowed"
    if cmd == "checkout" and ("." in rest or ("--" in rest and rest.index("--") < len(rest) - 1)):
        return "discarding changes with git checkout is not allowed"
    if cmd == "restore" and "--staged" not in rest and any(a == "." or not a.startswith("-") for a in rest):
        return "discarding changes with git restore is not allowed"
    if cmd == "stash" and rest[:1] in (["drop"], ["clear"]):
        return f"git stash {rest[0]} is not allowed"
    if cmd in ("filter-branch", "filter-repo"):
        return f"git {cmd} is not allowed"
    return None


# ---- stored credentials: avflow keeps tokens in the OS keyring; the agent must not read them (it could then call the
# ticket system or the forge around the avflow-tickets rules)
CREDENTIALS = ("reading stored credentials (OS keyring, credential manager, CLI tokens) is not allowed — tokens stay "
               "where avflow put them; use the avflow-tickets tools, glab and gh")
REDMINE_KEY = ("calling the ticket system with an API key directly is not allowed (X-Redmine-API-Key) — use the "
               "avflow-tickets tools, which keep the ticket rules")
_SECRET_IN_CODE = re.compile(
    r"(?i)\bkeyring\b|\bget_secret\b|passwordvault|\bcredread|get-storedcredential|find-(?:generic|internet)-password"
    r"|dump-keychain|seckeychain|secret-tool|\bkeytar\b|credential\s+fill|auth\s+token")
_SECURITY_READS = {"find-generic-password", "find-internet-password", "dump-keychain", "export"}


def check_credentials(prog: str, args: list[str]) -> str | None:
    low = [a.lower() for a in args]
    if prog == "security" and low[:1] and low[0] in _SECURITY_READS:
        return CREDENTIALS
    if prog in ("cmdkey", "vaultcmd", "get-storedcredential", "get-secret"):
        return CREDENTIALS
    if prog == "secret-tool" and low[:1] and low[0] in ("lookup", "search"):
        return CREDENTIALS
    if prog == "keyring" and "get" in low:
        return CREDENTIALS
    if prog in ("gh", "glab"):
        rest = [a for a in low if not a.startswith("-")]
        if rest[:2] == ["auth", "token"] or rest[:3] == ["config", "get", "token"]:
            return CREDENTIALS
        if rest[:2] == ["auth", "status"] and any(a in ("-t", "--show-token") for a in low):
            return CREDENTIALS
    return None


# ---- the command walker: every simple command, also inside shells, interpreters, wrappers, substitutions, aliases
MAX_DEPTH = 6
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "ash", "busybox"}
_POWERSHELLS = {"pwsh", "powershell"}
_PREFIX_WORDS = {"{", "}", "!", "then", "do", "else", "elif", "if", "while", "until", "noglob", "nohup",
                 "builtin", "exec", "command", "unbuffer", "caffeinate"}
_WRAPPER_VALUE_OPTS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-U", "-r", "-t", "-D", "-R", "-T"}, "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-P", "--unset", "--chdir"}, "nice": {"-n"}, "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "xargs": {"-I", "-n", "-L", "-P", "-s", "-d", "-E", "-e", "-a", "--max-args", "--max-procs", "--delimiter"},
    "stdbuf": {"-i", "-o", "-e"}, "time": {"-f", "-o"},
}
GIT_BUILTINS = {
    "add", "am", "apply", "archive", "bisect", "blame", "branch", "bundle", "cat-file", "check-ignore", "checkout",
    "cherry", "cherry-pick", "citool", "clean", "clone", "commit", "config", "count-objects", "credential", "describe",
    "diff", "difftool", "fetch", "filter-branch", "filter-repo", "for-each-ref", "format-patch", "fsck", "gc", "grep",
    "gui", "hash-object", "help", "init", "lfs", "log", "ls-files", "ls-remote", "ls-tree", "maintenance", "merge",
    "merge-base", "mergetool", "mv", "name-rev", "notes", "prune", "pull", "push", "range-diff", "rebase", "reflog",
    "remote", "repack", "replace", "request-pull", "reset", "restore", "rev-list", "rev-parse", "revert", "rm",
    "send-email", "shortlog", "show", "show-branch", "show-ref", "sparse-checkout", "stash", "status", "submodule",
    "switch", "symbolic-ref", "tag", "update-index", "update-ref", "var", "verify-commit", "verify-tag", "version",
    "whatchanged", "worktree"}
FORGE_COMMANDS = {
    "gh": {"alias", "api", "attestation", "auth", "browse", "cache", "codespace", "completion", "config", "copilot",
           "extension", "gist", "gpg-key", "help", "issue", "label", "org", "pr", "project", "release", "repo",
           "ruleset", "run", "search", "secret", "ssh-key", "status", "variable", "workflow"},
    "glab": {"alias", "api", "auth", "changelog", "check-update", "ci", "cluster", "completion", "config", "deploy-key",
             "duo", "gpg-key", "help", "incident", "issue", "iteration", "job", "label", "mr", "opentofu", "release",
             "repo", "schedule", "securefile", "snippet", "ssh-key", "stack", "token", "user", "variable", "version"},
}
_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?^[ \t]*\2[ \t]*$", re.S | re.M)
_LITERAL = re.compile(r"'{3}(.*?)'{3}|\"{3}(.*?)\"{3}|'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`([^`]*)`", re.S)
_PUNCT = ";&|()<>\n"


def _name(token: str) -> str:
    prog = token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    return prog[:-4] if prog.endswith(".exe") else prog


def _alias(prog: str, name: str, cwd: str | None) -> str | None:
    """The expansion of a git / gh / glab alias, or None."""
    try:
        if prog == "git":
            p = subprocess.run(["git", "config", "--get", f"alias.{name}"], cwd=cwd or None, capture_output=True,
                               text=True, timeout=5)
            return (p.stdout.strip() or None) if p.returncode == 0 else None
        p = subprocess.run([prog, "alias", "list"], cwd=cwd or None, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    for line in (p.stdout or "").splitlines():
        key, sep, value = line.replace("\t", ":", 1).partition(":")
        if sep and key.strip() == name:
            return value.strip().strip("'\"") or None
    return None


def _substitutions(text: str) -> list[str]:
    """Inner text of every $( … ) and ` … ` (quoted or not: the shell runs both inside double quotes)."""
    out = [m.group(1) for m in re.finditer(r"`([^`]*)`", text)]
    i = text.find("$(")
    while i != -1:
        depth, j = 0, i + 1
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(text[i + 2:j])
        i = text.find("$(", i + 2)
    return [o for o in out if o.strip()]


def _commands(text: str) -> list[tuple[list[str], list[str] | None]]:
    """Simple commands as (tokens, tokens of the command piped into it or None). Operators and redirections removed."""
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=_PUNCT)
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return [(_tokens(seg.strip()), None) for seg in SEPARATORS.split(text)]
    out, cur, prev, piped, i = [], [], None, False, 0
    while i < len(tokens):
        t = tokens[i]
        if t and set(t) <= set(_PUNCT) and ("<" in t or ">" in t) and not set(t) & set("()\n;"):
            if cur and cur[-1].isdigit():                  # 2>&1, 2> file: drop the fd and the target
                cur.pop()
            i += 2
            continue
        if t and set(t) <= set(_PUNCT):
            if cur:
                out.append((cur, prev if piped else None))
                prev = cur
            piped, cur = t in ("|", "|&"), []
        else:
            cur.append(t)
        i += 1
    if cur:
        out.append((cur, prev if piped else None))
    return out


def _unwrap(tokens: list[str]) -> tuple[list[str], bool]:
    """Strip shell keywords, env assignments and wrappers (env, sudo, xargs, …). (command tokens, ran through xargs)."""
    xargs = False
    while tokens:
        while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens = tokens[1:]
        if not tokens:
            break
        w = _name(tokens[0])
        if w in ("command", "type", "which") and tokens[1:2] and tokens[1] in ("-v", "-V"):
            return [], False                               # `command -v git` only looks the program up
        if w in _PREFIX_WORDS:
            tokens = tokens[1:]
            continue
        if w not in _WRAPPER_VALUE_OPTS:
            break
        value_opts = _WRAPPER_VALUE_OPTS[w]
        xargs = xargs or w == "xargs"
        j = 1
        while j < len(tokens):
            a = tokens[j]
            if a == "--":
                j += 1
                break
            if w == "env" and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a):
                j += 1
                continue
            if w == "env" and a in ("-S", "--split-string") and j + 1 < len(tokens):
                tokens = tokens[:j] + _tokens(tokens[j + 1]) + tokens[j + 2:]
                continue
            if not a.startswith("-"):
                if w == "timeout":                         # the duration
                    j += 1
                break
            j += 2 if a in value_opts else 1
        tokens = tokens[j:]
    return tokens, xargs


def _shell_script(args: list[str]) -> str | None:
    """The script of `bash -c <script>` (also -lc, -ec, …); None when the shell runs a file or reads stdin."""
    for j, a in enumerate(args):
        if a.startswith("-") and not a.startswith("--") and "c" in a[1:]:
            rest = [x for x in args[j + 1:] if not x.startswith("-")]
            return rest[0] if rest else ""
        if not a.startswith(("-", "+")):
            return None
    return None


def _powershell_code(prog: str, args: list[str]) -> str | None:
    for j, a in enumerate(args):
        low = a.lower()
        if low in ("-e", "-ec", "-en", "-enc") or (low.startswith("-enc") and "-encodedcommand".startswith(low)):
            try:
                return base64.b64decode(args[j + 1]).decode("utf-16-le")
            except (IndexError, ValueError):
                return None
        if low == "-c" or (len(low) >= 4 and "-command".startswith(low)):
            return " ".join(args[j + 1:])
    if prog == "powershell":                               # Windows PowerShell: the arguments are a command by default
        return " ".join(a for a in args if not a.startswith("-")) or None
    return None


def _inline_code(prog: str, args: list[str]) -> str | None:
    """The code of `python -c`, `node -e`, `ruby -e`, `osascript -e`, … (None if the program runs a file)."""
    if re.fullmatch(r"python[0-9.]*w?|py|pypy[0-9.]*", prog):
        for j, a in enumerate(args):
            if a == "-m":
                return " ".join(args[j + 1:]) if args[j + 1:j + 2] == ["keyring"] else None
            if a.startswith("-") and not a.startswith("--") and a.endswith("c"):
                return args[j + 1] if j + 1 < len(args) else None
            if not a.startswith("-"):
                return None
        return None
    if prog == "deno" and args[:1] == ["eval"]:
        return " ".join(args[1:])
    flags = {"node": ("-e", "--eval", "-p", "--print"), "nodejs": ("-e", "--eval", "-p", "--print"),
             "bun": ("-e", "--eval", "-p", "--print"), "ruby": ("-e",), "perl": ("-e", "-E"), "php": ("-r",),
             "osascript": ("-e",)}.get(prog)
    if not flags:
        return None
    code = [args[j + 1] for j, a in enumerate(args[:-1]) if a in flags]
    return "\n".join(code) or None


class _Walk:
    def __init__(self, protected, cwd, current, diff_provider, alias_provider):
        self.protected, self.cwd, self.current = protected, cwd, current
        self.diff_provider, self.alias = diff_provider, alias_provider

    def text(self, text: str, depth: int) -> str | None:
        if depth > MAX_DEPTH or not text.strip():
            return None
        if "x-redmine-api-key" in text.lower():
            return REDMINE_KEY
        text = _HEREDOC.sub("", text)
        for inner in _substitutions(text):
            reason = self.text(inner, depth + 1)
            if reason:
                return reason
        for tokens, piped_from in _commands(text):
            reason = self.command(tokens, piped_from, depth)
            if reason:
                return reason
        return None

    def code(self, code: str, depth: int) -> str | None:
        """Inline code of an interpreter: secret access, and every string literal (and run of literals) as a command."""
        if _SECRET_IN_CODE.search(code):
            return CREDENTIALS
        lits = [next(g for g in m.groups() if g is not None) for m in _LITERAL.finditer(code)][:40]
        for k in range(len(lits)):
            for candidate in (lits[k], " ".join(lits[k:])):
                reason = self.text(candidate, depth + 1)
                if reason:
                    return reason
        return None

    def command(self, tokens: list[str], piped_from: list[str] | None, depth: int) -> str | None:
        tokens, via_xargs = _unwrap(tokens)
        if not tokens:
            return None
        echoed = piped_from[1:] if piped_from and _name(piped_from[0]) in ("echo", "printf") else None
        if via_xargs and echoed:
            tokens = tokens + " ".join(echoed).split()
        prog, args = _name(tokens[0]), tokens[1:]
        if prog in _SHELLS:
            script = _shell_script(args)
            if script is None and not [a for a in args if not a.startswith("-")] and echoed:
                script = " ".join(echoed).replace("\\n", "\n")
            return self.text(script, depth + 1) if script else None
        if prog == "cmd":
            k = next((j for j, a in enumerate(args) if a.lower() in ("/c", "/k")), None)
            return self.text(" ".join(args[k + 1:]), depth + 1) if k is not None else None
        if prog == "eval":
            return self.text(" ".join(args), depth + 1)
        if prog in _POWERSHELLS:
            code = _powershell_code(prog, args)
            return (self.code(code, depth) or self.text(code, depth + 1)) if code else None
        code = _inline_code(prog, args)
        if code is not None:
            return self.code(code, depth)
        if prog == "git":
            return self.git(args, depth, self.cwd, {})
        if prog in ("gh", "glab"):
            return check_credentials(prog, args) or self.forge(prog, args, depth)
        return check_credentials(prog, args)

    def git(self, args: list[str], depth: int, cwd: str | None, inline: dict) -> str | None:
        out, j = [], 0
        while j < len(args):                               # -C <dir>, -c key=value (alias.x=… kept as inline aliases)
            if args[j] in ("-C", "-c") and j + 1 < len(args):
                if args[j] == "-C":
                    cwd = os.path.join(cwd, args[j + 1]) if cwd else args[j + 1]
                else:
                    key, _, value = args[j + 1].partition("=")
                    if key.lower().startswith("alias."):
                        inline = {**inline, key[6:].lower(): value}
                j += 2
                continue
            out.append(args[j])
            j += 1
        if not out:
            return None
        sub = out[0]
        if (sub == "credential" and "fill" in out[1:]) or (sub.startswith("credential-") and "get" in out[1:]):
            return CREDENTIALS
        if not sub.startswith("-") and sub not in GIT_BUILTINS:
            value = inline.get(sub.lower()) if sub.lower() in inline else self.alias("git", sub, cwd)
            if value:
                if depth >= MAX_DEPTH:
                    return None
                if value.startswith("!"):
                    return self.text(value[1:] + " " + " ".join(shlex.quote(a) for a in out[1:]), depth + 1)
                return self.git(_tokens(value) + out[1:], depth + 1, cwd, inline)
        return check_git(out, self.protected, cwd, self.current, self.diff_provider)

    def forge(self, prog: str, args: list[str], depth: int) -> str | None:
        reason = check_forge(prog, args)
        if reason:
            return reason
        sub = next((a for a in args if not a.startswith("-")), None)
        if sub is None or sub in FORGE_COMMANDS[prog] or depth >= MAX_DEPTH:
            return None
        value = self.alias(prog, sub, self.cwd)
        if not value:
            return None
        rest = args[args.index(sub) + 1:]
        if value.startswith("!"):
            return self.text(value[1:] + " " + " ".join(shlex.quote(a) for a in rest), depth + 1)
        return self.forge(prog, _tokens(value) + rest, depth + 1)


def evaluate(command: str, protected: list[str] | None = None, cwd: str | None = None, current=_current_branch,
             diff_provider=_staged_diff, alias_provider=_alias) -> str | None:
    """Reason to block, or None to allow."""
    walk = _Walk(protected or DEFAULT_PROTECTED, cwd, current, diff_provider, alias_provider)
    return walk.text(command or "", 0)


def main() -> int:
    """Never crashes Claude Code: any unexpected input or error allows the command (exit 0)."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
        command = (data.get("tool_input") or {}).get("command", "")
        if not isinstance(command, str):
            return 0
        protected = DEFAULT_PROTECTED
        try:
            from .config import Config
            protected = Config.load().workflow.protected_branches or DEFAULT_PROTECTED
        except (SystemExit, Exception):
            pass
        reason = evaluate(command, protected, data.get("cwd"))
    except Exception:
        return 0
    if reason:
        sys.stderr.write(f"BLOCKED by avflow git guardrails: {reason}. "
                         "You do not have authority to run this command. Do not work around it; tell the person.\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
