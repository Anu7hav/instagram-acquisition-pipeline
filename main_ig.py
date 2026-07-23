"""
main_ig.py — Instagram acquisition pipeline entry point.
Equivalent of main.py (Twitter branch). Same scope: fetch + save_raw +
save_processed only — NLP/analysis/charts stay separate manual scripts
(preprocess_ig.py / analysis_ig.py / visualise_ig.py / sentiment_report_ig.py),
exactly as they are on the Twitter branch too.

Key differences from main.py:
  - Reads accounts.txt instead of queries.txt — IMPORTANT: unlike Twitter
    queries (arbitrary search terms), these must be IG Business/Creator
    accounts you actually have tester/admin access to. Adding a random
    username here will fail, not just return empty results.
  - No pagination toggle / USE_PAGINATION — fetch_ig.py always paginates
    internally now (see the pagination fix), so there's no fetch_all_pages
    equivalent needed here.
  - check_token() replaces check_credits() — Graph API doesn't have a
    credit-balance concept, just token validity.

Scheduler behavior (RUN_INTERVAL_HOURS, MAX_RUNS, SCHEDULER_ENABLED) reuses
the exact same config.py settings the Twitter branch already defines.
"""

import logging
import time
from datetime import datetime
from config import *
from fetch_ig import fetch_account_data
from save_raw import save_raw
from save_processed_ig import save_processed_ig
from ig_client import check_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

ACCOUNTS_FILE = "accounts.txt"


def load_accounts():
    """Load and deduplicate account usernames from file.

    BUG FIX (mentor review): a Business Login token is tied to exactly ONE
    account — fetch_ig.py always pulls the token's own account via /me
    regardless of what's configured here. Previously accounts.txt could
    silently list multiple usernames with no warning that only one would
    ever actually be used. Now rejects >1 account outright rather than
    silently ignoring the rest.
    """
    with open(ACCOUNTS_FILE, "r") as f:
        raw_accounts = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    accounts = list(dict.fromkeys(raw_accounts))
    if len(accounts) < len(raw_accounts):
        log.warning(f"Removed {len(raw_accounts) - len(accounts)} duplicate accounts")

    if len(accounts) > 1:
        raise RuntimeError(
            "This Instagram acquisition pipeline currently supports "
            "only one authenticated account per access token.\n"
            "Please keep only one account in accounts.txt."
        )

    log.info(f"Loaded {len(accounts)} account(s) from {ACCOUNTS_FILE}")
    return accounts


def run_pipeline(accounts, run_number):
    """Run one full pipeline pass over the configured account.

    BUG FIX (mentor review): previously used the configured account name
    from accounts.txt directly for save_raw/save_processed_ig, trusting it
    blindly. Now verifies it against the actual authenticated username
    from /me and stops execution on any mismatch — the /me endpoint always
    returns the account that owns the access token, so a mismatch means
    accounts.txt and the .env token don't agree, which would otherwise
    silently mislabel data under the wrong account name.
    """
    log.info(f"{'#'*50}")
    log.info(f"RUN #{run_number} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Pipeline version: {PIPELINE_VERSION}")
    log.info(f"{'#'*50}")

    account_info = check_token()
    if not account_info:
        log.error("Stopping pipeline: token check failed.")
        return

    verified_username = account_info.get("username")
    if not verified_username:
        raise RuntimeError(
            "Instagram API did not return the authenticated username."
        )

    configured_account = accounts[0]
    if configured_account != verified_username:
        raise ValueError(
            f"\nAccount mismatch detected!\n\n"
            f"Configured account : {configured_account}\n"
            f"Authenticated user : {verified_username}\n\n"
            "The /me endpoint always returns the account that owns "
            "the access token.\n"
            "Please either:\n"
            "  • update accounts.txt to match the authenticated account\n"
            "  • use a matching access token\n"
        )

    log.info(f"{'='*50}")
    log.info(f"Account: '{verified_username}' (verified against authenticated token)")
    log.info(f"{'='*50}")

    # NOTE: fetch_account_data currently always pulls the token's own
    # account (via the /me alias) — see fetch_ig.py's module docstring.
    # With the verification above, we now know verified_username is
    # genuinely the account being fetched, not just an assumption.
    success, data = fetch_account_data()
    if not success:
        log.warning(f"Fetch failed for account: '{verified_username}'")
    else:
        save_raw(verified_username, data)
        save_processed_ig(verified_username, data)

    log.info(f"RUN #{run_number} completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


accounts   = load_accounts()
run_number = 1

if not SCHEDULER_ENABLED:
    run_pipeline(accounts, run_number)
else:
    log.info(f"Scheduler enabled — running every {RUN_INTERVAL_HOURS}h | Max runs: {'∞' if MAX_RUNS == 0 else MAX_RUNS}")
    while True:
        accounts = load_accounts()
        run_pipeline(accounts, run_number)

        if MAX_RUNS > 0 and run_number >= MAX_RUNS:
            log.info(f"Reached max runs ({MAX_RUNS}). Stopping.")
            break

        wait_seconds = RUN_INTERVAL_HOURS * 3600
        log.info(f"Next run in {RUN_INTERVAL_HOURS}h — sleeping until then. Press Ctrl+C to stop.")

        try:
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            log.info("Scheduler stopped by user.")
            break

        run_number += 1
