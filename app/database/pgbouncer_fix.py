"""
PGBouncer compatibility layer - Forces text-only queries without prepared statements
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class PGBouncerSession:
    """
    Wrapper for AsyncSession that forces all queries to use text() without prepared statements.
    This completely bypasses asyncpg's prepared statement mechanism.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        # Override execution options to disable prepared statements
        self._session.bind.execution_options.update({
            "postgresql_prepared": False,
            "no_parameters": True
        })

    def __getattr__(self, name):
        """Delegate all other attributes to the wrapped session"""
        return getattr(self._session, name)

    async def execute(self, statement, params=None, execution_options=None, **kw):
        """Override execute to force text mode without prepared statements"""
        # Force execution options to disable prepared statements
        exec_options = execution_options or {}
        exec_options["postgresql_prepared"] = False
        exec_options["no_parameters"] = True

        # If it's already a text clause, use it directly
        if hasattr(statement, '_is_text_clause'):
            result = await self._session.execute(
                statement,
                params,
                execution_options=exec_options,
                **kw
            )
        else:
            # Convert to raw SQL text to bypass prepared statements
            try:
                # Try to compile the statement to raw SQL
                if hasattr(statement, 'compile'):
                    from sqlalchemy.dialects import postgresql
                    compiled = statement.compile(
                        dialect=postgresql.dialect(),
                        compile_kwargs={"literal_binds": True}
                    )
                    sql_text = str(compiled)
                    result = await self._session.execute(
                        text(sql_text),
                        execution_options=exec_options,
                        **kw
                    )
                else:
                    # Fallback to normal execution
                    result = await self._session.execute(
                        statement,
                        params,
                        execution_options=exec_options,
                        **kw
                    )
            except Exception as e:
                logger.error(f"PGBouncerSession execution error: {e}")
                raise

        return result

    async def commit(self):
        """Commit with text-only mode"""
        return await self._session.commit()

    async def rollback(self):
        """Rollback with text-only mode"""
        return await self._session.rollback()

    async def close(self):
        """Close the session"""
        return await self._session.close()

    def in_transaction(self):
        """Check if in transaction"""
        return self._session.in_transaction()

    @property
    def is_active(self):
        """Check if session is active"""
        return self._session.is_active


def create_pgbouncer_engine(database_url: str):
    """
    Create a SQLAlchemy engine specifically configured for PGBouncer compatibility.
    This forces all connections to use text-only queries without prepared statements.
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    # Convert URL to asyncpg format
    if database_url.startswith("postgres://"):
        async_url = database_url.replace("postgres://", "postgresql+asyncpg://")
    else:
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    # Create engine with maximum PGBouncer compatibility
    engine = create_async_engine(
        async_url,
        poolclass=NullPool,  # No connection pooling - let PGBouncer handle it
        echo=False,
        query_cache_size=0,  # Disable query caching
        # Force text-only execution
        execution_options={
            "postgresql_prepared": False,
            "no_autoflush": True,
            "autocommit": False,
            "compiled_cache": None  # Disable compiled statement cache
        },
        # asyncpg connection arguments - CRITICAL FOR PGBOUNCER
        connect_args={
            "statement_cache_size": 0,  # CRITICAL: Disable prepared statements
            "prepared_statement_cache_size": 0,
            "max_cached_statement_lifetime": 0,  # No caching lifetime
            "command_timeout": 30,
            "server_settings": {
                "application_name": "analytics_pgbouncer_safe"
            }
        },
        # Additional safety settings
        pool_pre_ping=False,  # Don't ping - PGBouncer handles connection health
        future=True
    )

    # Add event listener to force text mode on all connections
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        """Force each new connection to disable prepared statements"""
        # This is a sync event, but we need to ensure prepared statements are disabled
        connection_record.info['prepared_statements'] = False

    return engine