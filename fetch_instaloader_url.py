"""
fetch_instaloader_url.py — fetches ONE specific Instagram post/reel given
its URL, rather than iterating a whole profile's post list.

This is lower-risk than fetch_instaloader.py's profile-based fetch: one
targeted request per URL, not iterating through a feed. Uses the same
saved session from import_firefox_session.py (anonymous mode is broken —
see fetch_instaloader.py docstring for why).

Usage:
    python fetch_instaloader_url.py <instagram_url> <login_as>
    python fetch_instaloader_url.py https://www.instagram.com/reel/Dxxxxx/ mea7.singh
    python fetch_instaloader_url.py https://www.instagram.com/p/Dxxxxx/ mea7.singh

Accepts both /p/ (regular posts) and /reel/ URLs.
"""

import sys
import re
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


def extract_shortcode(url: str) -> str:
    """Pull the shortcode out of a /p/ or /reel/ Instagram URL."""
    match = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not find a post/reel shortcode in URL: {url}")
    return match.group(1)


def fetch_post_by_url(url: str, login_as: str):
    shortcode = extract_shortcode(url)
    log.info(f"Fetching post/reel {shortcode} (logged in as @{login_as})")

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    try:
        L.load_session_from_file(login_as)
    except FileNotFoundError:
        log.error(f"  No saved session for @{login_as}. Run import_firefox_session.py first.")
        return False, None

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except Exception as e:
        log.error(f"  Failed to fetch {shortcode}: {type(e).__name__}: {e}")
        return False, None

    post_data = {
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
        "owner_username": post.owner_username,
    }

    log.info(f"  ✓ Fetched — @{post.owner_username}, {post.likes} likes, {post.comments} comments")

    result = {"posts": [post_data], "count": 1}
    return True, result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fetch_instaloader_url.py <instagram_url> <login_as>")
        print("Example: python fetch_instaloader_url.py https://www.instagram.com/reel/Dxxxxx/ mea7.singh")
        sys.exit(1)

    url = sys.argv[1]
    login_as = sys.argv[2].lstrip("@")

    success, data = fetch_post_by_url(url, login_as)

    if not success:
        print(f"\n✗ Failed to fetch from {url}. See log output above.")
        sys.exit(1)

    post = data["posts"][0]
    caption = (post.get("caption") or "")[:80]
    print(f"\n@{post['owner_username']} | {post['media_type']} | "
          f"{post['like_count']} likes | {post['comments_count']} comments")
    print(f"Caption: {caption!r}")

    label = post["owner_username"]
    raw_path = save_raw(label, data)
    processed_path = save_processed_ig(label, data, source="instaloader")
    print(f"\n✓ Raw saved      → {raw_path}")
    print(f"✓ Processed saved → {processed_path}")
