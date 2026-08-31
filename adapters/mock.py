"""Realistic fake availability, so the aggregator + viewer can be built
and proven out before any real credentials exist.

Generates the correct slot grid for each court (30 vs 60 minutes, per
clubs.json) between OPEN_HOUR and CLOSE_HOUR, and randomly marks some
slots booked so the rendered page looks like a real week rather than an
empty grid.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from models import TimeSlot
from .base import Adapter

OPEN_HOUR = 7
CLOSE_HOUR = 23


class MockAdapter(Adapter):
    def get_availability(self, day: date) -> list[TimeSlot]:
        slots: list[TimeSlot] = []
        # Deterministic per (club, day) so re-rendering the same day looks
        # stable rather than flickering randomly on every run.
        rng = random.Random(f"{self.club_id}-{day.isoformat()}")

        for court in self.courts():
            cursor = datetime.combine(day, time(OPEN_HOUR, 0))
            close = datetime.combine(day, time(CLOSE_HOUR, 0))
            step = timedelta(minutes=court.slot_minutes)

            while cursor < close:
                end = cursor + step
                status = "booked" if rng.random() < 0.35 else "available"
                slots.append(
                    TimeSlot(
                        court=court,
                        day=day,
                        start=cursor.time(),
                        end=end.time(),
                        status=status,
                    )
                )
                cursor = end

        return slots
