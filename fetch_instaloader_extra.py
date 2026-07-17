"""
fetch_instaloader_extra.py — additional Instaloader fetch capabilities
beyond the core three (profile posts, URL, hashtag).

⚠️ RISK TIERS — read before using:

LOWER RISK (similar to existing scripts):
  - profile_info    : bio/follower count only, no posts, single lightweight request
  - location_posts   : posts at a place, similar pattern to hashtag search
  - tagged_posts      : posts where an account is tagged

HIGHER RISK (use sparingly, small limits only):
  - comments          : ACTUAL comment text, not just counts. Multiplies request
                        volume significantly — this is the single riskiest
                        action in this whole project. Every other script
                        deliberately avoided this.
  - followers/followees: Instagram treats follower-list scraping as one of the
                        most heavily monitored actions on the platform —
                        higher ban risk than post fetching.
  - stories            : Ephemeral content; story-viewing is unusually closely
                        tracked. Often requires already following the account.

All functions use the saved session from import_firefox_session.py — no
anonymous mode (broken, see fetch_instaloader.py). Given the higher risk
here, delays are set more conservatively than the core scripts.

Usage (see bottom of file for full CLI):
    python fetch_instaloader_extra.py comments <post_url> <login_as> [limit]
    python fetch_instaloader_extra.py followers <username> <login_as> [limit]
    python fetch_instaloader_extra.py followees <username> <login_as> [limit]
    python fetch_instaloader_extra.py stories <username> <login_as>
    python fetch_instaloader_extra.py location <location_id> <login_as> [limit]
    python fetch_instaloader_extra.py tagged <username> <login_as> [limit]
    python fetch_instaloader_extra.py profile <username> <login_as>
"""

import sys
import time
import json
import os
import logging
import instaloader
from filenamegen import generate_filename
from save_raw import save_raw
from save_processed_ig import save_processed_ig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

LOW_RISK_DELAY = 3
HIGH_RISK_DELAY = 6


def _extract_media_objects(node, found=None):
    """Recursively walk a nested dict/list and collect every object that
    looks like a real Instagram media/post object (has 'pk', 'media_type',
    'taken_at', AND a real 'code' + owning 'user' — filters out ad
    placeholders/other cards that share some but not all of these keys,
    which showed up as empty entries in real testing)."""
    if found is None:
        found = []
    if isinstance(node, dict):
        if (node.get("pk") and node.get("media_type") and node.get("taken_at")
                and node.get("code") and node.get("user", {}).get("username")):
            found.append(node)
        for value in node.values():
            _extract_media_objects(value, found)
    elif isinstance(node, list):
        for item in node:
            _extract_media_objects(item, found)
    return found


def _iphone_media_to_post(media: dict) -> dict:
    """Map the v1/iPhone media object shape to this project's standard
    post shape (same mapping style PR #2706 established for post metadata)."""
    caption_obj = media.get("caption") or {}
    user = media.get("user") or {}
    media_type_int = media.get("media_type")
    return {
        "id": str(media.get("pk")),
        "shortcode": media.get("code", ""),
        "caption": caption_obj.get("text", "") if isinstance(caption_obj, dict) else "",
        "media_type": {1: "IMAGE", 2: "VIDEO", 8: "CAROUSEL_ALBUM"}.get(media_type_int, "UNKNOWN"),
        "media_url": "",  # image_versions2 nested structure varies — skip for now, not critical
        "permalink": f"https://www.instagram.com/p/{media.get('code','')}/",
        "timestamp": __import__("datetime").datetime.fromtimestamp(
            media.get("taken_at", 0), tz=__import__("datetime").timezone.utc
        ).isoformat() if media.get("taken_at") else "",
        "like_count": media.get("like_count", 0),
        "comments_count": media.get("comment_count", 0),
        "comments": [],
        "owner_username": user.get("username", ""),
    }


