import pickle
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd
import httpx
import os
import sys
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_500 = "https://image.tmdb.org/t/p/w500"

if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY missing. Please add it to .env file as: TMDB_API_KEY=your_api_key_here")

app = FastAPI(title="Movie Recommender API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DF_PATH = os.path.join(BASE_DIR, "df.pkl")
INDICES_PATH = os.path.join(BASE_DIR, "indices.pkl")
TFIDF_MATRIX_PATH = os.path.join(BASE_DIR, "tfidf_matrix.pkl")
TFIDF_PATH = os.path.join(BASE_DIR, "tfidf.pkl")

df: Optional[pd.DataFrame] = None
indices_obj: Any = None
tfidf_matrix: Any = None
tfidf_obj: Any = None
TITLE_TO_IDX: Optional[Dict[str, int]] = None

# =========================
# PYDANTIC MODELS
# =========================
class TMDBMovieCard(BaseModel):
    tmdb_id: int
    title: str
    poster_url: Optional[str] = None
    release_date: Optional[str] = None
    vote_average: Optional[float] = None

class TMDBMovieDetails(BaseModel):
    tmdb_id: int
    title: str
    overview: Optional[str] = None
    release_date: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    genres: List[dict] = []

class TFIDFRecItem(BaseModel):
    title: str
    score: float
    tmdb: Optional[TMDBMovieCard] = None

class SearchBundleResponse(BaseModel):
    query: str
    movie_details: TMDBMovieDetails
    tfidf_recommendations: List[TFIDFRecItem]
    genre_recommendations: List[TMDBMovieCard]

# =========================
# UTILITY FUNCTIONS
# =========================
def _norm_title(t: str) -> str:
    if not isinstance(t, str):
        t = str(t)
    return t.strip().lower()

def make_img_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"{TMDB_IMG_500}{path}"

async def tmdb_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    q = dict(params)
    q["api_key"] = TMDB_API_KEY
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{TMDB_BASE}{path}", params=q)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TMDB request timeout")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"TMDB connection error: {str(e)}")

    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Resource not found on TMDB")
    elif r.status_code == 401:
        raise HTTPException(status_code=502, detail="Invalid TMDB API key")
    elif r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"TMDB error {r.status_code}: {r.text[:200]}")
    return r.json()

async def tmdb_cards_from_results(results: List[dict], limit: int = 20) -> List[TMDBMovieCard]:
    out: List[TMDBMovieCard] = []
    for m in (results or [])[:limit]:
        try:
            out.append(TMDBMovieCard(
                tmdb_id=int(m["id"]),
                title=m.get("title") or m.get("name") or "Unknown",
                poster_url=make_img_url(m.get("poster_path")),
                release_date=m.get("release_date"),
                vote_average=m.get("vote_average"),
            ))
        except (KeyError, ValueError) as e:
            print(f"⚠️ Error creating movie card: {e}")
            continue
    return out

