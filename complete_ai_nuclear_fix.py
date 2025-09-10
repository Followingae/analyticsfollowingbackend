#!/usr/bin/env python3
"""
COMPLETE AI NUCLEAR FIX: Process ALL profiles and ALL posts completely
No timeouts, no partial processing - COMPLETE SYSTEM REPAIR
"""
import sys
import asyncio
from datetime import datetime

async def complete_all_profiles():
    print("=== COMPLETE AI NUCLEAR FIX ===")
    print("Processing ALL profiles and ALL posts - NO COMPROMISES")
    
    try:
        # Initialize database
        from app.database.connection import init_database
        print("[INIT] Initializing database...")
        await init_database()
        print("[OK] Database initialized")
        
        # Get ALL profiles without complete AI analysis
        from app.database.connection import get_session
        from app.database.unified_models import Profile, Post
        from sqlalchemy import select
        
        async with get_session() as session:
            # Get ALL profiles
            profiles_query = select(Profile)
            profiles_result = await session.execute(profiles_query)
            all_profiles = profiles_result.scalars().all()
            
            print(f"[TARGET] Found {len(all_profiles)} total profiles")
            
            # Process each profile completely
            for i, profile in enumerate(all_profiles, 1):
                print(f"\n[PROFILE {i}/{len(all_profiles)}] Processing: {profile.username}")
                
                # Count unanalyzed posts
                unanalyzed_query = select(Post).where(
                    Post.profile_id == profile.id,
                    Post.ai_analyzed_at.is_(None)
                )
                unanalyzed_result = await session.execute(unanalyzed_query)
                unanalyzed_posts = unanalyzed_result.scalars().all()
                
                # Count total posts
                total_query = select(Post).where(Post.profile_id == profile.id)
                total_result = await session.execute(total_query)
                total_posts = total_result.scalars().all()
                
                print(f"   Total posts: {len(total_posts)}")
                print(f"   Unanalyzed posts: {len(unanalyzed_posts)}")
                print(f"   Profile insights: {profile.ai_profile_analyzed_at}")
                
                if len(unanalyzed_posts) > 0 or not profile.ai_profile_analyzed_at:
                    print(f"   [PROCESSING] Running complete AI analysis...")
                    
                    # Import and run AI analysis
                    from app.workers.ai_background_worker import _async_analyze_profile_posts
                    
                    task_id = f"nuclear-{profile.username}-{datetime.now().strftime('%H%M%S')}"
                    
                    try:
                        result = await _async_analyze_profile_posts(
                            str(profile.id), 
                            profile.username, 
                            task_id
                        )
                        
                        print(f"   [RESULT] Success: {result.get('success')}")
                        print(f"   [RESULT] Posts analyzed: {result.get('posts_analyzed', 0)}")
                        print(f"   [RESULT] Profile insights: {result.get('profile_insights', False)}")
                        
                        # Verify results
                        await session.refresh(profile)
                        
                        # Count analyzed posts after processing
                        analyzed_query = select(Post).where(
                            Post.profile_id == profile.id,
                            Post.ai_analyzed_at.isnot(None)
                        )
                        analyzed_result = await session.execute(analyzed_query)
                        analyzed_posts = analyzed_result.scalars().all()
                        
                        print(f"   [VERIFY] Profile insights: {'YES' if profile.ai_profile_analyzed_at else 'NO'}")
                        print(f"   [VERIFY] Content type: {profile.ai_primary_content_type}")
                        print(f"   [VERIFY] Posts analyzed: {len(analyzed_posts)}/{len(total_posts)}")
                        
                        if len(analyzed_posts) != len(total_posts):
                            print(f"   [WARNING] Not all posts analyzed! {len(analyzed_posts)}/{len(total_posts)}")
                        
                        if not profile.ai_profile_analyzed_at:
                            print(f"   [CRITICAL] Profile insights still missing!")
                        
                    except Exception as e:
                        print(f"   [ERROR] Failed to analyze {profile.username}: {e}")
                        import traceback
                        traceback.print_exc()
                
                else:
                    print(f"   [SKIP] Already fully analyzed")
            
            print(f"\n[COMPLETE] Processed all {len(all_profiles)} profiles")
            
            # Final verification
            print("\n=== FINAL VERIFICATION ===")
            final_stats_query = """
                SELECT 
                    p.username,
                    CASE WHEN p.ai_profile_analyzed_at IS NOT NULL THEN 'YES' ELSE 'NO' END as profile_insights,
                    p.ai_primary_content_type,
                    COUNT(posts.id) as total_posts,
                    COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as analyzed_posts
                FROM profiles p
                LEFT JOIN posts ON posts.profile_id = p.id
                GROUP BY p.id, p.username, p.ai_profile_analyzed_at, p.ai_primary_content_type
                ORDER BY p.username
            """
            
            from sqlalchemy import text
            final_result = await session.execute(text(final_stats_query))
            final_stats = final_result.fetchall()
            
            print("Profile | Insights | Content Type | Posts Analyzed")
            print("-" * 60)
            
            total_profiles = 0
            complete_profiles = 0
            total_posts_all = 0
            analyzed_posts_all = 0
            
            for row in final_stats:
                username, insights, content_type, total_posts, analyzed_posts = row
                completion = f"{analyzed_posts}/{total_posts}"
                complete = "✅" if insights == "YES" and analyzed_posts == total_posts else "❌"
                
                print(f"{username:12} | {insights:8} | {content_type or 'None':12} | {completion:8} {complete}")
                
                total_profiles += 1
                if insights == "YES" and analyzed_posts == total_posts:
                    complete_profiles += 1
                total_posts_all += total_posts
                analyzed_posts_all += analyzed_posts
            
            print("-" * 60)
            print(f"SUMMARY:")
            print(f"  Complete Profiles: {complete_profiles}/{total_profiles} ({complete_profiles/total_profiles*100:.1f}%)")
            print(f"  Posts Analyzed: {analyzed_posts_all}/{total_posts_all} ({analyzed_posts_all/total_posts_all*100:.1f}%)")
            
            success = complete_profiles == total_profiles and analyzed_posts_all == total_posts_all
            
            if success:
                print(f"NUCLEAR FIX: COMPLETE SUCCESS!")
                print(f"   ALL profiles have complete AI analysis")
                print(f"   ALL posts have been processed") 
                print(f"   Users will now get FULL value for their credits")
            else:
                print(f"NUCLEAR FIX: INCOMPLETE!")
                print(f"   {total_profiles - complete_profiles} profiles still missing insights")
                print(f"   {total_posts_all - analyzed_posts_all} posts still unanalyzed")
            
            return success
            
    except Exception as e:
        print(f"[CRITICAL ERROR] Nuclear fix failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("COMPLETE AI NUCLEAR FIX - TOTAL SYSTEM REPAIR")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print("Processing ALL profiles and ALL posts completely")
    print("=" * 60)
    
    success = await complete_all_profiles()
    
    print("\n" + "=" * 60)
    if success:
        print("MISSION ACCOMPLISHED: System fully repaired!")
    else:
        print("MISSION FAILED: System still has critical issues!")
    
    print(f"Completed at: {datetime.now()}")
    print("=" * 60)

if __name__ == "__main__":
    # Set no timeout - let it complete fully
    asyncio.run(main())