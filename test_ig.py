"""
test_ig.py — standalone smoke test for the IG acquisition layer.
Run this directly (not through main.py) to confirm ig_client.py + fetch_ig.py
work end to end before wiring into save_raw.py / save_processed.py / db_manager.py.
"""

import logging
from datetime import datetime
from ig_client import check_token
from fetch_ig import fetch_account_data

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
