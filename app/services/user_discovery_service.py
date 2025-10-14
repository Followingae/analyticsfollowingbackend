"""
User Discovery Service - Frontend Profile Discovery

Service for frontend discovery functionality allowing users to:
1. Browse ALL profiles in the database
2. Search and filter profiles
3. Unlock profiles with credits for 30-day access
4. Track unlocked profiles and access expiry

This integrates with the existing credits system and UserProfileAccess table.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload

from app.database.unified_models import Profile, UserProfileAccess, Post
from app.services.credit_wallet_service import credit_wallet_service
from app.services.cdn_sync_service import cdn_sync_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserDiscoveryService:
    """
    User Discovery Service for Frontend

    Provides comprehensive discovery functionality for users to browse,
    search, filter, and unlock profiles with credit-based access.
    """

    def __init__(self):
        self.default_page_size = 20
        self.max_page_size = 100

    async def browse_all_profiles(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search_query: Optional[str] = None,
        category_filter: Optional[str] = None,
        min_followers: Optional[int] = None,
        max_followers: Optional[int] = None,
        engagement_rate_min: Optional[float] = None,
        engagement_rate_max: Optional[float] = None,
        sort_by: str = "followers_desc",
        include_unlocked_status: bool = True
    ) -> Dict[str, Any]:
        """
        Browse all profiles in the database with filtering and search

        Args:
            db: Database session
            user_id: Current user ID
            page: Page number (1-based)
            page_size: Results per page
            search_query: Search in username, full_name, biography
            category_filter: Filter by AI content category
            min_followers: Minimum followers count
            max_followers: Maximum followers count
            engagement_rate_min: Minimum engagement rate
            engagement_rate_max: Maximum engagement rate
            sort_by: Sort order (followers_desc, followers_asc, engagement_desc, recent)
            include_unlocked_status: Include user's unlock status for each profile

        Returns:
            Paginated discovery results with profiles and metadata
        """
        try:
            logger.info(f"🔍 User Discovery Browse: user={user_id}, page={page}, search='{search_query}'")

            # Validate pagination
            page = max(1, page)
            page_size = min(max(1, page_size), self.max_page_size)
            offset = (page - 1) * page_size

            # Build base query for complete profiles only
            base_query = select(Profile).where(
                and_(
                    Profile.followers_count > 0,
                    Profile.posts_count > 0,
                    Profile.biography.isnot(None),
                    Profile.ai_profile_analyzed_at.isnot(None)
                )
            )

            # Apply search filter
            if search_query and search_query.strip():
                search_term = f"%{search_query.strip().lower()}%"
                base_query = base_query.where(
                    or_(
                        func.lower(Profile.username).like(search_term),
                        func.lower(Profile.full_name).like(search_term),
                        func.lower(Profile.biography).like(search_term)
                    )
                )

            # Apply category filter
            if category_filter:
                base_query = base_query.where(
                    Profile.ai_primary_content_type == category_filter
                )

            # Apply follower count filters
            if min_followers is not None:
                base_query = base_query.where(Profile.followers_count >= min_followers)
            if max_followers is not None:
                base_query = base_query.where(Profile.followers_count <= max_followers)

            # Apply engagement rate filters (if we add this field later)
            # if engagement_rate_min is not None:
            #     base_query = base_query.where(Profile.engagement_rate >= engagement_rate_min)
            # if engagement_rate_max is not None:
            #     base_query = base_query.where(Profile.engagement_rate <= engagement_rate_max)

            # Apply sorting
            if sort_by == "followers_desc":
                base_query = base_query.order_by(desc(Profile.followers_count))
            elif sort_by == "followers_asc":
                base_query = base_query.order_by(asc(Profile.followers_count))
            elif sort_by == "recent":
                base_query = base_query.order_by(desc(Profile.created_at))
            elif sort_by == "alphabetical":
                base_query = base_query.order_by(asc(Profile.username))
            else:
                # Default to followers_desc
                base_query = base_query.order_by(desc(Profile.followers_count))

            # Get total count for pagination
            count_query = select(func.count()).select_from(base_query.subquery())
            count_result = await db.execute(count_query)
            total_profiles = count_result.scalar()

            # Get paginated results
            paginated_query = base_query.offset(offset).limit(page_size)
            profiles_result = await db.execute(paginated_query)
            profiles = profiles_result.scalars().all()

            # Get unlock status if requested
            unlocked_status = {}
            if include_unlocked_status and profiles:
                profile_ids = [str(p.id) for p in profiles]
                unlock_query = select(
                    UserProfileAccess.profile_id,
                    UserProfileAccess.granted_at,
                    UserProfileAccess.expires_at
                ).where(
                    and_(
                        UserProfileAccess.user_id == user_id,
                        UserProfileAccess.profile_id.in_(profile_ids),
                        UserProfileAccess.expires_at > datetime.now(timezone.utc)
                    )
                )
                unlock_result = await db.execute(unlock_query)
                unlock_rows = unlock_result.fetchall()

                for row in unlock_rows:
                    days_remaining = (row.expires_at - datetime.now(timezone.utc)).days if row.expires_at else None
                    unlocked_status[str(row.profile_id)] = {
                        "is_unlocked": True,
                        "granted_at": row.granted_at.isoformat() if row.granted_at else None,
                        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                        "days_remaining": days_remaining
                    }

            # Format response
            formatted_profiles = []
            unlocked_count = 0
            for profile in profiles:
                profile_id = str(profile.id)
                unlock_info = unlocked_status.get(profile_id, {
                    "is_unlocked": False,
                    "granted_at": None,
                    "expires_at": None,
                    "days_remaining": None
                })

                if unlock_info["is_unlocked"]:
                    unlocked_count += 1

                # Get CDN profile picture - EXACT same approach as creator analytics
                profile_pic_url = await cdn_sync_service.get_profile_cdn_url(
                    db, str(profile.id), profile.username
                )

                formatted_profiles.append({
                    "id": profile_id,
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "biography": profile.biography,
                    "profile_pic_url": profile_pic_url,
                    "followers_count": profile.followers_count,
                    "following_count": profile.following_count,
                    "posts_count": profile.posts_count,
                    "is_verified": profile.is_verified,
                    "is_private": profile.is_private,
                    "ai_analysis": {
                        "primary_content_type": profile.ai_primary_content_type,
                        "avg_sentiment_score": profile.ai_avg_sentiment_score,
                        "content_quality_score": profile.ai_content_quality_score
                    },
                    "unlock_status": unlock_info,
                    "created_at": profile.created_at.isoformat() if profile.created_at else None
                })

            # Calculate pagination metadata
            total_pages = (total_profiles + page_size - 1) // page_size
            has_next = page < total_pages
            has_previous = page > 1


            return {
                "success": True,
                "profiles": formatted_profiles,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_profiles": total_profiles,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_previous": has_previous
                },
                "filters_applied": {
                    "search_query": search_query,
                    "category_filter": category_filter,
                    "min_followers": min_followers,
                    "max_followers": max_followers,
                    "sort_by": sort_by
                },
                "unlocked_count": len(unlocked_status) if include_unlocked_status else 0
            }

        except Exception as e:
            logger.error(f"Discovery browse failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def unlock_profile_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        profile_id: UUID,
        credits_to_spend: int = 25
    ) -> Dict[str, Any]:
        """
        Unlock a profile for 30-day access using credits

        Args:
            db: Database session
            user_id: User requesting unlock
            profile_id: Profile to unlock
            credits_to_spend: Credits required (default 25)

        Returns:
            Unlock result with access information
        """
        try:
            logger.info(f"🔓 Profile Unlock: user={user_id}, profile={profile_id}")

            # Check if profile exists
            profile_query = select(Profile).where(Profile.id == profile_id)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()

            if not profile:
                return {
                    "success": False,
                    "error": "profile_not_found",
                    "message": "Profile not found"
                }

            # Check if already unlocked and not expired
            existing_access_query = select(UserProfileAccess).where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.profile_id == profile_id,
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )
            )
            existing_access_result = await db.execute(existing_access_query)
            existing_access = existing_access_result.scalar_one_or_none()

            if existing_access:
                days_remaining = (existing_access.expires_at - datetime.now(timezone.utc)).days
                return {
                    "success": True,
                    "already_unlocked": True,
                    "message": f"Profile already unlocked for {days_remaining} more days",
                    "access_info": {
                        "granted_at": existing_access.granted_at.isoformat() if existing_access.granted_at else None,
                        "expires_at": existing_access.expires_at.isoformat() if existing_access.expires_at else None,
                        "days_remaining": days_remaining
                    },
                    "profile": {
                        "username": profile.username,
                        "full_name": profile.full_name,
                        "followers_count": profile.followers_count
                    }
                }

            # Check user credits - get existing wallet or create if needed
            wallet = await credit_wallet_service.get_wallet(user_id)
            if not wallet:
                wallet = await credit_wallet_service.create_wallet(user_id)
            if wallet.current_balance < credits_to_spend:
                return {
                    "success": False,
                    "error": "insufficient_credits",
                    "message": f"Insufficient credits. Required: {credits_to_spend}, Available: {wallet.current_balance}",
                    "credits_available": wallet.current_balance,
                    "credits_required": credits_to_spend
                }

            # Spend credits using atomic method
            spend_result = await credit_wallet_service.spend_credits_atomic(
                db=db,
                user_id=user_id,
                credits_amount=credits_to_spend,
                action_type="profile_unlock",
                description=f"Unlocked profile @{profile.username}",
                reference_id=str(profile_id),
                reference_type="profile"
            )

            if not spend_result:
                return {
                    "success": False,
                    "error": "credit_spend_failed",
                    "message": "Failed to spend credits",
                    "credits_available": wallet.current_balance
                }

            # Create 30-day access record
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=30)

            new_access = UserProfileAccess(
                user_id=user_id,
                profile_id=profile_id,
                granted_at=now,
                expires_at=expires_at,
                created_at=now
            )

            db.add(new_access)
            await db.commit()
            await db.refresh(new_access)

            logger.info(f"✅ Profile unlocked: @{profile.username} for user {user_id}")

            return {
                "success": True,
                "unlocked": True,
                "credits_spent": credits_to_spend,
                "credits_remaining": wallet.current_balance - credits_to_spend,
                "message": f"Successfully unlocked @{profile.username} for 30 days",
                "access_info": {
                    "granted_at": new_access.granted_at.isoformat(),
                    "expires_at": new_access.expires_at.isoformat(),
                    "days_remaining": 30
                },
                "profile": {
                    "id": str(profile.id),
                    "username": profile.username,
                    "full_name": profile.full_name,
                    "followers_count": profile.followers_count,
                    "posts_count": profile.posts_count,
                    "is_verified": profile.is_verified,
                    "ai_primary_content_type": profile.ai_primary_content_type
                },
                "transaction_id": str(spend_result.transaction_id) if hasattr(spend_result, 'transaction_id') else None
            }

        except Exception as e:
            logger.error(f"Profile unlock failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def get_user_unlocked_profiles(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        include_expired: bool = False
    ) -> Dict[str, Any]:
        """
        Get all profiles the user has unlocked

        Args:
            db: Database session
            user_id: User ID
            page: Page number
            page_size: Results per page
            include_expired: Include expired access records

        Returns:
            User's unlocked profiles with access information
        """
        try:
            logger.info(f"📊 Getting unlocked profiles: user={user_id}")

            # Validate pagination
            page = max(1, page)
            page_size = min(max(1, page_size), self.max_page_size)
            offset = (page - 1) * page_size

            # Build query
            base_query = select(
                UserProfileAccess,
                Profile
            ).join(
                Profile, UserProfileAccess.profile_id == Profile.id
            ).where(
                UserProfileAccess.user_id == user_id
            )

            # Filter expired access if not requested
            if not include_expired:
                base_query = base_query.where(
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )

            # Order by most recent first
            base_query = base_query.order_by(desc(UserProfileAccess.granted_at))

            # Get total count
            count_query = select(func.count()).select_from(base_query.subquery())
            count_result = await db.execute(count_query)
            total_unlocked = count_result.scalar()

            # Get paginated results
            paginated_query = base_query.offset(offset).limit(page_size)
            results = await db.execute(paginated_query)
            access_records = results.fetchall()

            # Format response
            unlocked_profiles = []
            current_time = datetime.now(timezone.utc)

            for access, profile in access_records:
                is_active = access.expires_at > current_time
                days_remaining = (access.expires_at - current_time).days if is_active else 0

                unlocked_profiles.append({
                    "profile": {
                        "id": str(profile.id),
                        "username": profile.username,
                        "full_name": profile.full_name,
                        "biography": profile.biography,
                        "profile_pic_url": profile.profile_pic_url,
                        "followers_count": profile.followers_count,
                        "following_count": profile.following_count,
                        "posts_count": profile.posts_count,
                        "is_verified": profile.is_verified,
                        "ai_analysis": {
                            "primary_content_type": profile.ai_primary_content_type,
                            "avg_sentiment_score": profile.ai_avg_sentiment_score,
                            "content_quality_score": profile.ai_content_quality_score
                        }
                    },
                    "access_info": {
                        "granted_at": access.granted_at.isoformat() if access.granted_at else None,
                        "expires_at": access.expires_at.isoformat() if access.expires_at else None,
                        "is_active": is_active,
                        "days_remaining": max(0, days_remaining),
                        "hours_remaining": max(0, int((access.expires_at - current_time).total_seconds() / 3600)) if is_active else 0
                    }
                })

            # Calculate pagination
            total_pages = (total_unlocked + page_size - 1) // page_size
            has_next = page < total_pages
            has_previous = page > 1

            # Count active vs expired
            active_count = sum(1 for p in unlocked_profiles if p["access_info"]["is_active"])
            expired_count = len(unlocked_profiles) - active_count

            return {
                "success": True,
                "profiles": unlocked_profiles,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_unlocked": total_unlocked,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_previous": has_previous
                },
                "summary": {
                    "active_unlocks": active_count,
                    "expired_unlocks": expired_count,
                    "total_unlocks": len(unlocked_profiles)
                }
            }

        except Exception as e:
            logger.error(f"Get unlocked profiles failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def get_discovery_stats(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get discovery system statistics for user dashboard

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Discovery statistics and user activity
        """
        try:
            # Total profiles in discovery
            total_profiles_query = select(func.count(Profile.id)).where(
                and_(
                    Profile.followers_count > 0,
                    Profile.posts_count > 0,
                    Profile.biography.isnot(None),
                    Profile.ai_profile_analyzed_at.isnot(None)
                )
            )
            total_result = await db.execute(total_profiles_query)
            total_profiles = total_result.scalar()

            # User's unlocked profiles
            user_unlocked_query = select(func.count(UserProfileAccess.id)).where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )
            )
            unlocked_result = await db.execute(user_unlocked_query)
            user_unlocked = unlocked_result.scalar()

            # User's expired unlocks
            user_expired_query = select(func.count(UserProfileAccess.id)).where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.expires_at <= datetime.now(timezone.utc)
                )
            )
            expired_result = await db.execute(user_expired_query)
            user_expired = expired_result.scalar()

            # Content categories breakdown
            categories_query = select(
                Profile.ai_primary_content_type,
                func.count(Profile.id).label('count')
            ).where(
                and_(
                    Profile.followers_count > 0,
                    Profile.ai_primary_content_type.isnot(None)
                )
            ).group_by(Profile.ai_primary_content_type).order_by(desc('count'))

            categories_result = await db.execute(categories_query)
            categories = [
                {"category": row[0], "count": row[1]}
                for row in categories_result.fetchall()
            ]

            # User's credit balance - get existing wallet or create if needed
            wallet = await credit_wallet_service.get_wallet(user_id)
            if not wallet:
                wallet = await credit_wallet_service.create_wallet(user_id)

            return {
                "success": True,
                "discovery_overview": {
                    "total_profiles_available": total_profiles,
                    "user_unlocked_profiles": user_unlocked,
                    "user_expired_profiles": user_expired,
                    "discovery_percentage": round((user_unlocked / total_profiles * 100), 2) if total_profiles > 0 else 0
                },
                "content_categories": categories[:10],  # Top 10 categories
                "user_credits": {
                    "current_balance": wallet.current_balance,
                    "lifetime_earned": wallet.lifetime_earned,
                    "lifetime_spent": wallet.lifetime_spent,
                    "unlock_cost": 25,  # Credits per profile unlock
                    "possible_unlocks": wallet.current_balance // 25
                },
                "discovery_tips": [
                    "Each profile unlock gives you 30 days of full access",
                    "Use filters to find profiles matching your campaign needs",
                    "Unlock expires automatically after 30 days - renew as needed",
                    "Your credit balance allows for new discoveries"
                ]
            }

        except Exception as e:
            logger.error(f"Discovery stats failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def search_profiles_advanced(
        self,
        db: AsyncSession,
        user_id: UUID,
        search_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Advanced profile search with multiple criteria

        Args:
            db: Database session
            user_id: User ID for unlock status
            search_params: Advanced search parameters

        Returns:
            Advanced search results
        """
        # Extract search parameters
        query = search_params.get('query', '')
        categories = search_params.get('categories', [])
        follower_range = search_params.get('follower_range', {})
        sentiment_filter = search_params.get('sentiment_filter')
        verified_only = search_params.get('verified_only', False)
        private_filter = search_params.get('private_filter', 'all')  # all, public, private
        sort_by = search_params.get('sort_by', 'followers_desc')
        page = search_params.get('page', 1)
        page_size = search_params.get('page_size', 20)

        # Use the browse_all_profiles method with advanced parameters
        return await self.browse_all_profiles(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
            search_query=query,
            category_filter=categories[0] if categories else None,
            min_followers=follower_range.get('min'),
            max_followers=follower_range.get('max'),
            sort_by=sort_by,
            include_unlocked_status=True
        )


# Global service instance
user_discovery_service = UserDiscoveryService()