async def tmdb_movie_details(movie_id: int) -> TMDBMovieDetails:
    try:
        data = await tmdb_get(f"/movie/{movie_id}", {"language": "en-US"})
        return TMDBMovieDetails(
            tmdb_id=int(data["id"]),
            title=data.get("title") or "Unknown",
            overview=data.get("overview"),
            release_date=data.get("release_date"),
            poster_url=make_img_url(data.get("poster_path")),
            backdrop_url=make_img_url(data.get("backdrop_path")),
            genres=data.get("genres", []) or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching movie details: {str(e)}")

async def tmdb_search_movies(query: str, page: int = 1) -> Dict[str, Any]:
    return await tmdb_get(
        "/search/movie",
        {"query": query, "include_adult": "false", "language": "en-US", "page": page},
    )

async def tmdb_search_first(query: str) -> Optional[dict]:
    try:
        data = await tmdb_search_movies(query=query, page=1)
        results = data.get("results", [])
        return results[0] if results else None
    except Exception as e:
        print(f"⚠️ Error in tmdb_search_first: {e}")
        return None

# =========================
# TF-IDF HELPER FUNCTIONS
# =========================
def build_title_to_idx_map(indices: Any) -> Dict[str, int]:
    global df
    title_to_idx: Dict[str, int] = {}
    print(f"🔍 Building title map from indices type: {type(indices)}")

    if indices is None:
        print("⚠️ indices is None, trying to build from DataFrame")
        return _build_map_from_dataframe()

    if isinstance(indices, dict):
        print(f"📚 indices is a dictionary with {len(indices)} items")
        for k, v in indices.items():
            try:
                title_to_idx[_norm_title(str(k))] = int(v)
            except (ValueError, TypeError):
                continue
        if title_to_idx:
            print(f"✅ Converted {len(title_to_idx)} entries from dictionary")
            return title_to_idx

    try:
        if hasattr(indices, 'items') and hasattr(indices, 'index'):
            print(f"📚 indices is a Series with {len(indices)} items")
            for k, v in indices.items():
                try:
                    title_to_idx[_norm_title(str(k))] = int(v)
                except (ValueError, TypeError):
                    continue
            if title_to_idx:
                print(f"✅ Converted {len(title_to_idx)} entries from Series")
                return title_to_idx
    except Exception:
        pass

    try:
        if isinstance(indices, (list, np.ndarray)):
            print(f"📚 indices is a list/array of length {len(indices)}")
            if df is not None and 'title' in df.columns:
                for i, title in enumerate(df['title']):
                    if i < len(indices):
                        try:
                            title_to_idx[_norm_title(str(title))] = int(indices[i])
                        except (ValueError, TypeError):
                            continue
                if title_to_idx:
                    print(f"✅ Built map with {len(title_to_idx)} entries from array + DataFrame")
                    return title_to_idx
    except Exception:
        pass

    print("⚠️ Using DataFrame as fallback")
    return _build_map_from_dataframe()

def _build_map_from_dataframe() -> Dict[str, int]:
    global df
    title_to_idx: Dict[str, int] = {}
    if df is not None and 'title' in df.columns:
        for idx, title in enumerate(df['title']):
            try:
                title_to_idx[_norm_title(str(title))] = idx
            except Exception:
                continue
        print(f"✅ Built fallback map with {len(title_to_idx)} entries from DataFrame")
        return title_to_idx
    print("❌ Cannot build map: DataFrame not available or missing 'title' column")
    return {}

def get_local_idx_by_title(title: str) -> int:
    global TITLE_TO_IDX
    if TITLE_TO_IDX is None or len(TITLE_TO_IDX) == 0:
        raise HTTPException(status_code=500, detail="TF-IDF index map not initialized or empty")

    key = _norm_title(title)
    if key in TITLE_TO_IDX:
        return int(TITLE_TO_IDX[key])

    for stored_title, idx in TITLE_TO_IDX.items():
        if key in stored_title or stored_title in key:
            return int(idx)

    import re
    key_clean = re.sub(r'[^\w\s]', '', key)
    for stored_title, idx in TITLE_TO_IDX.items():
        stored_clean = re.sub(r'[^\w\s]', '', stored_title)
        if key_clean in stored_clean or stored_clean in key_clean:
            return int(idx)

    raise HTTPException(status_code=404, detail=f"Title not found in local dataset: '{title}'")

def tfidf_recommend_titles(query_title: str, top_n: int = 10) -> List[Tuple[str, float]]:
    global df, tfidf_matrix
    if df is None or tfidf_matrix is None:
        print("⚠️ TF-IDF resources not loaded")
        return []
    try:
        idx = get_local_idx_by_title(query_title)
    except HTTPException:
        print(f"⚠️ Title not found: {query_title}")
        return []
    try:
        qv = tfidf_matrix[idx]
        if hasattr(tfidf_matrix, 'dot'):
            scores = tfidf_matrix.dot(qv.T)
            if hasattr(scores, 'toarray'):
                scores = scores.toarray().ravel()
            else:
                scores = scores.ravel()
        else:
            scores = np.dot(tfidf_matrix, qv.T).ravel()

        order = np.argsort(-scores)
        out: List[Tuple[str, float]] = []
        for i in order:
            if int(i) == int(idx):
                continue
            try:
                title_i = str(df.iloc[int(i)]["title"])
                if scores[int(i)] > 0:
                    out.append((title_i, float(scores[int(i)])))
                    if len(out) >= top_n:
                        break
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"⚠️ Error in tfidf recommendation: {e}")
        return []

