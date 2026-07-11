"""
config.py — Central configuration for the Instagram acquisition pipeline.
Import with: from config import *
"""

# ── Pipeline version ──────────────────────────────────────────────────────────
PIPELINE_VERSION = "2.0.0"

# ── Retry / delay settings ────────────────────────────────────────────────────
MAX_RETRIES       = 3
RETRY_DELAY       = 3      # seconds between retries
RATE_LIMIT_DELAY  = 10     # seconds to wait on 429 / throttling
MAX_PAGES         = 3      # max pagination pages per fetch (posts and comments)
PAGE_DELAY        = 5      # seconds between pagination pages
QUERY_DELAY       = 5      # seconds between accounts / between post-comment calls
RETRY_CODES       = {429, 500, 502, 503}

# ── Scheduler settings ────────────────────────────────────────────────────────
SCHEDULER_ENABLED    = False  # set True to loop every RUN_INTERVAL_HOURS
RUN_INTERVAL_HOURS   = 2
MAX_RUNS             = 0      # 0 = run forever, N = stop after N runs

# ── File paths ────────────────────────────────────────────────────────────────
RAW_DATA_DIR      = "data/raw"
PROCESSED_DIR     = "data/processed"
NLP_DIR           = "data/nlp"

# ── Instagram Graph API settings ──────────────────────────────────────────────
IG_BASE_URL       = "https://graph.instagram.com"   # Business Login host — no version prefix
IG_ACCOUNT_FIELDS = "id,username,account_type,media_count"
IG_MEDIA_FIELDS   = "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count"
IG_COMMENT_FIELDS = "id,text,username,timestamp,like_count"

IG_POST_LIMIT     = 25    # posts per page (pagination follows paging.next up to MAX_PAGES)
IG_COMMENT_LIMIT  = 50    # comments per page, per post

# Long-lived tokens last 60 days and are NOT auto-renewed by Meta.
# Refresh proactively once this many days remain.
IG_MIN_TOKEN_DAYS_REMAINING = 10
