"""
preprocess_ig.py
Preprocessing pipeline for collected Instagram post data.
Adapted from preprocess.py (Twitter branch). Key differences, and why:

  - No isRetweet concept — that filter is simply dropped.
  - Twitter's is_valid() requires 5+ words of text, which would silently
    discard most real Instagram posts: captions are frequently empty
    (confirmed on our own test data — a real post with caption=None).
    Here, a missing/short caption does NOT disqualify a post — it just
    skips caption-dependent NLP (sentiment/keywords/entities default to
    neutral/empty) rather than dropping engagement data (likes, comments)
    that's still perfectly valid to store and analyze.
  - Language filtering only runs when there IS caption text to detect a
    language from; captionless posts pass through language-agnostic.
  - get_engagement() drops retweets/replies/views/bookmarks (no IG
    equivalent) and adds comment_count instead.
  - Comment text itself is NOT run through the full NLP pipeline here
    (sentiment/entities/keywords) — only post captions are. Comments are
    stored as-is via db_manager_ig.insert_comments(). Extending this to
    score individual comments (e.g. "is this comment negative?") is a
    reasonable next step but a separate table/pass, not bolted on here.
"""

import re
import json
import os
import logging
from collections import Counter
from datetime import datetime

from langdetect import detect, LangDetectException
from langdetect import DetectorFactory
DetectorFactory.seed = 0

import nltk
from nltk.corpus import stopwords
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True)

import spacy
import emoji as emoji_lib
from tqdm import tqdm

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

SKIP_DB_WRITE = os.environ.get("SKIP_DB_WRITE", "0") == "1"

if not SKIP_DB_WRITE:
    from db_manager_ig import (get_conn, init_db, upsert_account, insert_fetch_run,
                                insert_posts, insert_comments, insert_nlp, insert_entities,
                                insert_hashtags, insert_keywords,
                                insert_topics, insert_events)
    init_db()

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from sklearn.feature_extraction.text import TfidfVectorizer

log = logging.getLogger(__name__)

try:
    from bertopic import BERTopic
    BERTOPIC_AVAILABLE = True
except ImportError:
    BERTOPIC_AVAILABLE = False
    log.warning("BERTopic not installed — topic modelling disabled.")

vader              = SentimentIntensityAnalyzer()
ROBERTA_MODEL      = "cardiffnlp/twitter-roberta-base-sentiment"
_roberta_tokenizer = AutoTokenizer.from_pretrained(ROBERTA_MODEL)
_roberta_model     = AutoModelForSequenceClassification.from_pretrained(ROBERTA_MODEL)
_roberta_model     = _roberta_model.to(DEVICE)
_roberta_model.eval()
ROBERTA_LABELS     = ["negative", "neutral", "positive"]

nlp       = spacy.load("en_core_web_sm")
STOPWORDS = set(stopwords.words("english"))

NEUTRAL_VADER   = {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0, "label": "neutral", "confidence": 1.0}
NEUTRAL_ROBERTA = {"label": "neutral", "scores": {"negative": 0.0, "neutral": 1.0, "positive": 0.0}, "confidence": 1.0}


def extract_hashtags(text): return re.findall(r"#(\w+)", text) if text else []
def extract_mentions(text): return re.findall(r"@(\w+)", text) if text else []
def extract_urls(text):     return re.findall(r"http\S+|www\S+", text) if text else []
def extract_emojis(text):   return [e["emoji"] for e in emoji_lib.emoji_list(text)] if text else []

def clean_text(text) -> str:
    if not text: return ""
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#(\w+)", r"\1", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_valid(post: dict, allowed_langs=["en"]) -> bool:
    cleaned = clean_text(post.get("caption", ""))
    if not cleaned:
        return True  # captionless posts are valid — engagement data still matters
    try:
        if detect(cleaned) not in allowed_langs:
            return False
    except LangDetectException:
        pass  # can't detect on very short text — don't penalize for it
    return True


def deduplicate(posts: list) -> list:
    seen_ids, unique = set(), []
    for post in posts:
        pid = post.get("id")
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        unique.append(post)
    return unique


