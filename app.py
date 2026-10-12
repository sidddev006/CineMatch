"""
Movie Recommendation Web Application
A Flask-based web app that recommends movies based on user preferences using TMDB API.
Features: User authentication, personalized recommendations, and watchlist management.
"""

# ============================================================================
# IMPORTS
# ============================================================================
import time
import requests
from urllib.parse import urlencode
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps


# ============================================================================
# DECORATOR: LOGIN REQUIRED
# ============================================================================
def login_required(f):
    """
    Decorator to protect routes that require authentication.
    Redirects unauthenticated users to the login page.
    
    Source: Flask documentation on view decorators
    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================
app = Flask(__name__)

# Database connection - stores user accounts and watchlists
db = SQL("sqlite:///project.db")

# TMDB API key for fetching movie data
TMDB_API_KEY = "4e4a70b35de6e22f19ede8cb6c7b18d7"

# Session configuration - uses server-side file storage instead of cookies
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# ============================================================================
# RESPONSE HEADERS - PREVENT CACHING
# ============================================================================
@app.after_request
def after_request(response):
    """
    Ensures responses aren't cached by the browser.
    Important for dynamic content and logged-in user data.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# ============================================================================
# ADMIN ROUTE - VIEW DATABASE (DEVELOPMENT ONLY)
# ============================================================================
@app.route('/admin/viewdb')
def view_database():
    """
    Admin route to view all database tables and their contents.
    WARNING: Remove or password-protect this route in production!
    """
    db = SQL("sqlite:///project.db")
    
    # Fetch all table names from SQLite metadata
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    
    html = "<h1>Database Contents</h1>"
    
    # Iterate through each table and display its data
    for table in tables:
        table_name = table['name']
        html += f"<h2>Table: {table_name}</h2>"
        
        try:
            rows = db.execute(f"SELECT * FROM {table_name}")
            html += "<table border='1' style='border-collapse: collapse;'>"
            
            if rows:
                # Build table headers from column names
                html += "<tr>"
                for key in rows[0].keys():
                    html += f"<th style='padding: 10px;'>{key}</th>"
                html += "</tr>"
                
                # Build table rows with data
                for row in rows:
                    html += "<tr>"
                    for value in row.values():
                        html += f"<td style='padding: 10px;'>{value}</td>"
                    html += "</tr>"
            
            html += "</table><br>"
        except:
            html += "<p>No data</p><br>"
    
    return html


# ============================================================================
# ROUTE: HOME / INDEX
# ============================================================================
@app.route("/")
def index():
    """
    Landing page - displays welcome screen to all visitors.
    No authentication required.
    """
    return render_template("index.html")


# ============================================================================
# ROUTE: USER REGISTRATION
# ============================================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Handles new user registration.
    GET: Display registration form
    POST: Process registration, validate input, create account, and log user in
    """
    if request.method == "POST":
        # Get and validate username
        username = request.form.get("username")
        if not username:
            flash("invalid username")
            return render_template("register.html")
        
        # Check if username already exists in database
        users = db.execute("SELECT * FROM users WHERE username = ?", username)
        if users:
            flash("username already exists")
            return render_template("register.html")

        # Get passwords and verify they match
        password = request.form.get("password")
        pass_confirm = request.form.get("pass_confirm")
        if password != pass_confirm:
            flash("both passwords should be same")
            return render_template("register.html")

        # Hash password for security and insert new user into database
        pass_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, pass_hash)
        
        # Automatically log in the new user by storing their ID in session
        rows = db.execute("SELECT id FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]
        
        return redirect("/home")
    
    # GET request - show registration form
    return render_template("register.html")


# ============================================================================
# ROUTE: USER LOGIN
# ============================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user authentication.
    GET: Display login form
    POST: Validate credentials and create user session
    """
    if request.method == "POST":
        # Get and validate username
        username = request.form.get("username")
        if not username:
            flash("username required")
            return render_template("login.html")
        
        # Check if username exists in database
        users = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(users) == 0:
            flash("username not found, try entering correct username or register again")
            return render_template("login.html")
        
        # Verify password matches the stored hash
        password = request.form.get("password")
        if not check_password_hash(users[0]["hash"], password):
            flash("wrong password, please try again!")
            return render_template("login.html")
        
        # Store user ID in session to maintain login state
        session["user_id"] = users[0]["id"]
        return redirect("/home")
    
    # GET request - show login form
    return render_template("login.html")


