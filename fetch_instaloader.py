"""
fetch_instaloader.py — fetches posts from a PUBLIC Instagram account via
Instaloader (unofficial, scraping-based), per mentor's direct instruction.

⚠️ IMPORTANT — read before running:
This is NOT the official Graph API path used elsewhere in this pipeline
(ig_client.py / fetch_ig.py). Instaloader works by imitating a browser
against Instagram's internal web endpoints, which:
  - Violates Instagram's Terms of Service (confirmed in Instaloader's own docs)
  - Risks the source IP/account being rate-limited or blocked, even in
    anonymous (no-login) mode, especially at any real scale
  - Can break without warning whenever Instagram changes its frontend —
    there's no stability guarantee the way there is with the Graph API

Kept deliberately conservative here: no login (anonymous mode only, for
public accounts), a small default post limit, and real delays between
requests — this is not built for scale, on purpose.

Comment TEXT is NOT fetched by default — only post-level data (caption,
likes, comment count). Pulling actual comment text via Instaloader means
significantly more requests per post, which meaningfully raises ban risk
for comparatively low value here. This can be added later if genuinely
needed, as a conscious decision, not a default.

Usage:
    python fetch_instaloader.py <username> [limit]
    python fetch_instaloader.py ndtvnews 10
"""

import sys
import time
import logging
import instaloader
from save_raw import save_raw
from save_processed_ig import save_processed_ig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

POST_DELAY = 3  # seconds between posts — deliberately conservative, not tuned for speed


def fetch_public_posts(username: str, limit: int = 10, login_as: str = None):
    """
    Fetch up to `limit` recent posts from a public account. If login_as is
    given, uses that account's saved Instaloader session (imported via
    import_firefox_session.py) instead of anonymous mode — this also
    sidesteps the anonymous-mode 403 bug, since logged-in requests go
    through a different code path.

    Returns the same {"posts": [...], "count": N} shape the Graph API path
    uses, so it flows through save_raw / save_processed_ig unchanged — but
    every post's "comments" list will be empty (see module docstring).
    """
    if login_as:
        log.info(f"Fetching up to {limit} posts from @{username} via Instaloader (logged in as @{login_as})")
    else:
        log.info(f"Fetching up to {limit} posts from @{username} via Instaloader (anonymous, no login)")

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    if login_as:
        try:
            L.load_session_from_file(login_as)
        except FileNotFoundError:
            log.error(f"  No saved session for @{login_as}. Run import_firefox_session.py first.")
            return False, None

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.exceptions.ProfileNotExistsException as e:
        log.error(f"  @{username} does not exist or is not accessible. Underlying error: {e}")
        return False, None
    except Exception as e:
        log.error(f"  Failed to load profile @{username}: {type(e).__name__}: {e}")
        return False, None

    if profile.is_private:
        log.error(f"  @{username} is a private account — cannot fetch without following + login.")
        return False, None

    log.info(f"  ✓ Profile loaded — {profile.mediacount} total posts, {profile.followers} followers")

    posts = []
    try:
        for i, post in enumerate(profile.get_posts()):
            if i >= limit:
                break

            posts.append({
                "id": str(post.mediaid),
                "shortcode": post.shortcode,
                "caption": post.caption or "",
                "media_type": "VIDEO" if post.is_video else "IMAGE",
                "media_url": post.url,
                "permalink": f"https://www.instagram.com/p/{post.shortcode}/",
                "timestamp": post.date_utc.isoformat(),
                "like_count": post.likes,
                "comments_count": post.comments,
                "comments": [],
            })

            log.info(f"  [{i+1}/{limit}] {post.shortcode} — {post.likes} likes, {post.comments} comments")
            time.sleep(POST_DELAY)

    except instaloader.exceptions.TooManyRequestsException:
        log.error(f"  Rate-limited by Instagram after {len(posts)} posts. "
                  f"Stopping here rather than retrying aggressively (risks extending the block).")
        if not posts:
            return False, None

    result = {"posts": posts, "count": len(posts)}
    log.info(f"✓ Fetched {len(posts)} posts from @{username} (comment text not included)")
    return True, result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_instaloader.py <username> [limit] [login_as]")
        print("Example: python fetch_instaloader.py ndtvnews 10")
        print("Example (logged in): python fetch_instaloader.py ndtvnews 10 your_throwaway_account")
        sys.exit(1)

    target = sys.argv[1].lstrip("@")
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    login_as = sys.argv[3].lstrip("@") if len(sys.argv) > 3 else None

    success, data = fetch_public_posts(target, limit, login_as=login_as)

    if not success:
        print(f"\n✗ Failed to fetch @{target}. See log output above.")
        sys.exit(1)

    for post in data["posts"][:5]:
        caption = (post.get("caption") or "")[:60]
        print(f"  - {post['shortcode']} | {post['media_type']} | "
              f"{post['like_count']} likes | {post['comments_count']} comments | {caption!r}")

    raw_path = save_raw(target, data)
    processed_path = save_processed_ig(target, data)
    print(f"\n✓ Raw saved      → {raw_path}")
    print(f"✓ Processed saved → {processed_path}")
    print(f"\nNote: comment text is empty for every post — see fetch_instaloader.py docstring.")
