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

import fnmatch
import json
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


def evaluate(command: str, protected: list[str] | None = None, cwd: str | None = None, current=_current_branch,
             diff_provider=_staged_diff) -> str | None:
    """Reason to block, or None to allow."""
    protected = protected or DEFAULT_PROTECTED
    for segment in SEPARATORS.split(command or ""):
        tokens = _tokens(segment.strip())
        args = _git_args(tokens)
        if args is not None:
            reason = check_git(args, protected, cwd, current, diff_provider)
            if reason:
                return reason
        forge = _program(tokens, ("gh", "glab"))
        if forge is not None:
            reason = check_forge(*forge)
            if reason:
                return reason
    return None


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    protected = DEFAULT_PROTECTED
    try:
        from .config import Config
        protected = Config.load().workflow.protected_branches or DEFAULT_PROTECTED
    except (SystemExit, Exception):
        pass
    reason = evaluate(command, protected, data.get("cwd"))
    if reason:
        sys.stderr.write(f"BLOCKED by avflow git guardrails: {reason}. "
                         "You do not have authority to run this command. Do not work around it; tell the person.\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
