#!/usr/bin/env python3
"""
Grant access to fai.s.a.l profile for admin user to test full response structure
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid

# Add the app directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from app.database.connection import async_engine, init_database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def grant_access():
    """Grant access to fai.s.a.l for the admin user"""
    # Initialize database connection
    await init_database()
    engine = async_engine

    async with AsyncSession(engine) as db:
        try:
            # Insert the user_profile_access record
            access_insert = text("""
                INSERT INTO user_profile_access (
                    id, user_id, profile_id, granted_at, expires_at, created_at
                ) VALUES (
                    :access_id,
                    :user_id,
                    :profile_id,
                    :granted_at,
                    :expires_at,
                    :created_at
                )
            """)

            now = datetime.now(timezone.utc)
            access_id = str(uuid.uuid4())

            await db.execute(access_insert, {
                "access_id": access_id,
                "user_id": "11107e3c-01e1-4f19-bdd9-d0e22b7c3288",  # zain@following.ae (admin)
                "profile_id": "2b473d06-c407-4071-bd72-2e6414f249d8",  # fai.s.a.l
                "granted_at": now,
                "expires_at": now + timedelta(days=30),
                "created_at": now
            })

            await db.commit()

            print("✅ SUCCESS: Access granted to fai.s.a.l for zain@following.ae")
            print(f"✅ Access Record ID: {access_id}")
            print(f"✅ Expires: {(now + timedelta(days=30)).isoformat()}")

        except Exception as e:
            await db.rollback()
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(grant_access())