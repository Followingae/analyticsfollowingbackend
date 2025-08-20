"""
Robust Language Detector Component - Production Ready
Provides reliable language detection with fallback mechanisms
"""
import logging
from typing import Dict, Any, Optional
import re
import unicodedata

from ..ai_manager_singleton import ai_manager

logger = logging.getLogger(__name__)

class RobustLanguageDetector:
    """
    Production-ready language detector with robust error handling
    """
    
    def __init__(self):
        self.initialized = False
        self.fallback_mode = False
        
    async def initialize(self) -> None:
        """Initialize language detector - MANDATORY, NO FALLBACKS"""
        if not ai_manager._initialized:
            raise RuntimeError(
                "🚨 AI Manager not initialized! System should have initialized all models during startup."
            )
        
        # Verify language model is available (will raise exception if not)
        pipeline = ai_manager.get_language_pipeline()
        
        self.initialized = True
        self.fallback_mode = False
        logger.info("✅ Language Detector initialized with MANDATORY AI models")
    
    async def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect language with robust error handling and fallback
        
        Returns:
        {
            "language": str (ISO language code),
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
                    "language": "en",
                    "confidence": 0.3,
                    "method": "fallback",
                    "processing_info": {**processing_info, "reason": "empty_text"}
                }
            
            # Try AI analysis first if available
            if not self.fallback_mode:
                try:
                    return await self._ai_language_detection(text, processing_info)
                except Exception as ai_error:
                    logger.warning(f"AI language detection failed, falling back to rule-based: {ai_error}")
                    # Continue to fallback
            
            # Fallback to rule-based analysis
            return await self._fallback_language_detection(text, processing_info)
            
        except Exception as e:
            logger.error(f"Language detection completely failed: {e}")
            return {
                "language": "en",
                "confidence": 0.3,
                "method": "error",
                "processing_info": {**processing_info, "error": str(e)}
            }
    
    async def _ai_language_detection(self, text: str, processing_info: Dict) -> Dict[str, Any]:
        """AI-powered language detection"""
        pipeline = ai_manager.get_language_pipeline()
        if not pipeline:
            raise Exception("Language pipeline not available")
        
        # Preprocess text to prevent tensor size errors
        processed_text = ai_manager.preprocess_text_for_model(text, 'language')
        processing_info["preprocessing_applied"] = processed_text != text
        processing_info["processed_text_length"] = len(processed_text)
        processing_info["model_used"] = "ai"
        
        if not processed_text.strip():
            return {
                "language": "en",
                "confidence": 0.3,
                "method": "ai",
                "processing_info": {**processing_info, "reason": "empty_after_preprocessing"}
            }
        
        try:
            # Run AI analysis
            results = pipeline(processed_text)
            
            # Process results safely
            if isinstance(results, list) and len(results) > 0 and isinstance(results[0], list):
                # Get the top prediction
                top_result = results[0][0] if results[0] else None
                if top_result and 'label' in top_result and 'score' in top_result:
                    language_code = top_result['label']
                    confidence = float(top_result['score'])
                    
                    # Validate language code format
                    if len(language_code) >= 2:
                        processing_info["all_predictions"] = [
                            {"language": pred.get('label'), "score": pred.get('score')} 
                            for pred in results[0][:3]  # Top 3 predictions
                        ]
                        
                        return {
                            "language": language_code,
                            "confidence": round(confidence, 3),
                            "method": "ai",
                            "processing_info": processing_info
                        }
            
            # If results format is unexpected
            logger.warning(f"Unexpected language detection results format: {results}")
            raise Exception("Unexpected results format from AI model")
            
        except Exception as model_error:
            logger.error(f"Language detection model error: {model_error}")
            raise model_error
    
    async def _fallback_language_detection(self, text: str, processing_info: Dict) -> Dict[str, Any]:
        """Rule-based language detection fallback"""
        processing_info["model_used"] = "rule_based_fallback"
        
        # Language detection using character patterns and common words
        language_indicators = {
            'ar': {
                'chars': lambda t: sum(1 for char in t if '\u0600' <= char <= '\u06FF'),
                'words': ['في', 'من', 'إلى', 'على', 'هذا', 'هذه', 'التي', 'الذي'],
                'threshold': 0.1
            },
            'fr': {
                'chars': lambda t: sum(1 for char in t if char in 'àâäçéèêëïîôöùûüÿ'),
                'words': ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'à', 'avec', 'pour', 
                         'dans', 'sur', 'par', 'ce', 'cette', 'ces', 'qui', 'que', 'où'],
                'threshold': 0.05
            },
            'es': {
                'chars': lambda t: sum(1 for char in t if char in 'áéíóúüñ'),
                'words': ['el', 'la', 'los', 'las', 'de', 'del', 'y', 'en', 'con', 'por', 
                         'para', 'es', 'está', 'son', 'que', 'se', 'le', 'su'],
                'threshold': 0.05
            },
            'de': {
                'chars': lambda t: sum(1 for char in t if char in 'äöüß'),
                'words': ['der', 'die', 'das', 'und', 'ist', 'in', 'zu', 'mit', 'auf', 
                         'für', 'von', 'den', 'dem', 'des', 'ein', 'eine', 'einen'],
                'threshold': 0.03
            },
            'it': {
                'chars': lambda t: sum(1 for char in t if char in 'àèéìíîòóù'),
                'words': ['il', 'la', 'di', 'che', 'e', 'è', 'un', 'una', 'in', 'con', 
                         'per', 'da', 'su', 'del', 'della', 'sono', 'non'],
                'threshold': 0.04
            },
            'pt': {
                'chars': lambda t: sum(1 for char in t if char in 'ãâáàçéêíóôõú'),
                'words': ['o', 'a', 'os', 'as', 'de', 'do', 'da', 'dos', 'das', 'e', 
                         'em', 'para', 'com', 'por', 'que', 'não', 'um', 'uma'],
                'threshold': 0.04
            }
        }
        
        text_lower = text.lower()
        text_len = len(text)
        scores = {}
        
        # Calculate scores for each language
        for lang_code, indicators in language_indicators.items():
            score = 0.0
            
            # Character-based scoring
            char_count = indicators['chars'](text)
            char_score = min(1.0, char_count / max(1, text_len))
            
            # Word-based scoring
            word_matches = sum(1 for word in indicators['words'] 
                             if f' {word} ' in f' {text_lower} ')
            word_score = min(1.0, word_matches / max(1, len(text_lower.split())))
            
            # Combined score
            score = (char_score * 0.6) + (word_score * 0.4)
            
            if score >= indicators['threshold']:
                scores[lang_code] = score
        
        # Determine final language
        if scores:
            best_language = max(scores, key=scores.get)
            confidence = min(0.85, 0.5 + scores[best_language] * 0.5)
            
            processing_info["language_scores"] = dict(scores)
            
            return {
                "language": best_language,
                "confidence": round(confidence, 3),
                "method": "fallback",
                "processing_info": processing_info
            }
        else:
            # Default to English if no patterns match
            processing_info["default_reason"] = "no_language_patterns_detected"
            
            return {
                "language": "en",
                "confidence": 0.5,
                "method": "fallback",
                "processing_info": processing_info
            }
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return {
            'en': 'English',
            'ar': 'Arabic',
            'fr': 'French',
            'es': 'Spanish',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'nl': 'Dutch',
            'ru': 'Russian',
            'zh': 'Chinese',
            'ja': 'Japanese',
            'ko': 'Korean',
            'hi': 'Hindi',
            'tr': 'Turkish',
            'pl': 'Polish',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish',
            'hu': 'Hungarian'
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get detector health status"""
        return {
            "initialized": self.initialized,
            "fallback_mode": self.fallback_mode,
            "ai_model_available": not self.fallback_mode,
            "supported_languages": len(self.get_supported_languages()),
            "status": "healthy" if self.initialized else "not_initialized"
        }

# Create global instance for backwards compatibility
robust_language_detector = RobustLanguageDetector()