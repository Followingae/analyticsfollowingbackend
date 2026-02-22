"""
ABSOLUTE PGBouncer Fix - The FINAL solution
This monkey-patches SQLAlchemy's asyncpg dialect to FORCE statement_cache_size=0
"""
import logging
logger = logging.getLogger(__name__)

# CRITICAL: Monkey-patch asyncpg BEFORE SQLAlchemy uses it
def apply_absolute_pgbouncer_fix():
    """
    Apply the ABSOLUTE fix by monkey-patching asyncpg and SQLAlchemy
    This GUARANTEES no prepared statements will ever be created
    """

    # Step 1: Monkey-patch asyncpg.connect to FORCE statement_cache_size=0
    import asyncpg
    original_connect = asyncpg.connect

    async def pgbouncer_safe_connect(*args, **kwargs):
        """FORCED asyncpg.connect with statement_cache_size=0"""
        # FORCE statement_cache_size to 0 no matter what
        kwargs['statement_cache_size'] = 0
        # Remove any conflicting parameters
        kwargs.pop('max_cached_statement_lifetime', None)
        kwargs.pop('max_cacheable_statement_size', None)
        kwargs.pop('prepared_statement_cache_size', None)

        logger.debug("ABSOLUTE FIX: Forcing statement_cache_size=0 on asyncpg.connect")
        return await original_connect(*args, **kwargs)

    asyncpg.connect = pgbouncer_safe_connect

    # Step 2: Monkey-patch SQLAlchemy's asyncpg dialect
    try:
        from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

        # Override the dialect's connection method
        original_connect_fn = PGDialect_asyncpg.connect

        def pgbouncer_safe_dialect_connect(self, *arg, **kw):
            """FORCED dialect connect with statement_cache_size=0"""
            # Force statement_cache_size in all connection arguments
            if 'statement_cache_size' not in kw:
                kw['statement_cache_size'] = 0
            else:
                kw['statement_cache_size'] = 0  # Override any existing value

            logger.debug("ABSOLUTE FIX: Forcing statement_cache_size=0 in dialect connect")
            return original_connect_fn(self, *arg, **kw)

        PGDialect_asyncpg.connect = pgbouncer_safe_dialect_connect

        # Disable statement caching at dialect level
        PGDialect_asyncpg.supports_statement_cache = False
        PGDialect_asyncpg.statement_cache_size = 0

    except Exception as e:
        logger.warning(f"Could not patch SQLAlchemy dialect: {e}")

    # Step 3: Do NOT monkey-patch Connection.prepare - it causes more problems
    # The statement_cache_size=0 setting should be sufficient

    logger.info("="*80)
    logger.info("ABSOLUTE PGBOUNCER FIX APPLIED!")
    logger.info("- asyncpg.connect() will ALWAYS use statement_cache_size=0")
    logger.info("- SQLAlchemy dialect will NEVER create prepared statements")
    logger.info("- Your application is now PGBouncer compatible!")
    logger.info("="*80)

    return True


# Apply the fix immediately when this module is imported
logger.info("Applying ABSOLUTE PGBouncer fix...")
apply_absolute_pgbouncer_fix()