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