# ============================================================================
# ROUTE: USER HOME PAGE
# ============================================================================
@app.route("/home")
@login_required
def home():
    """
    User's home page after login.
    Displays personalized welcome message with username.
    """
    # Retrieve username from database using session user_id
    user_id = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = ?", user_id)
    username = username[0]["username"]
    
    return render_template("home.html", username=username)


# ============================================================================
# ALGORITHM: WEIGHTED RATING CALCULATION
# ============================================================================
def calculate_weighted_rating(vote_count, vote_average, m=500, c=8.0):
    """
    Calculates a Bayesian weighted rating for movies.
    
    This algorithm balances popularity (vote count) with quality (average rating)
    to prevent movies with few votes but high ratings from dominating results.
    
    Formula: (v/(v+m)) * R + (m/(v+m)) * C
    Where:
        v = vote_count (number of votes for the movie)
        R = vote_average (average rating of the movie)
        m = minimum votes required (default 500)
        C = mean vote across all movies (default 8.0)
    
    Returns: Weighted rating score (float)
    """
    return (vote_count/(vote_count + m)) * vote_average + (m/(vote_count + m)) * c


# ============================================================================
# DATA: TMDB GENRE MAPPING
# ============================================================================
# Genre IDs from The Movie Database (TMDB) API
# Used to filter movies by genre in recommendation system
genres = [
    {"id": 28, "name": "Action"}, 
    {"id": 12, "name": "Adventure"},
    {"id": 16, "name": "Animation"}, 
    {"id": 35, "name": "Comedy"},
    {"id": 80, "name": "Crime"}, 
    {"id": 99, "name": "Documentary"},
    {"id": 18, "name": "Drama"}, 
    {"id": 10751, "name": "Family"},
    {"id": 14, "name": "Fantasy"}, 
    {"id": 36, "name": "History"},
    {"id": 27, "name": "Horror"}, 
    {"id": 10402, "name": "Music"},
    {"id": 9648, "name": "Mystery"}, 
    {"id": 10749, "name": "Romance"},
    {"id": 878, "name": "Science Fiction"}, 
    {"id": 10770, "name": "TV Movie"},
    {"id": 53, "name": "Thriller"}, 
    {"id": 10752, "name": "War"},
    {"id": 37, "name": "Western"}
]


