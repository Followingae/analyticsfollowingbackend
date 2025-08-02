import asyncio
from databases import Database
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client
import logging

from app.core.config import settings
from .models import Base

logger = logging.getLogger(__name__)

async def _test_connection(engine):
    """Helper function to test database connection"""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

# Database instances
database: Database = None
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
        
        # ROBUST CONNECTION POOL - Professional implementation with Transaction Pooler support
        async_engine = create_async_engine(
            async_url,
            pool_pre_ping=True,          # Test connections before use
            pool_recycle=300,            # Recycle connections every 5 minutes
            pool_size=5,                 # Reduced pool size for stability
            max_overflow=2,              # Reduced overflow for stability
            pool_timeout=10,             # Reduced timeout for faster failure detection
            echo=False,
            connect_args={
                "command_timeout": 30,
                "server_settings": {
                    "application_name": "analytics_backend",
                    "tcp_keepalives_idle": "600",
                    "tcp_keepalives_interval": "30",
                    "tcp_keepalives_count": "3"
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
            await asyncio.wait_for(test_task, timeout=30)
            logger.info("Database connection test successful")
        except asyncio.TimeoutError:
            logger.error("Database connection test timed out after 30 seconds")
            raise Exception("Database connection timeout - cannot start application")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise Exception(f"Database connection failed: {e} - cannot start application")
        
        logger.info("SUCCESS: Database connection established")
        
        # Initialize databases connection for async operations (optional)
        try:
            database = Database(settings.DATABASE_URL)
            await database.connect()
            logger.info("SUCCESS: Database async interface initialized")
        except Exception as db_error:
            logger.warning(f"WARNING: Database async interface failed (using SQLAlchemy only): {str(db_error)}")
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
        if database:
            await database.disconnect()
            logger.info("Database async interface closed")
        
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
    """Create all database tables"""
    if not async_engine:
        logger.warning("WARNING:  Database not initialized. Skipping table creation.")
        return
        
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SUCCESS: Database tables created successfully")
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