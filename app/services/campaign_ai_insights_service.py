"""
Campaign AI Insights Service - Comprehensive AI Intelligence Aggregation
Aggregates all 10 AI models across campaign posts for intelligent insights
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from collections import Counter, defaultdict

from app.database.unified_models import Campaign, CampaignPost, Post, Profile

logger = logging.getLogger(__name__)


class CampaignAIInsightsService:
    """Service for aggregating AI insights across campaign posts"""

    async def get_campaign_ai_insights(
        self,
        db: AsyncSession,
        campaign_id: UUID,
        user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate AI insights from all posts in a campaign

        Returns comprehensive AI intelligence across 10 models:
        1. Sentiment Analysis
        2. Language Detection
        3. Category Classification
        4. Audience Quality
        5. Visual Content
        6. Audience Insights
        7. Trend Detection
        8. Advanced NLP
        9. Fraud Detection
        10. Behavioral Patterns
        """
        try:
            # 1. Verify campaign ownership
            campaign_query = select(Campaign).where(
                and_(
                    Campaign.id == campaign_id,
                    Campaign.user_id == user_id
                )
            )
            campaign_result = await db.execute(campaign_query)
            campaign = campaign_result.scalar_one_or_none()

            if not campaign:
                logger.warning(f"Campaign {campaign_id} not found for user {user_id}")
                return None

            # 2. Get all posts with AI analysis
            posts_query = (
                select(Post)
                .join(CampaignPost, CampaignPost.post_id == Post.id)
                .where(CampaignPost.campaign_id == campaign_id)
                .where(Post.ai_analyzed_at.isnot(None))  # Only posts with AI analysis
            )
            posts_result = await db.execute(posts_query)
            posts = posts_result.scalars().all()

            if not posts:
                logger.info(f"No AI-analyzed posts found for campaign {campaign_id}")
                return {
                    "total_posts": 0,
                    "ai_analyzed_posts": 0,
                    "message": "No AI analysis data available yet"
                }

            # 3. Aggregate AI insights from all posts
            insights = {
                "total_posts": len(posts),
                "ai_analyzed_posts": len(posts),
                "sentiment_analysis": self._aggregate_sentiment(posts),
                "language_detection": self._aggregate_languages(posts),
                "category_classification": self._aggregate_categories(posts),
                "audience_quality": self._aggregate_audience_quality(posts),
                "visual_content": self._aggregate_visual_content(posts),
                "audience_insights": self._aggregate_audience_insights(posts),
                "trend_detection": self._aggregate_trends(posts),
                "advanced_nlp": self._aggregate_nlp(posts),
                "fraud_detection": self._aggregate_fraud(posts),
                "behavioral_patterns": self._aggregate_behavioral_patterns(posts)
            }

            logger.info(f"✅ Aggregated AI insights for campaign {campaign_id}: {len(posts)} posts")
            return insights

        except Exception as e:
            logger.error(f"❌ Error aggregating AI insights for campaign {campaign_id}: {e}")
            raise

    def _aggregate_sentiment(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate sentiment analysis across posts"""
        sentiments = [p.ai_sentiment for p in posts if p.ai_sentiment]
        scores = [p.ai_sentiment_score for p in posts if p.ai_sentiment_score is not None]

        if not sentiments:
            return {"available": False}

        sentiment_counts = Counter(sentiments)
        total = len(sentiments)

        return {
            "available": True,
            "distribution": {
                "positive": sentiment_counts.get("positive", 0) / total * 100,
                "neutral": sentiment_counts.get("neutral", 0) / total * 100,
                "negative": sentiment_counts.get("negative", 0) / total * 100
            },
            "average_score": sum(scores) / len(scores) if scores else 0,
            "dominant_sentiment": sentiment_counts.most_common(1)[0][0] if sentiment_counts else "unknown"
        }

    def _aggregate_languages(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate language detection across posts"""
        languages = [p.ai_language_code for p in posts if p.ai_language_code]

        if not languages:
            return {"available": False}

        lang_counts = Counter(languages)
        total = len(languages)

        # Get top 5 languages
        top_languages = [
            {"language": lang, "percentage": count / total * 100}
            for lang, count in lang_counts.most_common(5)
        ]

        return {
            "available": True,
            "total_languages": len(lang_counts),
            "primary_language": lang_counts.most_common(1)[0][0] if lang_counts else "unknown",
            "top_languages": top_languages
        }

    def _aggregate_categories(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate content categories across posts"""
        categories = [p.ai_content_category for p in posts if p.ai_content_category]
        confidences = [p.ai_category_confidence for p in posts if p.ai_category_confidence is not None]

        if not categories:
            return {"available": False}

        category_counts = Counter(categories)
        total = len(categories)

        # Get top 5 categories
        top_categories = [
            {"category": cat, "percentage": count / total * 100}
            for cat, count in category_counts.most_common(5)
        ]

        return {
            "available": True,
            "total_categories": len(category_counts),
            "primary_category": category_counts.most_common(1)[0][0] if category_counts else "unknown",
            "average_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "top_categories": top_categories
        }

    def _aggregate_audience_quality(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate audience quality metrics from ai_analysis_raw"""
        quality_scores = []
        authenticity_scores = []
        bot_scores = []

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'audience_quality' in advanced:
                    aq = advanced['audience_quality']
                    if 'authenticity_score' in aq:
                        authenticity_scores.append(aq['authenticity_score'])
                    if 'bot_detection_score' in aq:
                        bot_scores.append(aq['bot_detection_score'])

        if not authenticity_scores:
            return {"available": False}

        return {
            "available": True,
            "average_authenticity": sum(authenticity_scores) / len(authenticity_scores),
            "average_bot_score": sum(bot_scores) / len(bot_scores) if bot_scores else 0,
            "quality_rating": "high" if sum(authenticity_scores) / len(authenticity_scores) > 75 else "medium" if sum(authenticity_scores) / len(authenticity_scores) > 50 else "low"
        }

    def _aggregate_visual_content(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate visual content analysis from ai_analysis_raw"""
        aesthetic_scores = []
        professional_scores = []
        faces_detected = 0

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'visual_content' in advanced:
                    vc = advanced['visual_content']
                    if 'aesthetic_score' in vc:
                        aesthetic_scores.append(vc['aesthetic_score'])
                    if 'professional_quality_score' in vc:
                        professional_scores.append(vc['professional_quality_score'])
                    if 'face_analysis' in vc and 'faces_detected' in vc['face_analysis']:
                        faces_detected += vc['face_analysis']['faces_detected']

        if not aesthetic_scores:
            return {"available": False}

        # Add image quality scores aggregation
        image_quality_scores = []
        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'visual_content' in advanced:
                    vc = advanced['visual_content']
                    if 'image_quality_metrics' in vc and 'average_quality' in vc['image_quality_metrics']:
                        image_quality_scores.append(vc['image_quality_metrics']['average_quality'])

        return {
            "available": True,
            "aesthetic_score": round(sum(aesthetic_scores) / len(aesthetic_scores), 2),
            "professional_quality_score": round(sum(professional_scores) / len(professional_scores), 2) if professional_scores else 0,
            "image_quality_metrics": {
                "average_quality": round(sum(image_quality_scores) / len(image_quality_scores), 2) if image_quality_scores else 0
            }
        }

    def _aggregate_audience_insights(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate audience insights (geographic, demographic) from ai_analysis_raw"""
        country_dist = defaultdict(int)
        location_dist = defaultdict(int)
        age_groups = defaultdict(float)
        gender_split = defaultdict(float)
        interests = defaultdict(float)
        brand_affinities = defaultdict(int)
        language_indicators = defaultdict(int)
        geographic_reach_values, diversity_scores, international_flags = [], [], []
        sophistication_values, social_contexts = [], []

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'audience_insights' in advanced:
                    ai = advanced['audience_insights']
                    if 'geographic_analysis' in ai:
                        ga = ai['geographic_analysis']
                        for country, count in ga.get('country_distribution', {}).items():
                            country_dist[country] += count
                        for loc, count in ga.get('location_distribution', {}).items():
                            location_dist[loc] += count
                        if 'geographic_reach' in ga:
                            geographic_reach_values.append(ga['geographic_reach'])
                        if 'geographic_diversity_score' in ga:
                            diversity_scores.append(ga['geographic_diversity_score'])
                        if 'international_reach' in ga:
                            international_flags.append(ga['international_reach'])
                    if 'demographic_insights' in ai:
                        di = ai['demographic_insights']
                        for age, pct in di.get('estimated_age_groups', {}).items():
                            age_groups[age] += pct
                        for gender, pct in di.get('estimated_gender_split', {}).items():
                            gender_split[gender] += pct
                        if 'audience_sophistication' in di:
                            sophistication_values.append(di['audience_sophistication'])
                    if 'audience_interests' in ai:
                        aint = ai['audience_interests']
                        for interest, pct in aint.get('interest_distribution', {}).items():
                            interests[interest] += pct
                        for brand, count in aint.get('brand_affinities', {}).items():
                            brand_affinities[brand] += count
                    if 'cultural_analysis' in ai:
                        ca = ai['cultural_analysis']
                        if 'social_context' in ca:
                            social_contexts.append(ca['social_context'])
                        for lang, count in ca.get('language_indicators', {}).items():
                            language_indicators[lang] += count

        if not country_dist and not age_groups:
            return {"available": False}

        num_posts = len(posts)
        return {
            "available": True,
            "geographic_analysis": {
                "country_distribution": dict(country_dist),
                "location_distribution": dict(location_dist),
                "geographic_reach": Counter(geographic_reach_values).most_common(1)[0][0] if geographic_reach_values else "local",
                "geographic_diversity_score": round(sum(diversity_scores) / len(diversity_scores), 1) if diversity_scores else 0.1,
                "international_reach": any(international_flags) if international_flags else False
            },
            "demographic_insights": {
                "estimated_age_groups": {age: round(pct / num_posts, 2) for age, pct in age_groups.items()},
                "estimated_gender_split": {gender: round(pct / num_posts, 2) for gender, pct in gender_split.items()},
                "audience_sophistication": Counter(sophistication_values).most_common(1)[0][0] if sophistication_values else "high"
            },
            "audience_interests": {
                "interest_distribution": {interest: round(pct / num_posts, 3) for interest, pct in interests.items()},
                "brand_affinities": dict(brand_affinities)
            },
            "cultural_analysis": {
                "social_context": Counter(social_contexts).most_common(1)[0][0] if social_contexts else "general",
                "language_indicators": dict(language_indicators)
            }
        }

    def _aggregate_trends(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate trend detection from ai_analysis_raw"""
        viral_scores = []

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'trend_detection' in advanced and 'viral_potential' in advanced['trend_detection']:
                    vp = advanced['trend_detection']['viral_potential']
                    if 'overall_viral_score' in vp:
                        viral_scores.append(vp['overall_viral_score'])

        if not viral_scores:
            return {"available": False}

        avg_viral = sum(viral_scores) / len(viral_scores)

        return {
            "available": True,
            "average_viral_potential": avg_viral,
            "viral_rating": "high" if avg_viral > 70 else "medium" if avg_viral > 40 else "low",
            "trending_posts": len([s for s in viral_scores if s > 70])
        }

    def _aggregate_nlp(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate advanced NLP insights from ai_analysis_raw"""
        word_counts = []
        readability_scores = []
        hashtag_counts = []
        brand_mentions = []

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'advanced_nlp' in advanced:
                    nlp = advanced['advanced_nlp']

                    if 'text_analysis' in nlp:
                        ta = nlp['text_analysis']
                        if 'average_word_count' in ta:
                            word_counts.append(ta['average_word_count'])
                        if 'readability_scores' in ta and 'flesch_ease' in ta['readability_scores']:
                            readability_scores.append(ta['readability_scores']['flesch_ease'])

                    if 'entity_extraction' in nlp:
                        ee = nlp['entity_extraction']
                        if 'hashtags' in ee:
                            hashtag_counts.append(ee['hashtags'])
                        if 'brand_mentions' in ee:
                            brand_mentions.extend(ee['brand_mentions'])

        if not word_counts:
            return {"available": False}

        return {
            "available": True,
            "average_word_count": sum(word_counts) / len(word_counts),
            "average_readability": sum(readability_scores) / len(readability_scores) if readability_scores else 0,
            "average_hashtags": sum(hashtag_counts) / len(hashtag_counts) if hashtag_counts else 0,
            "total_brand_mentions": len(brand_mentions),
            "content_depth": "detailed" if sum(word_counts) / len(word_counts) > 150 else "moderate" if sum(word_counts) / len(word_counts) > 50 else "brief"
        }

    def _aggregate_fraud(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate fraud detection from ai_analysis_raw"""
        fraud_scores = []
        risk_levels = []

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'fraud_detection' in advanced:
                    fd = advanced['fraud_detection']
                    if 'fraud_assessment' in fd:
                        fa = fd['fraud_assessment']
                        if 'overall_fraud_score' in fa:
                            fraud_scores.append(fa['overall_fraud_score'])
                        if 'risk_level' in fa:
                            risk_levels.append(fa['risk_level'])

        if not fraud_scores:
            return {"available": False}

        risk_counts = Counter(risk_levels)

        return {
            "available": True,
            "average_fraud_score": sum(fraud_scores) / len(fraud_scores),
            "risk_distribution": {
                "low": risk_counts.get("low", 0),
                "medium": risk_counts.get("medium", 0),
                "high": risk_counts.get("high", 0)
            },
            "overall_trust_level": "high" if sum(fraud_scores) / len(fraud_scores) < 20 else "medium" if sum(fraud_scores) / len(fraud_scores) < 50 else "low"
        }

    def _aggregate_behavioral_patterns(self, posts: List[Post]) -> Dict[str, Any]:
        """Aggregate behavioral patterns from ai_analysis_raw"""
        engagement_scores = []
        posting_frequencies = []

        for post in posts:
            if post.ai_analysis_raw and 'advanced_models' in post.ai_analysis_raw:
                advanced = post.ai_analysis_raw['advanced_models']
                if 'behavioral_patterns' in advanced:
                    bp = advanced['behavioral_patterns']
                    if 'behavioral_patterns' in bp and 'engagement_consistency_score' in bp['behavioral_patterns']:
                        engagement_scores.append(bp['behavioral_patterns']['engagement_consistency_score'])
                    if 'behavioral_patterns' in bp and 'posting_frequency' in bp['behavioral_patterns']:
                        posting_frequencies.append(bp['behavioral_patterns']['posting_frequency'])

        if not engagement_scores:
            return {"available": False}

        return {
            "available": True,
            "average_engagement_consistency": sum(engagement_scores) / len(engagement_scores),
            "average_posting_frequency": sum(posting_frequencies) / len(posting_frequencies) if posting_frequencies else 0,
            "consistency_rating": "high" if sum(engagement_scores) / len(engagement_scores) > 75 else "medium" if sum(engagement_scores) / len(engagement_scores) > 50 else "low"
        }


# Global service instance
campaign_ai_insights_service = CampaignAIInsightsService()
