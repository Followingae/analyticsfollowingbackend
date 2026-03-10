"""
Creator Search Response Builders

Extracted from main.py to enable reuse across:
- Sync fast-path responses (existing profiles served from DB)
- Async job results (new profiles processed by workers)

All builders return the exact same dict structure the frontend expects.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Helper functions (moved from main.py) ──────────────────────────────

def _normalize_demographics(demo_data):
    """Normalize demographics data to proper percentages.

    Handles three cases:
    - Values are decimal fractions (sum < 2): convert to 0-100 range
    - Values are near 100% total (80-120): already percentages, normalize to sum=100
    - Values are raw counts or other: normalize to sum=100
    """
    if not demo_data or not isinstance(demo_data, dict):
        return {}
    try:
        numeric_data = {k: float(v) for k, v in demo_data.items() if isinstance(v, (int, float))}
        if not numeric_data:
            return {}
        total = sum(numeric_data.values())
        if total <= 0:
            return {}
        # Values are decimal fractions (e.g., 0.35, 0.45, 0.20) - convert to percentages
        if total < 2:
            return {k: round(v * 100, 1) for k, v in numeric_data.items()}
        # Values already look like percentages (sum near 100) - normalize to exactly 100
        if 80 <= total <= 120:
            return {k: round((v / total) * 100, 1) for k, v in numeric_data.items()}
        # Raw counts or other - normalize to percentages
        return {k: round((v / total) * 100, 1) for k, v in numeric_data.items()}
    except (TypeError, ValueError):
        return {}


def _format_content_distribution(content_dist):
    """Format content distribution from JSONB to proper percentages"""
    if not content_dist:
        return {}
    if isinstance(content_dist, str):
        try:
            content_dist = json.loads(content_dist)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(content_dist, dict):
        return _normalize_demographics(content_dist)
    return {}


def _format_language_distribution(lang_dist):
    """Format language distribution from JSONB to proper percentages"""
    if not lang_dist:
        return {}
    if isinstance(lang_dist, str):
        try:
            lang_dist = json.loads(lang_dist)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(lang_dist, dict):
        return _normalize_demographics(lang_dist)
    return {}


def _format_ai_insights(profile):
    """Format AI insights from JSONB fields into structured data"""
    def safe_get_jsonb(field_value):
        if field_value is None:
            return {}
        if isinstance(field_value, dict):
            return field_value
        if isinstance(field_value, str):
            try:
                return json.loads(field_value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    audience_insights = safe_get_jsonb(profile.ai_audience_insights)
    visual_content = safe_get_jsonb(profile.ai_visual_content)
    behavioral_patterns = safe_get_jsonb(profile.ai_behavioral_patterns)
    fraud_detection = safe_get_jsonb(profile.ai_fraud_detection)
    audience_quality = safe_get_jsonb(profile.ai_audience_quality)
    trend_detection = safe_get_jsonb(profile.ai_trend_detection)
    advanced_nlp = safe_get_jsonb(profile.ai_advanced_nlp)

    return {
        "audience": {
            "demographics": {
                "countries": _normalize_demographics(
                    audience_insights.get('geographic_analysis', {}).get('country_distribution', {})
                ),
                "age_groups": _normalize_demographics(
                    audience_insights.get('demographic_insights', {}).get('estimated_age_groups', {})
                ),
                "gender_split": _normalize_demographics(
                    audience_insights.get('demographic_insights', {}).get('estimated_gender_split', {})
                )
            },
            "quality": {
                "authenticity_score": audience_quality.get('authenticity_score'),
                "bot_detection_score": audience_quality.get('bot_detection_score'),
                "fake_follower_percentage": audience_quality.get('fake_follower_percentage'),
                "engagement_authenticity": audience_quality.get('engagement_authenticity'),
                "quality_indicators": audience_quality.get('quality_indicators', {})
            },
            "geographic_insights": {
                "primary_regions": audience_insights.get('geographic_analysis', {}).get('primary_regions', []),
                "international_reach": audience_insights.get('geographic_analysis', {}).get('international_reach'),
                "geographic_diversity_score": audience_insights.get('geographic_analysis', {}).get('geographic_diversity_score')
            },
            "cultural_analysis": {
                "social_context": audience_insights.get('cultural_analysis', {}).get('social_context'),
                "language_indicators": audience_insights.get('cultural_analysis', {}).get('language_indicators', {})
            }
        },
        "content": {
            "visual_analysis": {
                "brands_detected": visual_content.get('brands_detected', []),
                "scene_distribution": visual_content.get('scene_distribution', {}),
                "content_types": visual_content.get('content_types', {}),
                "visual_consistency": visual_content.get('visual_consistency'),
                "production_quality": visual_content.get('production_quality'),
                "professional_score": visual_content.get('professional_score'),
                "analysis_method": visual_content.get('visual_analysis', {}).get('analysis_method'),
                "aesthetic_score": visual_content.get('aesthetic_score'),
                "professional_quality_score": visual_content.get('professional_quality_score'),
                "image_quality_metrics": {
                    "average_quality": visual_content.get('image_quality_metrics', {}).get('average_quality'),
                    "quality_consistency": visual_content.get('image_quality_metrics', {}).get('quality_consistency')
                },
                "face_analysis": {
                    "faces_detected": visual_content.get('face_analysis', {}).get('faces_detected'),
                    "unique_faces": visual_content.get('face_analysis', {}).get('unique_faces')
                }
            },
            "nlp_insights": {
                "vocabulary_richness": advanced_nlp.get('text_analysis', {}).get('vocabulary_richness'),
                "text_complexity_score": advanced_nlp.get('text_analysis', {}).get('text_complexity_score'),
                "readability_scores": advanced_nlp.get('text_analysis', {}).get('readability_scores', {}),
                "main_themes": advanced_nlp.get('topic_modeling', {}).get('main_themes', []),
                "top_keywords": [kw.get('keyword') for kw in advanced_nlp.get('topic_modeling', {}).get('top_keywords', [])[:10] if isinstance(kw, dict) and kw.get('keyword')]
            }
        },
        "engagement": {
            "behavioral_patterns": {
                "posting_consistency": behavioral_patterns.get('posting_consistency'),
                "engagement_optimization": behavioral_patterns.get('engagement_optimization'),
                "content_strategy_maturity": behavioral_patterns.get('content_strategy_maturity'),
                "current_stage": behavioral_patterns.get('lifecycle_analysis', {}).get('current_stage')
            },
            "trend_analysis": {
                "viral_potential": trend_detection.get('viral_potential', {}).get('overall_viral_score'),
                "optimization_recommendations": trend_detection.get('optimization_recommendations', {}).get('recommendations', [])
            }
        },
        "security": {
            "fraud_detection": {
                "overall_fraud_score": fraud_detection.get('fraud_assessment', {}).get('overall_fraud_score'),
                "risk_level": fraud_detection.get('fraud_assessment', {}).get('risk_level'),
                "authenticity_score": fraud_detection.get('fraud_assessment', {}).get('authenticity_score'),
                "bot_likelihood_percentage": fraud_detection.get('fraud_assessment', {}).get('bot_likelihood_percentage'),
                "trust_score": fraud_detection.get('recommendations', {}).get('trust_score')
            }
        }
    }


# ── Post data builder (shared across all paths) ────────────────────────

def build_post_data_basic(post, cdn_url: Optional[str] = None) -> Dict[str, Any]:
    """Build post dict with basic AI fields (used by complete-profile & new-profile paths)"""
    return {
        "id": post.instagram_post_id,
        "shortcode": post.shortcode,
        "caption": post.caption,
        "likes_count": post.likes_count,
        "comments_count": post.comments_count,
        "engagement_rate": post.engagement_rate,
        "display_url": cdn_url or post.display_url,
        "cdn_thumbnail_url": cdn_url,
        "taken_at": datetime.fromtimestamp(post.taken_at_timestamp, tz=timezone.utc).isoformat() if post.taken_at_timestamp else None,
        "ai_analysis": {
            "content_category": post.ai_content_category,
            "category_confidence": post.ai_category_confidence,
            "sentiment": post.ai_sentiment,
            "sentiment_score": post.ai_sentiment_score,
            "sentiment_confidence": post.ai_sentiment_confidence,
            "language_code": post.ai_language_code,
            "language_confidence": post.ai_language_confidence,
            "analyzed_at": post.ai_analyzed_at.isoformat() if post.ai_analyzed_at else None
        }
    }


def build_post_data_full(post, cdn_url: Optional[str] = None) -> Dict[str, Any]:
    """Build post dict with ALL AI fields including raw analysis (used by unlocked fast path)"""
    base = build_post_data_basic(post, cdn_url)
    # Extend ai_analysis with advanced model data
    base["ai_analysis"].update({
        "full_analysis": post.ai_analysis_raw.get("category", {}) if post.ai_analysis_raw else {},
        "visual_analysis": post.ai_analysis_raw.get("advanced_models", {}).get("visual_content", {}) if post.ai_analysis_raw else {},
        "text_analysis": post.ai_analysis_raw.get("advanced_models", {}).get("advanced_nlp", {}) if post.ai_analysis_raw else {},
        "engagement_prediction": post.ai_analysis_raw.get("advanced_models", {}).get("advanced_nlp", {}).get("engagement_prediction", {}) if post.ai_analysis_raw else {},
        "brand_safety": post.ai_analysis_raw.get("advanced_models", {}).get("fraud_detection", {}) if post.ai_analysis_raw else {},
        "hashtag_analysis": post.ai_analysis_raw.get("advanced_models", {}).get("advanced_nlp", {}).get("entity_extraction", {}) if post.ai_analysis_raw else {},
        "entity_extraction": post.ai_analysis_raw.get("advanced_models", {}).get("advanced_nlp", {}).get("entity_extraction", {}) if post.ai_analysis_raw else {},
        "topic_modeling": post.ai_analysis_raw.get("advanced_models", {}).get("advanced_nlp", {}).get("topic_modeling", {}) if post.ai_analysis_raw else {},
        "data_size_chars": len(str(post.ai_analysis_raw)) if post.ai_analysis_raw else 0
    })
    base["ai_analysis_raw"] = post.ai_analysis_raw if post.ai_analysis_raw else None
    return base


# ── Profile-level fields (shared across full-data paths) ───────────────

def _build_profile_base(profile, cdn_avatar_url: Optional[str] = None) -> Dict[str, Any]:
    """Core profile fields shared by all full-data response paths"""
    return {
        "id": str(profile.id),
        "username": profile.username,
        "full_name": profile.full_name,
        "biography": profile.biography,
        "followers_count": profile.followers_count,
        "following_count": profile.following_count,
        "posts_count": profile.posts_count,
        "is_verified": profile.is_verified,
        "is_private": profile.is_private,
        "is_business_account": profile.is_business_account,
        "profile_pic_url": profile.profile_pic_url or "",
        "profile_pic_url_hd": profile.profile_pic_url_hd or "",
        "cdn_avatar_url": cdn_avatar_url,
        "external_url": profile.external_url,
        "business_category_name": profile.category or profile.instagram_business_category,
        "business_email": getattr(profile, 'business_email', None),
        "business_phone_number": getattr(profile, 'business_phone_number', None),
        "engagement_rate": profile.engagement_rate,
        "detected_country": profile.detected_country,
    }


def _build_ai_analysis_section(profile) -> Dict[str, Any]:
    """AI analysis section shared by all full-data response paths"""
    return {
        "primary_content_type": profile.ai_primary_content_type,
        "content_distribution": _format_content_distribution(getattr(profile, 'ai_content_distribution', {})),
        "avg_sentiment_score": profile.ai_avg_sentiment_score,
        "language_distribution": _format_language_distribution(getattr(profile, 'ai_language_distribution', {})),
        "content_quality_score": profile.ai_content_quality_score,
        "profile_analyzed_at": profile.ai_profile_analyzed_at.isoformat() if profile.ai_profile_analyzed_at else None,
        "comprehensive_analyzed_at": getattr(profile, 'ai_comprehensive_analyzed_at', None).isoformat() if getattr(profile, 'ai_comprehensive_analyzed_at', None) else None,
        "models_success_rate": getattr(profile, 'ai_models_success_rate', 0.0)
    }


def _build_analytics_summary(posts_data: List[Dict], profile) -> Dict[str, Any]:
    """Analytics summary section"""
    ai_posts = [p for p in posts_data if p['ai_analysis']['analyzed_at']]
    return {
        "total_posts_analyzed": len(posts_data),
        "posts_with_ai": len(ai_posts),
        "ai_completion_rate": len(ai_posts) / max(len(posts_data), 1) * 100 if posts_data else 0,
        "avg_engagement_rate": profile.engagement_rate,
        "content_categories_found": len(profile.ai_top_10_categories) if profile.ai_top_10_categories else 0
    }


def _compute_post_averages(posts_data: List[Dict]):
    """Compute avg likes/comments from post dicts"""
    count = len(posts_data)
    if count == 0:
        return 0, 0
    total_likes = sum(p.get('likes_count', 0) for p in posts_data)
    total_comments = sum(p.get('comments_count', 0) for p in posts_data)
    return round(total_likes / count, 1), round(total_comments / count, 1)


# ── Public response builders ───────────────────────────────────────────

def build_unlocked_response(
    profile,
    posts,
    posts_cdn_urls: Dict[str, str],
    cdn_avatar_url: Optional[str],
    fast_time: float
) -> Dict[str, Any]:
    """
    Build response for an already-unlocked profile (fast path).
    Returns full data with advanced AI analysis per post.
    """
    try:
        posts_data = [
            build_post_data_full(post, posts_cdn_urls.get(post.instagram_post_id))
            for post in posts
        ]
        avg_likes, avg_comments = _compute_post_averages(posts_data)

        profile_dict = _build_profile_base(profile, cdn_avatar_url)
        profile_dict.update({
            "avg_likes": avg_likes,
            "avg_comments": avg_comments,
            "influence_score": getattr(profile, 'influence_score', None),
            "content_quality_score": getattr(profile, 'content_quality_score', None),
            "follower_growth_rate": getattr(profile, 'follower_growth_rate', None),
            "ai_analysis": _build_ai_analysis_section(profile),
            **_format_ai_insights(profile),
            "posts": posts_data,
            "last_refreshed": profile.last_refreshed.isoformat() if profile.last_refreshed else None,
            "data_quality_score": profile.data_quality_score,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        })

        return {
            "success": True,
            "profile": profile_dict,
            "analytics_summary": _build_analytics_summary(posts_data, profile),
            "background_processing": {"unified_processing": False, "already_complete": True, "fast_path": True},
            "message": f"INSTANT database return for already unlocked profile (completed in {fast_time:.3f}s)",
            "data_source": "database_fast_path",
            "cached": True,
            "unlock_required": False,
            "unlocked": True,
            "preview_mode": False,
            "performance": {
                "fast_path_enabled": True,
                "total_time_seconds": fast_time,
                "optimization": "already_unlocked_instant_return"
            }
        }
    except Exception as e:
        logger.error(f"Error building unlocked response for {getattr(profile, 'username', 'unknown')}: {e}", exc_info=True)
        # Return graceful fallback with basic profile data
        fallback_profile = {
            "username": getattr(profile, 'username', ''),
            "full_name": getattr(profile, 'full_name', ''),
            "followers_count": getattr(profile, 'followers_count', 0),
            "following_count": getattr(profile, 'following_count', 0),
            "posts_count": getattr(profile, 'posts_count', 0),
            "biography": getattr(profile, 'biography', ''),
            "profile_pic_url": getattr(profile, 'profile_pic_url', '') or '',
            "profile_pic_url_hd": getattr(profile, 'profile_pic_url_hd', '') or '',
            "is_verified": getattr(profile, 'is_verified', False),
            "is_private": getattr(profile, 'is_private', False),
            "engagement_rate": getattr(profile, 'engagement_rate', None),
            "ai_analysis": {},
            "audience": {},
            "content": {},
            "engagement": {},
            "security": {},
            "posts": [],
        }
        return {
            "success": True,
            "profile": fallback_profile,
            "analytics_summary": {"total_posts_analyzed": 0, "posts_with_ai": 0, "ai_completion_rate": 0},
            "background_processing": {"unified_processing": False, "already_complete": True, "fast_path": True},
            "message": f"Profile data loaded with limited AI details (completed in {fast_time:.3f}s)",
            "data_source": "database_fast_path",
            "cached": True,
            "unlock_required": False,
            "unlocked": True,
            "preview_mode": False,
            "partial_data": True,
            "performance": {
                "fast_path_enabled": True,
                "total_time_seconds": fast_time,
                "optimization": "already_unlocked_instant_return"
            }
        }


def build_preview_response(profile) -> Dict[str, Any]:
    """
    Build response for a locked profile (preview mode).
    Returns limited profile data with unlock prompt.
    """
    return {
        "success": True,
        "profile": {
            "id": str(profile.id),
            "username": profile.username,
            "full_name": profile.full_name,
            "followers_count": profile.followers_count,
            "following_count": profile.following_count,
            "posts_count": profile.posts_count,
            "biography": profile.biography,
            "profile_pic_url": profile.profile_pic_url or "",
            "profile_pic_url_hd": profile.profile_pic_url_hd or "",
            "is_verified": profile.is_verified,
            "is_private": profile.is_private,
        },
        "unlock_required": True,
        "unlock_cost": 25,
        "preview_mode": True,
        "message": "Profile found! Unlock for full analytics and insights (25 credits)",
        "unlock_endpoint": "/api/v1/discovery/unlock-profile"
    }


def build_complete_response(
    profile,
    posts,
    posts_cdn_urls: Dict[str, str],
    cdn_avatar_url: Optional[str],
) -> Dict[str, Any]:
    """
    Build response for an existing complete profile in DB (new unlock path).
    Returns full data with basic AI analysis per post.
    """
    posts_data = [
        build_post_data_basic(post, posts_cdn_urls.get(post.instagram_post_id))
        for post in posts
    ]
    avg_likes, avg_comments = _compute_post_averages(posts_data)

    profile_dict = _build_profile_base(profile, cdn_avatar_url)
    profile_dict.update({
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "influence_score": getattr(profile, 'influence_score', None),
        "content_quality_score": getattr(profile, 'content_quality_score', None),
        "follower_growth_rate": getattr(profile, 'follower_growth_rate', None),
        "ai_analysis": _build_ai_analysis_section(profile),
        **_format_ai_insights(profile),
        "posts": posts_data,
        "last_refreshed": profile.last_refreshed.isoformat() if profile.last_refreshed else None,
        "data_quality_score": profile.data_quality_score,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    })

    return {
        "success": True,
        "profile": profile_dict,
        "analytics_summary": _build_analytics_summary(posts_data, profile),
        "background_processing": {"unified_processing": False, "already_complete": True, "note": "serving_from_database"},
        "message": "Complete profile data loaded from database",
        "data_source": "database_complete",
        "cached": True
    }


def build_new_profile_response(
    profile,
    posts,
    posts_cdn_urls: Dict[str, str],
    cdn_avatar_url: Optional[str],
    pipeline_results: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Build response for a newly-processed profile (after Apify + CDN + AI pipeline).
    Used both by the sync endpoint (current) and by the worker job result storage.
    Posts are embedded inside profile.posts (same shape as build_unlocked_response).
    """
    posts_data = [
        build_post_data_basic(post, posts_cdn_urls.get(post.instagram_post_id))
        for post in posts
    ]
    avg_likes, avg_comments = _compute_post_averages(posts_data)

    profile_dict = _build_profile_base(profile, cdn_avatar_url)
    profile_dict.update({
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "influence_score": getattr(profile, 'influence_score', None),
        "content_quality_score": getattr(profile, 'content_quality_score', None),
        "follower_growth_rate": getattr(profile, 'follower_growth_rate', None),
        "ai_analysis": _build_ai_analysis_section(profile),
        **_format_ai_insights(profile),
        "posts": posts_data,
        "last_refreshed": profile.last_refreshed.isoformat() if profile.last_refreshed else None,
        "data_quality_score": profile.data_quality_score,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    })

    pr = pipeline_results or {}
    return {
        "success": True,
        "profile": profile_dict,
        "posts_count": len(posts_data),
        "processing_results": {
            "pipeline_completed": pr.get('overall_success', False),
            "cdn_processing": pr.get('results', {}).get('cdn_results', {}),
            "ai_processing": pr.get('results', {}).get('ai_results', {}),
            "processing_stages_completed": ["apify_storage", "cdn_processing", "ai_analysis"]
        },
        "analytics_summary": _build_analytics_summary(posts_data, profile),
        "message": "Profile processed and unlocked successfully! Full analytics access granted.",
        "data_source": "complete_pipeline",
        "cached": False,
        "unlock_required": False,
        "unlocked": True,
        "auto_unlocked": True,
        "preview_mode": False,
    }