def fetch_hashtag_posts_experimental(hashtag: str, login_as: str, limit: int = 10):
    """
    EXPERIMENTAL — bypasses the broken instaloader.Hashtag.get_posts() by
    calling the newer api/v1/tags/web_info/ endpoint directly via
    get_iphone_json(). CONFIRMED WORKING 2026-07-16 — returns real "top"
    posts for the hashtag (Instagram's Top tab equivalent, not a full
    chronological/comprehensive feed the way the old edge_hashtag_to_media
    pagination provided).

    Not part of Instaloader's public API — calling Instagram's backend more
    directly than the library's own abstraction currently supports.
    """
    hashtag = hashtag.lstrip("#")
    log.info(f"EXPERIMENTAL: direct web_info endpoint for #{hashtag}")

    L = _get_client(login_as)

    try:
        response = L.context.get_iphone_json(
            "api/v1/tags/web_info/", {"tag_name": hashtag}
        )
    except Exception as e:
        log.error(f"  Direct endpoint call failed: {type(e).__name__}: {e}")
        return False, None

    media_objects = _extract_media_objects(response)
    posts = [_iphone_media_to_post(m) for m in media_objects[:limit]]

    log.info(f"  ✓ Extracted {len(posts)} posts (from {len(media_objects)} found, capped at limit={limit})")
    for p in posts:
        log.info(f"    {p['shortcode']} (@{p['owner_username']}) — {p['like_count']} likes, {p['comments_count']} comments")

    return True, {"posts": posts, "count": len(posts)}


def fetch_location_experimental(location_id: str, login_as: str, limit: int = 10):
    """
    EXPERIMENTAL — same approach as fetch_hashtag_posts_experimental.
    CONFIRMED WORKING 2026-07-16 — same nested media-object structure as
    the hashtag endpoint, reuses the same extraction helpers. Returns
    "ranked" (Instagram's algorithmic top) posts for the location, not a
    full chronological feed.
    """
    log.info(f"EXPERIMENTAL: direct web_info endpoint for location {location_id}")
    L = _get_client(login_as)

    try:
        response = L.context.get_iphone_json(
            "api/v1/locations/web_info/", {"location_id": location_id}
        )
    except Exception as e:
        log.error(f"  Direct endpoint call failed: {type(e).__name__}: {e}")
        return False, None

    location_info = response.get("native_location_data", {}).get("location_info", {})
    log.info(f"  ✓ {location_info.get('name', location_id)} — {location_info.get('media_count', 0)} total posts")

    media_objects = _extract_media_objects(response)
    posts = [_iphone_media_to_post(m) for m in media_objects[:limit]]

    log.info(f"  ✓ Extracted {len(posts)} posts (from {len(media_objects)} found, capped at limit={limit})")
    for p in posts:
        log.info(f"    {p['shortcode']} (@{p['owner_username']}) — {p['like_count']} likes, {p['comments_count']} comments")

    return True, {"posts": posts, "count": len(posts)}


def _get_client(login_as: str):
    L = instaloader.Instaloader(
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False, compress_json=False,
    )
    L.load_session_from_file(login_as)
    return L


def _extract_shortcode(url: str) -> str:
    import re
    match = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not find a shortcode in URL: {url}")
    return match.group(1)


def fetch_comments(post_url: str, login_as: str, limit: int = 10):
    """Real comment TEXT for a single post/reel. Highest-risk function here —
    keep limit small."""
    shortcode = _extract_shortcode(post_url)
    log.info(f"HIGH RISK: fetching up to {limit} real comments for {shortcode}")

    L = _get_client(login_as)
    post = instaloader.Post.from_shortcode(L.context, shortcode)

    comments = []
    for i, c in enumerate(post.get_comments()):
        if i >= limit:
            break
        comments.append({
            "id": str(c.id),
            "text": c.text,
            "username": c.owner.username,
            "timestamp": c.created_at_utc.isoformat(),
            "like_count": getattr(c, "likes_count", 0),
        })
        log.info(f"  [{i+1}/{limit}] @{c.owner.username}: {c.text[:50]!r}")
        time.sleep(HIGH_RISK_DELAY)

    post_data = {
        "id": str(post.mediaid), "shortcode": post.shortcode,
        "caption": post.caption or "", "media_type": "VIDEO" if post.is_video else "IMAGE",
        "media_url": post.url, "permalink": f"https://www.instagram.com/p/{post.shortcode}/",
        "timestamp": post.date_utc.isoformat(), "like_count": post.likes,
        "comments_count": post.comments, "comments": comments,
        "owner_username": post.owner_username,
    }
    log.info(f"Fetched {len(comments)} real comments")
    return True, {"posts": [post_data], "count": 1}


