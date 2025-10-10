#!/usr/bin/env python3
"""
Fix location detection for existing profiles with Unicode text
Apply Unicode normalization to profiles that need location detection
"""

import asyncio
import sys
import os
sys.path.append(os.getcwd())

from app.services.location_detection_service import LocationDetectionService
from app.database.connection import get_db
from app.database.unified_models import Profile
from sqlalchemy import select, update
import unicodedata

async def fix_location_detection():
    """Fix location detection for profiles with Unicode text"""

    # Initialize services
    location_service = LocationDetectionService()

    async for db in get_db():
        # Get profiles without detected_country that have biography data
        query = select(Profile).where(
            Profile.detected_country.is_(None),
            Profile.biography.isnot(None),
            Profile.biography != ''
        )

        result = await db.execute(query)
        profiles = result.scalars().all()

        print(f"Found {len(profiles)} profiles without detected_country")

        updated_count = 0
        for profile in profiles:
            try:
                # Test if location can be detected from biography
                profile_data = {'biography': profile.biography}
                location_result = location_service.detect_country(profile_data)

                if location_result.get('country_code'):
                    print(f"Updating {profile.username}: {location_result['country_code']} (confidence: {location_result['confidence']})")

                    # Update the profile
                    update_query = (
                        update(Profile)
                        .where(Profile.id == profile.id)
                        .values(detected_country=location_result['country_code'])
                    )

                    await db.execute(update_query)
                    updated_count += 1

                    # Commit after each update
                    await db.commit()

            except Exception as e:
                print(f"Error processing {profile.username}: {e}")
                continue

        print(f"Successfully updated {updated_count} profiles")

if __name__ == "__main__":
    asyncio.run(fix_location_detection())