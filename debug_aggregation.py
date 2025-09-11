#!/usr/bin/env python3
"""
Debug script to test profile AI aggregation logic
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

async def debug_aggregation_for_profile(username: str):
    """Debug aggregation for a specific profile"""
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
                return
            
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
                return
            
            # Debug: Show raw post data
            print("\n[DEBUG] Raw post AI data:")
            for i, post in enumerate(analyzed_posts[:5]):  # Show first 5 posts
                print(f"  Post {i+1}: category='{post.ai_content_category}', sentiment={post.ai_sentiment_score}, language='{post.ai_language_code}'")
            
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
            
            print(f"\n[AGGREGATION] Results:")
            print(f"  Category counts: {category_counts}")
            print(f"  Sentiment scores: {len(sentiment_scores)} scores, sample: {sentiment_scores[:3]}")
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
                primary_content_type = sorted_categories[0][0]  # Keep for backwards compatibility
                
                # Calculate percentages and build structured data
                for category, count in sorted_categories:
                    percentage = round((count / total_analyzed) * 100, 1)
                    content_distribution[category] = round(count / total_analyzed, 2)  # Keep for backwards compatibility
                    
                    category_data = {
                        "category": category,
                        "percentage": percentage,
                        "count": count,
                        "confidence": 0.85  # Default confidence for aggregated data
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
            
            print(f"\n[FINAL] Calculated Values:")
            print(f"  Primary content type: '{primary_content_type}'")
            print(f"  Content distribution: {content_distribution}")
            print(f"  Avg sentiment score: {avg_sentiment_score}")
            print(f"  Language distribution: {language_distribution}")
            print(f"  Top 3 categories: {ai_top_3_categories}")
            print(f"  Top 10 categories: {ai_top_10_categories}")
            
            # Test if values are being set correctly
            if not primary_content_type:
                print("[CRITICAL] PRIMARY_CONTENT_TYPE IS NULL!")
            if not content_distribution:
                print("[CRITICAL] CONTENT_DISTRIBUTION IS EMPTY!")
            if not language_distribution:
                print("[CRITICAL] LANGUAGE_DISTRIBUTION IS EMPTY!")
            
        except Exception as e:
            print(f"[ERROR] Error during aggregation: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Test with evekellyg since we know it has good AI data
    asyncio.run(debug_aggregation_for_profile("evekellyg"))