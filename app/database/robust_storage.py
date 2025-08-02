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
    
    log_and_print("INFO", f">>> STARTING PROFILE STORAGE for username: {username}")
    log_and_print("INFO", f">>> Raw data size: {len(str(raw_data))} characters")
    
    # Extract and prepare profile data
    log_and_print("INFO", ">>> Extracting profile data from Decodo response...")
    profile_data = extract_profile_data(raw_data)
    profile_data['username'] = username.lower()
    
    log_and_print("INFO", f">>> Profile data extracted successfully")
    log_and_print("INFO", f">>> Profile data keys: {list(profile_data.keys())}")
    log_and_print("INFO", f">>> Critical values: username={profile_data.get('username')}, instagram_id={profile_data.get('instagram_user_id')}, followers={profile_data.get('followers_count')}")
    
    # Skip database schema check to avoid async engine inspection issues
    log_and_print("INFO", ">>> Skipping schema check due to async engine limitations")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        logger.info(f"Starting storage attempt {retry_count + 1}/{max_retries}")
        
        try:
            # Always start with fresh transaction state
            logger.info("Cleaning transaction state...")
            try:
                if db.in_transaction():
                    logger.info(" Rolling back existing transaction...")
                    await db.rollback()
                    logger.info("SUCCESS: Transaction rollback successful")
            except Exception as rollback_error:
                logger.warning(f"⚠️ Could not rollback existing transaction: {rollback_error}")
                # Force close and get fresh session
                try:
                    await db.close()
                    logger.info(" Forced database session close")
                except:
                    pass
            
            # Check if profile exists
            logger.info(f" Checking if profile '{username.lower()}' already exists...")
            result = await db.execute(
                select(Profile).where(Profile.username == username.lower())
            )
            existing_profile = result.scalar_one_or_none()
            
            if existing_profile:
                logger.info(f" Found existing profile with ID: {existing_profile.id}")
            else:
                logger.info(" No existing profile found, will create new one")
            
            if existing_profile:
                # Update existing profile
                logger.info(f" UPDATING existing profile: {username}")
                
                updated_fields = []
                failed_fields = []
                
                for key, value in profile_data.items():
                    if key != 'id':
                        if hasattr(existing_profile, key):
                            try:
                                setattr(existing_profile, key, value)
                                updated_fields.append(key)
                            except Exception as field_error:
                                failed_fields.append(f"{key}: {field_error}")
                                logger.error(f"❌ Failed to set field {key}={value}: {field_error}")
                        else:
                            failed_fields.append(f"{key}: attribute does not exist")
                            logger.warning(f"⚠️ Profile model does not have attribute: {key}")
                
                logger.info(f"SUCCESS: Successfully updated fields: {updated_fields}")
                if failed_fields:
                    logger.warning(f"⚠️ Failed to update fields: {failed_fields}")
                
                existing_profile.refresh_count = (existing_profile.refresh_count or 0) + 1
                logger.info(f"🔢 Updated refresh_count to: {existing_profile.refresh_count}")
                
                logger.info("💾 Committing profile update...")
                await db.commit()
                logger.info("SUCCESS: Profile update committed successfully")
                
                await db.refresh(existing_profile)
                logger.info(f"🎉 Profile '{username}' updated successfully!")
                return existing_profile, False
            
            else:
                # Create new profile
                logger.info(f" CREATING new profile: {username}")
                profile_data['refresh_count'] = 1
                logger.info(f"🔢 Set initial refresh_count to: 1")
                
                # Handle potential instagram_user_id conflicts
                if profile_data.get('instagram_user_id'):
                    logger.info(f" Checking for Instagram ID conflicts: {profile_data['instagram_user_id']}")
                    result = await db.execute(
                        select(Profile).where(
                            Profile.instagram_user_id == profile_data['instagram_user_id']
                        )
                    )
                    conflicting_profile = result.scalar_one_or_none()
                    
                    if conflicting_profile:
                        logger.warning(f"⚠️ Instagram ID conflict detected!")
                        logger.warning(f"   Existing profile: {conflicting_profile.username}")
                        logger.warning(f"   Instagram ID: {profile_data['instagram_user_id']}")
                        logger.warning(f"   Will update existing profile to username: {username}")
                        
                        # Update the conflicting profile's username
                        conflicting_profile.username = username.lower()
                        for key, value in profile_data.items():
                            if key != 'id' and hasattr(conflicting_profile, key):
                                setattr(conflicting_profile, key, value)
                        conflicting_profile.refresh_count = (conflicting_profile.refresh_count or 0) + 1
                        
                        logger.info("💾 Committing conflicting profile update...")
                        await db.commit()
                        await db.refresh(conflicting_profile)
                        logger.info(f"SUCCESS: Conflict resolved - updated existing profile")
                        return conflicting_profile, False
                else:
                    logger.info("ℹ️ No Instagram user ID provided, skipping conflict check")
                
                # Validate profile data before creation
                logger.info(" Validating profile data before creation...")
                logger.info(f"📋 Final profile data to insert: {list(profile_data.keys())}")
                
                # Log each field value for debugging
                for key, value in profile_data.items():
                    value_type = type(value).__name__
                    value_preview = str(value)[:100] if value is not None else "None"
                    logger.debug(f"   {key}: {value_type} = {value_preview}")
                
                # Create new profile
                log_and_print("INFO", ">>> Creating Profile object...")
                try:
                    new_profile = Profile(**profile_data)
                    log_and_print("INFO", ">>> Profile object created successfully")
                except Exception as creation_error:
                    log_and_print("ERROR", f">>> FAILED to create Profile object: {creation_error}")
                    log_and_print("ERROR", f">>> Profile data: {profile_data}")
                    raise creation_error
                
                logger.info("➕ Adding profile to database session...")
                db.add(new_profile)
                
                logger.info("💾 Committing new profile to database...")
                await db.commit()
                logger.info("SUCCESS: Profile committed successfully")
                
                logger.info(" Refreshing profile object...")
                await db.refresh(new_profile)
                
                logger.info(f"🎉 Successfully created new profile: {username} with ID: {new_profile.id}")
                return new_profile, True
                
        except IntegrityError as ie:
            retry_count += 1
            logger.error(f"🔒 INTEGRITY ERROR (attempt {retry_count}/{max_retries})")
            logger.error(f"   Error type: {type(ie).__name__}")
            logger.error(f"   Error message: {str(ie)}")
            logger.error(f"   Original error: {ie.orig if hasattr(ie, 'orig') else 'No original error'}")
            
            # Try to extract more details from the error
            error_str = str(ie).lower()
            if 'unique' in error_str:
                logger.error("   🔑 UNIQUE CONSTRAINT VIOLATION detected")
                if 'username' in error_str:
                    logger.error(f"      Username '{username}' already exists")
                if 'instagram_user_id' in error_str:
                    logger.error(f"      Instagram ID '{profile_data.get('instagram_user_id')}' already exists")
            elif 'not null' in error_str:
                logger.error("   ❌ NOT NULL CONSTRAINT VIOLATION detected")
                logger.error("      A required field is missing or null")
            elif 'foreign key' in error_str:
                logger.error("   🔗 FOREIGN KEY CONSTRAINT VIOLATION detected")
            
            if retry_count >= max_retries:
                logger.error(f"💥 FINAL FAILURE: Failed to store profile {username} after {max_retries} attempts")
                logger.error(f"   Last integrity error: {ie}")
                raise ValueError(f"Database constraint violation for {username}: {ie}")
            
            # Rollback and retry
            logger.info(f" Rolling back and retrying (attempt {retry_count}/{max_retries})...")
            try:
                await db.rollback()
                logger.info("SUCCESS: Rollback successful")
            except Exception as rollback_error:
                logger.error(f"❌ Rollback failed: {rollback_error}")
            
            continue
            
        except SQLAlchemyError as se:
            retry_count += 1
            logger.error(f"🗃️ SQLALCHEMY ERROR (attempt {retry_count}/{max_retries})")
            logger.error(f"   Error type: {type(se).__name__}")
            logger.error(f"   Error message: {str(se)}")
            logger.error(f"   Error details: {se.args if hasattr(se, 'args') else 'No args'}")
            
            # Log the full traceback for SQLAlchemy errors
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            
            if retry_count >= max_retries:
                logger.error(f"💥 FINAL FAILURE: SQLAlchemy error for {username} after {max_retries} attempts")
                raise ValueError(f"Database error for {username}: {se}")
            
            # Rollback and retry
            logger.info(f" Rolling back and retrying (attempt {retry_count}/{max_retries})...")
            try:
                await db.rollback()
                logger.info("SUCCESS: Rollback successful")
            except Exception as rollback_error:
                logger.error(f"❌ Rollback failed: {rollback_error}")
            
            continue
            
        except Exception as e:
            logger.error(f"💥 UNEXPECTED ERROR storing profile {username}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")
            logger.error(f"   Error args: {e.args if hasattr(e, 'args') else 'No args'}")
            logger.error(f"   Full traceback: {traceback.format_exc()}")
            
            try:
                await db.rollback()
                logger.info("SUCCESS: Emergency rollback successful")
            except Exception as rollback_error:
                logger.error(f"❌ Emergency rollback failed: {rollback_error}")
            
            raise ValueError(f"Storage failed for {username}: {e}")
    
    logger.error(f"💥 COMPLETE FAILURE: Failed to store profile {username} after {max_retries} attempts")
    raise ValueError(f"Failed to store profile {username} after {max_retries} attempts")


