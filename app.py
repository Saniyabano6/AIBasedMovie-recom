import requests
import streamlit as st
import threading
import time

# =============================
# CONFIG
# =============================
API_BASE = "https://aibasedmovie-recom-5.onrender.com"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

st.set_page_config(page_title="CineScope", page_icon="C", layout="wide")

# =============================
# STYLES — Vibrant Gradient + Material Icons (zero emojis)
# =============================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons+Round');

/* ── Variables ── */
:root {
    --c-purple: #c026d3;
    --c-cyan:   #06b6d4;
    --c-amber:  #f59e0b;
    --c-green:  #10b981;
    --c-rose:   #f43f5e;
    --surface:    rgba(255,255,255,0.07);
    --surface-hv: rgba(255,255,255,0.13);
    --border:     rgba(255,255,255,0.16);
    --text:       #ffffff;
    --text-sub:   rgba(255,255,255,0.70);
    --text-muted: rgba(255,255,255,0.40);
}

/* ── Animated mesh gradient background ── */
html, body { margin: 0; padding: 0; }

[data-testid="stApp"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    color: var(--text) !important;
    min-height: 100vh;
    background:
        radial-gradient(ellipse 90% 65% at 0%   5%,  rgba(192,38,211,0.45) 0%, transparent 55%),
        radial-gradient(ellipse 75% 60% at 100% 0%,  rgba(6,182,212,0.40)  0%, transparent 55%),
        radial-gradient(ellipse 80% 65% at 100% 100%,rgba(16,185,129,0.35) 0%, transparent 55%),
        radial-gradient(ellipse 70% 55% at 0%   100%,rgba(245,158,11,0.38) 0%, transparent 50%),
        radial-gradient(ellipse 60% 50% at 50%  50%, rgba(244,63,94,0.22)  0%, transparent 55%),
        linear-gradient(145deg, #08011f 0%, #03082e 50%, #001220 100%) !important;
    animation: meshPulse 22s ease-in-out infinite alternate;
}

@keyframes meshPulse {
    0%   { filter: hue-rotate(0deg)   brightness(1.00) saturate(1.0); }
    40%  { filter: hue-rotate(18deg)  brightness(1.06) saturate(1.1); }
    100% { filter: hue-rotate(-14deg) brightness(0.97) saturate(1.05); }
}

/* Noise grain overlay */
[data-testid="stApp"]::before {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 250 250' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='g'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.78' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23g)' opacity='0.035'/%3E%3C/svg%3E");
    opacity: 0.55;
}

/* ── Layout ── */
.block-container {
    position: relative;
    z-index: 1;
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1440px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: rgba(6, 2, 22, 0.78) !important;
    backdrop-filter: blur(28px) saturate(1.6) !important;
    border-right: 1px solid var(--border) !important;
    position: relative;
    z-index: 2;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* ── Text input ── */
[data-testid="stTextInput"] input {
    background: var(--surface) !important;
    backdrop-filter: blur(14px) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 50px !important;
    color: #fff !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 1rem !important;
    padding: 0.72rem 1.5rem !important;
    transition: all 0.25s ease !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: rgba(192,38,211,0.65) !important;
    box-shadow: 0 0 0 4px rgba(192,38,211,0.14), 0 4px 24px rgba(6,182,212,0.18) !important;
    background: var(--surface-hv) !important;
}
[data-testid="stTextInput"] input::placeholder { color: var(--text-muted) !important; }

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    background: var(--surface) !important;
    backdrop-filter: blur(14px) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 12px !important;
    color: #fff !important;
}

/* ── Buttons ── */
[data-testid="stButton"] button {
    width: 100% !important;
    background: var(--surface) !important;
    backdrop-filter: blur(10px) !important;
    color: #fff !important;
    border: 1px solid var(--border) !important;
    border-radius: 9px !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    padding: 0.42rem 0.9rem !important;
    transition: all 0.22s ease !important;
}
[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, var(--c-purple) 0%, var(--c-cyan) 100%) !important;
    border-color: transparent !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 24px rgba(192,38,211,0.38) !important;
    color: #fff !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1.2rem 0 !important; }

