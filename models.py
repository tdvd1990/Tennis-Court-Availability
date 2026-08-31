"""Shared data model used by every adapter.

Keeping this tiny and vendor-agnostic is the whole point: each adapter's
only job is to translate one club's booking system into a list of
TimeSlot objects. Everything downstream (aggregation, rendering) only
ever deals with TimeSlot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True)
class Court:
    club_id: str
    club_name: str
    number: int
    slot_minutes: int  # 30 or 60 - how finely this court can be booked
    label: str = ""  # optional extra info, e.g. "clay", "indoor"

    @property
    def display_name(self) -> str:
        suffix = f" ({self.label})" if self.label else ""
        return f"{self.club_name} - Court {self.number}{suffix}"


@dataclass(frozen=True)
class TimeSlot:
    court: Court
    day: date
    start: time
    end: time
    status: str  # "available" | "booked" | "unknown"

    @property
    def duration_minutes(self) -> int:
        return (self.end.hour * 60 + self.end.minute) - (
            self.start.hour * 60 + self.start.minute
        )