# ============================================================================
# ROUTE: MOVIE RECOMMENDATION ENGINE (CORE FEATURE)
# ============================================================================
@app.route("/recommend", methods=["GET", "POST"])
@login_required
def recommend():
    """
    Main recommendation system - the heart of the application.
    
    Handles both initial form display and filtered movie results.
    Accepts filters via POST (form submission) or GET (URL parameters).
    GET parameters are used when redirecting back from "add to watchlist"
    to preserve user's filter selections.
    
    Filters available:
    - Genre (e.g., Action, Comedy, Drama)
    - Runtime (maximum movie length in minutes)
    - Decade (e.g., 1990s, 2000s, 2010s)
    """
    
    # Initialize filter variables
    genre = None
    runtime = None
    decade = None

    # ---- DETERMINE REQUEST TYPE AND EXTRACT FILTERS ----
    
    if request.method == "POST":
        # User submitted the form - extract filters from form data
        genre = request.form.get("genre")
        runtime = request.form.get("runtime")
        decade = request.form.get("decade")

    elif request.args.get("genre") or request.args.get("runtime") or request.args.get("decade"):
        # User was redirected back with URL parameters (e.g., after adding to watchlist)
        # This preserves their filter selections
        genre = request.args.get("genre")
        runtime = request.args.get("runtime")
        decade = request.args.get("decade")

    else:
        # Initial GET request - show recommendation form
        user_id = session.get("user_id")
        username = db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"]
        return render_template("recommend.html", genres=genres, username=username)

    # ---- TMDB API CALL - FETCH MOVIES ----
    
    base_url = "https://api.themoviedb.org/3/discover/movie"
    recommend_movies = []  # Will store all filtered movie data

    # Build query parameters for TMDB API
    params = {
        "api_key": TMDB_API_KEY,
        "vote_count.gte": 450,  # Only movies with at least 450 votes (ensures quality)
        "sort_by": "vote_average.desc",  # Sort by highest rated first
        "include_adult": "true"
    }

    # Add optional filters if provided by user
    if genre:
        params["with_genres"] = genre
    if runtime:
        params["with_runtime.lte"] = runtime  # Movies shorter than or equal to specified runtime
    if decade:
        # Convert decade to date range (e.g., "1990" → "1990-01-01" to "1999-12-31")
        start_time = f"{decade[:3]}0-01-01"
        end_time = f"{decade[:3]}9-12-31"
        params["primary_release_date.gte"] = start_time
        params["primary_release_date.lte"] = end_time

    # ---- LOOP THROUGH API PAGES ----
    # Fetching first 3 pages provides enough high-quality results
    # without making too many API calls or slowing down the app
    for page in range(1, 3):
        params["page"] = page
        response = requests.get(base_url, params=params)

        # Skip this page if API call failed
        if response.status_code != 200:
            continue

        data = response.json()

        # Safety check - ensure response has results
        if "results" not in data:
            continue

        # ---- PROCESS EACH MOVIE ----
        for movie in data["results"]:
            vote_count = movie.get("vote_count", 0)
            vote_average = movie.get("vote_average", 0)
            
            # Calculate weighted rating using our custom algorithm
            weighted_rating = calculate_weighted_rating(vote_count, vote_average)

            # Filter out movies with low weighted ratings (below 7.0)
            if weighted_rating < 7.0:
                continue

            # Add movie to our results list
            recommend_movies.append({
                "id": movie.get("id"),
                "title": movie.get("title", "Unknown Title"),
                "overview": movie.get("overview", "No description available."),
                "poster_path": movie.get("poster_path"),
                "weighted_rating": weighted_rating,
                "release_date": movie.get("release_date", "N/A")
            })

    # ---- FINALIZE RESULTS ----

    # Sort movies by weighted rating (highest first)
    recommend_movies.sort(key=lambda x: x["weighted_rating"], reverse=True)

    # Limit to top 10 movies to avoid slow page loads
    top_movies = recommend_movies[:10]
    
    # ---- CHECK WATCHLIST STATUS ----
    # Pre-fetch all movie IDs already in user's watchlist
    # This allows us to show "Already in Watchlist" instead of "Add to Watchlist"
    user_id = session["user_id"]
    watchlist_movie_ids = db.execute("SELECT movie_id FROM watchlist WHERE user_id = ?", user_id)
    watchlist_ids = {row["movie_id"] for row in watchlist_movie_ids}

    # ---- FETCH RUNTIME FOR EACH MOVIE ----
    # TMDB's discover endpoint doesn't include runtime, so we need separate API calls
    detail_url = "https://api.themoviedb.org/3/movie"
    
    for movie in top_movies:
        try:
            # Make individual API call to get movie details including runtime
            detail_resp = requests.get(
                f"{detail_url}/{movie['id']}",
                params={"api_key": TMDB_API_KEY}
            )
            if detail_resp.status_code == 200:
                detail_data = detail_resp.json()
                movie["runtime"] = detail_data.get("runtime", "N/A")
            else:
                movie["runtime"] = "N/A"
        except Exception:
            # If API call fails, set runtime to "N/A"
            movie["runtime"] = "N/A"

        # Flag whether this movie is already in user's watchlist
        movie["in_watchlist"] = movie["id"] in watchlist_ids

    # ---- RENDER RESULTS PAGE ----
    # Pass movies and filter values to template for display
    return render_template("movies.html", movies=top_movies, genre=genre, decade=decade, runtime=runtime)


