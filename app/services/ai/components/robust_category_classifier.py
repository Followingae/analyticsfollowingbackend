"""
Robust Category Classifier Component - Production Ready
Provides reliable content categorization with hybrid AI + rule-based approach
"""
import logging
from typing import Dict, Any, Optional, List
import re

from ..ai_manager_singleton import ai_manager

logger = logging.getLogger(__name__)

class RobustCategoryClassifier:
    """
    Production-ready category classifier with hybrid AI + rule-based approach
    """
    
    def __init__(self):
        self.initialized = False
        self.fallback_mode = False
        
        # Comprehensive category definitions
        self.CATEGORIES = [
            "Fashion & Beauty",
            "Food & Drink", 
            "Travel & Tourism",
            "Technology",
            "Fitness & Health",
            "Entertainment",
            "Lifestyle",
            "Business & Finance",
            "Education",
            "Art & Culture",
            "Sports",
            "Music",
            "Photography",
            "Gaming",
            "Automotive",
            "Home & Garden",
            "Pets & Animals",
            "News & Politics",
            "Science",
            "General"
        ]
        
        # Detailed keyword mappings for rule-based classification
        self.CATEGORY_KEYWORDS = {
            "Fashion & Beauty": {
                "primary": ['fashion', 'style', 'outfit', 'ootd', 'beauty', 'makeup', 'skincare', 
                          'clothing', 'dress', 'shoes', 'accessories', 'jewelry', 'handbag', 'designer'],
                "hashtags": ['#fashion', '#style', '#ootd', '#beauty', '#makeup', '#skincare', 
                           '#outfit', '#fashionista', '#styleinspo', '#beautyblogger'],
                "weight": 1.0
            },
            "Food & Drink": {
                "primary": ['food', 'recipe', 'cooking', 'restaurant', 'meal', 'delicious', 'taste',
                          'dinner', 'lunch', 'breakfast', 'chef', 'cuisine', 'drink', 'coffee', 'wine'],
                "hashtags": ['#food', '#foodie', '#recipe', '#cooking', '#delicious', '#yummy',
                           '#restaurant', '#chef', '#cuisine', '#foodblogger'],
                "weight": 1.0
            },
            "Travel & Tourism": {
                "primary": ['travel', 'vacation', 'trip', 'destination', 'hotel', 'beach', 'city',
                          'country', 'explore', 'adventure', 'journey', 'tourism', 'flight', 'passport'],
                "hashtags": ['#travel', '#vacation', '#trip', '#explore', '#wanderlust', '#adventure',
                           '#tourism', '#destination', '#travelgram', '#travelblogger'],
                "weight": 1.0
            },
            "Technology": {
                "primary": ['tech', 'technology', 'software', 'app', 'digital', 'computer', 'phone',
                          'gadget', 'innovation', 'ai', 'coding', 'programming', 'startup', 'internet'],
                "hashtags": ['#tech', '#technology', '#software', '#app', '#digital', '#innovation',
                           '#coding', '#programming', '#startup', '#techreview'],
                "weight": 1.0
            },
            "Fitness & Health": {
                "primary": ['fitness', 'workout', 'gym', 'health', 'exercise', 'sport', 'training',
                          'wellness', 'nutrition', 'diet', 'yoga', 'running', 'muscle', 'cardio'],
                "hashtags": ['#fitness', '#workout', '#gym', '#health', '#exercise', '#training',
                           '#wellness', '#nutrition', '#yoga', '#fitnessmotivation'],
                "weight": 1.0
            },
            "Entertainment": {
                "primary": ['movie', 'film', 'show', 'tv', 'series', 'entertainment', 'celebrity',
                          'actor', 'actress', 'cinema', 'theater', 'concert', 'event', 'party'],
                "hashtags": ['#movie', '#film', '#entertainment', '#celebrity', '#concert', '#show',
                           '#cinema', '#theater', '#party', '#event'],
                "weight": 1.0
            },
            "Music": {
                "primary": ['music', 'song', 'singer', 'artist', 'album', 'concert', 'band',
                          'guitar', 'piano', 'drums', 'vocals', 'melody', 'rhythm', 'lyrics'],
                "hashtags": ['#music', '#song', '#singer', '#artist', '#concert', '#band',
                           '#musician', '#newmusic', '#livemusic', '#musiclover'],
                "weight": 1.0
            },
            "Sports": {
                "primary": ['sports', 'football', 'soccer', 'basketball', 'tennis', 'golf', 'baseball',
                          'hockey', 'swimming', 'athletics', 'competition', 'team', 'player', 'game'],
                "hashtags": ['#sports', '#football', '#soccer', '#basketball', '#tennis', '#golf',
                           '#athletics', '#competition', '#team', '#player'],
                "weight": 1.0
            },
            "Business & Finance": {
                "primary": ['business', 'finance', 'money', 'investment', 'entrepreneur', 'startup',
                          'marketing', 'sales', 'economy', 'stock', 'trading', 'bitcoin', 'crypto'],
                "hashtags": ['#business', '#entrepreneur', '#startup', '#marketing', '#finance',
                           '#investment', '#money', '#success', '#businesstips', '#trading'],
                "weight": 1.0
            },
            "Art & Culture": {
                "primary": ['art', 'artist', 'painting', 'drawing', 'sculpture', 'gallery', 'museum',
                          'culture', 'creative', 'design', 'illustration', 'artwork', 'exhibition'],
                "hashtags": ['#art', '#artist', '#painting', '#drawing', '#creative', '#design',
                           '#artwork', '#gallery', '#culture', '#illustration'],
                "weight": 1.0
            },
            "Education": {
                "primary": ['education', 'learning', 'school', 'university', 'student', 'teacher',
                          'study', 'knowledge', 'academic', 'research', 'science', 'lecture', 'course'],
                "hashtags": ['#education', '#learning', '#student', '#school', '#university',
                           '#knowledge', '#study', '#academic', '#research', '#science'],
                "weight": 1.0
            },
            "Photography": {
                "primary": ['photography', 'photo', 'camera', 'photographer', 'picture', 'image',
                          'shot', 'lens', 'portrait', 'landscape', 'studio', 'photoshoot'],
                "hashtags": ['#photography', '#photo', '#photographer', '#camera', '#photoshoot',
                           '#portrait', '#landscape', '#photooftheday', '#picoftheday', '#instaphoto'],
                "weight": 1.0
            },
            "Gaming": {
                "primary": ['gaming', 'game', 'gamer', 'video game', 'console', 'pc gaming',
                          'esports', 'streaming', 'twitch', 'youtube gaming', 'mobile game'],
                "hashtags": ['#gaming', '#gamer', '#videogames', '#console', '#pcgaming',
                           '#esports', '#streaming', '#gamers', '#gameplay', '#mobilegaming'],
                "weight": 1.0
            },
            "Lifestyle": {
                "primary": ['life', 'lifestyle', 'daily', 'routine', 'home', 'family', 'friends',
                          'personal', 'happiness', 'love', 'relationship', 'selfcare', 'mindfulness'],
                "hashtags": ['#lifestyle', '#life', '#daily', '#routine', '#selfcare', '#mindfulness',
                           '#happiness', '#love', '#family', '#friends'],
                "weight": 0.5  # Lower weight as it's often mixed with other categories
            }
        }
        
    async def initialize(self) -> bool:
        """Initialize category classifier using global singleton"""
        try:
            # Ensure the global AI manager is initialized
            if not ai_manager._initialized:
                await ai_manager.initialize_models(['category'])
            
            # Check if category model is available
            pipeline = ai_manager.get_category_pipeline()
            if pipeline:
                self.initialized = True
                self.fallback_mode = False
                logger.info("✅ Robust Category Classifier initialized with AI models")
            else:
                self.initialized = True
                self.fallback_mode = True
                logger.warning("⚠️ Category Classifier initialized in FALLBACK mode (no AI models)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Robust Category Classifier: {e}")
            self.initialized = True
            self.fallback_mode = True
            return True  # Always return True to allow fallback mode
    
    async def classify_content(self, text: str, hashtags: List[str] = None, 
                             media_type: str = None) -> Dict[str, Any]:
        """
        Classify content category with hybrid AI + rule-based approach
        
        Args:
            text: Caption/description text
            hashtags: List of hashtags
            media_type: Type of media (image, video, carousel)
            
        Returns:
        {
            "category": str,
            "confidence": float (0.0 to 1.0),
            "method": "ai"|"hybrid"|"fallback",
            "processing_info": dict
        }
        """
        if not self.initialized:
            await self.initialize()
        
        processing_info = {
            "text_length": len(text) if text else 0,
            "hashtags_count": len(hashtags) if hashtags else 0,
            "media_type": media_type,
            "method_used": "fallback"
        }
        
        try:
            # Input validation
            if not text and not hashtags:
                return {
                    "category": "General",
                    "confidence": 0.3,
                    "method": "fallback",
                    "processing_info": {**processing_info, "reason": "no_content"}
                }
            
            hashtags = hashtags or []
            
            # Try AI analysis first if available
            ai_result = None
            if not self.fallback_mode and text:
                try:
                    ai_result = await self._ai_category_classification(text, processing_info)
                    processing_info["method_used"] = "ai"
                except Exception as ai_error:
                    logger.warning(f"AI category classification failed: {ai_error}")
                    # Continue to rule-based or hybrid
            
            # Rule-based analysis (always run for hybrid approach)
            rule_result = await self._rule_based_classification(text, hashtags, processing_info)
            
            # Combine results if both are available (hybrid approach)
            if ai_result and ai_result.get("confidence", 0) > 0.3:
                final_result = await self._combine_ai_and_rule_results(ai_result, rule_result, processing_info)
                final_result["method"] = "hybrid"
                processing_info["method_used"] = "hybrid"
            elif ai_result:
                final_result = ai_result
                final_result["method"] = "ai"
            else:
                final_result = rule_result
                final_result["method"] = "fallback"
            
            final_result["processing_info"] = processing_info
            return final_result
            
        except Exception as e:
            logger.error(f"Category classification completely failed: {e}")
            return {
                "category": "General",
                "confidence": 0.3,
                "method": "error",
                "processing_info": {**processing_info, "error": str(e)}
            }
    
    async def _ai_category_classification(self, text: str, processing_info: Dict) -> Dict[str, Any]:
        """AI-powered category classification"""
        pipeline = ai_manager.get_category_pipeline()
        if not pipeline:
            raise Exception("Category pipeline not available")
        
        # Preprocess text to prevent tensor size errors
        processed_text = ai_manager.preprocess_text_for_model(text, 'category')
        processing_info["preprocessing_applied"] = processed_text != text
        processing_info["processed_text_length"] = len(processed_text)
        
        if not processed_text.strip():
            return {
                "category": "General",
                "confidence": 0.3,
                "reason": "empty_after_preprocessing"
            }
        
        try:
            # Run zero-shot classification
            results = pipeline(processed_text, self.CATEGORIES)
            
            if results and 'labels' in results and 'scores' in results:
                top_category = results['labels'][0]
                top_score = float(results['scores'][0])
                
                processing_info["ai_top_predictions"] = [
                    {"category": results['labels'][i], "score": float(results['scores'][i])}
                    for i in range(min(3, len(results['labels'])))
                ]
                
                return {
                    "category": top_category,
                    "confidence": round(top_score, 3)
                }
            
            raise Exception("Unexpected results format from AI model")
            
        except Exception as model_error:
            logger.error(f"Category classification model error: {model_error}")
            raise model_error
    
    async def _rule_based_classification(self, text: str, hashtags: List[str], 
                                       processing_info: Dict) -> Dict[str, Any]:
        """Rule-based category classification"""
        text = text or ""
        combined_text = f"{text} {' '.join(hashtags)}".lower()
        
        category_scores = {}
        
        for category, keywords_data in self.CATEGORY_KEYWORDS.items():
            score = 0.0
            matches_found = []
            
            # Primary keywords
            for keyword in keywords_data["primary"]:
                if keyword in combined_text:
                    score += 1.0
                    matches_found.append(f"primary:{keyword}")
            
            # Hashtag keywords (with higher weight)
            for hashtag_keyword in keywords_data["hashtags"]:
                if hashtag_keyword in combined_text:
                    score += 1.5  # Hashtags are more indicative
                    matches_found.append(f"hashtag:{hashtag_keyword}")
            
            # Apply category weight
            score *= keywords_data["weight"]
            
            if score > 0:
                category_scores[category] = {
                    "score": score,
                    "matches": matches_found
                }
        
        # Determine final category
        if category_scores:
            best_category = max(category_scores, key=lambda x: category_scores[x]["score"])
            best_score = category_scores[best_category]["score"]
            
            # Calculate confidence based on score and competition
            total_score = sum(data["score"] for data in category_scores.values())
            confidence = min(0.9, 0.4 + (best_score / max(1, total_score)) * 0.5)
            
            processing_info["rule_based_scores"] = {
                cat: data["score"] for cat, data in category_scores.items()
            }
            processing_info["matches_found"] = category_scores[best_category]["matches"]
            
            return {
                "category": best_category,
                "confidence": round(confidence, 3)
            }
        else:
            # Default to General if no matches
            processing_info["default_reason"] = "no_category_keywords_found"
            return {
                "category": "General",
                "confidence": 0.4
            }
    
    async def _combine_ai_and_rule_results(self, ai_result: Dict, rule_result: Dict,
                                         processing_info: Dict) -> Dict[str, Any]:
        """Combine AI and rule-based results intelligently"""
        ai_category = ai_result.get("category", "General")
        ai_confidence = ai_result.get("confidence", 0.0)
        
        rule_category = rule_result.get("category", "General")
        rule_confidence = rule_result.get("confidence", 0.0)
        
        # If both methods agree, boost confidence
        if ai_category == rule_category:
            final_category = ai_category
            final_confidence = min(0.95, (ai_confidence + rule_confidence) / 2 + 0.2)
            processing_info["agreement"] = True
        else:
            # Methods disagree - use the one with higher confidence
            if ai_confidence >= rule_confidence:
                final_category = ai_category
                final_confidence = ai_confidence * 0.9  # Slight penalty for disagreement
            else:
                final_category = rule_category
                final_confidence = rule_confidence * 0.9
            
            processing_info["agreement"] = False
            processing_info["ai_prediction"] = {"category": ai_category, "confidence": ai_confidence}
            processing_info["rule_prediction"] = {"category": rule_category, "confidence": rule_confidence}
        
        return {
            "category": final_category,
            "confidence": round(final_confidence, 3)
        }
    
    def get_available_categories(self) -> List[str]:
        """Get list of available categories"""
        return self.CATEGORIES.copy()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get classifier health status"""
        return {
            "initialized": self.initialized,
            "fallback_mode": self.fallback_mode,
            "ai_model_available": not self.fallback_mode,
            "available_categories": len(self.CATEGORIES),
            "keyword_mappings": len(self.CATEGORY_KEYWORDS),
            "status": "healthy" if self.initialized else "not_initialized"
        }

# Create global instance for backwards compatibility
robust_category_classifier = RobustCategoryClassifier()