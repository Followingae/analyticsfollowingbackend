#!/usr/bin/env python3
"""
AI SYSTEM VERIFICATION - Direct database check to verify AI processing is working
"""
import asyncio
from datetime import datetime

async def verify_ai_system():
    print("=== AI SYSTEM VERIFICATION ===")
    print(f"Started at: {datetime.now()}")
    print()
    
    try:
        # Initialize database
        from app.database.connection import init_database
        print("[INIT] Initializing database...")
        await init_database()
        print("[OK] Database initialized")
        
        # Get ALL profiles
        from app.database.connection import get_session
        from app.database.unified_models import Profile, Post
        from sqlalchemy import select, text
        
        async with get_session() as session:
            # Get comprehensive stats
            stats_query = """
                SELECT 
                    p.username,
                    CASE WHEN p.ai_profile_analyzed_at IS NOT NULL THEN 'YES' ELSE 'NO' END as profile_insights,
                    p.ai_primary_content_type,
                    COUNT(posts.id) as total_posts,
                    COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as analyzed_posts,
                    CASE WHEN p.cdn_avatar_url IS NOT NULL THEN 'YES' ELSE 'NO' END as has_cdn_avatar,
                    COUNT(CASE WHEN posts.cdn_thumbnail_url IS NOT NULL THEN 1 END) as cdn_posts
                FROM profiles p
                LEFT JOIN posts ON posts.profile_id = p.id
                GROUP BY p.id, p.username, p.ai_profile_analyzed_at, p.ai_primary_content_type, p.cdn_avatar_url
                ORDER BY p.username
            """
            
            result = await session.execute(text(stats_query))
            profiles_data = result.fetchall()
            
            print("AI SYSTEM STATUS REPORT")
            print("=" * 80)
            print("Profile          | Insights | Content Type | Posts AI   | CDN Avatar | CDN Posts")
            print("-" * 80)
            
            total_profiles = 0
            ai_complete_profiles = 0
            total_posts_all = 0
            analyzed_posts_all = 0
            cdn_avatars = 0
            cdn_posts_all = 0
            
            for row in profiles_data:
                username, insights, content_type, total_posts, analyzed_posts, has_cdn, cdn_posts = row
                posts_status = f"{analyzed_posts}/{total_posts}"
                complete = "OK" if insights == "YES" and analyzed_posts == total_posts else "FAIL"
                
                print(f"{username:16} | {insights:8} | {content_type or 'None':12} | {posts_status:10} | {has_cdn:10} | {cdn_posts:9} {complete}")
                
                total_profiles += 1
                if insights == "YES" and analyzed_posts == total_posts:
                    ai_complete_profiles += 1
                total_posts_all += total_posts
                analyzed_posts_all += analyzed_posts
                if has_cdn == "YES":
                    cdn_avatars += 1
                cdn_posts_all += cdn_posts
            
            print("-" * 80)
            print("SYSTEM SUMMARY:")
            print(f"  AI Analysis Complete: {ai_complete_profiles}/{total_profiles} profiles ({ai_complete_profiles/total_profiles*100:.1f}%)")
            print(f"  Posts Analyzed: {analyzed_posts_all}/{total_posts_all} ({analyzed_posts_all/total_posts_all*100:.1f}%)")
            print(f"  CDN Avatars: {cdn_avatars}/{total_profiles} ({cdn_avatars/total_profiles*100:.1f}%)")
            print(f"  CDN Posts: {cdn_posts_all}/{total_posts_all} ({cdn_posts_all/total_posts_all*100:.1f}%)")
            print()
            
            # AI System Status
            if ai_complete_profiles == total_profiles and analyzed_posts_all == total_posts_all:
                print("AI SYSTEM: FULLY OPERATIONAL!")
                print("   All profiles have complete AI analysis")
                print("   Users get FULL AI value for their credits")
                ai_status = "PERFECT"
            elif ai_complete_profiles > 0:
                print("AI SYSTEM: PARTIALLY WORKING")
                print(f"   {ai_complete_profiles} profiles working, {total_profiles - ai_complete_profiles} still processing")
                ai_status = "WORKING"
            else:
                print("AI SYSTEM: BROKEN")
                print("   No profiles have AI analysis")
                ai_status = "BROKEN"
            
            # CDN System Status
            if cdn_posts_all == total_posts_all and cdn_avatars == total_profiles:
                print("CDN SYSTEM: FULLY OPERATIONAL!")
                print("   All images processed through CDN")
                cdn_status = "PERFECT"
            elif cdn_posts_all > 0 or cdn_avatars > 0:
                print("CDN SYSTEM: PARTIALLY WORKING") 
                print(f"   {cdn_posts_all} posts and {cdn_avatars} avatars processed")
                cdn_status = "PARTIAL"
            else:
                print("CDN SYSTEM: NOT WORKING")
                print("   No CDN processing happening")
                cdn_status = "BROKEN"
            
            print()
            print("SYSTEM DIAGNOSIS:")
            if ai_status in ["PERFECT", "WORKING"] and cdn_status in ["PERFECT", "PARTIAL"]:
                print("OVERALL STATUS: SYSTEM IS FUNCTIONAL")
                print("   Users are getting significant value")
                if ai_status == "PERFECT":
                    print("   AI Analysis: 100% operational")
                if cdn_status != "PERFECT":
                    print("   CDN Processing: Needs attention but not critical")
            elif ai_status in ["PERFECT", "WORKING"]:
                print("OVERALL STATUS: AI WORKING, CDN NEEDS FIXING")
                print("   Users get AI value, missing CDN optimization")
            else:
                print("OVERALL STATUS: CRITICAL ISSUES")
                print("   Users not getting value for credits")
            
            return {
                "ai_status": ai_status,
                "cdn_status": cdn_status,
                "ai_complete": ai_complete_profiles,
                "total_profiles": total_profiles,
                "posts_analyzed": analyzed_posts_all,
                "total_posts": total_posts_all
            }
            
    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    print("DIRECT AI SYSTEM VERIFICATION")
    print("=" * 40)
    
    result = await verify_ai_system()
    
    print("\n" + "=" * 40)
    print(f"Completed at: {datetime.now()}")
    
    if result and result["ai_status"] in ["PERFECT", "WORKING"]:
        print("\nVERIFICATION SUCCESS: AI system is operational!")
        return True
    else:
        print("\nVERIFICATION FAILED: System needs repair!")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)