import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Instagram Data Acquisition & Analysis",
    page_icon="◎",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CSS_FILE = BASE_DIR / "styles" / "style.css"
DB_PATH = BASE_DIR / "data" / "pipeline_ig.db"
# Architecture is rendered as native HTML/CSS; no image file is required.


# ============================================================
# LOAD CSS
# ============================================================

if CSS_FILE.exists():
    css = CSS_FILE.read_text(encoding="utf-8")
    st.markdown(
        "<style>" + css + "</style>",
        unsafe_allow_html=True,
    )


def render_architecture():
    """Render the system architecture using native Streamlit components only."""
    st.markdown("**FIG. 01 / SYSTEM ARCHITECTURE**")

    # Source
    with st.container(border=True):
        st.markdown("### INSTAGRAM SOURCES")
        st.caption("accounts.txt / CLI / target accounts")

    st.markdown("<div style='text-align:center;font-size:28px;'>↓</div>", unsafe_allow_html=True)

    # Acquisition paths
    left, right = st.columns(2, gap="medium")

    with left:
        with st.container(border=True):
            st.caption("01A")
            st.markdown("### OFFICIAL GRAPH API")
            st.write("`ig_client.py` + `fetch_ig.py`")
            st.caption("Authorized structured acquisition")

    with right:
        with st.container(border=True):
            st.caption("01B")
            st.markdown("### INSTALOADER")
            st.write("`fetch_instaloader*.py`")
            st.caption("Public-account acquisition")

    st.markdown(
        "<div style='text-align:center;font-size:28px;margin:8px 0;'>↘ &nbsp;&nbsp; ↙</div>",
        unsafe_allow_html=True,
    )

    # Persistence
    with st.container(border=True):
        st.caption("02")
        st.markdown("### DATA PERSISTENCE")
        st.write("`save_raw.py` → `save_processed_ig.py`")

    st.markdown("<div style='text-align:center;font-size:28px;'>↓</div>", unsafe_allow_html=True)

    # Preprocessing
    with st.container(border=True):
        st.caption("03")
        st.markdown("### PREPROCESSING")
        st.write("`preprocess_ig.py`")

    st.markdown("<div style='text-align:center;font-size:28px;'>↓</div>", unsafe_allow_html=True)

    # NLP / feature extraction
    c1, c2, c3 = st.columns(3, gap="medium")

    with c1:
        with st.container(border=True):
            st.markdown("### SENTIMENT")
            st.caption("VADER + RoBERTa + fusion")

    with c2:
        with st.container(border=True):
            st.markdown("### NER")
            st.caption("Named-entity extraction")

    with c3:
        with st.container(border=True):
            st.markdown("### TF-IDF")
            st.caption("Keyword weighting")

    st.markdown(
        "<div style='text-align:center;font-size:28px;margin:8px 0;'>↘ &nbsp;&nbsp; ↓ &nbsp;&nbsp; ↙</div>",
        unsafe_allow_html=True,
    )

    # Final research store
    with st.container(border=True):
        st.caption("04")
        st.markdown("### PIPELINE_IG.DB → ANALYSIS → RESULTS")
        st.caption(
            "SQLite research store • `analysis_ig.py` • reports • visualizations"
        )


# ============================================================
# DATABASE
# ============================================================

@st.cache_data
def load_database():
    """Load the research database into pandas DataFrames."""

    conn = sqlite3.connect(DB_PATH)

    posts = pd.read_sql_query(
        "SELECT * FROM posts",
        conn,
    )

    nlp = pd.read_sql_query(
        "SELECT * FROM post_nlp",
        conn,
    )

    accounts = pd.read_sql_query(
        "SELECT * FROM accounts",
        conn,
    )

    comments = pd.read_sql_query(
        "SELECT * FROM comments",
        conn,
    )

    entities = pd.read_sql_query(
        "SELECT * FROM entities",
        conn,
    )

    hashtags = pd.read_sql_query(
        "SELECT * FROM hashtags",
        conn,
    )

    keywords = pd.read_sql_query(
        "SELECT * FROM keywords",
        conn,
    )

    events = pd.read_sql_query(
        "SELECT * FROM events",
        conn,
    )

    fetch_runs = pd.read_sql_query(
        "SELECT * FROM fetch_runs",
        conn,
    )

    topics = pd.read_sql_query(
        "SELECT * FROM topics",
        conn,
    )

    conn.close()

    return {
        "posts": posts,
        "nlp": nlp,
        "accounts": accounts,
        "comments": comments,
        "entities": entities,
        "hashtags": hashtags,
        "keywords": keywords,
        "events": events,
        "fetch_runs": fetch_runs,
        "topics": topics,
    }


# ============================================================
# DATABASE STATUS
# ============================================================

if not DB_PATH.exists():
    st.error(
        f"Database not found:\n\n`{DB_PATH}`"
    )
    st.stop()

try:
    data = load_database()
except Exception as e:
    st.error("Unable to load the SQLite database.")
    st.exception(e)
    st.stop()


posts = data["posts"]
nlp = data["nlp"]
accounts = data["accounts"]
comments = data["comments"]
entities = data["entities"]
hashtags = data["hashtags"]
keywords = data["keywords"]
events = data["events"]
fetch_runs = data["fetch_runs"]
topics = data["topics"]


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("### INSTAGRAM / RESEARCH")

    st.caption("DATA ACQUISITION • NLP • ANALYTICS")

    st.divider()

    st.markdown("**PROJECT MAP**")

    sections = [
        "01 / INTRO",
        "02 / RESEARCH CONTEXT",
        "03 / PLATFORM CONSTRAINTS",
        "04 / SYSTEM ARCHITECTURE",
        "05 / ACQUISITION PATHS",
        "06 / DATA ENGINEERING",
        "07 / NLP PIPELINE",
        "08 / MATHEMATICAL FOUNDATIONS",
        "09 / DATABASE",
        "10 / ENGINEERING JOURNEY",
        "11 / MULTI-DAY VALIDATION",
        "12 / RESULTS",
        "13 / DATABASE EXPLORER",
        "14 / LIMITATIONS",
        "15 / REPRODUCIBILITY",
        "16 / REPOSITORY",
    ]

    for item in sections:
        st.markdown(f"`{item}`")

    st.divider()

    st.caption(
        "END-TO-END DATA ACQUISITION\n\n"
        "NLP + ANALYTICS"
    )

    st.divider()

    st.caption(
        f"DATABASE\n"
        f"{len(posts):,} posts • "
        f"{len(nlp):,} NLP records"
    )


# ============================================================
# PRESENTER & RESEARCH CONTEXT
# ============================================================

st.divider()

st.markdown("`00 / PRESENTER & RESEARCH CONTEXT`")

