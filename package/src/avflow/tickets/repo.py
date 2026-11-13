"""The project repository the agent works in: its risk profile, the files a change touches, notes on the MR.

Facts come from git and GitLab, never from the agent: the changed files are computed here.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from .. import risk
from .. import setup_steps as st

GITLAB_MR = re.compile(r"^https://([^/]+)/(.+?)(?:/-)?/merge_requests/(\d+)/?$")


class RepoError(Exception):
    """git or glab could not answer."""


class GitRepo:
    def __init__(self, cwd: str | None = None, runner=st.run):
        self.cwd, self.run = cwd or os.getcwd(), runner

    def _git(self, *args: str) -> str:
        code, out = self.run(["git", "-C", self.cwd, "-c", "core.quotepath=off", *args])
        if code != 0:
            raise RepoError(f"git {' '.join(args)} failed: {out.strip()[:300]}")
        return out

    def root(self) -> Path | None:
        try:
            return Path(self._git("rev-parse", "--show-toplevel").strip())
        except RepoError:
            return None

    def profile(self) -> risk.Profile | None:
        r = self.root()
        return risk.load_valid(r) if r else None

    def _default_base(self) -> str:
        try:
            return self._git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
        except RepoError:
            for b in ("origin/develop", "origin/main", "origin/master"):
                try:
                    self._git("rev-parse", "--verify", "--quiet", b)
                    return b
                except RepoError:
                    continue
        raise RepoError("Cannot find the target branch: give base (for example base=\"develop\").")

    def changed_files(self, base: str | None = None) -> tuple[list[str], str]:
        """Files changed by the commits on this branch since it left `base` (the MR's target branch)."""
        if self.root() is None:
            raise RepoError(f"{self.cwd} is not a git repository — run the agent in the project repository.")
        if base:
            ref = None
            for cand, full in ((f"origin/{base}", f"refs/remotes/origin/{base}"), (base, f"refs/heads/{base}")):
                try:
                    self._git("rev-parse", "--verify", "--quiet", full)
                    ref = cand
                    break
                except RepoError:
                    continue
            if ref is None:
                raise RepoError(f"'{base}' is not a branch (on origin or local): give the merge request's target branch.")
        else:
            ref = self._default_base()
        mb = self._git("merge-base", ref, "HEAD").strip()
        out = self._git("diff", "--name-only", "--no-renames", mb, "HEAD")
        return [l.strip() for l in out.splitlines() if l.strip()], ref

    @staticmethod
    def _gitlab(url: str) -> tuple[str, str, str]:
        m = GITLAB_MR.match(url.strip())
        if not m:
            raise RepoError("Only GitLab merge requests are supported (…/-/merge_requests/<n>).")
        return m.group(1), m.group(2), m.group(3)

    def mr_target(self, url: str) -> str | None:
        try:
            host, path, iid = self._gitlab(url)
        except RepoError:
            return None
        code, out = self.run(["glab", "api", "--hostname", host, f"projects/{quote(path, safe='')}/merge_requests/{iid}"])
        if code != 0:
            return None
        try:
            return json.loads(out).get("target_branch") or None
        except (ValueError, AttributeError):
            return None

    def post_mr_note(self, url: str, text: str) -> None:
        host, path, iid = self._gitlab(url)
        code, out = self.run(["glab", "api", "--hostname", host, "--method", "POST",
                              f"projects/{quote(path, safe='')}/merge_requests/{iid}/notes", "--raw-field", f"body={text}"])
        if code != 0:
            raise RepoError(f"glab could not comment on the MR: {out.strip()[:200]}")

    def mr_description(self, url: str) -> str:
        host, path, iid = self._gitlab(url)
        code, out = self.run(["glab", "api", "--hostname", host, f"projects/{quote(path, safe='')}/merge_requests/{iid}"])
        if code != 0:
            raise RepoError(f"glab could not read the MR: {out.strip()[:200]}")
        try:
            return json.loads(out).get("description") or ""
        except (ValueError, AttributeError) as e:
            raise RepoError("glab returned something that is not the MR") from e

    def set_mr_description(self, url: str, text: str) -> None:
        host, path, iid = self._gitlab(url)
        code, out = self.run(["glab", "api", "--hostname", host, "--method", "PUT",
                              f"projects/{quote(path, safe='')}/merge_requests/{iid}", "--raw-field", f"description={text}"])
        if code != 0:
            raise RepoError(f"glab could not update the MR description: {out.strip()[:200]}")
