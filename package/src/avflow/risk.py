"""The project's risk profile (`.avflow/project.toml`) and the checks a change requires.

Pure functions only (no ticket system, no git): the MCP tools and `avflow risk` call them.
avflow knows *that* something is risky; the project's profile says *what* is risky.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

PROFILE = Path(".avflow") / "project.toml"
OTHER = "Other high risk"
NONE = "None"
CHECKS = ("plan-confirmation", "independent-review", "code-owner")     # plus "checklist:<text>"
CHECKLIST = "checklist:"
BUILTIN_OTHER = ["plan-confirmation", "independent-review"]           # [risk.other] when the profile has none
AREA_KEYS = {"name", "paths", "owners", "checks"}

DESCRIPTIONS = {
    "plan-confirmation": "Plan confirmation — stop after the plan; the assignee confirms it before any code",
    "independent-review": "Independent review — two-stage review (spec, then code quality) by the avflow-reviewer "
                          "subagent in a fresh context; result posted on the MR",
    "code-owner": "Code owner approval — one of the area's owners approves the MR",
}


class ProfileError(Exception):
    """The profile cannot be used (invalid TOML or invalid content)."""


@dataclass
class Area:
    name: str
    paths: list[str] = field(default_factory=list)
    owners: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


@dataclass
class Profile:
    name: str = ""
    areas: list[Area] = field(default_factory=list)
    other_checks: list[str] | None = None          # [risk.other]; None → BUILTIN_OTHER
    default_checks: list[str] = field(default_factory=list)
    default_until: date | None = None
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def area(self, name: str) -> Area | None:
        k = key(name)
        return next((a for a in self.areas if key(a.name) == k), None)


@dataclass
class Requirements:
    checks: list[str] = field(default_factory=list)
    areas: dict[str, str] = field(default_factory=dict)          # area name → "ticket" | "files"
    files: dict[str, list[str]] = field(default_factory=dict)    # area name → matched files
    gaps: list[str] = field(default_factory=list)                # files of a high-risk ticket outside every area
    default_applied: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def high_risk(self) -> bool:
        return bool(self.areas)


def key(name: str) -> str:
    """Area names compare loosely: case, spaces and underscores do not matter."""
    return re.sub(r"[\s_]+", " ", (name or "").strip()).lower()


def is_none(name: str) -> bool:
    return key(name) in ("", "none", "no", "-", "n/a")


# ---------- paths
_GLOB_CACHE: dict[str, re.Pattern] = {}


def norm_path(p: str) -> str:
    p = str(p).replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def _glob_re(pattern: str) -> re.Pattern:
    if pattern in _GLOB_CACHE:
        return _GLOB_CACHE[pattern]
    p = norm_path(pattern)
    if p.endswith("/"):
        p += "**"
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif p.startswith("/**", i) and i + 3 == len(p):
            out += "(?:/.*)?"
            i += 3
        elif p.startswith("**", i):
            out += ".*"
            i += 2
        elif p[i] == "*":
            out += "[^/]*"
            i += 1
        elif p[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(p[i])
            i += 1
    rx = re.compile(out + r"\Z")
    _GLOB_CACHE[pattern] = rx
    return rx


def glob_match(pattern: str, path: str) -> bool:
    """Glob relative to the repository root: `*` stays within a folder, `**` crosses folders."""
    return _glob_re(pattern).match(norm_path(path)) is not None


# ---------- checks
def _check_problem(c) -> str | None:
    if not isinstance(c, str):
        return f"check {c!r} must be text"
    if c.startswith(CHECKLIST):
        return None if c[len(CHECKLIST):].strip() else "a checklist check needs its text: checklist:<what a person ticks>"
    if c not in CHECKS:
        return f"unknown check '{c}' (use {', '.join(CHECKS)} or checklist:<text>)"
    return None


def grow(prior: list[str], new: list[str]) -> list[str]:
    """Union of two check lists — checks are only ever added — in catalogue order, then checklists."""
    seen = list(dict.fromkeys([*prior, *new]))
    return [c for c in CHECKS if c in seen] + [c for c in seen if c.startswith(CHECKLIST)]


def describe(check: str) -> str:
    if check.startswith(CHECKLIST):
        return f"Checklist — a person ticks in the MR: \"{check[len(CHECKLIST):].strip()}\""
    return DESCRIPTIONS.get(check, check)


# ---------- the profile file
def parse(text: str) -> Profile:
    p = Profile()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        p.problems.append(f"not valid TOML: {e}")
        return p
    p.name = str((data.get("project") or {}).get("name", "") or "")
    r = data.get("risk") or {}
    if not isinstance(r, dict):
        p.problems.append("[risk] must be a table")
        return p
    for k in r:
        if k not in ("area", "other", "default"):
            p.warnings.append(f"[risk.{k}] is not known to this avflow version; ignored")

    def checks_of(where: str, raw, required: bool = True) -> list[str]:
        if not isinstance(raw, list):
            p.problems.append(f"{where}: checks must be a list")
            return []
        if required and not raw:
            p.problems.append(f"{where}: needs at least one check")
        for c in raw:
            if (msg := _check_problem(c)):
                p.problems.append(f"{where}: {msg}")
        return [c for c in raw if isinstance(c, str)]

    def str_list(where: str, raw, what: str) -> list[str]:
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            p.problems.append(f"{where}: {what} must be a list of text")
            return []
        return raw

    areas = r.get("area") or []
    if not isinstance(areas, list):
        p.problems.append("risk areas must be written as [[risk.area]] tables")
        areas = []
    seen: set[str] = set()
    for n, a in enumerate(areas, 1):
        if not isinstance(a, dict):
            p.problems.append(f"risk area {n}: must be a [[risk.area]] table")
            continue
        name =str(a.get("name", "") or "").strip()
        where = f"risk area {n} ('{name}')" if name else f"risk area {n}"
        if not name:
            p.problems.append(f"{where}: needs a name")
        elif key(name) in (key(OTHER), key(NONE)):
            p.problems.append(f"{where}: '{name}' is reserved for the ticket's choice; use another name")
        elif key(name) in seen:
            p.problems.append(f"{where}: the name '{name}' is used twice")
        seen.add(key(name))
        for k in a:
            if k not in AREA_KEYS:
                p.warnings.append(f"{where}: '{k}' is not known to this avflow version; ignored")
        paths = str_list(where, a.get("paths", []), "paths")
        for g in paths:
            if g.startswith("/") or g.startswith("\\") or ".." in norm_path(g).split("/") or re.match(r"^[A-Za-z]:", g):
                p.problems.append(f"{where}: path '{g}' must be relative to the repository root")
        owners = str_list(where, a.get("owners", []), "owners")
        checks = checks_of(where, a.get("checks", []))
        if "code-owner" in checks and not owners:
            p.problems.append(f"{where}: 'code-owner' needs owners (for example owners = [\"@lead\"])")
        p.areas.append(Area(name, list(paths), list(owners), checks))

    if "other" in r:
        p.other_checks = checks_of("[risk.other]", (r["other"] or {}).get("checks", []))
    if "default" in r:
        d = r["default"] or {}
        p.default_checks = checks_of("[risk.default]", d.get("checks", []))
        u = d.get("until")
        if isinstance(u, date):
            p.default_until = u
        elif isinstance(u, str):
            try:
                p.default_until = date.fromisoformat(u.strip())
            except ValueError:
                p.problems.append(f"[risk.default]: until '{u}' must be a date like 2026-12-31")
        elif u is not None:
            p.problems.append("[risk.default]: until must be a date like 2026-12-31")
    return p


def load(root: Path | str) -> Profile | None:
    """The profile of the repository at `root`, or None when it has none. Problems are in `.problems`."""
    f = Path(root) / PROFILE
    if not f.exists():
        return None
    return parse(f.read_text(encoding="utf-8"))


def ensure_valid(p: Profile | None) -> Profile | None:
    if p is not None and p.problems:
        raise ProfileError(f"{PROFILE.as_posix()} has problems — fix it (run `avflow risk check`): " + "; ".join(p.problems))
    return p


def load_valid(root: Path | str) -> Profile | None:
    return ensure_valid(load(root))


# ---------- required checks
def requirements(profile: Profile | None, ticket_areas: list[str], files: list[str],
                 today: date | None = None) -> Requirements:
    """Checks required by the ticket's risk areas and by the files; the union of every matched area."""
    r = Requirements()
    files = [norm_path(f) for f in files if str(f).strip()]
    other = BUILTIN_OTHER if profile is None or profile.other_checks is None else profile.other_checks
    if profile is None:
        r.warnings.append(f"This repository has no {PROFILE.as_posix()}: only the ticket's risk area counts "
                          "(run `avflow init` to add one).")
    found: list[str] = []
    for name in ticket_areas or []:
        if is_none(name):
            continue
        if key(name) == key(OTHER):
            r.areas.setdefault(OTHER, "ticket")
            found = grow(found, other)
            continue
        a = profile.area(name) if profile else None
        if a is None:
            if profile is not None:
                r.warnings.append(f"Risk area '{name}' on the ticket is not in the project's profile; "
                                  f"treated as '{OTHER}'.")
            r.areas.setdefault(OTHER, "ticket")
            found = grow(found, other)
        else:
            r.areas.setdefault(a.name, "ticket")
            found = grow(found, a.checks)
    ticket_flagged = bool(r.areas)
    unmatched = []
    for f in files:
        hit = False
        for a in (profile.areas if profile else []):
            if any(glob_match(g, f) for g in a.paths):
                hit = True
                r.areas.setdefault(a.name, "files")
                r.files.setdefault(a.name, []).append(f)
                found = grow(found, a.checks)
        if not hit:
            unmatched.append(f)
    if not r.areas and profile is not None and profile.default_checks:
        if profile.default_until is None or (today or date.today()) <= profile.default_until:
            r.default_applied = True
            found = grow(found, profile.default_checks)
    if ticket_flagged:
        r.gaps = unmatched
    r.checks = found
    return r