def batch_roberta_sentiment(texts: list) -> list:
    results, batch_size = [], 16
    for i in tqdm(range(0, len(texts), batch_size), desc="  RoBERTa sentiment", leave=False):
        batch = texts[i: i + batch_size]
        try:
            encoded = _roberta_tokenizer(batch, return_tensors="pt", truncation=True, max_length=512, padding=True)
            inputs  = {k: v.to(DEVICE) for k, v in encoded.items()}
            with torch.no_grad():
                logits = _roberta_model(**inputs).logits
            for probs in torch.softmax(logits, dim=1).cpu().tolist():
                label      = ROBERTA_LABELS[probs.index(max(probs))]
                confidence = round(max(probs), 4)
                scores     = {l: round(p, 4) for l, p in zip(ROBERTA_LABELS, probs)}
                results.append({"label": label, "scores": scores, "confidence": confidence})
        except Exception:
            for _ in batch:
                results.append(dict(NEUTRAL_ROBERTA))
    return results


def get_final_sentiment(vader: dict, roberta: dict) -> dict:
    """
    BUG FIX (mentor review): previously final_label was hardcoded to
    roberta['label'] unconditionally — post['sentiment']['final_label'] =
    roberta['label'] — meaning VADER was computed and stored but never
    actually used for anything. This compares confidence scores and picks
    whichever model is more confident, exactly as specified.
    """
    if vader["confidence"] > roberta["confidence"]:
        return {
            "label": vader["label"],
            "confidence": vader["confidence"],
            "source": "VADER"
        }
    return {
        "label": roberta["label"],
        "confidence": roberta["confidence"],
        "source": "RoBERTa"
    }


def get_vader_sentiment(text: str) -> dict:
    if not text:
        return dict(NEUTRAL_VADER)
    s = vader.polarity_scores(text)
    c = s["compound"]
    label = "positive" if c>=0.05 else "negative" if c<=-0.05 else "neutral"
    # confidence on the same 0-1 scale as RoBERTa's softmax max-probability
    # (max of pos/neu/neg), NOT abs(compound) — needed so get_final_sentiment()
    # compares like with like rather than two differently-scaled numbers.
    confidence = round(max(s["pos"], s["neu"], s["neg"]), 4)
    return {"compound": round(c,4), "pos": round(s["pos"],4), "neu": round(s["neu"],4),
            "neg": round(s["neg"],4), "label": label, "confidence": confidence}


def batch_tfidf_keywords(texts: list, top_n=10) -> list:
    non_empty = [t for t in texts if t]
    if len(non_empty) < 2:
        return [[] for _ in texts]
    try:
        vec    = TfidfVectorizer(max_features=500, stop_words="english", ngram_range=(1,2))
        matrix = vec.fit_transform(texts)
        terms  = vec.get_feature_names_out()
        return [[t for t,s in sorted(zip(terms, row.toarray()[0]), key=lambda x:x[1], reverse=True)[:top_n] if s>0]
                for row in matrix]
    except Exception:
        return [[] for _ in texts]


def get_topics_bertopic(texts: list) -> list:
    non_empty = [t for t in texts if t]
    if not BERTOPIC_AVAILABLE or len(non_empty) < 5:
        return []
    try:
        from umap import UMAP
        from hdbscan import HDBSCAN

        n = len(non_empty)
        umap_model = UMAP(
            n_neighbors  = min(n - 1, 15),
            n_components = min(n - 1, 5),
            min_dist     = 0.0,
            metric       = "cosine",
            random_state = 42
        )
        hdbscan_model = HDBSCAN(
            min_cluster_size = 2,
            min_samples      = 1,
            prediction_data  = True
        )
        model = BERTopic(
            umap_model     = umap_model,
            hdbscan_model  = hdbscan_model,
            verbose        = False,
            nr_topics      = "auto",
            min_topic_size = 2
        )
        topics, _ = model.fit_transform(non_empty)
        info      = model.get_topic_info()
        result    = []
        for _, row in info[info["Topic"] != -1].head(5).iterrows():
            words = [w for w, _ in model.get_topic(row["Topic"])]
            result.append({"topic_id": int(row["Topic"]), "words": words[:5]})
        return result
    except Exception as e:
        log.warning(f"BERTopic failed: {e}")
        return []


def detect_events(posts: list, top_n=5) -> list:
    all_kw = []
    for p in posts: all_kw.extend(p.get("keywords", []))
    freq  = Counter(all_kw)
    total = sum(freq.values()) or 1
    return [{"keyword": kw, "count": cnt, "freq_ratio": round(cnt/total, 4)}
            for kw, cnt in freq.most_common(top_n)]


def get_engagement(post: dict) -> dict:
    return {
        "likes":    post.get("likeCount", 0),
        "comments": post.get("commentCount", 0),
    }


