# Instagram Data Acquisition & Analysis Pipeline

A complete end-to-end pipeline for acquiring, preprocessing, and analysing
Instagram Business/Creator account data via the official Instagram Graph API
(Business Login) — NOT scraping. Includes sentiment analysis (VADER +
RoBERTa), named entity recognition (spaCy), topic modelling (BERTopic), and
keyword extraction (TF-IDF).

---

## Pipeline Overview

```
accounts.txt
    │
    ▼
main_ig.py                          ← orchestrates one full pass
    │
    ├─ ig_client.py                 ← Graph API HTTP client (retry/backoff, pagination)
    ├─ fetch_ig.py                  ← pulls posts + comments for one account
    │
    ▼
save_raw.py → data/raw/             ← raw API response
    │
    ▼
save_processed_ig.py → data/processed/  ← cleaned post fields + nested comments
    │
    ▼
preprocess_ig.py → data/nlp/        ← NLP enrichment (spaCy, VADER, RoBERTa, BERTopic, TF-IDF)
    │                                  + writes directly to pipeline_ig.db
    ▼
analysis_ig.py → data/analysis/     ← JSON results, queries pipeline_ig.db
    │
    ▼
visualise_ig.py → data/charts/      ← 5–7 charts (PNG)
sentiment_report_ig.py → report_ig.md  ← auto-generated insight report
```

**Note:** `main_ig.py` only runs fetch + save. NLP/analysis/charts are
separate manual steps (`preprocess_ig.py` → `analysis_ig.py` →
`visualise_ig.py` → `sentiment_report_ig.py`), run individually as needed.

---

## Why Only the Official Graph API

Unofficial scraping of Instagram gets accounts flagged/banned quickly, so
this pipeline uses **only** the official Graph API. Practical implications:

- Requires a registered Meta Developer app + Instagram Business/Creator account
- Can only pull data for accounts you have tester/admin access to — not
  arbitrary public accounts (see `accounts.txt`)
- A Business Login token is tied to exactly one account — true multi-account
  support isn't built yet; `accounts.txt` currently only supports one real entry
- Comments get their own DB table (`comments`) and their own report section

---

## Setup

### 1. Register a Meta Developer app
- developers.facebook.com → Create App → Business
- Add Instagram product → "API setup with Instagram login" (Business Login —
  does NOT require linking a Facebook Page, unlike the older Facebook Login flow)
- Add your Instagram account as an **Instagram Tester** (App Roles → Roles)
- Grant `instagram_business_basic` + `instagram_business_manage_comments`
  under Permissions and features — **both** need to show "Ready for testing",
  not just be added to the app's permission list (confirmed bug: adding via
  "Add all required permissions" alone did not activate `manage_comments`;
  had to click "Add" on that row individually)
- Generate a long-lived access token from the App Dashboard
- **Publish the app to Live mode** — required for the `/comments` endpoint to
  return real data. In Development mode, `/comments` returns an empty `data`
  array even when `comments_count` on the media object is nonzero, with no
  error to explain why. Check this first if comments ever silently come back
  empty.

