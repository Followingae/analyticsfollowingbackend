#!/usr/bin/env python3
"""
Creator Analytics Final Script
Fetch basic Instagram analytics using Decodo API with correct data parsing.
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
        """Parse raw profile data from Decodo API response"""
        try:
            # Navigate to the user data - correct path for Decodo API
            if 'results' in raw_data and raw_data['results']:
                content = raw_data['results'][0].get('content', {})
                if 'data' in content and 'user' in content['data']:
                    user_data = content['data']['user']
                else:
                    return {
                        'username': username,
                        'error': 'No user data found in response',
                        'status': 'failed'
                    }
            else:
                return {
                    'username': username,
                    'error': 'Invalid response format',
                    'status': 'failed'
                }
            
            # Extract profile information
            full_name = user_data.get('full_name', '')
            biography = user_data.get('biography', '')
            
            # Get follower/following counts from edge data
            followers = user_data.get('edge_followed_by', {}).get('count', 0)
            following = user_data.get('edge_follow', {}).get('count', 0)
            posts_count = user_data.get('edge_owner_to_timeline_media', {}).get('count', 0)
            
            # Get verification and privacy status
            is_verified = user_data.get('is_verified', False)
            is_private = user_data.get('is_private', False)
            is_business = user_data.get('is_business_account', False)
            is_professional = user_data.get('is_professional_account', False)
            
            # External URL
            external_url = user_data.get('external_url', '')
            
            # Calculate basic metrics
            following_ratio = round(following / max(followers, 1), 4) if followers > 0 else 0
            posts_per_1k_followers = round((posts_count / max(followers, 1)) * 1000, 2) if followers > 0 else 0
            
            # Account type
            account_type = 'Personal'
            if is_business:
                account_type = 'Business'
            elif is_professional:
                account_type = 'Creator'
            
            return {
                'username': username,
                'full_name': full_name,
                'biography': biography[:150] + '...' if len(biography) > 150 else biography,
                'followers': followers,
                'following': following,
                'posts_count': posts_count,
                'following_ratio': following_ratio,
                'posts_per_1k_followers': posts_per_1k_followers,
                'is_verified': is_verified,
                'is_private': is_private,
                'account_type': account_type,
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
        """Fetch analytics for all creators with progress updates"""
        results = []
        
        print(f"Starting analytics collection for {len(usernames)} creators...")
        print("=" * 60)
        
        for i, username in enumerate(usernames, 1):
            print(f"[{i:2d}/{len(usernames)}] Processing @{username:<25}", end=" ... ")
            
            analytics = await self.fetch_creator_analytics(username)
            results.append(analytics)
            
            # Print result
            if analytics['status'] == 'success':
                followers = analytics.get('followers', 0)
                posts = analytics.get('posts_count', 0)
                verified = " [VERIFIED]" if analytics.get('is_verified') else ""
                print(f"{followers:>7,} followers, {posts:>3} posts{verified}")
            else:
                print(f"FAILED - {analytics.get('error', 'Unknown error')[:30]}")
            
            # Add delay to be respectful to API
            await asyncio.sleep(0.8)
        
        print("=" * 60)
        return results
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_filename = f"creator_analytics_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"JSON results saved to: {json_filename}")
        
        # Save CSV  
        csv_filename = f"creator_analytics_{timestamp}.csv"
        successful_results = [r for r in results if r['status'] == 'success']
        
        if successful_results:
            fieldnames = [
                'username', 'full_name', 'followers', 'following', 'posts_count',
                'following_ratio', 'posts_per_1k_followers', 'is_verified', 
                'is_private', 'account_type', 'has_website', 'bio_length', 
                'biography', 'scraped_at'
            ]
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in successful_results:
                    row = {field: result.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            print(f"CSV results saved to: {csv_filename}")
        
        # Also save failed results separately
        failed_results = [r for r in results if r['status'] == 'failed']
        if failed_results:
            failed_filename = f"failed_creators_{timestamp}.json"
            with open(failed_filename, 'w', encoding='utf-8') as f:
                json.dump(failed_results, f, indent=2, ensure_ascii=False)
            print(f"Failed results saved to: {failed_filename}")


async def main():
    # All creators to analyze
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
    
    # Fetch all creator analytics
    results = await collector.fetch_all_creators(creators)
    
    # Save results to files
    collector.save_results(results)
    
    # Print comprehensive summary
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    
    print(f"\nFINAL SUMMARY")
    print("=" * 60)
    print(f"Total creators analyzed: {len(results)}")
    print(f"Successfully analyzed: {len(successful)}")
    print(f"Failed to analyze: {len(failed)}")
    
    if successful:
        # Calculate comprehensive stats
        total_followers = sum(r['followers'] for r in successful)
        total_following = sum(r['following'] for r in successful)
        total_posts = sum(r['posts_count'] for r in successful)
        
        avg_followers = total_followers / len(successful)
        avg_following = total_following / len(successful)
        avg_posts = total_posts / len(successful)
        
        verified_count = sum(1 for r in successful if r['is_verified'])
        private_count = sum(1 for r in successful if r['is_private'])
        business_count = sum(1 for r in successful if r['account_type'] == 'Business')
        creator_count = sum(1 for r in successful if r['account_type'] == 'Creator')
        
        # Top performers
        top_followers = sorted(successful, key=lambda x: x['followers'], reverse=True)[:5]
        
        print(f"\nAGGREGATE STATISTICS")
        print("-" * 30)
        print(f"Total followers across all creators: {total_followers:,}")
        print(f"Average followers per creator: {avg_followers:,.0f}")
        print(f"Average following per creator: {avg_following:,.0f}")
        print(f"Average posts per creator: {avg_posts:.1f}")
        print(f"Verified accounts: {verified_count}")
        print(f"Private accounts: {private_count}")
        print(f"Business accounts: {business_count}")
        print(f"Creator accounts: {creator_count}")
        
        print(f"\nTOP 5 CREATORS BY FOLLOWERS")
        print("-" * 40)
        for i, creator in enumerate(top_followers, 1):
            verified_badge = " ✓" if creator['is_verified'] else ""
            print(f"{i}. @{creator['username']:<20} {creator['followers']:>8,} followers{verified_badge}")
        
        if failed:
            print(f"\nFAILED CREATORS ({len(failed)})")
            print("-" * 30)
            for creator in failed:
                print(f"@{creator['username']:<20} - {creator.get('error', 'Unknown error')[:40]}")


if __name__ == "__main__":
    asyncio.run(main())