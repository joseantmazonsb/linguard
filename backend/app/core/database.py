from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from .config_loader import config_loader

# Base class for models — available at import time, does not touch the filesystem
Base = declarative_base()

# Engine and session factory start as None.
# They are initialised by init_engine() (called from the lifespan on an existing install)
# or by reinit_engine() (called from the configure_database setup endpoint on a fresh install).
engine = None
AsyncSessionLocal = None


def _build_engine(database_url: str):
    """Create an AsyncEngine for *database_url* with appropriate settings."""
    eng = create_async_engine(
        database_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )

    # SQLite: enable foreign keys on every new connection
    if database_url.startswith("sqlite"):
        @event.listens_for(eng.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return eng


def init_engine():
    """
    Initialise the engine from the saved config file.

    Called at lifespan startup when linguard.config.json already exists
    (i.e. the user has previously completed the database setup step).
    Raises RuntimeError if the config file does not exist yet.
    """
    global engine, AsyncSessionLocal

    if not config_loader.exists():
        raise RuntimeError(
            "linguard.config.json does not exist — cannot initialise the database engine. "
            "The setup wizard must complete the database step first."
        )

    database_url = config_loader.get_database_url()
    engine = _build_engine(database_url)
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def reinit_engine(database_url: str):
    """
    Tear down any existing engine and create a new one pointing at *database_url*.

    Called from the configure_database setup endpoint after the user has chosen
    their database backend and the config file has been written.
    """
    global engine, AsyncSessionLocal

    if engine is not None:
        # Schedule disposal — fire-and-forget at the sync level; the caller is
        # responsible for not using the old engine after this point.
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(engine.dispose())
            else:
                loop.run_until_complete(engine.dispose())
        except Exception:
            pass  # best-effort cleanup

    engine = _build_engine(database_url)
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Dependency for getting a DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database engine has not been initialised. "
            "Complete the setup wizard database step first."
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables. Requires the engine to have been initialised first."""
    if engine is None:
        raise RuntimeError("Database engine has not been initialised.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
