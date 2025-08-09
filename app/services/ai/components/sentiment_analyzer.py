"""
Sentiment Analyzer Component
Provides sentiment analysis for Instagram post captions using transformers
"""
import logging
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Sentiment analysis component using pre-trained transformers models
    """
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        self.pipeline = None
        self.initialized = False
    
    async def initialize(self) -> bool:
        """Initialize sentiment analysis pipeline"""
        try:
            self.pipeline = self.models_manager.get_sentiment_pipeline()
            if not self.pipeline:
                logger.error("Sentiment pipeline not available from models manager")
                return False
            
            self.initialized = True
            logger.info("✅ Sentiment Analyzer initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Sentiment Analyzer: {e}")
            return False
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of given text
        
        Returns:
        {
            "label": "positive"|"negative"|"neutral",
            "score": float (-1.0 to 1.0),
            "confidence": float (0.0 to 1.0)
        }
        """
        if not self.initialized or not self.pipeline:
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}
        
        try:
            # Preprocess text
            processed_text = self._preprocess_text(text)
            
            if not processed_text.strip():
                return {"label": "neutral", "score": 0.0, "confidence": 0.5}
            
            # Run sentiment analysis
            results = self.pipeline(processed_text)
            
            # Process results (model returns all scores)
            if isinstance(results, list) and len(results) > 0:
                # Model returns all possible labels with scores
                scores_dict = {}
                for result in results[0]:  # First (and only) result
                    label = result['label'].lower()
                    score = result['score']
                    
                    # Normalize labels
                    if 'pos' in label:
                        scores_dict['positive'] = score
                    elif 'neg' in label:
                        scores_dict['negative'] = score
                    else:
                        scores_dict['neutral'] = score
                
                # Determine final sentiment
                final_label = max(scores_dict, key=scores_dict.get)
                final_confidence = scores_dict[final_label]
                
                # Convert to score (-1 to 1 scale)
                if final_label == 'positive':
                    final_score = final_confidence  # 0 to 1
                elif final_label == 'negative':
                    final_score = -final_confidence  # 0 to -1
                else:
                    final_score = 0.0
                
                return {
                    "label": final_label,
                    "score": round(final_score, 3),
                    "confidence": round(final_confidence, 3)
                }
            
            # Fallback if results format is unexpected
            return {"label": "neutral", "score": 0.0, "confidence": 0.5}
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {"label": "neutral", "score": 0.0, "confidence": 0.0}
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for sentiment analysis
        """
        if not text:
            return ""
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Clean up excessive whitespace
        text = re.sub(r'\\s+', ' ', text)
        
        # Limit length to avoid model limits
        max_length = 512  # BERT-based models typically have 512 token limit
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    def get_sentiment_stats(self, sentiments: list) -> Dict[str, Any]:
        """
        Calculate sentiment statistics for a list of sentiment results
        """
        if not sentiments:
            return {
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 0.0,
                "average_score": 0.0,
                "total_analyzed": 0
            }
        
        positive_count = sum(1 for s in sentiments if s.get("label") == "positive")
        negative_count = sum(1 for s in sentiments if s.get("label") == "negative")
        neutral_count = sum(1 for s in sentiments if s.get("label") == "neutral")
        
        total = len(sentiments)
        scores = [s.get("score", 0.0) for s in sentiments if isinstance(s.get("score"), (int, float))]
        
        return {
            "positive_ratio": round(positive_count / total, 3) if total > 0 else 0.0,
            "negative_ratio": round(negative_count / total, 3) if total > 0 else 0.0,
            "neutral_ratio": round(neutral_count / total, 3) if total > 0 else 0.0,
            "average_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "total_analyzed": total
        }