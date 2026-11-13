"""The project's risk profile (`.avflow/project.toml`) and the checks a change requires.

Pure functions only (no ticket system, no git): the MCP tools and `avflow risk` call them.
avflow knows *that* something is risky; the project's profile says *what* is risky.
"""
from __future__ import annotations

import json
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
MARKER = "[avflow]"                  # private ticket notes written by avflow's tools start their first line with it
REQUIRED = MARKER + " required "     # … followed by JSON: {"stage", "areas", "checks", "gaps"}
GATES = ("report", "fail")
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
    gate: str = "report"                           # [ci] gate: "report" (pilot) or "fail"
    presets: list[str] = field(default_factory=list)
    preset_version: int | None = None
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


def split_areas(v) -> list[str]:
    vals = v if isinstance(v, list) else re.split(r"\s*,\s*", str(v or ""))
    return [x.strip() for x in vals if isinstance(x, str) and x.strip() and not is_none(x)]


def unique_areas(areas: list[str]) -> list[str]:
    seen, out = set(), []
    for a in areas:
        if key(a) not in seen:
            seen.add(key(a))
            out.append(a)
    return out


# ---------- facts from the ticket's text (shared by the ticket adapter and the CI gate)
def description_fields(description: str) -> dict:
    """Values a person wrote in the description's "Size and mode" line."""
    d = description or ""
    out: dict = {}
    m = re.search(r"(?im)hotspot\s*:\s*\**\s*`?([^`\n·|*]+?)`?\s*\**\s*(?:[·|]|$)", d)
    if m:
        v = m.group(1).strip()
        out["hotspot"] = None if v.lower() in ("none", "-", "n/a", "") or v.lower().startswith("todo") else v
    m = re.search(r"(?im)risk[ -]area\s*:\s*\**\s*([^\n·|*]*?)\s*\**\s*(?:[·|]|$)", d)
    if m:
        out["risk_areas"] = split_areas(m.group(1))
    m = re.search(r"(?im)high[ -]risk\s*:\s*\**\s*(yes|no)\b", d)
    if m:
        out["risk_areas"] = out.get("risk_areas", []) + ([OTHER] if m.group(1).lower() == "yes" else [])
    if re.search(r"(?im)\btype\s*:\s*\**\s*spike\b", d):
        out["spike"] = True
    return out


def marker_fields(private_notes: list[str]) -> dict:
    """Values from PRIVATE notes like '[avflow] risk-area=Payments · hotspot=src/a.cs' (oldest first).

    Risk areas accumulate over all notes; for hotspot the latest wins.
    Callers must pass private notes only: anyone, including the customer, can write a public one.
    """
    out: dict = {"risk_areas": []}
    for text in private_notes or []:
        if MARKER not in (text or ""):
            continue
        line = next((l for l in text.splitlines() if l.strip().startswith(MARKER)), "")
        if line.startswith(REQUIRED):
            continue
        for k, v in re.findall(r"(risk-area|hotspot)=([^·\s]+)", line):
            if k == "risk-area":
                out["risk_areas"].append(v.replace("_", " "))
            else:
                out["hotspot"] = None if v in ("none", "-") else v
    return out


def required_from_notes(private_notes: list[str]) -> dict:
    """Union of the checks recorded at each stage in PRIVATE '[avflow] required {…}' notes."""
    out: dict = {"checks": [], "areas": {}, "stages": [], "gaps": []}
    for text in private_notes or []:
        for line in (text or "").splitlines():
            if not line.startswith(REQUIRED):
                continue
            try:
                d = json.loads(line[len(REQUIRED):])
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            out["checks"] = grow(out["checks"], [c for c in d.get("checks", []) if isinstance(c, str)])
            for k, v in (d.get("areas") or {}).items():
                out["areas"].setdefault(k, v)
            out["stages"].append(d.get("stage"))
            out["gaps"] += [g for g in d.get("gaps", []) if isinstance(g, str) and g not in out["gaps"]]
    return out


def required_line(stage: str, areas: dict, checks: list, gaps: list | None = None) -> str:
    d = {"stage": stage, "areas": areas, "checks": checks}
    if gaps:
        d["gaps"] = gaps
    return REQUIRED + json.dumps(d, ensure_ascii=False)


