"""Renders the aggregated availability into a single self-contained HTML
file: one page, a tab per day, a grid of every court from every club.

Time resolution is 30 minutes (the finest granularity in use, on Sir
Winston Churchill's Courts 1-5) - hourly courts just occupy two stacked
half-hour cells, which is what makes courts on different booking
granularities comparable at a glance.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

from models import TimeSlot

SLOT_MINUTES = 30
GRID_START = time(7, 0)
GRID_END = time(23, 0)


def _time_rows() -> list[time]:
    rows = []
    cursor = GRID_START
    while cursor < GRID_END:
        rows.append(cursor)
        total_minutes = cursor.hour * 60 + cursor.minute + SLOT_MINUTES
        cursor = time(total_minutes // 60, total_minutes % 60)
    return rows


def _status_at(slots: list[TimeSlot], row_time: time) -> str:
    for s in slots:
        if s.start <= row_time < s.end:
            return s.status
    return "unknown"


def _format_time_label(t: time) -> str:
    """"7:00 AM" style, no leading zero on the hour. strftime's no-leading-
    zero flag is spelled "%-I" on Linux/Mac but "%#I" on Windows - neither
    works on both, so this formats it by hand instead (this is what broke
    on Windows: %-I raised ValueError there)."""
    hour12 = t.hour % 12 or 12
    ampm = "AM" if t.hour < 12 else "PM"
    return f"{hour12}:{t.minute:02d} {ampm}"


def _format_day_label(d: date) -> str:
    """"Mon Aug 31" style - same cross-platform issue as above (%-d), so
    the day number is appended manually instead of via strftime."""
    return f'{d.strftime("%a %b")} {d.day}'


def render(
    availability: dict[str, dict[date, list[TimeSlot]]],
    courts_by_club: dict[str, list],
    out_path: Path,
) -> None:
    club_names = list(availability.keys())
    all_days = sorted(next(iter(availability.values())).keys()) if availability else []

    # courts_by_club comes from clubs.json (via aggregate.py), not from
    # whatever TimeSlots happened to come back this run - deliberately.
    # It used to be derived from day 0's slots instead, which meant a
    # club whose live fetch failed for every day (e.g. Churchill hitting
    # a Cloudflare/selector snag) lost its columns from the page
    # entirely, rather than showing them hatched/unknown like every
    # other "not available yet" cell. A club's set of real courts
    # doesn't change day to day, so it shouldn't depend on a live fetch
    # having succeeded at all.
    courts_by_club = {
        name: sorted(courts, key=lambda c: c.number)
        for name, courts in courts_by_club.items()
    }
    total_courts = sum(len(courts) for courts in courts_by_club.values())

    rows = _time_rows()

    day_sections = []
    for day_idx, day in enumerate(all_days):
        cols_html = []
        all_court_slots = []  # every court's slot list, for the Open count column
        for club_name in club_names:
            for court in courts_by_club.get(club_name, []):
                day_slots = availability[club_name].get(day, [])
                court_slots = [s for s in day_slots if s.court.number == court.number]
                all_court_slots.append(court_slots)
                cells = []
                for row_time in rows:
                    status = _status_at(court_slots, row_time)
                    cells.append(f'<div class="cell {status}"></div>')
                cols_html.append(
                    f'<div class="court-col">'
                    f'<div class="court-head">{court.display_name}</div>'
                    f'{"".join(cells)}'
                    f"</div>"
                )

        time_labels = "".join(
            f'<div class="time-label">{_format_time_label(t)}</div>' for t in rows
        )

        # How many courts (across every club shown) are available at each
        # row's start time - a quick "best odds" glance without reading
        # every column. Counts only "available" slots, out of however
        # many courts are actually on the page (mock/hatched-unknown
        # courts don't count as open).
        open_counts = "".join(
            f'<div class="time-label open-count">'
            f'{sum(1 for cs in all_court_slots if _status_at(cs, row_time) == "available")}'
            f"</div>"
            for row_time in rows
        )

        day_sections.append(
            f'<section class="day" id="day-{day_idx}" style="display:{"block" if day_idx == 0 else "none"}">'
            f'<div class="grid">'
            f'<div class="court-col time-col"><div class="court-head"></div>{time_labels}</div>'
            f'<div class="court-col open-col"><div class="court-head">Open /{total_courts}</div>{open_counts}</div>'
            f'{"".join(cols_html)}'
            f"</div></section>"
        )

    tabs = "".join(
        f'<button class="tab" onclick="showDay({i})" id="tab-{i}">'
        f'{_format_day_label(d)}</button>'
        for i, d in enumerate(all_days)
    )

    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Court Availability</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif; margin: 0; padding: 24px;
          background: #f7f7f5; color: #1a1a1a; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  p.sub {{ color: #666; margin: 0; font-size: 13px; }}
  .titlebar {{ display: flex; align-items: flex-start; justify-content: space-between;
               gap: 12px; margin-bottom: 20px; }}
  .reload-btn {{ padding: 8px 14px; border: 1px solid #ddd; background: white; border-radius: 6px;
                 cursor: pointer; font-size: 13px; color: #333; flex-shrink: 0; white-space: nowrap; }}
  .reload-btn:hover {{ background: #f2f2f2; }}
  .tabs {{ display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tab {{ padding: 8px 14px; border: 1px solid #ddd; background: white; border-radius: 6px;
          cursor: pointer; font-size: 13px; }}
  .tab.active {{ background: #2563eb; color: white; border-color: #2563eb; }}
  .grid {{ display: flex; overflow-x: auto; border: 1px solid #e2e2e2; border-radius: 8px;
           background: white; }}
  .court-col {{ display: flex; flex-direction: column; min-width: 92px; border-right: 1px solid #eee; }}
  .time-col {{ min-width: 68px; flex-shrink: 0; position: sticky; left: 0; z-index: 2;
               background: white; }}
  .open-col {{ min-width: 54px; flex-shrink: 0; position: sticky; left: 68px; z-index: 2;
               background: white; box-shadow: 2px 0 4px -2px rgba(0,0,0,0.15); }}
  .court-head {{ font-size: 11px; font-weight: 600; padding: 6px 4px; text-align: center;
                 border-bottom: 2px solid #ddd; height: 32px; display: flex; align-items: center;
                 justify-content: center; line-height: 1.2; }}
  .time-label {{ font-size: 11px; color: #888; height: 22px; display: flex; align-items: center;
                 padding-left: 6px; border-bottom: 1px solid #f2f2f2; }}
  .open-count {{ padding-left: 0; justify-content: center; font-weight: 700; color: #16a34a; }}
  .cell {{ height: 22px; border-bottom: 1px solid #f2f2f2; }}
  .cell.available {{ background: #4ade80; }}
  .cell.booked {{ background: #fee2e2; }}
  .cell.unknown {{ background: repeating-linear-gradient(45deg,#f4f4f4,#f4f4f4 4px,#ececec 4px,#ececec 8px); }}
  .legend {{ display: flex; gap: 16px; margin-top: 14px; font-size: 12px; color: #555; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
  .swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
</style>
</head>
<body>
  <div class="titlebar">
    <div>
      <h1>Court Availability — All Clubs</h1>
      <p class="sub">Sir Winston Churchill · Old Mill · Mimico · 10XTO — generated {datetime.now().strftime("%a %b")} {datetime.now().day}, {_format_time_label(datetime.now().time())}</p>
    </div>
    <button class="reload-btn" onclick="location.href = location.pathname + '?t=' + Date.now()">&#8635; Reload</button>
  </div>
  <div class="tabs">{tabs}</div>
  {"".join(day_sections)}
  <div class="legend">
    <span><span class="swatch" style="background:#4ade80"></span> Available</span>
    <span><span class="swatch" style="background:#fee2e2"></span> Booked</span>
    <span><span class="swatch" style="background:repeating-linear-gradient(45deg,#f4f4f4,#f4f4f4 4px,#ececec 4px,#ececec 8px)"></span> Unknown / not yet live</span>
  </div>
<script>
function showDay(i) {{
  document.querySelectorAll('.day').forEach((el, idx) => el.style.display = idx === i ? 'block' : 'none');
  document.querySelectorAll('.tab').forEach((el, idx) => el.classList.toggle('active', idx === i));
}}
showDay(0);
</script>
</body>
</html>"""

    # Explicit encoding="utf-8" matters here: the page declares utf-8 in
    # its <meta charset>, but write_text()'s default encoding is the OS's
    # locale encoding - on Windows that's usually cp1252, not utf-8. That
    # mismatch is what turned the em dashes in the title into "?" boxes.
    out_path.write_text(html, encoding="utf-8")