def preprocess_file(filepath: str, output_dir: str = "data/nlp"):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    original_count = len(data.get("posts", []))
    posts = data.get("posts", [])

    posts        = [p for p in posts if is_valid(p)]
    after_filter = len(posts)
    posts        = deduplicate(posts)
    after_dedup  = len(posts)

    if not posts:
        log.warning(f"  {original_count} → 0 posts after filtering — skipping {filepath}")
        return None

    for post in posts:
        raw = post.get("caption") or ""
        post["hashtags"]     = extract_hashtags(raw)
        post["mentions"]     = extract_mentions(raw)
        post["emojis"]       = extract_emojis(raw)
        post["urls"]         = extract_urls(raw)
        post["cleaned_text"] = clean_text(raw)

    cleaned_texts = [p["cleaned_text"] for p in posts]
    docs = list(tqdm(nlp.pipe(cleaned_texts, batch_size=50), total=len(cleaned_texts), desc="  spaCy NER", leave=False))

    for post, doc in zip(posts, docs):
        post["tokens"]            = [t.text.lower() for t in doc if t.is_alpha and t.text.lower() not in STOPWORDS]
        post["lemmatized_tokens"] = [t.lemma_.lower() for t in doc if t.is_alpha and t.lemma_.lower() not in STOPWORDS]
        entities                  = [{"text": e.text, "label": e.label_} for e in doc.ents]
        post["entities"]          = entities
        post["entity_freq"]       = dict(Counter([e["text"] for e in entities]))
        post["engagement"]        = get_engagement(post)

    for post in tqdm(posts, desc="  VADER sentiment", leave=False):
        post["sentiment"] = {"vader": get_vader_sentiment(post["cleaned_text"])}

    roberta_results = batch_roberta_sentiment(cleaned_texts)
    for post, roberta in zip(posts, roberta_results):
        vader = post["sentiment"]["vader"]
        post["sentiment"]["roberta"] = roberta
        final = get_final_sentiment(vader, roberta)
        post["sentiment"]["final"]          = final  # matches mentor-specified nested shape
        post["sentiment"]["final_label"]      = final["label"]       # flat keys kept for
        post["sentiment"]["final_confidence"] = final["confidence"]  # backward compatibility
        post["sentiment"]["final_source"]     = final["source"]      # with db_manager_ig.py

    tfidf_keywords = batch_tfidf_keywords(cleaned_texts)
    for post, kws in zip(posts, tfidf_keywords):
        post["keywords"] = kws

    topics = get_topics_bertopic(cleaned_texts)
    events = detect_events(posts)

    result = {
        "metadata": {
            **data.get("metadata", {}),
            "preprocessedAt": datetime.now().isoformat(),
            "originalCount":  original_count,
            "afterFilter":    after_filter,
            "afterDedup":     after_dedup,
            "finalCount":     len(posts),
            "device":         str(DEVICE),
        },
        "topics": topics,
        "events": events,
        "posts": posts,
    }

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(filepath)
    out_path = os.path.join(output_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"  ✓ {original_count} → {len(posts)} posts | Saved → {out_path}")

    if not SKIP_DB_WRITE:
        nlp_fname = os.path.basename(out_path)
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM fetch_runs WHERE nlp_file = ?", (nlp_fname,)
            ).fetchone()
            if existing:
                log.warning(f"  Already ingested {nlp_fname} — skipping DB write")
            else:
                account_id = upsert_account(conn, result["metadata"].get("account", "unknown"))
                run_id     = insert_fetch_run(conn, account_id, result["metadata"],
                                               processed_file=os.path.basename(filepath),
                                               nlp_file=nlp_fname)
                insert_posts(conn, run_id, data.get("posts", []),
                             default_source=result["metadata"].get("apiSource"))
                insert_comments(conn, run_id, data.get("posts", []))
                insert_hashtags(conn, run_id, posts)
                insert_nlp(conn, run_id, posts)
                insert_entities(conn, run_id, posts)
                insert_keywords(conn, run_id, posts)
                insert_topics(conn, run_id, topics)
                insert_events(conn, run_id, events)
                log.info(f"  ✓ Written to pipeline_ig.db")

    return out_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    processed_dir = "data/processed"
    files = []
    for root, dirs, filenames in os.walk(processed_dir):
        for f in filenames:
            if f.endswith(".json"):
                files.append(os.path.join(root, f))

    log.info(f"Found {len(files)} processed files")
    for fp in tqdm(files, desc="Files"):
        log.info(f"Processing: {fp}")
        result = preprocess_file(fp)
        if result is None:
            log.warning(f"  Skipped (no posts after filtering): {fp}")
