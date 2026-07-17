# Project Handover — Instagram Data Acquisition & Analysis Pipeline

**Author:** Anubhav Kumar
**Repo:** https://github.com/Anu7hav/instagram-acquisition-pipeline

---

## 1. What This Project Does (Plain Language)

This pipeline collects Instagram posts, reels, and engagement data (likes,
comments), then runs sentiment analysis, topic detection, and keyword
extraction on the captions — producing charts and a written report.

It solves two different problems, using two different methods, because
Instagram's official API and the project's actual needs don't fully overlap:

- **Deep monitoring of accounts we control** — full data, including actual
  comment text — via Instagram's **official Graph API**.
- **Broad collection from public accounts, hashtags, and locations we
  don't control** (news pages, meme pages, topic-based content) — via
  **Instaloader**, since Instagram's official API has no search/discovery
  capability at all for accounts outside our own.

Both methods feed the same downstream analysis pipeline — a post is a post
regardless of which method fetched it.

---

## 2. How It Works (Architecture)

```
                    +- Official Graph API -------+   (own account only,
accounts.txt / CLI -+   ig_client.py + fetch_ig.py|    includes real comment text)
                    +- Instaloader ---------------+   (any public account/
                       fetch_instaloader*.py            hashtag/location,
                                    |                    posts + engagement only)
                                    v
                    save_raw.py -> data/raw/          (untouched API response)
                                    |
                                    v
                    save_processed_ig.py -> data/processed/   (cleaned fields)
                                    |
                                    v
                    preprocess_ig.py -> pipeline_ig.db + data/nlp/
                                    |        (spaCy NER, VADER + RoBERTa
                                    |         sentiment, BERTopic, TF-IDF)
                                    v
                    analysis_ig.py -> data/analysis/   (JSON summary stats)
                                    |
                                    v
        visualise_ig.py -> data/charts/     sentiment_report_ig.py -> report_ig.md
              (7 PNG charts)                    (auto-written markdown report)
```

---

## 3. How To Test This Yourself

Everything below can be run and verified independently.

### 3.1 Setup (one-time)

```bash
git clone https://github.com/Anu7hav/instagram-acquisition-pipeline.git
cd instagram-acquisition-pipeline
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

You'll need a `.env` file (not in the repo — sent separately or set up
fresh per the README's Path 1 setup instructions) with:
```
IG_ACCESS_TOKEN=...
IG_APP_SECRET=...
IG_ACCOUNT_ID=...
```

### 3.2 Test Path 1 — Official API (own account)

```bash
python test_ig.py
```

**Expected output:** confirms the token, fetches real posts + comments from
the authorized test account, saves raw + processed JSON, inserts into
`pipeline_ig.db`. This is the fully official, sanctioned data path.

### 3.3 Test Path 2 — Instaloader (public accounts)

First, a one-time session setup (see README "Path 2" section for full
steps) — log into a throwaway Instagram account in Firefox, then:
```bash
python import_firefox_session.py
```

Then test each capability:
```bash
python fetch_instaloader.py ndtv 5 your_account_username
python fetch_instaloader_url.py https://www.instagram.com/reel/SOME_CODE/ your_account_username
python fetch_instaloader_extra.py hashtag-experimental memes your_account_username 5
python fetch_instaloader_extra.py location-experimental 213385402 your_account_username 5
```

**Expected output for each:** a list of real, current Instagram posts —
captions, media type, like/comment counts — saved to `data/raw/` and
`data/processed/`.

### 3.4 Test the full analysis pipeline

```bash
python preprocess_ig.py     # runs NLP on everything fetched so far
python analysis_ig.py       # prints a full summary to terminal + saves JSON
python visualise_ig.py      # generates charts in data/charts/
python sentiment_report_ig.py   # generates data/analysis/report_ig.md
```

**What to check:** `analysis_ig.py`'s terminal output shows sentiment
broken down per account, engagement stats, top hashtags/keywords, and
VADER-vs-RoBERTa model agreement — all computed from real fetched data, not
placeholders. Open `data/analysis/report_ig.md` for the plain-English
write-up, and the PNGs in `data/charts/` for visuals.

### 3.5 Quick database check (optional, for verification)

```bash
python -c "import sqlite3; c = sqlite3.connect('pipeline_ig.db'); print(c.execute('SELECT COUNT(*) FROM posts').fetchone())"
```
Confirms real rows exist in the database, not just files on disk.

---

## 4. What To Look At Specifically

- **`data/analysis/report_ig.md`** — the single best artifact to review;
  human-readable summary of everything the pipeline found
- **`data/charts/`** — visual sentiment/engagement/hashtag breakdowns
- **`pipeline_ig.db`** — the actual relational data, queryable directly
  with any SQLite browser if you want to inspect it more deeply

---

## 5. Honest Limitations (Read This Before Judging Scope)

- **Comment text is only available via the official API**, and only for
  accounts that explicitly authorize this app. Instaloader never returns
  comment content for accounts we don't own — only a count.
- **The Instaloader path is not the official API.** It works by reusing an
  authenticated browser/app session, which violates Instagram's Terms of
  Service and carries real account-risk. It broke once already mid-project
  (Instagram changed a backend endpoint in June 2026) and was fixed by
  calling a newer endpoint directly — it could break again without warning
  in the future. This is documented honestly in the README, not hidden.
- **Hashtag/location results are Instagram's algorithmic "Top" posts**,
  not a comprehensive chronological feed — a real constraint of the
  endpoints available, not a code limitation.
- **Single account per token** on the official API path — genuine
  multi-account support (beyond what Instaloader can reach) would need
  separate tokens per account, not built.
- **Tested at small-to-moderate scale so far** — proven against real data
  from multiple accounts/hashtags/locations, but not stress-tested at high
  volume.

---

## 6. Full File Reference

See `README.md` in the repo for the complete file-by-file breakdown,
database schema, and NLP stack details — this document is the "how to
verify it works" companion to that.
