#!/usr/bin/env python3
"""
Batch Creator Analytics Script using Decodo Batch API
Efficiently fetch analytics for all creators in a single batch request.
"""

import requests
import json
import csv
import time
from datetime import datetime
from typing import Dict, List, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BatchCreatorAnalytics:
    def __init__(self):
        self.username = os.getenv('SMARTPROXY_USERNAME')
        self.password = os.getenv('SMARTPROXY_PASSWORD')
        self.batch_url = "https://scraper-api.decodo.com/v2/task/batch"
        
        if not self.username or not self.password:
            raise ValueError("SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD must be set in environment")
    
    def create_batch_payload(self, usernames: List[str]) -> Dict[str, Any]:
        """Create batch request payload for Instagram profiles"""
        return {
            "query": usernames,
            "target": "instagram_graphql_profile",
            "parse": "true"
        }
    
    def submit_batch_request(self, payload: Dict[str, Any]) -> str:
        """Submit batch request and return task ID"""
        print(f"Submitting batch request for {len(payload['query'])} creators...")
        
        response = requests.post(
            self.batch_url,
            auth=(self.username, self.password),
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Batch request failed: {response.status_code} - {response.text}")
        
        result = response.json()
        batch_id = result.get('id')
        print(f"Batch request submitted successfully. Batch ID: {batch_id}")
        return batch_id
    
    def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Check the status of a batch request"""
        status_url = f"https://scraper-api.decodo.com/v2/batch/{batch_id}"
        
        response = requests.get(
            status_url,
            auth=(self.username, self.password),
            timeout=10
        )
        
        if response.status_code != 200:
            raise Exception(f"Status check failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def wait_for_completion(self, batch_id: str, max_wait_time: int = 300) -> Dict[str, Any]:
        """Wait for batch request to complete"""
        print("Waiting for batch processing to complete...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status = self.check_batch_status(batch_id)
            
            # Check if all queries in the batch are completed
            queries = status.get('queries', [])
            if not queries:
                time.sleep(10)
                continue
                
            completed_queries = [q for q in queries if q.get('status') == 'completed']
            failed_queries = [q for q in queries if q.get('status') == 'failed']
            total_queries = len(queries)
            
            print(f"Progress: {len(completed_queries)}/{total_queries} completed, {len(failed_queries)} failed")
            
            if len(completed_queries) + len(failed_queries) == total_queries:
                print("Batch processing completed!")
                return status
            
            # Wait before checking again
            time.sleep(15)
        
        raise Exception(f"Batch processing timed out after {max_wait_time} seconds")
    
    def get_batch_results(self, batch_status: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve the results of a completed batch request"""
        results = []
        
        queries = batch_status.get('queries', [])
        print(f"Retrieving results for {len(queries)} queries...")
        
        for query in queries:
            query_id = query.get('id')
            if query.get('status') == 'completed':
                result_url = f"https://scraper-api.decodo.com/v2/task/{query_id}/result"
                
                try:
                    response = requests.get(
                        result_url,
                        auth=(self.username, self.password),
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        results.append(result_data)
                    else:
                        print(f"Failed to get result for query {query_id}: {response.status_code}")
                        results.append({'error': f'Failed to retrieve result: {response.status_code}'})
                        
                except Exception as e:
                    print(f"Error getting result for query {query_id}: {e}")
                    results.append({'error': str(e)})
            else:
                results.append({'error': f'Query failed with status: {query.get("status")}'})
        
        return results
    
    def parse_profile_data(self, result_item: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Parse individual profile data from batch results"""
        try:
            # Navigate to user data in the result structure
            content = result_item.get('content', {})
            if 'data' in content and 'user' in content['data']:
                user_data = content['data']['user']
            else:
                return {
                    'username': username,
                    'error': 'No user data found in response',
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
            
            # Engagement estimate (very rough based on followers)
            if followers > 0:
                if followers < 1000:
                    engagement_tier = 'Micro'
                elif followers < 10000:
                    engagement_tier = 'Small'
                elif followers < 100000:
                    engagement_tier = 'Medium'
                elif followers < 1000000:
                    engagement_tier = 'Large'
                else:
                    engagement_tier = 'Mega'
            else:
                engagement_tier = 'Unknown'
            
            return {
                'username': username,
                'full_name': full_name,
                'biography': biography[:150] + '...' if len(biography) > 150 else biography,
                'followers': followers,
                'following': following,
                'posts_count': posts_count,
                'following_ratio': following_ratio,
                'posts_per_1k_followers': posts_per_1k_followers,
                'engagement_tier': engagement_tier,
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
    
    def process_batch_results(self, batch_results: List[Dict[str, Any]], usernames: List[str]) -> List[Dict[str, Any]]:
        """Process all results from the batch request"""
        processed_results = []
        
        print(f"Processing {len(batch_results)} results...")
        
        for i, result_item in enumerate(batch_results):
            if i < len(usernames):
                username = usernames[i]
                parsed_data = self.parse_profile_data(result_item, username)
                processed_results.append(parsed_data)
                
                # Print progress
                if parsed_data['status'] == 'success':
                    followers = parsed_data.get('followers', 0)
                    verified = " [VERIFIED]" if parsed_data.get('is_verified') else ""
                    print(f"  @{username:<20} - {followers:>7,} followers{verified}")
                else:
                    print(f"  @{username:<20} - FAILED: {parsed_data.get('error', 'Unknown')[:30]}")
        
        return processed_results
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to JSON and CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_filename = f"batch_creator_analytics_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"JSON results saved to: {json_filename}")
        
        # Save CSV for successful results
        successful_results = [r for r in results if r['status'] == 'success']
        
        if successful_results:
            csv_filename = f"batch_creator_analytics_{timestamp}.csv"
            fieldnames = [
                'username', 'full_name', 'followers', 'following', 'posts_count',
                'following_ratio', 'posts_per_1k_followers', 'engagement_tier',
                'is_verified', 'is_private', 'account_type', 'has_website', 
                'bio_length', 'biography', 'scraped_at'
            ]
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in successful_results:
                    row = {field: result.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            print(f"CSV results saved to: {csv_filename}")
        
        return json_filename, csv_filename if successful_results else None
    
    def run_batch_analysis(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Run the complete batch analysis process"""
        try:
            # Create and submit batch request
            payload = self.create_batch_payload(usernames)
            task_id = self.submit_batch_request(payload)
            
            # Wait for completion
            batch_status = self.wait_for_completion(task_id)
            
            # Get results
            batch_results = self.get_batch_results(batch_status)
            
            # Process results
            processed_results = self.process_batch_results(batch_results, usernames)
            
            return processed_results
            
        except Exception as e:
            print(f"Batch analysis failed: {str(e)}")
            return []


def main():
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
    
    print("BATCH CREATOR ANALYTICS")
    print("=" * 60)
    print(f"Analyzing {len(creators)} creators using Decodo Batch API")
    print("=" * 60)
    
    # Initialize analyzer
    analyzer = BatchCreatorAnalytics()
    
    # Run batch analysis
    results = analyzer.run_batch_analysis(creators)
    
    if results:
        # Save results
        json_file, csv_file = analyzer.save_results(results)
        
        # Generate comprehensive summary
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'failed']
        
        print("\n" + "=" * 60)
        print("FINAL ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"Total creators processed: {len(results)}")
        print(f"Successfully analyzed: {len(successful)}")
        print(f"Failed to analyze: {len(failed)}")
        
        if successful:
            # Calculate comprehensive stats
            total_followers = sum(r['followers'] for r in successful)
            avg_followers = total_followers / len(successful)
            
            # Categorize creators
            verified_count = sum(1 for r in successful if r['is_verified'])
            private_count = sum(1 for r in successful if r['is_private'])
            business_count = sum(1 for r in successful if r['account_type'] == 'Business')
            creator_count = sum(1 for r in successful if r['account_type'] == 'Creator')
            
            # Engagement tiers
            tier_counts = {}
            for r in successful:
                tier = r['engagement_tier']
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            
            # Top performers
            top_followers = sorted(successful, key=lambda x: x['followers'], reverse=True)[:10]
            
            print(f"\nAGGREGATE STATISTICS")
            print("-" * 30)
            print(f"Total followers: {total_followers:,}")
            print(f"Average followers: {avg_followers:,.0f}")
            print(f"Verified accounts: {verified_count}")
            print(f"Private accounts: {private_count}")
            print(f"Business accounts: {business_count}")
            print(f"Creator accounts: {creator_count}")
            
            print(f"\nENGAGEMENT TIERS")
            print("-" * 20)
            for tier, count in sorted(tier_counts.items()):
                print(f"{tier}: {count} creators")
            
            print(f"\nTOP 10 CREATORS BY FOLLOWERS")
            print("-" * 45)
            for i, creator in enumerate(top_followers, 1):
                verified_badge = " ✓" if creator['is_verified'] else ""
                private_badge = " [Private]" if creator['is_private'] else ""
                print(f"{i:2d}. @{creator['username']:<22} {creator['followers']:>8,}{verified_badge}{private_badge}")
            
            if failed:
                print(f"\nFAILED CREATORS ({len(failed)})")
                print("-" * 30)
                for creator in failed:
                    print(f"@{creator['username']:<20} - {creator.get('error', 'Unknown')[:40]}")
        
        print(f"\nFiles saved:")
        print(f"  - {json_file}")
        if csv_file:
            print(f"  - {csv_file}")
    
    else:
        print("No results obtained from batch analysis.")


if __name__ == "__main__":
    main()