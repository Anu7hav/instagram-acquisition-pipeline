"""
db_manager_ig.py
SQLite database layer — Instagram Acquisition Pipeline
Adapted from db_manager.py (Twitter branch). Schema mapping vs. Twitter:

    queries    -> accounts     (tracks IG usernames instead of search strings)
    tweets     -> posts        (drops retweet/reply/view fields — no IG equivalent;
                                 adds media_type, media_url)
    tweet_nlp  -> post_nlp     (same structure, keyed by post_id)
    entities, hashtags, keywords, topics, events -> unchanged structure,
                                 still NLP-derived from caption text, keyed by post_id
    (none)     -> comments     (NEW — flattens the nested comments list from
                                 save_processed_ig.py, same pattern hashtags
                                 uses to flatten out of nested tweet data)

10 Tables:
    1. accounts     — unique IG usernames pulled
    2. fetch_runs    — one per processed JSON file
    3. posts         — base post fields          (data/processed/)
    4. comments      — flattened per-post comments
    5. post_nlp      — NLP enrichment on captions (data/nlp/)
    6. entities      — named entities, normalized
    7. hashtags      — one row per hashtag per post (normalized, NLP-derived)
    8. keywords      — one row per TF-IDF keyword per post (normalized)
    9. topics        — BERTopic output per run
    10. events        — keyword frequency events per run
"""

import sqlite3
import json
import logging
from contextlib import contextmanager
from datetime import datetime

log = logging.getLogger(__name__)
DB_PATH = "pipeline_ig.db"

SEMANTIC_ENTITY_LABELS = {
    "PERSON", "ORG", "GPE", "LOC", "EVENT",
    "PRODUCT", "WORK_OF_ART", "LAW", "LANGUAGE", "NORP"
}


