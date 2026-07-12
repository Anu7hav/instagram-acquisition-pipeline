"""
visualise_ig.py
Reads analysis_results_ig.json and generates charts saved to data/charts/
Adapted from visualise.py (Twitter branch). Chart 4 swaps "Avg Retweets" for
"Avg Comments" (no retweet concept on Instagram). Chart 5's source pie is
mostly informational now since there's only one source (graph_api) — kept
for structural parity in case a second source is ever added.

Run: python visualise_ig.py
"""

import json
import os
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from wordcloud import WordCloud
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

ANALYSIS_PATH = "data/analysis/analysis_results_ig.json"
CHARTS_DIR    = "data/charts"
os.makedirs(CHARTS_DIR, exist_ok=True)

COLORS = {
    "positive": "#2ecc71",
    "neutral":  "#3498db",
    "negative": "#e74c3c",
}
PALETTE = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B",
           "#44BBA4", "#E94F37", "#393E41", "#F5A623", "#7B2D8B"]


def load():
    if not os.path.exists(ANALYSIS_PATH):
        raise FileNotFoundError(f"{ANALYSIS_PATH} not found. Run analysis_ig.py first.")
    with open(ANALYSIS_PATH, encoding="utf-8") as f:
        return json.load(f)


def short(q, max_len=20):
    return q if len(q) <= max_len else q[:max_len] + "…"


def chart_sentiment(sentiment: dict):
    accounts = list(sentiment.keys())
    labels   = [short(a) for a in accounts]
    pos      = [sentiment[a]["positive"] for a in accounts]
    neu      = [sentiment[a]["neutral"]  for a in accounts]
    neg      = [sentiment[a]["negative"] for a in accounts]

    x   = range(len(accounts))
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.bar(x, neg, label="Negative", color=COLORS["negative"])
    ax.bar(x, neu, bottom=neg, label="Neutral",  color=COLORS["neutral"])
    ax.bar(x, pos, bottom=[n + nu for n, nu in zip(neg, neu)],
           label="Positive", color=COLORS["positive"])

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Post Count")
    ax.set_title("Sentiment Distribution per Account (RoBERTa)", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "01_sentiment_distribution.png")
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"  ✓ Saved → {path}")


def chart_wordcloud(keywords: dict):
    freq = defaultdict(int)
    for kws in keywords.values():
        for k in kws:
            freq[k["keyword"]] += k["count"]

    if not freq:
        log.warning("No keywords found — skipping word cloud")
        return

    wc = WordCloud(
        width=1400, height=700,
        background_color="white",
        colormap="tab20",
        max_words=150,
        collocations=False,
    ).generate_from_frequencies(freq)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("Top Keywords — All Accounts Combined", fontsize=14, fontweight="bold")
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "02_wordcloud_keywords.png")
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"  ✓ Saved → {path}")


