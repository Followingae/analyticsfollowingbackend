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
    """Helper function to test database connection"""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

# Database instances  
database = None
engine = None
async_engine = None
SessionLocal = None
supabase: Client = None

async def init_database():
    """Initialize database connections - SINGLE CONNECTION POOL PATTERN"""
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
        
        # Try different connection approach for Supabase
        logger.info("Trying direct Supabase connection...")
        
        logger.info("Initializing database connections...")
        
        # Create SQLAlchemy engines first
        sync_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        
        # OPTIMIZED CONNECTION POOL - For Supabase pooler compatibility
        async_engine = create_async_engine(
            async_url,
            pool_pre_ping=True,          # Enable pre-ping to detect dead connections
            pool_recycle=600,            # Recycle connections every 10 minutes
            pool_size=5,                 # Increased pool size for better concurrency
            max_overflow=3,              # Increased overflow for peak loads
            pool_timeout=30,             # Longer timeout for connections
            echo=False,
            connect_args={
                "command_timeout": 60,   # 60 second timeout for commands
                "server_settings": {
                    "application_name": "analytics_backend",
                    "statement_timeout": "60s"  # 60 second statement timeout
                }
            }
        )
        
        # Create session factory
        SessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # MANDATORY CONNECTION TEST - Must succeed for app to start
        try:
            logger.info("Testing database connection...")
            test_task = asyncio.create_task(_test_connection(async_engine))
            await asyncio.wait_for(test_task, timeout=60)  # Increased timeout to 60 seconds
            logger.info("Database connection test successful")
        except asyncio.TimeoutError:
            logger.error("Database connection test timed out after 60 seconds")
            raise Exception("Database connection timeout - cannot start application")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise Exception(f"Database connection failed: {e} - cannot start application")
        
        logger.info("SUCCESS: Database connection established")
        
        # Using SQLAlchemy async only - databases library not needed
        database = None
        
        # Initialize Supabase client if key is provided
        if settings.SUPABASE_KEY:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("SUCCESS: Supabase client initialized")
        
        logger.info("SUCCESS: Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"ERROR: Database initialization failed: {str(e)}")
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

async def get_session() -> AsyncSession:
    """Get database session"""
    if not SessionLocal:
        raise Exception("Database not initialized")
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def get_supabase() -> Client:
    """Get Supabase client"""
    if not supabase:
        raise Exception("Supabase client not initialized")
    return supabase

# Database dependency for FastAPI
async def get_db():
    """Database dependency for FastAPI endpoints - STRICT MODE"""
    if not SessionLocal:
        logger.error("❌ Database not initialized - application should not have started")
        raise Exception("Database not initialized - critical system error")
        
    async for session in get_session():
        yield session