st.html("""
<style>
.presenter-section-title {
    font-size: clamp(28px, 3vw, 40px);
    font-weight: 750;
    letter-spacing: -0.035em;
    margin: 4px 0 28px 0;
    color: #edf2ee;
}

.presenter-grid {
    display: grid;
    grid-template-columns: minmax(280px, 0.78fr) minmax(420px, 1.35fr);
    gap: 28px;
    align-items: stretch;
    margin: 0 0 10px 0;
}

.presenter-profile {
    background: linear-gradient(145deg, #0b1534 0%, #080f28 100%);
    border: 1px solid rgba(92, 255, 157, 0.04);
    border-radius: 28px;
    padding: 28px 30px;
    min-height: 380px;
    box-sizing: border-box;
}

.presenter-name {
    color: #edf2ee;
    font-size: 18px;
    font-weight: 750;
    letter-spacing: -0.015em;
    margin-bottom: 14px;
}

.presenter-body {
    color: #b9c3d1;
    font-size: 14px;
    line-height: 1.65;
}

.presenter-rule {
    height: 1px;
    background: rgba(255,255,255,.30);
    margin: 22px 0;
}

.presenter-label {
    color: #edf2ee;
    font-size: 15px;
    font-weight: 750;
    margin-bottom: 10px;
}

.supervision-title {
    color: #edf2ee;
    font-size: 16px;
    font-weight: 750;
    margin: 10px 0 14px 0;
}

.supervision-card {
    position: relative;
    overflow: hidden;
    background: rgba(8, 8, 35, .72);
    border: 1px solid rgba(0, 229, 255, .88);
    border-left: 6px solid #00e5ff;
    border-radius: 16px;
    padding: 16px 20px;
    margin-bottom: 14px;
    box-sizing: border-box;
    transition: transform .18s ease, border-color .18s ease, background .18s ease;
}

.supervision-card:hover {
    transform: translateY(-2px);
    background: rgba(12, 15, 48, .88);
    border-color: #5cff9d;
}

.supervision-role {
    color: #dce1ed;
    font-size: 15px;
    font-weight: 750;
    margin-bottom: 12px;
}

.supervision-person {
    color: #edf2ee;
    font-size: 14px;
    font-weight: 750;
}

.supervision-affiliation {
    color: #b9c3d1;
    font-size: 14px;
}

.context-note {
    display: flex;
    align-items: flex-start;
    gap: 13px;
    margin-top: 16px;
    padding: 18px 20px;
    border-radius: 18px;
    background: linear-gradient(135deg, #008b63, #007a58);
    color: #f2fffa;
    font-size: 14px;
    line-height: 1.65;
    box-sizing: border-box;
}

.context-note-icon {
    flex: 0 0 12px;
    width: 12px;
    height: 12px;
    margin-top: 5px;
    border: 2px solid #9effd0;
    border-radius: 3px;
    box-sizing: border-box;
}

.presenter-figure {
    margin-top: 12px;
    color: #8f9a91;
    font-family: "JetBrains Mono", monospace;
    font-size: 10px;
    letter-spacing: .08em;
    text-transform: uppercase;
}

@media (max-width: 850px) {
    .presenter-grid {
        grid-template-columns: 1fr;
        gap: 18px;
    }

    .presenter-profile {
        min-height: auto;
    }
}
</style>

<div class="presenter-section-title">Presenter &amp; Research Context</div>

<div class="presenter-grid">
    <div class="presenter-profile">
        <div class="presenter-name">Anubhav Kumar</div>
        <div class="presenter-body">
            B.Tech, Electronics &amp; Communication Engineering<br>
            BIT Mesra
        </div>

        <div class="presenter-rule"></div>

        <div class="presenter-label">Role</div>
        <div class="presenter-body">
            Research Intern<br>
            Multimedia Analytics Group<br>
            IIT Guwahati
        </div>

        <div class="presenter-rule"></div>

        <div class="presenter-label">Duration</div>
        <div class="presenter-body">June – August 2026</div>
    </div>

    <div>
        <div class="supervision-title">Research Supervision</div>

        <div class="supervision-card">
            <div class="supervision-role">Faculty Advisor</div>
            <span class="supervision-person">Prof. Prithwijit Guha</span>
            <span class="supervision-affiliation"> — IIT Guwahati</span>
        </div>

        <div class="supervision-card">
            <div class="supervision-role">Mentor</div>
            <span class="supervision-person">Shlok Verma</span>
            <span class="supervision-affiliation"> — M.Tech Scholar, IIT Guwahati</span>
        </div>

        <div class="supervision-card">
            <div class="supervision-role">Mentor</div>
            <span class="supervision-person">Mohd. Amaan</span>
            <span class="supervision-affiliation"> — IIT Guwahati</span>
        </div>

        <div class="context-note">
            <span class="context-note-icon"></span>
            <span>
                This work was conducted under the Multimedia Analytics Group
                and directed toward social-media content research including
                memes, reels, and social-issue content.
            </span>
        </div>
    </div>
</div>

<div class="presenter-figure">FIG. 00 — PRESENTER &amp; RESEARCH CONTEXT</div>
""")


# ============================================================
# HERO
# ============================================================

