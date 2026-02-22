"""
ABSOLUTE PGBouncer Fix - The FINAL solution
This monkey-patches asyncpg to FORCE unnamed prepared statements,
eliminating DuplicatePreparedStatementError with any connection pooler.

The root cause: asyncpg creates NAMED prepared statements (__asyncpg_stmt_N__)
even with statement_cache_size=0. When a pooler (pgbouncer / Supavisor)
reassigns backend connections, those names collide. The fix is to force
asyncpg to always use UNNAMED prepared statements (empty string name),
which PostgreSQL overwrites automatically on each PARSE — no collision.
"""
import logging
logger = logging.getLogger(__name__)


def apply_absolute_pgbouncer_fix():
    """
    Apply the ABSOLUTE fix by monkey-patching asyncpg internals.
    This GUARANTEES no named prepared statements will ever be created.
    """

    # Step 1: Monkey-patch asyncpg.connect to FORCE statement_cache_size=0
    import asyncpg
    import asyncpg.connection
    original_connect = asyncpg.connect

    async def pgbouncer_safe_connect(*args, **kwargs):
        """FORCED asyncpg.connect with statement_cache_size=0"""
        kwargs['statement_cache_size'] = 0
        kwargs.pop('max_cached_statement_lifetime', None)
        kwargs.pop('max_cacheable_statement_size', None)
        kwargs.pop('prepared_statement_cache_size', None)
        return await original_connect(*args, **kwargs)

    asyncpg.connect = pgbouncer_safe_connect

    # Step 2: Monkey-patch asyncpg Connection._get_statement to force UNNAMED
    # This is the CRITICAL fix. Even with statement_cache_size=0, asyncpg's
    # _get_statement still creates NAMED statements when called via prepare().
    # By forcing named=False and use_cache=False, asyncpg uses the unnamed
    # prepared statement (empty string), which PostgreSQL safely overwrites.
    original_get_statement = asyncpg.connection.Connection._get_statement

    async def _unnamed_get_statement(self, query, timeout, *, named=False, use_cache=True):
        """Force unnamed prepared statements for pooler compatibility"""
        return await original_get_statement(
            self, query, timeout, named=False, use_cache=False
        )

    asyncpg.connection.Connection._get_statement = _unnamed_get_statement

    # Step 3: Monkey-patch SQLAlchemy's asyncpg dialect
    try:
        from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg
        PGDialect_asyncpg.supports_statement_cache = False
        PGDialect_asyncpg.statement_cache_size = 0
    except Exception as e:
        logger.warning(f"Could not patch SQLAlchemy dialect: {e}")

    logger.info("ABSOLUTE PGBOUNCER FIX APPLIED - all prepared statements forced to UNNAMED")

    return True


# Apply the fix immediately when this module is imported
apply_absolute_pgbouncer_fix()
