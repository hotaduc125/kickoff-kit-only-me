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
