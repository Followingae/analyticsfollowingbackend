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
    ProfileAnalysisResponse, EngagementMetrics, AudienceInsights,
    CompetitorAnalysis, ContentPerformance
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
        """Extract JSON data from Instagram HTML using multiple methods"""
        extracted_data = {}
        
        try:
            # Method 1: window._sharedData (older Instagram format)
            shared_data_match = re.search(r'window\._sharedData = ({.*?});', html)
            if shared_data_match:
                shared_data = json.loads(shared_data_match.group(1))
                if 'entry_data' in shared_data and 'ProfilePage' in shared_data['entry_data']:
                    profile_page = shared_data['entry_data']['ProfilePage'][0]
                    if 'graphql' in profile_page and 'user' in profile_page['graphql']:
                        extracted_data.update(profile_page['graphql']['user'])
                        logger.info("Extracted data from window._sharedData")
            
            # Method 2: Look for GraphQL data in script tags
            script_patterns = [
                r'window\.__additionalDataLoaded\([^,]+,\s*({.*?})\)',
                r'"ProfilePage"\s*:\s*\[({.*?})\]',
                r'{"data":{"user":({.*?})}',
                r'"graphql":{"user":({.*?})}'
            ]
            
            for pattern in script_patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                for match in matches:
                    try:
                        data = json.loads(match)
                        if isinstance(data, dict) and ('username' in data or 'id' in data):
                            extracted_data.update(data)
                            logger.info(f"Extracted data using pattern: {pattern[:30]}...")
                            break
                    except json.JSONDecodeError:
                        continue
                if extracted_data and 'username' in extracted_data:
                    break
            
            # Method 3: Look for application/ld+json scripts
            soup = BeautifulSoup(html, 'html.parser')
            script_tags = soup.find_all('script', type='application/ld+json')
            
            for script in script_tags:
                try:
                    data = json.loads(script.string or script.text)
                    if isinstance(data, dict):
                        # Check for social media profile schema
                        if '@type' in data and 'Person' in str(data.get('@type', '')):
                            if 'sameAs' in data:
                                for url in data.get('sameAs', []):
                                    if 'instagram.com' in url:
                                        username = url.split('/')[-1]
                                        extracted_data['username'] = username
                        
                        # Look for other profile data
                        if 'name' in data:
                            extracted_data['full_name'] = data['name']
                        if 'description' in data:
                            extracted_data['biography'] = data['description']
                            
                except json.JSONDecodeError:
                    continue
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting JSON from HTML: {e}")
            return extracted_data
    
    def _extract_profile_from_meta(self, html: str) -> Dict[str, Any]:
        """Extract profile data from meta tags and HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        profile_data = {}
        
        # Extract from Open Graph meta tags
        og_title = soup.find('meta', property='og:title')
        if og_title:
            content = og_title.get('content', '')
            # Parse different title formats
            # Format: "John Doe (@johndoe) • 1,234 followers • 567 following"
            follower_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+followers?', content, re.IGNORECASE)
            if follower_match:
                follower_str = follower_match.group(1).replace(',', '')
                profile_data['followers'] = self._parse_count(follower_str)
            
            following_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?[KMB]?)\s+following', content, re.IGNORECASE)
            if following_match:
                following_str = following_match.group(1).replace(',', '')
                profile_data['following'] = self._parse_count(following_str)
            
            # Extract name and username from title
            name_username_match = re.search(r'^([^(]+)\s*\(@([^)]+)\)', content)
            if name_username_match:
                profile_data['full_name'] = name_username_match.group(1).strip()
                profile_data['username'] = name_username_match.group(2)
        
        # Extract description
        og_description = soup.find('meta', property='og:description')
        if og_description:
            description = og_description.get('content', '')
            if description and len(description) > 5:  # Ignore generic descriptions
                profile_data['biography'] = description
        
        # Extract username from URL if not found
        if 'username' not in profile_data:
            og_url = soup.find('meta', property='og:url')
            if og_url:
                url = og_url.get('content', '')
                username_match = re.search(r'instagram\.com/([^/?]+)', url)
                if username_match:
                    profile_data['username'] = username_match.group(1)
        
        # Extract profile image
        og_image = soup.find('meta', property='og:image')
        if og_image:
            profile_data['profile_pic_url'] = og_image.get('content', '')
        
        # Extract additional meta information
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title and not profile_data.get('full_name'):
            title_content = twitter_title.get('content', '')
            if '@' in title_content:
                name_part = title_content.split('(@')[0].strip()
                if name_part:
                    profile_data['full_name'] = name_part
        
        # Look for verification badge in meta or structured data
        if soup.find('meta', attrs={'property': 'og:title', 'content': re.compile(r'verified', re.I)}):
            profile_data['is_verified'] = True
        
        # Extract from title tag as fallback
        title_tag = soup.find('title')
        if title_tag and not profile_data.get('username'):
            title = title_tag.get_text()
            username_match = re.search(r'\(@([^)]+)\)', title)
            if username_match:
                profile_data['username'] = username_match.group(1)
        
        return profile_data
    
    def _parse_count(self, count_str: str) -> int:
        """Parse follower/following counts with K, M, B suffixes"""
        if not count_str:
            return 0
        
        count_str = count_str.upper().replace(',', '')
        
        try:
            if 'K' in count_str:
                return int(float(count_str.replace('K', '')) * 1000)
            elif 'M' in count_str:
                return int(float(count_str.replace('M', '')) * 1000000)
            elif 'B' in count_str:
                return int(float(count_str.replace('B', '')) * 1000000000)
            else:
                return int(count_str)
        except (ValueError, TypeError):
            return 0
    
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
        
        # Calculate advanced metrics
        engagement_rate = self._calculate_engagement_rate(followers, is_verified, posts_count)
        content_quality_score = self._calculate_content_quality_score(posts_count, followers, following, is_verified)
        influence_score = self._calculate_influence_score(followers, is_verified, engagement_rate, posts_count)
        
        # Calculate estimated engagement numbers
        avg_likes = self._estimate_avg_likes(followers, engagement_rate)
        avg_comments = self._estimate_avg_comments(followers, engagement_rate)
        avg_engagement = avg_likes + avg_comments
        
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
            avg_likes=avg_likes,
            avg_comments=avg_comments,
            avg_engagement=avg_engagement,
            content_quality_score=content_quality_score,
            influence_score=influence_score
        )
    
    def _calculate_engagement_rate(self, followers: int, is_verified: bool, posts_count: int) -> float:
        """Calculate realistic engagement rate based on follower count and other factors"""
        if followers == 0:
            return 0.0
        
        # Base engagement rate varies by follower count
        if followers < 1000:
            base_rate = 8.0  # Micro accounts have higher engagement
        elif followers < 10000:
            base_rate = 4.0
        elif followers < 100000:
            base_rate = 2.5
        elif followers < 1000000:
            base_rate = 1.5
        else:
            base_rate = 0.8  # Large accounts have lower rates
        
        # Adjustments
        if is_verified:
            base_rate *= 0.8  # Verified accounts often have lower engagement
        
        if posts_count > 1000:
            base_rate *= 1.1  # Active accounts maintain better engagement
        elif posts_count < 50:
            base_rate *= 0.7  # New accounts have lower engagement
        
        return round(base_rate, 2)
    
    def _calculate_content_quality_score(self, posts_count: int, followers: int, following: int, is_verified: bool) -> float:
        """Calculate content quality score based on various factors"""
        score = 5.0  # Base score
        
        # Post frequency score
        if posts_count > 500:
            score += 2.0
        elif posts_count > 100:
            score += 1.5
        elif posts_count > 50:
            score += 1.0
        elif posts_count < 10:
            score -= 1.0
        
        # Follower to following ratio
        if followers > 0 and following > 0:
            ratio = followers / following
            if ratio > 10:
                score += 1.5  # Good follower ratio
            elif ratio > 3:
                score += 1.0
            elif ratio < 0.5:
                score -= 0.5  # Following too many
        
        # Verification bonus
        if is_verified:
            score += 1.0
        
        # Account size bonus
        if followers > 100000:
            score += 1.0
        elif followers > 10000:
            score += 0.5
        
        return round(min(10.0, max(1.0, score)), 1)
    
    def _calculate_influence_score(self, followers: int, is_verified: bool, engagement_rate: float, posts_count: int) -> float:
        """Calculate overall influence score"""
        score = 0.0
        
        # Follower score (0-5 points)
        if followers > 10000000:
            score += 5.0
        elif followers > 1000000:
            score += 4.5
        elif followers > 100000:
            score += 4.0
        elif followers > 10000:
            score += 3.0
        elif followers > 1000:
            score += 2.0
        else:
            score += min(2.0, followers / 500)
        
        # Engagement score (0-3 points)
        if engagement_rate > 5:
            score += 3.0
        elif engagement_rate > 3:
            score += 2.5
        elif engagement_rate > 1:
            score += 2.0
        else:
            score += engagement_rate / 2
        
        # Verification bonus (0-1 points)
        if is_verified:
            score += 1.0
        
        # Activity bonus (0-1 points)
        if posts_count > 500:
            score += 1.0
        elif posts_count > 100:
            score += 0.5
        
        return round(min(10.0, score), 1)
    
    def _estimate_avg_likes(self, followers: int, engagement_rate: float) -> float:
        """Estimate average likes per post"""
        if followers == 0:
            return 0.0
        
        # Calculate likes based on engagement rate
        estimated_likes = followers * (engagement_rate / 100) * 0.8  # 80% of engagement is likes
        return round(max(1.0, estimated_likes), 1)
    
    def _estimate_avg_comments(self, followers: int, engagement_rate: float) -> float:
        """Estimate average comments per post"""
        if followers == 0:
            return 0.0
        
        # Calculate comments based on engagement rate
        estimated_comments = followers * (engagement_rate / 100) * 0.2  # 20% of engagement is comments
        return round(max(0.1, estimated_comments), 1)
    
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
        """Perform comprehensive profile analysis with enhanced metrics"""
        try:
            # Scrape profile data
            raw_profile_data = await self.scrape_profile(username)
            profile = self._parse_profile_data(raw_profile_data, username)
            
            # Generate detailed analytics
            engagement_metrics = self._generate_engagement_metrics(profile)
            audience_insights = self._generate_audience_insights(profile)
            competitor_analysis = self._generate_competitor_analysis(profile)
            content_performance = self._generate_content_performance(profile)
            
            # Generate recommendations
            recommendations = self._generate_enhanced_recommendations(profile, engagement_metrics)
            
            # Advanced content strategy
            content_strategy = self._generate_advanced_content_strategy(profile)
            
            return ProfileAnalysisResponse(
                profile=profile,
                recent_posts=[],  # Will implement post scraping later
                hashtag_analysis=[],  # Will implement hashtag analysis later
                engagement_metrics=engagement_metrics,
                audience_insights=audience_insights,
                competitor_analysis=competitor_analysis,
                content_performance=content_performance,
                content_strategy=content_strategy,
                best_posting_times=self._get_optimal_posting_times(profile),
                growth_recommendations=recommendations,
                analysis_timestamp=datetime.now(),
                data_quality_score=0.85,
                scraping_method="inhouse"
            )
            
        except Exception as e:
            logger.error(f"Profile analysis failed for {username}: {e}")
            raise Exception(f"Profile analysis failed: {str(e)}")
    
    def _generate_engagement_metrics(self, profile: InstagramProfile) -> EngagementMetrics:
        """Generate detailed engagement metrics"""
        like_rate = profile.engagement_rate * 0.8  # 80% of engagement is likes
        comment_rate = profile.engagement_rate * 0.15  # 15% is comments
        save_rate = profile.engagement_rate * 0.03  # 3% is saves
        share_rate = profile.engagement_rate * 0.02  # 2% is shares
        
        # Reach rate estimation based on follower count
        if profile.followers < 1000:
            reach_rate = 50.0
        elif profile.followers < 10000:
            reach_rate = 30.0
        elif profile.followers < 100000:
            reach_rate = 20.0
        else:
            reach_rate = 10.0
        
        return EngagementMetrics(
            like_rate=round(like_rate, 2),
            comment_rate=round(comment_rate, 2),
            save_rate=round(save_rate, 2),
            share_rate=round(share_rate, 2),
            reach_rate=reach_rate
        )
    
    def _generate_audience_insights(self, profile: InstagramProfile) -> AudienceInsights:
        """Generate audience insights based on profile characteristics"""
        # Estimate demographics based on follower count and engagement
        if profile.followers < 1000:
            primary_age_group = "18-24"
            gender_split = {"female": 55.0, "male": 45.0}
        elif profile.followers < 10000:
            primary_age_group = "25-34"
            gender_split = {"female": 60.0, "male": 40.0}
        else:
            primary_age_group = "25-44"
            gender_split = {"female": 52.0, "male": 48.0}
        
        # Generate activity times based on engagement patterns
        activity_times = ["09:00-11:00", "14:00-16:00", "19:00-21:00"]
        
        # Estimate top locations (placeholder - would need real data)
        top_locations = ["United States", "United Kingdom", "Canada"]
        
        # Generate interests based on profile type
        interests = ["lifestyle", "fashion", "technology", "entertainment"]
        
        return AudienceInsights(
            primary_age_group=primary_age_group,
            gender_split=gender_split,
            top_locations=top_locations,
            activity_times=activity_times,
            interests=interests
        )
    
    def _generate_competitor_analysis(self, profile: InstagramProfile) -> CompetitorAnalysis:
        """Generate competitive analysis"""
        # Calculate competitive score based on metrics
        competitive_score = min(10.0, (profile.influence_score + profile.engagement_rate) / 2)
        
        # Determine market position
        if profile.followers > 1000000:
            market_position = "Market Leader"
        elif profile.followers > 100000:
            market_position = "Strong Challenger"
        elif profile.followers > 10000:
            market_position = "Growing Player"
        else:
            market_position = "Emerging Account"
        
        # Generate growth opportunities
        growth_opportunities = []
        if profile.engagement_rate < 2.0:
            growth_opportunities.append("Improve content engagement")
        if profile.posts_count < 100:
            growth_opportunities.append("Increase posting frequency")
        if not profile.is_verified and profile.followers > 10000:
            growth_opportunities.append("Apply for verification")
        
        return CompetitorAnalysis(
            similar_accounts=[],  # Would need niche analysis
            competitive_score=round(competitive_score, 1),
            market_position=market_position,
            growth_opportunities=growth_opportunities
        )
    
    def _generate_content_performance(self, profile: InstagramProfile) -> ContentPerformance:
        """Generate content performance insights"""
        # Estimate content types based on engagement
        if profile.engagement_rate > 3.0:
            top_performing_content_types = ["Video", "Carousel", "Photos"]
        else:
            top_performing_content_types = ["Photos", "Carousel", "Video"]
        
        # Optimal posting frequency based on follower count
        if profile.followers < 1000:
            optimal_posting_frequency = "3-5 times per week"
        elif profile.followers < 10000:
            optimal_posting_frequency = "5-7 times per week"
        else:
            optimal_posting_frequency = "1-2 times per day"
        
        content_themes = ["Behind the scenes", "Educational content", "User-generated content"]
        hashtag_effectiveness = {"trending": 8.5, "niche": 7.2, "branded": 6.8}
        
        return ContentPerformance(
            top_performing_content_types=top_performing_content_types,
            optimal_posting_frequency=optimal_posting_frequency,
            content_themes=content_themes,
            hashtag_effectiveness=hashtag_effectiveness
        )
    
    def _generate_advanced_content_strategy(self, profile: InstagramProfile) -> Dict[str, Any]:
        """Generate advanced content strategy"""
        return {
            'primary_content_pillars': ['Educational', 'Entertainment', 'Behind-the-scenes'],
            'posting_schedule': {
                'monday': ['09:00', '18:00'],
                'tuesday': ['10:00', '19:00'],
                'wednesday': ['09:00', '18:00'],
                'thursday': ['10:00', '19:00'],
                'friday': ['09:00', '17:00'],
                'saturday': ['11:00', '16:00'],
                'sunday': ['12:00', '18:00']
            },
            'content_mix': {
                'photos': 40,
                'videos': 35,
                'carousels': 20,
                'reels': 5
            },
            'hashtag_strategy': {
                'trending_hashtags': 3,
                'niche_hashtags': 15,
                'branded_hashtags': 2,
                'location_hashtags': 2
            },
            'engagement_tactics': [
                'Ask questions in captions',
                'Use polls in stories',
                'Respond to comments quickly',
                'Share user-generated content'
            ]
        }
    
    def _get_optimal_posting_times(self, profile: InstagramProfile) -> List[str]:
        """Get optimal posting times based on profile characteristics"""
        if profile.followers < 1000:
            return ['09:00', '12:00', '18:00']
        elif profile.followers < 10000:
            return ['08:00', '14:00', '19:00']
        else:
            return ['07:00', '12:00', '17:00', '20:00']
    
    def _generate_enhanced_recommendations(self, profile: InstagramProfile, engagement_metrics: EngagementMetrics) -> List[str]:
        """Generate enhanced recommendations based on comprehensive analysis"""
        recommendations = []
        
        # Engagement-based recommendations
        if profile.engagement_rate < 1.0:
            recommendations.append("🔥 Focus on increasing engagement - try asking questions in captions")
        elif profile.engagement_rate < 3.0:
            recommendations.append("📈 Good engagement! Consider posting more consistently to boost growth")
        else:
            recommendations.append("⭐ Excellent engagement rate! Maintain your current content strategy")
        
        # Follower-based recommendations
        if profile.followers < 1000:
            recommendations.append("🌱 Focus on niche hashtags and consistent posting to reach 1K followers")
        elif profile.followers < 10000:
            recommendations.append("🚀 You're growing! Consider collaborating with similar accounts")
        elif profile.followers > 100000:
            recommendations.append("💎 Consider monetizing your audience through partnerships or products")
        
        # Content recommendations
        if profile.posts_count < 50:
            recommendations.append("📸 Post more content - aim for at least 3-4 posts per week")
        elif profile.posts_count > 1000:
            recommendations.append("🗂️ Consider organizing your content with highlights and story categories")
        
        # Verification recommendations
        if not profile.is_verified and profile.followers > 10000:
            recommendations.append("✅ Apply for verification - you meet the follower criteria")
        
        # Bio optimization
        if not profile.biography or len(profile.biography) < 50:
            recommendations.append("📝 Optimize your bio with a clear value proposition and call-to-action")
        
        # Privacy recommendations
        if profile.is_private and profile.followers > 1000:
            recommendations.append("🔓 Consider switching to public for better discoverability")
        
        # Reach recommendations
        if engagement_metrics.reach_rate < 15:
            recommendations.append("📡 Use trending hashtags to improve your content reach")
        
        return recommendations