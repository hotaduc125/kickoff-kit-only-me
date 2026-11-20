"""avflow init: add the team's standard files to a project repository (never overwrites without --force)."""
from __future__ import annotations

import re
from datetime import date
from importlib import resources
from pathlib import Path

PLACEHOLDERS = ("{project}", "{date}")
AVFLOW_CI = ".gitlab-ci.avflow.yml"

# GitLab creates no pipeline whose jobs are all in the .pre / .post stages — and every avflow job is in one of them.
# So the project's .gitlab-ci.yml must keep at least one job in a normal stage; a new one starts with a placeholder.
CI_FILE = f"""include:
  - local: {AVFLOW_CI}

# GitLab runs no pipeline whose jobs are all in the .pre / .post stages (the avflow jobs are), so this file must keep
# at least one job in a normal stage. Replace this placeholder with the project's build and test jobs; keep the same
# rules (merge requests, and pushes to develop, where avflow-ready-for-test moves the tickets after a merge).
build-and-test:
  stage: test
  image: alpine:3.20
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == "develop" && $CI_PIPELINE_SOURCE == "push"'
  script:
    - echo "TODO: replace this placeholder with the project's build and test commands (see CLAUDE.md)"
"""
CI_NO_PIPELINE = (".gitlab-ci.yml has no job outside the .pre / .post stages: GitLab creates no pipeline for merge "
                  "requests or develop (the avflow jobs alone never run) — add the project's build and test jobs")
_CI_KEYWORDS = {"include", "stages", "variables", "default", "workflow", "image", "services", "cache",
                "before_script", "after_script", "spec"}
_TOP_KEY = re.compile(r"^([^\s#'\"-][^:]*|'[^']+'|\"[^\"]+\"):(.*)$")
_YML = re.compile(r"[\w./${}-]+\.ya?ml")


def ci_has_regular_job(text: str) -> bool | None:
    """True when the CI file defines a job in a normal stage (not .pre / .post), False when it does not, None when
    other included files may bring such jobs (unknown). Standard library only: a line-based reading of the YAML."""
    blocks: list[tuple[str, list[str]]] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+#.*$", "", raw)
        if not line.strip() or line.lstrip().startswith("#") or line.strip() in ("---", "..."):
            continue
        m = _TOP_KEY.match(line)
        if m:
            blocks.append((m.group(1).strip("'\""), [m.group(2)]))
        elif blocks:
            blocks[-1][1].append(line)
    unknown = False
    for key, body in blocks:
        if key == "include":
            inc = "\n".join(body)
            if re.search(r"\b(project|remote|template|component)\s*:", inc) or \
                    any(AVFLOW_CI not in y for y in _YML.findall(inc)):
                unknown = True
            continue
        if key in _CI_KEYWORDS or key.startswith("."):
            continue
        children = [ln for ln in body[1:] if ln.strip()]
        if not children:
            continue                                   # not a job (a scalar or an empty key)
        indent = len(children[0]) - len(children[0].lstrip())
        stage = "test"                                  # GitLab's default stage
        for ln in children:
            sm = re.match(r"^\s*stage\s*:\s*['\"]?([^'\"\s]+)", ln)
            if sm and len(ln) - len(ln.lstrip()) == indent:
                stage = sm.group(1)
        if stage not in (".pre", ".post"):
            return True
    return None if unknown else False


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
    result = {"created": [], "skipped": [], "overwritten": [], "stacks": stacks, "warnings": []}
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
        ci.write_text(CI_FILE, encoding="utf-8", newline="\n")
        result["created"].append(".gitlab-ci.yml")
    else:
        text = ci.read_text(encoding="utf-8")
        active = [ln.split("#", 1)[0] for ln in text.splitlines()]      # ignore comments
        if not any(AVFLOW_CI in ln for ln in active):
            result["skipped"].append(f".gitlab-ci.yml (add: include: - local: {AVFLOW_CI})")
        elif ci_has_regular_job(text) is False:
            result["warnings"].append(CI_NO_PIPELINE)
    return result
