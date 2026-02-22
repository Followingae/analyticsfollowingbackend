"""
Database engine with unnamed-prepared-statement safety.
pgbouncer_absolute_fix (imported first in connection.py) monkey-patches asyncpg
to force unnamed prepared statements, so this module only needs to configure
SQLAlchemy pooling and dialect settings.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)


def create_ultimate_pgbouncer_engine(database_url: str):
    """
    Create a pooler-safe async engine.

    Uses QueuePool (app-side connection reuse) since we connect via port 5432
    (Supabase direct / session-mode pooler).  The pgbouncer_absolute_fix
    monkey-patch guarantees every asyncpg prepared statement is UNNAMED,
    so no DuplicatePreparedStatementError can occur regardless of pool mode.
    """
    # Convert URL to asyncpg format
    if database_url.startswith("postgres://"):
        async_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    else:
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(
        async_url,

        # QueuePool: reuse connections app-side.  The unnamed-stmt patch
        # makes this fully safe even with external poolers.
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=10,
        pool_timeout=10,
        pool_recycle=3600,       # recycle connections every hour
        pool_pre_ping=True,      # validate connections before use

        query_cache_size=0,

        connect_args={
            "statement_cache_size": 0,
            "command_timeout": 30,
        },

        execution_options={
            "postgresql_prepared": False,
        },

        echo=False,
    )

    # Disable dialect-level statement caching
    engine.dialect.supports_statement_cache = False
    if hasattr(engine.dialect, "statement_cache_size"):
        engine.dialect.statement_cache_size = 0

    logger.info("Database engine created (QueuePool, unnamed prepared statements)")
    return engine


class UltimatePGBouncerSession(AsyncSession):
    """
    PGBouncer-safe session. Prepared statement prevention is handled
    globally by pgbouncer_absolute_fix (unnamed statements patch).
    This session just sets expire_on_commit=False for ORM convenience.
    """

    def __init__(self, *args, **kwargs):
        kwargs['expire_on_commit'] = False
        kwargs['autoflush'] = False
        kwargs['autocommit'] = False
        super().__init__(*args, **kwargs)


def create_ultimate_session_factory(engine):
    """
    Create the ULTIMATE session factory with ZERO prepared statements
    """
    return sessionmaker(
        bind=engine,
        class_=UltimatePGBouncerSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
    )


__all__ = [
    'create_ultimate_pgbouncer_engine',
    'create_ultimate_session_factory',
    'UltimatePGBouncerSession',
]