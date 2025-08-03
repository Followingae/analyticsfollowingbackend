"""
Robust database storage functions that handle transaction errors
WITH COMPREHENSIVE LOGGING FOR DEBUGGING
"""
import logging
import traceback
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.database.unified_models import Profile

logger = logging.getLogger(__name__)

def proxy_instagram_url(url: str) -> str:
    """Convert Instagram CDN URL to proxied URL to eliminate CORS issues"""
    if not url:
        return ''
    
    # Only proxy Instagram CDN URLs
    if url.startswith(('https://scontent-', 'https://instagram.', 'https://scontent.cdninstagram.com')):
        # Return proxied URL that frontend can use directly
        return f"/api/proxy-image?url={url}"
    return url

# Set up detailed logging with immediate console output
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Also print directly to ensure visibility
def log_and_print(level, message):
    """Log and also print to console for immediate visibility - Windows compatible"""
    # Remove problematic Unicode characters for Windows console
    clean_message = message.encode('ascii', 'ignore').decode('ascii')
    print(f"[STORAGE {level}] {clean_message}")
    
    # Also send clean message to logger to avoid Unicode issues
    clean_log_message = message.encode('ascii', 'ignore').decode('ascii')
    if level == "INFO":
        logger.info(clean_log_message)
    elif level == "DEBUG":
        logger.debug(clean_log_message)
    elif level == "ERROR":
        logger.error(clean_log_message)
    elif level == "WARNING":
        logger.warning(clean_log_message)

async def store_profile_robust(
    db: AsyncSession, 
    username: str, 
    raw_data: Dict[str, Any]
) -> Tuple[Profile, bool]:
    """
    Store profile with robust transaction handling - WITH COMPREHENSIVE LOGGING
    Returns (profile, is_new)
    """
    
    logger.info(f"Starting profile storage for: {username}")
    
    # Extract and prepare profile data
    profile_data = extract_profile_data(raw_data)
    profile_data['username'] = username.lower()
    
    logger.info(f"Profile data extracted - followers: {profile_data.get('followers_count')}, posts: {profile_data.get('posts_count')}")
    
    # Skip database schema check to avoid async engine inspection issues
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Always start with fresh transaction state
            try:
                if db.in_transaction():
                    await db.rollback()
            except Exception as rollback_error:
                logger.warning(f"Could not rollback existing transaction: {rollback_error}")
                # Force close and get fresh session
                try:
                    await db.close()
                except:
                    pass
            
            # Check if profile exists
            result = await db.execute(
                select(Profile).where(Profile.username == username.lower())
            )
            existing_profile = result.scalar_one_or_none()
            
            if existing_profile:
                # Update existing profile
                failed_fields = []
                
                for key, value in profile_data.items():
                    if key != 'id':
                        if hasattr(existing_profile, key):
                            try:
                                setattr(existing_profile, key, value)
                            except Exception as field_error:
                                failed_fields.append(f"{key}: {field_error}")
                                logger.error(f"Failed to set field {key}: {field_error}")
                        else:
                            failed_fields.append(f"{key}: attribute does not exist")
                
                if failed_fields:
                    logger.warning(f"Failed to update fields: {failed_fields}")
                
                existing_profile.refresh_count = (existing_profile.refresh_count or 0) + 1
                
                await db.commit()
                await db.refresh(existing_profile)
                logger.info(f"Profile '{username}' updated successfully")
                return existing_profile, False
            
            else:
                # Create new profile
                profile_data['refresh_count'] = 1
                
                # Handle potential instagram_user_id conflicts
                if profile_data.get('instagram_user_id'):
                    result = await db.execute(
                        select(Profile).where(
                            Profile.instagram_user_id == profile_data['instagram_user_id']
                        )
                    )
                    conflicting_profile = result.scalar_one_or_none()
                    
                    if conflicting_profile:
                        logger.warning(f"Instagram ID conflict - updating existing profile: {conflicting_profile.username}")
                        
                        # Update the conflicting profile's username
                        conflicting_profile.username = username.lower()
                        for key, value in profile_data.items():
                            if key != 'id' and hasattr(conflicting_profile, key):
                                setattr(conflicting_profile, key, value)
                        conflicting_profile.refresh_count = (conflicting_profile.refresh_count or 0) + 1
                        
                        await db.commit()
                        await db.refresh(conflicting_profile)
                        logger.info(f"Conflict resolved - updated existing profile")
                        return conflicting_profile, False
                
                # Create new profile
                try:
                    new_profile = Profile(**profile_data)
                except Exception as creation_error:
                    logger.error(f"Failed to create Profile object: {creation_error}")
                    logger.error(f"Profile data: {list(profile_data.keys())}")
                    raise creation_error
                
                db.add(new_profile)
                await db.commit()
                await db.refresh(new_profile)
                
                logger.info(f"Successfully created new profile: {username}")
                return new_profile, True
                
        except IntegrityError as ie:
            retry_count += 1
            logger.error(f"INTEGRITY ERROR (attempt {retry_count}/{max_retries}): {str(ie)}")
            
            if retry_count >= max_retries:
                logger.error(f"Failed to store profile {username} after {max_retries} attempts")
                raise ValueError(f"Database constraint violation for {username}: {ie}")
            
            # Rollback and retry
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            
            continue
            
        except SQLAlchemyError as se:
            retry_count += 1
            logger.error(f"SQLAlchemy error (attempt {retry_count}/{max_retries}): {str(se)}")
            
            if retry_count >= max_retries:
                logger.error(f"SQLAlchemy error for {username} after {max_retries} attempts")
                raise ValueError(f"Database error for {username}: {se}")
            
            # Rollback and retry
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            
            continue
            
        except Exception as e:
            logger.error(f"Unexpected error storing profile {username}: {str(e)}")
            
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(f"Emergency rollback failed: {rollback_error}")
            
            raise ValueError(f"Storage failed for {username}: {e}")
    
    logger.error(f"Failed to store profile {username} after {max_retries} attempts")
    raise ValueError(f"Failed to store profile {username} after {max_retries} attempts")


