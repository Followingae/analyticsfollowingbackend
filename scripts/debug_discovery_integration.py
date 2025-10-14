#!/usr/bin/env python3
"""
Discovery Integration Debug Script

Debug script for testing the integration between repair and discovery systems.
Helps debug issues and validate the complete pipeline.

Usage:
    python scripts/debug_discovery_integration.py --username=evekellyg
    python scripts/debug_discovery_integration.py --test-pipeline
    python scripts/debug_discovery_integration.py --check-database
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session
from app.database.unified_models import Profile, RelatedProfile, Post
from app.services.profile_completeness_repair_service import profile_completeness_repair_service
from app.services.similar_profiles_discovery_service import similar_profiles_discovery_service
from app.services.background.similar_profiles_processor import similar_profiles_background_processor
from app.services.creator_analytics_trigger_service import creator_analytics_trigger_service
from sqlalchemy import select, func, text, and_


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Reduce noise from other loggers
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)


def print_banner():
    """Print debug banner"""
    print("=" * 80)
    print("🐛 DISCOVERY INTEGRATION DEBUG TOOL")
    print("=" * 80)
    print("Debug tool for testing repair and discovery system integration")
    print()


async def debug_profile_completeness(username: str) -> Dict[str, Any]:
    """Debug profile completeness for specific username"""
    print(f"🔍 Debugging Profile Completeness: @{username}")
    print("-" * 50)

    try:
        async with get_session() as db:
            # Get profile data
            profile_query = select(Profile).where(Profile.username == username)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()

            if not profile:
                print(f"❌ Profile @{username} not found in database")
                return {"exists": False}

            # Get posts count
            posts_count_query = select(func.count(Post.id)).where(Post.profile_id == profile.id)
            posts_count_result = await db.execute(posts_count_query)
            stored_posts = posts_count_result.scalar()

            # Get related profiles count
            related_count_query = select(func.count(RelatedProfile.id)).where(
                RelatedProfile.profile_id == profile.id
            )
            related_count_result = await db.execute(related_count_query)
            related_count = related_count_result.scalar()

            # Analyze completeness
            completeness = {
                "has_followers": bool(profile.followers_count and profile.followers_count > 0),
                "has_posts_count": bool(profile.posts_count and profile.posts_count > 0),
                "has_biography": bool(profile.biography and profile.biography.strip()),
                "has_ai_analysis": bool(profile.ai_profile_analyzed_at),
                "has_stored_posts": stored_posts > 0,
                "stored_posts_count": stored_posts,
                "related_profiles_count": related_count
            }

            is_complete = all([
                completeness["has_followers"],
                completeness["has_posts_count"],
                completeness["has_biography"],
                completeness["has_ai_analysis"],
                completeness["has_stored_posts"]
            ])

            print(f"Profile Details:")
            print(f"   ID: {profile.id}")
            print(f"   Username: @{profile.username}")
            print(f"   Full Name: {profile.full_name or 'N/A'}")
            print(f"   Followers: {profile.followers_count:,}" if profile.followers_count else "   Followers: N/A")
            print(f"   Posts Count: {profile.posts_count or 'N/A'}")
            print(f"   Biography: {'✅' if completeness['has_biography'] else '❌'}")
            print(f"   AI Analysis: {'✅' if completeness['has_ai_analysis'] else '❌'} ({profile.ai_profile_analyzed_at})")
            print(f"   Stored Posts: {stored_posts}")
            print(f"   Related Profiles: {related_count}")
            print(f"   Complete: {'✅' if is_complete else '❌'}")
            print()

            if not is_complete:
                missing = []
                if not completeness["has_followers"]: missing.append("followers_count")
                if not completeness["has_posts_count"]: missing.append("posts_count")
                if not completeness["has_biography"]: missing.append("biography")
                if not completeness["has_ai_analysis"]: missing.append("ai_analysis")
                if not completeness["has_stored_posts"]: missing.append("stored_posts")

                print(f"Missing Components: {', '.join(missing)}")
                print()

            return {
                "exists": True,
                "profile_id": str(profile.id),
                "is_complete": is_complete,
                "completeness": completeness,
                "profile_data": {
                    "username": profile.username,
                    "followers_count": profile.followers_count,
                    "posts_count": profile.posts_count,
                    "has_biography": bool(profile.biography),
                    "ai_analyzed_at": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
                    "stored_posts": stored_posts,
                    "related_profiles": related_count
                }
            }

    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


async def debug_related_profiles(username: str) -> Dict[str, Any]:
    """Debug related profiles for specific username"""
    print(f"🔗 Debugging Related Profiles: @{username}")
    print("-" * 50)

    try:
        async with get_session() as db:
            # Get profile
            profile_query = select(Profile).where(Profile.username == username)
            profile_result = await db.execute(profile_query)
            profile = profile_result.scalar_one_or_none()

            if not profile:
                return {"error": "Profile not found"}

            # Get related profiles
            related_query = select(
                RelatedProfile.related_username,
                RelatedProfile.similarity_score,
                RelatedProfile.relationship_type,
                RelatedProfile.related_followers_count,
                RelatedProfile.created_at
            ).where(
                RelatedProfile.profile_id == profile.id
            ).order_by(RelatedProfile.similarity_score.desc())

            related_result = await db.execute(related_query)
            related_profiles = related_result.fetchall()

            print(f"Related Profiles for @{username}:")
            print(f"   Total: {len(related_profiles)}")
            print()

            if related_profiles:
                print("Top Related Profiles:")
                for i, related in enumerate(related_profiles[:10], 1):
                    print(f"   {i:2d}. @{related.related_username}")
                    print(f"       Similarity: {related.similarity_score or 0:.1f}")
                    print(f"       Followers: {related.related_followers_count:,}" if related.related_followers_count else "       Followers: N/A")
                    print(f"       Type: {related.relationship_type or 'N/A'}")
                    print()

                # Check which are already in profiles table
                related_usernames = [r.related_username for r in related_profiles]
                existing_query = select(Profile.username).where(
                    Profile.username.in_(related_usernames)
                )
                existing_result = await db.execute(existing_query)
                existing_usernames = set(existing_result.scalars().all())

                discovered_count = len(existing_usernames)
                undiscovered_count = len(related_usernames) - discovered_count

                print(f"Discovery Status:")
                print(f"   Already Discovered: {discovered_count}")
                print(f"   Not Yet Discovered: {undiscovered_count}")
                print()

                if undiscovered_count > 0:
                    undiscovered = [u for u in related_usernames if u not in existing_usernames]
                    print("Undiscovered Profiles (first 5):")
                    for i, username in enumerate(undiscovered[:5], 1):
                        print(f"   {i}. @{username}")
                    print()

            return {
                "profile_id": str(profile.id),
                "total_related": len(related_profiles),
                "discovered": len(existing_usernames) if related_profiles else 0,
                "undiscovered": undiscovered_count if related_profiles else 0,
                "related_profiles": [
                    {
                        "username": r.related_username,
                        "similarity_score": r.similarity_score,
                        "followers_count": r.related_followers_count
                    }
                    for r in related_profiles[:10]
                ]
            }

    except Exception as e:
        print(f"❌ Related profiles debug failed: {e}")
        return {"error": str(e)}


async def test_full_pipeline(username: str) -> Dict[str, Any]:
    """Test the full repair and discovery pipeline"""
    print(f"🔄 Testing Full Pipeline: @{username}")
    print("-" * 50)

    results = {
        "username": username,
        "steps": {},
        "success": False
    }

    try:
        async with get_session() as db:
            # Step 1: Check initial completeness
            print("Step 1: Initial Completeness Check...")
            initial_debug = await debug_profile_completeness(username)
            results["steps"]["initial_check"] = initial_debug

            if not initial_debug.get("exists"):
                print(f"❌ Profile @{username} not found")
                return results

            # Step 2: Check related profiles
            print("Step 2: Related Profiles Check...")
            related_debug = await debug_related_profiles(username)
            results["steps"]["related_check"] = related_debug

            # Step 3: Trigger Creator Analytics if incomplete
            if not initial_debug.get("is_complete"):
                print("Step 3: Triggering Creator Analytics (incomplete profile)...")
                profile, metadata = await creator_analytics_trigger_service.trigger_full_creator_analytics(
                    username=username,
                    db=db,
                    force_refresh=True
                )

                results["steps"]["creator_analytics"] = {
                    "triggered": True,
                    "success": profile is not None,
                    "metadata": metadata
                }

                if profile:
                    print(f"✅ Creator Analytics completed")
                else:
                    print(f"❌ Creator Analytics failed")
            else:
                print("Step 3: Profile already complete - skipping Creator Analytics")
                results["steps"]["creator_analytics"] = {"triggered": False, "reason": "already_complete"}

            # Step 4: Re-check completeness
            print("Step 4: Post-Analytics Completeness Check...")
            final_debug = await debug_profile_completeness(username)
            results["steps"]["final_check"] = final_debug

            # Step 5: Test discovery hook
            print("Step 5: Testing Discovery Hook...")
            if final_debug.get("exists") and final_debug.get("profile_data", {}).get("related_profiles", 0) > 0:
                profile_id = final_debug["profile_id"]

                await similar_profiles_discovery_service.hook_creator_analytics_similar_profiles(
                    source_username=username,
                    profile_id=profile_id,
                    db=db
                )

                results["steps"]["discovery_hook"] = {
                    "triggered": True,
                    "related_profiles_count": final_debug["profile_data"]["related_profiles"]
                }
                print(f"✅ Discovery hook triggered")
            else:
                results["steps"]["discovery_hook"] = {"triggered": False, "reason": "no_related_profiles"}
                print("⚠️ No related profiles to discover")

            results["success"] = final_debug.get("is_complete", False)
            print(f"\n🎯 Pipeline Result: {'✅ SUCCESS' if results['success'] else '❌ INCOMPLETE'}")

            return results

    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        results["error"] = str(e)
        return results


async def check_database_status() -> Dict[str, Any]:
    """Check overall database status for discovery"""
    print("📊 Checking Database Status for Discovery")
    print("-" * 50)

    try:
        async with get_session() as db:
            # Profile statistics
            total_profiles_query = select(func.count(Profile.id))
            total_profiles_result = await db.execute(total_profiles_query)
            total_profiles = total_profiles_result.scalar()

            # Complete profiles
            complete_profiles_query = select(func.count(Profile.id)).where(
                and_(
                    Profile.followers_count > 0,
                    Profile.posts_count > 0,
                    Profile.biography.isnot(None),
                    Profile.ai_profile_analyzed_at.isnot(None)
                )
            )
            complete_profiles_result = await db.execute(complete_profiles_query)
            complete_profiles = complete_profiles_result.scalar()

            # Related profiles statistics
            total_related_query = select(func.count(RelatedProfile.id))
            total_related_result = await db.execute(total_related_query)
            total_related = total_related_result.scalar()

            unique_related_query = select(func.count(func.distinct(RelatedProfile.related_username)))
            unique_related_result = await db.execute(unique_related_query)
            unique_related = unique_related_result.scalar()

            # Undiscovered profiles
            undiscovered_query = text("""
                SELECT COUNT(DISTINCT rp.related_username)
                FROM related_profiles rp
                LEFT JOIN profiles p ON p.username = rp.related_username
                WHERE p.username IS NULL
                AND rp.related_username IS NOT NULL
                AND rp.related_username != ''
            """)
            undiscovered_result = await db.execute(undiscovered_query)
            undiscovered_count = undiscovered_result.scalar()

            print(f"Database Overview:")
            print(f"   Total Profiles: {total_profiles}")
            print(f"   Complete Profiles: {complete_profiles}")
            print(f"   Incomplete Profiles: {total_profiles - complete_profiles}")
            print(f"   Completion Rate: {(complete_profiles/total_profiles*100):.1f}%" if total_profiles > 0 else "   Completion Rate: N/A")
            print()

            print(f"Related Profiles Data:")
            print(f"   Total Related Records: {total_related}")
            print(f"   Unique Related Usernames: {unique_related}")
            print(f"   Already Discovered: {unique_related - undiscovered_count}")
            print(f"   Not Yet Discovered: {undiscovered_count}")
            print(f"   Discovery Potential: {undiscovered_count} profiles")
            print()

            discovery_potential = undiscovered_count / unique_related * 100 if unique_related > 0 else 0
            print(f"Discovery Metrics:")
            print(f"   Discovery Potential: {discovery_potential:.1f}%")
            print(f"   Avg Related per Profile: {total_related/total_profiles:.1f}" if total_profiles > 0 else "   Avg Related per Profile: N/A")
            print()

            return {
                "profiles": {
                    "total": total_profiles,
                    "complete": complete_profiles,
                    "incomplete": total_profiles - complete_profiles,
                    "completion_rate": complete_profiles/total_profiles*100 if total_profiles > 0 else 0
                },
                "related_profiles": {
                    "total_records": total_related,
                    "unique_usernames": unique_related,
                    "discovered": unique_related - undiscovered_count,
                    "undiscovered": undiscovered_count,
                    "discovery_potential_percent": discovery_potential
                }
            }

    except Exception as e:
        print(f"❌ Database status check failed: {e}")
        return {"error": str(e)}


def main():
    """Main debug function"""
    parser = argparse.ArgumentParser(
        description="Discovery Integration Debug Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Debug Operations:
  --username=USER       Debug specific username completeness and related profiles
  --test-pipeline=USER  Test full repair and discovery pipeline for username
  --check-database      Check overall database status for discovery
  --all                 Run all checks

Examples:
  # Debug specific profile
  python scripts/debug_discovery_integration.py --username=evekellyg

  # Test full pipeline
  python scripts/debug_discovery_integration.py --test-pipeline=ola.alnomairi

  # Check database status
  python scripts/debug_discovery_integration.py --check-database
        """
    )

    # Debug operations
    parser.add_argument('--username', type=str, metavar='USERNAME',
                       help='Debug specific username completeness and related profiles')
    parser.add_argument('--test-pipeline', type=str, metavar='USERNAME',
                       help='Test full repair and discovery pipeline for username')
    parser.add_argument('--check-database', action='store_true',
                       help='Check overall database status for discovery')
    parser.add_argument('--all', action='store_true',
                       help='Run all checks (requires --username)')

    # Options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')

    args = parser.parse_args()

    # Validate arguments
    if not any([args.username, args.test_pipeline, args.check_database, args.all]):
        parser.error("Must specify at least one debug operation")

    if args.all and not args.username:
        parser.error("--all requires --username to be specified")

    # Setup logging
    setup_logging(args.verbose)

    # Print banner
    print_banner()

    async def run_debug():
        """Run the debug operations"""
        try:
            if args.check_database or args.all:
                await check_database_status()
                print()

            if args.username or args.all:
                username = args.username
                await debug_profile_completeness(username)
                await debug_related_profiles(username)
                print()

            if args.test_pipeline:
                await test_full_pipeline(args.test_pipeline)
                print()

            print("✅ Debug operations completed")

        except Exception as e:
            print(f"❌ Debug failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            raise

    # Run debug
    try:
        asyncio.run(run_debug())
    except KeyboardInterrupt:
        print("\n❌ Debug cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()