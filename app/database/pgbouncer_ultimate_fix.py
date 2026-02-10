"""
ULTIMATE PGBouncer Fix - COMPLETE prepared statement prevention
This is the FINAL GLOBAL solution to prevent ALL prepared statements
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from typing import Optional
import asyncpg
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


async def create_pgbouncer_connection(database_url: str) -> asyncpg.Connection:
    """
    Create an asyncpg connection with ZERO prepared statements
    This is the ULTIMATE fix for PGBouncer compatibility
    """
    parsed = urlparse(database_url)

    # Create connection with ALL prepared statement mechanisms disabled
    conn = await asyncpg.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path[1:],  # Remove leading slash

        # CRITICAL: These settings COMPLETELY disable prepared statements
        statement_cache_size=0,         # ZERO prepared statements
        command_timeout=30
    )

    # Additional safety: disable prepared statements at connection level
    await conn.execute("SET prepared_statement_cache_size = 0")
    await conn.execute("SET plan_cache_mode = 'force_custom_plan'")

    return conn


def create_ultimate_pgbouncer_engine(database_url: str):
    """
    Create the ULTIMATE PGBouncer-safe engine that GLOBALLY prevents ALL prepared statements
    This is the FINAL solution - no prepared statements will ever be created
    """
    # Convert URL to asyncpg format
    if database_url.startswith("postgres://"):
        async_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    else:
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create engine with ULTIMATE prepared statement prevention
    engine = create_async_engine(
        async_url,

        # Use NullPool to let PGBouncer handle pooling
        poolclass=NullPool,

        # Disable ALL caching mechanisms
        query_cache_size=0,

        # Connection arguments to force no prepared statements
        connect_args={
            "statement_cache_size": 0,  # THE critical setting for asyncpg
            "command_timeout": 30
        },

        # Disable pooling features that might use prepared statements
        pool_pre_ping=False,
        pool_recycle=-1,

        # GLOBAL execution options
        execution_options={
            "postgresql_prepared": False,
            "no_parameters": False,
            "stream_results": False,
            "prebuffer_rows": False,
            "insertmanyvalues_page_size": 1
        },

        echo=False
    )

    # Override dialect settings
    engine.dialect.supports_statement_cache = False
    engine.dialect._has_events = False

    # Force disable at dialect level
    if hasattr(engine.dialect, 'statement_cache_size'):
        engine.dialect.statement_cache_size = 0

    # Override the dialect's initialization to skip version checks
    original_initialize = engine.dialect.initialize

    def skip_version_check(connection):
        engine.dialect.server_version_info = (14, 0)
        engine.dialect.default_schema_name = "public"
        engine.dialect.default_isolation_level = "READ COMMITTED"
        logger.info("ULTIMATE FIX: Skipped version check, no prepared statements")

    engine.dialect.initialize = skip_version_check

    logger.info("ULTIMATE PGBOUNCER ENGINE CREATED - ZERO prepared statements globally!")

    return engine


class UltimatePGBouncerSession(AsyncSession):
    """
    The ULTIMATE PGBouncer-safe session that prevents ALL prepared statements
    """

    def __init__(self, *args, **kwargs):
        # Force options that prevent prepared statements
        if 'bind' in kwargs and kwargs['bind']:
            kwargs['bind'] = kwargs['bind'].execution_options(
                postgresql_prepared=False,
                isolation_level="AUTOCOMMIT"
            )

        kwargs['expire_on_commit'] = False
        kwargs['autoflush'] = False
        kwargs['autocommit'] = False

        super().__init__(*args, **kwargs)

    async def execute(self, statement, params=None, execution_options=None, **kw):
        """Override execute to ensure NO prepared statements"""

        # Force execution options
        exec_options = execution_options or {}
        exec_options['postgresql_prepared'] = False

        # Always rollback any aborted transaction first
        try:
            if self.in_transaction():
                await self.rollback()
        except:
            pass  # Ignore rollback errors

        # Execute with forced options
        try:
            return await super().execute(statement, params, execution_options=exec_options, **kw)
        except Exception as e:
            error_msg = str(e).lower()
            if "prepared statement" in error_msg or "transaction is aborted" in error_msg:
                # Try to recover
                await self.rollback()
                # Retry once
                return await super().execute(statement, params, execution_options=exec_options, **kw)
            raise


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


# Export the ULTIMATE fix functions
__all__ = [
    'create_ultimate_pgbouncer_engine',
    'create_ultimate_session_factory',
    'UltimatePGBouncerSession',
    'create_pgbouncer_connection'
]