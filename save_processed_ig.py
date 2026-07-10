"""
save_processed_ig.py — Instagram equivalent of save_processed.py.
Reshapes raw Graph API post objects into a clean, flat structure per post,
with comments nested (same pattern Twitter branch uses for hashtags —
nested in the processed JSON, flattened into their own DB table later in
db_manager.py, not here).

Field mapping vs. Twitter's save_processed.py, confirmed against real
Graph API responses (2026-07-10):
    Twitter field      -> Instagram field
    id                 -> id
    text               -> caption
    createdAt          -> timestamp
    author              (n/a — single account per fetch; see metadata.account)
    likeCount          -> like_count
    url                -> permalink
    hashtags (nested)  -> comments (nested) — different concept, same pattern
    source             -> static "graph_api" (single source, no fallback)

No Instagram equivalent exists for isReply/isRetweet/retweetCount/viewCount —
media_type (IMAGE/VIDEO/CAROUSEL_ALBUM) replaces them as the closest
"what kind of post is this" signal.
"""

import json
import os
import logging
from filenamegen import generate_filename
from datetime import datetime

log = logging.getLogger(__name__)


def save_processed_ig(account_username, data, source="graph_api"):
    posts = []

    for post in data.get("posts", []):
        comments = [
            {
                "id":        c.get("id"),
                "text":      c.get("text"),
                "username":  c.get("username"),
                "timestamp": c.get("timestamp"),
                "likeCount": c.get("like_count", 0),
            }
            for c in post.get("comments", [])
        ]

        posts.append({
            "id":            post.get("id"),
            "caption":       post.get("caption"),
            "mediaType":     post.get("media_type"),
            "mediaUrl":      post.get("media_url"),
            "createdAt":     post.get("timestamp"),
            "likeCount":     post.get("like_count", 0),
            "commentCount":  post.get("comments_count", len(comments)),
            "url":           post.get("permalink"),
            "comments":      comments,
            "source":        source,
        })

    processed = {
        "metadata": {
            "account":    account_username,
            "fetchedAt":  datetime.now().isoformat(),
            "apiSource":  source,
            "postCount":  len(posts),
        },
        "posts": posts
    }

    filepath = generate_filename(account_username, folder="processed")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
        log.info(f"  ✓ Processed data saved → {filepath}")
    except Exception as e:
        log.error(f"  ✗ Failed to save processed data: {e}")
        return None

    return filepath
