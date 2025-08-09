from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # SmartProxy credentials
    SMARTPROXY_USERNAME: str = os.getenv("SMARTPROXY_USERNAME", "")
    SMARTPROXY_PASSWORD: str = os.getenv("SMARTPROXY_PASSWORD", "")
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("PORT", os.getenv("API_PORT", "8080")))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Rate Limiting
    MAX_REQUESTS_PER_HOUR: int = int(os.getenv("MAX_REQUESTS_PER_HOUR", "500"))
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
    
    # Instagram settings
    INSTAGRAM_POST_ANALYSIS_LIMIT: int = int(os.getenv("INSTAGRAM_POST_ANALYSIS_LIMIT", "50"))
    INSTAGRAM_FOLLOWER_SAMPLE_SIZE: int = int(os.getenv("INSTAGRAM_FOLLOWER_SAMPLE_SIZE", "1000"))
    
    # Redis (optional)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # Authentication Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-this-to-a-secure-secret-key-in-production")
    
    # SmartProxy/Decodo API endpoints
    SMARTPROXY_BASE_URL: str = "https://scraper-api.decodo.com/v2"
    SMARTPROXY_INSTAGRAM_ENDPOINT: str = f"{SMARTPROXY_BASE_URL}/scrape"
    
    # AI/ML Configuration
    AI_MODELS_CACHE_DIR: str = os.getenv("AI_MODELS_CACHE_DIR", "./ai_models")
    AI_BATCH_SIZE: int = int(os.getenv("AI_BATCH_SIZE", "16"))
    AI_MAX_WORKERS: int = int(os.getenv("AI_MAX_WORKERS", "2"))
    AI_MODEL_DEVICE: str = os.getenv("AI_MODEL_DEVICE", "cpu")  # cpu or cuda
    ENABLE_AI_ANALYSIS: bool = os.getenv("ENABLE_AI_ANALYSIS", "true").lower() == "true"
    AI_ANALYSIS_QUEUE_SIZE: int = int(os.getenv("AI_ANALYSIS_QUEUE_SIZE", "100"))
    
    class Config:
        case_sensitive = True


settings = Settings()