async def attach_tmdb_card_by_title(title: str) -> Optional[TMDBMovieCard]:
    try:
        m = await tmdb_search_first(title)
        if not m:
            return None
        return TMDBMovieCard(
            tmdb_id=int(m["id"]),
            title=m.get("title") or title,
            poster_url=make_img_url(m.get("poster_path")),
            release_date=m.get("release_date"),
            vote_average=m.get("vote_average"),
        )
    except Exception as e:
        print(f"⚠️ Error attaching TMDB card for '{title}': {e}")
        return None

# =========================
# STARTUP: LOAD PICKLE FILES
# =========================
@app.on_event("startup")
def load_pickles():
    global df, indices_obj, tfidf_matrix, tfidf_obj, TITLE_TO_IDX  # ← only once, right at the top

    print("=" * 60)
    print("🚀 LOADING PICKLE FILES")
    print("=" * 60)

    # Check files exist
    files_to_check = {
        "df.pkl": DF_PATH,
        "indices.pkl": INDICES_PATH,
        "tfidf_matrix.pkl": TFIDF_MATRIX_PATH,
    }
    missing_files = []
    for name, path in files_to_check.items():
        if not os.path.exists(path):
            missing_files.append(name)
            print(f"❌ File not found: {name} at {path}")
        else:
            size = os.path.getsize(path) / 1024
            print(f"✅ Found {name} ({size:.2f} KB)")

    if missing_files:
        raise RuntimeError(f"Required files missing: {', '.join(missing_files)}")

    # Load DataFrame
    print("\n📊 Loading DataFrame...")
    try:
        with open(DF_PATH, "rb") as f:
            df = pickle.load(f)
        print(f"✅ DataFrame loaded. Shape: {df.shape}")
        print(f"   Columns: {list(df.columns)}")
        if 'title' in df.columns:
            print(f"   First 5 titles: {df['title'].head(5).tolist()}")
    except ModuleNotFoundError as e:
        if 'numpy._core' in str(e):
            print("⚠️ NumPy compatibility issue. Trying fix...")
            try:
                import numpy
                if not hasattr(numpy, '_core'):
                    class _Core:
                        pass
                    numpy._core = _Core
                    numpy._core.multiarray = numpy.core.multiarray
                with open(DF_PATH, "rb") as f:
                    df = pickle.load(f)
                print("✅ Loaded with compatibility fix")
            except Exception:
                try:
                    with open(DF_PATH, "rb") as f:
                        df = pickle.load(f, encoding='latin1')
                    print("✅ Loaded with latin1 encoding")
                except Exception:
                    raise RuntimeError("Could not load df.pkl with any method")
        else:
            raise RuntimeError(f"Failed to load df.pkl: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load df.pkl: {e}")

    # Load indices
    print("\n🔢 Loading indices...")
    indices_load_attempts = [
        ("normal", lambda f: pickle.load(f)),
        ("latin1 encoding", lambda f: pickle.load(f, encoding='latin1')),
        ("bytes encoding", lambda f: pickle.load(f, encoding='bytes')),
    ]
    indices_obj = None
    for method_name, load_func in indices_load_attempts:
        try:
            with open(INDICES_PATH, "rb") as f:
                indices_obj = load_func(f)
            print(f"✅ Indices loaded with {method_name}. Type: {type(indices_obj)}")
            if isinstance(indices_obj, dict):
                print(f"   Sample: {dict(list(indices_obj.items())[:3])}")
            elif hasattr(indices_obj, 'items'):
                print(f"   Sample: {dict(list(indices_obj.items())[:3])}")
            elif isinstance(indices_obj, (list, np.ndarray)):
                print(f"   First 5: {indices_obj[:5]}")
            break
        except Exception as e:
            print(f"⚠️ {method_name} failed: {e}")
            continue

    if indices_obj is None:
        print("⚠️ Could not load indices — will use DataFrame fallback")

    # Load TF-IDF matrix
    print("\n🔢 Loading TF-IDF matrix...")
    try:
        with open(TFIDF_MATRIX_PATH, "rb") as f:
            try:
                tfidf_matrix = pickle.load(f)
            except ModuleNotFoundError as e:
                if 'scipy' in str(e):
                    print("❌ Scipy not found. Installing...")
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy==1.10.0"])
                    with open(TFIDF_MATRIX_PATH, "rb") as f2:
                        tfidf_matrix = pickle.load(f2)
                else:
                    raise
        if hasattr(tfidf_matrix, 'shape'):
            print(f"✅ TF-IDF matrix loaded. Shape: {tfidf_matrix.shape}")
    except Exception as e:
        raise RuntimeError(f"Failed to load tfidf_matrix.pkl: {e}")

    # Load TF-IDF vectorizer (optional)
    print("\n🔧 Loading TF-IDF vectorizer...")
    try:
        if os.path.exists(TFIDF_PATH):
            with open(TFIDF_PATH, "rb") as f:
                tfidf_obj = pickle.load(f)
            print("✅ TF-IDF vectorizer loaded.")
        else:
            print("⚠️ tfidf.pkl not found - continuing without it")
            tfidf_obj = None
    except ModuleNotFoundError as e:
        if 'sklearn' in str(e):
            print("⚠️ scikit-learn not found - installing...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "scikit-learn==1.2.2"])
            with open(TFIDF_PATH, "rb") as f:
                tfidf_obj = pickle.load(f)
            print("✅ TF-IDF vectorizer loaded after installing sklearn")
        else:
            tfidf_obj = None
    except Exception as e:
        print(f"⚠️ Could not load tfidf.pkl: {e}")
        tfidf_obj = None

    # Build title-to-index map
    print("\n🔨 Building title-to-index map...")
    TITLE_TO_IDX = build_title_to_idx_map(indices_obj)

    if TITLE_TO_IDX and len(TITLE_TO_IDX) > 0:
        print(f"✅ Title map built. Size: {len(TITLE_TO_IDX)}")
        print(f"   Sample titles: {list(TITLE_TO_IDX.keys())[:5]}")
    else:
        print("❌ Title map is empty! Trying emergency fallback...")
        if df is not None and 'title' in df.columns:
            TITLE_TO_IDX = {_norm_title(str(title)): idx for idx, title in enumerate(df['title'])}
            print(f"✅ Emergency fallback map built with {len(TITLE_TO_IDX)} entries")
        else:
            print("❌ Cannot build emergency fallback")
            TITLE_TO_IDX = {}

    # Final validation
    print("\n🔍 Final validation:")
    print(f"   DataFrame:    {'✅' if df is not None else '❌'}")
    print(f"   Title map:    {'✅' if TITLE_TO_IDX else '❌'} ({len(TITLE_TO_IDX) if TITLE_TO_IDX else 0} entries)")
    print(f"   TF-IDF matrix:{'✅' if tfidf_matrix is not None else '❌'}")

    if TITLE_TO_IDX and tfidf_matrix is not None:
        print("\n🎬 SUCCESS: All systems ready!")
    else:
        print("\n⚠️ WARNING: Some components failed to load")
    print("=" * 60)

# =========================
# API ROUTES
# =========================
@app.get("/")
async def root():
    return {
        "message": "Movie Recommender API",
        "version": "3.0",
        "status": "running",
        "title_map_size": len(TITLE_TO_IDX) if TITLE_TO_IDX else 0,
        "endpoints": ["/health", "/home", "/tmdb/search", "/movie/id/{tmdb_id}",
                      "/recommend/genre", "/recommend/tfidf", "/movie/search"]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "title_map_size": len(TITLE_TO_IDX) if TITLE_TO_IDX else 0,
        "dataframe_loaded": df is not None,
        "tfidf_matrix_loaded": tfidf_matrix is not None
    }

@app.get("/home", response_model=List[TMDBMovieCard])
async def home(
    category: str = Query("popular"),
    limit: int = Query(24, ge=1, le=50),
):
    try:
        valid_categories = {"popular", "top_rated", "upcoming", "now_playing", "trending"}
        if category == "trending":
            data = await tmdb_get("/trending/movie/day", {"language": "en-US"})
            return await tmdb_cards_from_results(data.get("results", []), limit=limit)
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail="Invalid category")
        data = await tmdb_get(f"/movie/{category}", {"language": "en-US", "page": 1})
        return await tmdb_cards_from_results(data.get("results", []), limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Home route failed: {str(e)}")

@app.get("/tmdb/search")
async def tmdb_search(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1, le=10),
):
    try:
        return await tmdb_search_movies(query=query, page=page)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/movie/id/{tmdb_id}", response_model=TMDBMovieDetails)
