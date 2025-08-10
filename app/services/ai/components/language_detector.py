"""
Language Detector Component
Detects language of Instagram post captions using transformers
"""
import logging
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class LanguageDetector:
    """
    Language detection component using pre-trained transformers models
    """
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        self.pipeline = None
        self.initialized = False
        
        # Language code mapping (model output to ISO codes)
        self.language_mapping = {
            'ar': 'ar',  # Arabic
            'bg': 'bg',  # Bulgarian
            'de': 'de',  # German
            'el': 'el',  # Greek
            'en': 'en',  # English
            'es': 'es',  # Spanish
            'fr': 'fr',  # French
            'hi': 'hi',  # Hindi
            'it': 'it',  # Italian
            'ja': 'ja',  # Japanese
            'nl': 'nl',  # Dutch
            'pl': 'pl',  # Polish
            'pt': 'pt',  # Portuguese
            'ru': 'ru',  # Russian
            'sw': 'sw',  # Swahili
            'th': 'th',  # Thai
            'tr': 'tr',  # Turkish
            'ur': 'ur',  # Urdu
            'vi': 'vi',  # Vietnamese
            'zh': 'zh'   # Chinese
        }
    
    async def initialize(self) -> bool:
        """Initialize language detection pipeline"""
        try:
            self.pipeline = self.models_manager.get_language_pipeline()
            if not self.pipeline:
                logger.error("Language pipeline not available from models manager")
                return False
            
            self.initialized = True
            logger.info(" Language Detector initialized")
            return True
            
        except Exception as e:
            logger.error(f" Failed to initialize Language Detector: {e}")
            return False
    
    async def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect language of given text
        
        Returns:
        {
            "language": "en"|"ar"|"fr"|etc,
            "confidence": float (0.0 to 1.0)
        }
        """
        if not self.initialized or not self.pipeline:
            return {"language": "en", "confidence": 0.5}
        
        try:
            # Preprocess text
            processed_text = self._preprocess_text(text)
            
            if not processed_text.strip():
                return {"language": "en", "confidence": 0.5}
            
            # Run language detection
            results = self.pipeline(processed_text)
            
            # Process results
            if isinstance(results, list) and len(results) > 0:
                # Get the top result
                top_result = max(results[0], key=lambda x: x['score'])
                
                detected_language = top_result['label'].lower()
                confidence = top_result['score']
                
                # Map to standard ISO codes
                language_code = self.language_mapping.get(detected_language, detected_language)
                
                return {
                    "language": language_code,
                    "confidence": round(confidence, 3)
                }
            
            # Fallback
            return {"language": "en", "confidence": 0.5}
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return {"language": "en", "confidence": 0.0}
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for language detection
        """
        if not text:
            return ""
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove excessive emojis (keep some for language context)
        text = re.sub(r'[\\U0001F600-\\U0001F64F]{3,}', '😊', text)  # Emoticons
        text = re.sub(r'[\\U0001F300-\\U0001F5FF]{3,}', '🌟', text)  # Symbols & pictographs
        text = re.sub(r'[\\U0001F680-\\U0001F6FF]{3,}', '🚀', text)  # Transport & map
        text = re.sub(r'[\\U0001F1E0-\\U0001F1FF]{3,}', '🇺🇸', text)  # Flags
        
        # Remove Instagram-specific syntax but keep hashtags for language clues
        text = re.sub(r'@[\\w.]+', '', text)  # Remove mentions
        
        # Clean up excessive whitespace
        text = re.sub(r'\\s+', ' ', text)
        
        # Limit length
        max_length = 512
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    def get_language_stats(self, language_results: list) -> Dict[str, Any]:
        """
        Calculate language distribution statistics
        """
        if not language_results:
            return {
                "language_distribution": {},
                "primary_language": "en",
                "total_analyzed": 0
            }
        
        language_counts = {}
        total_confidence = {}
        
        for result in language_results:
            lang = result.get("language", "en")
            confidence = result.get("confidence", 0.0)
            
            if lang not in language_counts:
                language_counts[lang] = 0
                total_confidence[lang] = 0.0
            
            language_counts[lang] += 1
            total_confidence[lang] += confidence
        
        # Calculate distribution
        total = len(language_results)
        distribution = {}
        for lang, count in language_counts.items():
            avg_confidence = total_confidence[lang] / count
            distribution[lang] = {
                "ratio": round(count / total, 3),
                "count": count,
                "avg_confidence": round(avg_confidence, 3)
            }
        
        # Find primary language
        primary_language = max(language_counts, key=language_counts.get) if language_counts else "en"
        
        return {
            "language_distribution": distribution,
            "primary_language": primary_language,
            "total_analyzed": total
        }
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported language codes and names"""
        return {
            'ar': 'Arabic',
            'bg': 'Bulgarian', 
            'de': 'German',
            'el': 'Greek',
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'hi': 'Hindi',
            'it': 'Italian',
            'ja': 'Japanese',
            'nl': 'Dutch',
            'pl': 'Polish',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'sw': 'Swahili',
            'th': 'Thai',
            'tr': 'Turkish',
            'ur': 'Urdu',
            'vi': 'Vietnamese',
            'zh': 'Chinese'
        }