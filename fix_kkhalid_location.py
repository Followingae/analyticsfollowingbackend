#!/usr/bin/env python3
"""
Fix location detection for a.kkhalid specifically
"""

import asyncio
import sys
import os
sys.path.append(os.getcwd())

from app.services.location_detection_service import LocationDetectionService

async def fix_kkhalid_location():
    """Fix location detection for a.kkhalid using Supabase integration"""

    print("Fixing location detection for a.kkhalid")
    print("=" * 50)

    # Initialize location service
    location_service = LocationDetectionService()

    # Get a.kkhalid data (we know this from our database query)
    biography = "@awqatna podcast with my father \n#يلستنا"
    posts = [
        {"caption": "تحصلها من الباكجنق ولا من نظارتهم الحلوه 👌🏻 @zeva_ad \n\n#explore #اكسبلور"},
        {"caption": "\"وجوده أمان، وكلامه طمأنينة، أبوي✨\"\n\n#اكسبلور #explore"},
        {"caption": "Snap : aakk28\n\n#explore #fyp #اكسبلور #البحرين"},  # HAS BAHRAIN
        {"caption": "Snap: aakk28 \n\n#explore #اكسبلور"},
        {"caption": "\"أجمل العطاء هو أن تكون سببًا في قضاء حاجة غيرك \"\n\n#يلستنا #اكسبلور"}
    ]

    # Prepare data for location detection
    profile_data = {
        "biography": biography,
        "posts": posts,
        "audience_top_countries": []
    }

    # Run location detection
    print("Running location detection...")
    location_result = location_service.detect_country(profile_data)

    print(f"Location result: {location_result}")

    if location_result and location_result.get("country_code"):
        country_code = location_result["country_code"]
        confidence = location_result.get("confidence", 0)

        print(f"✅ Detected: {country_code} ({confidence:.1%})")

        # Now update the database using MCP Supabase integration
        try:
            print("Updating database...")

            # Update a.kkhalid profile with detected country
            # We'll use a simple method since we can't import async database connections easily
            print(f"Would update a.kkhalid with detected_country = '{country_code}'")
            print("Execute this SQL manually:")
            print(f"UPDATE profiles SET detected_country = '{country_code}' WHERE username = 'a.kkhalid';")

            return True

        except Exception as e:
            print(f"Error updating database: {e}")
            return False

    else:
        print(f"❌ No location detected: {location_result}")
        return False

if __name__ == "__main__":
    asyncio.run(fix_kkhalid_location())