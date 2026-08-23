"""
main_ig.py -- Instagram acquisition pipeline entry point.
Equivalent of main.py (Twitter branch). Same scope: fetch + save_raw +
save_processed only -- NLP/analysis/charts stay separate manual scripts.

Key differences from main.py:
  - Reads accounts.txt instead of queries.txt -- must be an IG
    Business/Creator account you actually have tester/admin access to.
  - No pagination toggle -- fetch_ig.py always paginates internally.
  - check_token() replaces check_credits().

TOKEN REFRESH (added per mentor instruction, 2026-08-03): before each run,
checks how many days remain on the current token (via
ig_client.get_token_days_remaining()). If below IG_MIN_TOKEN_DAYS_REMAINING
(config.py), refreshes automatically before continuing -- required for
unattended multi-day scheduler runs, since the token would otherwise
silently expire mid-window with no one there to notice.

RUN LOGGING (added per mentor instruction, 2026-08-03): every run attempt
(success or failure) is recorded via run_logger.log_attempt(), so a
multi-day unattended run produces a complete record, not just terminal
output that scrolls away. This includes token-refresh failures, which are
now logged (not just printed) and treated as a run-stopping condition.
"""

import logging
import time
from datetime import datetime
from config import *
from fetch_ig import fetch_account_data
from save_raw import save_raw
from save_processed_ig import save_processed_ig
from ig_client import check_token, get_token_days_remaining, refresh_long_lived_token
from run_logger import log_attempt, classify_error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

ACCOUNTS_FILE = "accounts.txt"


def load_accounts():
    """Load and deduplicate account usernames from file. Rejects >1
    account outright -- a Business Login token is tied to exactly one
    account, fetch_ig.py always pulls the token's own account via /me
    regardless of what's configured here."""
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


def ensure_token_fresh():
    """Check remaining token validity; refresh if below threshold. Logs
    clearly whenever a refresh happens (old expiry vs new expiry -- the
    actual before/after numbers are logged inside refresh_long_lived_token()
    itself). Returns True if the token is fine to proceed with, False if
    a needed refresh failed (caller should stop rather than proceed on a
    token that may expire imminently).

    A failed refresh is also recorded via log_attempt() (not just printed
    to the terminal), so it shows up in run_log.jsonl and in summarize()
    -- otherwise a multi-day unattended run could hit this repeatedly with
    no record of it anywhere but scrolled-away terminal output."""
    days_remaining = get_token_days_remaining()
    log.info(f"Token validity check: ~{days_remaining} days remaining")

    if days_remaining < IG_MIN_TOKEN_DAYS_REMAINING:
        log.warning(
            f"Token has ~{days_remaining} days remaining, below the "
            f"{IG_MIN_TOKEN_DAYS_REMAINING}-day threshold -- refreshing now"
        )
        new_token = refresh_long_lived_token()
        if not new_token:
            log.error(
                "Token refresh FAILED. Continuing with the existing token "
                "for this run, but it may expire before the next scheduled "
                "run if this isn't resolved."
            )
            log_attempt("graph_api", "token_refresh", success=False,
                        error_type="token_or_session_invalid",
                        error_message=f"refresh_long_lived_token() returned None "
                                       f"(had ~{days_remaining}d remaining)")
            return False
    return True


def run_pipeline(accounts, run_number):
    """Run one full pipeline pass over the configured account. Verifies
    the configured account against the actual authenticated account from
    /me before saving anything -- a mismatch stops execution rather than
    silently mislabeling data."""
    log.info(f"{'#'*50}")
    log.info(f"RUN #{run_number} started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Pipeline version: {PIPELINE_VERSION}")
    log.info(f"{'#'*50}")

    if not ensure_token_fresh():
        log.error("Stopping pipeline: token refresh failed and token may expire imminently.")
        log.info(f"RUN #{run_number} completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (with error)")
        return

    account_info = check_token()
    if not account_info:
        log.error("Stopping pipeline: token check failed.")
        log_attempt("graph_api", accounts[0] if accounts else "unknown",
                    success=False, error_type="token_or_session_invalid",
                    error_message="check_token() returned None")
        return

    verified_username = account_info.get("username")
    if not verified_username:
        err = "Instagram API did not return the authenticated username."
        log_attempt("graph_api", accounts[0] if accounts else "unknown",
                    success=False, error_type="unknown", error_message=err)
        raise RuntimeError(err)

    configured_account = accounts[0]
    if configured_account != verified_username:
        err = (f"Account mismatch: configured={configured_account}, "
               f"authenticated={verified_username}")
        log_attempt("graph_api", configured_account, success=False,
                    error_type="unknown", error_message=err)
        raise ValueError(
            f"\nAccount mismatch detected!\n\n"
            f"Configured account : {configured_account}\n"
            f"Authenticated user : {verified_username}\n\n"
            "The /me endpoint always returns the account that owns "
            "the access token.\n"
            "Please either:\n"
            "  - update accounts.txt to match the authenticated account\n"
            "  - use a matching access token\n"
        )

    log.info(f"{'='*50}")
    log.info(f"Account: '{verified_username}' (verified against authenticated token)")
    log.info(f"{'='*50}")

    try:
        success, data = fetch_account_data()
    except Exception as e:
        log.error(f"Fetch raised an exception for '{verified_username}': {e}")
        log_attempt("graph_api", verified_username, success=False,
                    error_type=classify_error(e), error_message=str(e))
        log.info(f"RUN #{run_number} completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (with error)")
        return

    if not success:
        log.warning(f"Fetch failed for account: '{verified_username}'")
        log_attempt("graph_api", verified_username, success=False,
                    error_type="empty_response", error_message="fetch_account_data() returned success=False")
    else:
        save_raw(verified_username, data)
        save_processed_ig(verified_username, data)
        log_attempt("graph_api", verified_username, success=True,
                    extra={"post_count": data.get("count", 0)})

    log.info(f"RUN #{run_number} completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


accounts   = load_accounts()
run_number = 1

if not SCHEDULER_ENABLED:
    run_pipeline(accounts, run_number)
else:
    log.info(f"Scheduler enabled -- running every {RUN_INTERVAL_HOURS}h | Max runs: {'unlimited' if MAX_RUNS == 0 else MAX_RUNS}")
    while True:
        accounts = load_accounts()
        run_pipeline(accounts, run_number)

        if MAX_RUNS > 0 and run_number >= MAX_RUNS:
            log.info(f"Reached max runs ({MAX_RUNS}). Stopping.")
            break

        wait_seconds = RUN_INTERVAL_HOURS * 3600
        log.info(f"Next run in {RUN_INTERVAL_HOURS}h -- sleeping until then. Press Ctrl+C to stop.")

        try:
            time.sleep(wait_seconds)
        except KeyboardInterrupt:
            log.info("Scheduler stopped by user.")
            break

        run_number += 1
