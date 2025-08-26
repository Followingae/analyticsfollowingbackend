import asyncio
# Using SQLAlchemy async only, databases library removed
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client
import logging

from app.core.config import settings
from .unified_models import Base

logger = logging.getLogger(__name__)

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

# Database instances  
database = None
engine = None
async_engine = None
SessionLocal = None
supabase: Client = None

async def init_database():
    """Initialize database connections with network resilience"""
    global database, engine, async_engine, SessionLocal, supabase
    
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
            logger.warning("NETWORK: Network unavailable during startup - initializing with minimal configuration")
            # Still create engine but don't test connection
            async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
            async_engine = create_async_engine(
                async_url,
                pool_pre_ping=True,
                pool_recycle=600,
                pool_size=2,  # Reduced pool size for network issues
                max_overflow=1,
                pool_timeout=10,  # Shorter timeout for network issues
                echo=False,
                connect_args={
                    "command_timeout": 30,
                    "server_settings": {
                        "application_name": "analytics_backend_resilient",
                        "statement_timeout": "30s"
                    }
                }
            )
            SessionLocal = sessionmaker(
                bind=async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("SUCCESS: Database initialized in resilient mode (network unavailable)")
            return
        
        logger.info("NETWORK: Network available - proceeding with full database initialization")
        logger.info("Initializing database connections...")
        
        # Create SQLAlchemy engines with network resilience
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        
        # Enhanced connection configuration with resilience
        async_engine = create_async_engine(
            async_url,
            pool_pre_ping=True,          # Enable pre-ping to detect dead connections
            pool_recycle=300,            # Shorter recycle time for network issues (5 minutes)
            pool_size=5,                 # Standard pool size
            max_overflow=3,              # Standard overflow
            pool_timeout=20,             # Shorter timeout for better error handling
            echo=False,
            connect_args={
                "command_timeout": 30,   # Shorter timeout for network resilience
                "server_settings": {
                    "application_name": "analytics_backend_resilient",
                    "statement_timeout": "30s"  # Shorter statement timeout
                }
            }
        )
        
        # Create session factory
        SessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Test connection with resilience
        try:
            test_result = await _test_connection_with_resilience(async_engine)
            if test_result:
                logger.info("SUCCESS: Database connection test passed")
                database_resilience.record_success()
            else:
                logger.warning("WARNING: Database connection test failed - continuing with resilient mode")
                database_resilience.record_failure()
        except Exception as test_error:
            logger.warning(f"WARNING: Connection test failed: {test_error} - continuing with resilient mode")
            database_resilience.record_failure()
        
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
            
            # Initialize minimal database configuration for resilient mode
            try:
                async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
                async_engine = create_async_engine(
                    async_url,
                    pool_pre_ping=False,  # Disable pre-ping in resilient mode
                    pool_recycle=3600,    # Longer recycle time
                    pool_size=1,          # Minimal pool size
                    max_overflow=0,       # No overflow
                    pool_timeout=5,       # Very short timeout
                    echo=False
                )
                SessionLocal = sessionmaker(
                    bind=async_engine,
                    class_=AsyncSession,
                    expire_on_commit=False
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
    
    try:
        async with get_session() as session:
            # Test the session with a simple query to detect network issues early
            try:
                await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=5)
                database_resilience.record_success()
                yield session
            except asyncio.TimeoutError:
                logger.warning("DATABASE: Session timeout - network issues detected")
                database_resilience.record_failure()
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail="Database response timeout - network connectivity issues detected"
                )
            except Exception as session_error:
                logger.warning(f"DATABASE: Session error: {session_error}")
                database_resilience.record_failure()
                
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
                    
    except Exception as connection_error:
        logger.error(f"DATABASE: Connection error in get_db: {connection_error}")
        database_resilience.record_failure()
        
        # Check for network-specific errors at connection level
        error_str = str(connection_error).lower()
        if any(net_error in error_str for net_error in 
               ["getaddrinfo failed", "name or service not known", "network is unreachable",
                "connection refused", "no route to host"]):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="Database service temporarily unavailable due to network connectivity issues"
            )
        else:
            # Re-raise other errors
            raise connection_error