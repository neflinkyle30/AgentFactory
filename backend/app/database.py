"""Database connection and session management.

Provides async SQLAlchemy engine, session factory, and FastAPI dependency
injection. Supports PostgreSQL (via asyncpg) and SQLite (via aiosqlite)
for development mode.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# ── Engine ──────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.resolved_database_url,
    echo=False,  # Set to True for SQL debug logging
    future=True,
)

# ── Session Factory ─────────────────────────────────────────────────

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI Dependency ──────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    Usage in route handlers:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """Get a database session for use outside of FastAPI dependency injection.

    The caller is responsible for closing the session.

    Usage:
        async with get_db_session() as session:
            ...
    """
    return async_session_factory()
