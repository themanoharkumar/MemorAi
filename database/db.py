"""
SQLAlchemy async engine and session factory for MemorAI.
Engine is created lazily on first use.
"""

import os
import re
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()


class Base(DeclarativeBase):
    pass


def _build_engine_url(database_url: str) -> str:
    """Convert standard postgresql:// URL to asyncpg-compatible format."""
    if database_url.startswith("postgresql://"):
        url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        url = database_url
    # Remove sslmode param from URL — asyncpg uses connect_args
    url = re.sub(r'[?&]sslmode=[^&]*', '', url)
    return url


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def _get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set. Please create a .env file based on .env.example.")

    async_url = _build_engine_url(database_url)
    uses_ssl = any(host in database_url for host in ("neon", "supabase", "amazonaws", ".cloud"))

    _engine = create_async_engine(
        async_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"ssl": "require"} if uses_ssl else {},
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    return _engine


def _get_session_factory() -> async_sessionmaker:
    _get_engine()  # ensures factory is initialized
    return _session_factory


class AsyncSessionLocal:
    """Context manager wrapper that creates sessions from the lazy factory."""
    def __call__(self):
        return _get_session_factory()()

    def __call_context__(self):
        return _get_session_factory()()


def get_async_session() -> AsyncSession:
    """Create and return a new async session."""
    return _get_session_factory()()


class _AsyncSessionContextManager:
    def __init__(self):
        self._session = None

    async def __aenter__(self) -> AsyncSession:
        self._session = _get_session_factory()()
        return self._session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()


def AsyncSessionLocal() -> _AsyncSessionContextManager:
    """Use as: async with AsyncSessionLocal() as db: ..."""
    return _AsyncSessionContextManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with _AsyncSessionContextManager() as session:
        try:
            yield session
        finally:
            pass  # __aexit__ already closes
