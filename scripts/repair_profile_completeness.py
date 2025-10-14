#!/usr/bin/env python3
"""
Profile Completeness Repair CLI Script

Standalone command-line tool for scanning and repairing incomplete profiles
in the analytics database. Can be run independently of the main application.

Usage:
    python scripts/repair_profile_completeness.py --help
    python scripts/repair_profile_completeness.py --scan-only
    python scripts/repair_profile_completeness.py --dry-run --limit=10
    python scripts/repair_profile_completeness.py --repair --username-filter="test"
    python scripts/repair_profile_completeness.py --repair --force
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import get_session
from app.services.profile_completeness_repair_service import profile_completeness_repair_service


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
    logging.getLogger('asyncio').setLevel(logging.WARNING)


def print_banner():
    """Print CLI banner"""
    print("=" * 80)
    print("📊 PROFILE COMPLETENESS REPAIR TOOL")
    print("=" * 80)
    print("Standalone tool for scanning and repairing incomplete Instagram profiles")
    print("in the analytics database.")
    print()


async def scan_only(
    limit: Optional[int] = None,
    username_filter: Optional[str] = None,
    verbose: bool = False
) -> None:
    """Run scan-only operation"""
    print("🔍 SCAN MODE - Checking profile completeness...")
    print()

    try:
        async with get_session() as db:
            statuses = await profile_completeness_repair_service.scan_profile_completeness(
                db=db,
                limit=limit,
                username_filter=username_filter
            )

            incomplete_profiles = [s for s in statuses if not s.is_complete]

            print(f"📊 SCAN RESULTS:")
            print(f"   Total Profiles Checked: {len(statuses)}")
            print(f"   Complete Profiles: {len(statuses) - len(incomplete_profiles)}")
            print(f"   Incomplete Profiles: {len(incomplete_profiles)}")
            print()

            if incomplete_profiles:
                print("❌ INCOMPLETE PROFILES:")
                print("-" * 60)
                for i, profile in enumerate(incomplete_profiles[:20], 1):  # Show first 20
                    print(f"{i:2d}. @{profile.username}")
                    print(f"     Missing: {', '.join(profile.missing_components)}")
                    print(f"     Followers: {profile.followers_count or 'N/A'}")
                    print(f"     Posts: {profile.stored_posts_count}")
                    print(f"     AI Analysis: {'✅' if profile.has_ai_analysis else '❌'}")
                    if verbose:
                        print(f"     Profile ID: {profile.profile_id}")
                    print()

                if len(incomplete_profiles) > 20:
                    print(f"... and {len(incomplete_profiles) - 20} more profiles")
                    print()
            else:
                print("✅ All profiles are complete!")
                print()

    except Exception as e:
        print(f"❌ Scan failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


async def repair_profiles(
    limit: Optional[int] = None,
    username_filter: Optional[str] = None,
    dry_run: bool = False,
    force_repair: bool = False,
    verbose: bool = False
) -> None:
    """Run repair operation"""
    mode = "DRY RUN" if dry_run else "LIVE REPAIR"
    print(f"🔧 {mode} MODE - Repairing incomplete profiles...")

    if not dry_run:
        print("⚠️  WARNING: This will trigger actual profile analytics for incomplete profiles!")
        response = input("Continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Operation cancelled.")
            return

    print()

    try:
        async with get_session() as db:
            result = await profile_completeness_repair_service.run_full_repair_scan(
                db=db,
                limit=limit,
                username_filter=username_filter,
                dry_run=dry_run,
                force_repair=force_repair
            )

            print(f"🎯 REPAIR RESULTS:")
            print(f"   Total Profiles: {result['scan_results']['total_profiles']}")
            print(f"   Complete Profiles: {result['scan_results']['complete_profiles']}")
            print(f"   Incomplete Profiles: {result['scan_results']['incomplete_profiles']}")
            print()

            if result.get('repair_results'):
                repair_data = result['repair_results']
                print(f"   Repair Attempted: {repair_data.repair_attempted}")
                print(f"   Repair Successful: {repair_data.repair_successful}")
                print(f"   Repair Failed: {repair_data.repair_failed}")
                print(f"   Execution Time: {repair_data.execution_time_seconds:.2f}s")
                print()

                if repair_data.failed_profiles:
                    print("❌ FAILED REPAIRS:")
                    print("-" * 60)
                    for failed in repair_data.failed_profiles:
                        print(f"   @{failed['username']}: {failed['error']}")
                    print()

            if result.get('incomplete_profiles_details'):
                print("📋 INCOMPLETE PROFILES DETAILS:")
                print("-" * 60)
                for profile in result['incomplete_profiles_details'][:10]:  # Show first 10
                    print(f"   @{profile['username']}")
                    print(f"      Missing: {', '.join(profile['missing_components'])}")
                    print(f"      Followers: {profile['followers_count'] or 'N/A'}")
                    print(f"      Stored Posts: {profile['stored_posts_count']}")
                print()

    except Exception as e:
        print(f"❌ Repair failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Profile Completeness Repair Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan all profiles for completeness
  python scripts/repair_profile_completeness.py --scan-only

  # Scan with limit and filter
  python scripts/repair_profile_completeness.py --scan-only --limit=50 --username-filter="test"

  # Dry run repair (simulation)
  python scripts/repair_profile_completeness.py --dry-run --limit=10

  # Live repair with filter
  python scripts/repair_profile_completeness.py --repair --username-filter="evekellyg"

  # Force repair all profiles (including seemingly complete ones)
  python scripts/repair_profile_completeness.py --repair --force --limit=5
        """
    )

    # Operation mode
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan for incomplete profiles, do not repair')
    parser.add_argument('--repair', action='store_true',
                       help='Repair incomplete profiles')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulate repair without actually executing')

    # Filters and limits
    parser.add_argument('--limit', type=int, metavar='N',
                       help='Limit number of profiles to process')
    parser.add_argument('--username-filter', type=str, metavar='PATTERN',
                       help='Filter profiles by username pattern (SQL LIKE)')

    # Options
    parser.add_argument('--force', action='store_true',
                       help='Force repair even for seemingly complete profiles')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')

    args = parser.parse_args()

    # Validate arguments
    if not args.scan_only and not args.repair and not args.dry_run:
        parser.error("Must specify one of: --scan-only, --repair, or --dry-run")

    if args.scan_only and args.repair:
        parser.error("Cannot use --scan-only with --repair")

    if args.scan_only and args.dry_run:
        parser.error("Cannot use --scan-only with --dry-run")

    # Setup logging
    setup_logging(args.verbose)

    # Print banner
    print_banner()

    # Print configuration
    print(f"Configuration:")
    print(f"   Mode: {'Scan Only' if args.scan_only else 'Repair' if args.repair else 'Dry Run'}")
    print(f"   Limit: {args.limit or 'No limit'}")
    print(f"   Username Filter: {args.username_filter or 'None'}")
    print(f"   Force Repair: {args.force}")
    print(f"   Verbose: {args.verbose}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Run operation
    try:
        if args.scan_only:
            asyncio.run(scan_only(
                limit=args.limit,
                username_filter=args.username_filter,
                verbose=args.verbose
            ))
        else:
            asyncio.run(repair_profiles(
                limit=args.limit,
                username_filter=args.username_filter,
                dry_run=args.dry_run,
                force_repair=args.force,
                verbose=args.verbose
            ))

        print("✅ Operation completed successfully!")

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Operation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()