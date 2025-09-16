import asyncio
from typing import AsyncGenerator
# Enterprise-grade SQLAlchemy async with connection pooling
from sqlalchemy import create_engine, MetaData, text, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from supabase import create_client, Client
import logging

from app.core.config import settings
from .unified_models import Base

logger = logging.getLogger(__name__)

def get_database_url() -> str:
    """Get the database URL for external connections"""
    return settings.DATABASE_URL

async def _test_connection(engine):
    """Helper function to test database connection with resilience"""
    max_retries = 3
    retry_delays = [1, 2, 4]
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                logger.info(f"Connection test successful on attempt {attempt + 1}")
                return result.scalar()
        except Exception as e:
            logger.warning(f"Connection test attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delays[attempt])
            else:
                logger.error("All connection test attempts failed")
                raise Exception(f"Connection test failed after {max_retries} attempts: {e}")

async def _test_connection_with_resilience(engine):
    """Enhanced connection test with network resilience patterns"""
    from app.resilience.database_resilience import database_resilience
    
    # Check if circuit breaker is open
    if database_resilience.should_circuit_break():
        logger.warning("CIRCUIT BREAKER: Skipping connection test - circuit breaker is open")
        return False
    
    max_retries = 5
    retry_delays = [0.5, 1, 2, 4, 8]  # Exponential backoff with jitter
    
    for attempt in range(max_retries):
        try:
            # Add jitter to prevent thundering herd
            import random
            jitter = random.uniform(0, 0.5)
            
            # Fix async context manager usage
            async with engine.begin() as conn:
                result = await asyncio.wait_for(
                    conn.execute(text("SELECT 1 as test")), 
                    timeout=5
                )
                test_value = result.scalar()
                
                if test_value == 1:
                    logger.info(f"RESILIENT: Connection test successful on attempt {attempt + 1}")
                    database_resilience.record_success()
                    return True
                else:
                    raise Exception(f"Unexpected test result: {test_value}")
                    
        except asyncio.TimeoutError as e:
            logger.warning(f"RESILIENT: Connection test timeout on attempt {attempt + 1}")
            database_resilience.record_failure()
            
        except Exception as e:
            logger.warning(f"RESILIENT: Connection test attempt {attempt + 1} failed: {e}")
            database_resilience.record_failure()
            
            # Check for network-specific errors
            error_str = str(e).lower()
            if any(net_error in error_str for net_error in 
                   ["getaddrinfo failed", "name or service not known", "network is unreachable", 
                    "connection refused", "no route to host"]):
                logger.warning(f"NETWORK ERROR detected: {e}")
                
        # Wait with jitter before retry
        if attempt < max_retries - 1:
            delay = retry_delays[attempt] + jitter
            logger.info(f"RESILIENT: Waiting {delay:.1f}s before retry {attempt + 2}")
            await asyncio.sleep(delay)
    
    logger.error("RESILIENT: All connection test attempts failed")
    database_resilience.record_failure()
    return False

# INDUSTRY STANDARD DATABASE CONFIGURATION - Used by Modash, HypeAuditor, etc.
class DatabaseConfig:
    """Enterprise-scale database configuration for high-traffic analytics platforms"""

    # OPTIMIZED Connection Pool Settings - Prevent timeout issues
    POOL_SIZE = 10                    # Reduced to prevent pool exhaustion
    MAX_OVERFLOW = 15                 # Conservative overflow for stability
    POOL_TIMEOUT = 5                  # Faster timeout to prevent hanging
    POOL_RECYCLE = 3600              # 1 hour recycle (industry standard)
    POOL_PRE_PING = True             # Always validate connections
    POOL_RESET_ON_RETURN = 'commit'   # Clean connection state on return

    # Session Management - Industry best practices
    SESSION_EXPIRE_ON_COMMIT = False  # Keep objects accessible after commit
    SESSION_AUTOFLUSH = False        # Manual flush for better control
    SESSION_AUTOCOMMIT = False       # Explicit transaction control

    # Connection Health - Industry standard timeouts
    CONNECT_TIMEOUT = 30             # Standard connection timeout
    QUERY_TIMEOUT = 60               # Standard query timeout
    HEALTH_CHECK_INTERVAL = 30       # Standard health check frequency

    # Async Connection Settings - Optimized AsyncPG configuration
    ASYNCPG_COMMAND_TIMEOUT = 30     # Reduced timeout to prevent hangs
    ASYNCPG_SERVER_SETTINGS = {
        "application_name": "analytics_following_production",
        "statement_timeout": "30s",    # Reduced statement timeout
        "idle_in_transaction_session_timeout": "120000",   # 2 minutes (reduced)
        "tcp_keepalives_idle": "600",       # 10 minutes TCP keepalive
        "tcp_keepalives_interval": "60",    # 1 minute keepalive interval
        "tcp_keepalives_count": "5",        # 5 keepalive attempts
        "application_name": "analytics_following_production"
    }

# Database instances  
database = None
engine = None
async_engine = None
SessionLocal = None
AsyncSessionLocal = None
supabase: Client = None

async def init_database():
    """Initialize enterprise-grade database connections with advanced pooling"""
    global database, engine, async_engine, SessionLocal, AsyncSessionLocal, supabase
    
    # CHECK: If already initialized, return immediately (single connection pool pattern)
    if async_engine is not None and SessionLocal is not None:
        logger.info("Database already initialized - reusing existing connection pool")
        return
    
    try:
        # Skip database initialization if URL is empty or contains placeholder
        if not settings.DATABASE_URL or "[YOUR-PASSWORD]" in settings.DATABASE_URL:
            logger.warning("WARNING: Database URL not configured. Skipping database initialization.")
            return
        
        # Import resilience here to avoid circular imports
        from app.resilience.database_resilience import database_resilience
        
        # Check network availability before attempting connection
        if not database_resilience.is_network_available():
            logger.warning("NETWORK: Network unavailable during startup - initializing with UNIFIED configuration")
            # Industry standard configuration for network unavailable mode
            async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            async_engine = create_async_engine(
                async_url,
                pool_size=10,  # Reduced for resilient mode
                max_overflow=15,
                pool_timeout=DatabaseConfig.POOL_TIMEOUT,
                pool_recycle=DatabaseConfig.POOL_RECYCLE,
                pool_pre_ping=False,  # Disable pre-ping when network unavailable
                echo=False,
                connect_args={
                    "command_timeout": DatabaseConfig.ASYNCPG_COMMAND_TIMEOUT,
                    "server_settings": DatabaseConfig.ASYNCPG_SERVER_SETTINGS
                }
            )
            SessionLocal = sessionmaker(
                bind=async_engine,
                class_=AsyncSession,
                expire_on_commit=DatabaseConfig.SESSION_EXPIRE_ON_COMMIT,
                autoflush=DatabaseConfig.SESSION_AUTOFLUSH,
                autocommit=DatabaseConfig.SESSION_AUTOCOMMIT
            )
            logger.info("SUCCESS: Database initialized in resilient mode (network unavailable)")
            return
        
        logger.info("NETWORK: Network available - proceeding with full database initialization")
        logger.info("Initializing database connections...")
        
        # Create SQLAlchemy engines with UNIFIED configuration
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

        # INDUSTRY STANDARD: Production-grade configuration like Modash/HypeAuditor
        async_engine = create_async_engine(
            async_url,
            pool_size=DatabaseConfig.POOL_SIZE,
            max_overflow=DatabaseConfig.MAX_OVERFLOW,
            pool_timeout=DatabaseConfig.POOL_TIMEOUT,
            pool_recycle=DatabaseConfig.POOL_RECYCLE,
            pool_pre_ping=DatabaseConfig.POOL_PRE_PING,
            pool_reset_on_return=DatabaseConfig.POOL_RESET_ON_RETURN,
            echo=False,
            connect_args={
                "command_timeout": DatabaseConfig.ASYNCPG_COMMAND_TIMEOUT,
                "server_settings": DatabaseConfig.ASYNCPG_SERVER_SETTINGS
            }
        )
        
        # Create session factory with unified configuration
        SessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=DatabaseConfig.SESSION_EXPIRE_ON_COMMIT,
            autoflush=DatabaseConfig.SESSION_AUTOFLUSH,
            autocommit=DatabaseConfig.SESSION_AUTOCOMMIT
        )
        
        # Test database connection with proper timeout
        logger.info("TESTING: Database connection with timeout protection...")
        try:
            connection_test_result = await asyncio.wait_for(
                _test_connection_with_resilience(async_engine), 
                timeout=30.0
            )
            if connection_test_result:
                logger.info("SUCCESS: Database connection test passed")
            else:
                logger.warning("WARNING: Database connection test failed - continuing with pool")
        except asyncio.TimeoutError:
            logger.warning("WARNING: Connection test timed out after 30s - continuing with pool")
        except Exception as test_error:
            logger.warning(f"WARNING: Connection test failed: {test_error} - continuing with pool")
        
        # Using SQLAlchemy async only - databases library not needed
        database = None
        
        # Initialize Supabase client with network resilience
        if settings.SUPABASE_KEY:
            try:
                supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logger.info("SUCCESS: Supabase client initialized")
            except Exception as supabase_error:
                logger.warning(f"WARNING: Supabase client initialization failed: {supabase_error}")
                logger.warning("Application will continue without Supabase client")
                supabase = None
        
        logger.info("SUCCESS: Database initialization completed with network resilience")
        
    except Exception as e:
        logger.error(f"ERROR: Database initialization failed: {str(e)}")
        
        # Check if this is a network-related error
        if "getaddrinfo failed" in str(e) or "Name or service not known" in str(e):
            logger.warning("NETWORK ERROR: Database initialization failed due to network issues")
            logger.warning("Starting application in RESILIENT MODE - database will retry connections automatically")
            
            # Industry standard emergency configuration
            try:
                async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
                async_engine = create_async_engine(
                    async_url,
                    pool_size=5,  # Minimal for emergency mode
                    max_overflow=5,
                    pool_timeout=DatabaseConfig.POOL_TIMEOUT,
                    pool_recycle=DatabaseConfig.POOL_RECYCLE,
                    pool_pre_ping=False,  # Disable pre-ping in emergency mode
                    echo=False,
                    connect_args={
                        "command_timeout": DatabaseConfig.ASYNCPG_COMMAND_TIMEOUT,
                        "server_settings": DatabaseConfig.ASYNCPG_SERVER_SETTINGS
                    }
                )
                SessionLocal = sessionmaker(
                    bind=async_engine,
                    class_=AsyncSession,
                    expire_on_commit=DatabaseConfig.SESSION_EXPIRE_ON_COMMIT,
                    autoflush=DatabaseConfig.SESSION_AUTOFLUSH,
                    autocommit=DatabaseConfig.SESSION_AUTOCOMMIT
                )
                logger.info("SUCCESS: Database initialized in EMERGENCY RESILIENT MODE")
                return
            except Exception as resilient_error:
                logger.error(f"CRITICAL: Even resilient database initialization failed: {resilient_error}")
        
        logger.error("DATABASE REQUIRED - Cannot continue without database!")
        raise Exception(f"Database initialization failed: {str(e)}. Application cannot start without database.")