async def movie_details_route(tmdb_id: int):
    return await tmdb_movie_details(tmdb_id)

@app.get("/recommend/genre", response_model=List[TMDBMovieCard])
async def recommend_genre(
    tmdb_id: int = Query(...),
    limit: int = Query(18, ge=1, le=50),
):
    try:
        details = await tmdb_movie_details(tmdb_id)
        if not details.genres:
            return []
        genre_id = details.genres[0]["id"]
        discover = await tmdb_get(
            "/discover/movie",
            {"with_genres": genre_id, "language": "en-US", "sort_by": "popularity.desc", "page": 1},
        )
        cards = await tmdb_cards_from_results(discover.get("results", []), limit=limit)
        return [c for c in cards if c.tmdb_id != tmdb_id]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Genre recommendation failed: {str(e)}")

@app.get("/recommend/tfidf")
async def recommend_tfidf(
    title: str = Query(..., min_length=1),
    top_n: int = Query(10, ge=1, le=50),
):
    if not TITLE_TO_IDX or len(TITLE_TO_IDX) == 0:
        raise HTTPException(status_code=503, detail="Recommendation system not fully initialized")
    recs = tfidf_recommend_titles(title, top_n=top_n)
    return [{"title": t, "score": round(s, 4)} for t, s in recs]

