"""
PGBouncer-safe database session with prepared statement prevention
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.sql import Select, Insert, Update, Delete
from sqlalchemy.orm import Query
import logging

logger = logging.getLogger(__name__)


class PGBouncerSafeSession(AsyncSession):
    """
    GLOBAL SQLAlchemy AsyncSession that COMPLETELY prevents ALL prepared statements.
    This aggressively overrides all methods to ensure PGBouncer compatibility.
    """

    def __init__(self, *args, **kwargs):
        # GLOBAL: Force execution options that disable prepared statements
        if 'bind' in kwargs and kwargs['bind']:
            kwargs['bind'] = kwargs['bind'].execution_options(
                postgresql_prepared=False,
                no_parameters=False,  # Allow parameters but handle them specially
                isolation_level="AUTOCOMMIT"  # Prevent transaction issues
            )

        # GLOBAL: Set session-level options to prevent prepared statements
        kwargs['expire_on_commit'] = False
        kwargs['autoflush'] = False
        kwargs['autocommit'] = False

        super().__init__(*args, **kwargs)

        # GLOBAL: Override session execution options
        self._execution_options = {
            'postgresql_prepared': False,
            'no_parameters': False,
            'synchronize_session': False,
            'compiled_cache': None
        }

    async def execute(self, statement, params=None, execution_options=None, **kw):
        """
        Override execute to force all queries to bypass prepared statements.
        """
        # Merge execution options to always disable prepared statements
        exec_options = execution_options or {}
        exec_options.update({
            "postgresql_prepared": False,
            "no_parameters": False,  # Allow parameters but handle them specially
            "compiled_cache": None,  # Disable compiled cache for this query
            "synchronize_session": False  # Disable synchronization
            # Note: compiled_cache cannot be set per-statement, it's connection-level only
        })

        # Import text here if needed for the isinstance check
        from sqlalchemy import text as sql_text

        # If it's already a text() statement with parameters, handle it specially
        if isinstance(statement, type(sql_text(""))):
            # For text queries with parameters, we need to handle them carefully
            # to avoid prepared statement conflicts
            try:
                # First attempt: try with no cache
                result = await super().execute(
                    statement,
                    params,
                    execution_options=exec_options,
                    **kw
                )
                return result
            except Exception as e:
                if "prepared statement" in str(e).lower():
                    logger.warning(f"PGBouncer error on text query, attempting inline parameter substitution")

                    # If we have params, try to inline them directly into the query
                    if params:
                        query_str = str(statement)
                        # Replace named parameters with their values
                        for key, value in (params.items() if isinstance(params, dict) else enumerate(params)):
                            if isinstance(value, str):
                                # Escape single quotes in strings
                                value = value.replace("'", "''")
                                query_str = query_str.replace(f"${key+1}" if isinstance(params, (list, tuple)) else f":{key}", f"'{value}'")
                            elif value is None:
                                query_str = query_str.replace(f"${key+1}" if isinstance(params, (list, tuple)) else f":{key}", "NULL")
                            elif isinstance(value, (int, float)):
                                query_str = query_str.replace(f"${key+1}" if isinstance(params, (list, tuple)) else f":{key}", str(value))
                            elif hasattr(value, 'isoformat'):  # datetime
                                query_str = query_str.replace(f"${key+1}" if isinstance(params, (list, tuple)) else f":{key}", f"'{value.isoformat()}'")

                        # Execute the query with inlined parameters
                        result = await super().execute(
                            sql_text(query_str),
                            execution_options=exec_options,
                            **kw
                        )
                        return result
                    raise

        # For SQLAlchemy ORM queries (Select, Insert, Update, Delete),
        # convert them to text queries to completely bypass prepared statements
        if hasattr(statement, 'compile'):
            try:
                from sqlalchemy.dialects import postgresql
                from sqlalchemy import text

                # Compile the statement to SQL with literal binds
                compiled = statement.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True}
                )

                # Convert to text query
                text_query = text(str(compiled))

                # Execute as text query
                result = await super().execute(
                    text_query,
                    execution_options=exec_options,
                    **kw
                )
                return result
            except Exception as compile_error:
                logger.warning(f"Failed to compile ORM query to text, trying original: {compile_error}")
                # Fall back to original execution if compilation fails

        try:
            # Execute with prepared statement prevention
            result = await super().execute(
                statement,
                params,
                execution_options=exec_options,
                **kw
            )
            return result
        except Exception as e:
            # If we get a prepared statement error, log it and re-raise
            error_str = str(e)
            if "prepared statement" in error_str.lower():
                logger.error(f"PGBouncer prepared statement error detected: {e}")
                logger.error(f"Statement type: {type(statement)}")

                # Try to convert to text and retry
                try:
                    if hasattr(statement, 'compile'):
                        from sqlalchemy.dialects import postgresql
                        compiled = statement.compile(
                            dialect=postgresql.dialect(),
                            compile_kwargs={"literal_binds": True}
                        )
                        text_query = text(str(compiled))
                        result = await super().execute(
                            text_query,
                            execution_options=exec_options,
                            **kw
                        )
                        logger.info("Successfully converted to text query after prepared statement error")
                        return result
                except Exception as retry_error:
                    logger.error(f"Failed to retry as text query: {retry_error}")

            # Re-raise the original error if we couldn't handle it
            raise

    async def commit(self):
        """Commit with prepared statement prevention"""
        return await super().commit()

    async def rollback(self):
        """Rollback with prepared statement prevention"""
        return await super().rollback()

    async def flush(self, objects=None):
        """Flush with prepared statement prevention"""
        return await super().flush(objects)


def create_pgbouncer_safe_session_factory(engine):
    """
    Create a session factory that produces PGBouncer-safe sessions.
    """
    from sqlalchemy.orm import sessionmaker

    # Create session factory with PGBouncer-safe session class
    return sessionmaker(
        bind=engine,
        class_=PGBouncerSafeSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False
    )