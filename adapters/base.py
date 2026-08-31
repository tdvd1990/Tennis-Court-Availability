"""Adapter interface every club-system integration implements.

An adapter's contract is deliberately narrow: given a club's config
(from clubs.json) and a date, return that club's real-world court
availability as a list of models.TimeSlot. Nothing else in this project
needs to know which vendor a club uses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from models import Court, TimeSlot


class Adapter(ABC):
    """Base class for a single booking-vendor integration."""

    def __init__(self, club_config: dict):
        self.club_config = club_config
        self.club_id = club_config["id"]
        self.club_name = club_config["name"]

    def courts(self) -> list[Court]:
        return [
            Court(
                club_id=self.club_id,
                club_name=self.club_name,
                number=c["number"],
                slot_minutes=c["slot_minutes"],
                label=c.get("surface") or ("indoor" if c.get("indoor") else ""),
            )
            for c in self.club_config["courts"]
        ]

    @abstractmethod
    def get_availability(self, day: date) -> list[TimeSlot]:
        """Return every bookable slot (available or booked) for `day`."""
        raise NotImplementedError

    # Booking is intentionally NOT part of the base interface yet.
    # Phase 2 (only once Phase 1 has proven each adapter reliably reads
    # real availability) would add something like:
    #
    #   def book(self, court: Court, day: date, start: time) -> bool: ...
    #
    # implemented per-vendor once we've captured the real request each
    # site's "Reserve" button makes.
