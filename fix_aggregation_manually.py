#!/usr/bin/env python3
"""
Manually fix aggregation for profiles with analyzed posts but null aggregation
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from datetime import datetime, timezone

from app.database.unified_models import Profile, Post
from app.database.connection import get_database_url

async def fix_profile_aggregation(username: str):
    """Fix aggregation for a specific profile"""
    # Database setup
    database_url = get_database_url()
    if not database_url.startswith('postgresql+asyncpg'):
        database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    engine = create_async_engine(database_url, echo=False)
    async_session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_factory() as db:
        try:
            # Get the profile
            profile_query = select(Profile).where(Profile.username == username)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()
            
            if not profile:
                print(f"[ERROR] Profile {username} not found")
                return False
            
            print(f"[OK] Found profile: {profile.username} (ID: {profile.id})")
            
            # Get all analyzed posts for this profile
            analyzed_posts_query = select(Post).where(
                Post.profile_id == profile.id,
                Post.ai_analyzed_at.isnot(None)
            )
            
            posts_result = await db.execute(analyzed_posts_query)
            analyzed_posts = posts_result.scalars().all()
            
            print(f"[INFO] Found {len(analyzed_posts)} analyzed posts")
            
            if not analyzed_posts:
                print("[ERROR] No analyzed posts found")
                return False
            
            # Calculate aggregated insights (same logic as worker)
            category_counts = {}
            sentiment_scores = []
            language_counts = {}
            
            for post in analyzed_posts:
                # Category distribution
                if post.ai_content_category:
                    category_counts[post.ai_content_category] = category_counts.get(post.ai_content_category, 0) + 1
                
                # Sentiment scores
                if post.ai_sentiment_score is not None:
                    sentiment_scores.append(float(post.ai_sentiment_score))
                
                # Language distribution
                if post.ai_language_code:
                    language_counts[post.ai_language_code] = language_counts.get(post.ai_language_code, 0) + 1
            
            total_analyzed = len(analyzed_posts)
            
            print(f"[AGGREGATION] Results:")
            print(f"  Category counts: {category_counts}")
            print(f"  Language counts: {language_counts}")
            print(f"  Total analyzed: {total_analyzed}")
            
            # Calculate insights
            primary_content_type = None
            content_distribution = {}
            ai_top_3_categories = []
            ai_top_10_categories = []
            
            if category_counts:
                # Sort categories by count (descending)
                sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
                primary_content_type = sorted_categories[0][0]
                
                # Calculate percentages and build structured data
                for category, count in sorted_categories:
                    percentage = round((count / total_analyzed) * 100, 1)
                    content_distribution[category] = round(count / total_analyzed, 2)
                    
                    category_data = {
                        "category": category,
                        "percentage": percentage,
                        "count": count,
                        "confidence": 0.85
                    }
                    
                    # Add to appropriate lists
                    if len(ai_top_3_categories) < 3:
                        ai_top_3_categories.append(category_data)
                    if len(ai_top_10_categories) < 10:
                        ai_top_10_categories.append(category_data)
            
            avg_sentiment_score = 0.0
            if sentiment_scores:
                avg_sentiment_score = round(sum(sentiment_scores) / len(sentiment_scores), 3)
            
            language_distribution = {}
            if language_counts:
                language_distribution = {
                    lang: round(count / total_analyzed, 2)
                    for lang, count in language_counts.items()
                }
            
            # Content quality score calculation
            content_quality_score = 0.0
            if sentiment_scores:
                sentiment_contribution = max(0, (avg_sentiment_score + 1) / 2)
                content_quality_score += sentiment_contribution * 0.4
                
                if content_distribution:
                    max_category_ratio = max(content_distribution.values())
                    content_quality_score += max_category_ratio * 0.3
                
                coverage_score = min(1.0, total_analyzed / max(1, total_analyzed))
                content_quality_score += coverage_score * 0.3
                content_quality_score = round(content_quality_score, 3)
            else:
                content_quality_score = 0.5  # Default
            
            print(f"[FINAL] Calculated Values:")
            print(f"  Primary content type: '{primary_content_type}'")
            print(f"  Content distribution: {content_distribution}")
            print(f"  Avg sentiment score: {avg_sentiment_score}")
            print(f"  Language distribution: {language_distribution}")
            print(f"  Content quality score: {content_quality_score}")
            
            # Update profile with insights
            print(f"[UPDATE] Updating database for {username}...")
            update_result = await db.execute(
                update(Profile)
                .where(Profile.id == profile.id)
                .values(
                    ai_primary_content_type=primary_content_type,
                    ai_content_distribution=content_distribution,
                    ai_avg_sentiment_score=avg_sentiment_score,
                    ai_language_distribution=language_distribution,
                    ai_content_quality_score=content_quality_score,
                    ai_profile_analyzed_at=datetime.now(timezone.utc),
                    ai_top_3_categories=ai_top_3_categories if ai_top_3_categories else None,
                    ai_top_10_categories=ai_top_10_categories if ai_top_10_categories else None
                )
            )
            
            print(f"[UPDATE] Database update result: {update_result.rowcount} rows affected")
            await db.commit()
            
            print(f"[SUCCESS] Fixed aggregation for {username}!")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error during aggregation fix: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    """Fix aggregation for profiles with analyzed posts but null aggregation"""
    profiles_to_fix = ["manaryouness5", "evekellyg"]
    
    for username in profiles_to_fix:
        print(f"\n{'='*60}")
        print(f"FIXING AGGREGATION FOR: {username}")
        print(f"{'='*60}")
        
        success = await fix_profile_aggregation(username)
        if success:
            print(f"[SUCCESS] {username} aggregation fixed!")
        else:
            print(f"[FAILED] {username} aggregation fix failed!")

if __name__ == "__main__":
    asyncio.run(main())