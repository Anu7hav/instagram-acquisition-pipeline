"""
ig_error_handler.py
HTTP + response-body handler for Instagram Graph API requests.
Equivalent of error_handler.py (which was written for twitterapi.io).

Graph API quirk this handles that error_handler.py didn't need to:
it can return HTTP 200 with an error payload in the JSON body (e.g. an
expired token), not just non-200 status codes -- so we always check the
parsed body for an "error" key, even on 200s.
"""

import logging

log = logging.getLogger(__name__)

_HTTP_MESSAGES = {
    400: "Bad request — check field names / params",
    401: "Invalid or expired access token",
    403: "Access denied — check permissions/scopes",
    404: "Wrong endpoint or object ID",
    429: "Rate limit exceeded — will retry",
    500: "Server error — will retry",
    502: "Bad gateway — will retry",
    503: "Service unavailable — will retry",
}

# Codes that should trigger a retry in ig_client.py (HTTP-level)
RETRY_CODES = {429, 500, 502, 503}

# Graph API error codes worth specific handling (body-level, not HTTP status)
#   code 190 = OAuthException (bad/expired token)
#     subcode 460 = password changed since token issued
#     subcode 467 = token expired
#   code 4, 17, 32, 613 = various rate-limit / throttling codes -> safe to retry
_RETRYABLE_GRAPH_CODES = {4, 17, 32, 613}
_TOKEN_EXPIRED_SUBCODES = {460, 467}


def handle_ig_response(response):
    """
    Returns (success: bool, data: dict | None).
    On failure, data may still be populated with the parsed error body plus
    internal flags (_retry, _token_expired) for ig_client.py to act on.
    """
    status = response.status_code

    try:
        body = response.json()
    except Exception as e:
        log.error(f"  Failed to parse JSON response: {e}")
        return False, None

    if isinstance(body, dict) and "error" in body:
        err = body["error"]
        code = err.get("code")
        subcode = err.get("error_subcode")
        message = err.get("message", "Unknown Graph API error")

        if code == 190 and subcode in _TOKEN_EXPIRED_SUBCODES:
            log.error(
                f"  Access token invalid/expired (code 190, subcode {subcode}): {message}. "
                f"Call ig_client.refresh_long_lived_token() or re-authenticate."
            )
            return False, {"_retry": False, "_token_expired": True, **body}

        if code in _RETRYABLE_GRAPH_CODES:
            log.warning(f"  Graph API throttling (code {code}): {message}")
            return False, {"_retry": True, **body}

        log.error(f"  Graph API error {code}/{subcode}: {message} (fbtrace_id={err.get('fbtrace_id')})")
        return False, {"_retry": False, **body}

    if status == 200:
        return True, body

    msg = _HTTP_MESSAGES.get(status, f"Unexpected error: {status}")
    level = logging.WARNING if status in RETRY_CODES else logging.ERROR
    log.log(level, f"HTTP {status}: {msg}")
    return False, body