def fetch_followers(username: str, login_as: str, limit: int = 20):
    """HIGH RISK — Instagram heavily monitors follower-list access."""
    log.info(f"HIGH RISK: fetching up to {limit} followers of @{username}")
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)

    followers = []
    for i, f in enumerate(profile.get_followers()):
        if i >= limit:
            break
        followers.append({"username": f.username, "full_name": f.full_name, "is_private": f.is_private})
        time.sleep(HIGH_RISK_DELAY)

    result = {"username": username, "followers": followers, "count": len(followers)}
    log.info(f"Fetched {len(followers)} followers")
    return True, result


def fetch_followees(username: str, login_as: str, limit: int = 20):
    """HIGH RISK — same concern as fetch_followers, reversed direction."""
    log.info(f"HIGH RISK: fetching up to {limit} accounts @{username} follows")
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)

    followees = []
    for i, f in enumerate(profile.get_followees()):
        if i >= limit:
            break
        followees.append({"username": f.username, "full_name": f.full_name, "is_private": f.is_private})
        time.sleep(HIGH_RISK_DELAY)

    result = {"username": username, "followees": followees, "count": len(followees)}
    log.info(f"Fetched {len(followees)} followees")
    return True, result


def fetch_stories(username: str, login_as: str):
    """HIGH RISK — story-viewing is unusually closely tracked by Instagram.
    Stories are ephemeral — may legitimately return zero if none active."""
    log.info(f"HIGH RISK: fetching current stories for @{username}")
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)

    stories_data = []
    for story in L.get_stories(userids=[profile.userid]):
        for item in story.get_items():
            stories_data.append({
                "id": str(item.mediaid),
                "media_type": "VIDEO" if item.is_video else "IMAGE",
                "media_url": item.url,
                "timestamp": item.date_utc.isoformat(),
                "expiring_at": item.expiring_utc.isoformat(),
            })
            time.sleep(HIGH_RISK_DELAY)

    result = {"username": username, "stories": stories_data, "count": len(stories_data)}
    log.info(f"Fetched {len(stories_data)} active story items")
    return True, result


def fetch_location_posts(location_id: str, login_as: str, limit: int = 10):
    """Posts tagged at a specific place. Uses L.get_location_posts() —
    NOT a standalone Location class (that was a bug in an earlier version
    of this function; instaloader.Location isn't a public constructor,
    location fetching is a method on the Instaloader instance itself)."""
    log.info(f"Fetching up to {limit} posts at location {location_id}")
    L = _get_client(login_as)

    posts = []
    for i, post in enumerate(L.get_location_posts(location_id)):
        if i >= limit:
            break
        posts.append({
            "id": str(post.mediaid), "shortcode": post.shortcode,
            "caption": post.caption or "", "media_type": "VIDEO" if post.is_video else "IMAGE",
            "media_url": post.url, "permalink": f"https://www.instagram.com/p/{post.shortcode}/",
            "timestamp": post.date_utc.isoformat(), "like_count": post.likes,
            "comments_count": post.comments, "comments": [],
            "owner_username": post.owner_username,
        })
        log.info(f"  [{i+1}/{limit}] {post.shortcode} (@{post.owner_username})")
        time.sleep(LOW_RISK_DELAY)

    log.info(f"Fetched {len(posts)} posts at this location")
    return True, {"posts": posts, "count": len(posts)}


