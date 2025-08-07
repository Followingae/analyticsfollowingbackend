"""
My Lists API Routes - Complete CRUD operations for user lists
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
import logging

from app.models.lists import (
    UserListCreate, UserListUpdate, UserListResponse, UserListsResponse,
    UserListItemCreate, UserListItemUpdate, UserListItemResponse,
    UserListItemBulkCreate, ListReorderRequest, ListDuplicateRequest,
    BulkOperationRequest, BulkOperationResponse, ErrorResponse,
    AvailableProfilesResponse, SingleListResponse
)
from app.models.auth import UserInDB
from app.middleware.auth_middleware import get_current_active_user
from app.database.connection import get_db
from app.services.lists_service import lists_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lists", tags=["My Lists"])

# =============================================================================
# LISTS MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("", response_model=UserListsResponse)
async def get_user_lists(
    include_items: bool = Query(False, description="Include list items in response"),
    sort: str = Query("created_at", description="Sort by: created_at, updated_at, name, items_count"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all lists for the authenticated user
    
    Returns paginated list of user's custom lists with optional item inclusion.
    Supports sorting and filtering options.
    """
    try:
        # Validate sort field
        valid_sort_fields = ["created_at", "updated_at", "name", "items_count", "last_updated"]
        if sort not in valid_sort_fields:
            sort = "created_at"
        
        result = await lists_service.get_user_lists(
            db=db,
            user_id=current_user.id,
            include_items=include_items,
            sort_by=sort,
            order=order,
            page=page,
            page_size=limit
        )
        
        return UserListsResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error getting user lists for {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user lists"
        )

