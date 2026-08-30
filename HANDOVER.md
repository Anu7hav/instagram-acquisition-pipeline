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
regardless of which method fetched it. Both also run **continuously and
unattended** via their own scheduler (`main_ig.py` / `main_instaloader.py`),
logging every attempt through a shared `run_logger.py`.

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
python fetch_instaloader.py theviralfever 5 your_throwaway_username
python fetch_instaloader_extra.py profile theviralfever your_throwaway_username
python fetch_instaloader_extra.py tagged theviralfever your_throwaway_username 5
python fetch_instaloader_extra.py hashtag-experimental indianmemes your_throwaway_username 5
python fetch_instaloader_extra.py location 416430758372868 your_throwaway_username 5
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

### 3.6 Multi-day continuous run validation (mentor-requested, completed)

Both paths were run continuously and unattended, per instruction, without
manual restarts during the window. Full raw log: `run_log.jsonl`
(gitignored — available on request).

**Token refresh:** wired into `main_ig.py`; verified by manually forcing a
refresh (temporarily raising `IG_MIN_TOKEN_DAYS_REMAINING`) — confirmed it
fires, persists to `.env` and `token_state.json`, and logs old→new expiry.
During the actual unattended window the token stayed at 58–60 days
remaining throughout (well above the 10-day threshold), so a refresh never
naturally triggered — noted honestly rather than claimed.

**Graph API path (`main_ig.py`, `SCHEDULER_ENABLED=True`,
`RUN_INTERVAL_HOURS=2`):**
- Window: 2026-08-23 ~12:34 to 2026-08-30 ~05:32 — **6.7+ days**,
  uninterrupted, untouched
- 45+ runs completed
- One real failure window: 2026-08-24, 4 consecutive
  `token_or_session_invalid` failures (connection errors, not an actual
  expired token) spanning ~12 hours; self-recovered without any manual
  intervention

**Instaloader path (`main_instaloader.py`, 3 randomized daily
slots/rotating real targets):**
- Window: 2026-08-26 ~16:29 onward — 3.5+ days
- Real target set used (not placeholders — chosen for relevance to the
  general/social-issues meme content research focus, India-focused):
  accounts `theviralfever`, `rvcjinsta`, `ghantaa`; hashtags
  `indianmemes`, `socialissues`, `desimemes`; location: Jantar Mantar,
  Delhi (`416430758372868`) — a well-known protest site
- All four `fetch_instaloader_extra.py` endpoint types
  (`profile`, `hashtag-experimental`, `tagged`, `location`) exercised
  successfully against real data
- One real failure observed: an SSL certificate verification error
  (self-signed cert in chain — most likely local antivirus/VPN TLS
  interception, not an Instagram-side block) on 2026-08-29. The scheduler
  logged it and correctly moved on to the next slot without crashing.
- **This failure exposed two real bugs**, documented in README.md's "Run
  Logging & Failure Tracking" section and not yet fixed:
  1. `classify_error()` only inspects the exception type name, so
     connection/SSL failures relayed through `main_instaloader.py`'s
     subprocess wrapper get bucketed as `unknown` instead of
     `connection_error`
  2. `fetch_instaloader.py` crashes with `UnicodeEncodeError` on its own
     failure-print (`✗` character vs. Windows `cp1252` console) — the
     underlying error is still logged correctly before the crash, so no
     data is lost, but the traceback is messy

**Failure logging (`run_logger.py`):** every attempt on both paths,
success or failure, logged with timestamp, path, target, and a classified
error type; `python run_logger.py` produces the end-of-window summary
(total attempts, per-path success/failure counts, failure-type breakdown).

---

## 4. What To Look At Specifically

- **`data/analysis/report_ig.md`** — the single best artifact to review;
  human-readable summary of everything the pipeline found
- **`data/charts/`** — visual sentiment/engagement/hashtag breakdowns
- **`pipeline_ig.db`** — the actual relational data, queryable directly
  with any SQLite browser if you want to inspect it more deeply
- **`run_log.jsonl`** — the raw multi-day run log (gitignored, available
  on request) — every attempt on both paths, timestamped and classified

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
- **Two known bugs in the failure-logging path**, found during the
  multi-day validation run, not yet fixed: `classify_error()`
  misclassifies connection/SSL failures as `unknown` when relayed through
  `main_instaloader.py`'s subprocess wrapper, and `fetch_instaloader.py`
  crashes on its own failure-print due to a Unicode/Windows-console
  incompatibility. Neither causes data loss — the underlying error is
  still logged before either issue occurs. Full detail in README.md.
- **Instaloader path used a dedicated throwaway account** (`login_as`),
  deliberately kept separate from the Graph API path's authorized account,
  so a checkpoint/restriction on the fragile path can never affect the
  official-API path.

---

## 6. Full File Reference

See `README.md` in the repo for the complete file-by-file breakdown,
database schema, NLP stack details, and the run-logging design — this
document is the "how to verify it works" companion to that.
