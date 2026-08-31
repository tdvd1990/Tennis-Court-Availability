# Court Availability

A single page showing court availability across every club you play at:
Sir Winston Churchill Tennis Club, Old Mill, and Mimico (all CourtReserve),
plus 10XTO (Club Automation).

## What this is right now

Sir Winston Churchill, Mimico, and 10XTO are still on mock data
(`"mode": "mock"` in `clubs.json`) — realistic, but not real.

**Old Mill is real.** It's set to `"mode": "replay"`, which parses an
actual captured CourtReserve response (`capture/court_reserve_old_mill.json`)
and shows genuine bookings for Monday, Aug 31, 2026 — the day the capture
was taken for. Every other day still falls back to "unknown" (hatched
cells) for Old Mill, because this is a one-time snapshot, not a live
fetch — see "From replay to live" below.

`python3 main.py` runs immediately with no setup and no credentials —
mock clubs generate fresh fake data every run, Old Mill replays its one
real snapshot.

Nothing books anything yet. That's a real, tractable next step, but
needs a short bit of your help first (see "About the 'book directly from
the app' part" below) since booking pages can't be safely
reverse-engineered from a script running somewhere I can't see your
actual browser session.

## Run it

```
pip install -r requirements.txt   # only needed once, for live_session.py
python3 main.py
```

Opens `availability.html` in your browser — one tab per day, one column
per court, green = available / red = booked (a hatched cell means that
club isn't live yet and mock/real data wasn't available for that slot).

## Project layout

- `clubs.json` — one entry per club: which vendor it uses, its courts,
  and each court's booking granularity. Old Mill and Mimico have
  `org_id: null` — see below.
- `models.py` — the shared `Court` / `TimeSlot` shape every adapter
  produces, regardless of vendor.
- `adapters/` — one file per booking vendor. `mock.py` is fully working.
  `court_reserve.py` and `club_automation.py` are real skeletons: correct
  interface, clear TODOs, just waiting on a captured sample response.
- `aggregate.py` — pulls each club's availability and assembles the week.
- `render_html.py` / `main.py` — builds `availability.html`.

## Making a club "live"

Each club in `clubs.json` has `"mode": "mock"`. To make one real:

### 1. Capture the real request (2 minutes, in your own logged-in browser)

1. Log into the club's booking site normally (e.g.
   `app.courtreserve.com` for CourtReserve, or
   `10xtoronto.clubautomation.com` for 10XTO).
2. Open DevTools → **Network** tab, filter to **Fetch/XHR**.
3. Click a date on the booking calendar so it loads that day's courts.
4. Find the request that returned the court/slot data (usually the
   largest JSON response right after you click). Right-click it →
   **Copy → Copy Response**.
5. Save that JSON as:
   - CourtReserve: `capture/court_reserve_swcptc.json`,
     `capture/court_reserve_old_mill.json`, or
     `capture/court_reserve_mimico.json`
   - Club Automation: `capture/club_automation_10xto.json`
6. Also note the request's **URL** and **headers** (right-click → Copy →
   Copy as cURL is easiest) — paste that into a message to me, or into a
   `capture/*_request.txt` file next to the JSON. That's what lets me
   wire up *live*, repeated fetching (not just parsing one saved
   snapshot).

### 2. Club IDs — all confirmed

- **Sir Winston Churchill**: CourtReserve `org_id` `6817`
- **Old Mill**: CourtReserve `org_id` `16627`
- **Mimico**: CourtReserve `org_id` `6034`
- **10XTO**: `10xtoronto.clubautomation.com`

All four are already filled in in `clubs.json`. Nothing left to look up —
the only remaining step per club is the capture below.

### 3. What happens once a capture file exists

