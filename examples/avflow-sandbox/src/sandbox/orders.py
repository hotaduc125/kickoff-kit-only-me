"""Orders of a small workshop: the data the report works on."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

STATUSES = ("open", "in_production", "done", "cancelled")


@dataclass(frozen=True)
class Order:
    number: str
    customer: str
    quantity: int
    due: date
    status: str = "open"

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status}")


def sample_orders() -> list[Order]:
    return [
        Order("WO-1001", "Acme", 120, date(2026, 11, 20)),
        Order("WO-1002", "Globex", 40, date(2026, 11, 18), "in_production"),
        Order("WO-1003", "Acme", 75, date(2026, 11, 25), "done"),
    ]