/* ── Material icon utility ── */
.mi {
    font-family: 'Material Icons Round';
    font-style: normal;
    font-size: 1.1rem;
    vertical-align: middle;
    line-height: 1;
    display: inline-block;
}
.mi-sm { font-size: 0.92rem; }
.mi-lg { font-size: 1.5rem; }

/* ── App title ── */
h1 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 900 !important;
    font-size: 3rem !important;
    letter-spacing: -0.01em !important;
    line-height: 1 !important;
    background: linear-gradient(130deg, #fff 0%, #67e8f9 38%, #c026d3 80%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
}
h2, h3 {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    color: #fff !important;
}

/* ── Section label ── */
.section-label {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 1.4rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 9px;
    background: linear-gradient(90deg, var(--c-amber), var(--c-rose));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.section-label .mi {
    -webkit-text-fill-color: var(--c-amber);
    background: none;
    font-size: 1.1rem;
}
.section-label::after {
    content: '';
    flex: 1;
    height: 1.5px;
    background: linear-gradient(to right, rgba(245,158,11,0.4), transparent);
    border-radius: 2px;
}

/* ── Movie card ── */
.movie-card {
    background: var(--surface);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s;
    margin-bottom: 4px;
}
.movie-card:hover {
    transform: translateY(-5px) scale(1.015);
    border-color: rgba(192,38,211,0.45);
    box-shadow:
        0 18px 50px rgba(0,0,0,0.55),
        0 0 0 1px rgba(6,182,212,0.22);
}
.movie-card-body { padding: 10px 11px 12px; }
.movie-card-title {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.81rem;
    font-weight: 600;
    color: #fff;
    line-height: 1.3;
    margin-bottom: 5px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    min-height: 2.15em;
}
.movie-card-meta {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 8px;
}
.movie-card-year {
    font-size: 0.68rem;
    color: var(--text-muted);
    background: rgba(255,255,255,0.08);
    padding: 2px 7px;
    border-radius: 20px;
    font-weight: 500;
}
.movie-card-rating {
    font-size: 0.68rem;
    font-weight: 700;
    background: linear-gradient(90deg, #f59e0b, #ef4444);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: inline-flex;
    align-items: center;
    gap: 2px;
}
.movie-card-rating .mi-sm { -webkit-text-fill-color: #f59e0b; }

/* No-poster placeholder */
.no-poster {
    width: 100%;
    aspect-ratio: 2/3;
    background: linear-gradient(135deg, rgba(192,38,211,0.18) 0%, rgba(6,182,212,0.14) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 14px 14px 0 0;
}
.no-poster .mi { font-size: 2.6rem; color: rgba(255,255,255,0.22); }

/* ── Detail page ── */
.detail-title {
    font-family: 'Syne', sans-serif;
    font-size: 2.4rem;
    font-weight: 900;
    line-height: 1.06;
    margin-bottom: 13px;
    background: linear-gradient(130deg, #fff 0%, #67e8f9 50%, #c026d3 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.detail-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(255,255,255,0.08);
    color: rgba(255,255,255,0.82);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 20px;
    font-size: 0.71rem;
    font-weight: 600;
    padding: 3px 12px;
    margin: 3px 4px 3px 0;
    letter-spacing: 0.04em;
    backdrop-filter: blur(8px);
}
.detail-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    margin: 14px 0 20px;
    font-size: 0.83rem;
    color: var(--text-sub);
}
.detail-meta-row span {
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.detail-meta-row .mi-sm { color: var(--c-cyan); }
.overview-label {
    font-family: 'Syne', sans-serif;
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    background: linear-gradient(90deg, var(--c-amber), var(--c-rose));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.overview-label .mi-sm { -webkit-text-fill-color: var(--c-amber); }
.overview-text {
    font-size: 0.94rem;
    line-height: 1.80;
    color: var(--text-sub);
}

/* ── Sidebar brand ── */
.sidebar-brand {
    font-family: 'Syne', sans-serif;
    font-size: 1.45rem;
    font-weight: 900;
    letter-spacing: 0.03em;
    background: linear-gradient(130deg, #c026d3, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 3px;
}
.sidebar-brand .mi {
    -webkit-text-fill-color: #c026d3;
    font-size: 1.45rem;
}
.feed-label {
    font-family: 'Syne', sans-serif;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 7px;
}

/* ── Muted text ── */
.muted { color: var(--text-muted); font-size: 0.84rem; }

/* ── Alerts ── */
[data-testid="stAlert"] {
    background: rgba(244,63,94,0.12) !important;
    border: 1px solid rgba(244,63,94,0.28) !important;
    border-radius: 10px !important;
    color: #fda4af !important;
    backdrop-filter: blur(10px) !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
</style>
""",
    unsafe_allow_html=True,
)

# =============================
# KEEP-ALIVE (pings backend every 10 min to prevent Render sleep)
# =============================
def keep_alive():
    while True:
        try:
            requests.get(
                f"{API_BASE}/health",
                timeout=10
            )
        except Exception:
            pass
        time.sleep(600)  # every 10 minutes

thread = threading.Thread(target=keep_alive, daemon=True)
thread.start()


# =============================
# STATE + ROUTING
# =============================
if "view" not in st.session_state:
    st.session_state.view = "home"
if "selected_tmdb_id" not in st.session_state:
    st.session_state.selected_tmdb_id = None


try:
    qp_view = st.query_params.get("view")
except AttributeError:
    qp_view = st.experimental_get_query_params().get("view", [None])[0]
qp_id = st.query_params.get("id")
if qp_view in ("home", "details"):
    st.session_state.view = qp_view
if qp_id:
    try:
        st.session_state.selected_tmdb_id = int(qp_id)
        st.session_state.view = "details"
    except Exception:
        pass


def goto_home():
    st.session_state.view = "home"
    st.query_params["view"] = "home"
    if "id" in st.query_params:
        del st.query_params["id"]
    st.rerun()


def goto_details(tmdb_id: int):
    st.session_state.view = "details"
    st.session_state.selected_tmdb_id = int(tmdb_id)
    st.query_params["view"] = "details"
    st.query_params["id"] = str(int(tmdb_id))
    st.rerun()


# =============================
# API HELPERS
# =============================
@st.cache_data(ttl=30)
def api_get_json(path: str, params: dict | None = None):
    """Fetch JSON from backend with simple retry logic."""
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(f"{API_BASE}{path}", params=params, timeout=60)
            if r.status_code >= 400:
                return None, f"HTTP {r.status_code}: {r.text[:300]}"
            return r.json(), None
        except requests.exceptions.Timeout:
            last_err = "Request timed out. The server may be waking up — please try again."
        except Exception as e:
            last_err = f"Request failed: {e}"
        time.sleep(2 ** attempt)  # wait 1s, 2s before retrying
    return None, last_err


def render_movie_card(col, m, key):
    tmdb_id = m.get("tmdb_id")
    title   = m.get("title", "Untitled")
    poster  = m.get("poster_url")
    year    = str(m.get("release_date") or m.get("year") or "")[:4]
    rating  = m.get("vote_average") or m.get("rating") or ""

    with col:
        st.markdown("<div class='movie-card'>", unsafe_allow_html=True)

        if poster:
            st.image(poster, use_column_width=True)
        else:
            st.markdown(
                "<div class='no-poster'><span class='mi'>movie</span></div>",
                unsafe_allow_html=True,
            )

        meta_html = ""
        if year:
            meta_html += f"<span class='movie-card-year'>{year}</span>"
        if rating:
            try:
                meta_html += (
                    f"<span class='movie-card-rating'>"
                    f"<span class='mi mi-sm'>star</span>{float(rating):.1f}"
                    f"</span>"
                )
            except Exception:
                pass

        st.markdown(
            f"""
            <div class='movie-card-body'>
                <div class='movie-card-title'>{title}</div>
                <div class='movie-card-meta'>{meta_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("View", key=key):
            if tmdb_id:
                goto_details(tmdb_id)

        st.markdown("</div>", unsafe_allow_html=True)


def poster_grid(cards, cols=6, key_prefix="grid"):
    if not cards:
        st.info("No movies to show.")
        return
    rows = (len(cards) + cols - 1) // cols
    idx  = 0
    for r in range(rows):
        colset = st.columns(cols, gap="small")
        for c in range(cols):
            if idx >= len(cards):
                break
            m = cards[idx]; idx += 1
            render_movie_card(
                colset[c], m,
                key=f"{key_prefix}_{r}_{c}_{idx}_{m.get('tmdb_id', '')}",
            )


def to_cards_from_tfidf_items(tfidf_items):
    cards = []
    for x in tfidf_items or []:
        tmdb = x.get("tmdb") or {}
        if tmdb.get("tmdb_id"):
            cards.append({
                "tmdb_id":      tmdb["tmdb_id"],
                "title":        tmdb.get("title") or x.get("title") or "Untitled",
                "poster_url":   tmdb.get("poster_url"),
                "release_date": tmdb.get("release_date", ""),
                "vote_average": tmdb.get("vote_average"),
            })
    return cards


def parse_tmdb_search_to_cards(data, keyword: str, limit: int = 24):
    keyword_l = keyword.strip().lower()

    if isinstance(data, dict) and "results" in data:
        raw_items = []
        for m in (data.get("results") or []):
            title = (m.get("title") or "").strip()
            tmdb_id = m.get("id")
            poster_path = m.get("poster_path")
            if not title or not tmdb_id:
                continue
            raw_items.append({
                "tmdb_id":      int(tmdb_id),
                "title":        title,
                "poster_url":   f"{TMDB_IMG}{poster_path}" if poster_path else None,
                "release_date": m.get("release_date", ""),
                "vote_average": m.get("vote_average"),
            })
    elif isinstance(data, list):
        raw_items = []
        for m in data:
            tmdb_id = m.get("tmdb_id") or m.get("id")
            title   = (m.get("title") or "").strip()
            if not title or not tmdb_id:
                continue
            raw_items.append({
                "tmdb_id":      int(tmdb_id),
                "title":        title,
                "poster_url":   m.get("poster_url"),
                "release_date": m.get("release_date", ""),
                "vote_average": m.get("vote_average"),
            })
    else:
        return [], []

    matched    = [x for x in raw_items if keyword_l in x["title"].lower()]
    final_list = matched if matched else raw_items

    suggestions = []
    for x in final_list[:10]:
        year  = (x.get("release_date") or "")[:4]
        label = f"{x['title']} ({year})" if year else x["title"]
        suggestions.append((label, x["tmdb_id"]))

    cards = [
        {
            "tmdb_id":      x["tmdb_id"],
            "title":        x["title"],
            "poster_url":   x["poster_url"],
            "release_date": x.get("release_date", ""),
            "vote_average": x.get("vote_average"),
        }
        for x in final_list[:limit]
    ]
    return suggestions, cards


# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown(
        "<div class='sidebar-brand'>"
        "<span class='mi'>theaters</span>CINESCOPE"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='muted'>Your personal cinema guide</div>", unsafe_allow_html=True)
    st.markdown("---")

    if st.button("Home"):
        goto_home()

    st.markdown("---")
    st.markdown("<div class='feed-label'>Home Feed</div>", unsafe_allow_html=True)
    home_category = st.selectbox(
        "Category",
        ["trending", "popular", "top_rated", "now_playing", "upcoming"],
        index=0,
        label_visibility="collapsed",
    )
    grid_cols = st.slider("Columns", 3, 8, 6)
    st.markdown("---")
    st.markdown("<div class='muted'>Powered by TMDB + TF-IDF</div>", unsafe_allow_html=True)


# =============================
# HEADER
# =============================
st.markdown("<h1>CINESCOPE</h1>", unsafe_allow_html=True)
st.markdown(
    "<div class='muted' style='margin-top:-6px;margin-bottom:16px'>"
    "Search &nbsp;&middot;&nbsp; Discover &nbsp;&middot;&nbsp; Explore"
    "</div>",
    unsafe_allow_html=True,
)
st.divider()


# ==========================================================
# VIEW: HOME
# ==========================================================
if st.session_state.view == "home":

    typed = st.text_input(
        "",
        placeholder="Search movies  —  Avengers, Inception, Love...",
        label_visibility="collapsed",
    )
    st.divider()

    # ── SEARCH MODE ──
    if typed.strip():
        if len(typed.strip()) < 2:
            st.markdown("<div class='muted'>Type at least 2 characters...</div>", unsafe_allow_html=True)
        else:
            with st.spinner("Searching..."):
                data, err = api_get_json("/tmdb/search", params={"query": typed.strip()})

            if err or data is None:
                st.error(f"Search failed: {err}")
            else:
                suggestions, cards = parse_tmdb_search_to_cards(data, typed.strip(), limit=24)

                if suggestions:
                    labels   = ["— Select a title —"] + [s[0] for s in suggestions]
                    selected = st.selectbox("", labels, index=0, label_visibility="collapsed")
                    if selected != "— Select a title —":
                        label_to_id = {s[0]: s[1] for s in suggestions}
                        goto_details(label_to_id[selected])
                else:
                    st.markdown(
                        "<div class='muted'>No suggestions found. Try another keyword.</div>",
                        unsafe_allow_html=True,
                    )

                if cards:
                    st.markdown(
                        f"<div class='section-label'>"
                        f"<span class='mi'>search</span>"
                        f"Results for &quot;{typed}&quot;"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    poster_grid(cards, cols=grid_cols, key_prefix="search_results")

        st.stop()

    # ── HOME FEED MODE ──
    category_icons = {
        "trending":    "local_fire_department",
        "popular":     "star",
        "top_rated":   "military_tech",
        "now_playing": "play_circle",
        "upcoming":    "event",
    }
    icon = category_icons.get(home_category, "movie")
    st.markdown(
        f"<div class='section-label'>"
        f"<span class='mi'>{icon}</span>"
        f"{home_category.replace('_', ' ').upper()}"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Loading movies..."):
        home_cards, err = api_get_json("/home", params={"category": home_category, "limit": 24})

    if err or not home_cards:
        st.error(f"Home feed failed: {err or 'Unknown error'}")
        st.stop()

    poster_grid(home_cards, cols=grid_cols, key_prefix="home_feed")


# ==========================================================
# VIEW: DETAILS
# ==========================================================
elif st.session_state.view == "details":
    tmdb_id = st.session_state.selected_tmdb_id
    if not tmdb_id:
        st.warning("No movie selected.")
        if st.button("Back to Home"):
            goto_home()
        st.stop()

    if st.button("Back"):
        goto_home()

    with st.spinner("Loading movie details..."):
        data, err = api_get_json(f"/movie/id/{tmdb_id}")

    if err or not data:
        st.error(f"Could not load details: {err or 'Unknown error'}")
        st.stop()

    # ── BACKDROP ──
    if data.get("backdrop_url"):
        st.markdown(
            f"""
            <div style="
                width:100%; height:300px; border-radius:18px; overflow:hidden;
                margin-bottom:24px; position:relative;
                background: url('{data['backdrop_url']}') center/cover no-repeat;
            ">
                <div style="
                    position:absolute; inset:0; border-radius:18px;
                    background: linear-gradient(
                        to top,
                        rgba(8,1,31,1) 0%,
                        rgba(8,1,31,0.52) 55%,
                        transparent 100%
                    );
                "></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── POSTER + INFO ──
    left, right = st.columns([1, 2.6], gap="large")

    with left:
        if data.get("poster_url"):
            st.image(data["poster_url"], use_column_width=True)
        else:
            st.markdown(
                "<div class='no-poster' style='height:420px;border-radius:14px'>"
                "<span class='mi mi-lg'>movie</span></div>",
                unsafe_allow_html=True,
            )

    with right:
        genres  = data.get("genres", [])
        release = data.get("release_date") or ""
        year    = release[:4] if release else ""
        rating  = data.get("vote_average")
        runtime = data.get("runtime")

        st.markdown(
            f"<div class='detail-title'>{data.get('title', '')}</div>",
            unsafe_allow_html=True,
        )

        if genres:
            badges = "".join(
                [f"<span class='detail-badge'>{g['name']}</span>" for g in genres]
            )
            st.markdown(f"<div style='margin-bottom:10px'>{badges}</div>", unsafe_allow_html=True)

        meta_parts = []
        if year:
            meta_parts.append(
                f"<span><span class='mi mi-sm'>calendar_today</span>{year}</span>"
            )
        if rating:
            try:
                meta_parts.append(
                    f"<span><span class='mi mi-sm'>star</span>{float(rating):.1f} / 10</span>"
                )
            except Exception:
                pass
        if runtime:
            h, m = divmod(int(runtime), 60)
            meta_parts.append(
                f"<span><span class='mi mi-sm'>schedule</span>{h}h {m}m</span>"
            )
        if meta_parts:
            st.markdown(
                f"<div class='detail-meta-row'>{''.join(meta_parts)}</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "<div class='overview-label'>"
            "<span class='mi mi-sm'>description</span>Overview"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='overview-text'>{data.get('overview') or 'No overview available.'}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── RECOMMENDATIONS ──
    title = (data.get("title") or "").strip()
    if title:
        with st.spinner("Finding recommendations..."):
            bundle, err2 = api_get_json(
                "/movie/search",
                params={"query": title, "tfidf_top_n": 12, "genre_limit": 12},
            )

        if not err2 and bundle:
            tfidf_cards = to_cards_from_tfidf_items(bundle.get("tfidf_recommendations"))
            genre_cards = bundle.get("genre_recommendations", [])

            if tfidf_cards:
                st.markdown(
                    "<div class='section-label'>"
                    "<span class='mi'>manage_search</span>Similar Movies"
                    "</div>",
                    unsafe_allow_html=True,
                )
                poster_grid(tfidf_cards, cols=grid_cols, key_prefix="details_tfidf")

            if genre_cards:
                st.markdown(
                    "<div class='section-label'>"
                    "<span class='mi'>category</span>More Like This"
                    "</div>",
                    unsafe_allow_html=True,
                )
                poster_grid(genre_cards, cols=grid_cols, key_prefix="details_genre")

        else:
            st.markdown(
                "<div class='section-label'>"
                "<span class='mi'>recommend</span>You May Also Like"
                "</div>",
                unsafe_allow_html=True,
            )
            with st.spinner("Loading recommendations..."):
                genre_only, err3 = api_get_json(
                    "/recommend/genre", params={"tmdb_id": tmdb_id, "limit": 18}
                )
            if not err3 and genre_only:
                poster_grid(genre_only, cols=grid_cols, key_prefix="details_genre_fallback")
            else:
                st.markdown(
                    "<div class='muted'>No recommendations available right now.</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            "<div class='muted'>No title available to compute recommendations.</div>",
            unsafe_allow_html=True,
        )
