# Instagram Data Acquisition & Analysis Pipeline

A pipeline for acquiring, preprocessing, and analysing Instagram post data,
with sentiment analysis (VADER + RoBERTa), named entity recognition (spaCy),
topic modelling (BERTopic), and keyword extraction (TF-IDF).

Two independent data-source paths feed the same downstream pipeline:

| | Official Graph API | Instaloader (session-based) |
|---|---|---|
| **Source accounts** | Only accounts that explicitly authorize this app as a Tester (realistically: accounts you control) | Any public account, no authorization needed |
| **Comment text** | ✅ Full comment text and metadata | ❌ Comment count only, no text |
| **Stability / ToS** | Sanctioned, stable, official | Unofficial — breaks when Instagram changes its frontend, violates Instagram's ToS, carries real account-risk |
| **Files** | `ig_client.py`, `fetch_ig.py`, `main_ig.py` | `fetch_instaloader.py`, `import_firefox_session.py` |

Both paths write into the **same** `save_raw.py` / `save_processed_ig.py` /
`db_manager_ig.py` / `preprocess_ig.py` / `analysis_ig.py` layer — a post is
a post regardless of which path fetched it, distinguished only by a
`source` field (`graph_api` vs `instaloader`).

---

## Pipeline Overview

```
                    ┌─ ig_client.py + fetch_ig.py ─────────┐  (own account, official API)
accounts.txt / CLI ─┤                                       ├─→ save_raw.py
                    └─ fetch_instaloader.py ─────────────────┘  (any public account, session-based)
                                    │
                                    ▼
                    save_processed_ig.py → data/processed/
                                    │
                                    ▼
                    preprocess_ig.py → data/nlp/ + pipeline_ig.db
                                    │
                                    ▼
                    analysis_ig.py → data/analysis/
                                    │
                                    ▼
        visualise_ig.py → data/charts/     sentiment_report_ig.py → report_ig.md
```

`main_ig.py` only orchestrates the official-API path (fetch + save for the
account in `accounts.txt`). The Instaloader path is currently a separate
manual script — run it, then run `preprocess_ig.py` onward same as always,
since those steps scan `data/processed/` generically regardless of source.

---

## Path 1: Official Graph API (own account)

### Setup
- developers.facebook.com → Create App → Business
- Add Instagram product → "API setup with Instagram login" (Business Login —
  does NOT require linking a Facebook Page)
- Add your Instagram account as an **Instagram Tester** (App Roles → Roles)
- Grant `instagram_business_basic` + `instagram_business_manage_comments`
  under Permissions and features — **both** need to show "Ready for testing,"
  not just "added" (confirmed bug: "Add all required permissions" alone did
  not activate `manage_comments`; had to click "Add" on that row individually)
- Generate a long-lived access token
- **Publish the app to Live mode** — required for `/comments` to return real
  data. In Development mode it silently returns an empty array with no error,
  even when `comments_count` on the post is nonzero.

### Run
```bash
python main_ig.py          # fetch + save for accounts.txt
python preprocess_ig.py    # NLP
python analysis_ig.py      # analysis
python visualise_ig.py     # charts
python sentiment_report_ig.py  # report
```

---

## Path 2: Instaloader (any public account)

Used when the target account won't/can't authorize this app (e.g. news
outlets, public figures) — the official API has no search/discovery
capability for accounts you don't control.

⚠️ **This path is NOT the official API.** It works by reusing an
already-authenticated browser session, which:
- Violates Instagram's Terms of Service
- Can break without warning whenever Instagram changes its frontend
  (confirmed — happened mid-project, June 2026 GraphQL endpoint deprecation
  broke anonymous-mode fetching entirely)
- Carries real account-risk for whichever account is used

**Never fetches comment text** — only a comment count. Kept deliberately
conservative: no bulk automation, small manual runs, real delays between
requests.

### Setup
1. Install: `pip install instaloader`
2. Log into Instagram **completely normally** in Firefox, using an account
   you're comfortable using for this (not a primary personal account)
3. Close Firefox
4. Import that session (bypasses Instaloader's own login flow, which
   triggered repeated Instagram security checkpoints when tested directly):
   ```bash
   python import_firefox_session.py
   ```

