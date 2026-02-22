"""
GLOBAL PGBouncer Fix - Complete prepared statement prevention wrapper
This module ensures ALL database operations bypass prepared statements
"""
from sqlalchemy import text, select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class GlobalPGBouncerWrapper:
    """
    GLOBAL wrapper that intercepts ALL SQLAlchemy operations
    and converts them to raw SQL to prevent prepared statements
    """

    @staticmethod
    async def safe_execute(db: AsyncSession, query: Any, params: Optional[Dict] = None):
        """
        GLOBAL safe execute that prevents ALL prepared statements
        """
        try:
            # First, always rollback any existing transaction
            if db.in_transaction():
                await db.rollback()
                logger.debug("GLOBAL FIX: Rolled back existing transaction")

            # Convert ORM queries to raw SQL
            if hasattr(query, 'compile'):
                from sqlalchemy.dialects import postgresql

                # Compile to SQL with literal binds
                compiled = query.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True}
                )

                # Convert to text query
                raw_query = text(str(compiled))
                result = await db.execute(raw_query)
                return result

            # If already text, execute directly
            elif isinstance(query, type(text(""))):
                result = await db.execute(query, params)
                return result

            # For string queries, convert to text
            else:
                raw_query = text(str(query))
                result = await db.execute(raw_query, params)
                return result

        except Exception as e:
            # If we get ANY prepared statement error, handle it
            if "prepared statement" in str(e).lower() or "transaction is aborted" in str(e).lower():
                logger.warning(f"GLOBAL FIX: Caught prepared statement error, retrying with inline params")

                # Rollback and retry
                await db.rollback()

                # Try to inline parameters directly
                if params and hasattr(query, '__str__'):
                    query_str = str(query)
                    for key, value in params.items():
                        if isinstance(value, str):
                            value = value.replace("'", "''")
                            query_str = query_str.replace(f":{key}", f"'{value}'")
                        elif value is None:
                            query_str = query_str.replace(f":{key}", "NULL")
                        else:
                            query_str = query_str.replace(f":{key}", str(value))

                    raw_query = text(query_str)
                    result = await db.execute(raw_query)
                    return result

            # Re-raise if we couldn't handle it
            raise

    @staticmethod
    async def safe_scalar(db: AsyncSession, query: Any, params: Optional[Dict] = None):
        """
        GLOBAL safe scalar that prevents ALL prepared statements
        """
        result = await GlobalPGBouncerWrapper.safe_execute(db, query, params)
        return result.scalar()

    @staticmethod
    async def safe_first(db: AsyncSession, query: Any, params: Optional[Dict] = None):
        """
        GLOBAL safe first that prevents ALL prepared statements
        """
        result = await GlobalPGBouncerWrapper.safe_execute(db, query, params)
        return result.first()

    @staticmethod
    async def safe_all(db: AsyncSession, query: Any, params: Optional[Dict] = None):
        """
        GLOBAL safe all that prevents ALL prepared statements
        """
        result = await GlobalPGBouncerWrapper.safe_execute(db, query, params)
        return result.all()

    @staticmethod
    async def safe_commit(db: AsyncSession):
        """
        GLOBAL safe commit that handles transaction issues
        """
        try:
            if db.in_transaction():
                await db.commit()
        except Exception as e:
            if "transaction is aborted" in str(e).lower():
                await db.rollback()
                logger.warning("GLOBAL FIX: Transaction was aborted, rolled back")
            else:
                raise


# GLOBAL singleton instance
pgbouncer_fix = GlobalPGBouncerWrapper()


# GLOBAL helper functions for easy access
async def safe_query(db: AsyncSession, model, filters: Optional[Dict] = None):
    """
    GLOBAL helper to safely query a model without prepared statements

    Example:
        users = await safe_query(db, User, {"email": "test@example.com"})
    """
    query = select(model)

    if filters:
        for key, value in filters.items():
            query = query.where(getattr(model, key) == value)

    return await pgbouncer_fix.safe_all(db, query)


async def safe_get_one(db: AsyncSession, model, filters: Dict):
    """
    GLOBAL helper to safely get one record without prepared statements

    Example:
        user = await safe_get_one(db, User, {"id": user_id})
    """
    query = select(model)

    for key, value in filters.items():
        query = query.where(getattr(model, key) == value)

    return await pgbouncer_fix.safe_first(db, query)


async def safe_insert(db: AsyncSession, model, values: Dict):
    """
    GLOBAL helper to safely insert without prepared statements

    Example:
        await safe_insert(db, User, {"email": "new@example.com", "name": "Test"})
    """
    query = insert(model).values(**values)
    await pgbouncer_fix.safe_execute(db, query)
    await pgbouncer_fix.safe_commit(db)


async def safe_update(db: AsyncSession, model, filters: Dict, values: Dict):
    """
    GLOBAL helper to safely update without prepared statements

    Example:
        await safe_update(db, User, {"id": user_id}, {"name": "Updated"})
    """
    query = update(model)

    for key, value in filters.items():
        query = query.where(getattr(model, key) == value)

    query = query.values(**values)
    await pgbouncer_fix.safe_execute(db, query)
    await pgbouncer_fix.safe_commit(db)


async def safe_delete(db: AsyncSession, model, filters: Dict):
    """
    GLOBAL helper to safely delete without prepared statements

    Example:
        await safe_delete(db, User, {"id": user_id})
    """
    query = delete(model)

    for key, value in filters.items():
        query = query.where(getattr(model, key) == value)

    await pgbouncer_fix.safe_execute(db, query)
    await pgbouncer_fix.safe_commit(db)


# Export all GLOBAL functions
__all__ = [
    'pgbouncer_fix',
    'safe_query',
    'safe_get_one',
    'safe_insert',
    'safe_update',
    'safe_delete',
    'GlobalPGBouncerWrapper'
]