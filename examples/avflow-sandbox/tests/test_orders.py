from datetime import date

import pytest

from sandbox.orders import Order, sample_orders


def test_sample_orders_are_valid():
    assert len(sample_orders()) == 3


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        Order("WO-1", "X", 0, date(2026, 1, 1))


def test_unknown_status_refused():
    with pytest.raises(ValueError):
        Order("WO-1", "X", 1, date(2026, 1, 1), "lost")
