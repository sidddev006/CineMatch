# 🎬 CineMatch - Smart Movie Recommendation System

[![CS50x 2025](https://img.shields.io/badge/CS50-Final%20Project-red)](https://cs50.harvard.edu/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)

> Stop scrolling endlessly. Start watching great movies.

**CS50 Final Project** | Built by Siddharth Mishra


---

## 🎯 The Problem

In the age of unlimited streaming, finding the perfect movie has become paradoxically harder. Users spend more time browsing than watching, overwhelmed by:
- Generic "Top 10" lists that favor blockbusters
- Pure rating systems that mislead (50 perfect reviews vs. 50,000 reviews)
- Endless scrolling through mediocre options

## 💡 The Solution

CineMatch uses a **weighted rating algorithm** to recommend genuinely exceptional films by balancing popularity with critical acclaim. No more decision paralysis—just consistently great recommendations.

---

## ✨ Features

### 🔐 User Authentication
- Secure registration and login
- Password hashing with Werkzeug
- Session-based authentication

### 🎬 Smart Recommendations
- **Weighted Rating Algorithm**: `(v/(v+m)) × R + (m/(v+m)) × C`
  - Filters out ultra-niche content (requires 450+ votes)
  - Balances popularity with quality
  - Allows hidden gems to compete with blockbusters
- **Customizable Filters**:
  - Genre (Action, Comedy, Drama, etc.)
  - Decade (1950s-2020s)
  - Runtime (under 90, 120, 150+ minutes)
- **Default Mode**: Leave filters blank for best overall recommendations

### 📋 Personal Watchlist
- Save movies you want to watch
- One-click add/remove
- Persistent across sessions
- State preservation (filters remain after adding movies)

### 🎨 Modern UI Design
- **Hybrid CSS approach**: Bootstrap for layout + Tailwind CSS for utility styling
- Responsive design across all devices
- Clean tabular results view
- Real-time watchlist status indicators

---

## 🛠️ Technology Stack

| Category | Technology |
|----------|-----------|
| **Backend** | Flask (Python) |
| **Database** | SQLite with CS50 SQL library |
| **API** | The Movie Database (TMDB) |
| **Authentication** | Werkzeug security |
| **Frontend** | Jinja2 templates, Bootstrap 5, Tailwind CSS (CDN) |
| **Session Management** | Flask-Session |
| **HTTP Requests** | Python Requests library |

---

## 📊 The Algorithm Explained

### Weighted Rating Formula
```python
weighted_rating = (v/(v+m)) × R + (m/(v+m)) × C
```

**Where:**
- `v` = number of votes for the movie
- `R` = average rating of the movie
- `m` = minimum votes threshold (500)
- `C` = baseline quality score (8.0)

### Why These Values?

**`vote_count.gte: 450`** → Filters out extremely niche content  
**`m = 500`** → Creates a "credibility gate" for validation  
**`C = 8.0`** → Helps hidden gems compete with blockbusters  
**`sort_by: vote_average.desc`** → Prevents low-quality high-vote films from dominating

### Example
- **Hidden Gem**: 600 votes, 9.5 rating → Can outrank blockbusters
- **Blockbuster**: 50,000 votes, 8.2 rating → Still ranks highly but fairly
- **Niche Film**: 100 votes, 10.0 rating → Filtered out (insufficient validation)

This balance prevented edge cases like a film titled "Nude" with suspiciously high ratings but minimal votes from appearing in recommendations.

---

## 📁 Project Structure
```
cinematch/
│
├── app.py                 # Main Flask application
├── project.db            # SQLite database
├── requirements.txt      # Python dependencies
├── README.md            # This file
│
├── templates/
│   ├── layout.html      # Base template with Bootstrap + Tailwind
│   ├── index.html       # Landing page
│   ├── register.html    # Registration form
│   ├── login.html       # Login form
│   ├── home.html        # User dashboard
│   ├── recommend.html   # Recommendation filters
│   ├── movies.html      # Results display
│   └── watchlist.html   # Saved movies
│
└── flask_session/       # Session storage (auto-generated)
```

---

## 🗄️ Database Schema
```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL
);

-- Watchlist table
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Ratings table (reserved for future features)
CREATE TABLE ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rating INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 🚀 How to Run

### Prerequisites
- Python 3.8+
- TMDB API key (free from [themoviedb.org](https://www.themoviedb.org/settings/api))

### Installation

1. **Clone the repository**
```bash
   git clone https://github.com/sidddev006/cinematch.git
   cd cinematch
```

2. **Install dependencies**
```bash
   pip install -r requirements.txt
```

3. **Set your TMDB API key**
   
   Open `app.py` and replace on line 26:
```python
   TMDB_API_KEY = "YOUR_API_KEY_HERE"
```

4. **Note on Frontend Styling**
   
   This project uses:
   - **Bootstrap 5** for responsive grid layout and components
   - **Tailwind CSS** (via CDN) for utility-first styling
   
   No additional CSS setup required - both are loaded via CDN in `layout.html`.

5. **Run the application**
```bash
   flask run
```

6. **Open in browser**
```
   http://localhost:5000
```

---

## 🎬 User Journey

1. **Register/Login** → Create account with secure password hashing
2. **Home Dashboard** → Choose to get recommendations or view watchlist
3. **Set Filters** → Select genre, decade, runtime (or leave blank for top picks)
4. **View Results** → See top 10 movies with weighted ratings, posters, details
5. **Add to Watchlist** → Save interesting movies (filters preserved after adding)
6. **Manage Watchlist** → View saved movies, remove when watched
7. **Logout** → Secure session clearing

---

## 🧠 Technical Challenges Solved

### 1. **Filter State Preservation**
**Problem**: After adding a movie to watchlist, users were redirected to an empty form, losing all filter selections.

**Solution**: Implemented hidden form fields that pass search parameters, then used `urlencode` to build dynamic redirect URLs with GET parameters. The `/recommend` route handles both POST (initial search) and GET-with-params (returning from watchlist addition).

### 2. **Dual API Requests**
**Problem**: TMDB's `/discover/movie` endpoint doesn't include runtime data.

**Solution**: Make initial discovery calls, then individual `/movie/{id}` requests for each top result to fetch runtime. Implemented error handling for failed requests.

### 3. **Algorithm Tuning**
**Problem**: Finding the right balance between popularity and quality.

**Solution**: Tested various threshold values. Settled on `m=500, C=8.0, vote_count.gte=450` after discovering edge cases like ultra-niche films with perfect ratings but only 20 votes.

### 4. **Watchlist Status Display**
**Problem**: Efficiently checking which movies are already in watchlist.

**Solution**: Pre-fetch all watchlist movie IDs into a Python set, then use set membership testing (`movie_id in watchlist_ids`) for O(1) lookup time.

---

## 📚 What I Learned

### Technical Skills
- Building full-stack web applications with Flask
- RESTful API integration and error handling
- Database design and SQL queries
- Session management and authentication
- Algorithm design and parameter tuning
- URL parameter handling and state management

### Problem-Solving
- Debugging complex user flow issues
- Balancing performance with functionality
- Handling API rate limits
- Managing state across multiple routes

### Design Thinking
- Understanding user pain points
- Translating algorithms into user value
- Creating intuitive navigation flows
- Balancing simplicity with features

---

## 🔮 Future Enhancements

- [ ] **User Ratings**: Implement the `ratings` table for personal movie ratings
- [ ] **Social Features**: Share watchlists with friends
- [ ] **Advanced Filters**: Director, actor, MPAA rating, streaming platform
- [ ] **Recommendation Engine**: Machine learning based on user preferences
- [ ] **Movie Details Page**: Dedicated page with trailers, cast, reviews
- [ ] **Dark Mode**: Toggle theme preference
- [ ] **Export Watchlist**: Download as PDF or CSV

---

## 💭 Development Notes

This project was built as part of CS50 with assistance from AI tools for:
- CSS styling and layout implementation (Tailwind CSS utilities)
- Debugging complex routing issues
- Understanding Flask best practices

The core algorithm, database design, and application logic were designed and implemented independently.

---

## 🙏 Acknowledgments

- **CS50 Staff** for an incredible course that made this possible
- **TMDB** for their comprehensive movie database API
- **Bootstrap & Tailwind CSS** for the responsive UI frameworks
- **Flask** community for excellent documentation
- **AI assistance** for frontend styling and debugging support

---

## 📄 License

This project was created for educational purposes as part of Harvard's CS50x course.

---

## 👤 Author

**Siddharth Mishra**  
CS50x 2025 | [GitHub: @sidddev006](https://github.com/sidddev006)

---

## 📬 Contact

Questions or feedback? Feel free to reach out via GitHub!

---

**This was CineMatch. Stop scrolling. Start watching.** 🎬
```