# ============================================================================
# ROUTE: ADD MOVIE TO WATCHLIST
# ============================================================================
@app.route("/add_to_watchlist", methods=["POST"])
@login_required
def add_to_watchlist():
    """
    Adds a movie to the user's watchlist.
    After adding, redirects back to recommendations page with filters preserved.
    """
    # Get movie ID and filter values from form
    movie_id = request.form.get("movie_id")
    runtime = request.form.get("runtime")
    genre = request.form.get("genre")
    decade = request.form.get("decade")
    user_id = session["user_id"]

    # Check if movie is already in watchlist (prevent duplicates)
    movie = db.execute(
        "SELECT * FROM watchlist WHERE movie_id = ? AND user_id = ?", 
        movie_id, user_id
    )

    # Only insert if movie doesn't already exist
    if not movie:
        db.execute("INSERT INTO watchlist (movie_id, user_id) VALUES (?, ?)", movie_id, user_id)

    # ---- PRESERVE FILTERS WHEN REDIRECTING ----
    # Build URL with query parameters to maintain user's filter selections
    query_params = {}
    if genre:
        query_params["genre"] = genre
    if runtime:
        query_params["runtime"] = runtime
    if decade:
        query_params["decade"] = decade

    # Redirect back to recommendations with or without filters
    if query_params:
        redirect_url = f"/recommend?{urlencode(query_params)}"
    else:
        redirect_url = "/recommend"

    return redirect(redirect_url)


# ============================================================================
# ROUTE: VIEW WATCHLIST
# ============================================================================
@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    """
    Displays all movies in the user's watchlist.
    Fetches fresh data from TMDB API for each movie to ensure up-to-date info.
    """
    user_id = session["user_id"]
    
    # Get all movie IDs from user's watchlist
    watchlist_items = db.execute("SELECT movie_id FROM watchlist WHERE user_id = ?", user_id)

    movies = []
    
    # Fetch full details for each movie from TMDB API
    for item in watchlist_items:
        movie_id = item["movie_id"]
        base_url = f"https://api.themoviedb.org/3/movie/{movie_id}"

        # Make API call to get movie details
        response = requests.get(base_url, params={"api_key": TMDB_API_KEY})
        
        if response.status_code == 200:  # Only process if API call succeeded
            movie_data = response.json()

            # Add movie details to our list
            movies.append({
                "id": movie_id,
                "title": movie_data.get("title", "Unknown Title"),
                "overview": movie_data.get("overview", "No description available."),
                "poster_path": movie_data.get("poster_path"),
                "release_date": movie_data.get("release_date", "N/A"),
                "runtime": movie_data.get("runtime")
            })

    return render_template("watchlist.html", movies=movies)


# ============================================================================
# ROUTE: REMOVE MOVIE FROM WATCHLIST
# ============================================================================
@app.route("/remove_from_watchlist", methods=["GET", "POST"])
@login_required
def remove_from_watchlist():
    """
    Removes a specific movie from the user's watchlist.
    Redirects back to watchlist page after deletion.
    """
    movie_id = request.form.get("movie_id")
    user_id = session["user_id"]
    
    # Delete the movie from watchlist table
    db.execute("DELETE FROM watchlist WHERE user_id = ? AND movie_id = ?", user_id, movie_id)
    
    return redirect("/watchlist")


