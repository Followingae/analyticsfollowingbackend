"""
AI Manager Singleton - Global AI Model Management
Ensures models are loaded once and cached throughout application lifecycle
"""
import logging
import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union
import torch
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    pipeline, Pipeline
)
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class AIManagerSingleton:
    """
    Thread-safe singleton AI manager for global model caching
    Ensures models are loaded only once per application lifecycle
    """
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AIManagerSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if hasattr(self, '_internal_initialized'):
            return
            
        self._internal_initialized = True
        self.models_cache: Dict[str, Any] = {}
        self.tokenizers_cache: Dict[str, Any] = {}
        self.pipelines_cache: Dict[str, Pipeline] = {}
        self.model_load_times: Dict[str, datetime] = {}
        self.model_usage_count: Dict[str, int] = {}
        self.initialization_lock = asyncio.Lock()
        
        # Model configurations
        self.MODEL_CONFIGS = {
            'sentiment': {
                'model_name': 'cardiffnlp/twitter-roberta-base-sentiment-latest',
                'type': 'sentiment-analysis',
                'device': 'cpu',
                'max_length': 512
            },
            'language': {
                'model_name': 'papluca/xlm-roberta-base-language-detection',
                'type': 'text-classification', 
                'device': 'cpu',
                'max_length': 512
            },
            'category': {
                'model_name': 'facebook/bart-large-mnli',
                'type': 'zero-shot-classification',
                'device': 'cpu',
                'max_length': 1024
            }
        }
        
        # Set cache directory
        cache_dir = os.getenv('AI_MODELS_CACHE_DIR', './ai_models')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Set transformers cache
        os.environ['TRANSFORMERS_CACHE'] = str(self.cache_dir)
        
        # Device detection
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"AI Manager Singleton initialized - Device: {self.device}")
    
    async def initialize_models(self, models_to_load: list = None) -> bool:
        """
        Initialize specified models or all models if none specified
        Thread-safe initialization with proper error handling
        """
        async with self.initialization_lock:
            try:
                if models_to_load is None:
                    models_to_load = ['sentiment', 'language']  # Load essential models first
                
                logger.info(f"Initializing AI models: {models_to_load}")
                
                success_count = 0
                for model_type in models_to_load:
                    if model_type in self.pipelines_cache:
                        logger.info(f"Model {model_type} already loaded, skipping")
                        success_count += 1
                        continue
                    
                    try:
                        success = await self._load_model(model_type)
                        if success:
                            success_count += 1
                            self.model_load_times[model_type] = datetime.now(timezone.utc)
                            self.model_usage_count[model_type] = 0
                            logger.info(f"✅ Model {model_type} loaded successfully")
                        else:
                            logger.error(f"❌ Failed to load model {model_type}")
                    except Exception as e:
                        logger.error(f"❌ Exception loading model {model_type}: {e}")
                
                self._initialized = success_count > 0
                logger.info(f"AI Manager initialization complete: {success_count}/{len(models_to_load)} models loaded")
                return self._initialized
                
            except Exception as e:
                logger.error(f"Failed to initialize AI Manager: {e}")
                return False
    
    async def _load_model(self, model_type: str) -> bool:
        """Load a specific model with error handling and memory management"""
        try:
            if model_type not in self.MODEL_CONFIGS:
                logger.error(f"Unknown model type: {model_type}")
                return False
            
            config = self.MODEL_CONFIGS[model_type]
            model_name = config['model_name']
            
            logger.info(f"Loading {model_type} model: {model_name}")
            
            # Determine device setting for pipeline
            device_setting = 0 if self.device == 'cuda' else -1
            
            # Load model based on type
            if model_type == 'sentiment':
                pipeline_obj = pipeline(
                    "sentiment-analysis",
                    model=model_name,
                    device=device_setting,
                    return_all_scores=True,
                    truncation=True,
                    max_length=config['max_length']
                )
            elif model_type == 'language':
                pipeline_obj = pipeline(
                    "text-classification",
                    model=model_name,
                    device=device_setting,
                    return_all_scores=True,
                    truncation=True,
                    max_length=config['max_length']
                )
            elif model_type == 'category':
                pipeline_obj = pipeline(
                    "zero-shot-classification",
                    model=model_name,
                    device=device_setting,
                    truncation=True,
                    max_length=config['max_length']
                )
            else:
                logger.error(f"Unknown model type for loading: {model_type}")
                return False
            
            # Cache the pipeline
            self.pipelines_cache[model_type] = pipeline_obj
            return True
            
        except Exception as e:
            logger.error(f"Failed to load {model_type} model: {e}")
            return False
    
    def get_model_pipeline(self, model_type: str) -> Optional[Pipeline]:
        """
        Get model pipeline with usage tracking
        Lazy loads model if not already loaded
        """
        try:
            # Check if model is already loaded
            if model_type in self.pipelines_cache:
                self.model_usage_count[model_type] = self.model_usage_count.get(model_type, 0) + 1
                return self.pipelines_cache[model_type]
            
            # Lazy load if not already loaded
            logger.info(f"Lazy loading model: {model_type}")
            
            # Run async loading in sync context (for compatibility)
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If we're in an async context, we can't use run_until_complete
                logger.warning(f"Cannot lazy load {model_type} in async context - please use await initialize_models()")
                return None
            else:
                success = loop.run_until_complete(self._load_model(model_type))
                if success:
                    self.model_load_times[model_type] = datetime.now(timezone.utc)
                    self.model_usage_count[model_type] = 1
                    return self.pipelines_cache.get(model_type)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get {model_type} pipeline: {e}")
            return None
    
    def get_sentiment_pipeline(self) -> Optional[Pipeline]:
        """Get sentiment analysis pipeline"""
        return self.get_model_pipeline('sentiment')
    
    def get_language_pipeline(self) -> Optional[Pipeline]:
        """Get language detection pipeline"""
        return self.get_model_pipeline('language')
    
    def get_category_pipeline(self) -> Optional[Pipeline]:
        """Get category classification pipeline"""
        return self.get_model_pipeline('category')
    
    def preprocess_text_for_model(self, text: str, model_type: str) -> str:
        """
        Preprocess text for specific model with proper tokenization limits
        Fixes tensor size mismatch issues
        """
        if not text:
            return ""
        
        config = self.MODEL_CONFIGS.get(model_type, {})
        max_length = config.get('max_length', 512)
        
        # Clean text
        import re
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Clean excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate to safe length (leaving room for special tokens)
        # For BERT-based models, reserve ~10% for special tokens
        safe_max_length = int(max_length * 0.9)
        
        if len(text) > safe_max_length:
            text = text[:safe_max_length]
        
        return text.strip()
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        return {
            "singleton_initialized": self._initialized,
            "models_loaded": list(self.pipelines_cache.keys()),
            "total_models_available": len(self.MODEL_CONFIGS),
            "device": self.device,
            "cache_directory": str(self.cache_dir),
            "model_load_times": {
                model: load_time.isoformat() 
                for model, load_time in self.model_load_times.items()
            },
            "model_usage_count": dict(self.model_usage_count),
            "memory_info": self._get_memory_info(),
            "system_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory usage information"""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            result = {
                "process_memory_mb": round(memory_info.rss / 1024 / 1024, 2),
                "process_memory_percent": round(process.memory_percent(), 2)
            }
            
            if torch.cuda.is_available():
                result.update({
                    "cuda_memory_allocated_mb": round(torch.cuda.memory_allocated() / 1024 / 1024, 2),
                    "cuda_memory_reserved_mb": round(torch.cuda.memory_reserved() / 1024 / 1024, 2),
                    "cuda_device_count": torch.cuda.device_count()
                })
            
            return result
        except Exception as e:
            logger.warning(f"Could not get memory info: {e}")
            return {"error": "Memory info unavailable"}
    
    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for AI system"""
        health_status = {
            "status": "healthy" if self._initialized else "unhealthy",
            "models_status": {},
            "system_ready": self._initialized,
            "last_check": datetime.now(timezone.utc).isoformat()
        }
        
        for model_type in self.MODEL_CONFIGS.keys():
            if model_type in self.pipelines_cache:
                health_status["models_status"][model_type] = {
                    "status": "loaded",
                    "usage_count": self.model_usage_count.get(model_type, 0),
                    "loaded_at": self.model_load_times.get(model_type, "unknown")
                }
            else:
                health_status["models_status"][model_type] = {
                    "status": "not_loaded",
                    "usage_count": 0
                }
        
        return health_status
    
    def clear_cache(self, models_to_clear: list = None):
        """
        Clear model cache with selective clearing
        """
        try:
            if models_to_clear is None:
                models_to_clear = list(self.pipelines_cache.keys())
            
            logger.info(f"Clearing AI models cache for: {models_to_clear}")
            
            for model_type in models_to_clear:
                if model_type in self.pipelines_cache:
                    del self.pipelines_cache[model_type]
                if model_type in self.model_load_times:
                    del self.model_load_times[model_type]
                if model_type in self.model_usage_count:
                    del self.model_usage_count[model_type]
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Clear CUDA cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(f"AI models cache cleared for: {models_to_clear}")
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

# Global singleton instance
ai_manager = AIManagerSingleton()