@router.get("/{list_id}", response_model=SingleListResponse)
async def get_list(
    list_id: UUID,
    include_profiles: bool = Query(True, description="Include full profile data"),
    sort_items: str = Query("position", pattern="^(position|added_at|name)$", description="Sort items by"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific list with all its items
    
    Returns detailed list information including all profiles in the list.
    Items can be sorted by position, added date, or profile name.
    """
    try:
        list_data = await lists_service.get_list_by_id(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            include_profiles=include_profiles,
            sort_items=sort_items
        )
        
        if not list_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List not found"
            )
        
        return SingleListResponse(
            success=True,
            data=list_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting list {list_id} for {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve list"
        )

@router.post("", response_model=SingleListResponse, status_code=status.HTTP_201_CREATED)
async def create_list(
    list_data: UserListCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new list
    
    Creates a new custom list for organizing Instagram profiles.
    All fields except name are optional with sensible defaults.
    """
    try:
        new_list = await lists_service.create_list(
            db=db,
            user_id=current_user.id,
            list_data=list_data
        )
        
        return SingleListResponse(
            success=True,
            data=new_list,
            message="List created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating list for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create list"
        )

@router.put("/{list_id}", response_model=SingleListResponse)
async def update_list(
    list_id: UUID,
    list_data: UserListUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing list
    
    Updates list metadata such as name, description, color, and settings.
    Only provided fields will be updated.
    """
    try:
        updated_list = await lists_service.update_list(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            list_data=list_data
        )
        
        if not updated_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List not found"
            )
        
        return SingleListResponse(
            success=True,
            data=updated_list,
            message="List updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating list {list_id} for {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update list"
        )

@router.delete("/{list_id}")
async def delete_list(
    list_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a list and all its items
    
    Permanently removes the list and all associated profile items.
    This action cannot be undone.
    """
    try:
        success = await lists_service.delete_list(
            db=db,
            user_id=current_user.id,
            list_id=list_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List not found"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "message": "List deleted successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting list {list_id} for {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete list"
        )

# =============================================================================
# LIST ITEMS MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/{list_id}/items", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_profile_to_list(
    list_id: UUID,
    item_data: UserListItemCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a profile to a list
    
    Adds an Instagram profile to the specified list.
    Requires user to have access to the profile (30-day unlocked access).
    """
    try:
        new_item = await lists_service.add_profile_to_list(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            item_data=item_data
        )
        
        if not new_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List not found"
            )
        
        return {
            "success": True,
            "data": new_item.dict(),
            "message": "Profile added to list successfully"
        }
        
    except ValueError as ve:
        if "Profile access required" in str(ve):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this profile"
            )
        elif "Profile already in list" in str(ve):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile already exists in this list"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding profile to list {list_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add profile to list"
        )

@router.put("/{list_id}/items/{item_id}", response_model=dict)
async def update_list_item(
    list_id: UUID,
    item_id: UUID,
    item_data: UserListItemUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a list item
    
    Updates item-specific data such as notes, tags, position, and visual settings.
    Only provided fields will be updated.
    """
    try:
        updated_item = await lists_service.update_list_item(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            item_id=item_id,
            item_data=item_data
        )
        
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List item not found"
            )
        
        return {
            "success": True,
            "data": updated_item.dict(),
            "message": "List item updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating list item {item_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update list item"
        )

@router.delete("/{list_id}/items/{item_id}")
async def remove_profile_from_list(
    list_id: UUID,
    item_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a profile from a list
    
    Removes the specified profile from the list.
    This does not affect the user's access to the profile.
    """
    try:
        success = await lists_service.remove_profile_from_list(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            item_id=item_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="List item not found"
            )
        
        return JSONResponse(
            content={
                "success": True,
                "message": "Profile removed from list successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing item {item_id} from list {list_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove profile from list"
        )

@router.post("/{list_id}/items/bulk", response_model=BulkOperationResponse)
async def bulk_add_profiles_to_list(
    list_id: UUID,
    bulk_data: UserListItemBulkCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add multiple profiles to a list
    
    Efficiently adds multiple profiles to a list in a single operation.
    Only profiles the user has access to will be added.
    """
    try:
        result = await lists_service.bulk_add_profiles_to_list(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            bulk_data=bulk_data
        )
        
        return BulkOperationResponse(
            success=True,
            data=result,
            message=f"Added {result['added_count']} profiles to list"
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error bulk adding profiles to list {list_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add profiles to list"
        )

# =============================================================================
# LIST OPERATIONS ENDPOINTS
# =============================================================================

@router.put("/{list_id}/reorder")
async def reorder_list_items(
    list_id: UUID,
    reorder_data: ListReorderRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reorder items in a list
    
    Updates the position of multiple list items in a single operation.
    Used for drag-and-drop reordering in the frontend.
    """
    try:
        result = await lists_service.reorder_list_items(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            item_positions=[item.dict() for item in reorder_data.item_positions]
        )
        
        return JSONResponse(
            content={
                "success": True,
                "message": "List reordered successfully",
                "data": result
            }
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error reordering list {list_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder list"
        )

@router.post("/{list_id}/duplicate", response_model=SingleListResponse)
async def duplicate_list(
    list_id: UUID,
    duplicate_data: ListDuplicateRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Duplicate a list
    
    Creates a copy of an existing list with optional item inclusion.
    Useful for creating variations of existing lists.
    """
    try:
        # Get the original list
        original_list = await lists_service.get_list_by_id(
            db=db,
            user_id=current_user.id,
            list_id=list_id,
            include_profiles=False
        )
        
        if not original_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original list not found"
            )
        
        # Create new list with same properties
        from app.models.lists import UserListCreate
        new_list_data = UserListCreate(
            name=duplicate_data.name,
            description=f"Copy of {original_list.description or original_list.name}",
            color=original_list.color,
            icon=original_list.icon,
            is_favorite=False
        )
        
        new_list = await lists_service.create_list(
            db=db,
            user_id=current_user.id,
            list_data=new_list_data
        )
        
        # Copy items if requested
        if duplicate_data.include_items and original_list.items:
            profile_ids = [item.profile.id for item in original_list.items]
            await lists_service.bulk_add_profiles_to_list(
                db=db,
                user_id=current_user.id,
                list_id=new_list.id,
                profile_ids=profile_ids,
                notes="Copied from original list"
            )
            
            # Refresh the list to get updated item count
            new_list = await lists_service.get_list_by_id(
                db=db,
                user_id=current_user.id,
                list_id=new_list.id,
                include_profiles=True
            )
        
        return SingleListResponse(
            success=True,
            data=new_list,
            message="List duplicated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error duplicating list {list_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate list"
        )

@router.post("/bulk-operations", response_model=BulkOperationResponse)
async def bulk_list_operations(
    bulk_data: BulkOperationRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Perform bulk operations on multiple lists
    
    Supports operations like delete, favorite/unfavorite on multiple lists.
    Useful for list management interfaces.
    """
    try:
        processed_count = 0
        failed_count = 0
        
        if bulk_data.operation == "delete":
            for list_id in bulk_data.list_ids:
                try:
                    success = await lists_service.delete_list(
                        db=db,
                        user_id=current_user.id,
                        list_id=list_id
                    )
                    if success:
                        processed_count += 1
                    else:
                        failed_count += 1
                except Exception:
                    failed_count += 1
        
        elif bulk_data.operation in ["favorite", "unfavorite"]:
            from app.models.lists import UserListUpdate
            is_favorite = bulk_data.operation == "favorite"
            
            for list_id in bulk_data.list_ids:
                try:
                    update_data = UserListUpdate(is_favorite=is_favorite)
                    success = await lists_service.update_list(
                        db=db,
                        user_id=current_user.id,
                        list_id=list_id,
                        list_data=update_data
                    )
                    if success:
                        processed_count += 1
                    else:
                        failed_count += 1
                except Exception:
                    failed_count += 1
        
        return BulkOperationResponse(
            success=True,
            data={
                "processed_count": processed_count,
                "failed_count": failed_count
            },
            message=f"Bulk {bulk_data.operation} operation completed"
        )
        
    except Exception as e:
        logger.error(f"Error in bulk operation {bulk_data.operation}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk operation"
        )

# =============================================================================
# DISCOVERY ENDPOINTS
# =============================================================================

@router.get("/available-profiles", response_model=AvailableProfilesResponse)
async def get_available_profiles_for_lists(
    search: Optional[str] = Query(None, description="Search by username or name"),
    not_in_list: Optional[UUID] = Query(None, description="Exclude profiles in this list"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_followers: Optional[int] = Query(None, ge=0, description="Minimum followers"),
    verified_only: bool = Query(False, description="Only verified profiles"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserInDB = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get profiles available to add to lists
    
    Returns user's unlocked profiles that can be added to lists.
    Supports filtering and search to help users find specific profiles.
    """
    try:
        result = await lists_service.get_available_profiles_for_lists(
            db=db,
            user_id=current_user.id,
            search=search,
            not_in_list=not_in_list,
            category=category,
            min_followers=min_followers,
            verified_only=verified_only,
            page=page,
            page_size=limit
        )
        
        return AvailableProfilesResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(f"Error getting available profiles for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available profiles"
        )

# =============================================================================
# ERROR HANDLERS - These should be added to the main app, not router
# =============================================================================

# Note: Exception handlers should be added to the main FastAPI app in main.py
# @app.exception_handler(ValueError)
# async def value_error_handler(request, exc):
#     return JSONResponse(
#         status_code=status.HTTP_400_BAD_REQUEST,
#         content=ErrorResponse(
#             error="validation_error",
#             message=str(exc)
#         ).dict()
#     )