### 2. Clone and set up
```bash
git clone https://github.com/Anu7hav/instagram-acquisition-pipeline.git
cd instagram-acquisition-pipeline
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Configure environment
Create a `.env` file in the root directory (never commit this):
```
IG_ACCESS_TOKEN=your_long_lived_token
IG_APP_SECRET=your_app_secret
IG_ACCOUNT_ID=your_ig_business_account_id
```

### 4. Add accounts
Edit `accounts.txt` — currently only one real entry is usable (see the
multi-account limitation above):
```
your_instagram_username
```

---

## Running the Pipeline

### Full acquisition run
```bash
python main_ig.py
```
Fetches posts + comments for the account in `accounts.txt`, saves raw +
processed JSON. Set `SCHEDULER_ENABLED = True` in `config.py` to run on a
loop (`RUN_INTERVAL_HOURS`) — defaults to `False` (single run) for safety.

### Preprocess NLP
```bash
python preprocess_ig.py
```
Runs spaCy NER, VADER, RoBERTa, TF-IDF, BERTopic on all `data/processed/`
files, writes to `data/nlp/` and `pipeline_ig.db`. Captionless posts
(common on Instagram) are NOT dropped — only caption-dependent NLP fields
default to neutral/empty; engagement data is always kept.

### Run analysis
```bash
python analysis_ig.py
```
Generates `data/analysis/analysis_results_ig.json` — sentiment, entities,
hashtags, keywords, engagement, volume, VADER/RoBERTa agreement, most-commented
posts.

### Generate charts
```bash
python visualise_ig.py
```
Saves up to 7 charts to `data/charts/`. Wordcloud/hashtag charts skip
gracefully (with a warning, not a crash) if no captions/hashtags exist yet.

### Auto insight report
```bash
python sentiment_report_ig.py
```
Generates `data/analysis/report_ig.md`.

---

## Database Schema (10 Tables)

| Table | Description |
|-------|-------------|
| `accounts` | Unique Instagram usernames pulled |
| `fetch_runs` | One row per processed JSON file |
| `posts` | Base post fields — caption, media type/url, likes, comment count |
| `comments` | Flattened per-post comments |
| `post_nlp` | NLP enrichment — sentiment, tokens, entities |
| `entities` | Named entities, normalized |
| `hashtags` | One row per hashtag per post (NLP-derived from captions) |
| `keywords` | TF-IDF keywords per post |
| `topics` | BERTopic output per run |
| `events` | Keyword frequency events per run |

---

## NLP Stack

| Task | Library | Model |
|------|---------|-------|
| Text cleaning | spaCy | `en_core_web_sm` |
| Named Entity Recognition | spaCy | `en_core_web_sm` |
| Sentiment (lexical) | VADER | `vaderSentiment` |
| Sentiment (transformer) | HuggingFace | `cardiffnlp/twitter-roberta-base-sentiment` |
| Topic modelling | BERTopic | UMAP + HDBSCAN (needs 5+ non-empty captions) |
| Keyword extraction | scikit-learn | TF-IDF |

---

## Known Limitations / Open Items

- **Only tested at small scale so far** — real volume (dozens of posts, deep
  comment threads) should be stress-tested before relying on this in production.
- **Single account per token** — `accounts.txt` supports listing multiple
  usernames structurally, but `fetch_ig.py` always pulls the token's own
  account via the `/me` alias. Real multi-account support needs per-account
  token management, not built yet.
- **Comment-level NLP not implemented** — sentiment/entities/keywords run on
  post captions only; individual comment text is stored but not analyzed.
- **`SCHEDULER_ENABLED`** defaults to `False`. Flip deliberately, not by
  accident — it loops for `RUN_INTERVAL_HOURS` (default 2h) indefinitely
  otherwise.
- **Access token rotated 2026-07-11 as a final security precaution before repo handoff/review.

---

## Project Structure

```
├── main_ig.py              # Pipeline entry point + scheduler
├── config.py                # Central configuration
├── ig_client.py              # Graph API HTTP client (retry/backoff, pagination, token refresh)
├── fetch_ig.py                # Posts + comments fetch, paginated
├── ig_error_handler.py        # Graph API response/error parsing
├── save_raw.py                # Save raw API response
├── save_processed_ig.py       # Save cleaned post fields + nested comments
├── preprocess_ig.py           # Full NLP pipeline
├── db_manager_ig.py           # SQLite schema + insert functions (10 tables)
├── analysis_ig.py             # Compute analysis from DB → JSON
├── visualise_ig.py            # Generate charts from JSON
├── sentiment_report_ig.py     # Auto insight report (Markdown)
├── test_ig.py                  # Standalone smoke test (fetch → save → DB insert)
└── accounts.txt                # IG usernames (currently single-account only)
```

---

## Author
**Anubhav Kumar** — B.Tech ECE, BIT Mesra
Research Intern, IIT Guwahati (June–July 2026)
Supervisor: Prof. Prithwijit Guha | Alloted to: Shlok Verman (M.Tech Scholar)
GitHub: [github.com/Anu7hav](https://github.com/Anu7hav)
