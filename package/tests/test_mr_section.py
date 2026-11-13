"""The avflow section of the MR description: checklist items a person ticks, and how CI reads them."""
from avflow import risk

CHECKS = ["independent-review", "code-owner", "checklist:Tested on the test bench", "checklist:Rollback tested"]


def test_section_added_after_the_description():
    d = risk.update_mr_description("## What and why\nRefs #1", CHECKS)
    assert d.startswith("## What and why\nRefs #1\n") and risk.MR_BEGIN in d and d.rstrip().endswith(risk.MR_END)
    assert "- [ ] Tested on the test bench" in d and "- [ ] Rollback tested" in d
    assert "- [ ] Independent review" not in d and "Independent review" in d       # listed, not a checkbox
    assert risk.ticked_checklist(d) == set()


def test_ticks_are_kept_and_text_outside_untouched():
    d = risk.update_mr_description("Intro", CHECKS[:3])
    d = d.replace("- [ ] Tested on the test bench", "- [x] Tested on the test bench") + "\nFooter by a person\n"
    d2 = risk.update_mr_description(d, CHECKS)
    assert "- [x] Tested on the test bench" in d2 and "- [ ] Rollback tested" in d2
    assert d2.startswith("Intro") and "Footer by a person" in d2 and d2.count(risk.MR_BEGIN) == 1
    assert risk.ticked_checklist(d2) == {"Tested on the test bench"}
    assert risk.update_mr_description(d2, CHECKS) == d2


def test_ticks_outside_the_section_do_not_count():
    d = "- [x] Tested on the test bench\n" + risk.update_mr_description("", CHECKS)
    assert risk.ticked_checklist(d) == set()


def test_capital_x_counts():
    d = risk.update_mr_description("", CHECKS).replace("- [ ] Rollback tested", "- [X] Rollback tested")
    assert risk.ticked_checklist(d) == {"Rollback tested"}


def test_no_checks_leaves_a_short_section():
    d = risk.update_mr_description("x", [])
    assert "standard flow" in d and risk.ticked_checklist(d) == set()
