import time  # This was just in case I had to delay API requests
# Importing libraries
import requests
from urllib.parse import urlencode
# I copied this part from problem set 9 Finance
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# This part is there to ensure that the user logins before directly accessing some routes
# I copied this from problem set 9 Finance


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


# Creating the app variable
app = Flask(__name__)

# Executing the database that I have created for this project
db = SQL("sqlite:///project.db")

TMDB_API_KEY = "4e4a70b35de6e22f19ede8cb6c7b18d7"
# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# This is the home/index route


@app.route("/")
def index():
    return render_template("index.html")

# This is the register route where a new user can register


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            flash("invalid username")
            return render_template("register.html")
        users = db.execute("SELECT * FROM users WHERE username = ?", username)
        if users:
            flash("username already exists")
            return render_template("register.html")

        password = request.form.get("password")
        pass_confirm = request.form.get("pass_confirm")
        if password != pass_confirm:
            flash("both passwords should be same")
            return render_template("register.html")

        pass_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash)  VALUES(?,?)", username, pass_hash)
        rows = db.execute("SELECT id FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]
        return redirect("/home")
    return render_template("register.html")

# This is the login route where can the user can login if they have already made their account


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            flash("username required")
            return render_template("login.html")
        users = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(users) == 0:
            flash("username not found , try entering correct username try registering again")
            return render_template("login.html")
        password = request.form.get("password")
        if not check_password_hash(users[0]["hash"], password):
            flash("wrong password , please try again !")
            return render_template("login.html")
        session["user_id"] = users[0]["id"]
        return redirect("/home")  # It redirects to "/home" route
    return render_template("login.html")

# This is the home route


@app.route("/home")
@login_required
def home():
    id = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = ?", id)
    username = username[0]["username"]
    return render_template("home.html", username=username)

# This is the main algorithm on which my whole project is based on


def calculate_weighted_rating(vote_count, vote_average, m=500, c=8.0):
    return (vote_count/(vote_count + m)) * vote_average + (m/(vote_count + m)) * c


# Making an dictionary of genres
genres = [{"id": 28, "name": "Action"}, {"id": 12, "name": "Adventure"},
          {"id": 16, "name": "Animation"}, {"id": 35, "name": "Comedy"},
          {"id": 80, "name": "Crime"}, {"id": 99, "name": "Documentary"},
          {"id": 18, "name": "Drama"}, {"id": 10751, "name": "Family"},
          {"id": 14, "name": "Fantasy"}, {"id": 36, "name": "History"},
          {"id": 27, "name": "Horror"}, {"id": 10402, "name": "Music"},
          {"id": 9648, "name": "Mystery"}, {"id": 10749, "name": "Romance"},
          {"id": 878, "name": "Science Fiction"}, {"id": 10770, "name": "TV Movie"},
          {"id": 53, "name": "Thriller"}, {"id": 10752, "name": "War"},
          {"id": 37, "name": "Western"}]

# This the main route of my project


@app.route("/recommend", methods=["GET", "POST"])
@login_required
def recommend():

    # Initialize variables
    genre = None
    runtime = None
    decade = None

    # In this I am accomodating for both the type of requests be it GET or POST
    # I have done this to ensure that after adding a movie to the watchlist the
    # user can be redirected back to the movies.html page with all their filters intact
    # This was a bit of hassle

    if request.method == "POST":
        # If data submitted via the form (POST request)
        genre = request.form.get("genre")
        runtime = request.form.get("runtime")
        decade = request.form.get("decade")

    elif request.args.get("genre") or request.args.get("runtime") or request.args.get("decade"):
        # If data submitted via URL parameters (GET request with filters)
        genre = request.args.get("genre")
        runtime = request.args.get("runtime")
        decade = request.args.get("decade")

    else:
        # This is the initial GET request where the user can submit their recommendations
        user_id = session.get("user_id")
        username = db.execute("SELECT username FROM users WHERE id = ?", user_id)[0]["username"]
        return render_template("recommend.html", genres=genres, username=username)

    # SEARCH AND API LOGIC (Runs for both POST and GET-with-params)

    base_url = "https://api.themoviedb.org/3/discover/movie"
    recommend_movies = []  # -> I am declaring an empty dictionary which can contain the filtered movies data

    # Build base query parameters
    params = {
        "api_key": TMDB_API_KEY,
        "vote_count.gte": 450,
        "sort_by": "vote_average.desc",
        "include_adult": "true"
    }

    # This all filters are optional
    if genre:
        params["with_genres"] = genre
    if runtime:
        params["with_runtime.lte"] = runtime
    if decade:
        start_time = f"{decade[:3]}0-01-01"
        end_time = f"{decade[:3]}9-12-31"
        params["primary_release_date.gte"] = start_time
        params["primary_release_date.lte"] = end_time

    # Loop through pages -> I am running thorough 3 pages only as in it can get all the movies which have to appear
    for page in range(1, 3):
        params["page"] = page
        response = requests.get(base_url, params=params)

        # Safety check for bad responses -> This is to check in any case the API call fails
        if response.status_code != 200:
            continue

        data = response.json()

        # Defensive check
        if "results" not in data:
            continue

        for movie in data["results"]:
            vote_count = movie.get("vote_count", 0)
            vote_average = movie.get("vote_average", 0)
            weighted_rating = calculate_weighted_rating(vote_count, vote_average)

            # Filter out low-rated ones early
            if weighted_rating < 7.0:
                continue

            # Adding all the selected movies data to the dictionary that I created earlier
            recommend_movies.append({
                "id": movie.get("id"),
                "title": movie.get("title", "Unknown Title"),
                "overview": movie.get("overview", "No description available."),
                "poster_path": movie.get("poster_path"),
                "weighted_rating": weighted_rating,
                "release_date": movie.get("release_date", "N/A")
            })

    # FINAL PROCESSING AND RENDERING

    # Sort movies by computed weighted rating
    recommend_movies.sort(key=lambda x: x["weighted_rating"], reverse=True)

    # Limit to top 10 and fetch runtime details as anything greater than this than my code will run horribly slow
    top_movies = recommend_movies[:10]
    detail_url = "https://api.themoviedb.org/3/movie"

    # Pre-fetch watchlist IDs for template check (to check whether a movie is already in watchlist)
    user_id = session["user_id"]
    watchlist_movie_ids = db.execute("SELECT movie_id FROM watchlist WHERE user_id =?", user_id)
    watchlist_ids = {row["movie_id"] for row in watchlist_movie_ids}

    # This is done as the TMDB calls doesnot include movie's runtime among all the thing that it gives
    # so I had to do API call again
    for movie in top_movies:
        try:
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
            movie["runtime"] = "N/A"

        # Check if movie is already in user's watchlist
        movie["in_watchlist"] = movie["id"] in watchlist_ids

    # Passing the templates with all the selected in the movies.html
    return render_template("movies.html", movies=top_movies, genre=genre, decade=decade, runtime=runtime)


# This part is to add a movie to the watchlist and display Movie already in watchlist if movie already exists in the watchlist
@app.route("/add_to_watchlist", methods=["POST"])
@login_required
def add_to_watchlist():
    movie_id = request.form.get("movie_id")
    runtime = request.form.get("runtime")
    genre = request.form.get("genre")
    decade = request.form.get("decade")
    user_id = session["user_id"]

    # Check if movie already exists
    movie = db.execute(
        "SELECT * FROM watchlist WHERE movie_id = ? AND user_id = ?", movie_id, user_id
    )

    if not movie:
        db.execute("INSERT INTO watchlist (movie_id, user_id) VALUES (?, ?)", movie_id, user_id)

    # Preserve filters when redirecting back
    query_params = {}
    if genre:
        query_params["genre"] = genre
    if runtime:
        query_params["runtime"] = runtime
    if decade:
        query_params["decade"] = decade

    # Build redirect URL dynamically
    if query_params:
        redirect_url = f"/recommend?{urlencode(query_params)}"
    else:
        redirect_url = "/recommend"

    return redirect(redirect_url)


# This is the route where the user can see all the movies they have to their watchlist
@app.route("/watchlist", methods=["GET", "POST"])
@login_required
def watchlist():
    user_id = session["user_id"]
    watchlist_items = db.execute("SELECT movie_id FROM watchlist WHERE user_id = ?", user_id)

    movies = []
    # I am calling API again as I was not saving the movies data locally
    for item in watchlist_items:
        movie_id = item["movie_id"]
        base_url = f"https://api.themoviedb.org/3/movie/{movie_id}"

        # Part of calling the API
        response = requests.get(base_url, params={"api_key": TMDB_API_KEY})
        if response.status_code == 200:  # This is done to ensure that if API call succeeds than execute the under code
            movie_data = response.json()

            movies.append({
                "id": movie_id,
                "title": movie_data.get("title", "Unknown Title"),
                "overview": movie_data.get("overview", "No description available."),
                "poster_path": movie_data.get("poster_path"),
                "release_date": movie_data.get("release_date", "N/A"),
                "runtime": movie_data.get("runtime")
            })

    return render_template("watchlist.html", movies=movies)

# This is the route to remove a movie from the watchlist


@app.route("/remove_from_watchlist", methods=["GET", "POST"])
@login_required
def remove_from_watchlist():
    movie_id = request.form.get("movie_id")
    user_id = session["user_id"]
    db.execute("DELETE FROM watchlist WHERE user_id = ? AND movie_id = ?", user_id, movie_id)
    return redirect("/watchlist")

# Route to logout


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect("/")
