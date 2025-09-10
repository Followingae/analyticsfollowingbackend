#!/usr/bin/env python3
"""
Final Creator Analytics - Using Working SmartProxyClient Approach
Sequential processing to get reliable results for all creators
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

# Import our working client
import sys
sys.path.append('.')
from app.scrapers.smartproxy_client import SmartProxyClient

class FinalCreatorAnalytics:
    def __init__(self):
        self.username = os.getenv('SMARTPROXY_USERNAME')
        self.password = os.getenv('SMARTPROXY_PASSWORD')
        if not self.username or not self.password:
            raise ValueError("SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD must be set")
    
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
            
            # Engagement tier based on followers
            if followers < 1000:
                engagement_tier = 'Nano (< 1K)'
            elif followers < 10000:
                engagement_tier = 'Micro (1K-10K)'
            elif followers < 100000:
                engagement_tier = 'Mid (10K-100K)'
            elif followers < 1000000:
                engagement_tier = 'Macro (100K-1M)'
            else:
                engagement_tier = 'Mega (1M+)'
            
            # Content activity score (posts per 1000 followers)
            if posts_per_1k_followers < 5:
                activity_level = 'Low'
            elif posts_per_1k_followers < 15:
                activity_level = 'Medium'
            else:
                activity_level = 'High'
            
            return {
                'username': username,
                'full_name': full_name,
                'biography': biography[:200] + '...' if len(biography) > 200 else biography,
                'followers': followers,
                'following': following,
                'posts_count': posts_count,
                'following_ratio': following_ratio,
                'posts_per_1k_followers': posts_per_1k_followers,
                'engagement_tier': engagement_tier,
                'activity_level': activity_level,
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
        """Fetch analytics for a single creator using SmartProxyClient"""
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
        """Fetch analytics for all creators sequentially"""
        results = []
        
        print(f"Sequential processing of {len(usernames)} creators...")
        print("=" * 70)
        
        for i, username in enumerate(usernames, 1):
            print(f"[{i:2d}/{len(usernames)}] Processing @{username:<25}", end=" ... ")
            
            analytics = await self.fetch_creator_analytics(username)
            results.append(analytics)
            
            # Print result
            if analytics['status'] == 'success':
                followers = analytics.get('followers', 0)
                posts = analytics.get('posts_count', 0)
                tier = analytics.get('engagement_tier', '')
                verified = " [VERIFIED]" if analytics.get('is_verified') else ""
                private = " [PRIVATE]" if analytics.get('is_private') else ""
                print(f"{followers:>7,} followers, {posts:>3} posts ({tier}){verified}{private}")
            else:
                error = analytics.get('error', 'Unknown error')[:40]
                print(f"FAILED - {error}")
            
            # Add delay between requests to be respectful
            await asyncio.sleep(1.0)
        
        print("=" * 70)
        return results
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save comprehensive JSON
        json_filename = f"creator_analytics_final_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Save CSV for successful results
        successful_results = [r for r in results if r['status'] == 'success']
        csv_filename = None
        
        if successful_results:
            csv_filename = f"creator_analytics_final_{timestamp}.csv"
            fieldnames = [
                'username', 'full_name', 'followers', 'following', 'posts_count',
                'following_ratio', 'posts_per_1k_followers', 'engagement_tier', 'activity_level',
                'is_verified', 'is_private', 'account_type', 'has_website',
                'bio_length', 'biography', 'scraped_at'
            ]
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in successful_results:
                    row = {field: result.get(field, '') for field in fieldnames}
                    writer.writerow(row)
        
        # Also save failed results separately
        failed_results = [r for r in results if r['status'] == 'failed']
        failed_filename = None
        if failed_results:
            failed_filename = f"failed_creators_{timestamp}.json"
            with open(failed_filename, 'w', encoding='utf-8') as f:
                json.dump(failed_results, f, indent=2, ensure_ascii=False)
        
        return json_filename, csv_filename, failed_filename


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
    
    print("FINAL CREATOR ANALYTICS REPORT")
    print("=" * 70)
    print(f"Analyzing {len(creators)} Instagram creators")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    analyzer = FinalCreatorAnalytics()
    
    # Fetch all creator analytics
    results = await analyzer.fetch_all_creators(creators)
    
    # Save results to files
    json_file, csv_file, failed_file = analyzer.save_results(results)
    
    # Generate comprehensive analysis summary
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    
    print(f"\nCOMPREHENSIVE ANALYTICS SUMMARY")
    print("=" * 70)
    print(f"Total creators processed: {len(results)}")
    print(f"Successfully analyzed: {len(successful)}")
    print(f"Failed to analyze: {len(failed)}")
    print(f"Success rate: {len(successful)/len(results)*100:.1f}%")
    
    if successful:
        # Calculate aggregate statistics
        total_followers = sum(r['followers'] for r in successful)
        total_following = sum(r['following'] for r in successful)
        total_posts = sum(r['posts_count'] for r in successful)
        
        avg_followers = total_followers / len(successful)
        avg_following = total_following / len(successful)
        avg_posts = total_posts / len(successful)
        median_followers = sorted([r['followers'] for r in successful])[len(successful)//2]
        
        # Account characteristics
        verified_count = sum(1 for r in successful if r['is_verified'])
        private_count = sum(1 for r in successful if r['is_private'])
        business_count = sum(1 for r in successful if r['account_type'] == 'Business')
        creator_count = sum(1 for r in successful if r['account_type'] == 'Creator')
        personal_count = len(successful) - business_count - creator_count
        
        # Engagement tiers
        tier_counts = {}
        activity_counts = {}
        for r in successful:
            tier = r['engagement_tier']
            activity = r['activity_level']
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
        
        # Top performers
        top_creators = sorted(successful, key=lambda x: x['followers'], reverse=True)[:15]
        
        print(f"\nAGGREGATE STATISTICS")
        print("-" * 50)
        print(f"Total combined followers: {total_followers:,}")
        print(f"Total combined following: {total_following:,}")
        print(f"Total combined posts: {total_posts:,}")
        print(f"Average followers per creator: {avg_followers:,.0f}")
        print(f"Median followers per creator: {median_followers:,}")
        print(f"Average following per creator: {avg_following:,.0f}")
        print(f"Average posts per creator: {avg_posts:.1f}")
        
        print(f"\nACCOUNT CHARACTERISTICS")
        print("-" * 40)
        print(f"Verified accounts: {verified_count:2d} ({verified_count/len(successful)*100:.1f}%)")
        print(f"Private accounts: {private_count:2d} ({private_count/len(successful)*100:.1f}%)")
        print(f"Business accounts: {business_count:2d} ({business_count/len(successful)*100:.1f}%)")
        print(f"Creator accounts: {creator_count:2d} ({creator_count/len(successful)*100:.1f}%)")
        print(f"Personal accounts: {personal_count:2d} ({personal_count/len(successful)*100:.1f}%)")
        
        print(f"\nENGAGEMENT TIERS")
        print("-" * 30)
        for tier in ['Nano (< 1K)', 'Micro (1K-10K)', 'Mid (10K-100K)', 'Macro (100K-1M)', 'Mega (1M+)']:
            count = tier_counts.get(tier, 0)
            percentage = count / len(successful) * 100 if successful else 0
            print(f"{tier:<18}: {count:2d} creators ({percentage:.1f}%)")
        
        print(f"\nCONTENT ACTIVITY LEVELS")
        print("-" * 30)
        for activity in ['Low', 'Medium', 'High']:
            count = activity_counts.get(activity, 0)
            percentage = count / len(successful) * 100 if successful else 0
            print(f"{activity:<10}: {count:2d} creators ({percentage:.1f}%)")
        
        print(f"\nTOP 15 CREATORS BY FOLLOWERS")
        print("-" * 60)
        for i, creator in enumerate(top_creators, 1):
            verified = " [VERIFIED]" if creator['is_verified'] else ""
            private = " [PRIVATE]" if creator['is_private'] else ""
            tier = creator['engagement_tier']
            activity = creator['activity_level']
            account_type = creator['account_type']
            
            print(f"{i:2d}. @{creator['username']:<22} {creator['followers']:>8,}")
            try:
                print(f"    {creator['full_name'][:40]}")
            except UnicodeEncodeError:
                print(f"    {creator['full_name'][:40].encode('ascii', 'ignore').decode('ascii')}")
            print(f"    {tier} | {activity} Activity | {account_type}{verified}{private}")
            print()
        
        if failed:
            print(f"\nFAILED CREATORS ({len(failed)})")
            print("-" * 30)
            error_counts = {}
            for creator in failed:
                error = creator.get('error', 'Unknown error')
                error_type = error.split(':')[0] if ':' in error else error
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            for error_type, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"{error_type}: {count} creators")
    
    print(f"\nOUTPUT FILES GENERATED")
    print("-" * 30)
    print(f"Main results (JSON): {json_file}")
    if csv_file:
        print(f"Spreadsheet (CSV): {csv_file}")
    if failed_file:
        print(f"Failed creators: {failed_file}")
    
    print(f"\nAnalysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())