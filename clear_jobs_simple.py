"""Simple script to clear stuck jobs directly from database"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use DIRECT database URL (no pgbouncer) to avoid prepared statement issues
DATABASE_URL = os.getenv("DIRECT_DATABASE_URL", "")
if not DATABASE_URL:
    # Fallback to regular URL if DIRECT not available
    DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")
elif not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = f"postgresql+asyncpg://{DATABASE_URL.replace('postgresql://', '')}"

async def clear_jobs():
    print("Connecting to database...")

    # Create engine
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True
    )

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    try:
        async with async_session() as session:
            # Get all jobs (checking actual table columns)
            result = await session.execute(
                text("SELECT id, job_type, status, created_at FROM job_queue WHERE status IN ('queued', 'processing')")
            )
            jobs = result.fetchall()

            print(f"\nFound {len(jobs)} stuck jobs")

            for job in jobs:
                print(f"  Job {job[0]}: {job[1]} - {job[2]}")

            if jobs:
                # Update all stuck jobs to failed
                await session.execute(
                    text("""
                        UPDATE job_queue
                        SET status = 'failed',
                            error = 'Manually cleared - stuck in queue',
                            completed_at = NOW()
                        WHERE status IN ('queued', 'processing')
                    """)
                )
                await session.commit()
                print(f"\nCleared {len(jobs)} stuck jobs!")
            else:
                print("\nNo stuck jobs to clear!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(clear_jobs())