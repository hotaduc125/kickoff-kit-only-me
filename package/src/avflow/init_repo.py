"""avflow init: add the team's standard files to a project repository (never overwrites without --force)."""
from __future__ import annotations

from datetime import date
from importlib import resources
from pathlib import Path

PLACEHOLDERS = ("{project}", "{date}")


def template_files() -> list[tuple[str, str]]:
    root = resources.files("avflow").joinpath("templates")
    out = []

    def walk(node, prefix=""):
        for child in node.iterdir():
            rel = f"{prefix}{child.name}"
            if child.is_dir():
                walk(child, rel + "/")
            elif not child.name.endswith((".pyc",)):
                out.append((rel, child.read_text(encoding="utf-8")))
    walk(root)
    return sorted(out)


def init_repo(target: Path, project: str | None = None, force: bool = False, cfg=None,
              stacks: list[str] | None = None, today: date | None = None) -> dict:
    from . import risk
    target = Path(target)
    project = project or target.resolve().name
    if cfg is None:
        from .config import Config
        cfg = Config.team()
    t = cfg.tickets
    stacks = risk.detect_stacks(target) if stacks is None else list(stacks)
    profile_text = risk.render_profile(project, stacks, today)          # raises ValueError for an unknown stack
    names = {"{status_in_review}": t.status_in_review, "{status_ready_for_test}": t.status_ready_for_test,
             "{field_risk_area}": t.field_risk_area}
    result = {"created": [], "skipped": [], "overwritten": [], "stacks": stacks}
    profile_existed = (target / risk.PROFILE).exists()
    for rel, text in template_files():
        if rel.startswith("__"):
            continue
        dst = target / rel
        content = text.replace("{project}", project).replace("{date}", date.today().isoformat())
        for k, v in names.items():
            content = content.replace(k, v)
        if dst.exists() and not force:
            result["skipped"].append(rel)
            continue
        existed = dst.exists()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8", newline="\n")
        result["overwritten" if existed else "created"].append(rel)
    generated = [(risk.PROFILE.as_posix(), profile_text), (risk.CI_COPY, risk.ci_copy())]
    for rel, content in generated:
        dst = target / rel
        if dst.exists() and not force:
            result["skipped"].append(rel)
            continue
        existed = dst.exists()
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8", newline="\n")
        result["overwritten" if existed else "created"].append(rel)
    co = target / "CODEOWNERS"
    if "CODEOWNERS" not in result["skipped"]:            # written from the template just now: add the avflow block
        prof = risk.load(target)
        if prof is not None and not prof.problems:
            co.write_text(risk.sync_codeowners(co.read_text(encoding="utf-8"), prof), encoding="utf-8", newline="\n")
    result["profile_existed"] = profile_existed
    ci = target / ".gitlab-ci.yml"
    if not ci.exists():
        ci.write_text("include:\n  - local: .gitlab-ci.avflow.yml\n\n# Add the project's build and test jobs below.\n",
                      encoding="utf-8", newline="\n")
        result["created"].append(".gitlab-ci.yml")
    else:
        text = ci.read_text(encoding="utf-8")
        active = [ln.split("#", 1)[0] for ln in text.splitlines()]      # ignore comments
        if not any(".gitlab-ci.avflow.yml" in ln for ln in active):
            result["skipped"].append(".gitlab-ci.yml (add: include: - local: .gitlab-ci.avflow.yml)")
    return result
