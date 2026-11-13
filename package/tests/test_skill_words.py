"""avflow's skills, commands and subagents use generic words (design 3.0, principle 6).

Project words (machine, panel, test bench, Mateo, …) belong to the project's own skills and risk areas;
the 2.x working modes no longer exist.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = sorted([*(ROOT / "plugin/plugins/avflow/skills").glob("*/SKILL.md"),
                *(ROOT / "plugin/plugins/avflow/commands").glob("*.md"),
                *(ROOT / "package/src/avflow/agents").glob("*.md"),
                ROOT / "package/src/avflow/templates/CLAUDE.md"])

FORBIDDEN = {
    "machine": r"\bmachines?\b(?!-readable)",
    "panel": r"\bpanels?\b",
    "test bench": r"\btest bench",
    "simulator": r"\bsimulat",
    "camera": r"\bcamera",
    "site visit": r"\bsite visit",
    "project name": r"\b(mateo|wkkm|zmotion)\b",
    "Chinese / zh": r"\bchinese\b|\bzh\b",
    "recipe / SPC": r"\brecipe|\bSPC\b",
    "sensitive path (now risk areas)": r"\bsensitive[- ]paths?\b",
    "2.x mode": r"\b(choose-mode|DIRECT|FULL|machine-side|proposed mode)\b|\bmode (DIRECT|PLAN|FULL|SPIKE)",
}


def test_files_found():
    assert len(FILES) >= 15


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_project_words(path):
    text = path.read_text(encoding="utf-8")
    hits = []
    for what, pattern in FORBIDDEN.items():
        flags = 0 if what == "2.x mode" else re.IGNORECASE
        for m in re.finditer(pattern, text, flags):
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"line {line}: {what!r} ({m.group(0)!r})")
    assert not hits, "\n".join(hits)


# Everything avflow ships (code, templates, defaults, the team file, scripts, docs for members) names no project or
# customer and carries no project concept such as Machine-side: avflow serves any project.
SHIPPED = sorted(p for base in ("package/src/avflow", "plugin", "team", "scripts", "examples/avflow-sandbox")
                 for p in (ROOT / base).rglob("*")
                 if p.is_file() and p.suffix in (".py", ".md", ".toml", ".yml", ".json", ".sh", ".ps1", "")
                 and not any(part.startswith(".") and part != ".claude" for part in p.relative_to(ROOT).parts)
                 and "__pycache__" not in p.parts)
SHIPPED += [ROOT / f for f in ("INSTALL.md", "package/README.md", "plugin/README.md", "docs/user-guide.md")]
PROJECT_CONCEPTS = r"\b(mateo|wkkm|zmotion)\b|machine[-_ ]side_area|field_machine_side|MACHINE_SIDE"


def test_shipped_files_found():
    assert len(SHIPPED) >= 60


@pytest.mark.parametrize("path", SHIPPED, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_project_or_customer_names(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    hits = [f"line {text.count(chr(10), 0, m.start()) + 1}: {m.group(0)!r}"
            for m in re.finditer(PROJECT_CONCEPTS, text, re.IGNORECASE)]
    assert not hits, "\n".join(hits)