# ---------- the avflow section of the merge request description (written by review_requirements, read by CI)
MR_BEGIN = "<!-- avflow:checks -->"
MR_END = "<!-- /avflow:checks -->"
_BOX = re.compile(r"^\s*[-*]\s*\[([ xX])\]\s*(.+?)\s*$")


def _mr_split(desc: str) -> tuple[str, str | None, str]:
    d = desc or ""
    b = d.find(MR_BEGIN)
    e = d.find(MR_END, b + 1) if b >= 0 else -1
    if b < 0 or e < 0:
        return d, None, ""
    return d[:b], d[b:e + len(MR_END)], d[e + len(MR_END):]


def ticked_checklist(desc: str) -> set[str]:
    """Checklist texts ticked inside the avflow section only (ticks elsewhere in the description do not count)."""
    section = _mr_split(desc)[1] or ""
    return {m.group(2) for m in map(_BOX.match, section.splitlines()) if m and m.group(1) in "xX"}


def update_mr_description(desc: str, checks: list[str]) -> str:
    """Write or refresh the avflow section, keeping the ticks a person already set and everything outside it."""
    before, _, after = _mr_split(desc)
    ticked = ticked_checklist(desc)
    L = [MR_BEGIN, "### Required checks (avflow)", ""]
    items = [c[len(CHECKLIST):].strip() for c in checks if c.startswith(CHECKLIST)]
    others = [c for c in checks if not c.startswith(CHECKLIST)]
    if not checks:
        L.append("None beyond the standard flow (tests, green pipeline, a person's review).")
    if items:
        L.append("Ticked by a person (never by the agent):")
        L += [f"- [{'x' if t in ticked else ' '}] {t}" for t in items]
    if others:
        L += ([""] if items else []) + ["Also required (checked by the CI job avflow-risk-check where it can):"]
        L += [f"- {describe(c)}" for c in others]
    L.append(MR_END)
    section = "\n".join(L)
    if not before and not after and not (desc or "").strip():
        return section + "\n"
    if _mr_split(desc)[1] is None:
        return (desc or "").rstrip("\n") + "\n\n" + section + "\n"
    return before + section + after


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
    proj = data.get("project") or {}
    p.name = str(proj.get("name", "") or "")
    p.presets = [x for x in proj.get("presets", []) if isinstance(x, str)] if isinstance(proj.get("presets"), list) else []
    if isinstance(proj.get("preset_version"), int):
        p.preset_version = proj["preset_version"]
    gate = (data.get("ci") or {}).get("gate", "report")
    if gate not in GATES:
        p.problems.append(f"[ci]: gate must be \"report\" or \"fail\", not {gate!r}")
    else:
        p.gate = gate
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


# ---------- stack presets (used by `avflow init` and `avflow risk check`; not needed by the CI copy)
SKIP_DIRS = {".git", "node_modules", "bin", "obj", ".venv", "venv", "dist", "build", "target", "vendor", "packages", ".idea"}
CONCERNS = (("dependencies", "Dependencies"), ("migrations", "Data migrations"), ("configuration", "Configuration"))
SHARED = (("ci", "Build and CI"), ("infrastructure", "Infrastructure"))


def load_presets() -> dict:
    from importlib import resources
    return tomllib.loads(resources.files("avflow").joinpath("data/presets.toml").read_text(encoding="utf-8"))


def preset_names(presets: dict | None = None) -> list[str]:
    return sorted((presets or load_presets())["preset"])


def detect_stacks(root: Path | str, presets: dict | None = None, depth: int = 3) -> list[str]:
    """Presets whose marker files exist in the repository (a few folders deep, vendored folders skipped)."""
    presets = presets or load_presets()
    names: list[str] = []

    def walk(d: Path, level: int):
        try:
            entries = list(d.iterdir())
        except OSError:
            return
        for e in entries:
            if e.is_file():
                names.append(e.name)
            elif e.is_dir() and level < depth and e.name not in SKIP_DIRS and not e.name.startswith("."):
                walk(e, level + 1)
    walk(Path(root), 0)
    return [k for k in preset_names(presets)
            if any(glob_match(pat, n) for pat in presets["preset"][k]["detect"] for n in names)]


def _preset_areas(stacks: list[str], presets: dict) -> list[tuple[str, str, list[str]]]:
    """(concern, area name, paths) for the stacks, then the shared areas; empty concerns are left out."""
    out = []
    for concern, title in CONCERNS:
        paths = list(dict.fromkeys(p for st in stacks for p in presets["preset"][st].get(concern, [])))
        if paths:
            out.append((concern, title, paths))
    for concern, title in SHARED:
        out.append((concern, title, list(presets["shared"][concern])))
    return out