@contextmanager
def get_conn(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH):
    with get_conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE,
                created_at  TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fetch_runs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id       INTEGER NOT NULL REFERENCES accounts(id),
                fetched_at       TEXT,
                api_source       TEXT,
                post_count       INTEGER,
                preprocessed_at  TEXT,
                original_count   INTEGER,
                after_filter     INTEGER,
                after_dedup      INTEGER,
                final_count      INTEGER,
                device           TEXT,
                processed_file   TEXT,
                nlp_file         TEXT
            );
            CREATE TABLE IF NOT EXISTS posts (
                id               TEXT    PRIMARY KEY,
                fetch_run_id     INTEGER NOT NULL REFERENCES fetch_runs(id),
                caption          TEXT,
                media_type       TEXT,
                media_url        TEXT,
                created_at       TEXT,
                like_count       INTEGER DEFAULT 0,
                comment_count    INTEGER DEFAULT 0,
                url              TEXT,
                source           TEXT
            );
            CREATE TABLE IF NOT EXISTS comments (
                id           TEXT    PRIMARY KEY,
                post_id      TEXT    NOT NULL REFERENCES posts(id),
                fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
                text         TEXT,
                username     TEXT,
                created_at   TEXT,
                like_count   INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS post_nlp (
                post_id           TEXT    PRIMARY KEY REFERENCES posts(id),
                fetch_run_id      INTEGER NOT NULL REFERENCES fetch_runs(id),
                cleaned_text      TEXT,
                tokens            TEXT    DEFAULT '[]',
                lemmatized_tokens TEXT    DEFAULT '[]',
                mentions          TEXT    DEFAULT '[]',
                emojis            TEXT    DEFAULT '[]',
                urls              TEXT    DEFAULT '[]',
                vader_compound    REAL,
                vader_pos         REAL,
                vader_neu         REAL,
                vader_neg         REAL,
                vader_label       TEXT,
                vader_confidence  REAL,
                roberta_label     TEXT,
                roberta_neg       REAL,
                roberta_neu       REAL,
                roberta_pos       REAL,
                roberta_confidence REAL,
                final_label       TEXT,
                final_confidence  REAL,
                final_source      TEXT,
                eng_likes         INTEGER DEFAULT 0,
                eng_comments      INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS entities (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id      TEXT    NOT NULL REFERENCES posts(id),
                fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
                entity_text  TEXT    NOT NULL,
                entity_label TEXT    NOT NULL,
                frequency    INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS hashtags (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id      TEXT    NOT NULL REFERENCES posts(id),
                fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
                hashtag      TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS keywords (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id      TEXT    NOT NULL REFERENCES posts(id),
                fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
                keyword      TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topics (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
                topic_id     INTEGER NOT NULL,
                words        TEXT    DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                fetch_run_id INTEGER NOT NULL REFERENCES fetch_runs(id),
                keyword      TEXT    NOT NULL,
                count        INTEGER NOT NULL,
                freq_ratio   REAL
            );
            CREATE INDEX IF NOT EXISTS idx_posts_run       ON posts(fetch_run_id);
            CREATE INDEX IF NOT EXISTS idx_posts_created   ON posts(created_at);
            CREATE INDEX IF NOT EXISTS idx_comments_post   ON comments(post_id);
            CREATE INDEX IF NOT EXISTS idx_nlp_label       ON post_nlp(final_label);
            CREATE INDEX IF NOT EXISTS idx_nlp_vader       ON post_nlp(vader_compound);
            CREATE INDEX IF NOT EXISTS idx_entities_text   ON entities(entity_text);
            CREATE INDEX IF NOT EXISTS idx_entities_label  ON entities(entity_label);
            CREATE INDEX IF NOT EXISTS idx_hashtags_tag    ON hashtags(hashtag);
            CREATE INDEX IF NOT EXISTS idx_keywords_kw     ON keywords(keyword);
            CREATE INDEX IF NOT EXISTS idx_runs_account    ON fetch_runs(account_id);
        """)
    log.info(f"Database initialized → {db_path} (10 tables)")


def _j(value) -> str:
    if value is None: return "[]"
    return json.dumps(value, ensure_ascii=False)


def upsert_account(conn, username: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO accounts (username, created_at) VALUES (?, ?)",
        (username, datetime.now().isoformat())
    )
    return conn.execute("SELECT id FROM accounts WHERE username = ?", (username,)).fetchone()["id"]


def insert_fetch_run(conn, account_id: int, metadata: dict,
                      processed_file=None, nlp_file=None) -> int:
    cur = conn.execute("""
        INSERT INTO fetch_runs
            (account_id, fetched_at, api_source, post_count,
             preprocessed_at, original_count, after_filter,
             after_dedup, final_count, device, processed_file, nlp_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (account_id, metadata.get("fetchedAt"), metadata.get("apiSource"),
          metadata.get("postCount"), metadata.get("preprocessedAt"),
          metadata.get("originalCount"), metadata.get("afterFilter"),
          metadata.get("afterDedup"), metadata.get("finalCount"),
          metadata.get("device"), processed_file, nlp_file))
    return cur.lastrowid


def insert_posts(conn, fetch_run_id: int, posts: list, default_source=None) -> int:
    inserted = 0
    for p in posts:
        source = p.get("source") or default_source
        try:
            cur = conn.execute("""
                INSERT OR IGNORE INTO posts
                    (id, fetch_run_id, caption, media_type, media_url,
                     created_at, like_count, comment_count, url, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(p.get("id")), fetch_run_id, p.get("caption"),
                  p.get("mediaType"), p.get("mediaUrl"), p.get("createdAt"),
                  p.get("likeCount", 0), p.get("commentCount", 0),
                  p.get("url"), source))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            log.warning(f"Post insert failed {p.get('id')}: {e}")
    return inserted


def insert_comments(conn, fetch_run_id: int, posts: list) -> int:
    """Flattens each post's nested comments list into its own table row —
    same pattern insert_hashtags() uses for tweets' nested hashtags."""
    inserted = 0
    for p in posts:
        post_id = str(p.get("id"))
        for c in p.get("comments", []):
            try:
                cur = conn.execute("""
                    INSERT OR IGNORE INTO comments
                        (id, post_id, fetch_run_id, text, username, created_at, like_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (str(c.get("id")), post_id, fetch_run_id,
                      c.get("text"), c.get("username"), c.get("timestamp"),
                      c.get("likeCount", 0)))
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                log.warning(f"Comment insert failed {c.get('id')}: {e}")
    return inserted


def insert_nlp(conn, fetch_run_id: int, posts: list) -> int:
    inserted = 0
    for p in posts:
        post_id    = str(p.get("id"))
        sentiment  = p.get("sentiment", {})
        vader      = sentiment.get("vader", {})
        roberta    = sentiment.get("roberta", {})
        final      = sentiment.get("final", {})
        rob_scores = roberta.get("scores", {})
        eng        = p.get("engagement", {})
        try:
            conn.execute("""
                INSERT OR REPLACE INTO post_nlp
                    (post_id, fetch_run_id, cleaned_text,
                     tokens, lemmatized_tokens, mentions, emojis, urls,
                     vader_compound, vader_pos, vader_neu, vader_neg, vader_label, vader_confidence,
                     roberta_label, roberta_neg, roberta_neu, roberta_pos, roberta_confidence,
                     final_label, final_confidence, final_source,
                     eng_likes, eng_comments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, fetch_run_id, p.get("cleaned_text"),
                  _j(p.get("tokens", [])), _j(p.get("lemmatized_tokens", [])),
                  _j(p.get("mentions", [])), _j(p.get("emojis", [])), _j(p.get("urls", [])),
                  vader.get("compound"), vader.get("pos"), vader.get("neu"), vader.get("neg"),
                  vader.get("label"), vader.get("confidence"),
                  roberta.get("label"), rob_scores.get("negative"), rob_scores.get("neutral"),
                  rob_scores.get("positive"), roberta.get("confidence"),
                  final.get("label", sentiment.get("final_label")),
                  final.get("confidence", sentiment.get("final_confidence")),
                  final.get("source", sentiment.get("final_source")),
                  eng.get("likes", 0), eng.get("comments", 0)))
            inserted += 1
        except Exception as e:
            log.warning(f"NLP insert failed {post_id}: {e}")
    return inserted


def insert_entities(conn, fetch_run_id: int, posts: list) -> int:
    inserted = 0
    for p in posts:
        post_id     = str(p.get("id"))
        entity_freq = p.get("entity_freq", {})
        seen        = set()
        for ent in p.get("entities", []):
            key = (post_id, ent.get("text",""), ent.get("label",""))
            if key in seen:
                continue
            if ent.get("label", "") not in SEMANTIC_ENTITY_LABELS:
                continue
            seen.add(key)
            try:
                conn.execute("""
                    INSERT INTO entities
                        (post_id, fetch_run_id, entity_text, entity_label, frequency)
                    VALUES (?, ?, ?, ?, ?)
                """, (post_id, fetch_run_id,
                      ent.get("text",""), ent.get("label",""),
                      entity_freq.get(ent.get("text",""), 1)))
                inserted += 1
            except Exception as e:
                log.warning(f"Entity insert failed: {e}")
    return inserted


def insert_hashtags(conn, fetch_run_id: int, posts: list) -> int:
    """NLP-derived — Instagram captions aren't structured like tweet
    entities, so hashtags get extracted from caption text in preprocess.py,
    same as they would be for any free-text field."""
    inserted = 0
    for p in posts:
        post_id = str(p.get("id"))
        seen = set()
        for tag in p.get("hashtags", []):
            if tag and tag.lower() not in seen:
                seen.add(tag.lower())
                try:
                    conn.execute(
                        "INSERT INTO hashtags (post_id, fetch_run_id, hashtag) VALUES (?, ?, ?)",
                        (post_id, fetch_run_id, tag.lower()))
                    inserted += 1
                except Exception as e:
                    log.warning(f"Hashtag insert failed: {e}")
    return inserted


def insert_keywords(conn, fetch_run_id: int, posts: list) -> int:
    inserted = 0
    for p in posts:
        post_id = str(p.get("id"))
        seen = set()
        for kw in p.get("keywords", []):
            if kw and kw not in seen:
                seen.add(kw)
                try:
                    conn.execute(
                        "INSERT INTO keywords (post_id, fetch_run_id, keyword) VALUES (?, ?, ?)",
                        (post_id, fetch_run_id, kw))
                    inserted += 1
                except Exception as e:
                    log.warning(f"Keyword insert failed: {e}")
    return inserted


def insert_topics(conn, fetch_run_id: int, topics: list) -> int:
    inserted = 0
    for topic in topics:
        conn.execute(
            "INSERT INTO topics (fetch_run_id, topic_id, words) VALUES (?, ?, ?)",
            (fetch_run_id, topic.get("topic_id"), _j(topic.get("words", []))))
        inserted += 1
    return inserted


def insert_events(conn, fetch_run_id: int, events: list) -> int:
    inserted = 0
    for event in events:
        conn.execute(
            "INSERT INTO events (fetch_run_id, keyword, count, freq_ratio) VALUES (?, ?, ?, ?)",
            (fetch_run_id, event.get("keyword"), event.get("count"), event.get("freq_ratio")))
        inserted += 1
    return inserted
