"""
ig_client.py -- Instagram Graph API HTTP client.
Equivalent of twitter_client.py, adapted for the Instagram Graph API
(Business Login, graph.instagram.com host).

Unlike Twitter's client, there is no fallback source here -- the official
Graph API is the only sanctioned path (see project notes on why: Instagram's
anti-scraping makes any unofficial route a ban risk).

TOKEN REFRESH (added per mentor instruction, 2026-08-03):
Meta does not expose a simple "check remaining days" endpoint for
Instagram Business Login tokens the way it does for Facebook tokens via
/debug_token. The standard pattern is to track the refresh/issue date
locally -- long-lived tokens are valid exactly 60 days from issuance or
last refresh -- and compute remaining days from that, rather than
querying Meta. State is stored in token_state.json (gitignored -- it's
a local runtime artifact, not a secret, but also not meaningful to share
across machines/environments).
"""

import requests
import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv, set_key
from ig_error_handler import handle_ig_response
from config import (
    MAX_RETRIES, RETRY_DELAY, RATE_LIMIT_DELAY, RETRY_CODES,
    IG_BASE_URL, IG_ACCOUNT_FIELDS,
)

load_dotenv()
log = logging.getLogger(__name__)

ENV_PATH = ".env"
TOKEN_STATE_FILE = "token_state.json"
TOKEN_VALIDITY_DAYS = 60  # Meta's fixed validity window for long-lived tokens

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
APP_SECRET   = os.getenv("IG_APP_SECRET")
ACCOUNT_ID   = os.getenv("IG_ACCOUNT_ID")

if not ACCESS_TOKEN:
    raise RuntimeError(
        "Instagram access token missing. Set IG_ACCESS_TOKEN in your .env file."
    )
if not ACCOUNT_ID:
    raise RuntimeError(
        "Instagram account ID missing. Set IG_ACCOUNT_ID in your .env file."
    )