st.markdown(
    '<div class="hero-eyebrow">DATA ACQUISITION / NLP / ANALYTICS</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero-title">Instagram Data<br>'
    '<span class="hero-accent">Acquisition</span> & Analysis</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero-description">'
    'A research-oriented end-to-end pipeline for acquiring Instagram '
    'post data, processing textual content, applying NLP models, '
    'storing structured results, and generating analytical insights '
    'under real platform constraints.'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# HERO METRICS
# ============================================================

st.markdown("")

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown("### 6.7 d")
    st.caption("GRAPH API VALIDATION")

with m2:
    st.markdown("### 3.5 d")
    st.caption("INSTALOADER VALIDATION")

with m3:
    st.markdown("### 40")
    st.caption("CURRENT POSTS")

with m4:
    st.markdown("### 10")
    st.caption("SQLITE TABLES")


# ============================================================
# 01 INTRO
# ============================================================

st.divider()

st.markdown("`01 / INTRO`")

st.title("What is this project?")

st.write(
    """
    This project implements an end-to-end Instagram data acquisition
    and analysis pipeline. It combines acquisition, persistence,
    preprocessing, NLP, sentiment analysis, entity extraction,
    keyword analysis, and visualization into a unified workflow.
    """
)

st.info(
    """
    **RESEARCH QUESTION**

    How can Instagram content be acquired and transformed into
    structured, queryable, and analyzable data while operating
    within real API, authentication, and platform constraints?
    """
)


# ============================================================
# 02 RESEARCH CONTEXT
# ============================================================

st.divider()

st.markdown("`02 / RESEARCH CONTEXT`")

st.title("Why Instagram?")

st.write(
    """
    The project is purpose-built for Instagram rather than being
    a generic social-media acquisition system. The research context
    includes memes, reels, general content, and social issues while
    dealing with real platform restrictions.
    """
)

st.markdown(
    """
    The central engineering challenge is not simply collecting data.
    It is designing a pipeline that remains useful when acquisition
    permissions, authentication, pagination, and platform behaviour
    impose constraints.
    """
)


# ============================================================
# 03 PLATFORM CONSTRAINTS
# ============================================================

st.divider()

st.markdown("`03 / PLATFORM CONSTRAINTS`")

st.title("Acquisition is not unrestricted")

st.write(
    """
    Instagram introduces important restrictions around search,
    permissions, authentication, comments, and unofficial
    acquisition mechanisms. These constraints directly shaped
    the architecture of the project.
    """
)

c1, c2 = st.columns(2)

with c1:
    st.warning(
        """
        **OFFICIAL GRAPH API**

        Authorized access, permission requirements,
        development-mode restrictions, pagination behaviour,
        and limited discovery capabilities.
        """
    )

with c2:
    st.error(
        """
        **UNOFFICIAL ACCESS**

        Instaloader can provide public-account acquisition
        without the official API flow, but introduces
        reliability and platform-risk considerations.
        """
    )


# ============================================================
# 04 ARCHITECTURE
# ============================================================

st.divider()


# ============================================================
# 03A / ACQUISITION FLOW
# ============================================================

st.divider()

st.markdown("`03A / ACQUISITION FLOW`")

st.title("Two acquisition paths, different operating constraints")

st.write(
    """
    The pipeline deliberately separates official Graph API acquisition from
    Instaloader-based acquisition. The two paths differ in authorization,
    available fields, reliability characteristics, and platform constraints,
    but converge into the same persistence and downstream analysis layers.
    """
)

acq_left, acq_right = st.columns(2, gap="medium")

with acq_left:
    with st.container(border=True):
        st.caption("PATH A / OFFICIAL")
        st.markdown("### Graph API")
        st.write(
            "Authorized acquisition for supported Instagram data through the "
            "project's Graph API client and fetch modules."
        )
        st.markdown(
            """
**Modules**

`ig_client.py`  
`fetch_ig.py`

**Characteristics**

- Authorized access
- Permission-dependent
- Structured API responses
- Pagination handling
- Full comment text when required access is available
"""
        )

with acq_right:
    with st.container(border=True):
        st.caption("PATH B / UNOFFICIAL")
        st.markdown("### Instaloader")
        st.write(
            "Public-account acquisition used when the official API does not "
            "provide the required discovery or access pattern."
        )
        st.markdown(
            """
**Modules**

`fetch_instaloader.py`  
`fetch_instaloader_extra.py`  
`fetch_instaloader_url.py`

**Characteristics**

- Public-account acquisition
- No official Graph API authorization flow
- Comment-count oriented collection in this project
- Dependent on undocumented platform behaviour
- Higher breakage / account-risk considerations
"""
        )

st.markdown("#### ACQUISITION BRANCH")

b1, bc, b2 = st.columns([1, 0.25, 1], gap="small")

with b1:
    with st.container(border=True):
        st.caption("02A")
        st.markdown("### Graph API")
        st.write("Official / authorized acquisition path")

with bc:
    st.markdown(
        "<div style='text-align:center;font-size:28px;margin-top:45px;'>↘</div>",
        unsafe_allow_html=True,
    )

with b2:
    with st.container(border=True):
        st.caption("02B")
        st.markdown("### Instaloader")
        st.write("Public / unofficial acquisition path")

st.markdown(
    "<div style='text-align:center;font-size:28px;'>↘ &nbsp;&nbsp; ↙</div>",
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.caption("SHARED DOWNSTREAM LAYER")
    st.markdown("### One persistence and analysis pipeline")
    st.write(
        "`save_raw.py` → `save_processed_ig.py` → `preprocess_ig.py` "
        "→ SQLite → analysis → visualization / report"
    )

st.markdown("#### PIPELINE STAGES")

stages = [
    ("01", "TARGET SELECTION", "`accounts.txt` / CLI",
     "Target accounts and acquisition inputs."),
    ("03", "RAW STORAGE", "`save_raw.py`",
     "Preserve acquired records before transformation."),
    ("04", "PROCESSED STORAGE", "`save_processed_ig.py`",
     "Normalize records into the project's structured representation."),
    ("05", "SHARED PIPELINE", "`preprocess_ig.py`",
     "Send both acquisition sources into common downstream processing."),
]

for num, title, module, desc in stages:
    with st.container(border=True):
        st.caption(num)
        st.markdown(f"### {title}")
        st.markdown(module)
        st.write(desc)
    if num != "05":
        st.markdown(
            "<div style='text-align:center;font-size:24px;'>↓</div>",
            unsafe_allow_html=True,
        )

st.markdown("#### LIVE ACQUISITION SNAPSHOT")

a1, a2, a3 = st.columns(3)

# Build acquisition-source counts locally for this section.
# This must be defined before the live snapshot is rendered.
acquisition_source_data = (
    posts["source"]
    .fillna("unknown")
    .astype(str)
    .value_counts()
    .rename_axis("Source")
    .reset_index(name="Posts")
)

source_lower = acquisition_source_data["Source"].astype(str).str.lower()

with a1:
    st.metric("TOTAL POSTS", f"{len(posts):,}")

with a2:
    graph_count = int(
        acquisition_source_data.loc[
            source_lower == "graph_api", "Posts"
        ].sum()
    )
    st.metric("GRAPH API", f"{graph_count:,}")

with a3:
    insta_count = int(
        acquisition_source_data.loc[
            source_lower == "instaloader", "Posts"
        ].sum()
    )
    st.metric("INSTALOADER", f"{insta_count:,}")

st.caption(
    "FIG. 02 — INSTAGRAM ACQUISITION FLOW: OFFICIAL GRAPH API AND "
    "INSTALOADER CONVERGE INTO A SHARED DOWNSTREAM PIPELINE"
)

st.markdown("`04 / SYSTEM ARCHITECTURE`")

st.title("Two acquisition paths. One analytical pipeline.")

st.write(
    """
    The acquisition layer separates official Graph API collection
    from Instaloader-based collection. Both paths converge into
    the same storage, preprocessing, analysis, and reporting workflow.
    """
)

render_architecture()

st.caption(
    "FIG. 01 — END-TO-END INSTAGRAM ACQUISITION AND ANALYSIS PIPELINE"
)


# ============================================================
# 05 ACQUISITION
# ============================================================

st.divider()

st.markdown("`05 / ACQUISITION PATHS`")

st.title("Official vs. unofficial acquisition")

st.write(
    """
    The project intentionally maintains two acquisition strategies.
    They are not treated as equivalent: each has different
    capabilities, restrictions, and reliability characteristics.
    """
)

a1, a2 = st.columns(2)

with a1:
    st.success(
        """
        ### PATH A — Official Graph API

        Designed around authorized Instagram API access.

        Where permissions allow, it provides structured post
        information and comment text.

        **Source:** `graph_api`
        """
    )

with a2:
    st.info(
        """
        ### PATH B — Instaloader

        Used for public-account acquisition without relying
        on the official API permission flow.

        **Source:** `instaloader`
        """
    )


# ============================================================
# 06 DATA ENGINEERING
# ============================================================

st.divider()

st.markdown("`06 / DATA ENGINEERING`")

st.title("Raw → processed → analytical")

st.write(
    """
    Raw acquisition is separated from preprocessing and analysis.
    This makes it possible to preserve source information while
    generating derived NLP and analytical outputs independently.
    """
)

st.code(
    """
Raw Instagram Records
        │
        ▼
   save_raw.py
        │
        ▼
save_processed_ig.py
        │
        ▼
 preprocess_ig.py
        │
        ├───────────────┐
        │               │
        ▼               ▼
   NLP Models       Metadata
        │               │
        └───────┬───────┘
                ▼
          pipeline_ig.db
                │
                ▼
           analysis_ig.py
                │
                ▼
       JSON + Markdown + Charts
    """,
    language="text",
)

st.caption(
    "FIG. 02 — DATA TRANSFORMATION LIFECYCLE"
)


# ============================================================
# 07 NLP PIPELINE
# ============================================================

st.divider()

st.markdown("`07 / NLP PIPELINE`")

st.title("Sentiment, entities, keywords")

st.write(
    """
    The NLP layer combines lexicon-based sentiment analysis
    with transformer-based classification. It also extracts
    named entities and important terms from acquired captions.
    """
)

# ------------------------------------------------------------
# NLP PIPELINE VISUALIZATION
# ------------------------------------------------------------

st.markdown("#### PIPELINE STAGES")

# Stage 01 — Input
with st.container(border=True):
    st.caption("01 / INPUT")
    st.markdown("### Caption & Post Text")
    st.write(
        "Acquired captions enter the NLP layer. Missing or very short "
        "captions are retained in the dataset, while caption-dependent "
        "NLP is skipped or assigned its project-defined defaults."
    )

st.markdown(
    "<div style='text-align:center;font-size:26px;'>↓</div>",
    unsafe_allow_html=True,
)

# Stage 02 — Filtering
with st.container(border=True):
    st.caption("02 / PREPROCESSING")
    st.markdown("### Language & Text Filtering")
    st.write(
        "Available caption text is normalized and passed through the "
        "project's language and preprocessing checks before model inference."
    )

st.markdown(
    "<div style='text-align:center;font-size:26px;'>↓</div>",
    unsafe_allow_html=True,
)

# Stage 03 — Parallel sentiment models
st.markdown("#### 03 / PARALLEL SENTIMENT MODELS")

nlp_a, nlp_b = st.columns(2, gap="medium")

with nlp_a:
    with st.container(border=True):
        st.caption("LEXICON MODEL")
        st.markdown("### VADER")
        st.write(
            "Lexicon-based sentiment scoring produces a label and "
            "confidence-oriented compound score."
        )
        st.markdown("`vader_label`  ·  `vader_confidence`")

with nlp_b:
    with st.container(border=True):
        st.caption("TRANSFORMER MODEL")
        st.markdown("### RoBERTa")
        st.write(
            "The project uses `cardiffnlp/twitter-roberta-base-sentiment` "
            "to classify text as negative, neutral, or positive."
        )
        st.markdown("`roberta_label`  ·  `roberta_confidence`")

st.markdown(
    "<div style='text-align:center;font-size:26px;'>↘ &nbsp;&nbsp; ↙</div>",
    unsafe_allow_html=True,
)

# Stage 04 — Fusion
with st.container(border=True):
    st.caption("04 / CONFIDENCE FUSION")
    st.markdown("### Final Sentiment Selection")
    st.write(
        "The two model outputs are compared post-hoc. The project selects "
        "the model with the higher confidence, with RoBERTa selected when "
        "the confidence values are equal."
    )
    st.markdown(
        "`final_label`  ·  `final_confidence`  ·  `final_source`"
    )

st.markdown(
    "<div style='text-align:center;font-size:26px;'>↓</div>",
    unsafe_allow_html=True,
)

# Stage 05 — Feature extraction
st.markdown("#### 05 / FEATURE EXTRACTION")

nlp_c, nlp_d = st.columns(2, gap="medium")

with nlp_c:
    with st.container(border=True):
        st.caption("ENTITY EXTRACTION")
        st.markdown("### Named Entity Recognition")
        st.write(
            "spaCy-based NER extracts named entities from eligible text "
            "for downstream analytical summaries."
        )

with nlp_d:
    with st.container(border=True):
        st.caption("TERM WEIGHTING")
        st.markdown("### TF-IDF")
        st.write(
            "TF-IDF identifies terms that are informative within the "
            "observed corpus and feeds keyword-level analysis."
        )

st.markdown(
    "<div style='text-align:center;font-size:26px;'>↘ &nbsp;&nbsp; ↓ &nbsp;&nbsp; ↙</div>",
    unsafe_allow_html=True,
)

# Stage 06 — Output
with st.container(border=True):
    st.caption("06 / ANALYTICAL OUTPUT")
    st.markdown("### SQLite → Analysis → Visualization")
    st.write(
        "Derived NLP features are persisted alongside post-level records "
        "and consumed by the analysis and reporting layers."
    )

# Live NLP snapshot
st.markdown("#### LIVE NLP SNAPSHOT")

n1, n2, n3, n4 = st.columns(4)

with n1:
    st.metric("NLP RECORDS", f"{len(nlp):,}")

with n2:
    if "vader_label" in nlp.columns:
        st.metric(
            "VADER LABELS",
            f"{nlp['vader_label'].notna().sum():,}",
        )
    else:
        st.metric("VADER LABELS", "—")

with n3:
    if "roberta_label" in nlp.columns:
        st.metric(
            "ROBERTA LABELS",
            f"{nlp['roberta_label'].notna().sum():,}",
        )
    else:
        st.metric("ROBERTA LABELS", "—")

with n4:
    if "final_label" in nlp.columns:
        st.metric(
            "FINAL LABELS",
            f"{nlp['final_label'].notna().sum():,}",
        )
    else:
        st.metric("FINAL LABELS", "—")

st.caption(
    "FIG. 03 — NLP PROCESSING FLOW: INPUT → FILTERING → DUAL SENTIMENT "
    "MODELS → CONFIDENCE FUSION → NER / TF-IDF → ANALYTICAL OUTPUT"
)


# ============================================================
# 08 MATHEMATICS
# ============================================================

st.divider()

st.markdown("`08 / MATHEMATICAL FOUNDATIONS`")

st.title("Theory behind the pipeline")

st.write(
    """
    The analytical system is grounded in mathematical formulations
    for sentiment normalization, transformer classification,
    and term weighting.
    """
)

st.markdown("#### EQ. 01 — VADER NORMALIZATION")

st.latex(
    r"""
    x_{\mathrm{norm}}
    =
    \frac{x}{\sqrt{x^2+\alpha}},
    \qquad
    \alpha = 15
    """
)

st.markdown("#### EQ. 02 — ROBERTA SOFTMAX")

st.latex(
    r"""
    P(y_i)
    =
    \frac{e^{z_i}}
    {\sum_{j=1}^{3}e^{z_j}}
    """
)

st.markdown("#### EQ. 03 — TF-IDF")

st.latex(
    r"""
    TFIDF(t,d)
    =
    TF(t,d)
    \times
    \log
    \left(
    \frac{df(t)}{N}
    \right)
    """
)

st.markdown("#### EQ. 04 — PROJECT CONFIDENCE FUSION")

st.latex(
    r"""
    Final(p)
    =
    \begin{cases}
    VADER(p),
    &
    Conf_{VADER}(p)>Conf_{RoBERTa}(p)
    \\[6pt]
    RoBERTa(p),
    &
    \text{otherwise}
    \end{cases}
    """
)


# ============================================================
# 09 DATABASE
# ============================================================

st.divider()

st.markdown("`09 / DATABASE`")

st.title("SQLite as the research store")

st.write(
    """
    The project uses a structured SQLite database to connect
    acquisition metadata, content, NLP results, and analytical
    entities.
    """
)

tables = [
    "accounts",
    "fetch_runs",
    "posts",
    "comments",
    "entities",
    "hashtags",
    "keywords",
    "topics",
    "events",
    "post_nlp",
]

for i, table in enumerate(tables, start=1):
    st.markdown(
        f"**{i:02d}** — `{table}`"
    )



# ============================================================
# 09A DATABASE ARCHITECTURE
# ============================================================

st.divider()

st.markdown("`09A / DATABASE ARCHITECTURE`")

st.title("How the research store is organized")

st.write(
    """
    The SQLite store separates acquisition metadata, post-level content,
    derived NLP features, and analytical entities. The layout below is a
    logical view of the ten tables used by the pipeline.
    """
)

# Acquisition layer
st.markdown("#### ACQUISITION LAYER")

a1, a2 = st.columns(2, gap="medium")

with a1:
    with st.container(border=True):
        st.caption("01")
        st.markdown("### `accounts`")
        st.write("Tracked Instagram account metadata.")

with a2:
    with st.container(border=True):
        st.caption("02")
        st.markdown("### `fetch_runs`")
        st.write("Records acquisition runs, sources, status, and execution metadata.")

st.markdown(
    "<div style='text-align:center;font-size:24px;'>↓</div>",
    unsafe_allow_html=True,
)

# Core content
st.markdown("#### CORE CONTENT")

with st.container(border=True):
    st.caption("03")
    st.markdown("### `posts`")
    st.write(
        "Central post-level store containing acquired Instagram content and "
        "engagement metadata."
    )

# Derived content
st.markdown(
    "<div style='text-align:center;font-size:24px;'>↓</div>",
    unsafe_allow_html=True,
)

st.markdown("#### POST-LEVEL DERIVED DATA")

d1, d2, d3 = st.columns(3, gap="medium")

with d1:
    with st.container(border=True):
        st.markdown("### `comments`")
        st.caption("Comment-level acquisition records.")

with d2:
    with st.container(border=True):
        st.markdown("### `post_nlp`")
        st.caption("VADER, RoBERTa, confidence, and final labels.")

with d3:
    with st.container(border=True):
        st.markdown("### `events`")
        st.caption("Structured event records generated by the pipeline.")

# Analytical entities
st.markdown(
    "<div style='text-align:center;font-size:24px;'>↓</div>",
    unsafe_allow_html=True,
)

st.markdown("#### ANALYTICAL ENTITIES")

e1, e2, e3, e4 = st.columns(4, gap="small")

with e1:
    with st.container(border=True):
        st.markdown("### `entities`")
        st.caption("Named entities extracted from content.")

with e2:
    with st.container(border=True):
        st.markdown("### `hashtags`")
        st.caption("Hashtag-level analytical records.")

with e3:
    with st.container(border=True):
        st.markdown("### `keywords`")
        st.caption("Keyword and term-frequency records.")

with e4:
    with st.container(border=True):
        st.markdown("### `topics`")
        st.caption("Topic-level analytical records.")

# Live table inventory
st.markdown("#### LIVE TABLE INVENTORY")

table_inventory = []

for table_name in tables:
    try:
        count_df = query_db(
            f"SELECT COUNT(*) AS count FROM `{table_name}`"
        )
        count = int(count_df.iloc[0]["count"]) if not count_df.empty else 0
    except Exception:
        count = 0

    table_inventory.append(
        {
            "Table": table_name,
            "Rows": count,
        }
    )

inventory_df = pd.DataFrame(table_inventory)

st.dataframe(
    inventory_df,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "FIG. 02 — LOGICAL DATABASE ARCHITECTURE AND CURRENT TABLE INVENTORY"
)


# ============================================================
# 10 ENGINEERING JOURNEY
# ============================================================

st.divider()

st.markdown("`10 / ENGINEERING JOURNEY`")

st.title("What broke — and what was learned")

st.write(
    """
    The system was developed under real-world failure conditions.
    Authentication behaviour, API restrictions, pagination,
    unofficial endpoint changes, and NLP edge cases all influenced
    the final implementation.
    """
)

engineering = {
    "01 — Authentication":
        "Misleading login and token/session failures required additional validation.",

    "02 — Pagination":
        "API pagination behaviour had to be handled carefully to avoid truncated acquisition.",

    "03 — Development mode":
        "Comment access differed depending on application mode and permissions.",

    "04 — Instaloader":
        "Unofficial acquisition could break when Instagram changed undocumented behaviour.",

    "05 — Sentiment ties":
        "The sentiment selection logic required explicit tie handling.",

    "06 — Account identity":
        "Safeguards were needed to avoid unintentionally collecting from the wrong account.",
}

for title, description in engineering.items():

    st.markdown(f"### {title}")
    st.write(description)



# ============================================================
# 03C RESEARCH METHODOLOGY
# ============================================================

st.divider()

st.markdown("`03C / RESEARCH METHODOLOGY`")

st.title("From acquisition to measurable analysis")

st.write(
    """
    The methodology follows a reproducible pipeline: acquire Instagram
    records through the available source path, preserve raw data, clean
    and normalize fields, apply NLP models, persist structured outputs,
    and derive analytical summaries and visualizations.
    """
)

st.markdown("### 01 — Research objective")

st.write(
    """
    The objective is to transform Instagram posts, reels, and engagement
    metadata into structured, queryable data and then analyse textual
    content using sentiment, entity, topic, and keyword techniques while
    documenting the platform constraints encountered during acquisition.
    """
)

st.markdown("### 02 — Dual-path acquisition")

m1, m2 = st.columns(2)

with m1:
    st.markdown("**OFFICIAL GRAPH API**")
    st.write(
        """
        Used for authorized accounts. The project records structured post
        information and, where the available permissions allow it, full
        comment text and metadata.
        """
    )
    st.caption("Modules: `ig_client.py` · `fetch_ig.py`")

with m2:
    st.markdown("**INSTALOADER**")
    st.write(
        """
        Used for public-account, hashtag, and location acquisition where
        the official API does not provide the required discovery path.
        The project records posts and engagement data; comment text is
        not available through this path.
        """
    )
    st.caption("Modules: `fetch_instaloader*.py`")

st.markdown("### 03 — Data transformation")

st.code(
    """
Raw Instagram records
        ↓
save_raw.py
        ↓
save_processed_ig.py
        ↓
preprocess_ig.py
        ↓
NLP + structured database
        ↓
analysis_ig.py
        ↓
JSON + charts + Markdown report
    """,
    language="text",
)

st.markdown("### 04 — NLP methodology")

n1, n2, n3 = st.columns(3)

with n1:
    st.markdown("**SENTIMENT**")
    st.write("VADER + RoBERTa")
    st.caption("Confidence-based final-label selection")

with n2:
    st.markdown("**ENTITIES**")
    st.write("spaCy NER")
    st.caption("Named entities extracted from captions")

with n3:
    st.markdown("**KEYWORDS**")
    st.write("TF-IDF")
    st.caption("Term importance across post captions")

st.markdown("### 05 — Confidence fusion")

st.latex(
    r"""
    Final(p)=
    \begin{cases}
    VADER(p), & Conf_{VADER}(p)>Conf_{RoBERTa}(p)\\
    RoBERTa(p), & \text{otherwise}
    \end{cases}
    """
)

st.write(
    """
    The final sentiment label is selected at inference time from the
    higher-confidence VADER or RoBERTa output. The database retains both
    model outputs, their confidence values, the final result, and the
    model selected as `final_source`.
    """
)

st.markdown("### 06 — Structured persistence and analysis")

st.write(
    """
    The processed records are persisted in a 10-table SQLite database.
    The analysis stage reads the structured data to calculate sentiment,
    engagement, hashtags, keywords, agreement between models, source
    distribution, and post-volume summaries. These outputs feed the
    interactive visualizations and the generated Markdown report.
    """
)

st.markdown("### 07 — Validation methodology")

st.write(
    """
    Reliability was evaluated through multi-day unattended execution.
    Every acquisition attempt was logged with its path and outcome,
    allowing successful runs and observed failures to be inspected
    separately rather than validating the pipeline from a single run.
    """
)

st.markdown("### 08 — Scope and limitations")

limitations = [
    ("API permissions", "Official API capabilities depend on the permissions and application mode available to the project."),
    ("Discovery", "The official API does not provide unrestricted third-party keyword/topic discovery for this workflow."),
    ("Comment availability", "Full comment text is associated with the Graph API path; Instaloader records comment counts rather than comment text."),
    ("Unofficial acquisition", "Instaloader depends on undocumented platform behaviour and can experience breakage or account-risk considerations."),
    ("NLP scope", "Caption-dependent NLP can be skipped or defaulted when captions are missing or unsuitable for processing."),
    ("Dataset scope", "The observed database snapshot represents the acquired sample and should not be interpreted as a complete representation of Instagram."),
]

for title, description in limitations:
    st.markdown(f"**{title}**")
    st.write(description)

st.caption(
    "FIG. 06 — RESEARCH METHODOLOGY: ACQUISITION → PROCESSING → NLP → STORAGE → ANALYSIS → VALIDATION"
)


# ============================================================
# 11 VALIDATION
# ============================================================

st.divider()

st.markdown("`11 / MULTI-DAY VALIDATION`")

st.title("Reliability beyond a single run")

st.write(
    """
    The acquisition system was evaluated across multiple days rather than
    being validated only through one successful execution. The validation
    report records the duration, scheduler attempts, successful runs,
    failures, and recovery behaviour of both acquisition paths.
    """
)

# ------------------------------------------------------------
# VALIDATION SUMMARY
# ------------------------------------------------------------

v1, v2, v3, v4 = st.columns(4)

with v1:
    st.metric("GRAPH API", "6.7 days", "45+ attempts")

with v2:
    st.metric("GRAPH API SUCCESS", "41+", "confirmed successful runs")

with v3:
    st.metric("INSTALOADER", "3.5 days", "12+ attempts")

with v4:
    st.metric("INSTALOADER SUCCESS", "11+", "confirmed successful runs")


# ------------------------------------------------------------
# VALIDATION WINDOWS
# ------------------------------------------------------------

st.markdown("#### VALIDATION WINDOWS")

window_left, window_right = st.columns(2, gap="medium")

with window_left:
    with st.container(border=True):
        st.caption("GRAPH API / `main_ig.py`")
        st.markdown("### 23 Aug → 30 Aug 2026")
        st.write("~12:34 IST → ~05:32 IST")
        st.markdown("**Duration:** `6.7 days`")
        st.write(
            """The unattended Graph API validation window ran beyond the
            requested 3–4 day minimum. The scheduler continued past the
            last confirmed check."""
        )

with window_right:
    with st.container(border=True):
        st.caption("INSTALOADER / `main_instaloader.py`")
        st.markdown("### 26 Aug → 30 Aug 2026")
        st.write("~16:29 IST → ~06:17 IST")
        st.markdown("**Duration:** `3.5 days`")
        st.write(
            """The unattended Instaloader validation window covered the
            requested minimum duration, with scheduled acquisition
            attempts recorded in the shared run log."""
        )


# ------------------------------------------------------------
# VISUAL TIMELINE
# ------------------------------------------------------------

st.markdown("#### EXPERIMENT TIMELINE")

validation_timeline = pd.DataFrame({
    "Path": ["Graph API", "Instaloader"],
    "Start": pd.to_datetime(["2026-08-23", "2026-08-26"]),
    "End": pd.to_datetime(["2026-08-30", "2026-08-30"]),
})

fig = px.timeline(
    validation_timeline,
    x_start="Start",
    x_end="End",
    y="Path",
    text="Path",
)

fig.update_yaxes(autorange="reversed", title=None)
fig.update_xaxes(title="August 2026", dtick="D1", tickformat="%d %b")
fig.update_traces(textposition="inside")
fig.update_layout(
    template="plotly_dark",
    height=260,
    margin=dict(l=20, r=20, t=20, b=20),
    showlegend=False,
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "FIG. 04 — MULTI-DAY VALIDATION TIMELINE: UNATTENDED GRAPH API "
    "AND INSTALOADER TEST WINDOWS"
)


# ------------------------------------------------------------
# FAILURE / RECOVERY EVENTS
# ------------------------------------------------------------

st.markdown("#### OBSERVED RELIABILITY EVENTS")

# Graph API failure window
with st.container(border=True):
    st.caption("EVENT 01 / GRAPH API / 24 AUG 2026")
    st.markdown("### Four consecutive connection-related failures")
    st.write(
        """Four `token_or_session_invalid` entries were recorded within a
        single approximately 12-hour window. Each attempt first went
        through three automatic connection-error retries before the
        failure was logged."""
    )
    st.markdown(
        "**Recovery:** next successful run confirmed at "
        "`2026-08-24 21:34:08 UTC`; the report states the path then ran "
        "cleanly."
    )
    st.info(
        """The validation report attributes these events to connection-level
        failures rather than an actually expired token."""
    )

# Instaloader SSL event
with st.container(border=True):
    st.caption("EVENT 02 / INSTALOADER / 29 AUG 2026")
    st.markdown("### SSL certificate verification failure")
    st.write(
        """One confirmed Instaloader failure was logged as an SSL certificate
        verification error. The scheduler recorded the failure and
        continued to the next scheduled slot without crashing."""
    )
    st.markdown(
        "**Recorded time:** `2026-08-29 21:08 IST`"
    )


# ------------------------------------------------------------
# TOKEN REFRESH VERIFICATION
# ------------------------------------------------------------

st.markdown("#### TOKEN-REFRESH VERIFICATION")

refresh_left, refresh_right = st.columns(2, gap="medium")

with refresh_left:
    with st.container(border=True):
        st.caption("MANUAL VERIFICATION / 23 AUG 2026")
        st.markdown("### Refresh path confirmed")
        st.write(
            """The refresh threshold was temporarily raised from 10 to 100
            days to force the refresh path before the unattended window.
            The report records that refresh fired correctly and persisted
            the updated state."""
        )

with refresh_right:
    with st.container(border=True):
        st.caption("UNATTENDED WINDOW")
        st.markdown("### Natural refresh was not triggered")
        st.write(
            """During the 6.7-day unattended Graph API window, the token
            remained at approximately 58–60 days remaining, above the
            configured 10-day threshold. The report therefore records
            no natural refresh during the test."""
        )


# ------------------------------------------------------------
# VALIDATION INTERPRETATION
# ------------------------------------------------------------

st.markdown("#### WHAT THE VALIDATION ESTABLISHED")

validation_points = [
    "Both acquisition paths completed multi-day unattended validation windows.",
    "Both paths recorded successful scheduled executions alongside logged failures.",
    "The Graph API failure cluster recovered without manual intervention.",
    "The Instaloader SSL failure was logged and did not stop the scheduler.",
    "The token-refresh mechanism was manually forced and verified before the unattended run.",
]

for point in validation_points:
    st.markdown(f"→ {point}")


st.caption(
    "FIG. 05 — VALIDATION EVENTS, FAILURE HANDLING, AND TOKEN-REFRESH VERIFICATION"
)


# ============================================================

# 12 RESULTS — LIVE DATABASE
# ============================================================

st.divider()

st.markdown("`12 / RESULTS`")

st.title("Current dataset snapshot")

st.write(
    """
    The following results are calculated directly from the
    project's SQLite database. They update automatically when
    the database changes.
    """
)


# ------------------------------------------------------------
# DATASET METRICS
# ------------------------------------------------------------

total_posts = len(posts)
total_entities = len(entities)
total_hashtags = len(hashtags)
total_keywords = len(keywords)

total_likes = int(
    posts["like_count"].fillna(0).sum()
)

total_comments = int(
    posts["comment_count"].fillna(0).sum()
)

avg_likes = (
    posts["like_count"].fillna(0).mean()
    if len(posts)
    else 0
)

avg_comments = (
    posts["comment_count"].fillna(0).mean()
    if len(posts)
    else 0
)


r1, r2, r3, r4 = st.columns(4)

with r1:
    st.metric(
        "POSTS",
        f"{total_posts:,}",
    )

with r2:
    st.metric(
        "ENTITIES",
        f"{total_entities:,}",
    )

with r3:
    st.metric(
        "HASHTAGS",
        f"{total_hashtags:,}",
    )

with r4:
    st.metric(
        "KEYWORDS",
        f"{total_keywords:,}",
    )


r5, r6, r7, r8 = st.columns(4)

with r5:
    st.metric(
        "TOTAL LIKES",
        f"{total_likes:,}",
    )

with r6:
    st.metric(
        "TOTAL COMMENTS",
        f"{total_comments:,}",
    )

with r7:
    st.metric(
        "AVG. LIKES",
        f"{avg_likes:,.0f}",
    )

with r8:
    st.metric(
        "AVG. COMMENTS",
        f"{avg_comments:,.0f}",
    )


# ============================================================
# SENTIMENT
# ============================================================

st.divider()

st.subheader("Sentiment Distribution")

sentiment = (
    nlp["final_label"]
    .fillna("unknown")
    .value_counts()
    .rename_axis("Sentiment")
    .reset_index(name="Posts")
)

if not sentiment.empty:

    fig = px.bar(
        sentiment,
        x="Sentiment",
        y="Posts",
        text="Posts",
    )

    fig.update_layout(
        template="plotly_dark",
        height=420,
        xaxis_title="Final Sentiment",
        yaxis_title="Number of Posts",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# VADER VS ROBERTA
# ============================================================

st.subheader("VADER vs RoBERTa")

comparison = (
    nlp.groupby(
        ["vader_label", "roberta_label"],
        dropna=False,
    )
    .size()
    .reset_index(name="Posts")
)

comparison["vader_label"] = comparison[
    "vader_label"
].fillna("unknown")

comparison["roberta_label"] = comparison[
    "roberta_label"
].fillna("unknown")

if not comparison.empty:

    fig = px.bar(
        comparison,
        x="vader_label",
        y="Posts",
        color="roberta_label",
        barmode="group",
        labels={
            "vader_label": "VADER",
            "roberta_label": "RoBERTa",
        },
    )

    fig.update_layout(
        template="plotly_dark",
        height=450,
        xaxis_title="VADER Label",
        yaxis_title="Number of Posts",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# ACQUISITION SOURCES
# ============================================================

st.subheader("Acquisition Source")

source_data = (
    posts["source"]
    .fillna("unknown")
    .value_counts()
    .rename_axis("Source")
    .reset_index(name="Posts")
)

if not source_data.empty:

    fig = px.pie(
        source_data,
        names="Source",
        values="Posts",
        hole=0.45,
    )

    fig.update_layout(
        template="plotly_dark",
        height=420,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# MEDIA TYPES
# ============================================================

st.subheader("Media Types")

media = (
    posts["media_type"]
    .fillna("unknown")
    .value_counts()
    .rename_axis("Media Type")
    .reset_index(name="Posts")
)

if not media.empty:

    fig = px.bar(
        media,
        x="Media Type",
        y="Posts",
        text="Posts",
    )

    fig.update_layout(
        template="plotly_dark",
        height=420,
        xaxis_title="Media Type",
        yaxis_title="Posts",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# ENGAGEMENT
# ============================================================

st.subheader("Engagement Analysis")

engagement = posts[
    [
        "id",
        "like_count",
        "comment_count",
        "source",
    ]
].copy()

engagement["like_count"] = (
    engagement["like_count"]
    .fillna(0)
    .clip(lower=0)
)

engagement["comment_count"] = (
    engagement["comment_count"]
    .fillna(0)
    .clip(lower=0)
)

if not engagement.empty:

    fig = px.scatter(
        engagement,
        x="like_count",
        y="comment_count",
        color="source",
        hover_data=["id"],
        log_x=True,
        log_y=True,
    )

    fig.update_layout(
        template="plotly_dark",
        height=520,
        xaxis_title="Likes",
        yaxis_title="Comments",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# FINAL SENTIMENT SOURCE
# ============================================================

st.subheader("Final Sentiment Model Source")

if "final_source" in nlp.columns:

    source_sentiment = (
        nlp["final_source"]
        .fillna("unknown")
        .value_counts()
        .rename_axis("Source")
        .reset_index(name="Posts")
    )

    if not source_sentiment.empty:

        fig = px.bar(
            source_sentiment,
            x="Source",
            y="Posts",
            text="Posts",
        )

        fig.update_layout(
            template="plotly_dark",
            height=420,
            xaxis_title="Selected Model",
            yaxis_title="Posts",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# CONFIDENCE DISTRIBUTION
# ============================================================

st.subheader("Final Sentiment Confidence")

if "final_confidence" in nlp.columns:

    confidence = pd.to_numeric(
        nlp["final_confidence"],
        errors="coerce",
    ).dropna()

    if not confidence.empty:

        fig = px.histogram(
            confidence,
            nbins=15,
        )

        fig.update_layout(
            template="plotly_dark",
            height=420,
            xaxis_title="Confidence",
            yaxis_title="Posts",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )



# ============================================================
# ADDITIONAL RESEARCH ANALYTICS
# ============================================================

st.divider()

st.markdown("`12A / CONTENT & RESEARCH ANALYTICS`")

st.title("Content-level research analysis")

st.write(
    """
    The following analyses are derived directly from the normalized
    Instagram research database. They extend the dataset snapshot with
    content frequency, entity extraction, engagement ranking, temporal
    activity, and automatically derived observations.
    """
)


# ------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------

def first_existing_column(df, candidates):
    """Return the first matching column from a list of candidates."""
    for column in candidates:
        if column in df.columns:
            return column
    return None


def frequency_table(df, value_candidates, weight_candidates=None, limit=15):
    """
    Build a frequency table from a normalized database table.

    Supports either:
    1. one row per occurrence, where values are counted, or
    2. a table containing an explicit frequency/count column.
    """
    value_col = first_existing_column(df, value_candidates)

    if value_col is None or df.empty:
        return pd.DataFrame(columns=["Item", "Frequency"])

    temp = df.copy()
    temp[value_col] = temp[value_col].astype(str).str.strip()
    temp = temp[
        (temp[value_col] != "")
        & (temp[value_col].str.lower() != "nan")
        & (temp[value_col].str.lower() != "none")
    ]

    if temp.empty:
        return pd.DataFrame(columns=["Item", "Frequency"])

    weight_col = first_existing_column(
        temp,
        weight_candidates or [
            "frequency",
            "freq",
            "count",
            "occurrences",
            "post_count",
        ],
    )

    if weight_col:
        temp[weight_col] = pd.to_numeric(
            temp[weight_col],
            errors="coerce",
        ).fillna(0)

        result = (
            temp.groupby(value_col, as_index=False)[weight_col]
            .sum()
            .rename(
                columns={
                    value_col: "Item",
                    weight_col: "Frequency",
                }
            )
        )
    else:
        result = (
            temp[value_col]
            .value_counts()
            .rename_axis("Item")
            .reset_index(name="Frequency")
        )

    return result.sort_values(
        "Frequency",
        ascending=False,
    ).head(limit)


def format_large_number(value):
    """Compact formatting for large research metrics."""
    value = float(value)

    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"

    return f"{value:,.0f}"


# ------------------------------------------------------------
# TOP HASHTAGS
# ------------------------------------------------------------

st.subheader("Top Hashtags")

top_hashtags = frequency_table(
    hashtags,
    [
        "hashtag",
        "hashtag_name",
        "name",
        "tag",
        "text",
        "value",
    ],
    [
        "frequency",
        "count",
        "occurrences",
        "post_count",
    ],
    limit=15,
)

if not top_hashtags.empty:
    fig = px.bar(
        top_hashtags.sort_values("Frequency"),
        x="Frequency",
        y="Item",
        orientation="h",
        text="Frequency",
    )

    fig.update_layout(
        template="plotly_dark",
        height=500,
        xaxis_title="Frequency",
        yaxis_title="Hashtag",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )
else:
    st.info("No hashtag frequency data is available.")


# ------------------------------------------------------------
# TOP KEYWORDS
# ------------------------------------------------------------

st.subheader("Top Keywords")

top_keywords = frequency_table(
    keywords,
    [
        "keyword",
        "term",
        "word",
        "name",
        "text",
        "value",
    ],
    [
        "frequency",
        "count",
        "occurrences",
        "post_count",
        "score",
    ],
    limit=15,
)

if not top_keywords.empty:
    fig = px.bar(
        top_keywords.sort_values("Frequency"),
        x="Frequency",
        y="Item",
        orientation="h",
        text="Frequency",
    )

    fig.update_layout(
        template="plotly_dark",
        height=500,
        xaxis_title="Frequency",
        yaxis_title="Keyword",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )
else:
    st.info("No keyword frequency data is available.")


# ------------------------------------------------------------
# NAMED ENTITIES
# ------------------------------------------------------------

st.subheader("Named Entities")

top_entities = frequency_table(
    entities,
    [
        "entity",
        "entity_text",
        "text",
        "name",
        "value",
    ],
    [
        "frequency",
        "count",
        "occurrences",
        "post_count",
    ],
    limit=15,
)

if not top_entities.empty:
    fig = px.bar(
        top_entities.sort_values("Frequency"),
        x="Frequency",
        y="Item",
        orientation="h",
        text="Frequency",
    )

    fig.update_layout(
        template="plotly_dark",
        height=500,
        xaxis_title="Frequency",
        yaxis_title="Entity",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )
else:
    st.info("No named-entity frequency data is available.")


# ------------------------------------------------------------
# MOST ENGAGED POSTS
# ------------------------------------------------------------

st.subheader("Most Engaged Posts")

engaged = posts.copy()

engaged["like_count"] = pd.to_numeric(
    engaged["like_count"],
    errors="coerce",
).fillna(0)

engaged["comment_count"] = pd.to_numeric(
    engaged["comment_count"],
    errors="coerce",
).fillna(0)

engaged["total_engagement"] = (
    engaged["like_count"] + engaged["comment_count"]
)

display_columns = []

id_col = first_existing_column(
    engaged,
    [
        "id",
        "post_id",
        "media_id",
        "instagram_id",
    ],
)

account_col = first_existing_column(
    engaged,
    [
        "username",
        "account",
        "account_name",
        "owner_username",
    ],
)

caption_col = first_existing_column(
    engaged,
    [
        "caption",
        "text",
        "description",
    ],
)

source_col = first_existing_column(
    engaged,
    ["source"],
)

if id_col:
    display_columns.append(id_col)

if account_col:
    display_columns.append(account_col)

if source_col:
    display_columns.append(source_col)

display_columns.extend(
    [
        "like_count",
        "comment_count",
        "total_engagement",
    ]
)

if caption_col:
    display_columns.append(caption_col)

top_posts = engaged.sort_values(
    "total_engagement",
    ascending=False,
).head(10)[display_columns].copy()

if caption_col:
    top_posts[caption_col] = (
        top_posts[caption_col]
        .fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.slice(0, 120)
    )

top_posts = top_posts.rename(
    columns={
        "like_count": "Likes",
        "comment_count": "Comments",
        "total_engagement": "Total Engagement",
    }
)

st.dataframe(
    top_posts,
    use_container_width=True,
    hide_index=True,
)


# ------------------------------------------------------------
# ENGAGEMENT SUMMARY
# ------------------------------------------------------------

st.subheader("Engagement Summary")

e1, e2, e3, e4 = st.columns(4)

median_likes = engaged["like_count"].median()
median_comments = engaged["comment_count"].median()
max_likes = engaged["like_count"].max()
max_comments = engaged["comment_count"].max()

with e1:
    st.metric(
        "MEDIAN LIKES",
        format_large_number(median_likes),
    )

with e2:
    st.metric(
        "MEDIAN COMMENTS",
        format_large_number(median_comments),
    )

with e3:
    st.metric(
        "MAX LIKES",
        format_large_number(max_likes),
    )

with e4:
    st.metric(
        "MAX COMMENTS",
        format_large_number(max_comments),
    )


# ------------------------------------------------------------
# POST VOLUME OVER TIME
# ------------------------------------------------------------

st.subheader("Post Volume Over Time")

date_col = first_existing_column(
    posts,
    [
        "timestamp",
        "created_time",
        "created_at",
        "published_at",
        "taken_at",
        "post_date",
        "date",
        "datetime",
    ],
)

if date_col:
    temporal = posts.copy()

    temporal["parsed_date"] = pd.to_datetime(
        temporal[date_col],
        errors="coerce",
    )

    temporal = temporal.dropna(subset=["parsed_date"])

    if not temporal.empty:
        temporal["Date"] = temporal["parsed_date"].dt.date

        volume = (
            temporal.groupby("Date")
            .size()
            .reset_index(name="Posts")
        )

        fig = px.line(
            volume,
            x="Date",
            y="Posts",
            markers=True,
        )

        fig.update_layout(
            template="plotly_dark",
            height=420,
            xaxis_title="Date",
            yaxis_title="Posts",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )
    else:
        st.info(
            f"The `{date_col}` column exists, but no valid dates "
            "could be parsed."
        )
else:
    st.info(
        "No recognized post-date column is available for temporal analysis."
    )


# ------------------------------------------------------------
# RESEARCH FINDINGS
# ------------------------------------------------------------

st.subheader("Automatically Derived Research Findings")

findings = []

# Media finding
if not media.empty:
    dominant_media = media.iloc[0]["Media Type"]
    dominant_media_count = int(media.iloc[0]["Posts"])

    findings.append(
        f"**Media composition:** {dominant_media} is the most frequent "
        f"media type with {dominant_media_count:,} posts."
    )

# Sentiment finding
if not sentiment.empty:
    dominant_sentiment = sentiment.iloc[0]["Sentiment"]
    dominant_sentiment_count = int(sentiment.iloc[0]["Posts"])

    findings.append(
        f"**Sentiment:** {dominant_sentiment} is the most frequent final "
        f"sentiment label with {dominant_sentiment_count:,} posts."
    )

# Source finding
if not source_data.empty:
    dominant_source = source_data.iloc[0]["Source"]
    dominant_source_count = int(source_data.iloc[0]["Posts"])

    findings.append(
        f"**Acquisition:** {dominant_source} contributes the largest "
        f"share of the current dataset ({dominant_source_count:,} posts)."
    )

# Model-source finding
if (
    "final_source" in nlp.columns
    and not source_sentiment.empty
):
    dominant_model = source_sentiment.iloc[0]["Source"]
    dominant_model_count = int(source_sentiment.iloc[0]["Posts"])

    findings.append(
        f"**Sentiment fusion:** {dominant_model} is selected as the final "
        f"sentiment source for {dominant_model_count:,} NLP records."
    )

# Agreement finding
if not comparison.empty:
    agreement_count = int(
        (
            comparison["vader_label"].astype(str).str.lower()
            == comparison["roberta_label"].astype(str).str.lower()
        )
        .mul(comparison["Posts"])
        .sum()
    )

    comparison_total = int(comparison["Posts"].sum())

    if comparison_total:
        agreement_pct = 100 * agreement_count / comparison_total

        findings.append(
            f"**Model agreement:** VADER and RoBERTa produce the same "
            f"label for {agreement_count:,} of {comparison_total:,} "
            f"comparable NLP records ({agreement_pct:.1f}%)."
        )

# Engagement finding
if not engaged.empty:
    top_engagement = engaged["total_engagement"].max()

    findings.append(
        f"**Engagement:** the highest-engagement post has "
        f"{format_large_number(top_engagement)} combined likes and comments."
    )

if findings:
    for finding in findings:
        st.markdown(f"→ {finding}")
else:
    st.info("Not enough data is available to derive research findings.")


# ============================================================
# 13 DATABASE EXPLORER
# ============================================================

st.divider()

st.markdown("`13 / DATABASE EXPLORER`")

st.title("Explore the research database")

st.write(
    """
    Inspect the structured records generated by the acquisition
    and NLP pipeline.
    """
)

available_tables = {
    "Posts": posts,
    "NLP": nlp,
    "Accounts": accounts,
    "Comments": comments,
    "Entities": entities,
    "Hashtags": hashtags,
    "Keywords": keywords,
    "Events": events,
    "Fetch Runs": fetch_runs,
    "Topics": topics,
}

selected_table = st.selectbox(
    "Select a table",
    list(available_tables.keys()),
)

selected_df = available_tables[selected_table]

st.caption(
    f"{len(selected_df):,} rows × "
    f"{len(selected_df.columns):,} columns"
)

st.dataframe(
    selected_df,
    use_container_width=True,
    height=450,
)


# ============================================================
# 14 LIMITATIONS
# ============================================================

st.divider()

st.markdown("`14 / LIMITATIONS`")

st.title("What the system cannot guarantee")

limitations = [
    "Official API access is permission-dependent.",
    "Third-party keyword/topic discovery is restricted.",
    "Unofficial acquisition can break when platform behaviour changes.",
    "Comment availability differs between acquisition paths.",
    "NLP quality depends on caption availability and language.",
]

for item in limitations:
    st.markdown(f"→ {item}")


# ============================================================
# 15 REPRODUCIBILITY
# ============================================================

st.divider()

st.markdown("`15 / REPRODUCIBILITY`")

st.title("From research question to executable pipeline")

st.write(
    """
    The final documentation connects the research narrative
    directly to the implementation: acquisition modules,
    preprocessing, database design, NLP models, validation
    experiments, and analytical outputs.
    """
)

st.code(
    """
accounts.txt
     │
     ▼
Acquisition
     │
     ▼
Raw Data
     │
     ▼
Preprocessing
     │
     ▼
SQLite Database
     │
     ▼
NLP + Analysis
     │
     ▼
Reports / Visualizations
    """,
    language="text",
)


# ============================================================
# 16 REPOSITORY
# ============================================================

st.divider()

st.markdown("`16 / REPOSITORY`")

st.title("Research documentation")

st.html("""
<style>
.repo-card {
    margin: 24px 0 22px 0;
    padding: 24px 26px;
    border: 1px solid rgba(92,255,157,.20);
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(16,20,18,.96), rgba(8,15,12,.96));
}
.repo-kicker {
    color: #5cff9d;
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: 9px;
}
.repo-title {
    color: #edf2ee;
    font-size: 22px;
    font-weight: 750;
    margin-bottom: 8px;
}
.repo-copy {
    color: #aeb9b1;
    font-size: 14px;
    line-height: 1.65;
    margin-bottom: 18px;
}
.repo-link {
    display: inline-block;
    padding: 10px 16px;
    border: 1px solid rgba(92,255,157,.55);
    border-radius: 10px;
    color: #5cff9d !important;
    text-decoration: none !important;
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
    transition: all .18s ease;
}
.repo-link:hover {
    background: rgba(92,255,157,.10);
    border-color: #5cff9d;
    transform: translateY(-1px);
}
.repo-url {
    margin-top: 12px;
    color: #738078;
    font-family: "JetBrains Mono", monospace;
    font-size: 10px;
    word-break: break-all;
}
</style>

<div class="repo-card">
    <div class="repo-kicker">SOURCE / GITHUB</div>
    <div class="repo-title">Instagram Acquisition Pipeline</div>
    <div class="repo-copy">
        Source repository containing the acquisition, preprocessing,
        database, NLP, analysis, and pipeline implementation.
    </div>
    <a class="repo-link"
       href="https://github.com/Anu7hav/instagram-acquisition-pipeline.git"
       target="_blank"
       rel="noopener noreferrer">
       VIEW GITHUB REPOSITORY ↗
    </a>
    <div class="repo-url">
        github.com/Anu7hav/instagram-acquisition-pipeline
    </div>
</div>
""")

st.write(
    """
    This website documents the engineering, research methodology,
    mathematical foundations, validation experiments, and analytical
    results of the Instagram acquisition pipeline.
    """
)

st.success(
    """
    **DATABASE CONNECTED**

    The dashboard is now reading directly from
    `data/pipeline_ig.db`.

    Interactive research visualizations are generated
    from the current database contents.
    """
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "INSTAGRAM DATA ACQUISITION & ANALYSIS  •  "
    "RESEARCH / ENGINEERING / NLP"
)