def fetch_tagged_posts(username: str, login_as: str, limit: int = 10):
    """Posts where @username is tagged by others."""
    log.info(f"Fetching up to {limit} posts tagging @{username}")
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)

    posts = []
    for i, post in enumerate(profile.get_tagged_posts()):
        if i >= limit:
            break
        posts.append({
            "id": str(post.mediaid), "shortcode": post.shortcode,
            "caption": post.caption or "", "media_type": "VIDEO" if post.is_video else "IMAGE",
            "media_url": post.url, "permalink": f"https://www.instagram.com/p/{post.shortcode}/",
            "timestamp": post.date_utc.isoformat(), "like_count": post.likes,
            "comments_count": post.comments, "comments": [],
            "owner_username": post.owner_username,
        })
        log.info(f"  [{i+1}/{limit}] {post.shortcode} (posted by @{post.owner_username})")
        time.sleep(LOW_RISK_DELAY)

    log.info(f"Fetched {len(posts)} tagged posts")
    return True, {"posts": posts, "count": len(posts)}


def fetch_profile_info(username: str, login_as: str):
    """Lightweight — bio/counts only, no posts. Lowest risk function here."""
    log.info(f"Fetching profile metadata for @{username}")
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)

    info = {
        "username": profile.username, "full_name": profile.full_name,
        "biography": profile.biography, "followers": profile.followers,
        "followees": profile.followees, "mediacount": profile.mediacount,
        "is_verified": profile.is_verified, "is_private": profile.is_private,
        "is_business_account": profile.is_business_account,
    }
    log.info(f"@{username} — {profile.followers} followers, {profile.mediacount} posts")
    return True, info


def _save_generic(label: str, data: dict, folder: str = "raw"):
    filepath = generate_filename(label, folder=folder)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    success = False

    if command == "comments":
        url, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_comments(url, login_as, limit)
        if success:
            post = data["posts"][0]
            raw_path = save_raw(post["owner_username"], data)
            processed_path = save_processed_ig(post["owner_username"], data, source="instaloader")
            print(f"Raw saved -> {raw_path}\nProcessed saved -> {processed_path}")

    elif command == "followers":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        success, data = fetch_followers(username, login_as, limit)
        if success:
            print(f"Saved -> {_save_generic(f'{username}_followers', data)}")

    elif command == "followees":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        success, data = fetch_followees(username, login_as, limit)
        if success:
            print(f"Saved -> {_save_generic(f'{username}_followees', data)}")

    elif command == "stories":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        success, data = fetch_stories(username, login_as)
        if success:
            print(f"Saved -> {_save_generic(f'{username}_stories', data)}")

    elif command == "location":
        location_id, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_location_posts(location_id, login_as, limit)
        if success:
            raw_path = save_raw(f"location_{location_id}", data)
            processed_path = save_processed_ig(f"location_{location_id}", data, source="instaloader")
            print(f"Raw saved -> {raw_path}\nProcessed saved -> {processed_path}")

    elif command == "tagged":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_tagged_posts(username, login_as, limit)
        if success:
            raw_path = save_raw(f"{username}_tagged", data)
            processed_path = save_processed_ig(f"{username}_tagged", data, source="instaloader")
            print(f"Raw saved -> {raw_path}\nProcessed saved -> {processed_path}")

    elif command == "profile":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        success, data = fetch_profile_info(username, login_as)
        if success:
            print(json.dumps(data, indent=2))
            print(f"Saved -> {_save_generic(f'{username}_profile_info', data)}")

    elif command == "hashtag-experimental":
        hashtag, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_hashtag_posts_experimental(hashtag, login_as, limit)
        if success:
            label = f"hashtag_{hashtag.lstrip('#')}"
            raw_path = save_raw(label, data)
            processed_path = save_processed_ig(label, data, source="instaloader")
            print(f"Raw saved -> {raw_path}\nProcessed saved -> {processed_path}")

    elif command == "location-experimental":
        location_id, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_location_experimental(location_id, login_as, limit)
        if success:
            label = f"location_{location_id}"
            raw_path = save_raw(label, data)
            processed_path = save_processed_ig(label, data, source="instaloader")
            print(f"Raw saved -> {raw_path}\nProcessed saved -> {processed_path}")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    if not success:
        print("Failed - see log output above.")
        sys.exit(1)
