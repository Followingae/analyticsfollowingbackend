#!/usr/bin/env python3
"""
Wemby Profile AI Data Analysis Script
=====================================

This script analyzes the AI data completeness for the wemby profile
using Supabase MCP integration to query the database directly.

Checks:
1. Profile existence and basic data
2. AI analysis fields on profile
3. Posts data and AI analysis completion
4. Specific AI fields analysis
5. Overall AI data completeness report
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os
import sys

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WembyAIAnalyzer:
    def __init__(self):
        """Initialize Supabase client for database queries."""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

        if not self.supabase_url or not self.supabase_service_key:
            raise ValueError("Missing Supabase configuration in environment variables")

        self.supabase: Client = create_client(self.supabase_url, self.supabase_service_key)
        self.username = 'wemby'

    def execute_query(self, query: str, description: str) -> Dict[str, Any]:
        """Execute a SQL query and return results with error handling."""
        try:
            print(f"\n🔍 {description}")
            print(f"📝 Query: {query}")
            print("-" * 80)

            result = self.supabase.rpc('execute_sql', {'query': query}).execute()

            if result.data:
                print(f"✅ Success: Found {len(result.data)} records")
                return {
                    'success': True,
                    'data': result.data,
                    'count': len(result.data),
                    'query': query,
                    'description': description
                }
            else:
                print(f"⚠️  No data returned")
                return {
                    'success': True,
                    'data': [],
                    'count': 0,
                    'query': query,
                    'description': description
                }

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'description': description
            }

    def analyze_profile_basic_data(self) -> Dict[str, Any]:
        """Query basic profile data for wemby."""
        query = f"SELECT * FROM profiles WHERE username = '{self.username}'"
        return self.execute_query(query, f"Checking basic profile data for {self.username}")

    def analyze_profile_ai_fields(self) -> Dict[str, Any]:
        """Query AI-specific fields from the profile."""
        query = f"""
        SELECT
            username,
            ai_primary_content_type,
            ai_content_distribution,
            ai_avg_sentiment_score,
            ai_language_distribution,
            ai_content_quality_score,
            ai_profile_analyzed_at,
            created_at,
            updated_at
        FROM profiles
        WHERE username = '{self.username}'
        """
        return self.execute_query(query, f"Checking AI analysis fields for {self.username} profile")

    def analyze_posts_basic_data(self) -> Dict[str, Any]:
        """Query basic posts data for wemby."""
        query = f"""
        SELECT
            COUNT(*) as total_posts
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
        """
        return self.execute_query(query, f"Counting total posts for {self.username}")

    def analyze_posts_ai_completion(self) -> Dict[str, Any]:
        """Analyze AI analysis completion status for posts."""
        query = f"""
        SELECT
            COUNT(*) as total_posts,
            COUNT(ai_content_category) as posts_with_category,
            COUNT(ai_sentiment) as posts_with_sentiment,
            COUNT(ai_language_code) as posts_with_language,
            COUNT(ai_analyzed_at) as posts_analyzed,
            COUNT(ai_analysis_raw) as posts_with_raw_analysis,
            ROUND(COUNT(ai_analyzed_at)::numeric / COUNT(*)::numeric * 100, 2) as completion_percentage
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
        """
        return self.execute_query(query, f"Analyzing AI completion rates for {self.username} posts")

    def analyze_posts_ai_samples(self) -> Dict[str, Any]:
        """Get sample posts with AI analysis data."""
        query = f"""
        SELECT
            p.id,
            LEFT(p.caption, 100) as caption_preview,
            p.ai_content_category,
            p.ai_category_confidence,
            p.ai_sentiment,
            p.ai_sentiment_score,
            p.ai_sentiment_confidence,
            p.ai_language_code,
            p.ai_language_confidence,
            p.ai_analyzed_at,
            CASE
                WHEN p.ai_analysis_raw IS NOT NULL THEN 'Present'
                ELSE 'Missing'
            END as raw_analysis_status
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
        ORDER BY p.created_at DESC
        LIMIT 10
        """
        return self.execute_query(query, f"Sampling recent posts with AI data for {self.username}")

    def analyze_ai_field_distribution(self) -> Dict[str, Any]:
        """Analyze distribution of AI analysis values."""
        query = f"""
        SELECT
            ai_content_category,
            COUNT(*) as count,
            ROUND(AVG(ai_category_confidence), 3) as avg_confidence
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
          AND ai_content_category IS NOT NULL
        GROUP BY ai_content_category
        ORDER BY count DESC
        """
        return self.execute_query(query, f"Analyzing content category distribution for {self.username}")

    def analyze_sentiment_distribution(self) -> Dict[str, Any]:
        """Analyze sentiment analysis distribution."""
        query = f"""
        SELECT
            ai_sentiment,
            COUNT(*) as count,
            ROUND(AVG(ai_sentiment_score), 3) as avg_score,
            ROUND(AVG(ai_sentiment_confidence), 3) as avg_confidence
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
          AND ai_sentiment IS NOT NULL
        GROUP BY ai_sentiment
        ORDER BY count DESC
        """
        return self.execute_query(query, f"Analyzing sentiment distribution for {self.username}")

    def analyze_language_distribution(self) -> Dict[str, Any]:
        """Analyze language detection distribution."""
        query = f"""
        SELECT
            ai_language_code,
            COUNT(*) as count,
            ROUND(AVG(ai_language_confidence), 3) as avg_confidence
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
          AND ai_language_code IS NOT NULL
        GROUP BY ai_language_code
        ORDER BY count DESC
        """
        return self.execute_query(query, f"Analyzing language distribution for {self.username}")

    def check_raw_analysis_samples(self) -> Dict[str, Any]:
        """Check samples of raw AI analysis data."""
        query = f"""
        SELECT
            p.id,
            LEFT(p.caption, 50) as caption_preview,
            ai_analysis_raw
        FROM posts p
        JOIN profiles pr ON p.profile_id = pr.id
        WHERE pr.username = '{self.username}'
          AND ai_analysis_raw IS NOT NULL
        ORDER BY p.created_at DESC
        LIMIT 3
        """
        return self.execute_query(query, f"Sampling raw AI analysis data for {self.username}")

    def print_analysis_results(self, results: Dict[str, Any]):
        """Print formatted analysis results."""
        if results['success']:
            if results['count'] > 0:
                for record in results['data']:
                    print(json.dumps(record, indent=2, default=str))
            else:
                print("No data found")
        else:
            print(f"Query failed: {results['error']}")
        print()

    def generate_comprehensive_report(self):
        """Generate a comprehensive AI data analysis report."""
        print("=" * 100)
        print(f"🤖 WEMBY PROFILE AI DATA ANALYSIS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)

        # Store all results for final summary
        all_results = {}

        # 1. Basic Profile Data
        print("\n📊 SECTION 1: BASIC PROFILE DATA")
        print("=" * 50)
        profile_data = self.analyze_profile_basic_data()
        self.print_analysis_results(profile_data)
        all_results['profile_basic'] = profile_data

        # 2. Profile AI Fields
        print("\n🧠 SECTION 2: PROFILE AI ANALYSIS FIELDS")
        print("=" * 50)
        profile_ai = self.analyze_profile_ai_fields()
        self.print_analysis_results(profile_ai)
        all_results['profile_ai'] = profile_ai

        # 3. Posts Count
        print("\n📝 SECTION 3: POSTS DATA OVERVIEW")
        print("=" * 50)
        posts_count = self.analyze_posts_basic_data()
        self.print_analysis_results(posts_count)
        all_results['posts_count'] = posts_count

        # 4. AI Completion Analysis
        print("\n✅ SECTION 4: AI ANALYSIS COMPLETION RATES")
        print("=" * 50)
        ai_completion = self.analyze_posts_ai_completion()
        self.print_analysis_results(ai_completion)
        all_results['ai_completion'] = ai_completion

        # 5. Sample Posts with AI Data
        print("\n🔍 SECTION 5: SAMPLE POSTS WITH AI DATA")
        print("=" * 50)
        posts_samples = self.analyze_posts_ai_samples()
        self.print_analysis_results(posts_samples)
        all_results['posts_samples'] = posts_samples

        # 6. Content Category Distribution
        print("\n📊 SECTION 6: CONTENT CATEGORY DISTRIBUTION")
        print("=" * 50)
        category_dist = self.analyze_ai_field_distribution()
        self.print_analysis_results(category_dist)
        all_results['category_distribution'] = category_dist

        # 7. Sentiment Analysis Distribution
        print("\n😊 SECTION 7: SENTIMENT ANALYSIS DISTRIBUTION")
        print("=" * 50)
        sentiment_dist = self.analyze_sentiment_distribution()
        self.print_analysis_results(sentiment_dist)
        all_results['sentiment_distribution'] = sentiment_dist

        # 8. Language Detection Distribution
        print("\n🌍 SECTION 8: LANGUAGE DETECTION DISTRIBUTION")
        print("=" * 50)
        language_dist = self.analyze_language_distribution()
        self.print_analysis_results(language_dist)
        all_results['language_distribution'] = language_dist

        # 9. Raw Analysis Samples
        print("\n🔬 SECTION 9: RAW AI ANALYSIS SAMPLES")
        print("=" * 50)
        raw_samples = self.check_raw_analysis_samples()
        self.print_analysis_results(raw_samples)
        all_results['raw_samples'] = raw_samples

        # 10. Executive Summary
        self.generate_executive_summary(all_results)

        return all_results

    def generate_executive_summary(self, results: Dict[str, Any]):
        """Generate executive summary of AI data completeness."""
        print("\n" + "=" * 100)
        print("📋 EXECUTIVE SUMMARY: WEMBY AI DATA COMPLETENESS")
        print("=" * 100)

        try:
            # Profile Status
            profile_exists = results['profile_basic']['success'] and results['profile_basic']['count'] > 0
            print(f"👤 Profile Status: {'✅ Found' if profile_exists else '❌ Not Found'}")

            if profile_exists and results['profile_ai']['success'] and results['profile_ai']['data']:
                profile_ai_data = results['profile_ai']['data'][0]
                print(f"🧠 Profile AI Analysis: {'✅ Complete' if profile_ai_data.get('ai_profile_analyzed_at') else '❌ Missing'}")
                print(f"📊 Content Type: {profile_ai_data.get('ai_primary_content_type', 'Not Set')}")
                print(f"😊 Avg Sentiment: {profile_ai_data.get('ai_avg_sentiment_score', 'Not Set')}")
                print(f"🏆 Quality Score: {profile_ai_data.get('ai_content_quality_score', 'Not Set')}")

            # Posts Analysis
            if results['posts_count']['success'] and results['posts_count']['data']:
                total_posts = results['posts_count']['data'][0]['total_posts']
                print(f"\n📝 Total Posts: {total_posts}")

                if results['ai_completion']['success'] and results['ai_completion']['data']:
                    completion_data = results['ai_completion']['data'][0]
                    completion_rate = completion_data.get('completion_percentage', 0)

                    print(f"🤖 AI Analysis Completion: {completion_rate}%")
                    print(f"   ├── Posts with Category: {completion_data.get('posts_with_category', 0)}/{total_posts}")
                    print(f"   ├── Posts with Sentiment: {completion_data.get('posts_with_sentiment', 0)}/{total_posts}")
                    print(f"   ├── Posts with Language: {completion_data.get('posts_with_language', 0)}/{total_posts}")
                    print(f"   └── Posts with Raw Analysis: {completion_data.get('posts_with_raw_analysis', 0)}/{total_posts}")

                    # Status assessment
                    if completion_rate >= 95:
                        status = "✅ EXCELLENT - Nearly complete AI analysis"
                    elif completion_rate >= 80:
                        status = "🟡 GOOD - Most posts analyzed"
                    elif completion_rate >= 50:
                        status = "🟠 PARTIAL - Some analysis missing"
                    else:
                        status = "❌ INCOMPLETE - Significant gaps in analysis"

                    print(f"\n🎯 Overall Status: {status}")

            # Data Quality Assessment
            print(f"\n📊 Data Quality Insights:")

            if results['category_distribution']['success'] and results['category_distribution']['data']:
                categories = len(results['category_distribution']['data'])
                print(f"   ├── Content Categories Detected: {categories}")

            if results['sentiment_distribution']['success'] and results['sentiment_distribution']['data']:
                sentiments = len(results['sentiment_distribution']['data'])
                print(f"   ├── Sentiment Types Detected: {sentiments}")

            if results['language_distribution']['success'] and results['language_distribution']['data']:
                languages = len(results['language_distribution']['data'])
                print(f"   └── Languages Detected: {languages}")

            # Recommendations
            print(f"\n💡 Recommendations:")
            if profile_exists:
                if results['ai_completion']['success']:
                    completion_rate = results['ai_completion']['data'][0].get('completion_percentage', 0) if results['ai_completion']['data'] else 0
                    if completion_rate < 100:
                        print(f"   ├── Re-run AI analysis for {100 - completion_rate:.1f}% of posts missing analysis")
                    if completion_rate == 0:
                        print(f"   ├── Initialize AI analysis pipeline for wemby profile")
                    else:
                        print(f"   ├── AI analysis is {completion_rate}% complete - very good coverage!")

                print(f"   └── Verify AI model performance and data quality metrics")
            else:
                print(f"   └── Profile not found - check username or data import status")

        except Exception as e:
            print(f"❌ Error generating summary: {str(e)}")

        print("\n" + "=" * 100)

def main():
    """Main execution function."""
    try:
        analyzer = WembyAIAnalyzer()
        results = analyzer.generate_comprehensive_report()

        # Save results to file for reference
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"wemby_ai_analysis_{timestamp}.json"

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n💾 Results saved to: {output_file}")

    except Exception as e:
        print(f"❌ Critical error: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())