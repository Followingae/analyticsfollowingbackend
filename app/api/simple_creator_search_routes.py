"""
Simple Creator Search Routes
Basic single-stage creator search without complex background processing
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging
import asyncio
from datetime import datetime, timezone

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_active_user
from app.scrapers.enhanced_decodo_client import EnhancedDecodoClient
from app.database.comprehensive_service import ComprehensiveDataService
from app.services.robust_creator_search_service import robust_creator_search_service
from app.models.auth import UserInDB

router = APIRouter(prefix="/api/v1/simple", tags=["Simple Creator Search"])
logger = logging.getLogger(__name__)

@router.post("/creator/search/{username}")
async def simple_creator_search(
    username: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Simple creator search - single stage, no background processing
    """
    try:
        logger.info(f"Simple creator search: {username}")
        
        # 1. Fetch from Decodo
        from app.core.config import settings
        async with EnhancedDecodoClient(
            settings.SMARTPROXY_USERNAME,
            settings.SMARTPROXY_PASSWORD
        ) as decodo_client:
            decodo_data = await decodo_client.get_instagram_profile_comprehensive(username)
        
        if not decodo_data:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # 2. Store in database
        comprehensive_service = ComprehensiveDataService()
        profile, is_new = await comprehensive_service.store_complete_profile(
            db, username, decodo_data
        )
        
        # 2.5. RUN AI ANALYSIS (synchronously - no background tasks)
        from app.services.ai.bulletproof_content_intelligence import BulletproofContentIntelligence
        from sqlalchemy import select
        from app.database.unified_models import Profile, Post
        
        # Use the profile returned from store_complete_profile
        
        # Get posts that need AI analysis
        posts_query = select(Post).where(
            Post.profile_id == profile.id,
            Post.ai_analyzed_at.is_(None)
        ).limit(12)
        posts_result = await db.execute(posts_query)
        unanalyzed_posts = posts_result.scalars().all()
        
        # Run AI analysis if needed
        if unanalyzed_posts:
            logger.info(f"Running AI analysis for {len(unanalyzed_posts)} posts")
            ai_service = BulletproofContentIntelligence()
            
            # Process posts in batch
            posts_data = [
                {
                    'id': str(post.id),
                    'caption': post.caption,
                    'likes_count': post.likes_count,
                    'comments_count': post.comments_count
                }
                for post in unanalyzed_posts
            ]
            
            # Run AI analysis
            ai_batch_result = await ai_service.batch_analyze_posts(posts_data)
            
            # Extract individual results from batch response
            ai_results = ai_batch_result.get('batch_results', []) if ai_batch_result else []
            
            # Update posts with AI results
            for post, result in zip(unanalyzed_posts, ai_results):
                if result.get('success'):
                    analysis = result.get('analysis', {})
                    
                    # Assign all AI fields with proper type handling and defaults
                    post.ai_content_category = analysis.get('ai_content_category')
                    post.ai_category_confidence = float(analysis.get('ai_category_confidence', 0.0))
                    post.ai_sentiment = analysis.get('ai_sentiment')
                    post.ai_sentiment_score = float(analysis.get('ai_sentiment_score', 0.0))
                    post.ai_sentiment_confidence = float(analysis.get('ai_sentiment_confidence', 0.0))
                    post.ai_language_code = analysis.get('ai_language_code')
                    post.ai_language_confidence = float(analysis.get('ai_language_confidence', 0.0))
                    post.ai_analysis_raw = analysis.get('ai_analysis_raw')
                    post.ai_analysis_version = analysis.get('ai_analysis_version', '2.0_bulletproof')
                    
                    # Convert ISO string to datetime object
                    analyzed_at_str = analysis.get('ai_analyzed_at')
                    if analyzed_at_str:
                        try:
                            post.ai_analyzed_at = datetime.fromisoformat(analyzed_at_str.replace('Z', '+00:00'))
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Failed to parse ai_analyzed_at '{analyzed_at_str}': {e}")
                            post.ai_analyzed_at = datetime.now(timezone.utc)
                    else:
                        post.ai_analyzed_at = datetime.now(timezone.utc)
                else:
                    # Mark as analyzed even if failed to prevent re-processing
                    post.ai_analyzed_at = datetime.now(timezone.utc)
                    logger.warning(f"AI analysis failed for post {post.id}: {result.get('error', 'Unknown error')}")
            
            await db.commit()
            
            # Update profile AI aggregates
            await ai_service.update_profile_aggregates(db, profile.id)
            await db.commit()
            
            logger.info(f"AI analysis completed for {username}")
        
        # 3. Get profile from database with AI data
        from sqlalchemy import select, text
        from app.database.unified_models import Profile
        
        profile_query = select(Profile).where(Profile.username == username)
        profile_result = await db.execute(profile_query)
        profile = profile_result.scalar_one_or_none()
        
        # 4. Get CDN URLs for profile media
        from app.services.cdn_image_service import CDNImageService
        cdn_service = CDNImageService()
        cdn_service.set_db_session(db)  # Inject database session
        cdn_media = await cdn_service.get_profile_media_urls(profile.id)
        
        # 5. Get posts with AI analysis and CDN URLs
        posts_query = text("""
            SELECT instagram_post_id, caption, likes_count, comments_count, display_url,
                   ai_content_category, ai_category_confidence, ai_sentiment, 
                   ai_sentiment_score, ai_language_code, ai_language_confidence
            FROM posts 
            WHERE profile_id = :profile_id 
            ORDER BY created_at DESC 
            LIMIT 12
        """)
        
        posts_result = await db.execute(posts_query, {"profile_id": profile.id})
        posts_raw = posts_result.fetchall()
        
        # Map posts with CDN URLs
        posts_with_ai = []
        for i, row in enumerate(posts_raw):
            post_data = {
                "id": row[0],
                "caption": row[1],
                "likes_count": row[2],
                "comments_count": row[3],
                "display_url": row[4],  # Original Instagram URL as default
                "ai_analysis": {
                    "content_category": row[5],
                    "category_confidence": row[6],
                    "sentiment": row[7],
                    "sentiment_score": row[8],
                    "language_code": row[9],
                    "language_confidence": row[10]
                }
            }
            
            # Add CDN URLs if available for this post
            if cdn_media and cdn_media.posts and i < len(cdn_media.posts):
                cdn_post = cdn_media.posts[i]
                # Build CDN URLs structure from individual URLs
                cdn_urls = {}
                if cdn_post.get('cdn_url_256'):
                    cdn_urls['256'] = cdn_post['cdn_url_256']
                if cdn_post.get('cdn_url_512'):
                    cdn_urls['512'] = cdn_post['cdn_url_512']
                
                if cdn_urls:
                    post_data["cdn_urls"] = cdn_urls
                    # Use 256px CDN URL as primary display_url - CDN EXCLUSIVE
                    post_data["display_url"] = cdn_urls.get('256')
                    post_data["cdn_available"] = True
                else:
                    # No CDN URLs available - return None (CDN EXCLUSIVE)
                    post_data["display_url"] = None
                    post_data["cdn_available"] = False
            
            posts_with_ai.append(post_data)
        
        # 6. COMPLETE response with AI data and CDN URLs
        response = {
            "success": True,
            "profile": {
                "username": profile.username,
                "full_name": profile.full_name,
                "biography": profile.biography,
                "followers_count": profile.followers_count,
                "following_count": profile.following_count,
                "posts_count": profile.posts_count,
                "is_verified": profile.is_verified,
                "profile_pic_url": cdn_media.avatar_256 if cdn_media and cdn_media.avatar_256 else None,  # CDN EXCLUSIVE
                "profile_pic_url_hd": cdn_media.avatar_512 if cdn_media and cdn_media.avatar_512 else None,  # CDN EXCLUSIVE
                "cdn_urls": {
                    "avatar_256": cdn_media.avatar_256 if cdn_media else None,
                    "avatar_512": cdn_media.avatar_512 if cdn_media else None
                },
                "posts": posts_with_ai,
                # AI PROFILE AGGREGATES
                "ai_analysis": {
                    "primary_content_type": profile.ai_primary_content_type,
                    "content_distribution": profile.ai_content_distribution,
                    "avg_sentiment_score": profile.ai_avg_sentiment_score,
                    "language_distribution": profile.ai_language_distribution,
                    "content_quality_score": profile.ai_content_quality_score,
                    "analysis_completed": profile.ai_profile_analyzed_at is not None
                }
            },
            "message": "Complete profile with AI analysis and CDN URLs ready"
        }
        
        logger.info(f"Simple creator search completed: {username}")
        return response
        
    except Exception as e:
        logger.error(f"Simple creator search failed for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/creator/{username}")
async def get_simple_profile(
    username: str,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get existing profile data - simple response
    """
    try:
        from sqlalchemy import select, text
        from app.database.unified_models import Profile
        
        # Get profile from database
        query = select(Profile).where(Profile.username == username)
        result = await db.execute(query)
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Get posts
        posts_query = text("""
            SELECT instagram_post_id, caption, likes_count, comments_count, display_url
            FROM posts 
            WHERE profile_id = :profile_id 
            ORDER BY created_at DESC 
            LIMIT 12
        """)
        
        posts_result = await db.execute(posts_query, {"profile_id": profile.id})
        posts = [
            {
                "id": row[0],
                "caption": row[1],
                "likes_count": row[2],
                "comments_count": row[3],
                "display_url": row[4]
            }
            for row in posts_result.fetchall()
        ]
        
        response = {
            "success": True,
            "profile": {
                "username": profile.username,
                "full_name": profile.full_name,
                "biography": profile.biography,
                "followers_count": profile.followers_count,
                "following_count": profile.following_count,
                "posts_count": profile.posts_count,
                "is_verified": profile.is_verified,
                "profile_pic_url": profile.profile_pic_url,
                "posts": posts
            },
            "message": "Profile data loaded"
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Get profile failed for {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")