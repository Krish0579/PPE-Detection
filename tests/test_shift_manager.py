from __future__ import annotations

from datetime import date, datetime, time

import pytest

from src.core.shifts import DEFAULT_SHIFTS, ShiftDefinition, ShiftManager, ShiftWindow, parse_shifts


def test_parse_shifts():
    shifts = parse_shifts("Morning=06:00-14:00, Night=22:00-06:00")
    assert len(shifts) == 2
    assert shifts[0].name == "Morning"
    assert shifts[0].start == time(6, 0)
    assert shifts[0].end == time(14, 0)
    assert not shifts[0].crosses_midnight

    assert shifts[1].name == "Night"
    assert shifts[1].crosses_midnight

    with pytest.raises(ValueError):
        parse_shifts("InvalidShiftFormat")

def test_shift_definition():
    shift = ShiftDefinition("Night", time(22, 0), time(6, 0))
    start, end = shift.window_for(date(2026, 10, 3))
    assert start == datetime(2026, 10, 3, 22, 0)
    assert end == datetime(2026, 10, 4, 6, 0)

def test_shift_manager_current():
    shifts = parse_shifts(DEFAULT_SHIFTS)
    manager = ShiftManager(shifts)

    # test shift A: 06:00 - 14:00
    dt = datetime(2026, 10, 3, 10, 0)
    current = manager.current(dt)
    assert current is not None
    assert current.shift.name == "A"
    assert current.start == datetime(2026, 10, 3, 6, 0)
    assert current.end == datetime(2026, 10, 3, 14, 0)

    # test shift C crossing midnight: 22:00 - 06:00
    dt = datetime(2026, 10, 4, 2, 0)
    current = manager.current(dt)
    assert current is not None
    assert current.shift.name == "C"
    assert current.start == datetime(2026, 10, 3, 22, 0)
    assert current.end == datetime(2026, 10, 4, 6, 0)

def test_shift_manager_previous():
    manager = ShiftManager(parse_shifts(DEFAULT_SHIFTS))
    
    dt = datetime(2026, 10, 3, 10, 0) # in shift A (06:00 - 14:00)
    prev = manager.previous(dt)
    assert prev is not None
    assert prev.shift.name == "C" # previous was 22:00 - 06:00
    assert prev.start == datetime(2026, 10, 2, 22, 0)
    assert prev.end == datetime(2026, 10, 3, 6, 0)

def test_shift_manager_close_shift():
    manager = ShiftManager()
    window = ShiftWindow(
        ShiftDefinition("A", time(6, 0), time(14, 0)),
        datetime(2026, 10, 3, 6, 0),
        datetime(2026, 10, 3, 14, 0)
    )

    def fetch_incidents(s, e): return [1, 2, 3]
    def build_digest(w, inc): return {"count": len(inc)}
    def archive(w, d): return "s3://path"
    
    res = manager.close_shift(
        window,
        fetch_incidents=fetch_incidents,
        build_digest=build_digest,
        archive=archive
    )
    
    assert res["incidents"] == 3
    assert res["archive"] == "s3://path"