def get(endpoint, params=None):
    """
    GET wrapper with retry/backoff, mirroring twitter_client.get().
    endpoint: path starting with '/', e.g. '/me' or f'/{ACCOUNT_ID}/media'
    """
    url = f"{IG_BASE_URL}{endpoint}"
    params = dict(params or {})
    params["access_token"] = ACCESS_TOKEN

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=15)

            usage_header = response.headers.get("X-Business-Use-Case-Usage")
            if usage_header:
                log.debug(f"  Rate-limit usage: {usage_header}")

            if response.status_code in RETRY_CODES:
                wait = RATE_LIMIT_DELAY if response.status_code == 429 else RETRY_DELAY
                log.warning(f"  HTTP {response.status_code}. Attempt {attempt+1}/{MAX_RETRIES} -- retrying in {wait}s...")
                time.sleep(wait)
                continue

            success, data = handle_ig_response(response)

            if not success and isinstance(data, dict) and data.get("_retry"):
                log.warning(f"  Graph API signaled retry. Attempt {attempt+1}/{MAX_RETRIES} -- retrying in {RATE_LIMIT_DELAY}s...")
                time.sleep(RATE_LIMIT_DELAY)
                continue

            return success, data

        except requests.exceptions.Timeout:
            log.warning(f"  Timeout. Attempt {attempt+1}/{MAX_RETRIES}")
        except requests.exceptions.ConnectionError:
            log.warning(f"  Connection error. Attempt {attempt+1}/{MAX_RETRIES}")
        except requests.exceptions.RequestException as e:
            log.error(f"  Request failed: {e}")

        if attempt < MAX_RETRIES - 1:
            log.info(f"  Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

    log.error("  All retry attempts failed.")
    return False, None


def get_url(full_url):
    """
    Follow an already-complete Graph API URL as-is (e.g. paging.next / .previous
    from a prior response -- these already include access_token and all params).
    Same retry/backoff behavior as get(), just skips URL construction.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(full_url, timeout=15)

            if response.status_code in RETRY_CODES:
                wait = RATE_LIMIT_DELAY if response.status_code == 429 else RETRY_DELAY
                log.warning(f"  HTTP {response.status_code}. Attempt {attempt+1}/{MAX_RETRIES} -- retrying in {wait}s...")
                time.sleep(wait)
                continue

            success, data = handle_ig_response(response)

            if not success and isinstance(data, dict) and data.get("_retry"):
                log.warning(f"  Graph API signaled retry. Attempt {attempt+1}/{MAX_RETRIES} -- retrying in {RATE_LIMIT_DELAY}s...")
                time.sleep(RATE_LIMIT_DELAY)
                continue

            return success, data

        except requests.exceptions.Timeout:
            log.warning(f"  Timeout. Attempt {attempt+1}/{MAX_RETRIES}")
        except requests.exceptions.ConnectionError:
            log.warning(f"  Connection error. Attempt {attempt+1}/{MAX_RETRIES}")
        except requests.exceptions.RequestException as e:
            log.error(f"  Request failed: {e}")

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)

    log.error("  All retry attempts failed (pagination request).")
    return False, None


def check_token():
    """
    Verify the access token is alive by hitting /me.
    Returns the account info dict, or None if the check fails.
    """
    success, data = get("/me", {"fields": IG_ACCOUNT_FIELDS})
    if success:
        log.info(
            f"  Token OK -- @{data.get('username')} ({data.get('account_type')}), "
            f"{data.get('media_count')} media"
        )
        return data
    log.error("  Token check failed -- access token may be invalid or expired.")
    return None


def _load_token_state():
    """Returns the recorded refresh datetime, or None if no record exists
    (e.g. first run since this feature was added -- the current token's
    true issuance date is unknown, so we can't compute real remaining days
    yet)."""
    if not os.path.exists(TOKEN_STATE_FILE):
        return None
    try:
        with open(TOKEN_STATE_FILE, "r") as f:
            state = json.load(f)
        return datetime.fromisoformat(state["refreshed_at"])
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        log.warning(f"  Could not read {TOKEN_STATE_FILE}: {e} -- treating as no record")
        return None


def _save_token_state(refreshed_at: datetime):
    with open(TOKEN_STATE_FILE, "w") as f:
        json.dump({"refreshed_at": refreshed_at.isoformat()}, f)


def get_token_days_remaining():
    """
    Returns estimated days remaining on the current token, computed from
    the locally tracked refresh date -- NOT queried from Meta (no such
    endpoint exists for this token type). If no refresh has been recorded
    yet (e.g. first run with this feature), seeds the state file with
    NOW as a conservative assumption (treats the token as freshly issued
    -- safe because it only delays refresh, never causes an unexpected
    expiry) and logs this clearly so it's not mistaken for a real
    historical record.
    """
    refreshed_at = _load_token_state()
    if refreshed_at is None:
        now = datetime.now(timezone.utc)
        _save_token_state(now)
        log.warning(
            f"  No token issuance record found in {TOKEN_STATE_FILE} -- "
            f"seeding with current time as a conservative assumption "
            f"(actual token may be older; this only makes refresh trigger "
            f"earlier than strictly necessary, never later)."
        )
        return TOKEN_VALIDITY_DAYS

    elapsed = datetime.now(timezone.utc) - refreshed_at
    remaining = TOKEN_VALIDITY_DAYS - elapsed.days
    return remaining


def refresh_long_lived_token():
    """
    Refresh the long-lived token for another 60 days, AND actually put the
    new token into effect:
      1. Updates the in-memory ACCESS_TOKEN used by get()/get_url() for
         the rest of this process's lifetime
      2. Persists the new token to .env (via python-dotenv's set_key) so
         future process starts pick it up too
      3. Records the refresh timestamp in token_state.json so
         get_token_days_remaining() reflects the new expiry

    Returns the new token string, or None on failure (in which case
    nothing is changed -- the old token remains in effect).
    """
    global ACCESS_TOKEN

    url = f"{IG_BASE_URL}/refresh_access_token"
    params = {"grant_type": "ig_refresh_token", "access_token": ACCESS_TOKEN}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)

            if not new_token:
                log.error(f"  Token refresh response missing access_token: {data}")
                return None

            old_days_remaining = get_token_days_remaining()

            ACCESS_TOKEN = new_token
            set_key(ENV_PATH, "IG_ACCESS_TOKEN", new_token)
            now = datetime.now(timezone.utc)
            _save_token_state(now)

            new_days = expires_in // 86400
            log.info(
                f"  Token refreshed successfully. "
                f"Old expiry: ~{old_days_remaining}d remaining -> "
                f"New expiry: ~{new_days}d remaining (until ~{(now + timedelta(seconds=expires_in)).date()})"
            )
            return new_token

        log.error(f"  Token refresh failed: HTTP {resp.status_code} -- {resp.text}")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"  Token refresh request failed: {e}")
        return None
