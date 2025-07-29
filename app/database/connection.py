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

# Database instances
database: Database = None
engine = None
async_engine = None
SessionLocal = None
supabase: Client = None

async def init_database():
    """Initialize database connections"""
    global database, engine, async_engine, SessionLocal, supabase
    
    try:
        # Skip database initialization if URL is empty or contains placeholder
        if not settings.DATABASE_URL or "[YOUR-PASSWORD]" in settings.DATABASE_URL:
            logger.warning("⚠️ Database URL not configured. Skipping database initialization.")
            return
        
        # Try different connection approach for Supabase
        logger.info("🔄 Trying direct Supabase connection...")
        
        logger.info("🔄 Initializing database connections...")
        
        # Create SQLAlchemy engines first
        sync_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
        async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        
        async_engine = create_async_engine(
            async_url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            echo=False
        )
        
        # Create session factory
        SessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Test the connection
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        
        logger.info("✅ Database connection established")
        
        # Initialize databases connection for async operations (optional)
        try:
            database = Database(settings.DATABASE_URL)
            await database.connect()
            logger.info("✅ Database async interface initialized")
        except Exception as db_error:
            logger.warning(f"⚠️ Database async interface failed (using SQLAlchemy only): {str(db_error)}")
            database = None
        
        # Initialize Supabase client if key is provided
        if settings.SUPABASE_KEY:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("✅ Supabase client initialized")
        
        logger.info("✅ Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        logger.warning("⚠️ Continuing without database (fallback mode)")
        # Don't raise the exception, continue without database

async def close_database():
    """Close database connections"""
    global database
    
    if database:
        await database.disconnect()
        logger.info("Database connection closed")

async def create_tables():
    """Create all database tables"""
    if not async_engine:
        logger.warning("⚠️  Database not initialized. Skipping table creation.")
        return
        
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {str(e)}")
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
    """Database dependency for FastAPI endpoints"""
    if not SessionLocal:
        # Return a mock session or skip database operations
        logger.warning("Database not initialized, using mock session")
        yield None
        return
        
    async for session in get_session():
        yield session