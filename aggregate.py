"""Pulls availability for every club in clubs.json and returns one
combined structure the renderer can draw as a single grid.

Each club's clubs.json entry has a "mode": "mock" or "live".
  - "mock"  -> always uses MockAdapter, regardless of vendor. This is the
              default for every club right now, since none are wired to
              real credentials yet.
  - "live"  -> uses the real vendor adapter (CourtReserveAdapter /
              ClubAutomationAdapter), which requires a capture/ file
              (see adapters/court_reserve.py and README.md).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from adapters import ADAPTERS_BY_SYSTEM, MockAdapter
from models import TimeSlot

CLUBS_FILE = Path(__file__).resolve().parent / "clubs.json"


def load_clubs() -> list[dict]:
    return json.loads(CLUBS_FILE.read_text())["clubs"]


def build_adapter(club_config: dict):
    if club_config.get("mode", "mock") == "mock":
        return MockAdapter(club_config)
    adapter_cls = ADAPTERS_BY_SYSTEM[club_config["system"]]
    return adapter_cls(club_config)


def get_week_availability(
    start_day: date, num_days: int = 7
) -> tuple[dict[str, dict[date, list[TimeSlot]]], dict[str, list]]:
    """Returns ({ club_name: { day: [TimeSlot, ...] } }, { club_name: [Court, ...] }).

    The second dict is each club's court list straight from clubs.json
    (via the adapter's courts() helper) - independent of whether this
    run's actual fetch succeeded for any day. render_html.py uses it to
    decide which columns to draw, so a club whose live fetch fails
    entirely still gets its real columns shown as hatched/unknown,
    instead of losing its columns from the page altogether.
    """
    clubs = load_clubs()
    result: dict[str, dict[date, list[TimeSlot]]] = {}
    courts_by_club: dict[str, list] = {}

    for club_config in clubs:
        adapter = build_adapter(club_config)
        courts_by_club[club_config["name"]] = adapter.courts()
        by_day: dict[date, list[TimeSlot]] = {}
        for i in range(num_days):
            day = start_day + timedelta(days=i)
            try:
                by_day[day] = adapter.get_availability(day)
            except NotImplementedError as e:
                print(f"[{club_config['name']}] {e}\n")
                by_day[day] = []
        result[club_config["name"]] = by_day

    return result, courts_by_club