@app.get("/movie/search", response_model=SearchBundleResponse)
async def search_bundle(
    query: str = Query(..., min_length=1),
    tfidf_top_n: int = Query(12, ge=1, le=30),
    genre_limit: int = Query(12, ge=1, le=30),
):
    best = await tmdb_search_first(query)
    if not best:
        raise HTTPException(status_code=404, detail=f"No TMDB movie found for query: '{query}'")

    tmdb_id = int(best["id"])
    details = await tmdb_movie_details(tmdb_id)

    tfidf_items: List[TFIDFRecItem] = []
    if TITLE_TO_IDX and len(TITLE_TO_IDX) > 0:
        recs = tfidf_recommend_titles(details.title, top_n=tfidf_top_n)
        if not recs:
            recs = tfidf_recommend_titles(query, top_n=tfidf_top_n)
        for title, score in recs:
            card = await attach_tmdb_card_by_title(title)
            tfidf_items.append(TFIDFRecItem(title=title, score=round(score, 4), tmdb=card))

    genre_recs: List[TMDBMovieCard] = []
    if details.genres:
        genre_id = details.genres[0]["id"]
        try:
            discover = await tmdb_get(
                "/discover/movie",
                {"with_genres": genre_id, "language": "en-US", "sort_by": "popularity.desc", "page": 1},
            )
            cards = await tmdb_cards_from_results(discover.get("results", []), limit=genre_limit)
            genre_recs = [c for c in cards if c.tmdb_id != details.tmdb_id]
        except Exception as e:
            print(f"⚠️ Error getting genre recommendations: {e}")

    return SearchBundleResponse(
        query=query,
        movie_details=details,
        tfidf_recommendations=tfidf_items,
        genre_recommendations=genre_recs,
    )

# =========================
# ERROR HANDLERS
# =========================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "success": False})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print(f"❌ Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "success": False})