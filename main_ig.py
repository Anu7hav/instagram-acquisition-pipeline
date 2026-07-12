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
    """Load and deduplicate account usernames from file."""
    with open(ACCOUNTS_FILE, "r") as f:
        raw_accounts = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    accounts = list(dict.fromkeys(raw_accounts))
    if len(accounts) < len(raw_accounts):
        log.warning(f"Removed {len(raw_accounts) - len(accounts)} duplicate accounts")
    log.info(f"Loaded {len(accounts)} account(s) from {ACCOUNTS_FILE}")
    return accounts


def run_pipeline(accounts, run_number):
    """Run one full pipeline pass over all accounts."""
    log.info(f"{'#'*50}")
    log.info(f"RUN #{run_number} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Pipeline version: {PIPELINE_VERSION}")
    log.info(f"{'#'*50}")

    account_info = check_token()
    if not account_info:
        log.error("Stopping pipeline: token check failed.")
        return

    for account in accounts:
        log.info(f"{'='*50}")
        log.info(f"Account: '{account}'")
        log.info(f"{'='*50}")

        # NOTE: fetch_account_data currently always pulls the token's own
        # account (via the /me alias) regardless of the account_id argument
        # passed in — see fetch_ig.py's module docstring. With one
        # account per token this is fine; a genuinely multi-account setup
        # would need a token per account, which is a Graph API constraint,
        # not a limitation of this code.
        success, data = fetch_account_data()
        if not success:
            log.warning(f"Skipping account: '{account}'")
            time.sleep(QUERY_DELAY)
            continue

        save_raw(account, data)
        save_processed_ig(account, data)
        time.sleep(QUERY_DELAY)

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
