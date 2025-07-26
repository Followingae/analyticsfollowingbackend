import asyncio
import json
import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import quote
import time
import random

from app.models.instagram import (
    InstagramProfile, InstagramPost, HashtagAnalytics, 
    ProfileAnalysisResponse
)

logger = logging.getLogger(__name__)


class InHouseInstagramScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session: Optional[httpx.AsyncClient] = None
        self.base_url = "https://www.instagram.com"
        
    async def __aenter__(self):
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        self.session = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    def _extract_json_from_html(self, html: str) -> Dict[str, Any]:
        """Extract JSON data from Instagram HTML"""
        try:
            # Look for window._sharedData
            shared_data_match = re.search(r'window\._sharedData = ({.*?});', html)
            if shared_data_match:
                shared_data = json.loads(shared_data_match.group(1))
                return shared_data
            
            # Look for additional data in script tags
            soup = BeautifulSoup(html, 'html.parser')
            script_tags = soup.find_all('script', type='application/ld+json')
            
            for script in script_tags:
                try:
                    data = json.loads(script.string)
                    if '@context' in data and 'ProfilePage' in str(data.get('@type', '')):
                        return data
                except json.JSONDecodeError:
                    continue
            
            return {}
            
        except Exception as e:
            logger.error(f"Error extracting JSON from HTML: {e}")
            return {}
    
    def _extract_profile_from_meta(self, html: str) -> Dict[str, Any]:
        """Extract profile data from meta tags"""
        soup = BeautifulSoup(html, 'html.parser')
        profile_data = {}
        
        # Extract from meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title:
            content = og_title.get('content', '')
            # Parse follower count from title like "John Doe (@johndoe) • 1,234 followers"
            follower_match = re.search(r'(\d+(?:,\d+)*)\s+followers?', content)
            if follower_match:
                follower_str = follower_match.group(1).replace(',', '')
                profile_data['followers'] = int(follower_str)
        
        og_description = soup.find('meta', property='og:description')
        if og_description:
            profile_data['biography'] = og_description.get('content', '')
        
        # Extract username from URL
        og_url = soup.find('meta', property='og:url')
        if og_url:
            url = og_url.get('content', '')
            username_match = re.search(r'instagram\.com/([^/]+)', url)
            if username_match:
                profile_data['username'] = username_match.group(1)
        
        # Extract profile image
        og_image = soup.find('meta', property='og:image')
        if og_image:
            profile_data['profile_pic_url'] = og_image.get('content', '')
        
        return profile_data
    
    def _parse_profile_from_scripts(self, html: str) -> Dict[str, Any]:
        """Parse profile data from script tags in HTML"""
        try:
            # Look for GraphQL data in script tags
            script_pattern = r'<script[^>]*>.*?window\.__additionalDataLoaded\(.*?,\s*({.*?})\);.*?</script>'
            matches = re.findall(script_pattern, html, re.DOTALL)
            
            for match in matches:
                try:
                    data = json.loads(match)
                    if 'graphql' in data and 'user' in data['graphql']:
                        return data['graphql']['user']
                except json.JSONDecodeError:
                    continue
            
            # Alternative pattern for newer Instagram pages
            pattern = r'"ProfilePage"\s*:\s*\[({.*?})\]'
            matches = re.findall(pattern, html, re.DOTALL)
            
            for match in matches:
                try:
                    data = json.loads(match)
                    if 'graphql' in data and 'user' in data['graphql']:
                        return data['graphql']['user']
                except json.JSONDecodeError:
                    continue
            
            return {}
            
        except Exception as e:
            logger.error(f"Error parsing profile from scripts: {e}")
            return {}
    
    async def scrape_profile(self, username: str) -> Dict[str, Any]:
        """Scrape Instagram profile data"""
        if not self.session:
            raise Exception("Session not initialized")
        
        try:
            # Add random delay to avoid detection
            await asyncio.sleep(random.uniform(1, 3))
            
            url = f"{self.base_url}/{username}/"
            logger.info(f"Scraping profile: {url}")
            
            response = await self.session.get(url)
            
            if response.status_code == 404:
                raise Exception(f"Profile not found: {username}")
            elif response.status_code != 200:
                raise Exception(f"Failed to fetch profile: {response.status_code}")
            
            html = response.text
            
            # Try multiple extraction methods
            profile_data = {}
            
            # Method 1: Extract from shared data
            shared_data = self._extract_json_from_html(html)
            if shared_data and 'entry_data' in shared_data:
                entry_data = shared_data['entry_data']
                if 'ProfilePage' in entry_data and entry_data['ProfilePage']:
                    graphql_data = entry_data['ProfilePage'][0].get('graphql', {})
                    if 'user' in graphql_data:
                        profile_data = graphql_data['user']
            
            # Method 2: Extract from meta tags (fallback)
            if not profile_data:
                profile_data = self._extract_profile_from_meta(html)
            
            # Method 3: Extract from script tags (fallback)
            if not profile_data:
                profile_data = self._parse_profile_from_scripts(html)
            
            # If we still don't have data, try basic parsing
            if not profile_data:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Try to find username in title
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text()
                    # Extract username from title like "John Doe (@johndoe) • Instagram"
                    username_match = re.search(r'\(@([^)]+)\)', title)
                    if username_match:
                        profile_data['username'] = username_match.group(1)
                    
                    # Extract name
                    name_match = re.search(r'^([^(]+)', title)
                    if name_match:
                        profile_data['full_name'] = name_match.group(1).strip()
            
            # Ensure we have at least the username
            if 'username' not in profile_data:
                profile_data['username'] = username
                
            logger.info(f"Extracted profile data keys: {list(profile_data.keys())}")
            return profile_data
            
        except Exception as e:
            logger.error(f"Error scraping profile {username}: {e}")
            raise Exception(f"Failed to scrape profile: {str(e)}")
    
    def _parse_profile_data(self, raw_data: Dict[str, Any], username: str) -> InstagramProfile:
        """Parse raw profile data into InstagramProfile model"""
        
        # Extract basic information with multiple fallback methods
        profile_username = raw_data.get('username', username)
        full_name = raw_data.get('full_name', raw_data.get('fullName', ''))
        biography = raw_data.get('biography', raw_data.get('bio', ''))
        
        # Handle follower counts with various formats
        followers = 0
        if 'edge_followed_by' in raw_data:
            followers = raw_data['edge_followed_by'].get('count', 0)
        elif 'follower_count' in raw_data:
            followers = raw_data['follower_count']
        elif 'followers' in raw_data:
            followers = raw_data['followers']
        
        following = 0
        if 'edge_follow' in raw_data:
            following = raw_data['edge_follow'].get('count', 0)
        elif 'following_count' in raw_data:
            following = raw_data['following_count']
        elif 'following' in raw_data:
            following = raw_data['following']
        
        posts_count = 0
        if 'edge_owner_to_timeline_media' in raw_data:
            posts_count = raw_data['edge_owner_to_timeline_media'].get('count', 0)
        elif 'media_count' in raw_data:
            posts_count = raw_data['media_count']
        elif 'posts' in raw_data:
            posts_count = raw_data['posts']
        
        is_verified = raw_data.get('is_verified', raw_data.get('verified', False))
        is_private = raw_data.get('is_private', raw_data.get('private', False))
        profile_pic_url = raw_data.get('profile_pic_url_hd', raw_data.get('profile_pic_url', ''))
        external_url = raw_data.get('external_url', raw_data.get('website', ''))
        
        # Calculate basic metrics
        engagement_rate = 0.0
        if followers > 0:
            # Estimate engagement rate (simplified calculation)
            engagement_rate = min(5.0, max(0.1, 100 / (followers / 1000 + 1)))
        
        content_quality_score = min(10.0, (posts_count / 100) + (followers / 10000) + 1)
        influence_score = min(10.0, (followers / 100000) + (2 if is_verified else 0) + (engagement_rate / 2))
        
        return InstagramProfile(
            username=profile_username,
            full_name=full_name,
            biography=biography,
            followers=followers,
            following=following,
            posts_count=posts_count,
            is_verified=is_verified,
            is_private=is_private,
            profile_pic_url=profile_pic_url,
            external_url=external_url,
            engagement_rate=engagement_rate,
            avg_likes=max(1, followers * engagement_rate / 100),
            avg_comments=max(1, followers * engagement_rate / 500),
            avg_engagement=max(1, followers * engagement_rate / 100),
            content_quality_score=content_quality_score,
            influence_score=influence_score
        )
    
    def _generate_recommendations(self, profile: InstagramProfile) -> List[str]:
        """Generate recommendations based on profile data"""
        recommendations = []
        
        if profile.followers < 1000:
            recommendations.append("Focus on creating consistent, high-quality content to grow your audience")
        elif profile.followers < 10000:
            recommendations.append("Great progress! Consider engaging more with your community")
        else:
            recommendations.append("Strong follower base! Focus on maintaining engagement quality")
        
        if not profile.is_verified and profile.followers > 10000:
            recommendations.append("Consider applying for account verification")
        
        if not profile.biography or len(profile.biography) < 50:
            recommendations.append("Optimize your bio with clear description and call-to-action")
        
        if profile.is_private and profile.followers > 1000:
            recommendations.append("Consider switching to public to increase discoverability")
        
        if profile.posts_count < 10:
            recommendations.append("Post more content to keep your audience engaged")
        
        return recommendations if recommendations else ["Keep creating great content!"]
    
    async def analyze_profile_comprehensive(self, username: str) -> ProfileAnalysisResponse:
        """Perform comprehensive profile analysis"""
        try:
            # Scrape profile data
            raw_profile_data = await self.scrape_profile(username)
            profile = self._parse_profile_data(raw_profile_data, username)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(profile)
            
            # Basic content strategy (estimated)
            content_strategy = {
                'best_posting_hour': 14,  # 2 PM is generally good
                'content_type_distribution': {'photo': 0.7, 'video': 0.3},
                'recommended_content_type': 'photo',
                'posting_frequency_per_day': 1.0,
                'avg_caption_length': 150
            }
            
            return ProfileAnalysisResponse(
                profile=profile,
                recent_posts=[],  # Will implement post scraping later
                hashtag_analysis=[],  # Will implement hashtag analysis later
                content_strategy=content_strategy,
                best_posting_times=['14:00', '19:00'],
                growth_recommendations=recommendations,
                analysis_timestamp=datetime.now(),
                data_quality_score=0.8
            )
            
        except Exception as e:
            logger.error(f"Profile analysis failed for {username}: {e}")
            raise Exception(f"Profile analysis failed: {str(e)}")