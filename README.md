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
| **Continuous run** | `main_ig.py` (2h interval scheduler) | `main_instaloader.py` (3 randomized daily slots) |
| **Files** | `ig_client.py`, `fetch_ig.py`, `main_ig.py` | `fetch_instaloader.py`, `fetch_instaloader_extra.py`, `import_firefox_session.py`, `main_instaloader.py` |

Both paths write into the **same** `save_raw.py` / `save_processed_ig.py` /
`db_manager_ig.py` / `preprocess_ig.py` / `analysis_ig.py` layer — a post is
a post regardless of which path fetched it, distinguished only by a
`source` field (`graph_api` vs `instaloader`). Both paths also log every
attempt (success or failure) through the shared `run_logger.py` module —
see "Run Logging & Failure Tracking" below.

---

## Pipeline Overview

```
                    ┌─ ig_client.py + fetch_ig.py ───────┐  (own account, official API)
accounts.txt / CLI ─┤                                     ├─→ save_raw.py
                    └─ fetch_instaloader.py ──────────────┘  (any public account, session-based)
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

`main_ig.py` orchestrates the official-API path continuously (fetch + save
for the account in `accounts.txt`, on a scheduler). `main_instaloader.py`
orchestrates the Instaloader path continuously in the same spirit, but with
randomized daily timing instead of a fixed interval (see below for why).
Both log every run through `run_logger.py`. Downstream steps
(`preprocess_ig.py` onward) scan `data/processed/` generically regardless
of source, so nothing downstream needs to know which path fetched a post.

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

### Run (single pass)
```bash
python main_ig.py          # fetch + save for accounts.txt
python preprocess_ig.py    # NLP
python analysis_ig.py      # analysis
python visualise_ig.py     # charts
python sentiment_report_ig.py  # report
```

### Run (continuous, multi-day)
`main_ig.py` supports an unattended scheduler mode via `config.py`:
```
SCHEDULER_ENABLED = True
RUN_INTERVAL_HOURS = 2     # hours between each full pipeline run
MAX_RUNS = 0               # 0 = run forever
```
Before every run, it checks the access token's remaining validity
(`ig_client.get_token_days_remaining()`). If below
`IG_MIN_TOKEN_DAYS_REMAINING` (default 10 days), it automatically calls
`refresh_long_lived_token()`, persists the new token to `.env`, and logs the
old vs. new expiry — no manual intervention needed to keep a long-running
scheduler alive.

**Validated:** run continuously, unattended, for 6.7+ days (Aug 23–30 2026)
against the authorized test account with no manual restarts. Self-recovered
from a transient ~12-hour connection-error window without intervention (see
Known Limitations for the one gap this exposed).

---

## Path 2: Instaloader (any public account)

Used when the target account won't/can't authorize this app (e.g. news
outlets, meme pages, public figures) — the official API has no
search/discovery capability for accounts, hashtags, or locations you don't
control.

⚠️ **This path is NOT the official API.** It works by reusing an
already-authenticated browser session, which:
- Violates Instagram's Terms of Service
- Can break without warning whenever Instagram changes its frontend
  (confirmed — happened mid-project, June 2026 GraphQL endpoint deprecation
  broke anonymous-mode fetching entirely)
- Carries real account-risk for whichever account is used — **use a
  dedicated throwaway account, never the account tied to your Graph API
  token**, so a checkpoint/restriction on this path can never take down the
  official-API path

**Never fetches comment text** — only a comment count. Kept deliberately
conservative: no bulk automation beyond the scheduler below, real delays
between requests, capped fetch sizes.

### Setup
1. Install: `pip install instaloader`
2. Log into a **dedicated throwaway** Instagram account completely normally
   in Firefox
3. Close Firefox
4. Import that session (bypasses Instaloader's own `--login` flow, which
   triggered repeated Instagram security checkpoints when tested directly):
   ```bash
   python import_firefox_session.py
   ```

### Run (single fetch)
```bash
python fetch_instaloader.py <username> [limit] [login_as]
python fetch_instaloader.py ndtv 10 your_throwaway_username
```
Anonymous mode (omitting `login_as`) is currently broken by an open,
unresolved Instaloader bug (403 on the GraphQL endpoint) — use the
logged-in/session-import method above.

### Run (continuous, multi-day): `main_instaloader.py`
Unlike the Graph API path, this path deliberately does **not** run on a
fixed interval — a robotic, clockwork request pattern is exactly what
Instagram's anti-scraping detection watches for. Instead:
```bash
python main_instaloader.py
```
- Fires **3 times/day** inside randomized windows (not a fixed clock time):
  morning profile fetch (~9–11am), afternoon hashtag fetch (~2–4pm), evening
  tagged-posts fetch (~7–9pm)
- **Rotates targets day-to-day** across a small real target set (see below),
  so no single account/hashtag gets hit repeatedly
- Every attempt logged via `run_logger.py`, success or failure, same as the
  Graph API path

**Real target set** (India-focused, meme/reel content covering general and
social issues — chosen deliberately, not placeholders):
- **Profile accounts:** `theviralfever`, `rvcjinsta`, `ghantaa`
- **Hashtags:** `indianmemes`, `socialissues`, `desimemes`
- **Location:** Jantar Mantar, Delhi (`location_id 416430758372868`) — a
  well-known protest/social-issues site, chosen to fit the research scope

**Validated:** all four endpoint types (`profile`, `hashtag-experimental`,
`tagged`, `location`) tested successfully against real data. Ran
continuously via the scheduler for 3.5+ days. One real failure observed —
an SSL certificate verification error (self-signed cert in chain, most
likely antivirus/VPN TLS interception on the local machine, not an
Instagram-side issue) — the scheduler logged it and correctly moved on to
the next slot without crashing. See Known Limitations for two bugs this
failure exposed.

### Extra capabilities: `fetch_instaloader_extra.py`

Tested against real data, 2026-07-16 (and again during the multi-day
validation run, 2026-08-26 to 2026-08-30):

| Capability | Status | Notes |
|---|---|---|
| Profile metadata | ✅ Working | Single request, no pagination |
| Tagged posts | ✅ Working | |
| Followers | ✅ Working | ⚠️ High risk — Instagram heavily monitors this |
| Followees | ✅ Working | ⚠️ High risk |
| Stories | ✅ Working | ⚠️ High risk, ephemeral (24h) — 31 items took ~3 min due to deliberate delay |
| Hashtag search | ✅ Working | Instaloader's own `Hashtag.get_posts()` is broken (confirmed multi-year open bug) — fixed by calling `api/v1/tags/web_info/` directly via `get_iphone_json()`, bypassing the library's high-level class entirely. Returns Instagram's "Top" posts for the tag, not a full chronological feed. |
| Location posts | ✅ Working | Same situation and same fix as hashtags — `instaloader.get_location_posts()` is broken (open GitHub issue #2447), fixed via `api/v1/locations/web_info/` directly. Bonus: also returns location metadata (name, category, total post count). |
| Comments (real text) | ⚠️ Uncertain | Generic Instagram server-side "fail" response, not a code bug. Highest-risk function — don't retry repeatedly if it fails. |

```bash
python fetch_instaloader_extra.py profile <username> <login_as>
python fetch_instaloader_extra.py tagged <username> <login_as> [limit]
python fetch_instaloader_extra.py followers <username> <login_as> [limit]
python fetch_instaloader_extra.py followees <username> <login_as> [limit]
python fetch_instaloader_extra.py stories <username> <login_as>
python fetch_instaloader_extra.py comments <post_url> <login_as> [limit]  # use sparingly
python fetch_instaloader_extra.py hashtag-experimental <hashtag> <login_as> [limit]
python fetch_instaloader_extra.py location <location_id> <login_as> [limit]
```

---

## Run Logging & Failure Tracking: `run_logger.py`

Every fetch attempt on **both** paths — success or failure — is recorded as
one JSON line in `run_log.jsonl` (gitignored — operational data, not
source) via `log_attempt(path, target, success, error_type, error_message)`.

Failures are auto-classified into buckets: `rate_limit`, `checkpoint`,
`token_or_session_invalid`, `connection_error`, `target_not_found`,
`unknown`.

```bash
python run_logger.py
```
prints an end-of-window summary: total attempts, success/failure counts per
path, and a failure-type breakdown with percentages.

**Known bug (not yet fixed):** `classify_error()`'s connection-error check
only inspects the exception's *type name*, not its message text. When
`main_instaloader.py` wraps a subprocess failure as a generic `RuntimeError`
(which it always does, since it captures another script's stdout/stderr),
genuine connection/SSL failures get classified as `unknown` instead of
`connection_error`, even though the failure text clearly describes a
connection issue. Confirmed during the multi-day run (2026-08-29): a real
SSL certificate error was logged but bucketed as `unknown`. Fix: check
`msg` (the message text), not just `name`, for connection-related keywords.

**Known bug (not yet fixed):** `fetch_instaloader.py`'s own failure-path
`print()` statement uses a `✗` character, which crashes with
`UnicodeEncodeError` on Windows PowerShell's default `cp1252` console
encoding. The underlying error is still logged correctly before the crash,
so no data is lost, but the script exits with a messy traceback instead of
a clean failure message. Fix: avoid non-ASCII characters in print
statements, or set `PYTHONIOENCODING=utf-8`.

---

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
  orchestrator — run `main_ig.py` and `main_instaloader.py` as separate
  processes/windows.
- **`classify_error()` misclassifies connection/SSL failures as `unknown`**
  when called from `main_instaloader.py`'s subprocess wrapper — see "Run
  Logging & Failure Tracking" above. Not yet fixed.
- **`fetch_instaloader.py` crashes on its own failure-print** on Windows
  due to a Unicode character incompatible with the default console
  encoding — see "Run Logging & Failure Tracking" above. Not yet fixed.
- **Graph API path had one ~12-hour connection-error window** during the
  6.7-day validation run (2026-08-24, 4 consecutive `token_or_session_invalid`
  failures) — self-recovered without intervention. Root cause not confirmed
  (likely transient network/API issue, not an actual expired token, since
  failures were connection errors, not auth rejections).

---

## Project Structure

```
Official API path:
├── main_ig.py                 # Orchestrator (own account, official API) — supports scheduler mode + token auto-refresh
├── ig_client.py                # Graph API HTTP client (retry/backoff, pagination, token refresh)
├── fetch_ig.py                  # Posts + comments fetch, paginated
├── ig_error_handler.py          # Graph API response/error parsing
├── accounts.txt                  # Authorized usernames (own account only, currently)