# ============================================================================
# ROUTE: LOGOUT
# ============================================================================
@app.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Logs out the user by clearing their session data.
    Redirects to landing page after logout.
    """
    session.clear()  # Remove all session data including user_id
    return redirect("/")


# ============================================================================
# PERSONALIZED MOVIE & SERIES RECOMMENDER
# ============================================================================
# This flow is separate from the original weighted-rating discovery route.
# It uses TMDB discovery results, genre affinity, and a user's 1-10 ratings.
MOVIE_GENRES = [
    {"id": 28, "name": "Action"}, {"id": 12, "name": "Adventure"},
    {"id": 16, "name": "Animation"}, {"id": 35, "name": "Comedy"},
    {"id": 80, "name": "Crime"}, {"id": 99, "name": "Documentary"},
    {"id": 18, "name": "Drama"}, {"id": 10751, "name": "Family"},
    {"id": 14, "name": "Fantasy"}, {"id": 36, "name": "History"},
    {"id": 27, "name": "Horror"}, {"id": 10402, "name": "Music"},
    {"id": 9648, "name": "Mystery"}, {"id": 10749, "name": "Romance"},
    {"id": 878, "name": "Science Fiction"}, {"id": 53, "name": "Thriller"},
    {"id": 10752, "name": "War"}, {"id": 37, "name": "Western"}
]
TV_GENRES = [
    {"id": 10759, "name": "Action & Adventure"}, {"id": 16, "name": "Animation"},
    {"id": 35, "name": "Comedy"}, {"id": 80, "name": "Crime"},
    {"id": 99, "name": "Documentary"}, {"id": 18, "name": "Drama"},
    {"id": 10751, "name": "Family"}, {"id": 10762, "name": "Kids"},
    {"id": 9648, "name": "Mystery"}, {"id": 10763, "name": "News"},
    {"id": 10764, "name": "Reality"}, {"id": 10765, "name": "Sci-Fi & Fantasy"},
    {"id": 10766, "name": "Soap"}, {"id": 10767, "name": "Talk"},
    {"id": 10768, "name": "War & Politics"}, {"id": 37, "name": "Western"}
]
GENRE_NAMES = {
    entry["id"]: entry["name"] for entry in MOVIE_GENRES + TV_GENRES
}

def _haunted_discover(media_type, genre_ids, page, recommendation=False):
    """Fetch one page from TMDB, with bounded timeouts and safe fallbacks."""
    endpoint = "tv" if media_type == "tv" else "movie"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "sort_by": "vote_average.desc",
        "include_adult": "false",
        "page": page,
        "vote_count.gte": 20 if recommendation else 5
    }
    if genre_ids:
        params["with_genres"] = "|".join(str(value) for value in genre_ids)
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/discover/" + endpoint,
            params=params,
            timeout=12
        )
        response.raise_for_status()
        payload = response.json()
        titles = []
        for result in payload.get("results", []):
            item = dict(result)
            item["media_type"] = media_type
            item["title"] = item.get("name" if media_type == "tv" else "title", "Untitled")
            item["release_date"] = item.get("first_air_date" if media_type == "tv" else "release_date", "")
            item["genre_ids"] = item.get("genre_ids", [])
            if item.get("title"):
                titles.append(item)
        return titles
    except (requests.RequestException, ValueError):
        return []

def _haunted_genre_ids(media_type, selected):
    if media_type == "tv":
        allowed = {entry["id"] for entry in TV_GENRES}
        # TMDB has no TV Horror genre. Mystery and Sci-Fi & Fantasy are the
        # closest TV catalog categories for supernatural and horror series.
        remap = {27: 9648, 14: 10765, 878: 10765, 53: 9648, 10749: 18}
        return list(dict.fromkeys(remap.get(int(value), int(value)) for value in selected
                                  if remap.get(int(value), int(value)) in allowed))
    allowed = {entry["id"] for entry in MOVIE_GENRES}
    return list(dict.fromkeys(int(value) for value in selected if int(value) in allowed))

def _haunted_title_quality(item):
    votes = max(int(item.get("vote_count") or 0), 0)
    rating = float(item.get("vote_average") or 0)
    return ((votes / (votes + 350)) * rating + (350 / (votes + 350)) * 6.8) / 10

@app.route("/haunted", methods=["GET", "POST"])
@login_required
def haunted_recommender():
    """Three-step, session-scoped recommender for films, series, or both."""
    if request.method == "GET":
        session.pop("haunted_recommender", None)
        return render_template("haunted.html", stage="preferences", genres=MOVIE_GENRES)

    stage = request.form.get("stage")
    if stage == "survey":
        media_type = request.form.get("media_type", "both")
        if media_type not in {"movie", "tv", "both"}:
            media_type = "both"
        selected_genres = request.form.getlist("genres")
        genres_by_type = {
            "movie": _haunted_genre_ids("movie", selected_genres),
            "tv": _haunted_genre_ids("tv", selected_genres)
        }
        types = ["movie", "tv"] if media_type == "both" else [media_type]
        titles = []
        for kind in types:
            genres_for_kind = genres_by_type[kind]
            for page in (1, 2):
                titles.extend(_haunted_discover(kind, genres_for_kind, page))
        # Interleave formats and genres so the taste check is not just one long block.
        deduped = {}
        for item in titles:
            deduped[(item["media_type"], item["id"])] = item
        titles = sorted(
            deduped.values(),
            key=lambda item: (item.get("vote_count", 0), item.get("vote_average", 0)),
            reverse=True
        )[:16]
        if len(titles) < 8:
            flash("TMDB returned too few titles just now. Please try again.")
            return render_template("haunted.html", stage="preferences", genres=MOVIE_GENRES)
        session["haunted_recommender"] = {
            "media_type": media_type,
            "genres": selected_genres,
            "titles": titles
        }
        return render_template("haunted.html", stage="survey", titles=titles)

    if stage == "results":
        state = session.get("haunted_recommender")
        if not state:
            flash("Please start a new recommendation round.")
            return redirect("/haunted")
        watched = set()
        ratings = {}
        for item in state["titles"]:
            key = item["media_type"] + "_" + str(item["id"])
            if request.form.get("status_" + key) == "watched":
                watched.add((item["media_type"], int(item["id"])))
                try:
                    ratings[key] = max(1, min(10, int(request.form.get("rating_" + key, 7))))
                except (TypeError, ValueError):
                    ratings[key] = 7

        # Begin with explicit genre choices, then learn from each watched title.
        genre_affinity = {}
        selected = {int(value) for value in state["genres"]}
        for genre_id in selected:
            genre_affinity[genre_id] = 1.0
        for item in state["titles"]:
            key = item["media_type"] + "_" + str(item["id"])
            if key not in ratings:
                continue
            # Ratings above/below 6 raise/lower the item's genre preference.
            preference = (ratings[key] - 5.5) / 4.5
            for genre_id in item.get("genre_ids", []):
                genre_affinity[genre_id] = max(-1.0, min(1.5,
                    genre_affinity.get(genre_id, 0.0) + preference * 0.65))

        media_types = ["movie", "tv"] if state["media_type"] == "both" else [state["media_type"]]
        picks = []
        for kind in media_types:
            genres_for_kind = _haunted_genre_ids(kind, state["genres"])
            # If the user supplied no genres, request a broad quality-ranked catalog.
            for page in (1, 2, 3):
                for item in _haunted_discover(kind, genres_for_kind, page, recommendation=True):
                    item_key = (kind, int(item["id"]))
                    if item_key in watched:
                        continue
                    genre_ids = item.get("genre_ids", [])
                    if genre_affinity and genre_ids:
                        mapped_affinity = []
                        for genre_id in genre_ids:
                            if kind == "tv" and genre_id == 10765:
                                mapped_affinity.extend(genre_affinity.get(g, 0) for g in (14, 878))
                            else:
                                mapped_affinity.append(genre_affinity.get(genre_id, 0))
                        taste = sum(mapped_affinity) / max(len(mapped_affinity), 1)
                    else:
                        taste = 0.2
                    # Blend personal genre affinity with a Bayesian quality score.
                    score = 0.72 * _haunted_title_quality(item) + 0.28 * max(0, min(1, (taste + 1) / 2))
                    item["match"] = round(score * 100)
                    item["year"] = (item.get("release_date") or "")[:4]
                    item["genre_names"] = [GENRE_NAMES.get(g, "Genre") for g in genre_ids]
                    picks.append(item)

        picks.sort(key=lambda item: (item["match"], item.get("vote_count", 0)), reverse=True)
        unique = {}
        for item in picks:
            unique[(item["media_type"], item["id"])] = item
        picks = list(unique.values())[:5]
        return render_template("haunted.html", stage="results", picks=picks)

    return redirect("/haunted")
