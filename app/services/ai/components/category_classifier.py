"""
Category Classifier Component  
Classifies Instagram posts into content categories using zero-shot classification
"""
import logging
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger(__name__)

class CategoryClassifier:
    """
    Content category classification component
    """
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        self.pipeline = None
        self.initialized = False
        
        # Content categories for classification
        self.CONTENT_CATEGORIES = [
            "Fashion & Beauty",
            "Food & Dining", 
            "Travel & Adventure",
            "Technology & Gadgets",
            "Fitness & Health",
            "Home & Lifestyle",
            "Business & Professional",
            "Art & Creativity",
            "Entertainment",
            "Education & Learning",
            "Sports & Recreation",
            "Family & Personal",
            "Photography",
            "Music & Audio",
            "Automotive",
            "Gaming",
            "Nature & Outdoors",
            "Shopping & Reviews",
            "News & Politics",
            "General"
        ]
        
        # Category keywords for enhanced classification
        self.category_keywords = {
            "Fashion & Beauty": [
                "fashion", "style", "outfit", "ootd", "beauty", "makeup", "cosmetics",
                "skincare", "hair", "nails", "accessories", "jewelry", "shoes", "bag"
            ],
            "Food & Dining": [
                "food", "recipe", "cooking", "restaurant", "dining", "cuisine", "meal",
                "breakfast", "lunch", "dinner", "dessert", "coffee", "drink", "chef"
            ],
            "Travel & Adventure": [
                "travel", "trip", "vacation", "adventure", "explore", "journey", "destination",
                "hotel", "flight", "beach", "mountain", "city", "country", "tour"
            ],
            "Technology & Gadgets": [
                "tech", "technology", "gadget", "smartphone", "computer", "software", "app",
                "digital", "innovation", "device", "electronics", "coding", "AI", "startup"
            ],
            "Fitness & Health": [
                "fitness", "workout", "exercise", "gym", "health", "wellness", "yoga",
                "running", "training", "nutrition", "diet", "healthy", "meditation", "sport"
            ],
            "Business & Professional": [
                "business", "work", "professional", "career", "office", "meeting", "corporate",
                "entrepreneur", "leadership", "marketing", "sales", "finance", "strategy"
            ],
            "Art & Creativity": [
                "art", "creative", "design", "artist", "painting", "drawing", "sculpture",
                "craft", "handmade", "DIY", "creative", "gallery", "exhibition", "artwork"
            ],
            "Sports & Recreation": [
                "sport", "game", "team", "player", "match", "competition", "tournament",
                "football", "basketball", "soccer", "tennis", "golf", "baseball", "hockey"
            ]
        }
    
    async def initialize(self) -> bool:
        """Initialize category classification pipeline"""
        try:
            # Category classification is loaded on-demand to save memory
            self.initialized = True
            logger.info(" Category Classifier initialized")
            return True
            
        except Exception as e:
            logger.error(f" Failed to initialize Category Classifier: {e}")
            return False
    
    async def classify_content(
        self, 
        text: str, 
        hashtags: List[str] = None, 
        media_type: str = None
    ) -> Dict[str, Any]:
        """
        Classify content into categories
        
        Returns:
        {
            "category": "Fashion & Beauty",
            "confidence": 0.87
        }
        """
        if not self.initialized:
            return {"category": "General", "confidence": 0.0}
        
        try:
            # First try keyword-based classification (faster and often accurate)
            keyword_result = self._classify_by_keywords(text, hashtags)
            
            if keyword_result["confidence"] >= 0.7:
                # High confidence keyword match, return it
                return keyword_result
            
            # Fall back to AI classification for ambiguous cases
            ai_result = await self._classify_with_ai(text)
            
            # Combine results (keyword match gets slight boost if AI is uncertain)
            if ai_result["confidence"] < 0.6 and keyword_result["confidence"] > 0.3:
                return {
                    "category": keyword_result["category"],
                    "confidence": min(0.6, keyword_result["confidence"] + 0.1)
                }
            
            return ai_result
            
        except Exception as e:
            logger.error(f"Content classification failed: {e}")
            return {"category": "General", "confidence": 0.0}
    
    def _classify_by_keywords(self, text: str, hashtags: List[str] = None) -> Dict[str, Any]:
        """
        Fast keyword-based classification
        """
        if not text and not hashtags:
            return {"category": "General", "confidence": 0.0}
        
        # Combine text and hashtags
        combined_text = text.lower() if text else ""
        if hashtags:
            hashtag_text = " ".join(hashtags).lower()
            combined_text = f"{combined_text} {hashtag_text}"
        
        category_scores = {}
        
        # Score each category based on keyword matches
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                # Count keyword occurrences (with word boundaries)
                matches = len(re.findall(rf'\\b{re.escape(keyword)}\\b', combined_text))
                score += matches
            
            if score > 0:
                # Normalize score based on text length and number of keywords
                normalized_score = min(1.0, score / len(keywords) * 2)
                category_scores[category] = normalized_score
        
        if not category_scores:
            return {"category": "General", "confidence": 0.0}
        
        # Get best category
        best_category = max(category_scores, key=category_scores.get)
        confidence = category_scores[best_category]
        
        return {
            "category": best_category,
            "confidence": round(confidence, 3)
        }
    
    async def _classify_with_ai(self, text: str) -> Dict[str, Any]:
        """
        AI-based classification using zero-shot classification
        """
        try:
            # Load model on-demand
            pipeline = await self.models_manager.load_category_model()
            
            if not pipeline:
                return {"category": "General", "confidence": 0.0}
            
            # Preprocess text
            processed_text = self._preprocess_text(text)
            
            if not processed_text.strip():
                return {"category": "General", "confidence": 0.0}
            
            # Run classification
            result = pipeline(processed_text, self.CONTENT_CATEGORIES)
            
            if result and 'labels' in result and 'scores' in result:
                # Get top result
                top_category = result['labels'][0]
                confidence = result['scores'][0]
                
                return {
                    "category": top_category,
                    "confidence": round(confidence, 3)
                }
            
            return {"category": "General", "confidence": 0.0}
            
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return {"category": "General", "confidence": 0.0}
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for classification
        """
        if not text:
            return ""
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove excessive emojis but keep some context
        text = re.sub(r'[\\U0001F600-\\U0001F64F]{2,}', '😊', text)
        
        # Clean mentions but keep hashtags
        text = re.sub(r'@[\\w.]+', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\\s+', ' ', text)
        
        # Limit length
        if len(text) > 500:
            text = text[:500]
        
        return text.strip()
    
    def get_category_stats(self, category_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate category distribution statistics
        """
        if not category_results:
            return {
                "category_distribution": {},
                "primary_category": "General",
                "total_analyzed": 0
            }
        
        category_counts = {}
        total_confidence = {}
        
        for result in category_results:
            category = result.get("category", "General")
            confidence = result.get("confidence", 0.0)
            
            if category not in category_counts:
                category_counts[category] = 0
                total_confidence[category] = 0.0
            
            category_counts[category] += 1
            total_confidence[category] += confidence
        
        # Calculate distribution
        total = len(category_results)
        distribution = {}
        
        for category, count in category_counts.items():
            avg_confidence = total_confidence[category] / count
            distribution[category] = {
                "ratio": round(count / total, 3),
                "count": count,
                "avg_confidence": round(avg_confidence, 3)
            }
        
        # Find primary category
        primary_category = max(category_counts, key=category_counts.get) if category_counts else "General"
        
        return {
            "category_distribution": distribution,
            "primary_category": primary_category,
            "total_analyzed": total
        }
    
    def get_supported_categories(self) -> List[str]:
        """Get list of supported content categories"""
        return self.CONTENT_CATEGORIES.copy()