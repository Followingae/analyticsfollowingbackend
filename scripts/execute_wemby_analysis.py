#!/usr/bin/env python3
"""
Execute Wemby AI Analysis - Direct Database Query Script
========================================================

This script connects directly to the Supabase database and executes
the comprehensive analysis queries for the wemby profile.

Run with: python scripts/execute_wemby_analysis.py
"""

import asyncio
import asyncpg
import json
import os
from datetime import datetime
from typing import Dict, Any, List
import sys

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

class WembyDatabaseAnalyzer:
    def __init__(self):
        """Initialize database connection."""
        # Parse the DATABASE_URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        self.database_url = database_url
        self.username = 'wemby'

    async def connect_db(self):
        """Create database connection."""
        try:
            self.conn = await asyncpg.connect(self.database_url)
            print("✅ Connected to database successfully")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {str(e)}")
            return False

    async def close_db(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            await self.conn.close()
            print("✅ Database connection closed")

    async def execute_query(self, query: str, description: str) -> Dict[str, Any]:
        """Execute a query and return formatted results."""
        try:
            print(f"\n🔍 {description}")
            print(f"📝 Query: {query[:100]}{'...' if len(query) > 100 else ''}")
            print("-" * 80)

            # Execute query
            rows = await self.conn.fetch(query)

            # Convert to list of dictionaries
            results = [dict(row) for row in rows]

            print(f"✅ Success: Found {len(results)} records")

            return {
                'success': True,
                'data': results,
                'count': len(results),
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

    def print_results(self, results: Dict[str, Any]):
        """Print formatted query results."""
        if results['success']:
            if results['count'] > 0:
                for i, record in enumerate(results['data']):
                    print(f"Record {i+1}:")
                    for key, value in record.items():
                        if isinstance(value, str) and len(value) > 100:
                            print(f"  {key}: {value[:100]}...")
                        else:
                            print(f"  {key}: {value}")
                    print()
            else:
                print("No data found")
        else:
            print(f"Query failed: {results['error']}")
        print()

    async def run_comprehensive_analysis(self):
        """Run all analysis queries."""
        print("=" * 100)
        print(f"🤖 WEMBY PROFILE AI DATA ANALYSIS")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)

        # Connect to database
        if not await self.connect_db():
            return None

        results = {}

        try:
            # 1. Basic Profile Data
            query1 = """
            SELECT
                id,
                username,
                full_name,
                biography,
                followers_count,
                following_count,
                posts_count,
                created_at,
                updated_at
            FROM profiles
            WHERE username = 'wemby'
            """
            results['profile_basic'] = await self.execute_query(query1, "Basic Profile Information")
            self.print_results(results['profile_basic'])

            # 2. Profile AI Fields
            query2 = """
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
            WHERE username = 'wemby'
            """
            results['profile_ai'] = await self.execute_query(query2, "Profile AI Analysis Fields")
            self.print_results(results['profile_ai'])

            # 3. Posts Count
            query3 = """
            SELECT
                COUNT(*) as total_posts
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE pr.username = 'wemby'
            """
            results['posts_count'] = await self.execute_query(query3, "Total Posts Count")
            self.print_results(results['posts_count'])

            # 4. AI Completion Analysis
            query4 = """
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
            WHERE pr.username = 'wemby'
            """
            results['ai_completion'] = await self.execute_query(query4, "AI Analysis Completion Rates")
            self.print_results(results['ai_completion'])

            # 5. Sample Posts with AI Data
            query5 = """
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
                END as raw_analysis_status,
                p.created_at
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE pr.username = 'wemby'
            ORDER BY p.created_at DESC
            LIMIT 10
            """
            results['posts_samples'] = await self.execute_query(query5, "Sample Posts with AI Data")
            self.print_results(results['posts_samples'])

            # 6. Content Category Distribution
            query6 = """
            SELECT
                ai_content_category,
                COUNT(*) as count,
                ROUND(AVG(ai_category_confidence), 3) as avg_confidence
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE pr.username = 'wemby'
              AND ai_content_category IS NOT NULL
            GROUP BY ai_content_category
            ORDER BY count DESC
            """
            results['category_distribution'] = await self.execute_query(query6, "Content Category Distribution")
            self.print_results(results['category_distribution'])

            # 7. Sentiment Distribution
            query7 = """
            SELECT
                ai_sentiment,
                COUNT(*) as count,
                ROUND(AVG(ai_sentiment_score), 3) as avg_score,
                ROUND(AVG(ai_sentiment_confidence), 3) as avg_confidence
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE pr.username = 'wemby'
              AND ai_sentiment IS NOT NULL
            GROUP BY ai_sentiment
            ORDER BY count DESC
            """
            results['sentiment_distribution'] = await self.execute_query(query7, "Sentiment Analysis Distribution")
            self.print_results(results['sentiment_distribution'])

            # 8. Language Distribution
            query8 = """
            SELECT
                ai_language_code,
                COUNT(*) as count,
                ROUND(AVG(ai_language_confidence), 3) as avg_confidence
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE pr.username = 'wemby'
              AND ai_language_code IS NOT NULL
            GROUP BY ai_language_code
            ORDER BY count DESC
            """
            results['language_distribution'] = await self.execute_query(query8, "Language Detection Distribution")
            self.print_results(results['language_distribution'])

            # 9. Raw Analysis Samples
            query9 = """
            SELECT
                p.id,
                LEFT(p.caption, 50) as caption_preview,
                ai_analysis_raw
            FROM posts p
            JOIN profiles pr ON p.profile_id = pr.id
            WHERE pr.username = 'wemby'
              AND ai_analysis_raw IS NOT NULL
            ORDER BY p.created_at DESC
            LIMIT 3
            """
            results['raw_samples'] = await self.execute_query(query9, "Raw AI Analysis Samples")
            self.print_results(results['raw_samples'])

            # Generate Executive Summary
            await self.generate_executive_summary(results)

            return results

        except Exception as e:
            print(f"❌ Critical error during analysis: {str(e)}")
            return None

        finally:
            await self.close_db()

    async def generate_executive_summary(self, results: Dict[str, Any]):
        """Generate executive summary of findings."""
        print("\n" + "=" * 100)
        print("📋 EXECUTIVE SUMMARY: WEMBY AI DATA COMPLETENESS")
        print("=" * 100)

        try:
            # Profile Status
            profile_exists = results['profile_basic']['success'] and results['profile_basic']['count'] > 0
            print(f"👤 Profile Status: {'✅ Found' if profile_exists else '❌ Not Found'}")

            if profile_exists:
                profile_data = results['profile_basic']['data'][0]
                print(f"📊 Profile Info:")
                print(f"   ├── Username: {profile_data.get('username')}")
                print(f"   ├── Full Name: {profile_data.get('full_name', 'Not Set')}")
                print(f"   ├── Followers: {profile_data.get('followers_count', 0):,}")
                print(f"   ├── Following: {profile_data.get('following_count', 0):,}")
                print(f"   └── Posts Count: {profile_data.get('posts_count', 0):,}")

                # Profile AI Analysis
                if results['profile_ai']['success'] and results['profile_ai']['data']:
                    ai_data = results['profile_ai']['data'][0]
                    analyzed = ai_data.get('ai_profile_analyzed_at') is not None
                    print(f"\n🧠 Profile AI Analysis: {'✅ Complete' if analyzed else '❌ Missing'}")
                    if analyzed:
                        print(f"   ├── Primary Content: {ai_data.get('ai_primary_content_type', 'Not Set')}")
                        print(f"   ├── Avg Sentiment: {ai_data.get('ai_avg_sentiment_score', 'Not Set')}")
                        print(f"   ├── Quality Score: {ai_data.get('ai_content_quality_score', 'Not Set')}")
                        print(f"   └── Analyzed At: {ai_data.get('ai_profile_analyzed_at', 'Not Set')}")

                # Posts Analysis
                if results['posts_count']['success'] and results['posts_count']['data']:
                    total_posts = results['posts_count']['data'][0]['total_posts']
                    print(f"\n📝 Posts Analysis:")
                    print(f"   └── Total Posts in DB: {total_posts:,}")

                    if results['ai_completion']['success'] and results['ai_completion']['data']:
                        completion = results['ai_completion']['data'][0]
                        completion_rate = completion.get('completion_percentage', 0)

                        print(f"\n🤖 AI Analysis Completion: {completion_rate}%")
                        print(f"   ├── Posts with Category: {completion.get('posts_with_category', 0)}/{total_posts}")
                        print(f"   ├── Posts with Sentiment: {completion.get('posts_with_sentiment', 0)}/{total_posts}")
                        print(f"   ├── Posts with Language: {completion.get('posts_with_language', 0)}/{total_posts}")
                        print(f"   └── Posts with Raw Analysis: {completion.get('posts_with_raw_analysis', 0)}/{total_posts}")

                        # Overall Status
                        if completion_rate >= 95:
                            status = "✅ EXCELLENT - AI analysis nearly complete"
                        elif completion_rate >= 80:
                            status = "🟡 GOOD - Most posts analyzed"
                        elif completion_rate >= 50:
                            status = "🟠 PARTIAL - Some analysis missing"
                        else:
                            status = "❌ INCOMPLETE - Significant gaps"

                        print(f"\n🎯 Overall Status: {status}")

                # Data Quality Insights
                print(f"\n📊 Data Quality Insights:")

                if results['category_distribution']['success'] and results['category_distribution']['data']:
                    categories = len(results['category_distribution']['data'])
                    print(f"   ├── Content Categories: {categories}")
                    top_category = results['category_distribution']['data'][0] if results['category_distribution']['data'] else None
                    if top_category:
                        print(f"   │   └── Top: {top_category['ai_content_category']} ({top_category['count']} posts)")

                if results['sentiment_distribution']['success'] and results['sentiment_distribution']['data']:
                    sentiments = len(results['sentiment_distribution']['data'])
                    print(f"   ├── Sentiment Types: {sentiments}")
                    for sentiment in results['sentiment_distribution']['data']:
                        print(f"   │   └── {sentiment['ai_sentiment']}: {sentiment['count']} posts (avg: {sentiment['avg_score']})")

                if results['language_distribution']['success'] and results['language_distribution']['data']:
                    languages = len(results['language_distribution']['data'])
                    print(f"   └── Languages Detected: {languages}")
                    for lang in results['language_distribution']['data']:
                        print(f"       └── {lang['ai_language_code']}: {lang['count']} posts")

                # Recommendations
                print(f"\n💡 Recommendations:")
                if results['ai_completion']['success'] and results['ai_completion']['data']:
                    completion_rate = results['ai_completion']['data'][0].get('completion_percentage', 0)
                    if completion_rate < 100:
                        missing = 100 - completion_rate
                        print(f"   ├── Re-run AI analysis for {missing:.1f}% missing posts")
                    if completion_rate == 0:
                        print(f"   ├── Initialize AI analysis pipeline for wemby")
                    elif completion_rate >= 95:
                        print(f"   ├── AI analysis is excellent ({completion_rate}% complete)")

                    print(f"   └── Verify AI model performance and accuracy")
            else:
                print(f"   └── Profile 'wemby' not found in database")
                print(f"\n💡 Recommendations:")
                print(f"   ├── Check if username is correct")
                print(f"   ├── Verify profile has been imported from Instagram")
                print(f"   └── Run profile import if needed")

        except Exception as e:
            print(f"❌ Error generating summary: {str(e)}")

        print("\n" + "=" * 100)


async def main():
    """Main execution function."""
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    try:
        analyzer = WembyDatabaseAnalyzer()
        results = await analyzer.run_comprehensive_analysis()

        if results:
            # Save results to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"wemby_ai_analysis_{timestamp}.json"

            # Convert datetime objects to strings for JSON serialization
            def json_serial(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=json_serial)

            print(f"\n💾 Results saved to: {output_file}")
            return 0
        else:
            print(f"❌ Analysis failed")
            return 1

    except Exception as e:
        print(f"❌ Critical error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))