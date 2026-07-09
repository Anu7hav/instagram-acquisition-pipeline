"""
ig_client.py — Instagram Graph API HTTP client.
Equivalent of twitter_client.py, adapted for the Instagram Graph API
(Business Login, graph.instagram.com host).

Unlike Twitter's client, there is no fallback source here — the official
Graph API is the only sanctioned path (see project notes on why: Instagram's
anti-scraping makes any unofficial route a ban risk).
"""

import requests
import os
import time
import logging
from dotenv import load_dotenv
from ig_error_handler import handle_ig_response
from config import (
    MAX_RETRIES, RETRY_DELAY, RATE_LIMIT_DELAY, RETRY_CODES,
    IG_BASE_URL, IG_ACCOUNT_FIELDS,
)

load_dotenv()
log = logging.getLogger(__name__)

ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
APP_SECRET   = os.getenv("IG_APP_SECRET")
ACCOUNT_ID   = os.getenv("IG_ACCOUNT_ID")

# Fail fast — same convention as twitter_client.py's API_KEY check
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

            # Graph API surfaces rate-limit usage here when you're close to quota —
            # logged for now; config.py's IG_MIN_TOKEN_DAYS_REMAINING-style throttling
            # off this header is a later refinement, not needed for MVP.
            usage_header = response.headers.get("X-Business-Use-Case-Usage")
            if usage_header:
                log.debug(f"  Rate-limit usage: {usage_header}")

            if response.status_code in RETRY_CODES:
                wait = RATE_LIMIT_DELAY if response.status_code == 429 else RETRY_DELAY
                log.warning(f"  HTTP {response.status_code}. Attempt {attempt+1}/{MAX_RETRIES} — retrying in {wait}s...")
                time.sleep(wait)
                continue

            success, data = handle_ig_response(response)

            # Graph API can return HTTP 200 with a throttling error in the body —
            # handle_ig_response flags these via data["_retry"]
            if not success and isinstance(data, dict) and data.get("_retry"):
                log.warning(f"  Graph API signaled retry. Attempt {attempt+1}/{MAX_RETRIES} — retrying in {RATE_LIMIT_DELAY}s...")
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


def check_token():
    """
    Verify the access token is alive by hitting /me.
    Returns the account info dict, or None if the check fails.
    Equivalent role to check_credits() in twitter_client.py — call this
    before a pipeline run, not on every request.
    """
    success, data = get("/me", {"fields": IG_ACCOUNT_FIELDS})
    if success:
        log.info(
            f"  ✓ Token OK — @{data.get('username')} ({data.get('account_type')}), "
            f"{data.get('media_count')} media"
        )
        return data
    log.error("  ✗ Token check failed — access token may be invalid or expired.")
    return None


def refresh_long_lived_token():
    """
    Refresh the long-lived token for another 60 days.
    Long-lived tokens are NOT auto-renewed by Meta — call this on a schedule
    (e.g. weekly) well before the 60-day expiry, not just when a call fails.
    Returns the new token string, or None on failure.
    """
    url = f"{IG_BASE_URL}/refresh_access_token"
    params = {"grant_type": "ig_refresh_token", "access_token": ACCESS_TOKEN}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)
            log.info(f"  ✓ Token refreshed — expires in ~{expires_in // 86400} days")
            return new_token
        log.error(f"  ✗ Token refresh failed: HTTP {resp.status_code} — {resp.text}")
        return None
    except requests.exceptions.RequestException as e:
        log.error(f"  ✗ Token refresh request failed: {e}")
        return None
