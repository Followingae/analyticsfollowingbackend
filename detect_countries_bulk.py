"""
Bulk Country Detection Script

Runs location detection on all existing profiles in the database
and updates them with detected countries.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
import asyncpg
import json
from typing import List, Dict, Any
from app.services.location_detection_service import LocationDetectionService
from app.core.config import settings

async def get_all_profiles():
    """Get all profiles from database"""
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        # Get profiles with their posts for content analysis
        query = """
        SELECT
            p.id,
            p.username,
            p.biography,
            p.detected_country,
            COALESCE(
                json_agg(
                    json_build_object('caption', posts.caption)
                    ORDER BY posts.created_at DESC
                ) FILTER (WHERE posts.id IS NOT NULL),
                '[]'::json
            ) as posts
        FROM profiles p
        LEFT JOIN posts ON posts.profile_id = p.id
        GROUP BY p.id, p.username, p.biography, p.detected_country
        ORDER BY p.username;
        """

        rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    finally:
        await conn.close()

async def update_profile_country(profile_id: str, country_code: str):
    """Update profile with detected country"""
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        await conn.execute(
            "UPDATE profiles SET detected_country = $1 WHERE id = $2",
            country_code, profile_id
        )
    finally:
        await conn.close()

async def run_bulk_detection():
    """Run location detection on all profiles"""
    print("Bulk Country Detection Starting...")
    print("=" * 50)

    # Initialize location service
    location_service = LocationDetectionService()

    # Get all profiles
    profiles = await get_all_profiles()
    print(f"Found {len(profiles)} profiles to process")

    results = []

    for i, profile in enumerate(profiles, 1):
        username = profile['username']
        biography = profile['biography'] or ""
        posts = profile['posts'] or []
        current_country = profile['detected_country']

        print(f"\n[{i}/{len(profiles)}] Processing @{username}")

        if current_country:
            print(f"  Already has country: {current_country}")
            results.append({
                'username': username,
                'country': current_country,
                'status': 'existing'
            })
            continue

        # Parse posts JSON if it's a string
        if isinstance(posts, str):
            try:
                posts = json.loads(posts)
            except:
                posts = []

        # Prepare data for location detection
        detection_data = {
            "biography": biography,
            "posts": posts,
            "audience_top_countries": []  # We don't have audience data yet
        }

        # Run detection
        try:
            result = location_service.detect_country(detection_data)
            detected_country = result['country_code']
            confidence = result['confidence']

            if detected_country:
                # Update database
                await update_profile_country(profile['id'], detected_country)
                print(f"  Detected: {detected_country} ({confidence:.1%})")

                results.append({
                    'username': username,
                    'country': detected_country,
                    'confidence': confidence,
                    'status': 'detected'
                })
            else:
                print(f"  No country detected")
                results.append({
                    'username': username,
                    'country': None,
                    'status': 'no_detection'
                })

        except Exception as e:
            print(f"  ERROR: {str(e)}")
            results.append({
                'username': username,
                'country': None,
                'status': 'error',
                'error': str(e)
            })

    # Print summary
    print("\n" + "=" * 50)
    print("BULK DETECTION SUMMARY")
    print("=" * 50)

    detected_count = sum(1 for r in results if r['status'] == 'detected')
    existing_count = sum(1 for r in results if r['status'] == 'existing')
    failed_count = len(results) - detected_count - existing_count

    print(f"Total Profiles: {len(results)}")
    print(f"Newly Detected: {detected_count}")
    print(f"Already Had Country: {existing_count}")
    print(f"Failed/No Detection: {failed_count}")

    print("\nDetailed Results:")
    for result in results:
        username = result['username']
        country = result['country'] or 'None'
        status = result['status']

        if status == 'detected':
            confidence = result.get('confidence', 0)
            print(f"  @{username:<15} -> {country} ({confidence:.1%})")
        elif status == 'existing':
            print(f"  @{username:<15} -> {country} (existing)")
        else:
            print(f"  @{username:<15} -> {country} ({status})")

    print("\nBulk country detection complete!")

if __name__ == "__main__":
    asyncio.run(run_bulk_detection())