Instaloader path:
├── fetch_instaloader.py         # Public-account fetch (session-based)
├── fetch_instaloader_extra.py    # profile / tagged / hashtag-experimental / location / followers / followees / stories / comments
├── import_firefox_session.py     # Firefox cookie import, bypasses Instaloader's login flow
├── main_instaloader.py           # Continuous scheduler — 3 randomized daily slots, rotating real targets

Shared pipeline (both paths):
├── config.py                   # Central configuration
├── run_logger.py                # Structured attempt logging + end-of-window summary (both paths)
├── save_raw.py                  # Save raw response
├── save_processed_ig.py         # Save cleaned post fields + nested comments
├── preprocess_ig.py              # Full NLP pipeline
├── db_manager_ig.py              # SQLite schema + insert functions (10 tables)
├── analysis_ig.py                # Compute analysis from DB → JSON
├── visualise_ig.py               # Generate charts from JSON
├── sentiment_report_ig.py        # Auto insight report (Markdown)
├── test_ig.py                     # Standalone smoke test (official API path)
```

---

## Author
**Anubhav Kumar** — B.Tech ECE, BIT Mesra
Research Intern, IIT Guwahati (June–July 2026)
Supervisor: Prof. Prithwijit Guha | Alloted to: Shlok Verman (M.Tech Scholar)
GitHub: [github.com/Anu7hav](https://github.com/Anu7hav)
