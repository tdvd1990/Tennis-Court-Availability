"""Entry point: generate a combined availability page for the next 7 days.

Usage:
    python main.py

Reads clubs.json, pulls availability from each club (mock data for any
club still set to "mode": "mock"), writes index.html next to this
script, then - if this folder is set up as a git repo with a remote
already configured (see README.md > "Publishing to GitHub Pages") -
commits and pushes it automatically, so a browser bookmark to the
GitHub Pages URL always shows the latest run.

Named index.html (not availability.html) specifically because that's
the filename GitHub Pages serves automatically at a repo's root URL -
no extra configuration needed on GitHub's side once it's pushed there.
"""

from __future__ import annotations

import subprocess
from datetime import date, datetime
from pathlib import Path

from aggregate import get_week_availability
from render_html import render

PROJECT_DIR = Path(__file__).resolve().parent
OUT_FILE = PROJECT_DIR / "index.html"


def main() -> None:
    availability, courts_by_club = get_week_availability(date.today(), num_days=7)
    render(availability, courts_by_club, OUT_FILE)
    print(f"Wrote {OUT_FILE}")
    _publish_to_github()


def _publish_to_github() -> None:
    """Commits and pushes index.html if this folder is a git repo with a
    remote configured. Safe to call even if git isn't set up at all yet
    (one-time setup - see README.md) - it just prints why it's skipping
    rather than failing the whole run, since generating the local page
    already succeeded regardless of whether publishing does."""
    if not (PROJECT_DIR / ".git").exists():
        print(
            "Publish: not set up yet (no .git folder here) - "
            "see README.md > 'Publishing to GitHub Pages' for one-time setup. "
            "index.html was still written locally above."
        )
        return

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=PROJECT_DIR, capture_output=True, text=True
        )

    add = run("add", "index.html")
    if add.returncode != 0:
        print(f"Publish: 'git add' failed - {add.stderr.strip()}")
        return

    # Checked directly rather than by parsing git commit's human-readable
    # output (which varies: "nothing to commit, working tree clean" vs
    # "nothing added to commit but untracked files present" depending on
    # what else is in the folder) - `diff --cached --quiet` exits 0 when
    # nothing is staged for this file, 1 when something is.
    unchanged = run("diff", "--cached", "--quiet", "--", "index.html").returncode == 0
    if unchanged:
        print("Publish: no changes since last run - nothing to push.")
        return

    commit = run("commit", "-m", f"Update availability - {datetime.now().isoformat(timespec='minutes')}")
    if commit.returncode != 0:
        print(f"Publish: 'git commit' failed - {commit.stderr.strip()}")
        return

    push = run("push")
    if push.returncode != 0:
        print(
            f"Publish: 'git push' failed - {push.stderr.strip()}\n"
            "(index.html was still updated and committed locally - it'll "
            "push next successful run, or push manually with 'git push'.)"
        )
        return

    print("Publish: pushed the latest index.html to GitHub.")


if __name__ == "__main__":
    main()