def chart_hashtags(hashtags: dict):
    if not hashtags:
        log.warning("No hashtags found — skipping hashtag chart")
        return

    fig, axes = plt.subplots(
        nrows=(len(hashtags) + 1) // 2, ncols=2,
        figsize=(16, max(6, 3 * ((len(hashtags) + 1) // 2)))
    )
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for idx, (account, tags) in enumerate(hashtags.items()):
        top    = tags[:8]
        names  = [f"#{t['hashtag']}" for t in top]
        counts = [t["count"] for t in top]
        color  = PALETTE[idx % len(PALETTE)]

        axes[idx].barh(names[::-1], counts[::-1], color=color)
        axes[idx].set_title(short(account, 28), fontsize=10, fontweight="bold")
        axes[idx].set_xlabel("Count", fontsize=8)
        axes[idx].tick_params(axis="y", labelsize=8)

    for idx in range(len(hashtags), len(axes)):
        axes[idx].set_visible(False)

    plt.suptitle("Top Hashtags per Account", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "03_top_hashtags.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"  ✓ Saved → {path}")


def chart_engagement(engagement: dict):
    accounts     = list(engagement.keys())
    labels       = [short(a) for a in accounts]
    avg_likes    = [engagement[a]["avg_likes"]    for a in accounts]
    avg_comments = [engagement[a]["avg_comments"] for a in accounts]

    x   = range(len(accounts))
    w   = 0.35
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.bar([i - w/2 for i in x], avg_likes,    w, label="Avg Likes",    color="#F18F01")
    ax.bar([i + w/2 for i in x], avg_comments, w, label="Avg Comments", color="#2E86AB")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Average Count")
    ax.set_title("Engagement Comparison per Account", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "04_engagement_comparison.png")
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"  ✓ Saved → {path}")


def chart_sources(sources: dict):
    labels = list(sources.keys())
    sizes  = list(sources.values())
    colors = ["#2E86AB", "#A23B72", "#F18F01"][:len(labels)]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=140,
        textprops={"fontsize": 12}
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")

    ax.set_title("Post Source Distribution\n(Instagram Graph API)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "05_source_distribution.png")
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"  ✓ Saved → {path}")


def chart_agreement(agreement: dict):
    import pandas as pd
    labels = ["negative", "neutral", "positive"]
    matrix = {l: {l2: 0 for l2 in labels} for l in labels}

    for row in agreement["breakdown"]:
        v = row.get("vader_label")
        r = row.get("roberta_label")
        if v in matrix and r in matrix[v]:
            matrix[v][r] = row["count"]

    df  = pd.DataFrame(matrix, index=labels, columns=labels)
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(df, annot=True, fmt="d", cmap="Blues",
                xticklabels=["VADER: " + l for l in labels],
                yticklabels=["RoBERTa: " + l for l in labels],
                ax=ax)
    ax.set_title(
        f"VADER vs RoBERTa Agreement\n(Agreement rate: {agreement['agreement_rate']}%)",
        fontsize=13, fontweight="bold"
    )
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "06_vader_roberta_agreement.png")
    plt.savefig(path, dpi=150)
    plt.close()
    log.info(f"  ✓ Saved → {path}")


def chart_volume(volume: dict):
    from datetime import datetime

    def parse_date(d: str):
        d = d.strip()
        for fmt in ("%Y-%m-%d", "%a %b %d", "%b %d"):
            try:
                dt = datetime.strptime(d, fmt)
                if dt.year == 1900:
                    dt = dt.replace(year=2026)
                return dt
            except ValueError:
                continue
        return None

    fig, ax = plt.subplots(figsize=(16, 6))

    for idx, (account, points) in enumerate(volume.items()):
        if not points:
            continue
        parsed = [(parse_date(p["date"]), p["count"]) for p in points]
        parsed = [(d, c) for d, c in parsed if d is not None]
        if not parsed:
            continue
        parsed.sort(key=lambda x: x[0])
        dates  = [x[0] for x in parsed]
        counts = [x[1] for x in parsed]
        color  = PALETTE[idx % len(PALETTE)]
        ax.plot(dates, counts, marker="o", label=short(account, 22),
                color=color, linewidth=1.8, markersize=4)

    ax.set_xlabel("Date")
    ax.set_ylabel("Post Count")
    ax.set_title("Post Volume Over Time per Account", fontsize=14, fontweight="bold")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))

    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %Y"))
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.tight_layout()

    path = os.path.join(CHARTS_DIR, "07_post_volume_over_time.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"  ✓ Saved → {path}")


if __name__ == "__main__":
    log.info("Loading analysis results...")
    data = load()

    log.info("Generating charts...")
    chart_sentiment(data["sentiment"])
    chart_wordcloud(data["keywords"])
    chart_hashtags(data["hashtags"])
    chart_engagement(data["engagement"])
    chart_sources(data["sources"])
    chart_agreement(data["agreement"])
    chart_volume(data["volume"])

    log.info(f"All charts saved to {CHARTS_DIR}/")
    print(f"\n✓ Charts saved to {CHARTS_DIR}/")
