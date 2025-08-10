"""
AI Data Consistency Service - Mission Critical for Data Integrity
Detects, validates, and repairs partial AI analysis data
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from contextlib import asynccontextmanager

from app.database.connection import get_db
from app.database.unified_models import Profile, Post, AIAnalysisJob, AIAnalysisJobLog
# Background task manager removed - using direct analysis now

logger = logging.getLogger(__name__)

class AIDataConsistencyService:
    """
    Mission Critical: Ensures AI analysis data integrity across the platform
    
    Key Functions:
    - Detect partial AI analysis states
    - Validate data consistency 
    - Repair incomplete analysis data
    - Monitor analysis health
    - Generate integrity reports
    """
    
    def __init__(self):
        self.consistency_checks = {
            'partial_post_analysis': self._check_partial_post_analysis,
            'missing_profile_aggregation': self._check_missing_profile_aggregation,
            'inconsistent_analysis_dates': self._check_inconsistent_analysis_dates,
            'orphaned_ai_data': self._check_orphaned_ai_data,
            'failed_jobs_with_data': self._check_failed_jobs_with_data
        }
    
    async def run_comprehensive_consistency_check(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Run all consistency checks and return comprehensive report
        CRITICAL: This identifies all partial data states
        """
        logger.info("Starting comprehensive AI data consistency check")
        
        report = {
            "check_timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "issues_found": [],
            "profiles_affected": [],
            "repair_recommendations": [],
            "statistics": {}
        }
        
        total_issues = 0
        
        try:
            # Run all consistency checks
            for check_name, check_function in self.consistency_checks.items():
                logger.info(f"Running consistency check: {check_name}")
                
                check_result = await check_function(db)
                
                if check_result['issues_count'] > 0:
                    total_issues += check_result['issues_count']
                    report['issues_found'].append({
                        "check_type": check_name,
                        "severity": check_result.get('severity', 'medium'),
                        "issues_count": check_result['issues_count'],
                        "description": check_result['description'],
                        "affected_profiles": check_result.get('affected_profiles', []),
                        "repair_action": check_result.get('repair_action')
                    })
                    
                    # Collect unique affected profiles
                    for profile_id in check_result.get('affected_profiles', []):
                        if profile_id not in report['profiles_affected']:
                            report['profiles_affected'].append(profile_id)
            
            # Generate repair recommendations
            if total_issues > 0:
                report['overall_status'] = "issues_detected"
                report['repair_recommendations'] = await self._generate_repair_recommendations(
                    db, report['issues_found']
                )
            
            # Add statistics
            report['statistics'] = await self._generate_consistency_statistics(db)
            
            logger.info(f"Consistency check completed: {total_issues} issues found affecting {len(report['profiles_affected'])} profiles")
            
            return report
            
        except Exception as e:
            logger.error(f"Comprehensive consistency check failed: {e}")
            report['overall_status'] = "check_failed"
            report['error'] = str(e)
            return report
    
    async def _check_partial_post_analysis(self, db: AsyncSession) -> Dict[str, Any]:
        """
        CRITICAL CHECK: Detect profiles with posts that have partial AI analysis
        This identifies the exact bug we experienced with veraciocca
        """
        
        # Find profiles where some posts have AI data but others don't
        query = text("""
            SELECT 
                p.id as profile_id,
                p.username,
                COUNT(posts.id) as total_posts,
                COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as posts_with_ai,
                COUNT(CASE WHEN posts.ai_analyzed_at IS NULL THEN 1 END) as posts_without_ai
            FROM profiles p
            LEFT JOIN posts ON posts.profile_id = p.id
            WHERE posts.id IS NOT NULL
            GROUP BY p.id, p.username
            HAVING 
                COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) > 0
                AND COUNT(CASE WHEN posts.ai_analyzed_at IS NULL THEN 1 END) > 0
            ORDER BY posts_without_ai DESC
        """)
        
        result = await db.execute(query)
        partial_profiles = result.fetchall()
        
        affected_profiles = []
        for row in partial_profiles:
            affected_profiles.append({
                'profile_id': str(row.profile_id),
                'username': row.username,
                'total_posts': row.total_posts,
                'posts_with_ai': row.posts_with_ai,
                'posts_without_ai': row.posts_without_ai,
                'completion_percentage': round((row.posts_with_ai / row.total_posts) * 100, 1)
            })
        
        return {
            'issues_count': len(partial_profiles),
            'severity': 'high',
            'description': 'Profiles with partial post AI analysis detected',
            'affected_profiles': [p['profile_id'] for p in affected_profiles],
            'detailed_findings': affected_profiles,
            'repair_action': 'run_repair_analysis'
        }
    
    async def _check_missing_profile_aggregation(self, db: AsyncSession) -> Dict[str, Any]:
        """
        CRITICAL CHECK: Detect profiles where posts have AI data but profile aggregation is missing
        This is the exact failure mode from the veraciocca incident
        """
        
        query = text("""
            SELECT 
                p.id as profile_id,
                p.username,
                p.ai_profile_analyzed_at,
                COUNT(posts.id) as total_posts,
                COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as posts_with_ai
            FROM profiles p
            LEFT JOIN posts ON posts.profile_id = p.id
            WHERE posts.id IS NOT NULL
            GROUP BY p.id, p.username, p.ai_profile_analyzed_at
            HAVING 
                COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) > 0
                AND p.ai_profile_analyzed_at IS NULL
            ORDER BY posts_with_ai DESC
        """)
        
        result = await db.execute(query)
        missing_aggregation = result.fetchall()
        
        affected_profiles = []
        for row in missing_aggregation:
            affected_profiles.append({
                'profile_id': str(row.profile_id),
                'username': row.username,
                'total_posts': row.total_posts,
                'posts_with_ai': row.posts_with_ai,
                'has_posts_analysis': True,
                'has_profile_aggregation': False
            })
        
        return {
            'issues_count': len(missing_aggregation),
            'severity': 'critical',
            'description': 'Profiles with posts analysis but missing profile aggregation (veraciocca-type bug)',
            'affected_profiles': [p['profile_id'] for p in affected_profiles],
            'detailed_findings': affected_profiles,
            'repair_action': 'regenerate_profile_aggregation'
        }
    
    async def _check_inconsistent_analysis_dates(self, db: AsyncSession) -> Dict[str, Any]:
        """Check for profiles where post analysis dates are newer than profile analysis dates"""
        
        query = text("""
            SELECT 
                p.id as profile_id,
                p.username,
                p.ai_profile_analyzed_at as profile_date,
                MAX(posts.ai_analyzed_at) as latest_post_date,
                COUNT(CASE WHEN posts.ai_analyzed_at > p.ai_profile_analyzed_at THEN 1 END) as newer_posts
            FROM profiles p
            LEFT JOIN posts ON posts.profile_id = p.id
            WHERE p.ai_profile_analyzed_at IS NOT NULL
              AND posts.ai_analyzed_at IS NOT NULL
            GROUP BY p.id, p.username, p.ai_profile_analyzed_at
            HAVING COUNT(CASE WHEN posts.ai_analyzed_at > p.ai_profile_analyzed_at THEN 1 END) > 0
            ORDER BY newer_posts DESC
        """)
        
        result = await db.execute(query)
        inconsistent_dates = result.fetchall()
        
        affected_profiles = []
        for row in inconsistent_dates:
            affected_profiles.append({
                'profile_id': str(row.profile_id),
                'username': row.username,
                'profile_analysis_date': row.profile_date.isoformat() if row.profile_date else None,
                'latest_post_analysis_date': row.latest_post_date.isoformat() if row.latest_post_date else None,
                'newer_posts_count': row.newer_posts
            })
        
        return {
            'issues_count': len(inconsistent_dates),
            'severity': 'medium',
            'description': 'Profiles with inconsistent analysis timestamps',
            'affected_profiles': [p['profile_id'] for p in affected_profiles],
            'detailed_findings': affected_profiles,
            'repair_action': 'update_analysis_timestamps'
        }
    
    async def _check_orphaned_ai_data(self, db: AsyncSession) -> Dict[str, Any]:
        """Check for AI analysis data without corresponding profiles/posts"""
        
        # Check for posts with AI data but no profile
        orphaned_posts = await db.execute(
            select(func.count(Post.id)).where(
                and_(
                    Post.ai_analyzed_at.isnot(None),
                    Post.profile_id.is_(None)
                )
            )
        )
        orphaned_posts_count = orphaned_posts.scalar()
        
        return {
            'issues_count': orphaned_posts_count,
            'severity': 'low',
            'description': 'Posts with AI data but no associated profile',
            'affected_profiles': [],
            'repair_action': 'cleanup_orphaned_data'
        }
    
    async def _check_failed_jobs_with_data(self, db: AsyncSession) -> Dict[str, Any]:
        """Check for failed jobs that actually produced partial data"""
        
        query = text("""
            SELECT 
                j.id as job_id,
                j.job_id as job_name,
                j.profile_id,
                p.username,
                j.status,
                j.posts_successful,
                j.total_posts,
                COUNT(posts.id) as actual_posts_with_ai
            FROM ai_analysis_jobs j
            LEFT JOIN profiles p ON p.id = j.profile_id
            LEFT JOIN posts ON posts.profile_id = j.profile_id AND posts.ai_analyzed_at IS NOT NULL
            WHERE j.status IN ('failed', 'repair_needed')
              AND j.posts_successful > 0
            GROUP BY j.id, j.job_id, j.profile_id, p.username, j.status, j.posts_successful, j.total_posts
            HAVING COUNT(posts.id) > 0
            ORDER BY actual_posts_with_ai DESC
        """)
        
        result = await db.execute(query)
        failed_jobs_with_data = result.fetchall()
        
        affected_profiles = []
        for row in failed_jobs_with_data:
            affected_profiles.append({
                'profile_id': str(row.profile_id),
                'username': row.username,
                'job_id': row.job_name,
                'job_status': row.status,
                'reported_success_count': row.posts_successful,
                'actual_ai_posts': row.actual_posts_with_ai
            })
        
        return {
            'issues_count': len(failed_jobs_with_data),
            'severity': 'medium',
            'description': 'Failed jobs that actually produced partial AI data',
            'affected_profiles': [p['profile_id'] for p in affected_profiles],
            'detailed_findings': affected_profiles,
            'repair_action': 'complete_failed_jobs'
        }
    
    async def _generate_repair_recommendations(
        self, 
        db: AsyncSession, 
        issues_found: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate specific repair recommendations based on issues found"""
        
        recommendations = []
        
        for issue in issues_found:
            if issue['check_type'] == 'missing_profile_aggregation':
                recommendations.append({
                    "priority": "critical",
                    "action": "regenerate_profile_aggregation",
                    "description": "Regenerate profile-level AI insights from existing post data",
                    "affected_profiles": len(issue['affected_profiles']),
                    "estimated_time": "5-10 minutes",
                    "risk_level": "low"
                })
            
            elif issue['check_type'] == 'partial_post_analysis':
                recommendations.append({
                    "priority": "high", 
                    "action": "complete_post_analysis",
                    "description": "Complete AI analysis for remaining posts",
                    "affected_profiles": len(issue['affected_profiles']),
                    "estimated_time": "10-30 minutes",
                    "risk_level": "low"
                })
            
            elif issue['check_type'] == 'failed_jobs_with_data':
                recommendations.append({
                    "priority": "medium",
                    "action": "repair_failed_jobs", 
                    "description": "Clean up and retry failed jobs with partial data",
                    "affected_profiles": len(issue['affected_profiles']),
                    "estimated_time": "5-15 minutes",
                    "risk_level": "medium"
                })
        
        return recommendations
    
    async def _generate_consistency_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """Generate overall AI analysis statistics"""
        
        try:
            # Profile statistics
            total_profiles = await db.execute(select(func.count(Profile.id)))
            total_profiles_count = total_profiles.scalar()
            
            profiles_with_posts = await db.execute(
                select(func.count(Profile.id.distinct())).select_from(Profile).join(Post)
            )
            profiles_with_posts_count = profiles_with_posts.scalar()
            
            profiles_with_ai = await db.execute(
                select(func.count(Profile.id)).where(Profile.ai_profile_analyzed_at.isnot(None))
            )
            profiles_with_ai_count = profiles_with_ai.scalar()
        
            # Post statistics  
            total_posts = await db.execute(select(func.count(Post.id)))
            total_posts_count = total_posts.scalar()
            
            posts_with_ai = await db.execute(
                select(func.count(Post.id)).where(Post.ai_analyzed_at.isnot(None))
            )
            posts_with_ai_count = posts_with_ai.scalar()
            
            # Job statistics
            total_jobs = await db.execute(select(func.count(AIAnalysisJob.id)))
            total_jobs_count = total_jobs.scalar()
            
            successful_jobs = await db.execute(
                select(func.count(AIAnalysisJob.id)).where(AIAnalysisJob.status == 'completed')
            )
            successful_jobs_count = successful_jobs.scalar()
            
            failed_jobs = await db.execute(
                select(func.count(AIAnalysisJob.id)).where(AIAnalysisJob.status == 'failed')
            )
            failed_jobs_count = failed_jobs.scalar()
            
            return {
                "profiles": {
                    "total": total_profiles_count,
                    "with_posts": profiles_with_posts_count,
                    "with_ai_analysis": profiles_with_ai_count,
                    "ai_coverage_percentage": round(
                        (profiles_with_ai_count / max(1, profiles_with_posts_count)) * 100, 1
                    )
                },
                "posts": {
                    "total": total_posts_count,
                    "with_ai_analysis": posts_with_ai_count,
                    "ai_coverage_percentage": round(
                        (posts_with_ai_count / max(1, total_posts_count)) * 100, 1
                    )
                },
                "jobs": {
                    "total": total_jobs_count,
                    "successful": successful_jobs_count,
                    "failed": failed_jobs_count,
                    "success_rate_percentage": round(
                        (successful_jobs_count / max(1, total_jobs_count)) * 100, 1
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating consistency statistics: {e}")
            return {
                "error": "Failed to generate statistics",
                "profiles": {"total": 0, "with_posts": 0, "with_ai_analysis": 0, "ai_coverage_percentage": 0},
                "posts": {"total": 0, "with_ai_analysis": 0, "ai_coverage_percentage": 0},
                "jobs": {"total": 0, "successful": 0, "failed": 0, "success_rate_percentage": 0}
            }
    
    async def repair_missing_profile_aggregation(
        self, 
        db: AsyncSession, 
        profile_ids: List[str]
    ) -> Dict[str, Any]:
        """
        CRITICAL REPAIR: Fix profiles missing aggregation (veraciocca-type bug)
        Regenerate profile-level insights from existing post AI data
        """
        
        logger.info(f"Starting profile aggregation repair for {len(profile_ids)} profiles")
        
        repair_results = {
            "profiles_processed": 0,
            "profiles_repaired": 0,
            "profiles_failed": 0,
            "repair_details": []
        }
        
        for profile_id in profile_ids:
            try:
                # Get profile
                profile_result = await db.execute(
                    select(Profile).where(Profile.id == profile_id)
                )
                profile = profile_result.scalar_one_or_none()
                
                if not profile:
                    continue
                
                # Get posts with AI data
                posts_result = await db.execute(
                    select(Post).where(
                        and_(
                            Post.profile_id == profile_id,
                            Post.ai_analyzed_at.isnot(None)
                        )
                    )
                )
                posts = posts_result.scalars().all()
                
                if not posts:
                    repair_results['repair_details'].append({
                        'profile_id': profile_id,
                        'username': profile.username,
                        'status': 'skipped',
                        'reason': 'no_posts_with_ai'
                    })
                    continue
                
                # Aggregate data from posts
                category_distribution = {}
                sentiment_scores = []
                language_counts = {}
                
                for post in posts:
                    if post.ai_content_category:
                        category_distribution[post.ai_content_category] = category_distribution.get(
                            post.ai_content_category, 0
                        ) + 1
                    
                    if post.ai_sentiment_score is not None:
                        sentiment_scores.append(post.ai_sentiment_score)
                    
                    if post.ai_language_code:
                        language_counts[post.ai_language_code] = language_counts.get(
                            post.ai_language_code, 0
                        ) + 1
                
                # Calculate profile insights
                profile_insights = self._calculate_profile_insights(
                    category_distribution, sentiment_scores, language_counts, len(posts)
                )
                
                # Update profile
                await db.execute(
                    update(Profile)
                    .where(Profile.id == profile_id)
                    .values(
                        ai_primary_content_type=profile_insights.get("ai_primary_content_type"),
                        ai_content_distribution=profile_insights.get("ai_content_distribution"),
                        ai_avg_sentiment_score=profile_insights.get("ai_avg_sentiment_score"),
                        ai_language_distribution=profile_insights.get("ai_language_distribution"),
                        ai_content_quality_score=profile_insights.get("ai_content_quality_score"),
                        ai_profile_analyzed_at=datetime.now(timezone.utc)
                    )
                )
                
                await db.commit()
                
                repair_results['profiles_repaired'] += 1
                repair_results['repair_details'].append({
                    'profile_id': profile_id,
                    'username': profile.username,
                    'status': 'repaired',
                    'posts_analyzed': len(posts),
                    'primary_category': profile_insights.get("ai_primary_content_type"),
                    'avg_sentiment': profile_insights.get("ai_avg_sentiment_score")
                })
                
                logger.info(f"Repaired profile aggregation for {profile.username}: {len(posts)} posts processed")
                
            except Exception as e:
                repair_results['profiles_failed'] += 1
                repair_results['repair_details'].append({
                    'profile_id': profile_id,
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"Failed to repair profile {profile_id}: {e}")
            
            finally:
                repair_results['profiles_processed'] += 1
        
        logger.info(f"Profile aggregation repair completed: {repair_results['profiles_repaired']}/{repair_results['profiles_processed']} successful")
        
        return repair_results
    
    def _calculate_profile_insights(
        self, 
        category_distribution: Dict[str, int], 
        sentiment_scores: List[float], 
        language_counts: Dict[str, int],
        total_posts: int
    ) -> Dict[str, Any]:
        """Calculate aggregated profile insights from post analyses (shared logic)"""
        
        # Primary content type (most common category)
        primary_content_type = None
        if category_distribution:
            primary_content_type = max(category_distribution, key=category_distribution.get)
        
        # Content distribution (normalized)
        content_distribution = {}
        if category_distribution:
            for category, count in category_distribution.items():
                content_distribution[category] = round(count / total_posts, 2)
        
        # Average sentiment score
        avg_sentiment = 0.0
        if sentiment_scores:
            avg_sentiment = round(sum(sentiment_scores) / len(sentiment_scores), 3)
        
        # Language distribution (normalized) 
        language_distribution = {}
        if language_counts:
            for language, count in language_counts.items():
                language_distribution[language] = round(count / total_posts, 2)
        
        # Content quality score
        content_quality_score = self._calculate_content_quality_score(
            content_distribution, avg_sentiment, len(sentiment_scores), total_posts
        )
        
        return {
            "ai_primary_content_type": primary_content_type,
            "ai_content_distribution": content_distribution,
            "ai_avg_sentiment_score": avg_sentiment,
            "ai_language_distribution": language_distribution,
            "ai_content_quality_score": content_quality_score
        }
    
    def _calculate_content_quality_score(
        self, 
        content_distribution: Dict[str, float], 
        avg_sentiment: float,
        analyzed_posts: int, 
        total_posts: int
    ) -> float:
        """Calculate overall content quality score (shared logic)"""
        
        score = 0.0
        
        # Sentiment contribution (positive sentiment is better)
        sentiment_contribution = max(0, (avg_sentiment + 1) / 2)  # Normalize -1,1 to 0,1
        score += sentiment_contribution * 0.4  # 40% weight
        
        # Content consistency (focused content is better)
        consistency_score = 0.0
        if content_distribution:
            max_category_ratio = max(content_distribution.values())
            consistency_score = max_category_ratio
        score += consistency_score * 0.3  # 30% weight
        
        # Analysis coverage (more analyzed posts is better)
        coverage_score = min(1.0, analyzed_posts / max(1, total_posts))
        score += coverage_score * 0.3  # 30% weight
        
        return round(score, 3)
    
    async def cleanup_partial_ai_data(
        self, 
        db: AsyncSession, 
        profile_ids: List[str],
        cleanup_mode: str = "posts_only"
    ) -> Dict[str, Any]:
        """
        Clean up partial AI data before running fresh analysis
        cleanup_mode: "posts_only", "profile_only", "all"
        """
        
        logger.info(f"Cleaning up partial AI data for {len(profile_ids)} profiles (mode: {cleanup_mode})")
        
        cleanup_results = {
            "profiles_processed": 0,
            "posts_cleaned": 0,
            "profiles_cleaned": 0,
            "cleanup_details": []
        }
        
        for profile_id in profile_ids:
            try:
                posts_cleaned = 0
                profile_cleaned = False
                
                if cleanup_mode in ["posts_only", "all"]:
                    # Clear post AI data
                    posts_result = await db.execute(
                        update(Post)
                        .where(Post.profile_id == profile_id)
                        .values(
                            ai_content_category=None,
                            ai_category_confidence=None,
                            ai_sentiment=None,
                            ai_sentiment_score=None,
                            ai_sentiment_confidence=None,
                            ai_language_code=None,
                            ai_language_confidence=None,
                            ai_analysis_raw=None,
                            ai_analyzed_at=None,
                            ai_analysis_version=None
                        )
                    )
                    posts_cleaned = posts_result.rowcount
                
                if cleanup_mode in ["profile_only", "all"]:
                    # Clear profile AI data
                    await db.execute(
                        update(Profile)
                        .where(Profile.id == profile_id)
                        .values(
                            ai_primary_content_type=None,
                            ai_content_distribution=None,
                            ai_avg_sentiment_score=None,
                            ai_language_distribution=None,
                            ai_content_quality_score=None,
                            ai_profile_analyzed_at=None
                        )
                    )
                    profile_cleaned = True
                
                await db.commit()
                
                cleanup_results['posts_cleaned'] += posts_cleaned
                if profile_cleaned:
                    cleanup_results['profiles_cleaned'] += 1
                
                cleanup_results['cleanup_details'].append({
                    'profile_id': profile_id,
                    'posts_cleaned': posts_cleaned,
                    'profile_cleaned': profile_cleaned,
                    'status': 'success'
                })
                
                logger.info(f"Cleaned AI data for profile {profile_id}: {posts_cleaned} posts, profile: {profile_cleaned}")
                
            except Exception as e:
                cleanup_results['cleanup_details'].append({
                    'profile_id': profile_id,
                    'status': 'failed',
                    'error': str(e)
                })
                logger.error(f"Failed to cleanup AI data for profile {profile_id}: {e}")
            
            finally:
                cleanup_results['profiles_processed'] += 1
        
        logger.info(f"AI data cleanup completed: {cleanup_results['posts_cleaned']} posts, {cleanup_results['profiles_cleaned']} profiles")
        
        return cleanup_results
    
    async def detect_veraciocca_type_bugs(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        SPECIALIZED: Detect the exact bug pattern that happened with veraciocca
        Posts have AI data but profile aggregation is missing
        """
        
        logger.info("Scanning for veraciocca-type AI analysis bugs")
        
        # This is the exact query to find profiles in veraciocca's state
        query = text("""
            SELECT 
                p.id as profile_id,
                p.username,
                p.ai_profile_analyzed_at,
                COUNT(posts.id) as total_posts,
                COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) as posts_with_ai,
                COUNT(CASE WHEN posts.ai_content_category IS NOT NULL THEN 1 END) as posts_with_categories,
                COUNT(CASE WHEN posts.ai_sentiment IS NOT NULL THEN 1 END) as posts_with_sentiment
            FROM profiles p
            LEFT JOIN posts ON posts.profile_id = p.id
            WHERE posts.id IS NOT NULL
            GROUP BY p.id, p.username, p.ai_profile_analyzed_at
            HAVING 
                COUNT(CASE WHEN posts.ai_analyzed_at IS NOT NULL THEN 1 END) > 0
                AND p.ai_profile_analyzed_at IS NULL
            ORDER BY posts_with_ai DESC
        """)
        
        result = await db.execute(query)
        veraciocca_bugs = result.fetchall()
        
        bug_profiles = []
        for row in veraciocca_bugs:
            bug_profiles.append({
                'profile_id': str(row.profile_id),
                'username': row.username,
                'total_posts': row.total_posts,
                'posts_with_ai': row.posts_with_ai,
                'posts_with_categories': row.posts_with_categories,
                'posts_with_sentiment': row.posts_with_sentiment,
                'completion_percentage': round((row.posts_with_ai / row.total_posts) * 100, 1),
                'bug_severity': 'critical' if row.posts_with_ai == row.total_posts else 'high',
                'recommended_action': 'regenerate_profile_aggregation'
            })
        
        if bug_profiles:
            logger.warning(f"Found {len(bug_profiles)} profiles with veraciocca-type bugs")
        else:
            logger.info("No veraciocca-type bugs detected")
        
        return bug_profiles

# Global instance
ai_data_consistency_service = AIDataConsistencyService()