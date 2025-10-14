#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_discovery_profiles():
    try:
        from app.database.connection import init_database, get_session
        from sqlalchemy import select, text

        print("Initializing database connection...")
        await init_database()

        async with get_session() as db:
            print("\n=== CHECKING DISCOVERED PROFILES ===")

            # Check for aishaharib and ahmadalshugairi
            query = text("""
                SELECT
                    username,
                    followers_count,
                    posts_count,
                    ai_profile_analyzed_at,
                    ai_primary_content_type,
                    ai_content_distribution,
                    profile_pic_url IS NOT NULL as has_profile_pic,
                    LENGTH(profile_pic_url) as pic_url_length,
                    created_at,
                    updated_at
                FROM profiles
                WHERE username IN ('aishaharib', 'ahmadalshugairi')
                ORDER BY created_at DESC;
            """)

            result = await db.execute(query)
            profiles = result.fetchall()

            for profile in profiles:
                print(f"\nPROFILE: @{profile.username}")
                print(f"   Followers: {profile.followers_count:,}")
                print(f"   Posts: {profile.posts_count:,}")
                print(f"   AI Analyzed: {'YES' if profile.ai_profile_analyzed_at else 'NO'}")
                print(f"   AI Content Type: {profile.ai_primary_content_type or 'Not analyzed'}")
                print(f"   AI Distribution: {'Available' if profile.ai_content_distribution else 'None'}")
                print(f"   Profile Pic: {'Available' if profile.has_profile_pic else 'None'}")
                if profile.has_profile_pic:
                    print(f"   Pic URL Length: {profile.pic_url_length}")
                print(f"   Created: {profile.created_at}")
                print(f"   Updated: {profile.updated_at}")

            # Check posts for these profiles
            print(f"\n=== CHECKING POSTS ===")
            posts_query = text("""
                SELECT
                    p.username,
                    COUNT(posts.id) as total_posts,
                    COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as ai_analyzed_posts,
                    COUNT(CASE WHEN posts.cdn_thumbnail_url IS NOT NULL THEN 1 END) as cdn_processed_posts
                FROM profiles p
                LEFT JOIN posts ON p.id = posts.profile_id
                WHERE p.username IN ('aishaharib', 'ahmadalshugairi')
                GROUP BY p.username
                ORDER BY p.username;
            """)

            result = await db.execute(posts_query)
            posts_data = result.fetchall()

            for post_data in posts_data:
                print(f"\nPOSTS for @{post_data.username}:")
                print(f"   Total Posts: {post_data.total_posts}")
                print(f"   AI Analyzed: {post_data.ai_analyzed_posts}")
                print(f"   CDN Processed: {post_data.cdn_processed_posts}")

                # Calculate completeness
                if post_data.total_posts > 0:
                    ai_percent = (post_data.ai_analyzed_posts / post_data.total_posts) * 100
                    cdn_percent = (post_data.cdn_processed_posts / post_data.total_posts) * 100
                    print(f"   AI Progress: {ai_percent:.1f}%")
                    print(f"   CDN Progress: {cdn_percent:.1f}%")

                    if ai_percent == 100 and cdn_percent == 100:
                        print(f"   STATUS: COMPLETE")
                    else:
                        print(f"   STATUS: PROCESSING...")

        print(f"\n=== CHECK COMPLETE ===")

    except Exception as e:
        print(f"Error checking profiles: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_discovery_profiles())