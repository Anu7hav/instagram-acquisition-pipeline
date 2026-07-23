"""
sentiment_report_ig.py
Auto-generates a human-readable markdown insight report from analysis_results_ig.json.
Adapted from sentiment_report.py (Twitter branch).

Dropped: the "Crisis vs Non-Crisis Sentiment" section — that was a hardcoded
keyword match against query strings (flood/conflict/attack/etc.), which
doesn't map to Instagram since "queries" are now account usernames, not
search topics. Forcing that section to "work" would just produce noise.

Added: "Most-Commented Posts" — uses comment data Twitter's version never had.

Output: data/analysis/report_ig.md
Run: python sentiment_report_ig.py
"""

import json
import os
import sys
from datetime import datetime

INPUT  = "data/analysis/analysis_results_ig.json"
OUTPUT = "data/analysis/report_ig.md"

if not os.path.exists(INPUT):
    print(f"ERROR: {INPUT} not found. Run analysis_ig.py first.")
    sys.exit(1)

with open(INPUT, encoding="utf-8") as f:
    data = json.load(f)

sentiment      = data["sentiment"]
engagement     = data["engagement"]
agreement      = data["agreement"]
entities       = data["entities"]
hashtags       = data["hashtags"]
keywords       = data["keywords"]
most_commented = data.get("most_commented", [])

lines = []
w = lines.append

w("# Instagram NLP Pipeline — Insight Report")
w(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
w(f"**Accounts analysed:** {len(sentiment)}  ")
w(f"**Total posts:** {sum(s['total'] for s in sentiment.values()):,}\n")
w("---\n")

w("## 1. Sentiment Distribution\n")

if sentiment:
    neg_sorted = sorted(sentiment.items(), key=lambda x: x[1]["negative"] / max(x[1]["total"],1), reverse=True)
    most_neg = neg_sorted[0]
    neg_pct = most_neg[1]["negative"] / max(most_neg[1]["total"], 1) * 100

    pos_sorted = sorted(sentiment.items(), key=lambda x: x[1]["positive"] / max(x[1]["total"],1), reverse=True)
    most_pos = pos_sorted[0]
    pos_pct = most_pos[1]["positive"] / max(most_pos[1]["total"], 1) * 100

    neu_sorted = sorted(sentiment.items(), key=lambda x: x[1]["neutral"] / max(x[1]["total"],1), reverse=True)
    most_neu = neu_sorted[0]
    neu_pct = most_neu[1]["neutral"] / max(most_neu[1]["total"], 1) * 100

    w(f"- **Most negative account:** `{most_neg[0]}` — {neg_pct:.1f}% negative posts")
    w(f"- **Most positive account:** `{most_pos[0]}` — {pos_pct:.1f}% positive posts")
    w(f"- **Most neutral account:** `{most_neu[0]}` — {neu_pct:.1f}% neutral posts\n")

    w("| Account | Positive | Neutral | Negative | Total |")
    w("|---------|----------|---------|----------|-------|")
    for acc, s in sorted(sentiment.items(), key=lambda x: x[1]["negative"], reverse=True):
        t = max(s["total"], 1)
        w(f"| {acc} | {s['positive']/t*100:.0f}% | {s['neutral']/t*100:.0f}% | {s['negative']/t*100:.0f}% | {s['total']} |")
    w("")

w("## 2. VADER vs RoBERTa Agreement\n")
w(f"- **Agreement rate:** {agreement['agreement_rate']}%")
w(f"- **Total posts compared:** {agreement['total_posts']:,}")
w(f"- **Agreed:** {agreement['agreed']:,} | **Disagreed:** {agreement['disagreed']:,}")
w(f"\n> A {agreement['agreement_rate']}% agreement rate indicates {'strong' if agreement['agreement_rate'] > 60 else 'moderate'} "
  f"alignment between the rule-based (VADER) and transformer-based (RoBERTa) models. "
  f"On Instagram this is measured against captions only — many posts have no caption "
  f"at all, which both models score as neutral by default, inflating agreement on "
  f"caption-light accounts.\n")

w("## 3. Engagement Analysis\n")
if engagement:
    top_eng = sorted(engagement.items(), key=lambda x: x[1]["avg_likes"], reverse=True)
    w(f"- **Highest avg likes:** `{top_eng[0][0]}` — {top_eng[0][1]['avg_likes']:.1f} likes/post")
    top_comments = max(engagement.items(), key=lambda x: x[1]["avg_comments"])
    w(f"- **Highest avg comments:** `{top_comments[0]}` — {top_comments[1]['avg_comments']:.1f} comments/post\n")

    w("| Account | Posts | Avg Likes | Avg Comments |")
    w("|---------|-------|-----------|--------------|")
    for acc, e in top_eng[:10]:
        w(f"| {acc} | {e['post_count']} | {e['avg_likes']:.1f} | {e['avg_comments']:.1f} |")
    w("")

w("## 4. Top Named Entities (All Accounts)\n")
all_ents = {}
for acc, elist in entities.items():
    for e in elist:
        key = (e["entity"], e["label"])
        all_ents[key] = all_ents.get(key, 0) + e["count"]

top_ents = sorted(all_ents.items(), key=lambda x: x[1], reverse=True)[:15]
if top_ents:
    w("| Entity | Type | Frequency |")
    w("|--------|------|-----------|")
    for (text, label), freq in top_ents:
        w(f"| {text} | {label} | {freq} |")
else:
    w("*No named entities extracted yet — most captions are empty or too short.*")
w("")

w("## 5. Top Hashtags per Account\n")
if hashtags:
    for acc, tags in list(hashtags.items())[:8]:
        top5 = ", ".join([f"`#{t['hashtag']}`" for t in tags[:5]])
        w(f"- **{acc}:** {top5}")
else:
    w("*No hashtags found in captions yet.*")
w("")

w("## 6. Most-Commented Posts\n")
if most_commented:
    w("| Post ID | Account | Caption | Comments |")
    w("|---------|---------|---------|----------|")
    for p in most_commented[:10]:
        cap = p["caption"] or "*(no caption)*"
        w(f"| {p['post_id']} | {p['account']} | {cap} | {p['comment_count']} |")
else:
    w("*No comments recorded yet.*")
w("")

w("## 7. Key Findings\n")
w("### Engagement vs Sentiment Correlation")
if engagement and sentiment:
    high_eng = sorted(engagement.items(), key=lambda x: x[1]["avg_likes"], reverse=True)[:5]
    w("Top accounts by engagement and their dominant sentiment:")
    for acc, e in high_eng:
        if acc in sentiment:
            s = sentiment[acc]
            counts = {label: s[label] for label in ["positive", "neutral", "negative"]}
            max_count = max(counts.values())
            tied_labels = [label for label, count in counts.items() if count == max_count]
            # BUG FIX (mentor review): max(["positive","neutral","negative"], key=lambda x: s[x])
            # silently returned "positive" on every exact tie, since Python's max() picks the
            # first element achieving the max value and "positive" is listed first — a genuine
            # 1/1/1 split was confidently reported as "dominant sentiment: positive". Now
            # detects ties explicitly and reports "mixed" instead of guessing.
            if len(tied_labels) > 1:
                dominant = f"mixed ({'/'.join(tied_labels)} tied at {max_count})"
            else:
                dominant = tied_labels[0]
            w(f"- `{acc}`: {e['avg_likes']:.1f} avg likes — dominant sentiment: **{dominant}**")
w("")

w("---")
w(f"*Report generated by `sentiment_report_ig.py` | Instagram Acquisition Pipeline*")

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"✓ Report saved → {OUTPUT}")