### Run
```bash
python fetch_instaloader.py <username> [limit] [login_as]
python fetch_instaloader.py ndtv 10 your_account_username
```
Anonymous mode (omitting `login_as`) is currently broken by an open,
unresolved Instaloader bug (403 on the GraphQL endpoint) — use the
logged-in/session-import method above.

### Extra capabilities: `fetch_instaloader_extra.py`

Tested against real data, 2026-07-16:

| Capability | Status | Notes |
|---|---|---|
| Profile metadata | ✅ Working | Single request, no pagination |
| Tagged posts | ✅ Working | |
| Followers | ✅ Working | ⚠️ High risk — Instagram heavily monitors this |
| Followees | ✅ Working | ⚠️ High risk |
| Stories | ✅ Working | ⚠️ High risk, ephemeral (24h) — 31 items took ~3 min due to deliberate delay |
| Hashtag search | ❌ Broken | Confirmed open Instaloader bug — `KeyError: edge_hashtag_to_media` |
| Location posts | ❌ Broken | Confirmed open Instaloader bug (GitHub #2447) — `201 Created` error |
| Comments (real text) | ⚠️ Uncertain | Generic Instagram server-side "fail" response, not a code bug. Highest-risk function — don't retry repeatedly if it fails. |

```bash
python fetch_instaloader_extra.py profile <username> <login_as>
python fetch_instaloader_extra.py tagged <username> <login_as> [limit]
python fetch_instaloader_extra.py followers <username> <login_as> [limit]
python fetch_instaloader_extra.py followees <username> <login_as> [limit]
python fetch_instaloader_extra.py stories <username> <login_as>
python fetch_instaloader_extra.py comments <post_url> <login_as> [limit]  # use sparingly
```



## Database Schema (10 Tables)

| Table | Description |
|-------|-------------|
| `accounts` | Unique Instagram usernames pulled (either path) |
| `fetch_runs` | One row per processed JSON file |
| `posts` | Base post fields — caption, media type/url, likes, comment count, `source` |
| `comments` | Flattened per-post comments — empty for Instaloader-sourced posts |
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

- **Comment TEXT only available via the official API**, and only for
  accounts that authorize this app — Instaloader never returns comment
  content, only counts, for any account.
- **Instaloader path is inherently unstable** — it broke once already
  during this project (Instagram deprecated a GraphQL endpoint in June
  2026) and could break again without warning. Not suitable as the sole
  data source for anything that needs long-term reliability.
- **Single account per token** on the official API path — `accounts.txt`
  supports listing multiple usernames structurally, but `fetch_ig.py`
  always pulls the token's own account via the `/me` alias.
- **Comment-level NLP not implemented** — sentiment/entities/keywords run
  on post captions only.
- **`SCHEDULER_ENABLED`** defaults to `False`. Flip deliberately, not by
  accident.
- Official API and Instaloader paths are NOT wired into a single
  orchestrator — run them as separate manual steps.

---

## Project Structure

```
Official API path:
├── main_ig.py              # Orchestrator (own account, official API)
├── ig_client.py              # Graph API HTTP client (retry/backoff, pagination, token refresh)
├── fetch_ig.py                # Posts + comments fetch, paginated
├── ig_error_handler.py        # Graph API response/error parsing
├── accounts.txt                # Authorized usernames (own account only, currently)

Instaloader path:
├── fetch_instaloader.py       # Public-account fetch (session-based)
├── import_firefox_session.py  # Firefox cookie import, bypasses Instaloader's login flow

Shared pipeline (both paths):
├── config.py                # Central configuration
├── save_raw.py                # Save raw response
├── save_processed_ig.py       # Save cleaned post fields + nested comments
├── preprocess_ig.py           # Full NLP pipeline
├── db_manager_ig.py           # SQLite schema + insert functions (10 tables)
├── analysis_ig.py             # Compute analysis from DB → JSON
├── visualise_ig.py            # Generate charts from JSON
├── sentiment_report_ig.py     # Auto insight report (Markdown)
├── test_ig.py                  # Standalone smoke test (official API path)
```

---

## Author
**Anubhav Kumar** — B.Tech ECE, BIT Mesra
Research Intern, IIT Guwahati (June–July 2026)
Supervisor: Prof. Prithwijit Guha | Alloted to: Shlok Verman (M.Tech Scholar)
GitHub: [github.com/Anu7hav](https://github.com/Anu7hav)
