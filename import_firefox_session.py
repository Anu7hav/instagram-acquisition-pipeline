"""
import_firefox_session.py — imports Instagram session cookies directly from
Firefox into Instaloader, bypassing Instaloader's own --login flow entirely.

Why: Instaloader's built-in login procedure is what triggered repeated
Instagram security checkpoints on mea7.singh. This script sidesteps that
by reusing a session you already authenticated normally, through the
actual Firefox browser — nothing automated touches the login itself.

Adapted from Instaloader's own official troubleshooting documentation:
https://instaloader.github.io/troubleshooting.html

BEFORE RUNNING THIS:
1. Log into Instagram completely normally in Firefox — a fresh throwaway
   account, not one that's already hit checkpoints tonight.
2. Make sure you're actually logged in and can browse Instagram normally
   in that Firefox window.
3. Close Firefox is NOT required, but the cookies.sqlite file must not be
   locked — if this script fails with a database lock error, close
   Firefox first and retry.

Usage:
    python import_firefox_session.py
"""

from glob import glob
from os.path import expanduser
from platform import system
from sqlite3 import OperationalError, connect

try:
    from instaloader import ConnectionException, Instaloader
except ModuleNotFoundError:
    raise SystemExit("Instaloader not found.\n  pip install instaloader")


import os


def get_cookiefile():
    candidates = []

    # Standard desktop Firefox install
    standard_pattern = {
        "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
        "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
    }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")
    candidates.extend(glob(expanduser(standard_pattern)))

    # Microsoft Store Firefox — sandboxed under LOCALAPPDATA\Packages\...
    if system() == "Windows":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        packages_dir = os.path.join(localappdata, "Packages")
        if os.path.isdir(packages_dir):
            for entry in os.listdir(packages_dir):
                if entry.startswith("Mozilla.Firefox"):
                    ms_store_pattern = os.path.join(
                        packages_dir, entry,
                        "LocalCache", "Roaming", "Mozilla", "Firefox",
                        "Profiles", "*", "cookies.sqlite"
                    )
                    candidates.extend(glob(ms_store_pattern))

    if not candidates:
        raise SystemExit(
            "No Firefox cookies.sqlite file found (checked both standard "
            "and Microsoft Store install locations). Make sure Firefox is "
            "installed and you've logged into Instagram at least once."
        )

    # If multiple profiles/cookie files exist, use the most recently
    # modified one — almost certainly the one just used to log in
    newest = max(candidates, key=os.path.getmtime)
    if len(candidates) > 1:
        print(f"Found {len(candidates)} cookie files, using the most recently used one:")
        print(f"  {newest}")
    return newest


def import_session(cookiefile, sessionfile=None):
    print(f"Using cookies from {cookiefile}")
    conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
    try:
        cookie_data = conn.execute(
            "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
        )
    except OperationalError:
        cookie_data = conn.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
        )

    L = Instaloader(max_connection_attempts=1)
    L.context._session.cookies.update(cookie_data)
    username = L.test_login()

    if not username:
        raise SystemExit(
            "Not logged in. Make sure you're actually logged into Instagram "
            "in Firefox right now, then retry."
        )

    print(f"✓ Imported session cookie for @{username}")
    L.context.username = username
    L.save_session_to_file(sessionfile)
    print(f"✓ Session saved — Instaloader can now use --login={username} "
          f"without triggering its own login flow.")


if __name__ == "__main__":
    try:
        import_session(get_cookiefile())
    except (ConnectionException, OperationalError) as e:
        raise SystemExit(f"Cookie import failed: {e}")
