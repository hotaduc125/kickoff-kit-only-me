"""Plain-text order report (the 'list screen' of the sample project)."""
from __future__ import annotations

from .orders import Order

COLUMNS = ("Number", "Customer", "Qty", "Due", "Status")


def rows(orders: list[Order]) -> list[tuple[str, ...]]:
    # Dates are shown with the default str() of date (YYYY-MM-DD). A shared formatting helper is planned (ticket T1).
    return [(o.number, o.customer, str(o.quantity), str(o.due), o.status) for o in orders]


def render(orders: list[Order]) -> str:
    lines = [" | ".join(COLUMNS)]
    lines += [" | ".join(r) for r in rows(orders)]
    return "\n".join(lines)
