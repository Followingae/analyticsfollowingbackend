#!/usr/bin/env python3
"""
Check location detection status across all profiles
"""
import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from app.database.connection import get_session, init_database
from sqlalchemy import text

async def check_location_detection_status():
    """Check location detection status and identify issues"""

    # Initialize database connection
    await init_database()

    async with get_session() as db:
        print("=== LOCATION DETECTION STATUS REPORT ===\n")

        # Overall statistics
        stats_query = text("""
            SELECT
                COUNT(*) as total_profiles,
                COUNT(detected_country) as profiles_with_detection,
                COUNT(CASE WHEN detected_country = 'FAILED' THEN 1 END) as failed_detections,
                COUNT(CASE WHEN detected_country = 'NONE' THEN 1 END) as no_location_found,
                COUNT(CASE WHEN detected_country NOT IN ('FAILED', 'NONE') AND detected_country IS NOT NULL THEN 1 END) as successful_detections
            FROM profiles
        """)

        result = await db.execute(stats_query)
        stats = result.fetchone()

        print("OVERALL STATISTICS:")
        print(f"  Total Profiles: {stats.total_profiles}")
        print(f"  Successful Detections: {stats.successful_detections}")
        print(f"  No Location Found: {stats.no_location_found}")
        print(f"  Failed Detections: {stats.failed_detections}")
        print(f"  Unprocessed (NULL): {stats.total_profiles - stats.profiles_with_detection}")
        print(f"  Success Rate: {(stats.successful_detections / stats.total_profiles * 100):.1f}%")
        print()

        # Profile details
        details_query = text("""
            SELECT username, detected_country,
                   CASE
                       WHEN biography LIKE '%Dubai%' OR biography LIKE '%UAE%' THEN 'UAE_KEYWORDS'
                       WHEN biography LIKE '%USA%' OR biography LIKE '%America%' THEN 'USA_KEYWORDS'
                       WHEN biography LIKE '%UK%' OR biography LIKE '%London%' THEN 'UK_KEYWORDS'
                       ELSE 'NO_OBVIOUS_KEYWORDS'
                   END as bio_signals,
                   LENGTH(biography) as bio_length
            FROM profiles
            ORDER BY
                CASE
                    WHEN detected_country IS NULL THEN 1
                    WHEN detected_country = 'FAILED' THEN 2
                    WHEN detected_country = 'NONE' THEN 3
                    ELSE 4
                END,
                username
        """)

        result = await db.execute(details_query)
        profiles = result.fetchall()

        print("PROFILE DETAILS:")
        for profile in profiles:
            status_symbol = {
                None: "[NULL]",
                'FAILED': "[FAILED]",
                'NONE': "[NONE]"
            }.get(profile.detected_country, f"[{profile.detected_country}]")

            bio_signal = profile.bio_signals.replace('_KEYWORDS', '')
            print(f"  {status_symbol} @{profile.username}: {profile.detected_country or 'NULL'} ({bio_signal}, {profile.bio_length} chars)")

        print()
        print("STATUS LEGEND:")
        print("  [COUNTRY_CODE] = Detected country code")
        print("  [NONE] = No location found")
        print("  [FAILED] = Detection failed")
        print("  [NULL] = Not processed")

if __name__ == "__main__":
    asyncio.run(check_location_detection_status())