"""
fetch_instaloader_hashtag.py — fetches posts/reels tagged with a specific
hashtag (e.g. #memes, #socialissue), rather than needing a known account
username. This is the closest thing to Twitter-style topic search available
to us — the official Graph API has no equivalent at all.

Same session-based approach as the rest of the Instaloader path (anonymous
mode is broken — see fetch_instaloader.py). Same conservative defaults:
small limit, real delays, comment text not included.

Usage:
    python fetch_instaloader_hashtag.py <hashtag> [limit] <login_as>
    python fetch_instaloader_hashtag.py memes 10 mea7.singh
    python fetch_instaloader_hashtag.py SamvidhanHatyaDiwas 10 mea7.singh

Don't include the # symbol.
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

POST_DELAY = 3


def fetch_hashtag_posts(hashtag: str, limit: int, login_as: str):
    hashtag = hashtag.lstrip("#")
    log.info(f"Fetching up to {limit} posts tagged #{hashtag} (logged in as @{login_as})")

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
        hashtag_obj = instaloader.Hashtag.from_name(L.context, hashtag)
    except Exception as e:
        log.error(f"  Failed to load #{hashtag}: {type(e).__name__}: {e}")
        return False, None

    log.info(f"  ✓ #{hashtag} — {hashtag_obj.mediacount} total posts tagged")

    posts = []
    try:
        for i, post in enumerate(hashtag_obj.get_posts()):
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
                "owner_username": post.owner_username,
            })

            log.info(f"  [{i+1}/{limit}] {post.shortcode} (@{post.owner_username}) — "
                      f"{post.likes} likes, {post.comments} comments")
            time.sleep(POST_DELAY)

    except instaloader.exceptions.TooManyRequestsException:
        log.error(f"  Rate-limited after {len(posts)} posts. Stopping — don't retry immediately.")
        if not posts:
            return False, None

    result = {"posts": posts, "count": len(posts)}
    log.info(f"✓ Fetched {len(posts)} posts tagged #{hashtag} (comment text not included)")
    return True, result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fetch_instaloader_hashtag.py <hashtag> [limit] <login_as>")
        print("Example: python fetch_instaloader_hashtag.py memes 10 mea7.singh")
        sys.exit(1)

    hashtag = sys.argv[1]
    if len(sys.argv) == 3:
        limit, login_as = 10, sys.argv[2].lstrip("@")
    else:
        limit, login_as = int(sys.argv[2]), sys.argv[3].lstrip("@")

    success, data = fetch_hashtag_posts(hashtag, limit, login_as)

    if not success:
        print(f"\n✗ Failed to fetch #{hashtag}. See log output above.")
        sys.exit(1)

    for post in data["posts"][:5]:
        caption = (post.get("caption") or "")[:60]
        print(f"  - {post['shortcode']} (@{post['owner_username']}) | {post['media_type']} | "
              f"{post['like_count']} likes | {post['comments_count']} comments | {caption!r}")

    label = f"hashtag_{hashtag.lstrip('#')}"
    raw_path = save_raw(label, data)
    processed_path = save_processed_ig(label, data, source="instaloader")
    print(f"\n✓ Raw saved      → {raw_path}")
    print(f"✓ Processed saved → {processed_path}")
