#!/usr/bin/env python3
"""
Working Batch Creator Analytics - Using individual query tracking
"""

import requests
import json
import csv
import time
from datetime import datetime
from typing import Dict, List, Any
import os
from dotenv import load_dotenv

load_dotenv()

class WorkingBatchAnalytics:
    def __init__(self):
        self.username = os.getenv('SMARTPROXY_USERNAME')
        self.password = os.getenv('SMARTPROXY_PASSWORD')
        self.batch_url = "https://scraper-api.decodo.com/v2/task/batch"
        
        if not self.username or not self.password:
            raise ValueError("SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD must be set")
    
    def submit_batch_request(self, usernames: List[str]) -> List[str]:
        """Submit batch request and return list of query IDs"""
        payload = {
            "query": usernames,
            "target": "instagram_graphql_profile",
            "parse": "true"
        }
        
        print(f"Submitting batch request for {len(usernames)} creators...")
        
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
        queries = result.get('queries', [])
        query_ids = [q.get('id') for q in queries]
        
        print(f"Batch submitted (ID: {batch_id}) - {len(query_ids)} individual queries created")
        return query_ids
    
    def check_query_status(self, query_id: str) -> Dict[str, Any]:
        """Check the status of an individual query"""
        status_url = f"https://scraper-api.decodo.com/v2/task/{query_id}"
        
        response = requests.get(
            status_url,
            auth=(self.username, self.password),
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {'status': 'error', 'error': f'Status check failed: {response.status_code}'}
    
    def get_query_result(self, query_id: str) -> Dict[str, Any]:
        """Get the result of a completed query"""
        result_url = f"https://scraper-api.decodo.com/v2/task/{query_id}/result"
        
        response = requests.get(
            result_url,
            auth=(self.username, self.password),
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'Result retrieval failed: {response.status_code}'}
    
    def wait_for_queries_completion(self, query_ids: List[str], usernames: List[str], max_wait_time: int = 600):
        """Wait for all queries to complete and collect results"""
        print("Waiting for queries to complete...")
        start_time = time.time()
        
        completed_results = {}
        failed_queries = set()
        
        while time.time() - start_time < max_wait_time:
            pending_queries = [qid for qid in query_ids if qid not in completed_results and qid not in failed_queries]
            
            if not pending_queries:
                break
            
            print(f"Checking status of {len(pending_queries)} pending queries...")
            
            for query_id in pending_queries:
                try:
                    status = self.check_query_status(query_id)
                    query_status = status.get('status')
                    
                    if query_status == 'completed':
                        result = self.get_query_result(query_id)
                        completed_results[query_id] = result
                        print(f"  Query {query_id[:8]}... completed")
                        
                    elif query_status in ['failed', 'error']:
                        failed_queries.add(query_id)
                        print(f"  Query {query_id[:8]}... failed")
                        
                except Exception as e:
                    print(f"  Error checking query {query_id[:8]}...: {e}")
            
            completed_count = len(completed_results)
            failed_count = len(failed_queries)
            total_processed = completed_count + failed_count
            
            print(f"Progress: {completed_count} completed, {failed_count} failed, {len(query_ids) - total_processed} pending")
            
            if total_processed == len(query_ids):
                break
                
            time.sleep(20)  # Wait 20 seconds before next check
        
        # Create ordered results matching the input usernames
        ordered_results = []
        for i, username in enumerate(usernames):
            if i < len(query_ids):
                query_id = query_ids[i]
                if query_id in completed_results:
                    ordered_results.append(completed_results[query_id])
                else:
                    ordered_results.append({'error': 'Query failed or timed out', 'username': username})
            else:
                ordered_results.append({'error': 'No query created', 'username': username})
        
        return ordered_results
    
    def parse_profile_data(self, result_item: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Parse profile data from query result"""
        try:
            if 'error' in result_item:
                return {
                    'username': username,
                    'error': result_item['error'],
                    'status': 'failed',
                    'scraped_at': datetime.now().isoformat()
                }
            
            # Navigate to user data
            content = result_item.get('content', {})
            if 'data' in content and 'user' in content['data']:
                user_data = content['data']['user']
            else:
                return {
                    'username': username,
                    'error': 'No user data found',
                    'status': 'failed'
                }
            
            # Extract profile information
            full_name = user_data.get('full_name', '')
            biography = user_data.get('biography', '')
            
            followers = user_data.get('edge_followed_by', {}).get('count', 0)
            following = user_data.get('edge_follow', {}).get('count', 0)
            posts_count = user_data.get('edge_owner_to_timeline_media', {}).get('count', 0)
            
            is_verified = user_data.get('is_verified', False)
            is_private = user_data.get('is_private', False)
            is_business = user_data.get('is_business_account', False)
            is_professional = user_data.get('is_professional_account', False)
            
            external_url = user_data.get('external_url', '')
            
            # Calculate metrics
            following_ratio = round(following / max(followers, 1), 4) if followers > 0 else 0
            posts_per_1k_followers = round((posts_count / max(followers, 1)) * 1000, 2) if followers > 0 else 0
            
            # Account type
            account_type = 'Personal'
            if is_business:
                account_type = 'Business'
            elif is_professional:
                account_type = 'Creator'
            
            # Engagement tier
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
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_filename = f"creator_analytics_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Save CSV for successful results
        successful_results = [r for r in results if r['status'] == 'success']
        csv_filename = None
        
        if successful_results:
            csv_filename = f"creator_analytics_{timestamp}.csv"
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
        
        return json_filename, csv_filename
    
    def run_analysis(self, usernames: List[str]) -> List[Dict[str, Any]]:
        """Run the complete analysis"""
        try:
            # Submit batch request
            query_ids = self.submit_batch_request(usernames)
            
            # Wait for completion and get results
            raw_results = self.wait_for_queries_completion(query_ids, usernames)
            
            # Parse results
            print(f"\nProcessing {len(raw_results)} results...")
            processed_results = []
            
            for i, raw_result in enumerate(raw_results):
                username = usernames[i] if i < len(usernames) else f"unknown_{i}"
                parsed = self.parse_profile_data(raw_result, username)
                processed_results.append(parsed)
                
                if parsed['status'] == 'success':
                    followers = parsed.get('followers', 0)
                    verified = " ✓" if parsed.get('is_verified') else ""
                    print(f"  @{username:<25} - {followers:>8,} followers{verified}")
                else:
                    print(f"  @{username:<25} - FAILED: {parsed.get('error', '')[:30]}")
            
            return processed_results
            
        except Exception as e:
            print(f"Analysis failed: {e}")
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
    
    print("CREATOR ANALYTICS - BATCH API")
    print("=" * 60)
    print(f"Analyzing {len(creators)} creators")
    print("=" * 60)
    
    analyzer = WorkingBatchAnalytics()
    results = analyzer.run_analysis(creators)
    
    if results:
        # Save results
        json_file, csv_file = analyzer.save_results(results)
        
        # Generate summary
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'failed']
        
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(f"Total creators: {len(results)}")
        print(f"Successfully analyzed: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if successful:
            # Stats
            total_followers = sum(r['followers'] for r in successful)
            avg_followers = total_followers / len(successful)
            
            verified_count = sum(1 for r in successful if r['is_verified'])
            private_count = sum(1 for r in successful if r['is_private'])
            
            # Top performers
            top_creators = sorted(successful, key=lambda x: x['followers'], reverse=True)[:10]
            
            print(f"\nSTATISTICS")
            print("-" * 30)
            print(f"Total followers: {total_followers:,}")
            print(f"Average followers: {avg_followers:,.0f}")
            print(f"Verified accounts: {verified_count}")
            print(f"Private accounts: {private_count}")
            
            print(f"\nTOP 10 CREATORS")
            print("-" * 50)
            for i, creator in enumerate(top_creators, 1):
                verified = " ✓" if creator['is_verified'] else ""
                tier = creator['engagement_tier']
                print(f"{i:2d}. @{creator['username']:<20} {creator['followers']:>8,} {tier}{verified}")
        
        print(f"\nFiles saved:")
        print(f"  JSON: {json_file}")
        if csv_file:
            print(f"  CSV: {csv_file}")
    
    else:
        print("No results obtained.")


if __name__ == "__main__":
    main()