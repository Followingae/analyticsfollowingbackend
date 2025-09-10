#!/usr/bin/env python3
"""
Decodo Batch Analytics - Following Official Documentation
Uses individual task submission for reliable results
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

class DecodoBatchAnalytics:
    def __init__(self):
        self.username = os.getenv('SMARTPROXY_USERNAME')
        self.password = os.getenv('SMARTPROXY_PASSWORD')
        self.single_task_url = "https://scraper-api.decodo.com/v2/task"
        
        if not self.username or not self.password:
            raise ValueError("SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD must be set")
    
    def submit_single_task(self, username: str) -> str:
        """Submit a single Instagram profile task and return task_id"""
        payload = {
            "query": username,
            "target": "instagram_graphql_profile",
            "parse": True
        }
        
        response = requests.post(
            self.single_task_url,
            auth=(self.username, self.password),
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"Task submission failed for {username}: {response.status_code} - {response.text}")
        
        result = response.json()
        task_id = result.get('id')
        
        if not task_id:
            raise Exception(f"No task_id received for {username}")
        
        return task_id
    
    def submit_all_tasks(self, usernames: List[str]) -> Dict[str, str]:
        """Submit tasks for all creators and return username -> task_id mapping"""
        task_mapping = {}
        
        print(f"Submitting {len(usernames)} individual tasks...")
        
        for i, username in enumerate(usernames, 1):
            try:
                task_id = self.submit_single_task(username)
                task_mapping[username] = task_id
                print(f"[{i:2d}/{len(usernames)}] @{username:<25} -> Task {task_id}")
                
                # Small delay between submissions to be respectful
                time.sleep(0.5)
                
            except Exception as e:
                print(f"[{i:2d}/{len(usernames)}] @{username:<25} -> FAILED: {str(e)[:50]}")
                task_mapping[username] = None
        
        successful_tasks = sum(1 for task_id in task_mapping.values() if task_id is not None)
        print(f"\nSuccessfully submitted: {successful_tasks}/{len(usernames)} tasks")
        
        return task_mapping
    
    def check_task_status(self, task_id: str) -> str:
        """Check the status of a task"""
        status_url = f"{self.single_task_url}/{task_id}"
        
        try:
            response = requests.get(
                status_url,
                auth=(self.username, self.password),
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('status', 'unknown')
            else:
                return 'error'
        except:
            return 'error'
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """Get the result of a completed task"""
        result_url = f"{self.single_task_url}/{task_id}/results"
        
        try:
            response = requests.get(
                result_url,
                auth=(self.username, self.password),
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'Result retrieval failed: {response.status_code}'}
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def wait_for_tasks_completion(self, task_mapping: Dict[str, str], max_wait_time: int = 600):
        """Wait for all tasks to complete and collect results"""
        print(f"\nWaiting for task completion (max {max_wait_time}s)...")
        start_time = time.time()
        
        results = {}
        completed_tasks = set()
        failed_tasks = set()
        
        # Get valid tasks
        valid_tasks = {username: task_id for username, task_id in task_mapping.items() if task_id is not None}
        
        while time.time() - start_time < max_wait_time:
            pending_tasks = {
                username: task_id for username, task_id in valid_tasks.items() 
                if username not in completed_tasks and username not in failed_tasks
            }
            
            if not pending_tasks:
                break
            
            print(f"Checking {len(pending_tasks)} pending tasks...")
            
            for username, task_id in pending_tasks.items():
                try:
                    status = self.check_task_status(task_id)
                    
                    if status == 'done':
                        # Task completed, get result
                        result = self.get_task_result(task_id)
                        results[username] = result
                        completed_tasks.add(username)
                        print(f"  + @{username:<20} completed")
                        
                    elif status in ['failed', 'error']:
                        results[username] = {'error': f'Task failed with status: {status}'}
                        failed_tasks.add(username)
                        print(f"  - @{username:<20} failed")
                        
                    # If status is still 'pending' or 'running', continue waiting
                    
                except Exception as e:
                    results[username] = {'error': f'Status check failed: {str(e)}'}
                    failed_tasks.add(username)
                    print(f"  ! @{username:<20} error: {str(e)[:30]}")
            
            completed = len(completed_tasks)
            failed = len(failed_tasks) 
            pending = len(valid_tasks) - completed - failed
            
            print(f"Progress: {completed} completed, {failed} failed, {pending} pending")
            
            if pending == 0:
                break
                
            time.sleep(20)  # Wait before next status check
        
        # Handle tasks that never got submitted
        for username, task_id in task_mapping.items():
            if task_id is None:
                results[username] = {'error': 'Task submission failed'}
        
        return results
    
    def parse_profile_data(self, result_item: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Parse profile data from task result"""
        try:
            if 'error' in result_item:
                return {
                    'username': username,
                    'error': result_item['error'],
                    'status': 'failed',
                    'scraped_at': datetime.now().isoformat()
                }
            
            # Navigate to user data - handle different response structures
            content = result_item.get('content', {})
            
            # For individual tasks, the structure might be different
            if 'data' in content and 'user' in content['data']:
                user_data = content['data']['user']
            elif 'user' in content:
                user_data = content['user']
            else:
                return {
                    'username': username,
                    'error': 'No user data found in response',
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
        """Run the complete analysis using individual task submission"""
        try:
            # Submit all tasks
            task_mapping = self.submit_all_tasks(usernames)
            
            # Wait for completion and get results
            raw_results = self.wait_for_tasks_completion(task_mapping)
            
            # Parse results
            print(f"\nProcessing {len(raw_results)} results...")
            processed_results = []
            
            for username in usernames:
                raw_result = raw_results.get(username, {'error': 'No result found'})
                parsed = self.parse_profile_data(raw_result, username)
                processed_results.append(parsed)
                
                if parsed['status'] == 'success':
                    followers = parsed.get('followers', 0)
                    verified = " [VERIFIED]" if parsed.get('is_verified') else ""
                    tier = parsed.get('engagement_tier', '')
                    print(f"  @{username:<25} - {followers:>8,} followers ({tier}){verified}")
                else:
                    error = parsed.get('error', 'Unknown error')[:40]
                    print(f"  @{username:<25} - FAILED: {error}")
            
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
    
    print("DECODO CREATOR ANALYTICS")
    print("=" * 60)
    print(f"Analyzing {len(creators)} Instagram creators")
    print("Using individual task submission for reliability")
    print("=" * 60)
    
    analyzer = DecodoBatchAnalytics()
    results = analyzer.run_analysis(creators)
    
    if results:
        # Save results
        json_file, csv_file = analyzer.save_results(results)
        
        # Generate comprehensive summary
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'failed']
        
        print("\n" + "=" * 60)
        print("COMPREHENSIVE ANALYTICS SUMMARY")
        print("=" * 60)
        print(f"Total creators analyzed: {len(results)}")
        print(f"Successfully processed: {len(successful)}")
        print(f"Failed to process: {len(failed)}")
        
        if successful:
            # Calculate comprehensive statistics
            total_followers = sum(r['followers'] for r in successful)
            total_following = sum(r['following'] for r in successful)
            total_posts = sum(r['posts_count'] for r in successful)
            
            avg_followers = total_followers / len(successful)
            avg_following = total_following / len(successful)
            avg_posts = total_posts / len(successful)
            
            # Categorization
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
            top_creators = sorted(successful, key=lambda x: x['followers'], reverse=True)[:10]
            
            print(f"\nAGGREGATE STATISTICS")
            print("-" * 40)
            print(f"Combined followers: {total_followers:,}")
            print(f"Combined following: {total_following:,}")
            print(f"Total posts: {total_posts:,}")
            print(f"Average followers per creator: {avg_followers:,.0f}")
            print(f"Average following per creator: {avg_following:,.0f}")
            print(f"Average posts per creator: {avg_posts:.1f}")
            
            print(f"\nACCOUNT CHARACTERISTICS")
            print("-" * 30)
            print(f"Verified accounts: {verified_count} ({verified_count/len(successful)*100:.1f}%)")
            print(f"Private accounts: {private_count} ({private_count/len(successful)*100:.1f}%)")
            print(f"Business accounts: {business_count}")
            print(f"Creator accounts: {creator_count}")
            print(f"Personal accounts: {len(successful) - business_count - creator_count}")
            
            print(f"\nENGAGEMENT TIER DISTRIBUTION")
            print("-" * 35)
            for tier, count in sorted(tier_counts.items()):
                percentage = count / len(successful) * 100
                print(f"{tier:<15}: {count:2d} creators ({percentage:.1f}%)")
            
            print(f"\nTOP 10 CREATORS BY FOLLOWERS")
            print("-" * 50)
            for i, creator in enumerate(top_creators, 1):
                verified = " [VERIFIED]" if creator['is_verified'] else ""
                private = " [Private]" if creator['is_private'] else ""
                tier = creator['engagement_tier']
                print(f"{i:2d}. @{creator['username']:<22} {creator['followers']:>8,} ({tier}){verified}{private}")
            
            if failed:
                print(f"\nFAILED CREATORS ({len(failed)})")
                print("-" * 30)
                for creator in failed[:10]:  # Show first 10 failures
                    error = creator.get('error', 'Unknown error')[:50]
                    print(f"@{creator['username']:<20} - {error}")
                if len(failed) > 10:
                    print(f"... and {len(failed) - 10} more")
        
        print(f"\nOUTPUT FILES")
        print("-" * 20)
        print(f"JSON: {json_file}")
        if csv_file:
            print(f"CSV:  {csv_file}")
        
        print(f"\nAnalysis completed successfully!")
        
    else:
        print("No results obtained from analysis.")


if __name__ == "__main__":
    main()