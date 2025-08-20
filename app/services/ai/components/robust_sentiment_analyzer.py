"""
Robust Sentiment Analyzer Component - Production Ready
Fixes tensor size issues and provides bulletproof sentiment analysis
"""
import logging
from typing import Dict, Any, Optional
import re
import asyncio

from ..ai_manager_singleton import ai_manager

logger = logging.getLogger(__name__)

class RobustSentimentAnalyzer:
    """
    Production-ready sentiment analyzer with robust error handling
    Fixes tensor dimension mismatches and provides fallback mechanisms
    """
    
    def __init__(self):
        self.initialized = False
        self.fallback_mode = False
        
    async def initialize(self) -> None:
        """Initialize sentiment analyzer - MANDATORY, NO FALLBACKS"""
        if not ai_manager._initialized:
            raise RuntimeError(
                "🚨 AI Manager not initialized! System should have initialized all models during startup."
            )
        
        # Verify sentiment model is available (will raise exception if not)
        pipeline = ai_manager.get_sentiment_pipeline()
        
        self.initialized = True
        self.fallback_mode = False
        logger.info("✅ Sentiment Analyzer initialized with MANDATORY AI models")
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment with robust error handling and fallback
        
        Returns:
        {
            "label": "positive"|"negative"|"neutral",
            "score": float (-1.0 to 1.0),
            "confidence": float (0.0 to 1.0),
            "method": "ai"|"fallback",
            "processing_info": dict
        }
        """
        if not self.initialized:
            await self.initialize()
        
        processing_info = {
            "text_length": len(text) if text else 0,
            "preprocessing_applied": False,
            "model_used": "fallback"
        }
        
        try:
            # Input validation
            if not text or not isinstance(text, str):
                return {
                    "label": "neutral",
                    "score": 0.0,
                    "confidence": 0.5,
                    "method": "fallback",
                    "processing_info": {**processing_info, "reason": "empty_text"}
                }
            
            # Try AI analysis first if available
            if not self.fallback_mode:
                try:
                    return await self._ai_sentiment_analysis(text, processing_info)
                except Exception as ai_error:
                    logger.warning(f"AI sentiment analysis failed, falling back to rule-based: {ai_error}")
                    # Continue to fallback
            
            # Fallback to rule-based analysis
            return await self._fallback_sentiment_analysis(text, processing_info)
            
        except Exception as e:
            logger.error(f"Sentiment analysis completely failed: {e}")
            return {
                "label": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "method": "error",
                "processing_info": {**processing_info, "error": str(e)}
            }
    
    async def _ai_sentiment_analysis(self, text: str, processing_info: Dict) -> Dict[str, Any]:
        """AI-powered sentiment analysis with tensor size protection"""
        pipeline = ai_manager.get_sentiment_pipeline()
        if not pipeline:
            raise Exception("Sentiment pipeline not available")
        
        # CRITICAL: Preprocess text to prevent tensor size errors
        processed_text = ai_manager.preprocess_text_for_model(text, 'sentiment')
        processing_info["preprocessing_applied"] = processed_text != text
        processing_info["processed_text_length"] = len(processed_text)
        processing_info["model_used"] = "ai"
        
        if not processed_text.strip():
            return {
                "label": "neutral",
                "score": 0.0,
                "confidence": 0.5,
                "method": "ai",
                "processing_info": {**processing_info, "reason": "empty_after_preprocessing"}
            }
        
        try:
            # Run AI analysis with processed text
            results = pipeline(processed_text)
            
            # Process results safely
            if isinstance(results, list) and len(results) > 0 and isinstance(results[0], list):
                scores_dict = {}
                for result in results[0]:
                    label = result['label'].lower()
                    score = float(result['score'])
                    
                    # Normalize different label formats
                    if any(pos_indicator in label for pos_indicator in ['pos', 'positive']):
                        scores_dict['positive'] = score
                    elif any(neg_indicator in label for neg_indicator in ['neg', 'negative']):
                        scores_dict['negative'] = score
                    else:
                        scores_dict['neutral'] = score
                
                # Determine final sentiment
                if scores_dict:
                    final_label = max(scores_dict, key=scores_dict.get)
                    final_confidence = scores_dict[final_label]
                    
                    # Convert to score (-1 to 1 scale)
                    if final_label == 'positive':
                        final_score = final_confidence
                    elif final_label == 'negative':
                        final_score = -final_confidence
                    else:
                        final_score = 0.0
                    
                    processing_info["scores_breakdown"] = scores_dict
                    
                    return {
                        "label": final_label,
                        "score": round(final_score, 3),
                        "confidence": round(final_confidence, 3),
                        "method": "ai",
                        "processing_info": processing_info
                    }
            
            # If results format is unexpected, log for debugging
            logger.warning(f"Unexpected sentiment analysis results format: {results}")
            raise Exception("Unexpected results format from AI model")
            
        except Exception as model_error:
            # Log specific error for debugging tensor issues
            if "tensor" in str(model_error).lower() or "size" in str(model_error).lower():
                logger.error(f"TENSOR SIZE ERROR in sentiment analysis: {model_error}")
                logger.error(f"Text length: {len(processed_text)}, Text preview: {processed_text[:100]}...")
            
            raise model_error
    
    async def _fallback_sentiment_analysis(self, text: str, processing_info: Dict) -> Dict[str, Any]:
        """Rule-based sentiment analysis fallback"""
        processing_info["model_used"] = "rule_based_fallback"
        
        # Enhanced sentiment keywords
        positive_keywords = [
            'amazing', 'awesome', 'beautiful', 'best', 'brilliant', 'excellent', 'fantastic',
            'good', 'great', 'happy', 'incredible', 'love', 'perfect', 'wonderful',
            'outstanding', 'magnificent', 'superb', 'delightful', 'pleasant', 'enjoyable',
            'excited', 'thrilled', 'grateful', 'blessed', 'lucky', 'proud', 'satisfied'
        ]
        
        negative_keywords = [
            'awful', 'bad', 'broken', 'disappointed', 'failed', 'hate', 'horrible',
            'sad', 'terrible', 'ugly', 'worst', 'annoying', 'frustrated', 'angry',
            'disgusting', 'pathetic', 'useless', 'boring', 'stupid', 'ridiculous',
            'upset', 'worried', 'concerned', 'stressed', 'tired', 'exhausted'
        ]
        
        # Negation words that can flip sentiment
        negation_words = ['not', 'no', 'never', 'without', 'barely', 'hardly', 'scarcely']
        
        text_lower = text.lower()
        words = text_lower.split()
        
        positive_score = 0
        negative_score = 0
        
        # Analyze words with context
        for i, word in enumerate(words):
            # Check for negation in previous 2 words
            negated = False
            for j in range(max(0, i-2), i):
                if words[j] in negation_words:
                    negated = True
                    break
            
            if word in positive_keywords:
                if negated:
                    negative_score += 1
                else:
                    positive_score += 1
            elif word in negative_keywords:
                if negated:
                    positive_score += 1
                else:
                    negative_score += 1
        
        # Calculate final sentiment
        total_sentiment_words = positive_score + negative_score
        
        if total_sentiment_words == 0:
            final_label = "neutral"
            final_score = 0.0
            final_confidence = 0.5
        elif positive_score > negative_score:
            final_label = "positive"
            final_score = min(0.8, 0.5 + (positive_score - negative_score) * 0.1)
            final_confidence = min(0.9, 0.6 + (positive_score / total_sentiment_words) * 0.3)
        elif negative_score > positive_score:
            final_label = "negative"
            final_score = max(-0.8, -0.5 - (negative_score - positive_score) * 0.1)
            final_confidence = min(0.9, 0.6 + (negative_score / total_sentiment_words) * 0.3)
        else:
            final_label = "neutral"
            final_score = 0.0
            final_confidence = 0.6
        
        processing_info.update({
            "positive_keywords_found": positive_score,
            "negative_keywords_found": negative_score,
            "total_sentiment_indicators": total_sentiment_words
        })
        
        return {
            "label": final_label,
            "score": round(final_score, 3),
            "confidence": round(final_confidence, 3),
            "method": "fallback",
            "processing_info": processing_info
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get analyzer health status"""
        return {
            "initialized": self.initialized,
            "fallback_mode": self.fallback_mode,
            "ai_model_available": not self.fallback_mode,
            "status": "healthy" if self.initialized else "not_initialized"
        }

# Create global instance for backwards compatibility
robust_sentiment_analyzer = RobustSentimentAnalyzer()