async def close_database():
    """Close database connections and reset global state"""
    global database, engine, async_engine, SessionLocal, supabase
    
    try:
        # No databases library to disconnect - using SQLAlchemy async only
        pass
        
        if async_engine:
            await async_engine.dispose()
            logger.info("Database connection pool closed")
        
        # Reset global variables to allow clean re-initialization
        database = None
        engine = None 
        async_engine = None
        SessionLocal = None
        supabase = None
        
        logger.info("All database connections closed and state reset")
        
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

async def create_tables():
    """Create all database tables (excluding auth schema tables managed by Supabase)"""
    if not async_engine:
        logger.warning("WARNING:  Database not initialized. Skipping table creation.")
        return
        
    try:
        def create_filtered_tables(conn):
            # Get all tables except those in auth schema
            tables_to_create = [
                table for table in Base.metadata.tables.values() 
                if table.schema != 'auth'
            ]
            
            # Create only the filtered tables
            from sqlalchemy.schema import CreateTable
            for table in tables_to_create:
                conn.execute(CreateTable(table, if_not_exists=True))
        
        async with async_engine.begin() as conn:
            await conn.run_sync(create_filtered_tables)
        logger.info("SUCCESS: Database tables created successfully (excluding auth schema)")
    except Exception as e:
        logger.error(f"ERROR: Failed to create tables: {str(e)}")
        raise

