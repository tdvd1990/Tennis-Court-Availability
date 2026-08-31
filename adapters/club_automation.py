"""Club Automation integration - covers 10XTO (10xtoronto.clubautomation.com).

Same status as court_reserve.py: real vendor confirmed (via web search and
the club's Android app package name, com.clubautomation.xto), but not
wired to live data yet since that needs your login and a captured sample
of the real request/response. See README "Capturing the real request".
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from models import TimeSlot
from .base import Adapter

CAPTURE_DIR = Path(__file__).resolve().parent.parent / "capture"


class ClubAutomationAdapter(Adapter):
    def get_availability(self, day: date) -> list[TimeSlot]:
        capture_file = CAPTURE_DIR / f"club_automation_{self.club_id}.json"

        if not capture_file.exists():
            base_url = self.club_config.get("club_automation", {}).get("base_url")
            raise NotImplementedError(
                f"No captured Club Automation response for '{self.club_name}' yet "
                f"(looked for {capture_file}).\n"
                f"Site: {base_url}\n"
                "See README.md > 'Capturing the real request', then drop the "
                "saved JSON at that path and switch this club's \"mode\" to "
                "\"live\" in clubs.json."
            )

        raw = json.loads(capture_file.read_text())
        return self._parse(raw, day)

    def _parse(self, raw: dict, day: date) -> list[TimeSlot]:
        # Placeholder mapping - rewrite once we see a real capture's shape.
        slots: list[TimeSlot] = []
        courts_by_number = {c.number: c for c in self.courts()}

        for entry in raw.get("events", []):
            court = courts_by_number.get(entry["resourceNumber"])
            if court is None:
                continue
            slots.append(
                TimeSlot(
                    court=court,
                    day=day,
                    start=entry["start"],
                    end=entry["end"],
                    status="booked" if entry.get("reserved") else "available",
                )
            )
        return slots
