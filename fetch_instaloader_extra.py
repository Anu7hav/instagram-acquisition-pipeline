"""
fetch_instaloader_extra.py -- additional Instaloader fetch capabilities.

FIX applied per mentor review:
1. Deleted the broken fetch_location_posts() that called L.get_location_posts()
   (Instaloader's own high-level method -- confirmed broken, 201 Created error,
   open upstream issue #2447).
2. Renamed the working fetch_location_experimental() to fetch_location_posts().
3. CLI: "location" now calls the renamed working function.
   "location-experimental" removed as a separate command (redundant).
4. Hashtag half untouched per mentor instruction -- already correct.
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


def _iphone_media_to_post(media):
    caption_obj = media.get("caption") or {}
    user = media.get("user") or {}
    media_type_int = media.get("media_type")
    return {
        "id": str(media.get("pk")),
        "shortcode": media.get("code", ""),
        "caption": caption_obj.get("text", "") if isinstance(caption_obj, dict) else "",
        "media_type": {1: "IMAGE", 2: "VIDEO", 8: "CAROUSEL_ALBUM"}.get(media_type_int, "UNKNOWN"),
        "media_url": "",
        "permalink": "https://www.instagram.com/p/" + media.get("code", "") + "/",
        "timestamp": __import__("datetime").datetime.fromtimestamp(
            media.get("taken_at", 0), tz=__import__("datetime").timezone.utc
        ).isoformat() if media.get("taken_at") else "",
        "like_count": media.get("like_count", 0),
        "comments_count": media.get("comment_count", 0),
        "comments": [],
        "owner_username": user.get("username", ""),
    }


def fetch_hashtag_posts_experimental(hashtag, login_as, limit=10):
    hashtag = hashtag.lstrip("#")
    log.info("EXPERIMENTAL: direct web_info endpoint for #" + hashtag)
    L = _get_client(login_as)
    try:
        response = L.context.get_iphone_json("api/v1/tags/web_info/", {"tag_name": hashtag})
    except Exception as e:
        log.error("  Direct endpoint call failed: " + type(e).__name__ + ": " + str(e))
        return False, None
    media_objects = _extract_media_objects(response)
    posts = [_iphone_media_to_post(m) for m in media_objects[:limit]]
    log.info("  Extracted " + str(len(posts)) + " posts")
    for p in posts:
        log.info("    " + p["shortcode"] + " (@" + p["owner_username"] + ")")
    return True, {"posts": posts, "count": len(posts)}


def fetch_location_posts(location_id, login_as, limit=10):
    """
    Posts at a specific location, via api/v1/locations/web_info/ called
    directly through get_iphone_json(). CONFIRMED WORKING 2026-07-16.

    FIX (per mentor review): this exact function name previously belonged
    to a BROKEN implementation that called L.get_location_posts()
    (Instaloader's own high-level method -- fails with confirmed
    "201 Created" ConnectionException, open upstream issue #2447). That
    broken version has been DELETED. This function is the renamed former
    fetch_location_experimental() -- the working direct-endpoint version --
    now the only implementation under this name.
    """
    log.info("Fetching posts for location " + str(location_id))
    L = _get_client(login_as)
    try:
        response = L.context.get_iphone_json("api/v1/locations/web_info/", {"location_id": location_id})
    except Exception as e:
        log.error("  Direct endpoint call failed: " + type(e).__name__ + ": " + str(e))
        return False, None
    location_info = response.get("native_location_data", {}).get("location_info", {})
    log.info("  " + str(location_info.get("name", location_id)) + " - " + str(location_info.get("media_count", 0)) + " total posts")
    media_objects = _extract_media_objects(response)
    posts = [_iphone_media_to_post(m) for m in media_objects[:limit]]
    log.info("  Extracted " + str(len(posts)) + " posts")
    for p in posts:
        log.info("    " + p["shortcode"] + " (@" + p["owner_username"] + ")")
    return True, {"posts": posts, "count": len(posts)}


def _get_client(login_as):
    L = instaloader.Instaloader(
        download_pictures=False, download_videos=False,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False, compress_json=False,
    )
    L.load_session_from_file(login_as)
    return L


def _extract_shortcode(url):
    import re
    match = re.search(r"instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError("Could not find a shortcode in URL: " + url)
    return match.group(1)


def fetch_comments(post_url, login_as, limit=10):
    shortcode = _extract_shortcode(post_url)
    log.info("HIGH RISK: fetching up to " + str(limit) + " real comments for " + shortcode)
    L = _get_client(login_as)
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    comments = []
    for i, c in enumerate(post.get_comments()):
        if i >= limit:
            break
        comments.append({
            "id": str(c.id), "text": c.text, "username": c.owner.username,
            "timestamp": c.created_at_utc.isoformat(), "like_count": getattr(c, "likes_count", 0),
        })
        time.sleep(HIGH_RISK_DELAY)
    post_data = {
        "id": str(post.mediaid), "shortcode": post.shortcode,
        "caption": post.caption or "", "media_type": "VIDEO" if post.is_video else "IMAGE",
        "media_url": post.url, "permalink": "https://www.instagram.com/p/" + post.shortcode + "/",
        "timestamp": post.date_utc.isoformat(), "like_count": post.likes,
        "comments_count": post.comments, "comments": comments,
        "owner_username": post.owner_username,
    }
    log.info("Fetched " + str(len(comments)) + " real comments")
    return True, {"posts": [post_data], "count": 1}


def fetch_followers(username, login_as, limit=20):
    log.info("HIGH RISK: fetching up to " + str(limit) + " followers of @" + username)
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)
    followers = []
    for i, f in enumerate(profile.get_followers()):
        if i >= limit:
            break
        followers.append({"username": f.username, "full_name": f.full_name, "is_private": f.is_private})
        time.sleep(HIGH_RISK_DELAY)
    result = {"username": username, "followers": followers, "count": len(followers)}
    log.info("Fetched " + str(len(followers)) + " followers")
    return True, result


def fetch_followees(username, login_as, limit=20):
    log.info("HIGH RISK: fetching up to " + str(limit) + " accounts @" + username + " follows")
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)
    followees = []
    for i, f in enumerate(profile.get_followees()):
        if i >= limit:
            break
        followees.append({"username": f.username, "full_name": f.full_name, "is_private": f.is_private})
        time.sleep(HIGH_RISK_DELAY)
    result = {"username": username, "followees": followees, "count": len(followees)}
    log.info("Fetched " + str(len(followees)) + " followees")
    return True, result


def fetch_stories(username, login_as):
    log.info("HIGH RISK: fetching current stories for @" + username)
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)
    stories_data = []
    for story in L.get_stories(userids=[profile.userid]):
        for item in story.get_items():
            stories_data.append({
                "id": str(item.mediaid), "media_type": "VIDEO" if item.is_video else "IMAGE",
                "media_url": item.url, "timestamp": item.date_utc.isoformat(),
                "expiring_at": item.expiring_utc.isoformat(),
            })
            time.sleep(HIGH_RISK_DELAY)
    result = {"username": username, "stories": stories_data, "count": len(stories_data)}
    log.info("Fetched " + str(len(stories_data)) + " active story items")
    return True, result


def fetch_tagged_posts(username, login_as, limit=10):
    log.info("Fetching up to " + str(limit) + " posts tagging @" + username)
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)
    posts = []
    for i, post in enumerate(profile.get_tagged_posts()):
        if i >= limit:
            break
        posts.append({
            "id": str(post.mediaid), "shortcode": post.shortcode,
            "caption": post.caption or "", "media_type": "VIDEO" if post.is_video else "IMAGE",
            "media_url": post.url, "permalink": "https://www.instagram.com/p/" + post.shortcode + "/",
            "timestamp": post.date_utc.isoformat(), "like_count": post.likes,
            "comments_count": post.comments, "comments": [],
            "owner_username": post.owner_username,
        })
        time.sleep(LOW_RISK_DELAY)
    log.info("Fetched " + str(len(posts)) + " tagged posts")
    return True, {"posts": posts, "count": len(posts)}


def fetch_profile_info(username, login_as):
    log.info("Fetching profile metadata for @" + username)
    L = _get_client(login_as)
    profile = instaloader.Profile.from_username(L.context, username)
    info = {
        "username": profile.username, "full_name": profile.full_name,
        "biography": profile.biography, "followers": profile.followers,
        "followees": profile.followees, "mediacount": profile.mediacount,
        "is_verified": profile.is_verified, "is_private": profile.is_private,
        "is_business_account": profile.is_business_account,
    }
    log.info("@" + username + " - " + str(profile.followers) + " followers")
    return True, info


def _save_generic(label, data, folder="raw"):
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
            print("Raw saved -> " + raw_path + "\nProcessed saved -> " + processed_path)

    elif command == "followers":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        success, data = fetch_followers(username, login_as, limit)
        if success:
            print("Saved -> " + _save_generic(username + "_followers", data))

    elif command == "followees":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
        success, data = fetch_followees(username, login_as, limit)
        if success:
            print("Saved -> " + _save_generic(username + "_followees", data))

    elif command == "stories":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        success, data = fetch_stories(username, login_as)
        if success:
            print("Saved -> " + _save_generic(username + "_stories", data))

    elif command == "location":
        location_id, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_location_posts(location_id, login_as, limit)
        if success:
            raw_path = save_raw("location_" + location_id, data)
            processed_path = save_processed_ig("location_" + location_id, data, source="instaloader")
            print("Raw saved -> " + raw_path + "\nProcessed saved -> " + processed_path)

    elif command == "tagged":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_tagged_posts(username, login_as, limit)
        if success:
            raw_path = save_raw(username + "_tagged", data)
            processed_path = save_processed_ig(username + "_tagged", data, source="instaloader")
            print("Raw saved -> " + raw_path + "\nProcessed saved -> " + processed_path)

    elif command == "profile":
        username, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        success, data = fetch_profile_info(username, login_as)
        if success:
            print(json.dumps(data, indent=2))
            print("Saved -> " + _save_generic(username + "_profile_info", data))

    elif command == "hashtag-experimental":
        hashtag, login_as = sys.argv[2], sys.argv[3].lstrip("@")
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        success, data = fetch_hashtag_posts_experimental(hashtag, login_as, limit)
        if success:
            label = "hashtag_" + hashtag.lstrip("#")
            raw_path = save_raw(label, data)
            processed_path = save_processed_ig(label, data, source="instaloader")
            print("Raw saved -> " + raw_path + "\nProcessed saved -> " + processed_path)

    else:
        print("Unknown command: " + command)
        print(__doc__)
        sys.exit(1)

    if not success:
        print("Failed - see log output above.")
        sys.exit(1)
