"""
My Lists Service - Business logic for user lists functionality
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, text
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import logging
from datetime import datetime, timezone

from app.database.unified_models import User, UserList, UserListItem, Profile, UserProfileAccess
from app.models.lists import (
    UserListCreate, UserListUpdate, UserListResponse, UserListSummary,
    UserListItemCreate, UserListItemUpdate, UserListItemResponse,
    UserListItemBulkCreate, ProfileSummary, PaginationInfo, ListAnalyticsSummary
)

logger = logging.getLogger(__name__)

class ListsService:
    """Service class for My Lists functionality"""
    
    async def _get_database_user_id(self, db: AsyncSession, supabase_user_id: UUID) -> UUID:
        """Convert Supabase user ID to database user ID"""
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT id FROM users WHERE id::text = :user_id OR supabase_user_id::text = :user_id"), 
            {"user_id": str(supabase_user_id)}
        )
        user_row = result.fetchone()
        if not user_row:
            raise ValueError(f"User {supabase_user_id} not found in database")
        return user_row[0]
    
    async def _get_profile_id_from_username(self, db: AsyncSession, username: str) -> UUID:
        """Get profile ID from username"""
        result = await db.execute(
            select(Profile.id).where(Profile.username == username)
        )
        profile_row = result.fetchone()
        if not profile_row:
            raise ValueError(f"Profile with username '{username}' not found")
        return profile_row[0]
    
    async def _resolve_profile_id(self, db: AsyncSession, item_data: UserListItemCreate) -> UUID:
        """Resolve profile ID from either profile_id or profile_username"""
        if item_data.profile_id:
            return item_data.profile_id
        elif item_data.profile_username:
            return await self._get_profile_id_from_username(db, item_data.profile_username)
        else:
            raise ValueError("Either profile_id or profile_username must be provided")
    
    async def _resolve_bulk_profile_ids(self, db: AsyncSession, bulk_data: UserListItemBulkCreate) -> List[UUID]:
        """Resolve multiple profile IDs from either profile_ids or profile_usernames"""
        if bulk_data.profile_ids:
            return bulk_data.profile_ids
        elif bulk_data.profile_usernames:
            profile_ids = []
            for username in bulk_data.profile_usernames:
                profile_id = await self._get_profile_id_from_username(db, username)
                profile_ids.append(profile_id)
            return profile_ids
        else:
            raise ValueError("Either profile_ids or profile_usernames must be provided")
    
    async def get_user_lists(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        include_items: bool = False,
        sort_by: str = "created_at",
        order: str = "desc",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get all lists for a user with pagination"""
        try:
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Calculate offset
            offset = (page - 1) * page_size
            
            # Build base query
            query = select(UserList).where(UserList.user_id == database_user_id)
            
            # Add sorting
            sort_column = getattr(UserList, sort_by, UserList.created_at)
            if order.lower() == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # Add eager loading for items if requested
            if include_items:
                query = query.options(
                    selectinload(UserList.list_items)
                    .selectinload(UserListItem.profile)
                )
            
            # Get total count
            count_query = select(func.count(UserList.id)).where(UserList.user_id == database_user_id)
            total_result = await db.execute(count_query)
            total_items = total_result.scalar() or 0
            
            # Apply pagination
            query = query.offset(offset).limit(page_size)
            
            # Execute query
            result = await db.execute(query)
            lists = result.scalars().all()
            
            # Convert to response models
            if include_items:
                list_data = [
                    UserListResponse(
                        **list_obj.__dict__,
                        items=[
                            UserListItemResponse(
                                **item.__dict__,
                                profile=ProfileSummary(**item.profile.__dict__)
                            ) for item in sorted(list_obj.list_items, key=lambda x: x.position)
                        ]
                    ) for list_obj in lists
                ]
            else:
                list_data = [UserListSummary(**list_obj.__dict__) for list_obj in lists]
            
            # Calculate pagination
            total_pages = (total_items + page_size - 1) // page_size
            pagination = PaginationInfo(
                current_page=page,
                total_pages=total_pages,
                total_items=total_items,
                items_per_page=page_size,
                has_next=page < total_pages,
                has_prev=page > 1
            )
            
            return {
                "lists": list_data,
                "pagination": pagination.dict()
            }
            
        except Exception as e:
            logger.error(f"Error getting user lists: {e}")
            raise

    async def get_list_by_id(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID,
        include_profiles: bool = True,
        sort_items: str = "position"
    ) -> Optional[UserListResponse]:
        """Get a specific list with its items"""
        try:
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Build query with eager loading
            query = select(UserList).where(
                and_(UserList.id == list_id, UserList.user_id == database_user_id)
            ).options(
                selectinload(UserList.list_items)
                .selectinload(UserListItem.profile)
            )
            
            result = await db.execute(query)
            list_obj = result.scalar_one_or_none()
            
            if not list_obj:
                return None
            
            # Sort items
            items = list_obj.list_items
            if sort_items == "position":
                items = sorted(items, key=lambda x: (not x.is_pinned, x.position))
            elif sort_items == "added_at":
                items = sorted(items, key=lambda x: x.added_at, reverse=True)
            elif sort_items == "name":
                items = sorted(items, key=lambda x: x.profile.username.lower())
            
            # Convert to response model
            return UserListResponse(
                **list_obj.__dict__,
                items=[
                    UserListItemResponse(
                        **item.__dict__,
                        profile=ProfileSummary(**item.profile.__dict__) if include_profiles else None
                    ) for item in items
                ]
            )
            
        except Exception as e:
            logger.error(f"Error getting list {list_id}: {e}")
            raise

    async def create_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_data: UserListCreate
    ) -> UserListResponse:
        """Create a new list"""
        try:
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Create new list
            new_list = UserList(
                user_id=database_user_id,
                name=list_data.name,
                description=list_data.description,
                color=list_data.color or "#3B82F6",
                icon=list_data.icon or "list",
                is_favorite=list_data.is_favorite or False
            )
            
            db.add(new_list)
            await db.commit()
            await db.refresh(new_list)
            
            return UserListResponse(**new_list.__dict__, items=[])
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating list: {e}")
            raise

    async def update_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        list_data: UserListUpdate
    ) -> Optional[UserListResponse]:
        """Update an existing list"""
        try:
            # Get existing list
            query = select(UserList).where(
                and_(UserList.id == list_id, UserList.user_id == user_id)
            )
            result = await db.execute(query)
            list_obj = result.scalar_one_or_none()
            
            if not list_obj:
                return None
            
            # Update fields
            update_data = list_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(list_obj, field, value)
            
            await db.commit()
            await db.refresh(list_obj)
            
            return UserListResponse(**list_obj.__dict__, items=[])
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating list {list_id}: {e}")
            raise

    async def delete_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID
    ) -> bool:
        """Delete a list and all its items"""
        try:
            # Delete the list (cascade will handle items)
            result = await db.execute(
                delete(UserList).where(
                    and_(UserList.id == list_id, UserList.user_id == user_id)
                )
            )
            
            await db.commit()
            return result.rowcount > 0
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting list {list_id}: {e}")
            raise

    async def add_profile_to_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        item_data: UserListItemCreate
    ) -> Optional[UserListItemResponse]:
        """Add a profile to a list"""
        try:
            # Verify user owns the list
            list_query = select(UserList).where(
                and_(UserList.id == list_id, UserList.user_id == user_id)
            )
            list_result = await db.execute(list_query)
            list_obj = list_result.scalar_one_or_none()
            
            if not list_obj:
                return None
            
            # Resolve profile ID from username or UUID
            profile_id = await self._resolve_profile_id(db, item_data)
            
            # Verify user has access to the profile
            access_query = select(UserProfileAccess).where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.profile_id == profile_id,
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )
            )
            access_result = await db.execute(access_query)
            access_obj = access_result.scalar_one_or_none()
            
            if not access_obj:
                raise ValueError("Profile access required")
            
            # Check if profile already in list
            existing_query = select(UserListItem).where(
                and_(
                    UserListItem.list_id == list_id,
                    UserListItem.profile_id == profile_id
                )
            )
            existing_result = await db.execute(existing_query)
            existing_item = existing_result.scalar_one_or_none()
            
            if existing_item:
                raise ValueError("Profile already in list")
            
            # Get profile data
            profile_query = select(Profile).where(Profile.id == profile_id)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()
            
            if not profile:
                raise ValueError("Profile not found")
            
            # Create new list item
            new_item = UserListItem(
                list_id=list_id,
                profile_id=profile_id,
                user_id=user_id,
                position=item_data.position or 0,
                notes=item_data.notes,
                tags=item_data.tags or [],
                is_pinned=item_data.is_pinned or False,
                color_label=item_data.color_label
            )
            
            db.add(new_item)
            await db.commit()
            await db.refresh(new_item)
            
            return UserListItemResponse(
                **new_item.__dict__,
                profile=ProfileSummary(**profile.__dict__)
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error adding profile to list: {e}")
            raise

    async def update_list_item(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        item_id: UUID, 
        item_data: UserListItemUpdate
    ) -> Optional[UserListItemResponse]:
        """Update a list item"""
        try:
            # Get item with profile data
            query = select(UserListItem).where(
                and_(
                    UserListItem.id == item_id,
                    UserListItem.list_id == list_id,
                    UserListItem.user_id == user_id
                )
            ).options(joinedload(UserListItem.profile))
            
            result = await db.execute(query)
            item = result.scalar_one_or_none()
            
            if not item:
                return None
            
            # Update fields
            update_data = item_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(item, field, value)
            
            await db.commit()
            await db.refresh(item)
            
            return UserListItemResponse(
                **item.__dict__,
                profile=ProfileSummary(**item.profile.__dict__)
            )
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating list item {item_id}: {e}")
            raise

    async def remove_profile_from_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        item_id: UUID
    ) -> bool:
        """Remove a profile from a list"""
        try:
            result = await db.execute(
                delete(UserListItem).where(
                    and_(
                        UserListItem.id == item_id,
                        UserListItem.list_id == list_id,
                        UserListItem.user_id == user_id
                    )
                )
            )
            
            await db.commit()
            return result.rowcount > 0
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error removing item {item_id} from list: {e}")
            raise

    async def bulk_add_profiles_to_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        bulk_data: UserListItemBulkCreate
    ) -> Dict[str, Any]:
        """Add multiple profiles to a list"""
        try:
            # Verify user owns the list
            list_query = select(UserList).where(
                and_(UserList.id == list_id, UserList.user_id == user_id)
            )
            list_result = await db.execute(list_query)
            list_obj = list_result.scalar_one_or_none()
            
            if not list_obj:
                raise ValueError("List not found")
            
            # Resolve profile IDs from bulk data
            profile_ids = await self._resolve_bulk_profile_ids(db, bulk_data)
            
            # Get user's accessible profiles
            accessible_query = select(UserProfileAccess.profile_id).where(
                and_(
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.profile_id.in_(profile_ids),
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )
            )
            accessible_result = await db.execute(accessible_query)
            accessible_profiles = {row[0] for row in accessible_result.fetchall()}
            
            # Get already added profiles
            existing_query = select(UserListItem.profile_id).where(
                and_(
                    UserListItem.list_id == list_id,
                    UserListItem.profile_id.in_(profile_ids)
                )
            )
            existing_result = await db.execute(existing_query)
            existing_profiles = {row[0] for row in existing_result.fetchall()}
            
            # Create items for valid, non-existing profiles
            valid_profiles = accessible_profiles - existing_profiles
            added_count = 0
            items_created = []
            
            for i, profile_id in enumerate(valid_profiles):
                new_item = UserListItem(
                    list_id=list_id,
                    profile_id=profile_id,
                    user_id=user_id,
                    position=i,
                    notes=bulk_data.notes,
                    tags=bulk_data.tags or []
                )
                db.add(new_item)
                items_created.append(new_item)
                added_count += 1
            
            await db.commit()
            
            # Refresh and get profile data
            for item in items_created:
                await db.refresh(item)
            
            return {
                "added_count": added_count,
                "skipped_count": len(profile_ids) - added_count,
                "items": items_created
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error bulk adding profiles to list: {e}")
            raise

    async def reorder_list_items(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        item_positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Reorder items in a list"""
        try:
            # Verify user owns the list
            list_query = select(UserList).where(
                and_(UserList.id == list_id, UserList.user_id == user_id)
            )
            list_result = await db.execute(list_query)
            list_obj = list_result.scalar_one_or_none()
            
            if not list_obj:
                raise ValueError("List not found")
            
            updated_count = 0
            
            # Update positions
            for position_data in item_positions:
                result = await db.execute(
                    update(UserListItem)
                    .where(
                        and_(
                            UserListItem.id == position_data["item_id"],
                            UserListItem.list_id == list_id,
                            UserListItem.user_id == user_id
                        )
                    )
                    .values(position=position_data["position"])
                )
                updated_count += result.rowcount
            
            await db.commit()
            
            return {"updated_count": updated_count}
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error reordering list items: {e}")
            raise

    async def get_available_profiles_for_lists(
        self, 
        db: AsyncSession, 
        user_id: UUID,
        search: Optional[str] = None,
        not_in_list: Optional[UUID] = None,
        category: Optional[str] = None,
        min_followers: Optional[int] = None,
        verified_only: bool = False,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get profiles available to add to lists"""
        try:
            # Base query for accessible profiles
            query = select(Profile).join(
                UserProfileAccess,
                and_(
                    UserProfileAccess.profile_id == Profile.id,
                    UserProfileAccess.user_id == user_id,
                    UserProfileAccess.expires_at > datetime.now(timezone.utc)
                )
            )
            
            # Apply filters
            if search:
                query = query.where(
                    or_(
                        Profile.username.ilike(f"%{search}%"),
                        Profile.full_name.ilike(f"%{search}%")
                    )
                )
            
            if not_in_list:
                # Exclude profiles already in the specified list
                subquery = select(UserListItem.profile_id).where(
                    UserListItem.list_id == not_in_list
                )
                query = query.where(~Profile.id.in_(subquery))
            
            if category:
                query = query.where(Profile.category.ilike(f"%{category}%"))
            
            if min_followers:
                query = query.where(Profile.followers_count >= min_followers)
            
            if verified_only:
                query = query.where(Profile.is_verified == True)
            
            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total_items = total_result.scalar() or 0
            
            # Apply pagination and ordering
            offset = (page - 1) * page_size
            query = query.order_by(Profile.followers_count.desc())
            query = query.offset(offset).limit(page_size)
            
            # Execute query
            result = await db.execute(query)
            profiles = result.scalars().all()
            
            # Get list counts for each profile
            profile_data = []
            for profile in profiles:
                # Count how many lists this profile is in for this user
                count_query = select(func.count(UserListItem.id)).where(
                    and_(
                        UserListItem.profile_id == profile.id,
                        UserListItem.user_id == user_id
                    )
                )
                count_result = await db.execute(count_query)
                in_lists_count = count_result.scalar() or 0
                
                profile_dict = profile.__dict__.copy()
                profile_dict['in_lists_count'] = in_lists_count
                profile_dict['access_expires_at'] = None  # Could add this if needed
                
                profile_data.append(profile_dict)
            
            # Calculate pagination
            total_pages = (total_items + page_size - 1) // page_size
            pagination = PaginationInfo(
                current_page=page,
                total_pages=total_pages,
                total_items=total_items,
                items_per_page=page_size,
                has_next=page < total_pages,
                has_prev=page > 1
            )
            
            return {
                "profiles": profile_data,
                "pagination": pagination.dict()
            }
            
        except Exception as e:
            logger.error(f"Error getting available profiles: {e}")
            raise

# Create service instance
lists_service = ListsService()