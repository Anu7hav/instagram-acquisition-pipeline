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
from ig_client import get, get_url, ACCOUNT_ID
from config import (IG_MEDIA_FIELDS, IG_COMMENT_FIELDS, IG_POST_LIMIT, IG_COMMENT_LIMIT,
                     QUERY_DELAY, MAX_PAGES, PAGE_DELAY)

log = logging.getLogger(__name__)


def fetch_posts(account_id=ACCOUNT_ID, limit=IG_POST_LIMIT, max_pages=MAX_PAGES):
    """Fetch recent posts (media objects) for the account, following
    pagination up to max_pages. Previously this silently stopped at the
    first page (up to `limit` posts) with no warning if more existed —
    fixed 2026-07-11."""
    log.info(f"Fetching posts for account {account_id} (via /me alias)")
    params = {"fields": IG_MEDIA_FIELDS, "limit": limit}
    success, data = get("/me/media", params)

    if not success:
        log.error(f"  Failed to fetch posts for {account_id}")
        return False, []

    posts = data.get("data", [])
    pages_fetched = 1
    next_url = data.get("paging", {}).get("next")

    while next_url and pages_fetched < max_pages:
        log.info(f"  Fetching posts page {pages_fetched + 1}...")
        success, data = get_url(next_url)
        if not success:
            log.warning("  Pagination request failed — stopping with partial results")
            break
        page_posts = data.get("data", [])
        if not page_posts:
            break
        posts.extend(page_posts)
        next_url = data.get("paging", {}).get("next")
        pages_fetched += 1
        time.sleep(PAGE_DELAY)

    if next_url:
        log.warning(f"  Reached MAX_PAGES={max_pages} — more posts likely exist beyond "
                    f"the {len(posts)} fetched. Raise MAX_PAGES in config.py to pull more.")

    log.info(f"  ✓ {len(posts)} posts fetched across {pages_fetched} page(s)")
    return True, posts


def fetch_comments(media_id, limit=IG_COMMENT_LIMIT, max_pages=MAX_PAGES):
    """Fetch comments for a single post, following pagination up to max_pages —
    same silent-truncation risk as posts existed here before this fix."""
    params = {"fields": IG_COMMENT_FIELDS, "limit": limit}
    success, data = get(f"/{media_id}/comments", params)

    if not success:
        log.warning(f"  Failed to fetch comments for media {media_id}")
        return []

    comments = data.get("data", [])
    pages_fetched = 1
    next_url = data.get("paging", {}).get("next")

    while next_url and pages_fetched < max_pages:
        success, data = get_url(next_url)
        if not success:
            break
        page_comments = data.get("data", [])
        if not page_comments:
            break
        comments.extend(page_comments)
        next_url = data.get("paging", {}).get("next")
        pages_fetched += 1
        time.sleep(PAGE_DELAY)

    if next_url:
        log.warning(f"  Comments for {media_id}: reached MAX_PAGES={max_pages} — "
                    f"more comments likely exist beyond the {len(comments)} fetched.")

    return comments


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


def fetch_business_discovery(target_username, limit=IG_POST_LIMIT):
    """
    Pull PUBLIC data for ANY other Instagram Business/Creator account — does
    NOT require that account to add your app as a Tester. Uses the Business
    Discovery endpoint, a fundamentally different query shape from fetch_posts
    (nested field syntax, queried against YOUR OWN account_id, not a direct
    path to the target).

    Hard limitations vs. fetch_account_data():
      - Target account must be a PUBLIC Business or Creator account. Personal
        or private accounts return nothing.
      - Comment TEXT is not available — only comments_count on each post.
        Real comment content requires the target account to authorize your
        app as a Tester (i.e. fetch_comments() only works on accounts you
        actually manage). Every post here gets "comments": [] — this is
        expected, not a bug.
      - Subject to Platform Rate Limiting (separate quota from the normal
        Business Use Case limits fetch_posts/fetch_comments use).

    Returns the same {"posts": [...], "count": N} shape fetch_account_data()
    does, so it flows through save_raw / save_processed_ig / db_manager_ig
    unchanged.
    """
    log.info(f"Business Discovery: fetching public data for @{target_username}")

    fields = (
        f"business_discovery.username({target_username})"
        f"{{id,username,followers_count,follows_count,media_count,biography,"
        f"media.limit({limit}){{{IG_MEDIA_FIELDS}}}}}"
    )
    success, data = get(f"/{ACCOUNT_ID}", {"fields": fields})

    if not success:
        log.error(f"  Failed Business Discovery lookup for @{target_username} — "
                  f"check the account is Business/Creator and public.")
        return False, None

    discovery = data.get("business_discovery")
    if not discovery:
        log.error(f"  No business_discovery data returned for @{target_username}")
        return False, None

    log.info(f"  ✓ @{discovery.get('username')} — {discovery.get('followers_count')} followers, "
              f"{discovery.get('media_count')} total media")

    media_block = discovery.get("media", {})
    posts = media_block.get("data", [])

    # Business Discovery's media edge paginates too — same pattern as fetch_posts
    pages_fetched = 1
    next_url = media_block.get("paging", {}).get("next")
    while next_url and pages_fetched < MAX_PAGES:
        log.info(f"  Fetching discovery media page {pages_fetched + 1}...")
        success, page_data = get_url(next_url)
        if not success:
            log.warning("  Pagination request failed — stopping with partial results")
            break
        page_posts = page_data.get("data", [])
        if not page_posts:
            break
        posts.extend(page_posts)
        next_url = page_data.get("paging", {}).get("next")
        pages_fetched += 1
        time.sleep(PAGE_DELAY)

    if next_url:
        log.warning(f"  Reached MAX_PAGES={MAX_PAGES} — more posts likely exist beyond "
                    f"the {len(posts)} fetched.")

    # No comment TEXT available via Business Discovery — see docstring.
    # comments_count is already present per-post via IG_MEDIA_FIELDS.
    for post in posts:
        post["comments"] = []

    log.info(f"  ✓ {len(posts)} posts fetched across {pages_fetched} page(s) "
              f"(comment text unavailable — Business Discovery only)")

    result = {"posts": posts, "count": len(posts)}
    return True, result
