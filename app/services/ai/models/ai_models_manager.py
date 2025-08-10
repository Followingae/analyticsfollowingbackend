"""
AI Models Manager - Handles loading, caching, and management of AI/ML models
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
import torch
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    pipeline, Pipeline
)

logger = logging.getLogger(__name__)

class AIModelsManager:
    """
    Centralized manager for AI/ML models
    Handles model loading, caching, and memory management
    """
    
    def __init__(self):
        self.models_cache: Dict[str, Any] = {}
        self.tokenizers_cache: Dict[str, Any] = {}
        self.pipelines_cache: Dict[str, Pipeline] = {}
        self.initialized = False
        
        # Model configurations
        self.MODEL_CONFIGS = {
            'sentiment': {
                'model_name': 'cardiffnlp/twitter-roberta-base-sentiment-latest',
                'type': 'sentiment-analysis',
                'device': 'cpu'  # Can be changed to 'cuda' if GPU available
            },
            'language': {
                'model_name': 'papluca/xlm-roberta-base-language-detection',
                'type': 'text-classification',
                'device': 'cpu'
            },
            'category_text': {
                'model_name': 'facebook/bart-large-mnli',
                'type': 'zero-shot-classification',
                'device': 'cpu'
            }
        }
        
        # Set cache directory
        cache_dir = os.getenv('AI_MODELS_CACHE_DIR', './ai_models')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Set transformers cache
        os.environ['TRANSFORMERS_CACHE'] = str(self.cache_dir)
    
    async def initialize(self) -> bool:
        """Initialize all models"""
        try:
            logger.info("Initializing AI Models Manager...")
            
            # Check device availability
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device}")
            
            # Update device in configs if GPU available
            if device == "cuda":
                for config in self.MODEL_CONFIGS.values():
                    config['device'] = device
            
            # Pre-load critical models
            await self._load_sentiment_model()
            await self._load_language_model()
            
            self.initialized = True
            logger.info(" AI Models Manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f" Failed to initialize AI Models Manager: {e}")
            return False
    
    async def _load_sentiment_model(self) -> bool:
        """Load sentiment analysis model"""
        try:
            config = self.MODEL_CONFIGS['sentiment']
            model_name = config['model_name']
            
            logger.info(f"Loading sentiment model: {model_name}")
            
            # Create pipeline (automatically downloads and caches model)
            sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=model_name,
                device=0 if config['device'] == 'cuda' else -1,
                return_all_scores=True
            )
            
            self.pipelines_cache['sentiment'] = sentiment_pipeline
            logger.info(" Sentiment model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f" Failed to load sentiment model: {e}")
            return False
    
    async def _load_language_model(self) -> bool:
        """Load language detection model"""
        try:
            config = self.MODEL_CONFIGS['language']
            model_name = config['model_name']
            
            logger.info(f"Loading language model: {model_name}")
            
            # Create pipeline
            language_pipeline = pipeline(
                "text-classification",
                model=model_name,
                device=0 if config['device'] == 'cuda' else -1,
                return_all_scores=True
            )
            
            self.pipelines_cache['language'] = language_pipeline
            logger.info(" Language model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f" Failed to load language model: {e}")
            return False
    
    def get_sentiment_pipeline(self) -> Optional[Pipeline]:
        """Get sentiment analysis pipeline"""
        return self.pipelines_cache.get('sentiment')
    
    def get_language_pipeline(self) -> Optional[Pipeline]:
        """Get language detection pipeline"""
        return self.pipelines_cache.get('language')
    
    async def load_category_model(self) -> Optional[Pipeline]:
        """Load category classification model on-demand"""
        if 'category' not in self.pipelines_cache:
            try:
                config = self.MODEL_CONFIGS['category_text']
                model_name = config['model_name']
                
                logger.info(f"Loading category model: {model_name}")
                
                category_pipeline = pipeline(
                    "zero-shot-classification",
                    model=model_name,
                    device=0 if config['device'] == 'cuda' else -1
                )
                
                self.pipelines_cache['category'] = category_pipeline
                logger.info(" Category model loaded successfully")
                
            except Exception as e:
                logger.error(f" Failed to load category model: {e}")
                return None
        
        return self.pipelines_cache.get('category')
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models"""
        return {
            "initialized": self.initialized,
            "loaded_models": list(self.pipelines_cache.keys()),
            "cache_directory": str(self.cache_dir),
            "device_info": {
                "cuda_available": torch.cuda.is_available(),
                "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
            },
            "model_configs": self.MODEL_CONFIGS
        }
    
    def clear_cache(self):
        """Clear model cache to free memory"""
        logger.info("Clearing AI models cache...")
        self.pipelines_cache.clear()
        self.models_cache.clear()
        self.tokenizers_cache.clear()
        
        # Force garbage collection
        import gc
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info("AI models cache cleared")