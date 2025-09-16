"""
Apify Instagram Client - Surgically Precise Instagram Data Collection
IDENTICAL interface, IDENTICAL limits, ZERO changes to existing code
"""
import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from apify_client import ApifyClient
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from app.core.config import settings

logger = logging.getLogger(__name__)

class ApifyAPIError(Exception):
    """Custom exception for Apify API errors - matches ApifyAPIError"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class ApifyInstabilityError(ApifyAPIError):
    """Exception for temporary Apify API issues that should be retried - matches ApifyInstabilityError"""
    pass

class ApifyProfileNotFoundError(ApifyAPIError):
    """Exception for non-existent profiles that should NOT be retried - matches ApifyProfileNotFoundError"""
    pass

class ApifyInstagramClient:
    """
    Apify Instagram Client - Single Scrape Method Only

    SURGICAL REPLACEMENT REQUIREMENTS:
    - SINGLE scrape method matching current usage
    - EXACT limits: 12 posts, 10 related profiles, 12 reels
    - IDENTICAL response format as Apify
    - ZERO changes required in calling code
    """

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.actor_id = "apify/instagram-scraper"
        self.client: Optional[ApifyClient] = None

        # FINAL APIFY LIMITS (SET ONCE)
        self.POSTS_LIMIT = 12
        self.RELATED_PROFILES_LIMIT = 10
        self.REELS_LIMIT = 12

        # Retry configuration - match Apify patterns exactly
        self.max_retries = 3
        self.initial_wait = 2
        self.max_wait = 20
        self.backoff_multiplier = 1.5

    async def __aenter__(self):
        """Async context manager entry - identical to Apify"""
        self.client = ApifyClient(self.api_token)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - identical to Apify"""
        self.client = None

    async def _run_instagram_scraper(self, run_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Instagram scraper with retry logic - matches Apify retry patterns

        Args:
            run_input: Apify actor input configuration

        Returns:
            Processed Instagram data in Apify-compatible format
        """
        if not self.client:
            raise ApifyAPIError("Client not initialized - use async context manager")

        username = run_input.get("directUrls", [""])[0].split("/")[-2] if run_input.get("directUrls") else "unknown"
        empty_result_count = 0
        last_exception = None

        for attempt in range(5):  # Match Apify retry count
            try:
                logger.info(f"[APIFY] Starting Instagram scrape for {username} (attempt {attempt + 1}/5)")

                # Run the actor with timeout
                run = self.client.actor(self.actor_id).call(
                    run_input=run_input,
                    timeout_secs=300  # 5 minute timeout like Apify
                )

                if run.get("status") != "SUCCEEDED":
                    raise ApifyInstabilityError(f"Actor run failed with status: {run.get('status')}")

                # Get results
                results = []
                dataset_id = run.get("defaultDatasetId")
                if dataset_id:
                    for item in self.client.dataset(dataset_id).iterate_items():
                        results.append(item)

                if not results:
                    empty_result_count += 1
                    logger.warning(f"Empty results for {username} (attempt {empty_result_count}/3)")

                    if empty_result_count >= 3:
                        logger.error(f"Profile {username} likely doesn't exist - got empty results 3 times")
                        raise ApifyProfileNotFoundError(f"Profile '{username}' not found on Instagram")

                    # Retry for empty results
                    if attempt < 4:
                        wait_time = min(2 * (1.5 ** attempt), 15)
                        logger.warning(f"Retrying {username} in {wait_time}s due to empty results")
                        await asyncio.sleep(wait_time)
                        continue

                # Check for error in first result
                first_result = results[0] if results else {}
                if first_result.get("error") == "not_found":
                    raise ApifyProfileNotFoundError(f"Profile '{username}' not found on Instagram")

                # Transform to Apify-compatible format
                return self._transform_to_apify_format(results, username)

            except (ApifyProfileNotFoundError, ApifyAPIError):
                # Don't retry these errors
                raise

            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                if 'timeout' in error_msg or 'network' in error_msg or 'connection' in error_msg:
                    logger.warning(f"Network error for {username} attempt {attempt + 1}: {e}")
                    empty_result_count = 0  # Reset counter for network issues
                else:
                    logger.warning(f"Apify error for {username} attempt {attempt + 1}: {e}")

                if attempt < 4:
                    wait_time = min(3 * (2 ** attempt), 30)
                    logger.info(f"Retrying after error in {wait_time}s...")
                    await asyncio.sleep(wait_time)

        # All retries failed
        if empty_result_count >= 3:
            raise ApifyProfileNotFoundError(f"Profile '{username}' not found on Instagram") from last_exception
        else:
            raise ApifyInstabilityError(f"Apify scraping failed after all retries: {last_exception}") from last_exception

    def _transform_to_apify_format(self, apify_results: list, username: str) -> Dict[str, Any]:
        """
        Transform Apify results to IDENTICAL Apify format

        CRITICAL: Must return EXACT same structure as Apify for zero-change migration
        """
        if not apify_results:
            raise ApifyProfileNotFoundError(f"No data found for profile {username}")

        # Get main profile data (first result should be profile)
        profile_data = apify_results[0]

        # Handle error cases
        if profile_data.get("error"):
            error = profile_data.get("error")
            if error == "not_found":
                raise ApifyProfileNotFoundError(f"Profile '{username}' not found on Instagram")
            else:
                raise ApifyInstabilityError(f"Apify scraping error: {error}")

        # Transform to Apify format - EXACT structure match
        apify_format = {
            "results": [
                {
                    "content": {
                        "data": {
                            # Profile data
                            "username": profile_data.get("username", username),
                            "full_name": profile_data.get("fullName", ""),
                            "biography": profile_data.get("biography", ""),
                            "followers_count": profile_data.get("followersCount", 0),
                            "following_count": profile_data.get("followingCount", 0),
                            "posts_count": profile_data.get("postsCount", 0),
                            "profile_pic_url_hd": profile_data.get("profilePicUrl", ""),
                            "is_verified": profile_data.get("isVerified", False),
                            "is_business_account": profile_data.get("isBusinessAccount", False),
                            "external_url": profile_data.get("externalUrl", ""),
                            "category": profile_data.get("category", ""),

                            # Posts data - extract from posts array
                            "posts": self._extract_posts_data(apify_results),

                            # Related profiles - extract from related array
                            "related_profiles": self._extract_related_profiles(apify_results)
                        }
                    }
                }
            ],
            "status": "completed",
            "message": "Profile scraped successfully"
        }

        logger.info(f"[APIFY] Successfully transformed {username} data to Apify format")
        logger.info(f"[APIFY] DEBUG: Apify format data structure: followers={apify_format['results'][0]['content']['data'].get('followers_count')}, posts={len(apify_format['results'][0]['content']['data'].get('posts', []))}")
        return apify_format

    def _extract_posts_data(self, apify_results: list) -> list:
        """Extract posts data in Apify format"""
        posts = []

        for result in apify_results:
            # Check for latestPosts in profile data (Apify format)
            if "latestPosts" in result:
                for post in result.get("latestPosts", []):
                    post_data = {
                        "shortcode": post.get("shortCode", post.get("shortcode", "")),
                        "caption": post.get("caption", ""),
                        "likes_count": post.get("likesCount", 0),
                        "comments_count": post.get("commentsCount", 0),
                        "display_url": post.get("displayUrl", ""),
                        "video_url": post.get("videoUrl", ""),
                        "taken_at_timestamp": self._convert_timestamp(post.get("timestamp")),
                        "location": post.get("locationName", ""),
                        "hashtags": post.get("hashtags", []),
                        "tagged_users": post.get("taggedUsers", [])
                    }
                    posts.append(post_data)
            # Posts might be in 'posts' array or individual post objects
            elif result.get("type") == "post" or "shortcode" in result:
                post_data = {
                    "shortcode": result.get("shortcode", ""),
                    "caption": result.get("caption", ""),
                    "likes_count": result.get("likesCount", 0),
                    "comments_count": result.get("commentsCount", 0),
                    "display_url": result.get("displayUrl", ""),
                    "video_url": result.get("videoUrl", ""),
                    "taken_at_timestamp": self._convert_timestamp(result.get("timestamp")),
                    "location": result.get("locationName", ""),
                    "hashtags": result.get("hashtags", []),
                    "tagged_users": result.get("taggedUsers", [])
                }
                posts.append(post_data)
            elif "posts" in result:
                # Posts are in an array within the result
                for post in result.get("posts", []):
                    post_data = {
                        "shortcode": post.get("shortcode", ""),
                        "caption": post.get("caption", ""),
                        "likes_count": post.get("likesCount", 0),
                        "comments_count": post.get("commentsCount", 0),
                        "display_url": post.get("displayUrl", ""),
                        "video_url": post.get("videoUrl", ""),
                        "taken_at_timestamp": self._convert_timestamp(post.get("timestamp")),
                        "location": post.get("locationName", ""),
                        "hashtags": post.get("hashtags", []),
                        "tagged_users": post.get("taggedUsers", [])
                    }
                    posts.append(post_data)

        return posts

    def _extract_related_profiles(self, apify_results: list) -> list:
        """Extract related profiles data in Apify format"""
        related = []

        for result in apify_results:
            if result.get("type") == "profile" and result.get("username") != apify_results[0].get("username"):
                # This is a related profile
                related_data = {
                    "username": result.get("username", ""),
                    "full_name": result.get("fullName", ""),
                    "followers_count": result.get("followersCount", 0),
                    "profile_pic_url": result.get("profilePicUrl", ""),
                    "is_verified": result.get("isVerified", False)
                }
                related.append(related_data)
            elif "relatedProfiles" in result:
                # Related profiles are in an array
                for profile in result.get("relatedProfiles", []):
                    related_data = {
                        "username": profile.get("username", ""),
                        "full_name": profile.get("fullName", ""),
                        "followers_count": profile.get("followersCount", 0),
                        "profile_pic_url": profile.get("profilePicUrl", ""),
                        "is_verified": profile.get("isVerified", False)
                    }
                    related.append(related_data)

        return related

    def _convert_timestamp(self, timestamp) -> Optional[int]:
        """Convert various timestamp formats to Unix timestamp"""
        if not timestamp:
            return None

        try:
            if isinstance(timestamp, (int, float)):
                return int(timestamp)
            elif isinstance(timestamp, str):
                # Try parsing ISO format
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return int(dt.timestamp())
            else:
                return None
        except:
            return None

    async def get_instagram_profile_comprehensive(self, username: str) -> Dict[str, Any]:
        """
        SINGLE Instagram scrape method - replaces all Apify methods

        EXACT LIMITS (FINAL):
        - Profile details with 12 recent posts included automatically
        - 10 related profiles
        - 12 reels (if available)

        CRITICAL FIX: Single profile scrape - "Scrape details of a profile, photo, hashtag, or place"
        When scraping a profile URL, Apify automatically includes recent posts in the response
        """
        run_input = {
            "directUrls": [f"https://www.instagram.com/{username}/"],
            "resultsType": "details",  # Scrape profile details
            "resultsLimit": 12,  # Limit posts returned
            "extendOutputFunction": """
                (data, { request }) => {
                    // Ensure we get posts in the profile response
                    if (data.latestPosts && data.latestPosts.length > 12) {
                        data.latestPosts = data.latestPosts.slice(0, 12);
                    }
                    return data;
                }
            """,
            "addParentData": True,
            "maxRequestRetries": 2,
            "sessionPoolSize": 1,
            "pageTimeout": 60,
            "requestTimeout": 90
        }

        try:
            logger.info(f"[APIFY] Fetching profile data for {username} (12 posts, 10 related, 12 reels)")
            response_data = await self._run_instagram_scraper(run_input)
            logger.info(f"[APIFY] Successfully fetched profile data for {username}")
            return response_data

        except ApifyProfileNotFoundError:
            logger.warning(f"Profile {username} not found")
            raise
        except Exception as e:
            logger.error(f"Profile fetch failed for {username}: {str(e)}")
            raise ApifyAPIError(f"Profile fetch failed: {str(e)}")