import re

import pytest

from avflow import setup_steps as st
from avflow.config import MODEL_CHOICES, Config, ModelsConfig


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "missing frontmatter"
    return dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)


def test_install_writes_three_agents_with_chosen_models(tmp_path):
    done = st.install_agents(ModelsConfig(plan="opus", implement="sonnet", review="haiku"), tmp_path)
    assert len(done) == 3
    fm = {n: frontmatter((tmp_path / f"{n}.md").read_text()) for n in st.AGENT_ROLES.values()}
    assert fm["avflow-planner"]["model"].strip() == "opus"
    assert fm["avflow-implementer"]["model"].strip() == "sonnet"
    assert fm["avflow-reviewer"]["model"].strip() == "haiku"
    for n, f in fm.items():
        assert f["name"].strip() == n and f["description"].strip()


def test_planner_and_reviewer_cannot_edit_files(tmp_path):
    st.install_agents(ModelsConfig(), tmp_path)
    for n in ("avflow-planner", "avflow-reviewer"):
        tools = frontmatter((tmp_path / f"{n}.md").read_text())["tools"]
        assert "Edit" not in tools and "Write" not in tools
    assert "tools" not in frontmatter((tmp_path / "avflow-implementer.md").read_text())


def test_status_ok_then_detects_changes(tmp_path):
    m = ModelsConfig()
    st.install_agents(m, tmp_path)
    assert all(good for _, good, _ in st.agents_status(m, tmp_path))
    changed = ModelsConfig(review="sonnet")
    bad = [d for n, good, d in st.agents_status(changed, tmp_path) if not good]
    assert bad == ["model is opus, configuration says sonnet — run avflow setup"]
    f = tmp_path / "avflow-planner.md"
    f.write_text(f.read_text() + "\nextra line\n")
    assert any("edited by hand" in d for _, _, d in st.agents_status(m, tmp_path))


def test_missing_and_remove(tmp_path):
    assert all(not good for _, good, _ in st.agents_status(ModelsConfig(), tmp_path))
    st.install_agents(ModelsConfig(), tmp_path)
    assert sorted(st.remove_agents(tmp_path)) == sorted(st.AGENT_ROLES.values())
    assert list(tmp_path.iterdir()) == []


def test_models_config_roundtrip(tmp_path):
    p = tmp_path / "c.toml"
    Config(models=ModelsConfig(plan="inherit", implement="haiku", review="sonnet")).save(p)
    m = Config.load(p).models
    assert (m.plan, m.implement, m.review) == ("inherit", "haiku", "sonnet")


@pytest.mark.parametrize("model", MODEL_CHOICES)
def test_every_choice_renders(model, tmp_path):
    st.install_agents(ModelsConfig(plan=model, implement=model, review=model), tmp_path)
    assert all(good for _, good, _ in st.agents_status(ModelsConfig(plan=model, implement=model, review=model), tmp_path))
