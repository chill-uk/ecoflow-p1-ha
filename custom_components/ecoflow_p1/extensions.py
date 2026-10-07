"""DSMR compatibility extensions not modeled by the shared parser contract."""

from __future__ import annotations

from decimal import Decimal

from .models import DemandPeak, ObisValue, split_number_and_unit


def parse_demand_history(value: ObisValue | None) -> tuple[DemandPeak, ...]:
    """Read Fluvius eMUCS-P1 13-month demand history.

    dsmr-parser models this field, but the EcoFlow integration deliberately keeps
    the raw DSMR local timestamps (including invalid/uninitialized placeholders)
    for backwards-compatible attributes. Keep that compatibility behavior here.
    """
    if value is None or len(value.values) < 3:
        return ()

    count, first, second, *groups = value.values
    if not count.isascii() or not count.isdecimal():
        return ()
    if (first, second) != ("1-0:1.6.0", "1-0:1.6.0"):
        return ()
    if len(groups) != int(count) * 3:
        return ()

    records: list[DemandPeak] = []
    for index in range(0, len(groups), 3):
        period, timestamp, raw = groups[index : index + 3]
        reading = split_number_and_unit(raw)
        if reading is None:
            continue
        peak, unit = reading
        if unit != "kW" or not peak.is_finite() or peak < Decimal(0):
            continue
        records.append(DemandPeak(period, timestamp, peak))

    return tuple(records)
