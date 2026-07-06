"""
MemorAI — FastAPI application entry point.
Turn any PDF into a smart study deck powered by AI and spaced repetition.
"""

from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

from routers import auth, ingest, decks, study, review, stats, schedule, calendar, tutor
from services.auth import UnauthenticatedException, get_current_user_page, get_current_user_optional
from models.models import User

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="MemorAI",
    description="Turn any PDF into a smart study deck powered by AI and spaced repetition.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler to redirect unauthenticated page requests to login
@app.exception_handler(UnauthenticatedException)
async def unauthenticated_exception_handler(request: Request, exc: UnauthenticatedException):
    return RedirectResponse(url="/login")

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Include API routers
app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(decks.router)
app.include_router(study.router)
app.include_router(review.router)
app.include_router(stats.router)
app.include_router(schedule.router)
app.include_router(calendar.router)
app.include_router(tutor.router)


# ── Page Routes ───────────────────────────────────────────────────────────────

@app.get("/login", include_in_schema=False)
async def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
):
    """Render login page. Redirect to home if already logged in."""
    if current_user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, "login.html")


@app.get("/signup", include_in_schema=False)
async def signup_page(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
):
    """Render signup page. Redirect to home if already logged in."""
    if current_user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, "signup.html")


@app.get("/", include_in_schema=False)
async def home(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
):
    """Home landing page (guest) or upload screen (auth)."""
    if current_user:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"user": current_user},
        )
    return templates.TemplateResponse(request, "landing.html")


@app.get("/decks", include_in_schema=False)
async def decks_page(
    request: Request,
    current_user: User = Depends(get_current_user_page),
):
    """Decks listing screen — requires login."""
    return templates.TemplateResponse(
        request,
        "decks.html",
        {"user": current_user},
    )


@app.get("/decks/{deck_id}", include_in_schema=False)
async def deck_detail_page(
    request: Request,
    deck_id: str,
    current_user: User = Depends(get_current_user_page),
):
    """Deck detail & stats screen — requires login."""
    return templates.TemplateResponse(
        request,
        "deck_detail.html",
        {"deck_id": deck_id, "user": current_user},
    )


@app.get("/decks/{deck_id}/study", include_in_schema=False)
async def study_page(
    request: Request,
    deck_id: str,
    current_user: User = Depends(get_current_user_page),
):
    """Study session player — requires login."""
    return templates.TemplateResponse(
        request,
        "study.html",
        {"deck_id": deck_id, "user": current_user},
    )


@app.get("/calendar", include_in_schema=False)
async def calendar_page(
    request: Request,
    current_user: User = Depends(get_current_user_page),
):
    """Heatmap calendar view — requires login."""
    return templates.TemplateResponse(
        request,
        "calendar.html",
        {"user": current_user},
    )


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user_page),
):
    """Global Auth Dashboard — requires login."""
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": current_user},
    )
