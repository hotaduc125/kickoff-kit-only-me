"""Simulated machine control — the project's risk area "Machine control" (see .avflow/project.toml).

Changes here require plan confirmation, an independent review, a code-owner approval and a test by someone other
than the author, and must keep the safety checks below.
"""
from __future__ import annotations

MAX_SPEED_MM_S = 250          # hardware limit — never raise without a hardware review
SAFE_POSITION_MM = 0.0


class Machine:
    def __init__(self):
        self.position_mm = SAFE_POSITION_MM
        self.door_closed = True
        self.running = False

    def move_to(self, target_mm: float, speed_mm_s: float) -> float:
        if not self.door_closed:
            raise RuntimeError("door open: motion refused")
        if speed_mm_s <= 0 or speed_mm_s > MAX_SPEED_MM_S:
            raise ValueError(f"speed must be in (0, {MAX_SPEED_MM_S}] mm/s")
        self.position_mm = float(target_mm)
        return self.position_mm

    def stop(self) -> None:
        self.running = False
        self.position_mm = SAFE_POSITION_MM
