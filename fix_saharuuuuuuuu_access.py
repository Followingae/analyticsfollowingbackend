#!/usr/bin/env python3
"""
EMERGENCY FIX: Grant access to saharuuuuuuuu for the user who was charged credits
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

from app.database.connection import get_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def fix_access():
    """Grant access to saharuuuuuuuu for the user who was charged"""
    engine = get_async_engine()

    async with AsyncSession(engine) as db:
        try:
            # Insert the missing user_profile_access record
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
                "user_id": "99b1001b-69a0-4d75-9730-3177ba42c642",  # client@analyticsfollowing.com
                "profile_id": "b041f8cf-725d-4301-8217-d9ce2418b31a",  # saharuuuuuuuu
                "granted_at": now,
                "expires_at": now + timedelta(days=30),
                "created_at": now
            })

            await db.commit()

            print("✅ SUCCESS: Access granted to saharuuuuuuuu for client@analyticsfollowing.com")
            print(f"✅ Access Record ID: {access_id}")
            print(f"✅ Expires: {(now + timedelta(days=30)).isoformat()}")

        except Exception as e:
            await db.rollback()
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(fix_access())