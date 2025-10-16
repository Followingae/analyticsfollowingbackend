#!/usr/bin/env python3
"""
Debug Profile Completeness Script

Quick debugging script to analyze specific profiles and understand their completeness status.
Useful for troubleshooting individual profile issues and validating completeness criteria.

Usage:
    python scripts/debug_profile_completeness.py ola.alnomairi
    python scripts/debug_profile_completeness.py --all-incomplete --limit 5
    python scripts/debug_profile_completeness.py --benchmark-comparison ola.alnomairi
"""

import asyncio
import argparse
import logging
import sys
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import get_session, init_database
from app.services.superadmin_analytics_completeness_service import superadmin_analytics_completeness_service
from sqlalchemy import select, text
from app.database.unified_models import Profile, Post

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProfileCompletenessDebugger:
    """Debug profile completeness issues"""

    async def debug_single_profile(self, username: str) -> Dict[str, Any]:
        """Debug a single profile's completeness in detail"""
        try:
            logger.info(f"🔍 Debugging profile completeness for @{username}")

            async with get_session() as db:
                # Get detailed profile analysis
                result = await superadmin_analytics_completeness_service.validate_single_profile(
                    db=db,
                    username=username
                )

                # Get raw database data for comparison
                raw_data = await self._get_raw_profile_data(db, username)

                debug_info = {
                    "username": username,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "completeness_analysis": result["profile_analysis"],
                    "posts_analysis": result["posts_analysis"],
                    "recommendations": result["recommendations"],
                    "raw_database_data": raw_data,
                    "completeness_breakdown": self._analyze_completeness_breakdown(
                        result["profile_analysis"], raw_data
                    )
                }

                self._print_debug_summary(debug_info)
                return debug_info

        except Exception as e:
            logger.error(f"❌ Debug failed for @{username}: {e}")
            raise

    async def _get_raw_profile_data(self, db, username: str) -> Dict[str, Any]:
        """Get raw profile data from database"""
        # Get profile data
        profile_query = text("""
            SELECT id, username, full_name, biography, followers_count, posts_count,
                   ai_profile_analyzed_at, ai_content_distribution, ai_language_distribution,
                   ai_content_quality_score, created_at, updated_at
            FROM profiles
            WHERE username = :username
        """)

        profile_result = await db.execute(profile_query, {"username": username})
        profile_row = profile_result.fetchone()

        if not profile_row:
            raise Exception(f"Profile @{username} not found")

        # Get posts data
        posts_query = text("""
            SELECT COUNT(*) as total_posts,
                   COUNT(CASE WHEN ai_analyzed_at IS NOT NULL THEN 1 END) as ai_analyzed_posts,
                   COUNT(CASE WHEN cdn_thumbnail_url IS NOT NULL THEN 1 END) as cdn_processed_posts,
                   COUNT(CASE WHEN ai_content_category IS NOT NULL THEN 1 END) as posts_with_ai_category,
                   COUNT(CASE WHEN ai_sentiment IS NOT NULL THEN 1 END) as posts_with_ai_sentiment,
                   COUNT(CASE WHEN ai_language_code IS NOT NULL THEN 1 END) as posts_with_ai_language,
                   MIN(created_at) as oldest_post,
                   MAX(created_at) as newest_post,
                   AVG(likes_count) as avg_likes,
                   AVG(comments_count) as avg_comments
            FROM posts p
            JOIN profiles pr ON pr.id = p.profile_id
            WHERE pr.username = :username
        """)

        posts_result = await db.execute(posts_query, {"username": username})
        posts_row = posts_result.fetchone()

        return {
            "profile": dict(profile_row._mapping),
            "posts_summary": dict(posts_row._mapping)
        }

    def _analyze_completeness_breakdown(
        self,
        analysis: Dict[str, Any],
        raw_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze completeness breakdown in detail"""
        breakdown = {
            "criteria_analysis": {},
            "missing_components_detail": {},
            "data_quality_issues": []
        }

        profile = raw_data["profile"]
        posts = raw_data["posts_summary"]

        # Analyze each completeness criterion
        criteria = {
            "basic_data": {
                "required": "followers_count > 0, posts_count > 0, biography exists, full_name exists",
                "current": {
                    "followers_count": profile["followers_count"],
                    "posts_count": profile["posts_count"],
                    "has_biography": bool(profile["biography"]),
                    "has_full_name": bool(profile["full_name"])
                },
                "passes": bool(analysis["has_basic_data"])
            },
            "minimum_posts": {
                "required": "At least 12 posts stored in database",
                "current": {
                    "stored_posts": posts["total_posts"]
                },
                "passes": bool(analysis["has_minimum_posts"])
            },
            "ai_analysis": {
                "required": "At least 12 posts with AI analysis (category, sentiment, language)",
                "current": {
                    "ai_analyzed_posts": posts["ai_analyzed_posts"],
                    "posts_with_category": posts["posts_with_ai_category"],
                    "posts_with_sentiment": posts["posts_with_ai_sentiment"],
                    "posts_with_language": posts["posts_with_ai_language"]
                },
                "passes": analysis["ai_analyzed_posts_count"] >= 12
            },
            "profile_ai": {
                "required": "Profile-level AI analysis completed (ai_profile_analyzed_at not null)",
                "current": {
                    "ai_profile_analyzed_at": profile["ai_profile_analyzed_at"]
                },
                "passes": bool(analysis["has_profile_ai_analysis"])
            },
            "cdn_processing": {
                "required": "At least 12 posts with CDN thumbnails",
                "current": {
                    "cdn_processed_posts": posts["cdn_processed_posts"]
                },
                "passes": bool(analysis["has_cdn_thumbnails"])
            },
            "ai_aggregation": {
                "required": "Profile AI aggregation data (content_distribution, language_distribution)",
                "current": {
                    "ai_content_distribution": bool(profile["ai_content_distribution"]),
                    "ai_language_distribution": bool(profile["ai_language_distribution"])
                },
                "passes": bool(analysis["has_ai_aggregation"])
            }
        }

        breakdown["criteria_analysis"] = criteria

        # Identify specific issues for missing components
        for component in analysis["missing_components"]:
            if component == "basic_data":
                issues = []
                if not profile["followers_count"] or profile["followers_count"] <= 0:
                    issues.append("followers_count is 0 or null")
                if not profile["posts_count"] or profile["posts_count"] <= 0:
                    issues.append("posts_count is 0 or null")
                if not profile["biography"]:
                    issues.append("biography is null or empty")
                if not profile["full_name"]:
                    issues.append("full_name is null or empty")

                breakdown["missing_components_detail"]["basic_data"] = issues

            elif component == "minimum_posts":
                breakdown["missing_components_detail"]["minimum_posts"] = [
                    f"Only {posts['total_posts']} posts stored, need at least 12"
                ]

            elif component == "ai_analysis":
                issues = []
                if posts["ai_analyzed_posts"] < 12:
                    issues.append(f"Only {posts['ai_analyzed_posts']} posts have AI analysis, need 12")
                if posts["posts_with_ai_category"] < posts["ai_analyzed_posts"]:
                    issues.append(f"Some posts missing AI category analysis")
                if posts["posts_with_ai_sentiment"] < posts["ai_analyzed_posts"]:
                    issues.append(f"Some posts missing AI sentiment analysis")
                if posts["posts_with_ai_language"] < posts["ai_analyzed_posts"]:
                    issues.append(f"Some posts missing AI language analysis")

                breakdown["missing_components_detail"]["ai_analysis"] = issues

            elif component == "profile_ai":
                breakdown["missing_components_detail"]["profile_ai"] = [
                    "ai_profile_analyzed_at is null - profile AI analysis not completed"
                ]

            elif component == "cdn_processing":
                breakdown["missing_components_detail"]["cdn_processing"] = [
                    f"Only {posts['cdn_processed_posts']} posts have CDN thumbnails, need at least 12"
                ]

            elif component == "ai_aggregation":
                issues = []
                if not profile["ai_content_distribution"]:
                    issues.append("ai_content_distribution is null")
                if not profile["ai_language_distribution"]:
                    issues.append("ai_language_distribution is null")

                breakdown["missing_components_detail"]["ai_aggregation"] = issues

        return breakdown

    def _print_debug_summary(self, debug_info: Dict[str, Any]):
        """Print formatted debug summary"""
        analysis = debug_info["completeness_analysis"]
        breakdown = debug_info["completeness_breakdown"]

        print(f"\n{'='*80}")
        print(f"🔍 PROFILE COMPLETENESS DEBUG: @{debug_info['username']}")
        print(f"{'='*80}")

        print(f"\n📊 OVERVIEW:")
        print(f"   Complete: {'✅ YES' if analysis['is_complete'] else '❌ NO'}")
        print(f"   Completeness Score: {analysis['completeness_score']:.2f}/1.00 ({analysis['completeness_score']*100:.1f}%)")
        print(f"   Followers: {analysis['followers_count']:,}")
        print(f"   Posts Stored: {analysis['stored_posts_count']}")

        if analysis['missing_components']:
            print(f"\n❌ MISSING COMPONENTS ({len(analysis['missing_components'])}):")
            for component in analysis['missing_components']:
                print(f"   • {component}")

        print(f"\n🔧 DETAILED CRITERIA ANALYSIS:")
        for criterion, details in breakdown['criteria_analysis'].items():
            status = "✅ PASS" if details['passes'] else "❌ FAIL"
            print(f"   {criterion:20} {status}")
            print(f"      Required: {details['required']}")

            if not details['passes'] and criterion in breakdown['missing_components_detail']:
                print(f"      Issues:")
                for issue in breakdown['missing_components_detail'][criterion]:
                    print(f"        - {issue}")

        print(f"\n📋 RECOMMENDATIONS:")
        for i, rec in enumerate(debug_info['recommendations'], 1):
            print(f"   {i}. {rec}")

        print(f"\n🕒 TIMESTAMPS:")
        if analysis.get('ai_profile_analyzed_at'):
            print(f"   AI Analysis: {analysis['ai_profile_analyzed_at']}")
        else:
            print(f"   AI Analysis: ❌ Not completed")

        print(f"   Debug Time: {debug_info['timestamp']}")
        print(f"{'='*80}\n")

    async def compare_with_benchmark(self, username: str, benchmark: str = "ola.alnomairi") -> Dict[str, Any]:
        """Compare profile with benchmark profile"""
        try:
            logger.info(f"🔍 Comparing @{username} with benchmark @{benchmark}")

            async with get_session() as db:
                # Get both profiles
                target_result = await superadmin_analytics_completeness_service.validate_single_profile(
                    db=db, username=username
                )

                benchmark_result = await superadmin_analytics_completeness_service.validate_single_profile(
                    db=db, username=benchmark
                )

                comparison = {
                    "target_profile": username,
                    "benchmark_profile": benchmark,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "comparison_analysis": self._generate_comparison_analysis(
                        target_result["profile_analysis"],
                        benchmark_result["profile_analysis"]
                    )
                }

                self._print_comparison_summary(comparison)
                return comparison

        except Exception as e:
            logger.error(f"❌ Comparison failed: {e}")
            raise

    def _generate_comparison_analysis(self, target: Dict[str, Any], benchmark: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed comparison analysis"""
        comparison_fields = [
            ("completeness_score", "Completeness Score"),
            ("followers_count", "Followers Count"),
            ("stored_posts_count", "Stored Posts"),
            ("ai_analyzed_posts_count", "AI Analyzed Posts"),
            ("cdn_processed_posts_count", "CDN Processed Posts"),
            ("has_basic_data", "Has Basic Data"),
            ("has_minimum_posts", "Has Minimum Posts"),
            ("has_profile_ai_analysis", "Has Profile AI"),
            ("has_ai_aggregation", "Has AI Aggregation"),
            ("has_cdn_thumbnails", "Has CDN Thumbnails")
        ]

        analysis = {
            "target_vs_benchmark": {},
            "gaps_to_address": [],
            "target_advantages": []
        }

        for field, label in comparison_fields:
            target_val = target.get(field)
            benchmark_val = benchmark.get(field)

            comparison_item = {
                "target_value": target_val,
                "benchmark_value": benchmark_val,
                "gap": None,
                "status": "equal"
            }

            if isinstance(target_val, (int, float)) and isinstance(benchmark_val, (int, float)):
                gap = target_val - benchmark_val
                comparison_item["gap"] = gap

                if gap < 0:
                    comparison_item["status"] = "below_benchmark"
                    if field in ["completeness_score", "stored_posts_count", "ai_analyzed_posts_count"]:
                        analysis["gaps_to_address"].append({
                            "field": field,
                            "label": label,
                            "gap": gap,
                            "target": target_val,
                            "benchmark": benchmark_val
                        })
                elif gap > 0:
                    comparison_item["status"] = "above_benchmark"
                    analysis["target_advantages"].append({
                        "field": field,
                        "label": label,
                        "advantage": gap
                    })

            elif isinstance(target_val, bool) and isinstance(benchmark_val, bool):
                if target_val and not benchmark_val:
                    comparison_item["status"] = "above_benchmark"
                    analysis["target_advantages"].append({
                        "field": field,
                        "label": label,
                        "advantage": "Has feature that benchmark lacks"
                    })
                elif not target_val and benchmark_val:
                    comparison_item["status"] = "below_benchmark"
                    analysis["gaps_to_address"].append({
                        "field": field,
                        "label": label,
                        "gap": "Missing feature that benchmark has",
                        "target": target_val,
                        "benchmark": benchmark_val
                    })

            analysis["target_vs_benchmark"][field] = comparison_item

        return analysis

    def _print_comparison_summary(self, comparison: Dict[str, Any]):
        """Print formatted comparison summary"""
        analysis = comparison["comparison_analysis"]

        print(f"\n{'='*80}")
        print(f"🔍 BENCHMARK COMPARISON")
        print(f"Target: @{comparison['target_profile']} vs Benchmark: @{comparison['benchmark_profile']}")
        print(f"{'='*80}")

        if analysis["gaps_to_address"]:
            print(f"\n❌ GAPS TO ADDRESS ({len(analysis['gaps_to_address'])}):")
            for gap in analysis["gaps_to_address"]:
                if isinstance(gap.get("gap"), (int, float)):
                    print(f"   • {gap['label']}: {gap['target']} vs {gap['benchmark']} (gap: {gap['gap']})")
                else:
                    print(f"   • {gap['label']}: {gap['gap']}")

        if analysis["target_advantages"]:
            print(f"\n✅ TARGET ADVANTAGES ({len(analysis['target_advantages'])}):")
            for adv in analysis["target_advantages"]:
                print(f"   • {adv['label']}: {adv.get('advantage', 'Better than benchmark')}")

        if not analysis["gaps_to_address"]:
            print(f"\n🎉 PERFECT MATCH: Target profile meets or exceeds benchmark in all areas!")

        print(f"{'='*80}\n")

    async def find_incomplete_profiles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Find and analyze incomplete profiles"""
        try:
            logger.info(f"🔍 Finding {limit} incomplete profiles for analysis...")

            async with get_session() as db:
                result = await superadmin_analytics_completeness_service.scan_all_profiles_completeness(
                    db=db,
                    limit=limit,
                    include_complete=False
                )

            incomplete_profiles = result["incomplete_profiles"]

            print(f"\n{'='*80}")
            print(f"🔍 INCOMPLETE PROFILES ANALYSIS ({len(incomplete_profiles)} found)")
            print(f"{'='*80}")

            for i, profile in enumerate(incomplete_profiles, 1):
                print(f"\n{i}. @{profile['username']}")
                print(f"   Score: {profile['completeness_score']:.2f} ({profile['completeness_score']*100:.1f}%)")
                print(f"   Followers: {profile['followers_count']:,}")
                print(f"   Posts: {profile['stored_posts_count']}")
                print(f"   Missing: {', '.join(profile['missing_components'])}")

            return incomplete_profiles

        except Exception as e:
            logger.error(f"❌ Failed to find incomplete profiles: {e}")
            raise


async def main():
    """Main debug function"""
    parser = argparse.ArgumentParser(description="Debug Profile Completeness")

    parser.add_argument("username", nargs="?", help="Username to debug")
    parser.add_argument("--all-incomplete", action="store_true", help="Show all incomplete profiles")
    parser.add_argument("--benchmark-comparison", type=str, help="Compare with benchmark profile")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of profiles to show")

    args = parser.parse_args()

    if not any([args.username, args.all_incomplete, args.benchmark_comparison]):
        parser.print_help()
        return

    debugger = ProfileCompletenessDebugger()

    try:
        await init_database()

        if args.username:
            await debugger.debug_single_profile(args.username)

        if args.benchmark_comparison:
            if not args.username:
                logger.error("❌ --benchmark-comparison requires a username argument")
                return
            await debugger.compare_with_benchmark(args.username, args.benchmark_comparison)

        if args.all_incomplete:
            await debugger.find_incomplete_profiles(args.limit)

    except KeyboardInterrupt:
        logger.info("🛑 Debug interrupted by user")
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())