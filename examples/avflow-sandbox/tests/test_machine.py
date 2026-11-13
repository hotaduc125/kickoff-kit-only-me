import pytest

from sandbox.machine import MAX_SPEED_MM_S, Machine


def test_move_within_limits():
    assert Machine().move_to(100, 50) == 100.0


def test_speed_limit_enforced():
    with pytest.raises(ValueError):
        Machine().move_to(10, MAX_SPEED_MM_S + 1)


def test_door_open_refuses_motion():
    m = Machine()
    m.door_closed = False
    with pytest.raises(RuntimeError):
        m.move_to(10, 50)


def test_stop_returns_to_safe_position():
    m = Machine()
    m.move_to(80, 50)
    m.stop()
    assert m.position_mm == 0.0 and not m.running
