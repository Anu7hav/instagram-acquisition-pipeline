"""
test_ig.py — standalone smoke test for the IG acquisition layer.
Run this directly (not through main.py) to confirm ig_client.py + fetch_ig.py
work end to end before wiring into save_raw.py / save_processed.py / db_manager.py.
"""

import logging
from datetime import datetime
from ig_client import check_token
from fetch_ig import fetch_account_data
from save_raw import save_raw
from save_processed_ig import save_processed_ig
from db_manager_ig import (
    init_db, get_conn, upsert_account, insert_fetch_run,
    insert_posts, insert_comments,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

print(f"Starting IG acquisition smoke test at {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

account_info = check_token()
if not account_info:
    print("✗ Token check failed — fix this before continuing. See earlier log output.")
    raise SystemExit(1)

print(f"✓ Token OK for @{account_info.get('username')}\n")

success, data = fetch_account_data()

if not success:
    print("✗ fetch_account_data failed — see log output above.")
    raise SystemExit(1)

print(f"\n✓ Fetched {data['count']} posts")
for post in data["posts"][:3]:
    caption = (post.get("caption") or "")[:60]
    print(f"  - {post.get('id')} | {post.get('media_type')} | {len(post.get('comments', []))} comments | {caption!r}")

if data["count"] == 0:
    print(
        "\nNote: 0 posts is expected right now — your test account has no media yet "
        "(media_count was 0 when we verified the token). Post one photo/reel to the "
        "account and rerun this script to see the full posts + comments shape."
    )
else:
    username = account_info.get("username")
    raw_path = save_raw(username, data)
    processed_path = save_processed_ig(username, data)
    print(f"\n✓ Raw saved      → {raw_path}")
    print(f"✓ Processed saved → {processed_path}")

    # Re-read the processed file so DB insert matches exactly what's on disk
    import json
    with open(processed_path, encoding="utf-8") as f:
        processed = json.load(f)

    init_db()
    with get_conn() as conn:
        account_id = upsert_account(conn, username)
        fetch_run_id = insert_fetch_run(conn, account_id, processed["metadata"], processed_path)
        n_posts = insert_posts(conn, fetch_run_id, processed["posts"])
        n_comments = insert_comments(conn, fetch_run_id, processed["posts"])
        print(f"✓ DB insert       → {n_posts} posts, {n_comments} comments (pipeline_ig.db)")
