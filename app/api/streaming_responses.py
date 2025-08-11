"""
Streaming Responses Service - Real-time data streaming for large datasets
Provides async streaming responses to prevent blocking and improve user experience
"""
import logging
import asyncio
import json
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime, timezone
from fastapi import Response
from fastapi.responses import StreamingResponse
import time

from app.database.unified_models import Profile, Post
from app.services.cache_integration_service import cache_integration_service
from app.monitoring.performance_monitor import performance_monitor

logger = logging.getLogger(__name__)

class StreamingResponseService:
    """
    Service for creating streaming responses for large datasets
    """
    
    def __init__(self):
        self.active_streams: Dict[str, Dict[str, Any]] = {}
        
    async def stream_posts_data(
        self, 
        db_session,
        username: str,
        limit: int = 20,
        offset: int = 0,
        include_ai_analysis: bool = True,
        chunk_size: int = 5
    ) -> AsyncGenerator[str, None]:
        """
        Stream posts data in chunks for better performance
        
        Args:
            db_session: Database session
            username: Instagram username
            limit: Maximum number of posts
            offset: Offset for pagination
            include_ai_analysis: Include AI analysis data
            chunk_size: Number of posts per chunk
        """
        stream_id = f"posts_stream_{username}_{int(time.time())}"
        
        try:
            # Record stream start
            self.active_streams[stream_id] = {
                "type": "posts_stream",
                "username": username,
                "started_at": datetime.now(timezone.utc),
                "total_items": 0,
                "chunks_sent": 0
            }
            
            # Start streaming metadata
            yield f"data: {json.dumps({\n"
            yield f'    "stream_type": "posts_data",\n'
            yield f'    "username": "{username}",\n'
            yield f'    "stream_id": "{stream_id}",\n'
            yield f'    "started_at": "{datetime.now(timezone.utc).isoformat()}",\n'
            yield f'    "pagination": {{"limit": {limit}, "offset": {offset}}},\n'
            yield f'    "posts": [\n'
            
            # Get posts in chunks
            current_offset = offset
            posts_sent = 0
            first_chunk = True
            
            while posts_sent < limit:
                current_limit = min(chunk_size, limit - posts_sent)
                
                # Use circuit breaker for database operations
                from app.resilience.circuit_breaker import circuit_breaker_manager
                
                async def get_posts_chunk():
                    # Get posts from database
                    from sqlalchemy import select
                    
                    # Get profile first
                    profile_query = select(Profile).where(Profile.username == username)
                    profile_result = await db_session.execute(profile_query)
                    profile = profile_result.scalar_one_or_none()
                    
                    if not profile:
                        return []
                    
                    # Get posts chunk
                    posts_query = (
                        select(Post)
                        .where(Post.profile_id == profile.id)
                        .order_by(Post.created_at.desc())
                        .limit(current_limit)
                        .offset(current_offset)
                    )
                    
                    posts_result = await db_session.execute(posts_query)
                    return posts_result.scalars().all()
                
                try:
                    posts_chunk = await circuit_breaker_manager.execute_with_breaker(
                        "database", get_posts_chunk
                    )
                    
                    if not posts_chunk:
                        break
                    
                    # Stream each post in the chunk
                    for i, post in enumerate(posts_chunk):
                        if not first_chunk or i > 0:
                            yield ",\n"
                        
                        # Convert post to dict
                        post_data = {
                            "id": str(post.id),
                            "url": post.url,
                            "caption": post.caption,
                            "hashtags": post.hashtags,
                            "mentions": post.mentions,
                            "likes": post.likes,
                            "comments": post.comments,
                            "created_at": post.created_at.isoformat() if post.created_at else None,
                            "media_type": post.media_type,
                            "engagement_rate": float(post.engagement_rate) if post.engagement_rate else 0.0,
                            "image_url": post.image_url,
                            "video_url": post.video_url
                        }
                        
                        # Add AI analysis if available and requested
                        if include_ai_analysis and post.ai_analyzed_at:
                            post_data["ai_analysis"] = {
                                "content_category": post.ai_content_category,
                                "category_confidence": float(post.ai_category_confidence) if post.ai_category_confidence else None,
                                "sentiment": post.ai_sentiment,
                                "sentiment_score": float(post.ai_sentiment_score) if post.ai_sentiment_score else None,
                                "sentiment_confidence": float(post.ai_sentiment_confidence) if post.ai_sentiment_confidence else None,
                                "language_code": post.ai_language_code,
                                "language_confidence": float(post.ai_language_confidence) if post.ai_language_confidence else None,
                                "analyzed_at": post.ai_analyzed_at.isoformat() if post.ai_analyzed_at else None
                            }
                        
                        # Stream the post data
                        post_json = json.dumps(post_data, indent=8, default=str)
                        yield f"        {post_json}"
                        
                        posts_sent += 1
                        first_chunk = False
                        
                        # Small delay to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                    
                    # Update stream metadata
                    self.active_streams[stream_id]["total_items"] = posts_sent
                    self.active_streams[stream_id]["chunks_sent"] += 1
                    
                    current_offset += current_limit
                    
                    # Small delay between chunks
                    await asyncio.sleep(0.05)
                    
                except Exception as e:
                    logger.error(f"Error streaming posts chunk: {e}")
                    # Stream error information
                    if not first_chunk:
                        yield ",\n"
                    
                    error_data = {
                        "error": "chunk_failed",
                        "message": str(e),
                        "chunk_offset": current_offset
                    }
                    yield f"        {json.dumps(error_data, indent=8)}"
                    break
            
            # Close posts array and add metadata
            yield f"\n    ],\n"
            yield f'    "total_posts_streamed": {posts_sent},\n'
            yield f'    "chunks_sent": {self.active_streams[stream_id]["chunks_sent"]},\n'
            yield f'    "completed_at": "{datetime.now(timezone.utc).isoformat()}",\n'
            yield f'    "stream_completed": true\n'
            yield f"}}\n\n"
            
        except Exception as e:
            logger.error(f"Posts streaming failed for {username}: {e}")
            
            # Stream error response
            error_response = {
                "stream_type": "posts_data",
                "username": username,
                "error": str(e),
                "stream_completed": false,
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
            
            yield f"data: {json.dumps(error_response)}\n\n"
        
        finally:
            # Clean up stream tracking
            self.active_streams.pop(stream_id, None)
    
    async def stream_analytics_data(
        self,
        db_session,
        username: str,
        include_historical: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream analytics data progressively
        
        Args:
            db_session: Database session
            username: Instagram username  
            include_historical: Include historical metrics
        """
        stream_id = f"analytics_stream_{username}_{int(time.time())}"
        
        try:
            self.active_streams[stream_id] = {
                "type": "analytics_stream",
                "username": username,
                "started_at": datetime.now(timezone.utc),
                "sections_sent": 0
            }
            
            # Start streaming response
            yield f"data: {{\n"
            yield f'    "stream_type": "analytics_data",\n'
            yield f'    "username": "{username}",\n'
            yield f'    "stream_id": "{stream_id}",\n'
            yield f'    "started_at": "{datetime.now(timezone.utc).isoformat()}",\n'
            
            # Stream basic profile data first
            from sqlalchemy import select
            profile_query = select(Profile).where(Profile.username == username)
            profile_result = await db_session.execute(profile_query)
            profile = profile_result.scalar_one_or_none()
            
            if profile:
                basic_data = {
                    "profile_id": str(profile.id),
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "bio": profile.bio,
                    "followers": profile.followers,
                    "following": profile.following,
                    "posts_count": profile.posts_count,
                    "is_verified": profile.is_verified,
                    "profile_picture_url": profile.profile_picture_url,
                    "last_scraped": profile.last_scraped_at.isoformat() if profile.last_scraped_at else None
                }
                
                yield f'    "profile": {json.dumps(basic_data, indent=8, default=str)},\n'
                
                # Small delay
                await asyncio.sleep(0.1)
                
                # Stream engagement metrics
                engagement_data = {
                    "engagement_rate": float(profile.engagement_rate) if profile.engagement_rate else 0.0,
                    "avg_likes": profile.avg_likes,
                    "avg_comments": profile.avg_comments,
                    "best_time_to_post": profile.best_time_to_post,
                    "influence_score": float(profile.influence_score) if profile.influence_score else 0.0,
                    "content_quality_score": float(profile.content_quality_score) if profile.content_quality_score else 0.0
                }
                
                yield f'    "engagement_metrics": {json.dumps(engagement_data, indent=8, default=str)},\n'
                
                # Small delay
                await asyncio.sleep(0.1)
                
                # Stream AI insights if available
                if profile.ai_profile_analyzed_at:
                    ai_insights = {
                        "primary_content_type": profile.ai_primary_content_type,
                        "content_distribution": profile.ai_content_distribution,
                        "avg_sentiment_score": float(profile.ai_avg_sentiment_score) if profile.ai_avg_sentiment_score else None,
                        "language_distribution": profile.ai_language_distribution,
                        "content_quality_score": float(profile.ai_content_quality_score) if profile.ai_content_quality_score else None,
                        "analyzed_at": profile.ai_profile_analyzed_at.isoformat()
                    }
                    
                    yield f'    "ai_insights": {json.dumps(ai_insights, indent=8, default=str)},\n'
                
                # Stream historical data if requested
                if include_historical:
                    # This would typically include engagement trends, growth metrics, etc.
                    historical_data = {
                        "note": "Historical analytics would be streamed here",
                        "available": False
                    }
                    
                    yield f'    "historical_analytics": {json.dumps(historical_data, indent=8)},\n'
            
            # Complete the stream
            yield f'    "stream_completed": true,\n'
            yield f'    "completed_at": "{datetime.now(timezone.utc).isoformat()}"\n'
            yield f"}}\n\n"
            
        except Exception as e:
            logger.error(f"Analytics streaming failed for {username}: {e}")
            
            error_response = {
                "stream_type": "analytics_data", 
                "username": username,
                "error": str(e),
                "stream_completed": false,
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
            
            yield f"data: {json.dumps(error_response)}\n\n"
        
        finally:
            self.active_streams.pop(stream_id, None)
    
    async def stream_real_time_metrics(self) -> AsyncGenerator[str, None]:
        """
        Stream real-time system metrics
        """
        stream_id = f"metrics_stream_{int(time.time())}"
        
        try:
            self.active_streams[stream_id] = {
                "type": "real_time_metrics",
                "started_at": datetime.now(timezone.utc),
                "metrics_sent": 0
            }
            
            # Stream metrics every 5 seconds
            while stream_id in self.active_streams:
                try:
                    # Get current metrics
                    performance_summary = performance_monitor.get_performance_summary(5)  # Last 5 minutes
                    system_status = performance_monitor.get_system_status()
                    
                    metrics_data = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "performance": {
                            "requests_per_minute": performance_summary.get("requests_per_minute", 0),
                            "avg_response_time_ms": performance_summary.get("response_times", {}).get("avg_ms", 0),
                            "success_rate": performance_summary.get("success_rate_percent", 0),
                            "total_requests": performance_summary.get("total_requests", 0)
                        },
                        "system": {
                            "cpu_percent": system_status.get("metrics", {}).get("cpu_percent", 0),
                            "memory_percent": system_status.get("metrics", {}).get("memory_percent", 0),
                            "active_connections": system_status.get("metrics", {}).get("active_connections", 0)
                        }
                    }
                    
                    # Stream the data
                    yield f"data: {json.dumps(metrics_data)}\n\n"
                    
                    self.active_streams[stream_id]["metrics_sent"] += 1
                    
                    # Wait 5 seconds before next update
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error streaming real-time metrics: {e}")
                    
                    error_data = {
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    yield f"data: {json.dumps(error_data)}\n\n"
                    await asyncio.sleep(5)
        
        except Exception as e:
            logger.error(f"Real-time metrics streaming failed: {e}")
        
        finally:
            self.active_streams.pop(stream_id, None)
    
    def stop_stream(self, stream_id: str) -> bool:
        """Stop a specific stream"""
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
            logger.info(f"Stopped stream: {stream_id}")
            return True
        return False
    
    def get_active_streams(self) -> Dict[str, Any]:
        """Get information about active streams"""
        return {
            "active_streams": len(self.active_streams),
            "streams": {
                stream_id: {
                    "type": stream_data.get("type"),
                    "started_at": stream_data.get("started_at").isoformat() if stream_data.get("started_at") else None,
                    "username": stream_data.get("username"),
                    "items_sent": stream_data.get("total_items", stream_data.get("metrics_sent", 0))
                }
                for stream_id, stream_data in self.active_streams.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Global streaming service instance
streaming_service = StreamingResponseService()