# MemorAI

**Turn any study material into smart active-recall decks — powered by AI and spaced repetition.**

MemorAI is a modern, high-performance web application designed to optimize learning. Users can upload a study PDF, let the AI processor automatically generate high-retention active-recall cards, and study them using an adaptive spaced repetition schedule based on the SM-2 algorithm.

---

## 🚀 Key Features

- **Automated Card Generation** — Analyzes study documents to extract core concepts, definitions, practical applications, relationship patterns, and edge cases.
- **SM-2 Spaced Repetition** — Adaptive study scheduling using a 4-point rating scale (Again, Hard, Good, Easy) designed to minimize study time and maximize long-term retention.
- **Global Study Dashboard** — A centralized progress center highlighting total cards, global mastery levels, study consistency logs, and active streaks.
- **Spaced Heatmap Calendar** — A visual monthly overview tracking past study activity and forecasting upcoming reviews.
- **Flashcard CRUD Builder** — Create, edit, and delete flashcards manually directly within the deck manager interface.
- **Multi-Tenant User Accounts** — Secured with user registration, secure session authentication, and data isolation so users only access their own decks.

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python 3.10+)
- **Database ORM:** SQLAlchemy 2.0 (Async) + Alembic migrations
- **Database:** PostgreSQL
- **Frontend:** Jinja2 Templates, HTML5 Semantic Elements, Vanilla CSS variables, and Vanilla Javascript
- **AI Processing:** Google Gemini API (`google-genai` SDK)
- **PDF Parser:** PyMuPDF (`fitz`)

---

## 📁 Project Structure

```
memorai/
├── main.py                    # FastAPI application entry point
├── pyproject.toml             # Python package dependencies
├── .env.example               # Environment variables template
├── alembic.ini                # Alembic database migration config
│
├── database/
│   └── db.py                  # Lazy SQLAlchemy async engine + session factory
│
├── models/
│   └── models.py              # SQLAlchemy database ORM schemas
│
├── schemas/
│   └── schemas.py             # Pydantic validation schemas
│
├── services/                  # Core Business Services
│   ├── auth.py                # Hashing, JWT tokens, and auth dependencies
│   ├── gemini.py              # AI content generator
│   ├── pdf_parser.py          # PyMuPDF text & image extractor
│   ├── sm2.py                 # SM-2 spaced repetition scheduler
│   ├── streak.py              # Consecutive day streak calculator
│   └── utils.py               # Formatting helpers
│
├── routers/                   # HTTP Route Endpoints
│   ├── auth.py                # User login, logout, and registration
│   ├── ingest.py              # PDF upload & streaming card generator
│   ├── decks.py               # Deck list & manual card CRUD operations
│   ├── study.py               # Due flashcard player feed
│   ├── review.py              # Rating submission & SM-2 logging
│   ├── stats.py               # Analytical deck & global metrics
│   ├── schedule.py            # 14-day study forecast
│   └── calendar.py            # Heatmap data & day drill-down
│
├── static/                    # Public Static Assets
│   ├── css/
│   │   └── globals.css        # Custom neon-dark theme design tokens
│   └── js/
│       ├── app.js             # API client, toast notifications, navigation
│       ├── upload.js          # File drop zone & streaming upload progress
│       └── flashcard.js       # 3D card flipping & review keyboard controls
│
└── templates/                 # Jinja2 HTML Page Layouts
    ├── base.html              # Core navigation layout
    ├── landing.html           # Guest landing page & interactive preview
    ├── login.html             # User login portal
    ├── signup.html            # User signup portal
    ├── index.html             # App workspace (drop zone + recent decks)
    ├── dashboard.html         # Global stats dashboard
    ├── decks.html             # Deck gallery list
    ├── deck_detail.html       # Card list & manual builder
    └── study.html             # Study player session
```

---

## ⚡ Getting Started

### Prerequisites

- Python 3.10 or higher
- PostgreSQL database instance (local, Supabase, or Neon)
- Google AI Studio API key

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/memorai.git
   cd memorai
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   # OR if using uv:
   uv sync
   ```

3. **Configure environment:**
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   copy .env.example .env
   ```
   *Edit `.env` values:*
   ```env
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.zssvkdsnteceidwnjdsx.supabase.co:5432/postgres
   GEMINI_API_KEY=AIzaSy...
   ```

4. **Initialize database schema:**
   ```bash
   python -m alembic upgrade head
   ```

5. **Start server:**
   ```bash
   python -m uvicorn main:app --reload
   ```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🔑 API Reference

Interactive Swagger documentation is auto-generated and available at **`http://localhost:8000/docs`**.

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | `POST` | Create a new user account |
| `/api/auth/login` | `POST` | Authenticate and set HTTP-only JWT cookie |
| `/api/auth/logout` | `POST` | Clear access session cookie |
| `/api/ingest` | `POST` | Upload PDF and stream NDJSON progress |
| `/api/decks` | `GET` / `DELETE` | Fetch user decks or delete a deck |
| `/api/decks/card` | `POST`/`PUT`/`DELETE` | Manual flashcard CRUD builder |
| `/api/study` | `GET` | Fetch due study cards in a deck |
| `/api/review` | `POST` | Submit review rating (runs SM-2 updates) |
| `/api/stats/global` | `GET` | Overall dashboard metrics |
| `/api/calendar` | `GET` | Monthly heatmap grid states |
