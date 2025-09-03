#!/usr/bin/env python3
"""
Run Comprehensive AI Analysis on Real Profile
Tests the enhanced AI analysis system on actual profile data
"""
import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database.connection import get_session, init_database
from app.workers.ai_background_worker import _async_analyze_profile_posts
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_comprehensive_analysis():
    """Run comprehensive AI analysis on a real profile"""
    logger.info("🚀 RUNNING COMPREHENSIVE AI ANALYSIS")
    logger.info("====================================")
    
    # Initialize database
    await init_database()
    
    async with get_session() as db:
        # Find moweeezy profile since it has unanalyzed posts
        profile_query = """
        SELECT id, username FROM profiles WHERE username = 'moweeezy' LIMIT 1;
        """
        
        result = await db.execute(text(profile_query))
        profile = result.fetchone()
        
        if not profile:
            logger.error("Profile 'moweeezy' not found")
            return
        
        logger.info(f"Running analysis on profile: {profile.username} ({profile.id})")
        
        # Check current unanalyzed posts
        posts_query = """
        SELECT COUNT(*) as unanalyzed_count
        FROM posts 
        WHERE profile_id = :profile_id AND ai_analyzed_at IS NULL;
        """
        
        result = await db.execute(text(posts_query), {'profile_id': profile.id})
        unanalyzed = result.fetchone()
        
        logger.info(f"Found {unanalyzed.unanalyzed_count} unanalyzed posts for {profile.username}")
        
        if unanalyzed.unanalyzed_count == 0:
            logger.info("No unanalyzed posts found. Analysis already complete!")
            return
        
        # Run the comprehensive analysis
        logger.info("\n🧠 Starting comprehensive AI analysis...")
        task_id = f"manual_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            result = await _async_analyze_profile_posts(
                str(profile.id), 
                profile.username, 
                task_id
            )
            
            logger.info(f"\n🎉 ANALYSIS COMPLETE!")
            logger.info(f"Posts analyzed: {result.get('posts_analyzed', 0)}")
            logger.info(f"Total posts found: {result.get('total_posts_found', 0)}")
            logger.info(f"Success rate: {result.get('batch_success_rate', 0):.1%}")
            logger.info(f"Profile insights updated: {result.get('profile_insights', False)}")
            logger.info(f"Task ID: {result.get('task_id')}")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
        
        # Check results
        logger.info(f"\n📊 POST-ANALYSIS VERIFICATION")
        
        analyzed_query = """
        SELECT 
            COUNT(*) as total_posts,
            COUNT(CASE WHEN ai_analyzed_at IS NOT NULL THEN 1 END) as analyzed_posts,
            COUNT(CASE WHEN ai_content_category IS NOT NULL THEN 1 END) as categorized_posts,
            COUNT(CASE WHEN ai_sentiment IS NOT NULL THEN 1 END) as sentiment_posts,
            COUNT(CASE WHEN ai_language_code IS NOT NULL THEN 1 END) as language_posts
        FROM posts 
        WHERE profile_id = :profile_id;
        """
        
        result = await db.execute(text(analyzed_query), {'profile_id': profile.id})
        stats = result.fetchone()
        
        logger.info(f"Total posts: {stats.total_posts}")
        logger.info(f"Analyzed posts: {stats.analyzed_posts}")
        logger.info(f"With categories: {stats.categorized_posts}")
        logger.info(f"With sentiment: {stats.sentiment_posts}")
        logger.info(f"With language: {stats.language_posts}")
        
        # Show sample analysis
        sample_query = """
        SELECT 
            caption,
            ai_content_category,
            ai_sentiment,
            ai_sentiment_score,
            ai_language_code,
            ai_analysis_version
        FROM posts 
        WHERE profile_id = :profile_id 
        AND ai_analyzed_at IS NOT NULL
        ORDER BY ai_analyzed_at DESC 
        LIMIT 3;
        """
        
        result = await db.execute(text(sample_query), {'profile_id': profile.id})
        samples = result.fetchall()
        
        logger.info(f"\n🎯 SAMPLE ANALYSIS RESULTS:")
        for i, sample in enumerate(samples, 1):
            caption = (sample.caption[:50] + "...") if sample.caption and len(sample.caption) > 50 else (sample.caption or "No caption")
            logger.info(f"{i}. Caption: {caption}")
            logger.info(f"   Category: {sample.ai_content_category} | Sentiment: {sample.ai_sentiment} ({sample.ai_sentiment_score:.3f})")
            logger.info(f"   Language: {sample.ai_language_code} | Version: {sample.ai_analysis_version}")
    
    logger.info(f"\n✅ COMPREHENSIVE AI ANALYSIS DEMONSTRATION COMPLETE")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_analysis())