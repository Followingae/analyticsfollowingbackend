"""
Supabase-Optimized Database Connection Pools
Industry-standard separation for API vs Background workloads
"""
import logging
import os
from typing import Dict, Optional, AsyncGenerator
from sqlalchemy import create_engine, text, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)

class SupabaseOptimizedPools:
    """
    Industry-standard database pool management optimized for Supabase Pro

    Provides complete isolation between:
    - User-facing API operations (fast, small transactions)
    - Background worker operations (long-running, batch processing)
    - AI processing operations (heavy computational workloads)
    - Discovery operations (bulk data operations)
    """

    def __init__(self):
        self.pools: Dict[str, any] = {}
        self.session_makers: Dict[str, async_sessionmaker] = {}
        self.initialized = False

        # Supabase Pro connection allocation strategy
        # Total available: ~500 connections
        self.pool_config = {
            'user_api': {
                'pool_size': 100,        # 20% - High concurrency for user requests
                'max_overflow': 50,      # Burst capacity
                'pool_timeout': 2,       # Fast timeout - users can't wait
                'pool_recycle': 1800,    # 30min - Supabase optimal
                'application_name': 'analytics_api',
                'statement_timeout': 10000,  # 10s max query time
                'command_timeout': 5
            },
            'background_workers': {
                'pool_size': 80,         # 16% - Background operations
                'max_overflow': 20,
                'pool_timeout': 30,      # Can wait longer
                'pool_recycle': 3600,    # 1hr
                'application_name': 'analytics_workers',
                'statement_timeout': 300000,  # 5min for long operations
                'command_timeout': 60
            },
            'ai_workers': {
                'pool_size': 30,         # 6% - AI intensive operations
                'max_overflow': 10,
                'pool_timeout': 60,      # AI can wait longer
                'pool_recycle': 3600,
                'application_name': 'analytics_ai_workers',
                'statement_timeout': 600000,  # 10min for AI processing
                'command_timeout': 300
            },
            'discovery_workers': {
                'pool_size': 20,         # 4% - Discovery operations
                'max_overflow': 5,
                'pool_timeout': 45,
                'pool_recycle': 3600,
                'application_name': 'analytics_discovery',
                'statement_timeout': 300000,  # 5min
                'command_timeout': 60
            }
        }

    async def initialize(self) -> bool:
        """Initialize all connection pools with Supabase optimization (alias for initialize_pools)"""
        return await self.initialize_pools()

    async def initialize_pools(self) -> bool:
        """Initialize all connection pools with Supabase optimization"""
        try:
            if self.initialized:
                return True

            logger.info("Initializing Supabase-optimized connection pools...")

            # Build Supabase connection URL
            supabase_url = self._build_supabase_url()

            # Create pools for each workload type
            for pool_name, config in self.pool_config.items():
                logger.info(f"Creating {pool_name} pool: {config['pool_size']} connections")

                # Create async engine optimized for Supabase (pgbouncer)
                engine = create_async_engine(
                    supabase_url,
                    # Basic async engine configuration
                    pool_size=config['pool_size'],
                    max_overflow=config['max_overflow'],
                    pool_timeout=config['pool_timeout'],
                    pool_recycle=config['pool_recycle'],
                    pool_pre_ping=False,  # Disable pre-ping to avoid prepared statements
                    echo=False,  # Disable SQL logging in production
                    connect_args={
                        # Essential pgbouncer compatibility settings
                        'statement_cache_size': 0,  # Required for pgbouncer transaction pooling
                        'prepared_statement_cache_size': 0,  # Additional safety for prepared statements
                        'prepared_statement_name_func': None,  # Disable named prepared statements
                        'server_settings': {
                            'application_name': config['application_name']
                        }
                    }
                )

                # Skip connection test to avoid pgbouncer prepared statement conflicts
                # Connection will be tested when first used
                logger.info(f"Pool {pool_name} created successfully (connection test skipped for pgbouncer compatibility)")

                # Store pool and create session maker
                self.pools[pool_name] = engine
                self.session_makers[pool_name] = async_sessionmaker(
                    engine,
                    class_=AsyncSession,
                    expire_on_commit=False
                )

            self.initialized = True
            logger.info("All connection pools initialized successfully")

            # Log connection allocation summary
            total_allocated = sum(
                config['pool_size'] + config['max_overflow']
                for config in self.pool_config.values()
            )
            logger.info(f"Total connections allocated: {total_allocated}/500 (Safety buffer: {500-total_allocated})")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize connection pools: {e}")
            return False

    def _build_supabase_url(self) -> str:
        """Build optimized Supabase connection URL"""
        try:
            # Handle URL encoding and format validation
            database_url = settings.DATABASE_URL.strip()

            # Support both postgres:// and postgresql:// schemes
            if database_url.startswith('postgres://'):
                # Convert postgres:// to postgresql+asyncpg://
                return database_url.replace('postgres://', 'postgresql+asyncpg://')
            elif database_url.startswith('postgresql://'):
                # Convert postgresql:// to postgresql+asyncpg://
                return database_url.replace('postgresql://', 'postgresql+asyncpg://')
            elif database_url.startswith('postgresql+asyncpg://'):
                # Already in correct format
                return database_url
            else:
                # Fallback: assume it's a valid connection string and add async driver
                logger.warning(f"Unrecognized DATABASE_URL format, attempting fallback: {database_url[:50]}...")
                if '://' in database_url:
                    return database_url.replace('://', '+asyncpg://', 1)
                else:
                    raise ValueError(f"Invalid DATABASE_URL format: {database_url[:100]}...")

        except Exception as e:
            logger.error(f"Error parsing DATABASE_URL: {e}")
            # Graceful fallback for development
            logger.warning("Using fallback database connection...")
            return "postgresql+asyncpg://postgres:password@localhost:5432/analytics"

    async def _test_pool_connection(self, engine, pool_name: str) -> None:
        """Test connection pool health"""
        try:
            async with engine.begin() as conn:
                # Use simple query that doesn't require prepared statements
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                logger.info(f"Pool {pool_name} connection test successful: {row}")
        except Exception as e:
            logger.error(f"Pool {pool_name} connection test failed: {e}")
            raise

    @asynccontextmanager
    async def get_user_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session optimized for user-facing operations"""
        if not self.initialized:
            await self.initialize_pools()

        session_maker = self.session_makers['user_api']
        async with session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"User session error: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_background_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session optimized for background operations"""
        if not self.initialized:
            await self.initialize_pools()

        session_maker = self.session_makers['background_workers']
        async with session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Background session error: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_ai_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session optimized for AI operations"""
        if not self.initialized:
            await self.initialize_pools()

        session_maker = self.session_makers['ai_workers']
        async with session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"AI session error: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_discovery_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session optimized for discovery operations"""
        if not self.initialized:
            await self.initialize_pools()

        session_maker = self.session_makers['discovery_workers']
        async with session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Discovery session error: {e}")
                raise
            finally:
                await session.close()

    async def get_pool_stats(self) -> Dict[str, Dict[str, any]]:
        """Get comprehensive pool statistics for monitoring"""
        stats = {}

        for pool_name, engine in self.pools.items():
            pool = engine.pool

            stats[pool_name] = {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'total_connections': pool.checkedin() + pool.checkedout(),
                'utilization_percent': round(
                    ((pool.checkedin() + pool.checkedout()) / pool.size()) * 100, 2
                ),
                'config': self.pool_config[pool_name]
            }

        return stats

    async def health_check(self) -> Dict[str, any]:
        """Comprehensive health check for all pools"""
        health_status = {
            'overall_healthy': True,
            'pools': {},
            'total_connections_used': 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        for pool_name in self.pools.keys():
            try:
                # Test connection
                if pool_name == 'user_api':
                    async with self.get_user_session() as session:
                        result = await session.execute(text("SELECT 1"))
                        result.scalar()
                elif pool_name == 'background_workers':
                    async with self.get_background_session() as session:
                        result = await session.execute(text("SELECT 1"))
                        result.scalar()
                elif pool_name == 'ai_workers':
                    async with self.get_ai_session() as session:
                        result = await session.execute(text("SELECT 1"))
                        result.scalar()
                elif pool_name == 'discovery_workers':
                    async with self.get_discovery_session() as session:
                        result = await session.execute(text("SELECT 1"))
                        result.scalar()

                health_status['pools'][pool_name] = {
                    'status': 'healthy',
                    'last_check': datetime.now(timezone.utc).isoformat()
                }

            except Exception as e:
                health_status['pools'][pool_name] = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
                health_status['overall_healthy'] = False

        # Get pool statistics
        pool_stats = await self.get_pool_stats()
        health_status['pool_stats'] = pool_stats

        # Calculate total connection usage
        health_status['total_connections_used'] = sum(
            stats['total_connections'] for stats in pool_stats.values()
        )

        return health_status

    async def cleanup_pools(self) -> None:
        """Cleanup all connection pools gracefully"""
        logger.info("Cleaning up connection pools...")

        for pool_name, engine in self.pools.items():
            try:
                await engine.dispose()
                logger.info(f"Pool {pool_name} disposed successfully")
            except Exception as e:
                logger.error(f"Error disposing pool {pool_name}: {e}")

        self.pools.clear()
        self.session_makers.clear()
        self.initialized = False

# Global optimized pools instance
optimized_pools = SupabaseOptimizedPools()

# Convenience functions for backward compatibility
async def get_user_db_session():
    """Get optimized session for user operations"""
    return optimized_pools.get_user_session()

async def get_background_db_session():
    """Get optimized session for background operations"""
    return optimized_pools.get_background_session()

async def get_ai_db_session():
    """Get optimized session for AI operations"""
    return optimized_pools.get_ai_session()

async def get_discovery_db_session():
    """Get optimized session for discovery operations"""
    return optimized_pools.get_discovery_session()