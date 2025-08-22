"""
Discovery Service - Credit-gated influencer discovery with advanced filtering
Implements paginated search with credit consumption and profile unlocking
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import json

from sqlalchemy import and_, or_, func, text, desc, asc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.database.connection import get_session
from app.database.unified_models import (
    Profile, User, DiscoverySession, DiscoveryFilter, 
    UnlockedProfile, CreditTransaction
)
from app.services.credit_wallet_service import credit_wallet_service
from app.services.credit_transaction_service import credit_transaction_service
from app.cache.redis_cache_manager import cache_manager

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Service for credit-gated influencer discovery with advanced filtering"""
    
    def __init__(self):
        self.free_pages = 3  # First 3 pages are free
        self.results_per_page = 20
        self.session_timeout_hours = 2
        
    async def start_discovery_session(
        self,
        user_id: UUID,
        search_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Start a new discovery session with search criteria
        
        Returns:
            session_id, total_results, first_page_data
        """
        try:
            async with get_session() as session:
                # Create discovery session
                discovery_session = DiscoverySession(
                    user_id=user_id,
                    search_criteria=search_criteria,
                    results_per_page=self.results_per_page,
                    expires_at=datetime.utcnow() + timedelta(hours=self.session_timeout_hours)
                )
                
                session.add(discovery_session)
                await session.commit()
                await session.refresh(discovery_session)
                
                # Get first page results
                page_data = await self._get_page_results(
                    session=session,
                    discovery_session=discovery_session,
                    page_number=1
                )
                
                # Update session with total results
                discovery_session.total_results = page_data["total_count"]
                await session.commit()
                
                return {
                    "session_id": discovery_session.id,
                    "total_results": page_data["total_count"],
                    "results_per_page": self.results_per_page,
                    "first_page": page_data["results"],
                    "credits_consumed": 0,  # First page is free
                    "free_pages_remaining": self.free_pages - 1,
                    "search_criteria": search_criteria
                }
                
        except Exception as e:
            logger.error(f"Error starting discovery session for user {user_id}: {e}")
            raise
    
    async def get_discovery_page(
        self,
        user_id: UUID,
        session_id: UUID,
        page_number: int
    ) -> Dict[str, Any]:
        """
        Get a specific page of discovery results with credit checking
        
        Returns:
            results, credits_info, pagination_info
        """
        try:
            async with get_session() as session:
                # Get discovery session
                discovery_session = await session.get(DiscoverySession, session_id)
                
                if not discovery_session or discovery_session.user_id != user_id:
                    raise ValueError("Discovery session not found or unauthorized")
                
                if discovery_session.expires_at < datetime.utcnow():
                    raise ValueError("Discovery session has expired")
                
                # Check if credits are required for this page
                credits_required = 0
                if page_number > self.free_pages:
                    credits_required = 1  # 1 credit per page after free pages
                
                # Check credits if required
                if credits_required > 0:
                    permission = await credit_wallet_service.can_perform_action(
                        user_id, "discovery", credits_required
                    )
                    
                    if not permission.can_perform:
                        return {
                            "error": "insufficient_credits",
                            "message": permission.message,
                            "credits_required": credits_required,
                            "wallet_balance": permission.wallet_balance
                        }
                
                # Get page results
                page_data = await self._get_page_results(
                    session=session,
                    discovery_session=discovery_session,
                    page_number=page_number
                )
                
                # Spend credits if required (only after successful page load)
                transaction = None
                if credits_required > 0:
                    transaction = await credit_wallet_service.spend_credits(
                        user_id=user_id,
                        amount=credits_required,
                        action_type="discovery",
                        reference_id=str(session_id),
                        reference_type="discovery_session",
                        description=f"Discovery page {page_number} viewed"
                    )
                
                # Update session tracking
                discovery_session.pages_viewed = max(discovery_session.pages_viewed, page_number)
                discovery_session.credits_consumed += credits_required
                discovery_session.last_accessed = datetime.utcnow()
                
                if page_number <= self.free_pages:
                    discovery_session.free_pages_used = min(
                        discovery_session.free_pages_used + 1, 
                        self.free_pages
                    )
                
                await session.commit()
                
                return {
                    "results": page_data["results"],
                    "pagination": {
                        "current_page": page_number,
                        "total_pages": (page_data["total_count"] + self.results_per_page - 1) // self.results_per_page,
                        "total_results": page_data["total_count"],
                        "results_per_page": self.results_per_page
                    },
                    "credits_info": {
                        "credits_spent": credits_required,
                        "total_credits_consumed": discovery_session.credits_consumed,
                        "free_pages_remaining": max(0, self.free_pages - page_number),
                        "transaction_id": transaction.id if transaction else None
                    }
                }
                
        except Exception as e:
            logger.error(f"Error getting discovery page {page_number} for user {user_id}: {e}")
            raise
    
    async def _get_page_results(
        self,
        session: AsyncSession,
        discovery_session: DiscoverySession,
        page_number: int
    ) -> Dict[str, Any]:
        """
        Get paginated search results based on discovery session criteria
        """
        try:
            # Build base query
            query = select(Profile).filter(
                Profile.discovery_visible == True,
                Profile.blacklisted == False,
                Profile.inactive == False
            )
            
            # Apply search criteria filters
            criteria = discovery_session.search_criteria
            query = self._apply_search_filters(query, criteria)
            
            # Get total count
            count_query = select(func.count(Profile.id)).filter(
                Profile.discovery_visible == True,
                Profile.blacklisted == False,
                Profile.inactive == False
            )
            count_query = self._apply_search_filters(count_query, criteria)
            total_count = await session.scalar(count_query)
            
            # Apply pagination and ordering
            offset = (page_number - 1) * self.results_per_page
            query = query.order_by(desc(Profile.followers_count)).offset(offset).limit(self.results_per_page)
            
            # Execute query with relationships
            query = query.options(
                selectinload(Profile.unlocked_by_users)
            )
            
            result = await session.execute(query)
            profiles = result.scalars().all()
            
            # Format results with unlock status
            results = []
            for profile in profiles:
                is_unlocked = any(
                    unlock.user_id == discovery_session.user_id 
                    for unlock in profile.unlocked_by_users
                )
                
                result = {
                    "profile_id": profile.id,
                    "username": profile.username,
                    "platform": profile.platform,
                    "is_unlocked": is_unlocked,
                    "preview_data": self._get_preview_data(profile),
                    "full_data": self._get_full_data(profile) if is_unlocked else None
                }
                results.append(result)
            
            return {
                "results": results,
                "total_count": total_count
            }
            
        except Exception as e:
            logger.error(f"Error getting page results: {e}")
            raise
    
    def _apply_search_filters(self, query, criteria: Dict[str, Any]):
        """Apply search criteria filters to the query"""
        
        # Platform filter
        if platform := criteria.get("platform"):
            query = query.filter(Profile.platform == platform)
        
        # Follower count range
        if min_followers := criteria.get("min_followers"):
            query = query.filter(Profile.followers_count >= min_followers)
        
        if max_followers := criteria.get("max_followers"):
            query = query.filter(Profile.followers_count <= max_followers)
        
        # Engagement rate range
        if min_engagement := criteria.get("min_engagement"):
            query = query.filter(Profile.engagement_rate >= min_engagement)
        
        if max_engagement := criteria.get("max_engagement"):
            query = query.filter(Profile.engagement_rate <= max_engagement)
        
        # Categories filter (JSONB array contains any of the specified categories)
        if categories := criteria.get("categories"):
            if isinstance(categories, list) and categories:
                category_conditions = [
                    Profile.categories.op("?")(category) for category in categories
                ]
                query = query.filter(or_(*category_conditions))
        
        # Languages filter
        if languages := criteria.get("languages"):
            if isinstance(languages, list) and languages:
                language_conditions = [
                    Profile.languages.op("?")(language) for language in languages
                ]
                query = query.filter(or_(*language_conditions))
        
        # Verified status filter
        if verified := criteria.get("verified"):
            query = query.filter(Profile.is_verified == verified)
        
        # Business account filter
        if business := criteria.get("business_account"):
            query = query.filter(Profile.is_business_account == business)
        
        # Barter eligible filter
        if barter := criteria.get("barter_eligible"):
            query = query.filter(Profile.barter_eligible == barter)
        
        # Text search in username and full name
        if search_text := criteria.get("search_text"):
            search_pattern = f"%{search_text.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Profile.username).like(search_pattern),
                    func.lower(Profile.full_name).like(search_pattern)
                )
            )
        
        return query
    
    def _get_preview_data(self, profile: Profile) -> Dict[str, Any]:
        """Get preview data that's always available (no unlock required)"""
        followers_range = self._get_followers_range(profile.followers_count)
        
        return {
            "username": profile.username,
            "platform": profile.platform,
            "followers_range": followers_range,
            "profile_picture_url": profile.profile_picture_url,
            "verified": profile.is_verified,
            "business_account": profile.is_business_account,
            "categories": profile.categories[:2] if profile.categories else [],  # Show first 2 categories
            "location": profile.external_url if profile.external_url else None
        }
    
    def _get_full_data(self, profile: Profile) -> Dict[str, Any]:
        """Get full data that requires unlock"""
        return {
            "followers_count": profile.followers_count,
            "following_count": profile.following_count,
            "posts_count": profile.posts_count,
            "engagement_rate": float(profile.engagement_rate) if profile.engagement_rate else None,
            "avg_likes": profile.avg_likes,
            "avg_comments": profile.avg_comments,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "external_url": profile.external_url,
            "categories": profile.categories,
            "languages": profile.languages,
            "sell_price_usd": profile.sell_price_usd,
            "min_collaboration_fee": profile.min_collaboration_fee,
            "barter_eligible": profile.barter_eligible,
            "ai_content_insights": {
                "primary_content_type": profile.ai_primary_content_type,
                "content_distribution": profile.ai_content_distribution,
                "avg_sentiment_score": float(profile.ai_avg_sentiment_score) if profile.ai_avg_sentiment_score else None,
                "language_distribution": profile.ai_language_distribution,
                "content_quality_score": float(profile.ai_content_quality_score) if profile.ai_content_quality_score else None
            }
        }
    
    def _get_followers_range(self, followers_count: Optional[int]) -> str:
        """Convert follower count to range string"""
        if not followers_count:
            return "Unknown"
        
        if followers_count < 1000:
            return "< 1K"
        elif followers_count < 10000:
            return "1K - 10K"
        elif followers_count < 100000:
            return "10K - 100K"
        elif followers_count < 1000000:
            return "100K - 1M"
        elif followers_count < 10000000:
            return "1M - 10M"
        else:
            return "10M+"
    
    async def unlock_profile(
        self,
        user_id: UUID,
        profile_id: UUID,
        unlock_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Unlock a profile using credits (profile_analysis action - 25 credits)
        """
        try:
            async with get_session() as session:
                # Check if already unlocked
                existing_unlock_query = select(UnlockedProfile).filter(
                    UnlockedProfile.user_id == user_id,
                    UnlockedProfile.profile_id == profile_id
                )
                existing_unlock_result = await session.execute(existing_unlock_query)
                existing_unlock = existing_unlock_result.scalar_one_or_none()
                
                if existing_unlock:
                    return {
                        "already_unlocked": True,
                        "unlocked_at": existing_unlock.unlocked_at,
                        "credits_spent": existing_unlock.credits_spent
                    }
                
                # Check if profile exists and is discoverable
                profile = await session.get(Profile, profile_id)
                if not profile:
                    raise ValueError("Profile not found")
                
                if profile.blacklisted or profile.inactive:
                    raise ValueError("Profile is not available for unlock")
                
                # Check credits for profile_analysis action (25 credits)
                permission = await credit_wallet_service.can_perform_action(
                    user_id, "profile_analysis", 25
                )
                
                if not permission.can_perform:
                    return {
                        "error": "insufficient_credits",
                        "message": permission.message,
                        "credits_required": 25,
                        "wallet_balance": permission.wallet_balance
                    }
                
                # Spend credits
                transaction = await credit_wallet_service.spend_credits(
                    user_id=user_id,
                    amount=25,
                    action_type="profile_analysis",
                    reference_id=str(profile_id),
                    reference_type="profile",
                    description=f"Profile unlock: {profile.username}"
                )
                
                # Create unlock record
                unlock_record = UnlockedProfile(
                    user_id=user_id,
                    profile_id=profile_id,
                    credits_spent=25,
                    unlock_type="profile_analysis",
                    unlock_reason=unlock_reason,
                    transaction_id=transaction.id
                )
                
                session.add(unlock_record)
                await session.commit()
                await session.refresh(unlock_record)
                
                return {
                    "unlocked": True,
                    "unlock_id": unlock_record.id,
                    "credits_spent": 25,
                    "transaction_id": transaction.id,
                    "unlocked_at": unlock_record.unlocked_at,
                    "full_data": self._get_full_data(profile)
                }
                
        except Exception as e:
            logger.error(f"Error unlocking profile {profile_id} for user {user_id}: {e}")
            raise
    
    async def get_user_unlocked_profiles(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get list of profiles unlocked by the user"""
        try:
            async with get_session() as session:
                query = select(UnlockedProfile).filter(
                    UnlockedProfile.user_id == user_id
                ).options(
                    joinedload(UnlockedProfile.profile)
                ).order_by(desc(UnlockedProfile.unlocked_at)).offset(offset).limit(limit)
                
                result = await session.execute(query)
                unlocked_profiles = result.scalars().all()
                
                results = []
                for unlock in unlocked_profiles:
                    profile = unlock.profile
                    result = {
                        "unlock_id": unlock.id,
                        "unlocked_at": unlock.unlocked_at,
                        "credits_spent": unlock.credits_spent,
                        "profile": {
                            "profile_id": profile.id,
                            "username": profile.username,
                            "platform": profile.platform,
                            "preview_data": self._get_preview_data(profile),
                            "full_data": self._get_full_data(profile)
                        }
                    }
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting unlocked profiles for user {user_id}: {e}")
            raise
    
    async def save_discovery_filter(
        self,
        user_id: UUID,
        filter_name: str,
        filter_criteria: Dict[str, Any],
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Save a discovery filter for reuse"""
        try:
            async with get_session() as session:
                discovery_filter = DiscoveryFilter(
                    user_id=user_id,
                    filter_name=filter_name,
                    description=description,
                    filter_criteria=filter_criteria
                )
                
                session.add(discovery_filter)
                await session.commit()
                await session.refresh(discovery_filter)
                
                return {
                    "filter_id": discovery_filter.id,
                    "filter_name": discovery_filter.filter_name,
                    "description": discovery_filter.description,
                    "filter_criteria": discovery_filter.filter_criteria,
                    "created_at": discovery_filter.created_at
                }
                
        except Exception as e:
            logger.error(f"Error saving discovery filter for user {user_id}: {e}")
            raise
    
    async def get_user_discovery_filters(
        self,
        user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get user's saved discovery filters"""
        try:
            async with get_session() as session:
                query = select(DiscoveryFilter).filter(
                    DiscoveryFilter.user_id == user_id
                ).order_by(desc(DiscoveryFilter.last_used), desc(DiscoveryFilter.created_at))
                
                result = await session.execute(query)
                filters = result.scalars().all()
                
                return [
                    {
                        "filter_id": f.id,
                        "filter_name": f.filter_name,
                        "description": f.description,
                        "filter_criteria": f.filter_criteria,
                        "usage_count": f.usage_count,
                        "last_used": f.last_used,
                        "created_at": f.created_at
                    }
                    for f in filters
                ]
                
        except Exception as e:
            logger.error(f"Error getting discovery filters for user {user_id}: {e}")
            raise


# Global service instance
discovery_service = DiscoveryService()