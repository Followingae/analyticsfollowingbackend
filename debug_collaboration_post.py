#!/usr/bin/env python3
"""
Debug script to test collaboration post processing
"""

import asyncio
import sys
import os
sys.path.append('.')

from app.services.standalone_post_analytics_service import standalone_post_analytics_service
from app.database.connection import get_session, init_database
from app.database.unified_models import User
from sqlalchemy import select
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_collaboration_post():
    # Initialize database first
    await init_database()
    """Test the collaboration post processing"""

    # Test post URL
    post_url = "https://www.instagram.com/reel/DN-O5tODA7m/"

    print(f"Testing collaboration post: {post_url}")

    try:
        # Get a user ID (use the admin user)
        async with get_session() as db:
            result = await db.execute(
                select(User).where(User.email == "zain@following.ae")
            )
            user = result.scalar_one_or_none()

            if not user:
                print("ERROR: Admin user not found!")
                return

            print(f"SUCCESS: Using user: {user.email} (ID: {user.id})")

            # Test the post analytics service
            print(f"INFO: Analyzing post...")
            result = await standalone_post_analytics_service.analyze_post_by_url(
                post_url=post_url,
                db=db,
                user_id=user.id
            )

            print(f"SUCCESS: Analysis complete!")
            print(f"RESULT: Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

            if isinstance(result, dict) and 'collaborators' in result:
                print(f"COLLABORATORS: Collaborators found: {result.get('collaborators', [])}")
            else:
                print(f"WARNING: No collaborators field in result")

    except Exception as e:
        print(f"ERROR: Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_collaboration_post())