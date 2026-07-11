"""
analysis_ig.py
Reads from pipeline_ig.db and computes structured analysis across all accounts.
Adapted from analysis.py (Twitter branch). Mapping: queries->accounts,
tweets->posts, tweet_nlp->post_nlp, eng_retweets/eng_replies/eng_views (no
IG equivalent) -> dropped, eng_comments added.
Outputs: data/analysis/analysis_results_ig.json + printed summary tables.

Run: python analysis_ig.py
"""

import sqlite3
import json
import os
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

DB_PATH    = "pipeline_ig.db"
OUTPUT_DIR = "data/analysis"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_conn():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"{DB_PATH} not found. Run preprocess_ig.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sentiment_by_account(conn) -> dict:
    rows = conn.execute("""
        SELECT a.username, n.final_label, COUNT(*) as count
        FROM post_nlp n
        JOIN posts p       ON p.id = n.post_id
        JOIN fetch_runs r  ON r.id = p.fetch_run_id
        JOIN accounts a    ON a.id = r.account_id
        WHERE n.final_label IS NOT NULL
        GROUP BY a.username, n.final_label
        ORDER BY a.username, n.final_label
    """).fetchall()

    result = {}
    for row in rows:
        acc = row["username"]
        if acc not in result:
            result[acc] = {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
        result[acc][row["final_label"]] = row["count"]
        result[acc]["total"] += row["count"]
    return result


def top_entities_by_account(conn, top_n=10) -> dict:
    rows = conn.execute("""
        SELECT a.username, e.entity_text, e.entity_label,
               SUM(e.frequency) as total_freq
        FROM entities e
        JOIN fetch_runs r ON r.id = e.fetch_run_id
        JOIN accounts a   ON a.id = r.account_id
        GROUP BY a.username, e.entity_text, e.entity_label
        ORDER BY a.username, total_freq DESC
    """).fetchall()

    result = {}
    for row in rows:
        acc = row["username"]
        if acc not in result:
            result[acc] = []
        if len(result[acc]) < top_n:
            result[acc].append({
                "entity": row["entity_text"],
                "label":  row["entity_label"],
                "count":  row["total_freq"]
            })
    return result


def top_hashtags_by_account(conn, top_n=10) -> dict:
    rows = conn.execute("""
        SELECT a.username, h.hashtag, COUNT(*) as count
        FROM hashtags h
        JOIN fetch_runs r ON r.id = h.fetch_run_id
        JOIN accounts a   ON a.id = r.account_id
        GROUP BY a.username, h.hashtag
        ORDER BY a.username, count DESC
    """).fetchall()

    result = {}
    for row in rows:
        acc = row["username"]
        if acc not in result:
            result[acc] = []
        if len(result[acc]) < top_n:
            result[acc].append({"hashtag": row["hashtag"], "count": row["count"]})
    return result


def top_keywords_by_account(conn, top_n=10) -> dict:
    rows = conn.execute("""
        SELECT a.username, k.keyword, COUNT(*) as count
        FROM keywords k
        JOIN fetch_runs r ON r.id = k.fetch_run_id
        JOIN accounts a   ON a.id = r.account_id
        GROUP BY a.username, k.keyword
        ORDER BY a.username, count DESC
    """).fetchall()

    result = {}
    for row in rows:
        acc = row["username"]
        if acc not in result:
            result[acc] = []
        if len(result[acc]) < top_n:
            result[acc].append({"keyword": row["keyword"], "count": row["count"]})
    return result


def engagement_by_account(conn) -> dict:
    rows = conn.execute("""
        SELECT a.username,
               COUNT(*)            as post_count,
               AVG(n.eng_likes)    as avg_likes,
               AVG(n.eng_comments) as avg_comments,
               MAX(n.eng_likes)    as max_likes,
               MAX(n.eng_comments) as max_comments
        FROM post_nlp n
        JOIN posts p      ON p.id = n.post_id
        JOIN fetch_runs r ON r.id = p.fetch_run_id
        JOIN accounts a   ON a.id = r.account_id
        GROUP BY a.username
        ORDER BY avg_likes DESC
    """).fetchall()

    return {
        row["username"]: {
            "post_count":    row["post_count"],
            "avg_likes":     round(row["avg_likes"] or 0, 2),
            "avg_comments":  round(row["avg_comments"] or 0, 2),
            "max_likes":     row["max_likes"] or 0,
            "max_comments":  row["max_comments"] or 0,
        }
        for row in rows
    }


def post_volume_over_time(conn) -> dict:
    rows = conn.execute("""
        SELECT a.username, p.created_at, COUNT(*) as count
        FROM posts p
        JOIN fetch_runs r ON r.id = p.fetch_run_id
        JOIN accounts a   ON a.id = r.account_id
        WHERE p.created_at IS NOT NULL
        GROUP BY a.username, p.created_at
        ORDER BY a.username, p.created_at
    """).fetchall()

    from datetime import datetime as dt
    def parse(s):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return dt.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    from collections import defaultdict
    buckets = defaultdict(lambda: defaultdict(int))
    for row in rows:
        d = parse(row["created_at"])
        if d:
            buckets[row["username"]][d] += row["count"]

    return {
        acc: [{"date": d, "count": c} for d, c in sorted(dates.items())]
        for acc, dates in buckets.items()
    }


def sentiment_agreement(conn) -> dict:
    rows = conn.execute("""
        SELECT vader_label, roberta_label, COUNT(*) as count
        FROM post_nlp
        WHERE vader_label IS NOT NULL AND roberta_label IS NOT NULL
        GROUP BY vader_label, roberta_label
    """).fetchall()

    total   = sum(r["count"] for r in rows)
    agreed  = sum(r["count"] for r in rows if r["vader_label"] == r["roberta_label"])
    rate    = round(agreed / total * 100, 2) if total > 0 else 0

    return {
        "total_posts":    total,
        "agreed":         agreed,
        "disagreed":      total - agreed,
        "agreement_rate": rate,
        "breakdown":      [dict(r) for r in rows]
    }


def source_distribution(conn) -> dict:
    rows = conn.execute("""
        SELECT source, COUNT(*) as count
        FROM posts
        WHERE source IS NOT NULL
        GROUP BY source
        ORDER BY count DESC
    """).fetchall()
    return {row["source"]: row["count"] for row in rows}


def comment_stats_by_post(conn, top_n=10) -> list:
    """No Twitter-branch equivalent — comments are an Instagram-only concept."""
    rows = conn.execute("""
        SELECT p.id, p.caption, a.username,
               COUNT(c.id) as comment_count
        FROM posts p
        JOIN fetch_runs r ON r.id = p.fetch_run_id
        JOIN accounts a   ON a.id = r.account_id
        LEFT JOIN comments c ON c.post_id = p.id
        GROUP BY p.id
        ORDER BY comment_count DESC
        LIMIT ?
    """, (top_n,)).fetchall()
    return [
        {
            "post_id":       row["id"],
            "caption":       (row["caption"] or "")[:60],
            "account":       row["username"],
            "comment_count": row["comment_count"],
        }
        for row in rows
    ]


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_sentiment(sentiment):
    print_section("1. SENTIMENT DISTRIBUTION PER ACCOUNT")
    print(f"{'Account':<25} {'Pos':>6} {'Neu':>6} {'Neg':>6} {'Total':>7}")
    print("-" * 55)
    for acc, s in sentiment.items():
        print(f"{acc:<25} {s['positive']:>6} {s['neutral']:>6} {s['negative']:>6} {s['total']:>7}")


def print_engagement(engagement):
    print_section("2. ENGAGEMENT STATS PER ACCOUNT")
    print(f"{'Account':<25} {'Posts':>6} {'AvgLikes':>9} {'AvgComm':>8} {'MaxLikes':>9}")
    print("-" * 62)
    for acc, e in engagement.items():
        print(f"{acc:<25} {e['post_count']:>6} {e['avg_likes']:>9} {e['avg_comments']:>8} {e['max_likes']:>9}")


def print_top_hashtags(hashtags):
    print_section("3. TOP HASHTAGS PER ACCOUNT (Top 5)")
    for acc, tags in hashtags.items():
        print(f"\n  {acc}:")
        for h in tags[:5]:
            print(f"    #{h['hashtag']:<30} {h['count']:>5}")


def print_top_keywords(keywords):
    print_section("4. TOP KEYWORDS PER ACCOUNT (Top 5)")
    for acc, kws in keywords.items():
        print(f"\n  {acc}:")
        for k in kws[:5]:
            print(f"    {k['keyword']:<32} {k['count']:>5}")


def print_agreement(agreement):
    print_section("5. VADER vs RoBERTa AGREEMENT")
    print(f"  Total posts analysed  : {agreement['total_posts']}")
    print(f"  Agreed                : {agreement['agreed']}")
    print(f"  Disagreed             : {agreement['disagreed']}")
    print(f"  Agreement rate        : {agreement['agreement_rate']}%")


def print_sources(sources):
    print_section("6. SOURCE DISTRIBUTION")
    for src, count in sources.items():
        print(f"  {src:<25} {count:>6} posts")


def print_most_commented(posts):
    print_section("7. MOST-COMMENTED POSTS")
    for p in posts:
        print(f"  [{p['comment_count']:>3}] {p['post_id']}  ({p['account']})  {p['caption']!r}")


if __name__ == "__main__":
    log.info("Starting analysis...")
    conn = get_conn()

    sentiment      = sentiment_by_account(conn)
    entities       = top_entities_by_account(conn)
    hashtags       = top_hashtags_by_account(conn)
    keywords       = top_keywords_by_account(conn)
    engagement     = engagement_by_account(conn)
    volume         = post_volume_over_time(conn)
    agreement      = sentiment_agreement(conn)
    sources        = source_distribution(conn)
    most_commented = comment_stats_by_post(conn)

    conn.close()

    print_sentiment(sentiment)
    print_engagement(engagement)
    print_top_hashtags(hashtags)
    print_top_keywords(keywords)
    print_agreement(agreement)
    print_sources(sources)
    print_most_commented(most_commented)

    results = {
        "generatedAt":    datetime.now().isoformat(),
        "sentiment":      sentiment,
        "entities":       entities,
        "hashtags":       hashtags,
        "keywords":       keywords,
        "engagement":     engagement,
        "volume":         volume,
        "agreement":      agreement,
        "sources":        sources,
        "most_commented": most_commented,
    }

    out_path = os.path.join(OUTPUT_DIR, "analysis_results_ig.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log.info(f"Analysis complete → {out_path}")
    print(f"\n✓ Full results saved to {out_path}")