def _toml_list(items: list[str]) -> str:
    q = [json.dumps(x, ensure_ascii=False) for x in items]
    one = "[" + ", ".join(q) + "]"
    return one if len(one) <= 90 else "[\n" + "".join(f"    {x},\n" for x in q) + "]"


def render_profile(name: str, stacks: list[str], today: date | None = None, presets: dict | None = None) -> str:
    """The .avflow/project.toml that `avflow init` writes: preset areas, suggestions (commented), defaults."""
    from datetime import timedelta
    presets = presets or load_presets()
    unknown = [x for x in stacks if x not in presets["preset"]]
    if unknown:
        raise ValueError(f"Unknown stack: {', '.join(unknown)} (known: {', '.join(preset_names(presets))})")
    today = today or date.today()
    titles = ", ".join(presets["preset"][x]["title"] for x in stacks) or "none detected"
    L = [
        "# Risk profile of this project — read by avflow's ticket tools, `avflow risk` and the CI job avflow-risk-check.",
        "# Reviewed by merge request like code. `avflow risk check` validates it; `avflow risk sync` regenerates CODEOWNERS.",
        "# Checks: plan-confirmation · independent-review · code-owner (needs owners) · \"checklist:<what a person ticks>\".",
        f"# Written by `avflow init` on {today.isoformat()} from the stack presets ({titles}). The project owns it now.",
        "",
        "[project]",
        f"name = {json.dumps(name, ensure_ascii=False)}",
        f"presets = {_toml_list(stacks)}",
        f"preset_version = {presets['version']}",
        "",
        "[ci]",
        "gate = \"report\"      # pilot: the CI job lists missing checks; \"fail\" makes it block the merge",
    ]
    for concern, title, paths in _preset_areas(stacks, presets):
        L += ["", "[[risk.area]]", f"name   = {json.dumps(title)}", f"paths  = {_toml_list(paths)}",
              "# owners = [\"@username\"]   # then add \"code-owner\" to checks and run `avflow risk sync`",
              f"checks = {_toml_list(presets['checks'][concern])}"]
    sugg = [(st, x) for st in stacks for x in presets["preset"][st].get("suggested", [])]
    if sugg:
        L += ["", "# ---- Suggested by the stack presets: uncomment what applies to this project."]
        for st, x in sugg:
            L += ["", f"# [[risk.area]]   # {presets['preset'][st]['title']}: {x['reason']}",
                  f"# name   = {json.dumps(x['name'])}", f"# paths  = {json.dumps(x['paths'])}",
                  f"# checks = {json.dumps(x['checks'])}"]
    L += ["", "# ---- Domain areas: the project's own risks (no preset can know them). Paths may be empty at first:",
          "# tickets can name the area, and paths are added once the folder structure is decided.",
          "", "# [[risk.area]]", "# name   = \"Payments\"", "# paths  = []", "# owners = [\"@lead\"]",
          "# checks = [\"plan-confirmation\", \"independent-review\", \"code-owner\", \"checklist:Refund and failure paths tested\"]",
          "", "[risk.other]          # the ticket's \"Other high risk\": risky, but no area fits yet",
          "checks = [\"plan-confirmation\", \"independent-review\"]",
          "", "[risk.default]        # strict start: every change outside all areas, until the date (then remove it)",
          "checks = [\"plan-confirmation\", \"independent-review\"]",
          f"until  = \"{(today + timedelta(weeks=6)).isoformat()}\"", ""]
    return "\n".join(L)


def preset_drift(profile: Profile, presets: dict | None = None) -> dict[str, list[str]]:
    """Paths a newer preset has that the profile's area of the same name lacks (only after a preset version bump)."""
    presets = presets or load_presets()
    if not profile.presets or profile.preset_version is None or profile.preset_version >= presets["version"]:
        return {}
    stacks = [x for x in profile.presets if x in presets["preset"]]
    out = {}
    for _, title, paths in _preset_areas(stacks, presets):
        a = profile.area(title)
        if a is None:
            continue                       # the project removed the area: its choice
        missing = [x for x in paths if x not in a.paths]
        if missing:
            out[a.name] = missing
    return out


