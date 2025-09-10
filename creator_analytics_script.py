#!/usr/bin/env python3
"""
Creator Analytics Script
Simple script to fetch basic Instagram analytics using Decodo API only.
No database storage, no user association, no AI analysis, no CDN work.
"""

import asyncio
import json
import csv
from datetime import datetime
from typing import Dict, List, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our existing client
import sys
sys.path.append('.')
from app.scrapers.smartproxy_client import SmartProxyClient

class CreatorAnalyticsCollector:
    def __init__(self):
        self.username = os.getenv('SMARTPROXY_USERNAME')
        self.password = os.getenv('SMARTPROXY_PASSWORD')
        if not self.username or not self.password:
            raise ValueError("SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD must be set in environment")
    
    def parse_profile_data(self, raw_data: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Parse raw profile data into clean analytics format"""
        try:
            # Handle Decodo API response format
            if 'results' in raw_data and raw_data['results']:
                profile_data = raw_data['results'][0].get('content', {})
            elif 'data' in raw_data:
                profile_data = raw_data['data']
            else:
                profile_data = raw_data
            
            if not profile_data:
                return {
                    'username': username,
                    'error': 'No profile data found',
                    'status': 'failed'
                }
            
            # Handle different possible data structures
            user_data = profile_data.get('user', profile_data)
            if not user_data and 'graphql' in profile_data:
                user_data = profile_data.get('graphql', {}).get('user', {})
            
            # Extract basic information
            full_name = user_data.get('full_name', user_data.get('fullName', ''))
            biography = user_data.get('biography', user_data.get('bio', ''))
            
            # Handle follower counts with different possible keys
            followers = 0
            if 'edge_followed_by' in user_data:
                followers = int(user_data.get('edge_followed_by', {}).get('count', 0))
            elif 'follower_count' in user_data:
                followers = int(user_data.get('follower_count', 0))
            elif 'followers' in user_data:
                followers = int(user_data.get('followers', 0))
            
            following = 0
            if 'edge_follow' in user_data:
                following = int(user_data.get('edge_follow', {}).get('count', 0))
            elif 'following_count' in user_data:
                following = int(user_data.get('following_count', 0))
            elif 'following' in user_data:
                following = int(user_data.get('following', 0))
            
            posts_count = 0
            if 'edge_owner_to_timeline_media' in user_data:
                posts_count = int(user_data.get('edge_owner_to_timeline_media', {}).get('count', 0))
            elif 'media_count' in user_data:
                posts_count = int(user_data.get('media_count', 0))
            elif 'posts' in user_data:
                posts_count = int(user_data.get('posts', 0))
            
            is_verified = user_data.get('is_verified', user_data.get('verified', False))
            is_private = user_data.get('is_private', user_data.get('private', False))
            external_url = user_data.get('external_url', user_data.get('website', ''))
            
            # Calculate basic metrics
            following_ratio = round(following / max(followers, 1), 4)
            posts_per_1k_followers = round((posts_count / max(followers, 1)) * 1000, 2)
            
            return {
                'username': username,
                'full_name': full_name,
                'biography': biography[:100] + '...' if len(biography) > 100 else biography,
                'followers': followers,
                'following': following,
                'posts_count': posts_count,
                'following_ratio': following_ratio,
                'posts_per_1k_followers': posts_per_1k_followers,
                'is_verified': is_verified,
                'is_private': is_private,
                'has_website': bool(external_url),
                'bio_length': len(biography),
                'status': 'success',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'username': username,
                'error': str(e),
                'status': 'failed',
                'scraped_at': datetime.now().isoformat()
            }
    
    async def fetch_creator_analytics(self, username: str) -> Dict[str, Any]:
        """Fetch analytics for a single creator"""
        try:
            async with SmartProxyClient(self.username, self.password) as client:
                raw_data = await client.scrape_instagram_profile(username)
                return self.parse_profile_data(raw_data, username)
        except Exception as e:
            return {
                'username': username,
                'error': str(e),
                'status': 'failed',
                'scraped_at': datetime.now().isoformat()
            }
    
    async def fetch_all_creators(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Fetch analytics for all creators"""
        results = []
        
        print(f"Starting analytics collection for {len(usernames)} creators...")
        
        for i, username in enumerate(usernames, 1):
            print(f"[{i}/{len(usernames)}] Fetching data for @{username}...")
            
            analytics = await self.fetch_creator_analytics(username)
            results.append(analytics)
            
            # Add small delay to be respectful to the API
            await asyncio.sleep(0.5)
            
            # Print status
            if analytics['status'] == 'success':
                print(f"  Success - {analytics.get('followers', 0):,} followers")
            else:
                print(f"  Failed - {analytics.get('error', 'Unknown error')}")
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], format: str = 'both'):
        """Save results to JSON and/or CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format in ['json', 'both']:
            json_filename = f"creator_analytics_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results saved to {json_filename}")
        
        if format in ['csv', 'both']:
            csv_filename = f"creator_analytics_{timestamp}.csv"
            
            # Get all possible fields from successful results
            all_fields = set()
            for result in results:
                if result['status'] == 'success':
                    all_fields.update(result.keys())
            
            # Define field order for CSV
            field_order = [
                'username', 'full_name', 'followers', 'following', 'posts_count',
                'following_ratio', 'posts_per_1k_followers', 'is_verified', 
                'is_private', 'has_website', 'bio_length', 'biography',
                'status', 'error', 'scraped_at'
            ]
            
            # Add any extra fields not in our predefined order
            extra_fields = sorted(all_fields - set(field_order))
            fieldnames = [f for f in field_order if f in all_fields] + extra_fields
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in results:
                    # Fill missing fields with empty strings for CSV
                    row = {field: result.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            print(f"Results saved to {csv_filename}")


async def main():
    # List of creators to analyze
    creators = [
        "_shafaqsfoodcam_", "Imaan.rehman", "narjesgram", "Sabisfooddiary", 
        "aimenblogs", "sareens.stories", "Craving.unwrap", "Explore_by_deep",
        "millicious__", "Neelam_trends_dubai", "dcinni22", "Fattumreviews",
        "Abubakr.dxb", "Alinaaharis_", "shiningwith_mystars", "Loca_llica",
        "elias.a.saad", "illustrify_bynk_", "Saharuuuuuuuu", "explorewithrinnitangri",
        "Livewithshikha", "Mpress____", "Desiburgerduo", "Irsanoman",
        "hinasufyaan", "joyful_jasmine8", "yaa.its_ayaz", "Foodventurres",
        "Suroobee", "Myfamilymyworldd", "Aisha_in_dxb", "Ugc_zainabbachlani",
        "Sidrakhanyousufzaiii", "Priti_upadhyay", "Self_xplorer", "bong_mom_in_dubai",
        "Blogs_by_zunaira", "Lizbethology", "Sruthiprathyush", "dxb_heer",
        "noreen_blogs", "rashi_rahul_ruhan_rahul", "Uaelifeofwife", "aishaaa_asif",
        "Dubai_backpacker", "Desimomlife", "naziyafzal", "Farziiim",
        "Imahimunawar", "Bhartibhatt999", "xaxmofficial", "mazen.shamsan",
        "Momofzohan", "explore_with_ruchit"
    ]
    
    collector = CreatorAnalyticsCollector()
    
    # Fetch analytics for all creators
    results = await collector.fetch_all_creators(creators)
    
    # Save results
    collector.save_results(results, format='both')
    
    # Print summary
    successful = sum(1 for r in results if r['status'] == 'success')
    failed = len(results) - successful
    
    print(f"\nAnalytics Collection Complete!")
    print(f"Successfully analyzed: {successful} creators")
    print(f"Failed to analyze: {failed} creators")
    
    if successful > 0:
        # Calculate some quick stats from successful results
        success_results = [r for r in results if r['status'] == 'success']
        total_followers = sum(r['followers'] for r in success_results)
        avg_followers = total_followers / successful
        verified_count = sum(1 for r in success_results if r['is_verified'])
        private_count = sum(1 for r in success_results if r['is_private'])
        
        print(f"\nQuick Stats:")
        print(f"Total followers across all creators: {total_followers:,}")
        print(f"Average followers per creator: {avg_followers:,.0f}")
        print(f"Verified accounts: {verified_count}")
        print(f"Private accounts: {private_count}")


if __name__ == "__main__":
    asyncio.run(main())