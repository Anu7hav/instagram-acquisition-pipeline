"""
fetch_ig.py — pulls posts and comments for ONE Instagram Business/Creator account.
Equivalent of fetch_tweets.py. Single source (Graph API) — there is no
fallback source the way twitter_client.py has twitterapi.io.

IMPORTANT: Business Login tokens on graph.instagram.com must call the
special "me" alias (/me/media), not the raw numeric account ID
(/{account_id}/media) — the latter returns a misleading transient-looking
OAuthException (code 2) rather than a clear 4xx. Confirmed via manual curl
on 2026-07-10: /284751110582077541/media failed repeatedly, /me/media
succeeded immediately with the same token. ACCOUNT_ID from config/.env is
still useful for logging/DB tagging, just not as a URL path segment here.
"""

import logging
import time
from ig_client import get, ACCOUNT_ID
from config import IG_MEDIA_FIELDS, IG_COMMENT_FIELDS, IG_POST_LIMIT, IG_COMMENT_LIMIT, QUERY_DELAY

log = logging.getLogger(__name__)


def fetch_posts(account_id=ACCOUNT_ID, limit=IG_POST_LIMIT):
    """Fetch recent posts (media objects) for the account. Always calls the
    'me' alias, not the raw account_id, per the Business Login quirk above."""
    log.info(f"Fetching posts for account {account_id} (via /me alias)")
    params = {"fields": IG_MEDIA_FIELDS, "limit": limit}
    success, data = get("/me/media", params)

    if not success:
        log.error(f"  Failed to fetch posts for {account_id}")
        return False, []

    posts = data.get("data", [])
    log.info(f"  ✓ {len(posts)} posts fetched")
    return True, posts


def fetch_comments(media_id, limit=IG_COMMENT_LIMIT):
    """Fetch comments for a single post."""
    params = {"fields": IG_COMMENT_FIELDS, "limit": limit}
    success, data = get(f"/{media_id}/comments", params)

    if not success:
        log.warning(f"  Failed to fetch comments for media {media_id}")
        return []

    return data.get("data", [])


def fetch_account_data(account_id=ACCOUNT_ID, post_limit=IG_POST_LIMIT, comment_limit=IG_COMMENT_LIMIT):
    """
    Full pull for one account: posts, with comments attached to each post.
    Mirrors the {"tweets": [...]} shape fetch_tweets.py returns — "posts" is
    the Instagram-side equivalent key. save_raw.py works unchanged against
    this; save_processed.py needs the field-mapping pass (next step).
    """
    success, posts = fetch_posts(account_id, post_limit)
    if not success:
        return False, None

    for post in posts:
        media_id = post.get("id")
        comments = fetch_comments(media_id, comment_limit)
        post["comments"] = comments
        log.info(f"  Post {media_id}: {len(comments)} comments")
        time.sleep(QUERY_DELAY)  # BUC quota is per-account, not per-endpoint — space out calls

    total_comments = sum(len(p.get("comments", [])) for p in posts)
    data = {"posts": posts, "count": len(posts)}
    log.info(f"✓ Account pull complete — {len(posts)} posts, {total_comments} total comments")
    return True, data