For CourtReserve this is done — `adapters/court_reserve.py` parses the
real Kendo-grid response shape (confirmed from Old Mill's capture):
`{"Data": [...]}`, where each item is either a real reservation
(`CourtLabel: "Court #3"`, local-time `ReservationStart`/`ReservationEnd`)
or a per-half-hour "WAITLIST ME" placeholder that gets filtered out. The
actual slot grid isn't returned directly — it's inferred by generating
every possible slot for each court and marking it booked if a real
reservation overlaps it.

For Club Automation (10XTO), the shape is still an unconfirmed guess in
`adapters/club_automation.py` — same idea, needs one real capture to
adjust the field names.

### From replay to live

A capture file is a single frozen snapshot of one day. Two things about
that are worth knowing:

- **Sanity-check the date.** CourtReserve's own timestamps aren't always
  the day you think you captured — Old Mill's capture read as
  2026-09-01 in the raw JSON, but was actually Monday 2026-08-31's grid.
  A `capture/*.meta.json` file next to the capture (see
  `court_reserve_old_mill.meta.json`) can override which real day a
  snapshot represents, independent of what the raw JSON's dates say.
- **It only ever answers for that one day** — every other day in the
  week falls back to "unknown" until either a fresh capture is dropped
  in for that day, or real live fetching is built.

Live fetching (an authenticated `requests.Session` that logs in and
pulls fresh data every run, instead of replaying one saved file) isn't
built yet — `live_session.py` is the skeleton for it, waiting on two
captures.

### Capturing the login request

**Never paste your actual password into chat with me.** Redact it as
described in step 5 below — I only need the *shape* of the request
(the URL, the field names, whether there's a hidden anti-forgery
token), not the real value. Your real password only ever goes into a
local `.env` file (copy `.env.example` to `.env`) that stays on your
machine and that I never see.

1. Open a **private/incognito** browser window, so you start fully
   logged out (a normal window that's already logged in won't show the
   login request at all).
2. Go to Old Mill's login page:
   `https://app.courtreserve.com/Online/Account/LogIn/16627`
3. Open DevTools → **Network** tab. Check **"Preserve log"** (important —
   logging in navigates to a new page, which normally clears the network
   list right when you need it).
4. Enter your real email and password and click Login.
5. Find the request that fired when you clicked Login (usually near the
   top of the list once "Preserve log" is on — often named something
   like "LogIn"). Right-click it → **Copy → Copy as cURL**.
6. **Before pasting it to me**: find your password's value in the
   copied text and replace it with the word `REDACTED`, keeping
   everything else (including the field name next to it, e.g.
   `Password=REDACTED`) intact. Then paste the whole thing here.
7. Now that you're logged in, repeat the earlier capture: click a date
   on the booking calendar, find the request that returns the day's
   JSON (same one as before), right-click → Copy as cURL, and paste
   that one to me in full — no redaction needed, it doesn't contain
   your password.

**Update:** the login request is captured and wired up. Two things it
revealed, worth knowing:

- Old Mill's CourtReserve sits behind **Cloudflare bot protection**
  (its cookies included `cf_clearance` / `__cf_bm`). A plain HTTP
  request (Python's `requests` library) would very likely get a
  Cloudflare challenge page back instead of actually logging in -
  Cloudflare's JS challenge needs a real browser to solve. So
  `live_session.py` uses **Playwright** (a real, scriptable Chromium
  browser) to load the login page first, then makes the same JSON login
  call the real site makes (`POST .../Account/Login?id=16627` with
  `{"IsApiCall": true, "UserNameOrEmail", "Password"}`) through that
  browser's context, so it carries the right cookies automatically.
- The frontend logs in via a JSON API call, not a classic HTML form -
  so there's no form field to click, which sidesteps needing to know
  exact input selectors.

Run `pip install -r requirements.txt` then, once, `playwright install
chromium` to get a browser Playwright can drive.

**Update 2:** the actual scheduler data request is identified too -
`GET https://backend.courtreserve.com/api/scheduler/member-expanded`.
Its `jsonData` param decoded to real, useful config (our 4 real courts
+ the WAITLIST pseudo-court, hourly interval, your Old Mill member id).
But its other param, `RequestData`, is an opaque encrypted/signed blob -
clearly generated by CourtReserve's own frontend JavaScript, not
something safe to hand-construct (reverse-engineering an encryption
scheme we haven't seen the code for is a good way to build something
that silently breaks). So `live_session.py` takes the more robust path:
navigate a real, logged-in browser to the actual scheduler page and
capture whatever response it gets back, rather than building the
request by hand.

**Still needed - the scheduler page's URL (step 7):** just the URL in
your browser's address bar when you're looking at Old Mill's actual
booking calendar (the page with the date picker and the 4 courts) - not
an API request this time, just the plain page URL. Nothing sensitive in
it, safe to paste in full.

Once that's in, `live_session.py`'s last TODO (`SCHEDULER_PAGE_URL`)
gets filled in and `python3 live_session.py` becomes a real script:
logs in with the credentials from your local `.env`, opens the
scheduler page, and returns today's real availability - no more manual
captures needed for that. (Picking an arbitrary day, not just today, is
the natural next step after that works - see the "current limitation"
note in `live_session.py`.)

## About the "book directly from the app" part

Worth flagging plainly rather than glossing over: automating the actual
booking step (not just viewing) means storing your login/session for
four systems and scripting the exact submit request — and most booking
platforms' terms of service technically prohibit automated/bot access,
even for a personal single-user tool like this one. It's very doable
technically, and I'm glad to build it, but it's worth doing only after
Phase 1 (live viewing) is solid, and worth a quick gut-check from you on
the ToS/reliability tradeoff before we wire up real "Book" buttons.
