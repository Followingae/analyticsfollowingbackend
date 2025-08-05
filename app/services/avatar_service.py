"""
Avatar Service for handling user avatar uploads and management
Integrates with Supabase Storage and manages avatar metadata
"""

import uuid
import io
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from fastapi import UploadFile, HTTPException
from supabase import Client
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.core.config import settings
from app.database.unified_models import UserAvatar

logger = logging.getLogger(__name__)

class AvatarService:
    """Service for managing user avatar uploads and storage"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.bucket_name = "avatars"
        self.max_file_size = 5 * 1024 * 1024  # 5MB
        self.allowed_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
        self.image_size = (400, 400)  # Standard avatar size
        self.quality = 85  # JPEG quality
        
        # Supabase storage base URL
        self.storage_base_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{self.bucket_name}/"
    
    async def upload_avatar(
        self, 
        user_id: str, 
        file: UploadFile,
        db: AsyncSession = None
    ) -> Tuple[str, str]:
        """
        Upload and process user avatar
        
        Args:
            user_id: UUID of the user
            file: Uploaded file
            db: Database session (optional)
            
        Returns:
            Tuple of (file_path, public_url)
        """
        try:
            logger.info(f"Starting avatar upload for user {user_id}")
            
            # Validate file
            await self._validate_file(file)
            
            # Process image
            processed_image, final_size = await self._process_image(file)
            
            # Generate unique file path
            file_extension = self._get_file_extension(file.filename or "avatar.jpg")
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            file_path = f"{user_id}/avatar_{timestamp}_{uuid.uuid4().hex[:8]}.{file_extension}"
            
            # Upload to Supabase Storage
            logger.info(f"Uploading to storage path: {file_path}")
            result = self.supabase.storage.from_(self.bucket_name).upload(
                file_path, 
                processed_image,
                file_options={
                    "content-type": f"image/{file_extension}",
                    "cache-control": "3600",
                    "upsert": False  # Don't overwrite existing files
                }
            )
            
            # Check for upload errors
            if hasattr(result, 'error') and result.error:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Storage upload failed: {result.error}"
                )
            
            # Generate public URL
            public_url = f"{self.storage_base_url}{file_path}"
            
            # Update database records
            await self._update_user_avatar_records(
                user_id=user_id,
                file_path=file_path,
                file_size=len(processed_image),
                mime_type=f"image/{file_extension}",
                original_filename=file.filename,
                processed_size=f"{final_size[0]}x{final_size[1]}",
                public_url=public_url,
                db=db
            )
            
            logger.info(f"Avatar upload completed successfully for user {user_id}")
            return file_path, public_url
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Avatar upload failed for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Avatar upload failed: {str(e)}")
    
    async def get_avatar_url(
        self, 
        user_id: str, 
        fallback_instagram_url: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """
        Get user's avatar URL with fallback to Instagram profile picture
        
        Args:
            user_id: UUID of the user
            fallback_instagram_url: Instagram profile picture URL as fallback
            db: Database session (optional)
            
        Returns:
            Dict with avatar_url, has_custom_avatar, and metadata
        """
        try:
            # Query for active avatar using Supabase client (for RLS)
            result = self.supabase.table('user_avatars').select(
                'file_path, uploaded_at, file_size, processed_size'
            ).eq('user_id', user_id).eq('is_active', True).order(
                'uploaded_at', desc=True
            ).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                avatar_data = result.data[0]
                avatar_url = f"{self.storage_base_url}{avatar_data['file_path']}"
                
                return {
                    "avatar_url": avatar_url,
                    "has_custom_avatar": True,
                    "uploaded_at": avatar_data.get('uploaded_at'),
                    "file_size": avatar_data.get('file_size'),
                    "processed_size": avatar_data.get('processed_size'),
                    "fallback_url": fallback_instagram_url
                }
            
            # No custom avatar found, return Instagram fallback
            return {
                "avatar_url": fallback_instagram_url,
                "has_custom_avatar": False,
                "uploaded_at": None,
                "file_size": None,
                "processed_size": None,
                "fallback_url": fallback_instagram_url
            }
            
        except Exception as e:
            logger.warning(f"Error fetching avatar for user {user_id}: {str(e)}")
            # Return fallback on any error
            return {
                "avatar_url": fallback_instagram_url,
                "has_custom_avatar": False,
                "uploaded_at": None,
                "file_size": None,
                "processed_size": None,
                "fallback_url": fallback_instagram_url,
                "error": str(e)
            }
    
    async def delete_avatar(self, user_id: str, db: AsyncSession = None) -> bool:
        """
        Delete user's current avatar
        
        Args:
            user_id: UUID of the user
            db: Database session (optional)
            
        Returns:
            True if avatar was deleted, False if no avatar existed
        """
        try:
            logger.info(f"Deleting avatar for user {user_id}")
            
            # Get current active avatar
            result = self.supabase.table('user_avatars').select(
                'file_path'
            ).eq('user_id', user_id).eq('is_active', True).single().execute()
            
            if not result.data:
                logger.info(f"No active avatar found for user {user_id}")
                return False
            
            file_path = result.data['file_path']
            
            # Delete from Supabase storage
            logger.info(f"Deleting file from storage: {file_path}")
            storage_result = self.supabase.storage.from_(self.bucket_name).remove([file_path])
            
            if hasattr(storage_result, 'error') and storage_result.error:
                logger.warning(f"Storage deletion warning: {storage_result.error}")
                # Continue with database update even if storage deletion fails
            
            # Deactivate avatar record in database
            update_result = self.supabase.table('user_avatars').update({
                'is_active': False,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('user_id', user_id).eq('file_path', file_path).execute()
            
            # Update users table to remove avatar_url
            self.supabase.table('users').update({
                'avatar_url': None
            }).eq('id', user_id).execute()
            
            logger.info(f"Avatar deleted successfully for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Avatar deletion failed for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Avatar deletion failed: {str(e)}")
    
    async def cleanup_old_avatars(self, user_id: str, keep_count: int = 1) -> int:
        """
        Clean up old inactive avatar files for a user
        
        Args:
            user_id: UUID of the user
            keep_count: Number of recent avatars to keep (default: 1)
            
        Returns:
            Number of avatars cleaned up
        """
        try:
            # Get old inactive avatars
            result = self.supabase.table('user_avatars').select(
                'file_path'
            ).eq('user_id', user_id).eq('is_active', False).order(
                'uploaded_at', desc=True
            ).offset(keep_count).execute()
            
            if not result.data:
                return 0
            
            # Delete files from storage
            file_paths = [avatar['file_path'] for avatar in result.data]
            if file_paths:
                self.supabase.storage.from_(self.bucket_name).remove(file_paths)
                
                # Delete records from database
                for file_path in file_paths:
                    self.supabase.table('user_avatars').delete().eq(
                        'user_id', user_id
                    ).eq('file_path', file_path).execute()
            
            logger.info(f"Cleaned up {len(file_paths)} old avatars for user {user_id}")
            return len(file_paths)
            
        except Exception as e:
            logger.error(f"Avatar cleanup failed for user {user_id}: {str(e)}")
            return 0
    
    # Private helper methods
    
    async def _validate_file(self, file: UploadFile):
        """Validate uploaded file"""
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large (max {self.max_file_size // (1024*1024)}MB)"
            )
        
        if file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(self.allowed_types)}"
            )
    
    async def _process_image(self, file: UploadFile) -> Tuple[bytes, Tuple[int, int]]:
        """Process and optimize image"""
        # Read file content
        contents = await file.read()
        
        try:
            # Open image
            image = Image.open(io.BytesIO(contents))
            
            # Fix orientation based on EXIF data
            image = ImageOps.exif_transpose(image)
            
            # Convert to RGB if necessary (handles PNG with transparency)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize to square while maintaining aspect ratio
            image.thumbnail(self.image_size, Image.Resampling.LANCZOS)
            
            # Create square image with white background
            square_image = Image.new('RGB', self.image_size, (255, 255, 255))
            
            # Center the image
            offset = (
                (self.image_size[0] - image.size[0]) // 2,
                (self.image_size[1] - image.size[1]) // 2
            )
            square_image.paste(image, offset)
            
            # Save to bytes with optimization
            output = io.BytesIO()
            square_image.save(
                output, 
                format='JPEG', 
                quality=self.quality, 
                optimize=True,
                progressive=True
            )
            
            return output.getvalue(), square_image.size
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        extension = filename.split('.')[-1].lower() if '.' in filename else 'jpg'
        # Normalize extensions
        if extension in ['jpeg', 'jpg']:
            return 'jpg'
        elif extension in ['png']:
            return 'jpg'  # Convert PNG to JPG for consistency
        elif extension in ['webp']:
            return 'jpg'  # Convert WebP to JPG for compatibility
        else:
            return 'jpg'  # Default to JPG
    
    async def _update_user_avatar_records(
        self,
        user_id: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        original_filename: Optional[str],
        processed_size: str,
        public_url: str,
        db: Optional[AsyncSession] = None
    ):
        """Update database records for new avatar"""
        try:
            # Deactivate all existing avatars for this user
            self.supabase.table('user_avatars').update({
                'is_active': False,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('user_id', user_id).execute()
            
            # Insert new avatar record
            avatar_data = {
                'user_id': user_id,
                'file_path': file_path,
                'file_size': file_size,
                'mime_type': mime_type,
                'original_filename': original_filename,
                'processed_size': processed_size,
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                'is_active': True
            }
            
            insert_result = self.supabase.table('user_avatars').insert(avatar_data).execute()
            
            if hasattr(insert_result, 'error') and insert_result.error:
                raise Exception(f"Database insert failed: {insert_result.error}")
            
            # Update users table with new avatar URL
            self.supabase.table('users').update({
                'avatar_url': public_url
            }).eq('id', user_id).execute()
            
            logger.info(f"Database records updated for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to update database records: {str(e)}")
            raise Exception(f"Database update failed: {str(e)}")


# Singleton instance
avatar_service = None

def get_avatar_service() -> AvatarService:
    """Get avatar service instance"""
    global avatar_service
    if avatar_service is None:
        from supabase import create_client
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        avatar_service = AvatarService(supabase)
    return avatar_service