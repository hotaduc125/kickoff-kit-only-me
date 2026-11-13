from sandbox.orders import sample_orders
from sandbox.report import COLUMNS, render, rows


def test_header_and_rows():
    text = render(sample_orders())
    assert text.splitlines()[0] == " | ".join(COLUMNS)
    assert len(text.splitlines()) == 4


def test_dates_are_iso():
    assert rows(sample_orders())[0][3] == "2026-11-20"
