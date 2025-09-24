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

from app.database.unified_models import (
    User, UserList, UserListItem, Profile, UserProfileAccess,
    ListTemplate, ListCollaboration, ListPerformanceMetrics, ListExportJob
)
from app.models.lists import (
    UserListCreate, UserListUpdate, UserListResponse, UserListSummary,
    UserListItemCreate, UserListItemUpdate, UserListItemResponse,
    UserListItemBulkCreate, ProfileSummary, PaginationInfo, ListAnalyticsSummary
)

logger = logging.getLogger(__name__)

class ListsService:
    """Service class for My Lists functionality"""
    
    async def _get_database_user_id(self, db: AsyncSession, supabase_user_id: UUID) -> UUID:
        """Convert Supabase user ID to database user ID with caching"""
        from sqlalchemy import text
        from app.services.redis_cache_service import redis_cache

        # Try cache first
        try:
            cached_user_id = await redis_cache.get("user_id_mapping", str(supabase_user_id))
            if cached_user_id:
                return UUID(cached_user_id)
        except Exception as cache_error:
            logger.warning(f"Cache lookup failed for user {supabase_user_id}: {cache_error}")

        # Query database - enterprise-grade UUID handling with proper type casting
        result = await db.execute(
            text("SELECT id FROM users WHERE id = CAST(:user_id AS uuid) OR supabase_user_id = :user_id_text"),
            {"user_id": str(supabase_user_id), "user_id_text": str(supabase_user_id)}
        )
        user_row = result.fetchone()
        if not user_row:
            raise ValueError(f"User {supabase_user_id} not found in database")

        # Cache for 30 minutes
        user_id = user_row[0]
        try:
            await redis_cache.set("user_id_mapping", str(supabase_user_id), str(user_id), ttl=1800)
        except Exception as cache_error:
            logger.warning(f"Cache set failed for user {supabase_user_id}: {cache_error}")

        return user_id
    
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
    
    async def _log_activity(
        self,
        db: AsyncSession,
        list_id: UUID,
        list_item_id: Optional[UUID],
        user_id: UUID,
        action_type: str,
        action_description: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        affected_fields: Optional[List[str]] = None
    ):
        """Log activity for audit trail - temporarily disabled due to missing table"""
        try:
            # TODO: Re-enable when list_activity_logs table is created
            logger.info(f"List activity: {action_type} - {action_description} for list {list_id}")
            pass
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
    
    async def _check_list_permission(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID, 
        required_permission: str = "view"
    ) -> bool:
        """Check if user has permission to access list"""
        try:
            # Check if user owns the list
            owner_query = select(UserList).where(
                and_(UserList.id == list_id, UserList.user_id == user_id)
            )
            owner_result = await db.execute(owner_query)
            if owner_result.scalar_one_or_none():
                return True
            
            # Check collaboration permissions
            collab_query = select(ListCollaboration).where(
                and_(
                    ListCollaboration.list_id == list_id,
                    ListCollaboration.shared_with_user_id == user_id,
                    ListCollaboration.status == 'accepted'
                )
            )
            collab_result = await db.execute(collab_query)
            collaboration = collab_result.scalar_one_or_none()
            
            if not collaboration:
                return False
                
            # Check permission level
            permission_hierarchy = {
                "view": ["view", "comment", "edit", "admin"],
                "comment": ["comment", "edit", "admin"],
                "edit": ["edit", "admin"],
                "admin": ["admin"]
            }
            
            return collaboration.permission_level in permission_hierarchy.get(required_permission, [])
            
        except Exception as e:
            logger.error(f"Error checking list permission: {e}")
            return False
    
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
        """Create a new list with enhanced features"""
        try:
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Create new list with enhanced fields
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
            
            # Log activity
            await self._log_activity(
                db, new_list.id, None, database_user_id,
                "list_created", f"Created list '{list_data.name}'"
            )
            
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

    # ===============================================================================
    # ENHANCED LISTS FEATURES - Templates, Collaboration, Analytics, Export
    # ===============================================================================
    
    async def get_list_templates(
        self, 
        db: AsyncSession, 
        user_id: UUID,
        category: Optional[str] = None,
        public_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get available list templates"""
        try:
            query = select(ListTemplate)
            
            if category:
                query = query.where(ListTemplate.category == category)
            
            if public_only:
                query = query.where(ListTemplate.is_public == True)
            else:
                # Include public templates and user's private templates
                query = query.where(
                    or_(
                        ListTemplate.is_public == True,
                        ListTemplate.created_by == user_id
                    )
                )
            
            query = query.order_by(ListTemplate.usage_count.desc(), ListTemplate.template_name)
            
            result = await db.execute(query)
            templates = result.scalars().all()
            
            return [template.__dict__ for template in templates]
            
        except Exception as e:
            logger.error(f"Error getting list templates: {e}")
            raise
    
    async def create_list_from_template(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        template_id: UUID,
        list_name: str,
        customize_settings: Optional[Dict] = None
    ) -> UserListResponse:
        """Create a list from a template"""
        try:
            # Get template
            template_query = select(ListTemplate).where(ListTemplate.id == template_id)
            template_result = await db.execute(template_query)
            template = template_result.scalar_one_or_none()
            
            if not template:
                raise ValueError("Template not found")
            
            # Convert Supabase user ID to database user ID
            database_user_id = await self._get_database_user_id(db, user_id)
            
            # Merge template settings with customizations
            template_settings = template.default_settings.copy()
            if customize_settings:
                template_settings.update(customize_settings)
            
            # Create list from template
            new_list = UserList(
                user_id=database_user_id,
                name=list_name,
                description=template.description,
                color=template.color or "#3B82F6",
                icon=template.icon or "list"
            )
            
            db.add(new_list)
            
            # Update template usage count
            await db.execute(
                update(ListTemplate)
                .where(ListTemplate.id == template_id)
                .values(usage_count=ListTemplate.usage_count + 1)
            )
            
            await db.commit()
            await db.refresh(new_list)
            
            # Log activity
            await self._log_activity(
                db, new_list.id, None, database_user_id,
                "list_created_from_template", f"Created list '{list_name}' from template '{template.template_name}'"
            )
            await db.commit()
            
            return UserListResponse(**new_list.__dict__, items=[])
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating list from template: {e}")
            raise
    
    async def share_list(
        self, 
        db: AsyncSession, 
        owner_user_id: UUID, 
        list_id: UUID,
        shared_with_user_id: UUID,
        permission_level: str = "view",
        invitation_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Share a list with another user"""
        try:
            # Check if user owns the list
            if not await self._check_list_permission(db, owner_user_id, list_id, "admin"):
                raise ValueError("You don't have permission to share this list")
            
            # Check if already shared with this user
            existing_query = select(ListCollaboration).where(
                and_(
                    ListCollaboration.list_id == list_id,
                    ListCollaboration.shared_with_user_id == shared_with_user_id
                )
            )
            existing_result = await db.execute(existing_query)
            existing_collaboration = existing_result.scalar_one_or_none()
            
            if existing_collaboration:
                if existing_collaboration.status == 'accepted':
                    raise ValueError("List already shared with this user")
                else:
                    # Update existing invitation
                    existing_collaboration.permission_level = permission_level
                    existing_collaboration.invitation_message = invitation_message
                    existing_collaboration.status = 'pending'
                    existing_collaboration.updated_at = datetime.now(timezone.utc)
            else:
                # Create new collaboration
                collaboration = ListCollaboration(
                    list_id=list_id,
                    shared_with_user_id=shared_with_user_id,
                    shared_by_user_id=owner_user_id,
                    permission_level=permission_level,
                    invitation_message=invitation_message,
                    status='pending'
                )
                db.add(collaboration)
            
            # Update list sharing status
            await db.execute(
                update(UserList)
                .where(UserList.id == list_id)
                .values(is_shared=True)
            )
            
            await db.commit()
            
            # Log activity
            await self._log_activity(
                db, list_id, None, owner_user_id,
                "list_shared", f"Shared list with user {shared_with_user_id} ({permission_level} access)"
            )
            await db.commit()
            
            return {"success": True, "message": "List shared successfully"}
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error sharing list: {e}")
            raise
    
    async def get_shared_lists(
        self, 
        db: AsyncSession, 
        user_id: UUID,
        status: str = "accepted"
    ) -> List[Dict[str, Any]]:
        """Get lists shared with the user"""
        try:
            query = select(UserList, ListCollaboration).join(
                ListCollaboration,
                UserList.id == ListCollaboration.list_id
            ).where(
                and_(
                    ListCollaboration.shared_with_user_id == user_id,
                    ListCollaboration.status == status
                )
            ).order_by(ListCollaboration.accepted_at.desc())
            
            result = await db.execute(query)
            shared_lists = []
            
            for user_list, collaboration in result:
                list_dict = user_list.__dict__.copy()
                list_dict['shared_by_user_id'] = collaboration.shared_by_user_id
                list_dict['permission_level'] = collaboration.permission_level
                list_dict['accepted_at'] = collaboration.accepted_at
                shared_lists.append(list_dict)
            
            return shared_lists
            
        except Exception as e:
            logger.error(f"Error getting shared lists: {e}")
            raise
    
    async def get_list_activity(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """Get activity log for a list"""
        try:
            # Check permission
            if not await self._check_list_permission(db, user_id, list_id, "view"):
                raise ValueError("You don't have permission to view this list")
            
            offset = (page - 1) * page_size
            
            # Activity logs temporarily disabled - return empty result
            activities = []
            total_items = 0
            
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
                "activities": activities,
                "pagination": pagination.dict()
            }
            
        except Exception as e:
            logger.error(f"Error getting list activity: {e}")
            raise
    
    async def export_list(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID,
        export_format: str = "csv",
        include_unlocked_data: bool = False,
        export_fields: Optional[List[str]] = None
    ) -> UUID:
        """Create an export job for a list"""
        try:
            # Check permission
            if not await self._check_list_permission(db, user_id, list_id, "view"):
                raise ValueError("You don't have permission to export this list")
            
            # Create export job
            export_job = ListExportJob(
                list_id=list_id,
                user_id=user_id,
                export_format=export_format,
                export_fields=export_fields or ["username", "followers_count", "engagement_rate"],
                include_unlocked_data=include_unlocked_data,
                status='pending'
            )
            
            db.add(export_job)
            await db.commit()
            await db.refresh(export_job)
            
            # Log activity
            await self._log_activity(
                db, list_id, None, user_id,
                "export_requested", f"Requested {export_format} export"
            )
            await db.commit()
            
            # TODO: Trigger background job for actual export processing
            # This would be handled by a Celery task or similar
            
            return export_job.id
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating export job: {e}")
            raise
    
    async def get_list_analytics(
        self, 
        db: AsyncSession, 
        user_id: UUID, 
        list_id: UUID,
        date_range: Optional[int] = 30  # days
    ) -> Dict[str, Any]:
        """Get analytics for a list"""
        try:
            # Check permission
            if not await self._check_list_permission(db, user_id, list_id, "view"):
                raise ValueError("You don't have permission to view this list analytics")
            
            # Get basic list info
            list_query = select(UserList).where(UserList.id == list_id)
            list_result = await db.execute(list_query)
            user_list = list_result.scalar_one_or_none()
            
            if not user_list:
                raise ValueError("List not found")
            
            # Get recent metrics
            from datetime import date, timedelta
            start_date = date.today() - timedelta(days=date_range)
            
            metrics_query = select(ListPerformanceMetrics).where(
                and_(
                    ListPerformanceMetrics.list_id == list_id,
                    ListPerformanceMetrics.date_recorded >= start_date
                )
            ).order_by(ListPerformanceMetrics.date_recorded.desc())
            
            metrics_result = await db.execute(metrics_query)
            metrics = metrics_result.scalars().all()
            
            # Calculate summary statistics
            total_items = user_list.items_count
            unlocked_items = sum(m.unlocked_items for m in metrics) if metrics else 0
            total_views = sum(m.views_count for m in metrics) if metrics else 0
            
            return {
                "list_info": {
                    "id": str(list_id),
                    "name": user_list.name,
                    "total_items": total_items,
                    "created_at": user_list.created_at,
                    "last_updated": user_list.last_updated
                },
                "summary": {
                    "total_items": total_items,
                    "unlocked_items": unlocked_items,
                    "unlock_rate": (unlocked_items / total_items * 100) if total_items > 0 else 0,
                    "total_views": total_views,
                    "avg_daily_views": total_views / date_range if date_range > 0 else 0
                },
                "daily_metrics": [
                    {
                        "date": m.date_recorded,
                        "items": m.total_items,
                        "unlocked": m.unlocked_items,
                        "views": m.views_count,
                        "updates": m.updates_count
                    } for m in metrics
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting list analytics: {e}")
            raise

# Create service instance
lists_service = ListsService()