def extract_profile_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract profile data from Decodo response"""
    try:
        # Get user data from Decodo response
        user_data = {}
        
        if raw_data and 'results' in raw_data and len(raw_data['results']) > 0:
            result = raw_data['results'][0]
            if 'content' in result and 'data' in result['content']:
                user_data = result['content']['data'].get('user', {})
        
        if not user_data:
            logger.warning("No user data extracted from Decodo response")
        
        # Map to profile fields with multiple field name attempts
        instagram_id = (
            user_data.get('id') or 
            user_data.get('pk') or 
            user_data.get('instagram_user_id') or 
            ''
        )
        
        followers_count = (
            user_data.get('follower_count') or 
            user_data.get('followers_count') or
            user_data.get('edge_followed_by', {}).get('count', 0)
        )
        
        following_count = (
            user_data.get('following_count') or
            user_data.get('edge_follow', {}).get('count', 0)
        )
        
        posts_count = (
            user_data.get('media_count') or
            user_data.get('posts_count') or
            user_data.get('edge_owner_to_timeline_media', {}).get('count', 0)
        )
        
        profile_data = {
            'instagram_user_id': str(instagram_id) if instagram_id else None,
            'full_name': user_data.get('full_name', ''),
            'biography': user_data.get('biography', ''),
            'external_url': user_data.get('external_url'),  # Don't proxy external URLs as they're not Instagram CDN
            'profile_pic_url': proxy_instagram_url(user_data.get('profile_pic_url', '')),
            'profile_pic_url_hd': proxy_instagram_url(user_data.get('profile_pic_url_hd', '')),
            'followers_count': followers_count,
            'following_count': following_count,
            'posts_count': posts_count,
            'is_verified': user_data.get('is_verified', False),
            'is_private': user_data.get('is_private', False),
            'is_business_account': (
                user_data.get('is_business') or 
                user_data.get('is_business_account', False)
            ),
            'category': user_data.get('category'),
            'engagement_rate': None,  # Will be calculated later
            'influence_score': None,  # Will be calculated later
            'data_quality_score': 1.0,
            'raw_data': raw_data  # Store complete raw response
        }
        
        # Clean up None values and ensure proper types
        cleaned_data = {}
        
        for key, value in profile_data.items():
            if value is not None:
                if key.endswith('_count') and isinstance(value, str):
                    try:
                        cleaned_data[key] = int(value)
                    except (ValueError, TypeError):
                        cleaned_data[key] = 0
                        logger.warning(f"Failed to convert {key}: '{value}' -> 0")
                else:
                    cleaned_data[key] = value
            elif key == 'raw_data':
                cleaned_data[key] = raw_data
        
        logger.info(f"Extracted data: followers={cleaned_data.get('followers_count')}, posts={cleaned_data.get('posts_count')}, verified={cleaned_data.get('is_verified')}")
        
        return cleaned_data
        
    except Exception as e:
        logger.error(f"Error extracting profile data: {e}")
        
        # Return minimal fallback data
        return {
            'raw_data': raw_data,
            'followers_count': 0,
            'following_count': 0,
            'posts_count': 0,
            'is_verified': False,
            'is_private': False,
            'is_business_account': False
        }