# ---------- generated files: CODEOWNERS block and the CI copy of this module
CODEOWNERS_BEGIN = "# >>> avflow risk areas"
CODEOWNERS_END = "# <<< avflow risk areas"
CODEOWNERS_FILES = ("CODEOWNERS", "docs/CODEOWNERS", ".gitlab/CODEOWNERS")     # GitLab uses the first that exists
CI_COPY = "ci/avflow_risk.py"


def codeowners_pattern(glob: str) -> str:
    """Profile globs are relative to the repository root; CODEOWNERS anchors a pattern with a leading slash."""
    g = norm_path(glob)
    return g if g.startswith("**/") else "/" + g


def codeowners_block(profile: Profile) -> str:
    L = [f"{CODEOWNERS_BEGIN} — generated by `avflow risk sync` from {PROFILE.as_posix()}; edit the profile, not this block",
         "# (When patterns overlap, GitLab uses the LAST matching line.)"]
    for a in profile.areas:
        if not a.owners:
            continue
        if not a.paths:
            L.append(f"# {a.name}: no paths yet — owners {' '.join(a.owners)} apply once paths are added")
            continue
        L.append(f"# {a.name}")
        L += [f"{codeowners_pattern(g)} {' '.join(a.owners)}" for g in a.paths]
    if len(L) == 2:
        L.append("# No risk area has owners yet: add owners = [\"@username\"] in the profile, then run `avflow risk sync`.")
    L.append(CODEOWNERS_END)
    return "\n".join(L)


def _split_block(text: str) -> tuple[str, str | None, str]:
    lines = (text or "").splitlines()
    try:
        b = next(i for i, l in enumerate(lines) if l.startswith(CODEOWNERS_BEGIN))
        e = next(i for i in range(b, len(lines)) if lines[i].startswith(CODEOWNERS_END))
    except StopIteration:
        return text or "", None, ""
    before, after = "\n".join(lines[:b]), "\n".join(lines[e + 1:])
    return (before + "\n" if before else ""), "\n".join(lines[b:e + 1]), (after + "\n" if after else "")


def sync_codeowners(text: str, profile: Profile) -> str:
    """Replace (or append) the avflow block; every line outside it is kept as written."""
    before, block, after = _split_block(text)
    if block is None:
        sep = "" if not before or before.endswith("\n\n") else ("\n" if before.endswith("\n") else "\n\n")
        return before + sep + codeowners_block(profile) + "\n"
    return before + codeowners_block(profile) + "\n" + after


def codeowners_in_sync(text: str, profile: Profile) -> bool:
    return _split_block(text)[1] == codeowners_block(profile)


def _own_source() -> str:
    return Path(__file__).read_text(encoding="utf-8")


def ci_copy() -> str:
    try:
        from avflow import __version__ as v
    except ImportError:          # inside the CI copy itself
        v = "copy"
    return (f"# avflow {v} — copy of avflow's risk.py for the CI job avflow-risk-check. Do not edit:\n"
            "# `avflow risk sync` refreshes it.\n" + _own_source())


def ci_copy_current(text: str) -> bool:
    body = "\n".join((text or "").splitlines(keepends=False)[2:])
    return body == "\n".join(_own_source().splitlines(keepends=False))


# ---------- profile gaps → suggested paths (`avflow risk suggest`; a person decides)
def suggest_paths(entries: list[dict], profile: Profile | None) -> list[dict]:
    """entries: {"ticket", "areas" (name → source), "gaps"} from review notes. One suggestion per (area, folder)."""
    found: dict[tuple[str, str], dict] = {}
    for e in entries:
        blamed = [a for a, src in (e.get("areas") or {}).items() if src == "ticket"] or ["(high-risk ticket)"]
        for g in e.get("gaps") or []:
            g = norm_path(g)
            if profile and any(glob_match(p, g) for a in profile.areas for p in a.paths):
                continue                              # the profile covers it by now
            folder = g.rsplit("/", 1)[0] + "/**" if "/" in g else g
            for a in blamed:
                s = found.setdefault((a, folder), {"area": a, "path": folder, "tickets": [], "examples": []})
                if e["ticket"] not in s["tickets"]:
                    s["tickets"].append(e["ticket"])
                if g not in s["examples"]:
                    s["examples"].append(g)
    out = sorted(found.values(), key=lambda s: (-len(s["tickets"]), s["area"], s["path"]))
    for s in out:
        s["tickets"].sort()
        s["examples"].sort()
    return out