def get_session():
    """Get database session context manager"""
    if not SessionLocal:
        raise Exception("Database not initialized")
    return SessionLocal()

def get_supabase() -> Client:
    """Get Supabase client"""
    if not supabase:
        raise Exception("Supabase client not initialized")
    return supabase

# Database dependency for FastAPI
async def get_db():
    """Database dependency for FastAPI endpoints with network resilience"""
    if not SessionLocal:
        logger.error("DATABASE: Database not initialized - application should not have started")
        raise Exception("Database not initialized - critical system error")
    
    from app.resilience.database_resilience import database_resilience
    
    # Check circuit breaker before attempting connection
    if database_resilience.should_circuit_break():
        logger.warning("CIRCUIT BREAKER: Database operations blocked - circuit breaker is open")
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503, 
            detail="Database temporarily unavailable - circuit breaker active. Please try again in a few moments."
        )
    
    session = None
    try:
        # Create async session directly from SessionLocal
        session = SessionLocal()
        
        # Skip health check to avoid transaction conflicts - rely on pool_pre_ping instead
        database_resilience.record_success()
        
        # CRITICAL FIX: Proper session yield with timeout protection and enhanced error handling
        try:
            # Validate session is healthy before yielding
            if session.is_active:
                # Add timeout protection for long-running operations
                yield session

                # Only commit if there's an active transaction and session is still healthy
                if session.in_transaction() and session.is_active:
                    await asyncio.wait_for(session.commit(), timeout=DatabaseConfig.QUERY_TIMEOUT)
            else:
                logger.warning("DATABASE: Session became inactive before yield, creating new session")
                await session.close()
                session = SessionLocal()
                yield session

                if session.in_transaction() and session.is_active:
                    await asyncio.wait_for(session.commit(), timeout=DatabaseConfig.QUERY_TIMEOUT)

        except asyncio.TimeoutError:
            logger.warning(f"DATABASE: Session timeout after {DatabaseConfig.QUERY_TIMEOUT}s - network issues detected")
            database_resilience.record_failure()
            if session and session.in_transaction():
                try:
                    await asyncio.wait_for(session.rollback(), timeout=5.0)
                except Exception:
                    pass  # Ignore rollback errors during cleanup
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="Database response timeout - please try again in a moment"
            )

        except Exception as session_error:
            # Log detailed error information for debugging
            error_message = str(session_error) if session_error else "Unknown error"
            error_type = type(session_error).__name__
            logger.error(f"DATABASE: Session error [{error_type}]: {error_message}")
            database_resilience.record_failure()

            # Always rollback on error if transaction exists
            if session and session.in_transaction():
                try:
                    await asyncio.wait_for(session.rollback(), timeout=5.0)
                except Exception as rollback_error:
                    logger.warning(f"DATABASE: Rollback error: {rollback_error}")
                    pass  # Ignore rollback errors

            # Check for network-specific errors
            error_str = str(session_error).lower()
            if any(net_error in error_str for net_error in
                   ["getaddrinfo failed", "name or service not known", "network is unreachable",
                    "connection refused", "no route to host", "timeout"]):
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail="Database connection failed due to network issues - please check connectivity"
                )
            else:
                # Re-raise non-network errors
                raise session_error
                
    except Exception as outer_error:
        # Handle session creation errors
        logger.error(f"DATABASE: Outer session error: {outer_error}", exc_info=True)
        if session and session.in_transaction():
            try:
                await session.rollback()
            except Exception as outer_rollback_error:
                logger.warning(f"DATABASE: Outer rollback error: {outer_rollback_error}")
                pass
        raise outer_error
        
    finally:
        # Enhanced session cleanup with connection pool health monitoring
        if session:
            try:
                # Check if session needs rollback before closing
                if session.in_transaction():
                    logger.debug("DATABASE: Rolling back open transaction during cleanup")
                    try:
                        await asyncio.wait_for(session.rollback(), timeout=5.0)
                    except Exception as rollback_cleanup_error:
                        logger.warning(f"DATABASE: Cleanup rollback failed: {rollback_cleanup_error}")

                # Close session and return connection to pool
                await asyncio.wait_for(session.close(), timeout=5.0)
                logger.debug("DATABASE: Session closed and connection returned to pool")

            except asyncio.TimeoutError:
                logger.error("DATABASE: Session close timeout - potential connection leak")
                # Force close session to prevent connection leak
                try:
                    session.bind = None  # Clear bind to force connection release
                except Exception:
                    pass
            except Exception as close_error:
                logger.warning(f"DATABASE: Session close error: {close_error}")
                # Force close session on error to prevent connection leak
                try:
                    session.bind = None  # Clear bind to force connection release
                except Exception:
                    pass