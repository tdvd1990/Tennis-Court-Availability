"""CourtReserve integration - covers Sir Winston Churchill, Old Mill, and
Mimico, since all three use this vendor.

STATUS: parsing is real and working, driven off an actual captured
response (see capture/court_reserve_old_mill.json). Two ways a club's
availability gets fetched, chosen by its clubs.json "mode":
  - "replay" (or "mock", handled one level up in aggregate.py) - parses
    a frozen capture/*.json snapshot. Works for any day the snapshot
    represents (see _represents_day); every other day raises
    NotImplementedError. No credentials, no browser, instant.
  - "live" - logs in for real via live_session.CourtReserveSession and
    fetches genuinely fresh data. Needs COURTRESERVE_<CLUB_ID>_EMAIL /
    _PASSWORD in a local .env, and "scheduler_page_urls" (a list - most
    clubs have one entry, but Churchill has two: courts 1-5 and 6-10 are
    two separate schedulers, merged together) set in that club's
    clubs.json > court_reserve section. Opens a real, visible Chrome
    window for a few seconds while it runs, then covers as much of the
    week as the site's own "next day" button gets it through on each
    scheduler (see live_session.py's fetch_days_multi()) - one browser
    session per club for the whole week, not one per day or scheduler.
    Whichever days aren't reached this way still fall back to "unknown"
    for that club, same as before.

What the real response looks like (confirmed from a live capture):
CourtReserve's booking calendar is backed by a Kendo UI grid endpoint
that returns {"Data": [...], "Total": N, "AggregateResults": ..., "Errors": ...}.
Each item in "Data" is either:
  - a real reservation: CourtLabel like "Court #3", a ReservationType
    (Singles/Doubles/Summer Camp/etc), and local-time ReservationStart /
    ReservationEnd fields (no timezone suffix - these are club-local
    wall-clock times, unlike Start/End which are true UTC instants).
  - a per-half-hour "WAITLIST ME" placeholder (CourtLabel "WAITLISTxxxxx",
    Title "WAITLIST ME") representing an open-match/waitlist join option,
    not a specific court's real availability. These are filtered out.

The grid itself (which slots exist at all, and whether they're open) is
NOT returned directly - it has to be inferred: generate every possible
slot for each court from OPEN_HOUR to CLOSE_HOUR at that court's
slot_minutes, then mark a generated slot "booked" if it overlaps a real
reservation, "available" otherwise.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from models import Court, TimeSlot
from .base import Adapter

CAPTURE_DIR = Path(__file__).resolve().parent.parent / "capture"
COURT_LABEL_RE = re.compile(r"Court\s*#\s*(\d+)")

OPEN_HOUR = 7
CLOSE_HOUR = 23


class CourtReserveAdapter(Adapter):
    # How many consecutive days (starting today) to try to fetch in one
    # live browser session. Matches main.py's default week length; if
    # fewer clicks succeed than this, whatever was reached is still used.
    LIVE_WEEK_DAYS = 7

    def __init__(self, club_config: dict):
        super().__init__(club_config)
        # Filled in lazily by the FIRST live get_availability() call, then
        # reused for the rest of the week - so one adapter instance opens
        # the browser and logs in exactly once per run, not once per day.
        # None = not fetched yet; {} or a partial dict = fetched (however
        # far it got).
        self._live_week_cache: dict[date, dict] | None = None

    def get_availability(self, day: date) -> list[TimeSlot]:
        if self.club_config.get("mode") == "live":
            return self._get_live_availability(day)
        return self._get_replay_availability(day)

    def _get_live_availability(self, day: date) -> list[TimeSlot]:
        """Logs in for real (via live_session.CourtReserveSession) and
        fetches genuinely fresh data for as much of the week as the
        site's own "next day" button gets us through - see
        live_session.CourtReserveSession.fetch_days() for exactly how
        that's verified rather than assumed. Opens a real, visible Chrome
        window for a few seconds while it runs (once per run, not once
        per day - see live_session.py's UPDATE 2 on why headless doesn't
        work here, and the earlier version of this method's docstring in
        git history for the "opened 5-6 windows" bug this replaced)."""
        if self._live_week_cache is None:
            self._live_week_cache = self._fetch_live_week()

        raw = self._live_week_cache.get(day)
        if raw is None:
            reached = sorted(self._live_week_cache.keys())
            detail = (
                f"reached through {reached[-1].isoformat()}" if reached
                else "didn't reach any day"
            )
            raise NotImplementedError(
                f"'{self.club_name}' live fetch {detail} this run - "
                f"{day.isoformat()} wasn't covered (see live_session.py)."
            )
        return self._parse(raw, day)

    def _fetch_live_week(self) -> dict[date, dict]:
        # Imported lazily: only clubs actually set to "mode": "live" need
        # Playwright installed and a real Chrome available.
        from live_session import CourtReserveSession

        cr_config = self.club_config.get("court_reserve", {})
        org_id = cr_config.get("org_id")
        # A club's courts can be split across multiple independent
        # scheduler pages (Churchill: courts 1-5 vs 6-10, each its own
        # Kendo Scheduler with its own date navigation) - clubs.json
        # always uses a list, "scheduler_page_urls", even for the common
        # one-scheduler case (Old Mill, Mimico each just have a
        # single-item list).
        scheduler_page_urls = cr_config.get("scheduler_page_urls") or []
        if not scheduler_page_urls:
            raise NotImplementedError(
                f"'{self.club_name}' is set to \"mode\": \"live\" but has no "
                "\"scheduler_page_urls\" in clubs.json - nothing to fetch."
            )
        email_env = f"COURTRESERVE_{self.club_id.upper()}_EMAIL"
        password_env = f"COURTRESERVE_{self.club_id.upper()}_PASSWORD"
        days = [date.today() + timedelta(days=i) for i in range(self.LIVE_WEEK_DAYS)]

        with CourtReserveSession(email_env, password_env, org_id=org_id) as sess:
            return sess.fetch_days_multi(scheduler_page_urls, days)

    def _get_replay_availability(self, day: date) -> list[TimeSlot]:
        capture_file = CAPTURE_DIR / f"court_reserve_{self.club_id}.json"

        if not capture_file.exists():
            org_id = self.club_config.get("court_reserve", {}).get("org_id")
            raise NotImplementedError(
                f"No captured CourtReserve response for '{self.club_name}' yet "
                f"(looked for {capture_file}).\n"
                f"org_id on file: {org_id or 'UNKNOWN - see README'}\n"
                "See README.md > 'Capturing the real request' for the "
                "2-minute DevTools steps, then drop the saved JSON at that path."
            )

        raw = json.loads(capture_file.read_text())
        represents_day = self._represents_day(capture_file)

        if represents_day is not None and represents_day != day:
            # We only have a one-time snapshot, not live fetching yet - it's
            # only valid for the single day it was captured for.
            raise NotImplementedError(
                f"'{self.club_name}' only has a captured snapshot for "
                f"{represents_day.isoformat()} (not live fetching yet - see README)."
            )

        return self._parse(raw, day)

    def _represents_day(self, capture_file: Path) -> date | None:
        """Which real-world day this snapshot should be shown as.

        Prefers an explicit *.meta.json override (needed when the site's
        own timestamps don't match the day the user actually meant to
        capture - e.g. a 'today' rollover quirk), falling back to the date
        embedded in the raw response's own ReservationStart values.
        """
        meta_file = capture_file.with_suffix("").with_suffix(".meta.json")
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
            override = meta.get("represents_day")
            if override:
                return date.fromisoformat(override)

        raw = json.loads(capture_file.read_text())
        for event in raw.get("Data", []):
            start = event.get("ReservationStart")
            if start:
                return datetime.fromisoformat(start).date()
        return None

    def _parse(self, raw: dict, day: date) -> list[TimeSlot]:
        courts = self.courts()
        court_by_number = {c.number: c for c in courts}
        booked: dict[int, list[tuple[time, time]]] = {c.number: [] for c in courts}

        for event in raw.get("Data", []):
            if event.get("Title") == "WAITLIST ME":
                continue  # an open-waitlist marker, not a real court reservation
            label = event.get("CourtLabel") or ""
            match = COURT_LABEL_RE.search(label)
            if not match:
                continue
            court_num = int(match.group(1))
            if court_num not in court_by_number:
                continue
            start_str = event.get("ReservationStart")
            end_str = event.get("ReservationEnd")
            if not start_str or not end_str:
                continue
            # Only the time-of-day matters - the captured snapshot's own
            # date may not match `day` (see _represents_day / the .meta.json
            # override), so we deliberately ignore the date component here.
            booked[court_num].append(
                (datetime.fromisoformat(start_str).time(), datetime.fromisoformat(end_str).time())
            )

        slots: list[TimeSlot] = []
        for court in courts:
            cursor = datetime.combine(day, time(OPEN_HOUR, 0))
            close = datetime.combine(day, time(CLOSE_HOUR, 0))
            step = timedelta(minutes=court.slot_minutes)
            while cursor < close:
                end = cursor + step
                overlaps = any(
                    cursor.time() < b_end and end.time() > b_start
                    for b_start, b_end in booked[court.number]
                )
                slots.append(
                    TimeSlot(
                        court=court,
                        day=day,
                        start=cursor.time(),
                        end=end.time(),
                        status="booked" if overlaps else "available",
                    )
                )
                cursor = end

        return slots