def extract_profile_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract profile data from Decodo response - WITH COMPREHENSIVE LOGGING"""
    logger.info(" STARTING DATA EXTRACTION from Decodo response")
    
    try:
        # Get user data from Decodo response
        logger.info("📊 Parsing Decodo response structure...")
        user_data = {}
        
        if raw_data:
            logger.info(f"   Raw data type: {type(raw_data)}")
            logger.info(f"   Raw data keys: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'Not a dict'}")
            
            if 'results' in raw_data and len(raw_data['results']) > 0:
                result = raw_data['results'][0]
                logger.info(f"   Results[0] keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                
                if 'content' in result and 'data' in result['content']:
                    user_data = result['content']['data'].get('user', {})
                    logger.info(f"   Successfully extracted user data with {len(user_data)} fields")
                else:
                    logger.warning("   Missing content.data in result")
            else:
                logger.warning("   Missing or empty results array")
        else:
            logger.error("   No raw_data provided")
        
        if user_data:
            logger.info(f"📋 Available user data fields: {list(user_data.keys())[:15]}")
            if len(user_data.keys()) > 15:
                logger.info(f"   ... and {len(user_data.keys()) - 15} more fields")
        else:
            logger.warning("⚠️ No user data extracted from Decodo response")
        
        # Map to profile fields with multiple field name attempts
        logger.info("🗂️ Mapping Decodo fields to database fields...")
        
        instagram_id = (
            user_data.get('id') or 
            user_data.get('pk') or 
            user_data.get('instagram_user_id') or 
            ''
        )
        logger.info(f"   Instagram ID: {instagram_id} (from fields: id, pk, instagram_user_id)")
        
        followers_count = (
            user_data.get('follower_count') or 
            user_data.get('followers_count') or
            user_data.get('edge_followed_by', {}).get('count', 0)
        )
        logger.info(f"   Followers: {followers_count} (from fields: follower_count, followers_count, edge_followed_by.count)")
        
        following_count = (
            user_data.get('following_count') or
            user_data.get('edge_follow', {}).get('count', 0)
        )
        logger.info(f"   Following: {following_count} (from fields: following_count, edge_follow.count)")
        
        posts_count = (
            user_data.get('media_count') or
            user_data.get('posts_count') or
            user_data.get('edge_owner_to_timeline_media', {}).get('count', 0)
        )
        logger.info(f"   Posts: {posts_count} (from fields: media_count, posts_count, edge_owner_to_timeline_media.count)")
        
        profile_data = {
            'instagram_user_id': str(instagram_id) if instagram_id else None,
            'full_name': user_data.get('full_name', ''),
            'biography': user_data.get('biography', ''),
            'external_url': user_data.get('external_url'),
            'profile_pic_url': user_data.get('profile_pic_url'),
            'profile_pic_url_hd': user_data.get('profile_pic_url_hd'),
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
        
        logger.info(f"SUCCESS: Initial profile data mapping complete")
        logger.info(f"   Mapped fields: {list(profile_data.keys())}")
        
        # Clean up None values and ensure proper types
        logger.info(" Cleaning and validating field types...")
        cleaned_data = {}
        
        for key, value in profile_data.items():
            if value is not None:
                if key.endswith('_count') and isinstance(value, str):
                    try:
                        cleaned_value = int(value)
                        cleaned_data[key] = cleaned_value
                        logger.debug(f"   Converted {key}: '{value}' -> {cleaned_value}")
                    except (ValueError, TypeError) as convert_error:
                        cleaned_data[key] = 0
                        logger.warning(f"   Failed to convert {key}: '{value}' -> 0 (error: {convert_error})")
                else:
                    cleaned_data[key] = value
            elif key == 'raw_data':
                cleaned_data[key] = raw_data
            else:
                logger.debug(f"   Skipping None value for: {key}")
        
        logger.info(f"🎯 FINAL extracted data summary:")
        logger.info(f"   Instagram ID: {cleaned_data.get('instagram_user_id', 'N/A')}")
        logger.info(f"   Full name: {cleaned_data.get('full_name', 'N/A')}")
        logger.info(f"   Biography length: {len(cleaned_data.get('biography', ''))}")
        logger.info(f"   Followers: {cleaned_data.get('followers_count', 'N/A')}")
        logger.info(f"   Following: {cleaned_data.get('following_count', 'N/A')}")
        logger.info(f"   Posts: {cleaned_data.get('posts_count', 'N/A')}")
        logger.info(f"   Verified: {cleaned_data.get('is_verified', 'N/A')}")
        logger.info(f"   Private: {cleaned_data.get('is_private', 'N/A')}")
        logger.info(f"   Business: {cleaned_data.get('is_business_account', 'N/A')}")
        logger.info(f"   Raw data size: {len(str(cleaned_data.get('raw_data', {})))} chars")
        
        return cleaned_data
        
    except Exception as e:
        logger.error(f"💥 ERROR extracting profile data: {e}")
        logger.error(f"   Exception type: {type(e).__name__}")
        logger.error(f"   Exception traceback: {traceback.format_exc()}")
        
        # Return minimal fallback data
        fallback_data = {
            'raw_data': raw_data,
            'followers_count': 0,
            'following_count': 0,
            'posts_count': 0,
            'is_verified': False,
            'is_private': False,
            'is_business_account': False
        }
        
        logger.warning(f" Returning fallback data: {fallback_data}")
        return fallback_data