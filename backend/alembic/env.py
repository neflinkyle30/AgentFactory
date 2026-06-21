"""Alembic environment configuration for Agent Factory.

Sets up async migrations using SQLAlchemy 2.0 and the project's
Settings class for database URL resolution.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Import our models and config
from app.config import settings
from app.models import Base  # noqa: F401 — registers all models on Base.metadata

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata

# Resolve the database URL from application config
DATABASE_URL = settings.resolved_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with a URL only — no engine needed.
    Useful for generating SQL scripts without a live database.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """Execute migrations within a transaction."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine.

    Creates an async engine from the resolved database URL
    and runs all pending migrations.
    """
    connectable = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
