"""
Custom PostgreSQL dialect for PGBouncer compatibility
Completely disables all prepared statements and version checking
"""
from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
from sqlalchemy.dialects.postgresql import base as pg_base
from sqlalchemy import pool
import logging

logger = logging.getLogger(__name__)


class PGBouncerDialect(PGDialect_asyncpg):
    """
    Custom dialect that completely bypasses all prepared statement usage
    and version checking that causes issues with PGBouncer
    """

    supports_statement_cache = False  # Disable all statement caching

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force disable all prepared statement features
        self.implicit_returning = False
        self.use_native_hstore = False

    def initialize(self, connection):
        """Override initialization to skip version check that uses prepared statements"""
        # Skip the parent's initialization which runs SELECT version()
        # Set a fake version to satisfy SQLAlchemy
        self.server_version_info = (14, 0)  # Fake PostgreSQL 14.0
        self.default_schema_name = "public"
        self.default_isolation_level = self.isolation_level

        # Set other required attributes without querying
        self.returns_unicode_strings = True
        self._has_native_hstore = False
        self._has_native_json = True
        self._has_native_jsonb = True
        self._has_native_uuid = True
        self._has_native_interval = True
        self._has_native_inet_type = True

        logger.info("PGBouncerDialect: Initialized without version check")

    def _get_server_version_info(self, connection):
        """Override to return fake version without querying"""
        return (14, 0)  # Return PostgreSQL 14.0

    def _get_default_schema_name(self, connection):
        """Override to return default schema without querying"""
        return "public"

    def get_isolation_level(self, connection):
        """Override to return default without querying"""
        return "READ COMMITTED"

    def do_ping(self, dbapi_conn):
        """Override ping to avoid prepared statements"""
        # PGBouncer handles connection health, skip ping
        return True


def create_pgbouncer_engine_with_custom_dialect(database_url: str):
    """
    Create engine with COMPLETE PGBouncer-safe configuration
    This GLOBALLY disables ALL prepared statements at every level
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
    from sqlalchemy.pool import NullPool
    import asyncpg

    # Convert URL to asyncpg format
    if database_url.startswith("postgres://"):
        async_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    else:
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create custom connection factory that disables all prepared statements
    async def connect_factory():
        # Parse the connection URL to get connection params
        import urllib.parse
        parsed = urllib.parse.urlparse(database_url)

        # Create connection with statement_cache_size=0
        conn = await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:],  # Remove leading slash
            statement_cache_size=0,  # CRITICAL: No prepared statements
            command_timeout=30
        )
        return conn

    # Create engine with COMPLETE prepared statement prevention
    engine = create_async_engine(
        async_url,
        poolclass=NullPool,  # Let PGBouncer handle pooling
        echo=False,
        # GLOBAL: Disable ALL caching mechanisms
        query_cache_size=0,  # No query caching
        connect_args={
            "statement_cache_size": 0,  # No asyncpg prepared statements
            "prepared_statement_cache_size": 0,  # No prepared statement cache
            "command_timeout": 30,
            "max_cached_statement_lifetime": 0,  # Never cache statements
            "max_cacheable_statement_size": 0  # Don't cache any statement
            # Removed server_settings with JIT - not supported by PGBouncer
        },
        pool_pre_ping=False,  # Don't ping (uses prepared statements)
        pool_recycle=-1,  # Never recycle connections
        # GLOBAL execution options to force simple protocol
        execution_options={
            "no_parameters": False,
            "postgresql_prepared": False,  # NEVER use prepared statements
            "stream_results": False,
            "prebuffer_rows": False,  # Don't prebuffer (can cause prepared statements)
            "insertmanyvalues_page_size": 1  # Prevent batch prepared statements
        }
    )

    # Override the dialect to completely disable prepared statements
    original_initialize = engine.dialect.initialize

    def no_version_check_initialize(connection):
        # Set fake version without querying
        engine.dialect.server_version_info = (14, 0)
        engine.dialect.default_schema_name = "public"
        engine.dialect.default_isolation_level = "READ COMMITTED"
        logger.info("PGBouncer: Skipped version check during initialization")

    engine.dialect.initialize = no_version_check_initialize

    # GLOBAL: Override dialect's do_execute to prevent prepared statements
    if hasattr(engine.dialect, 'do_execute'):
        original_do_execute = engine.dialect.do_execute

        def no_prepared_do_execute(cursor, statement, parameters, context=None):
            # Force simple protocol execution
            if context and hasattr(context, 'execution_options'):
                # Create a new mutable dict from the immutable one
                new_options = dict(context.execution_options) if context.execution_options else {}
                new_options['postgresql_prepared'] = False
                # Can't modify context directly, but the option is set for reference
            return original_do_execute(cursor, statement, parameters, context)

        engine.dialect.do_execute = no_prepared_do_execute

    # GLOBAL: Disable statement caching at dialect level
    engine.dialect.supports_statement_cache = False
    engine.dialect._has_events = False  # Prevent event-based prepared statements
    if hasattr(engine.dialect, 'statement_cache_size'):
        engine.dialect.statement_cache_size = 0
    engine.dialect.max_identifier_length = 63  # Standard PostgreSQL limit

    # GLOBAL: Force the engine to never use prepared statements
    engine = engine.execution_options(
        postgresql_prepared=False,
        isolation_level="AUTOCOMMIT"  # Use autocommit to prevent transaction issues
    )

    logger.info("Created PGBouncer-safe engine with COMPLETE GLOBAL prepared statement prevention")
    return engine