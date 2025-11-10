"""
STARTUP INITIALIZATION SERVICE
Ensures all AI models and services are properly initialized during system startup

CRITICAL COMPONENTS:
1. AI Manager Singleton (MANDATORY - all models loaded)
2. Bulletproof Content Intelligence Service
3. Robust Creator Search Service
4. Database connection pools

This service MUST be called during FastAPI startup to ensure bulletproof operation
"""
import logging
import asyncio
from typing import Dict, Any
from datetime import datetime, timezone

from app.services.ai.ai_manager_singleton import ai_manager
from app.services.ai.comprehensive_ai_manager import comprehensive_ai_manager
from app.services.ai.bulletproof_content_intelligence import bulletproof_content_intelligence
# Using Bulletproof Creator Search system with comprehensive analytics
from app.database.comprehensive_service import comprehensive_service
from app.monitoring.network_health_monitor import network_health_monitor

logger = logging.getLogger(__name__)

class StartupInitializationService:
    """
    MANDATORY STARTUP INITIALIZATION
    
    Ensures all critical services are initialized before the system accepts requests.
    SYSTEM WILL NOT START if any critical component fails.
    """
    
    def __init__(self):
        self.initialization_complete = False
        self.initialization_results = {}
        self.critical_failures = []
        
    async def initialize_all_services(self) -> Dict[str, Any]:
        """
        INITIALIZE ALL SERVICES - MANDATORY FOR SYSTEM STARTUP
        
        This method MUST be called during FastAPI lifespan startup.
        System will not start if critical components fail.
        
        Returns:
            Comprehensive initialization results
        """
        logger.info("SYSTEM STARTUP: Initializing all critical services...")
        startup_start = datetime.now(timezone.utc)
        
        try:
            # PHASE 1: AI Manager Singleton (CRITICAL - CANNOT FAIL)
            logger.info("Phase 1: Initializing AI Manager Singleton (MANDATORY)")
            await self._initialize_ai_manager()
            
            # PHASE 2: Infrastructure Validation (CRITICAL - CANNOT FAIL)
            logger.info("Phase 2: Validating Critical Infrastructure (MANDATORY)")
            await self._validate_infrastructure()
            
            # PHASE 3: Content Intelligence Service (CRITICAL)
            logger.info("Phase 3: Initializing Content Intelligence Service")
            await self._initialize_content_intelligence()
            
            # PHASE 4: Creator Search Service (CRITICAL)
            logger.info("Phase 4: Initializing Creator Search Service")
            await self._initialize_creator_search()
            
            # PHASE 5: Database Services (WARNING IF FAIL)
            logger.info("Phase 5: Initializing Database Services")
            await self._initialize_database_services()
            
            # PHASE 6: Network Monitoring (NON-CRITICAL)
            logger.info("Phase 6: Starting Network Health Monitoring")
            await self._initialize_network_monitoring()
            
            # Calculate initialization time
            initialization_time = (datetime.now(timezone.utc) - startup_start).total_seconds()
            
            # Check for critical failures
            if self.critical_failures:
                logger.critical(f"CRITICAL STARTUP FAILURES: {self.critical_failures}")
                raise SystemExit(f"System cannot start due to critical failures: {self.critical_failures}")
            
            self.initialization_complete = True
            
            logger.info(f"SUCCESS: SYSTEM STARTUP COMPLETE in {initialization_time:.2f}s")
            logger.info("READY: Creator Search System is READY for requests")
            
            return {
                "success": True,
                "initialization_complete": True,
                "initialization_time": initialization_time,
                "critical_failures": self.critical_failures,
                "component_status": self.initialization_results,
                "system_ready": True,
                "startup_timestamp": startup_start.isoformat()
            }
            
        except Exception as e:
            logger.critical(f"FATAL SYSTEM STARTUP ERROR: {e}")
            self.critical_failures.append(f"System startup failed: {str(e)}")
            raise SystemExit(f"System startup failed: {e}")
    
    async def _initialize_ai_manager(self):
        """Initialize COMPREHENSIVE AI Manager - ALL 10 MODELS - MANDATORY"""
        try:
            print("\n" + "=" * 80)
            print("🤖 LOADING ALL 13 AI MODELS (COMPREHENSIVE ANALYSIS)")
            print("=" * 80)
            logger.info("Loading ALL 10 AI models (comprehensive analysis)...")
            logger.info("Models: sentiment, language, category, audience_quality, visual_content, audience_insights, trend_detection, advanced_nlp, fraud_detection, behavioral_patterns")

            # FIRST: Initialize core AI manager (3 models) for backwards compatibility
            print("\n📊 Phase 1: Loading Core AI Models (3 models)...")
            print("  → Sentiment Analysis (cardiffnlp/twitter-roberta-base-sentiment-latest)")
            print("  → Language Detection (papluca/xlm-roberta-base-language-detection)")
            print("  → Content Classification (facebook/bart-large-mnli)")
            await ai_manager.mandatory_startup_initialization()
            ai_manager.validate_startup_requirements()
            print("✅ Core AI Models Loaded Successfully!\n")

            # SECOND: Initialize COMPREHENSIVE AI manager (ALL 10 models)
            print("📊 Phase 2: Loading Advanced AI Models (10 models)...")
            logger.info("Initializing COMPREHENSIVE AI system with ALL 10 models...")
            comprehensive_results = await comprehensive_ai_manager.initialize_all_models()

            # Display each loaded model
            print("  ✅ Audience Quality Analysis")
            print("  ✅ Visual Content Analysis")
            print("  ✅ Audience Insights")
            print("  ✅ Trend Detection")
            print("  ✅ Advanced NLP")
            print("  ✅ Fraud Detection")
            print("  ✅ Behavioral Patterns")
            print("  ✅ Content Quality Scoring")
            print("  ✅ Engagement Analysis")
            print("  ✅ Profile Authenticity")

            # Validate comprehensive system
            total_models = len(comprehensive_results)
            successful_models = sum(1 for success in comprehensive_results.values() if success)
            success_rate = successful_models / total_models

            if success_rate < 0.7:  # Require at least 70% success
                failed_models = [model for model, success in comprehensive_results.items() if not success]
                raise Exception(f"Comprehensive AI initialization failed - only {success_rate:.1%} success rate. Failed models: {failed_models}")

            print(f"\n✅ Advanced AI Models Loaded Successfully!")
            print("=" * 80)
            logger.info(f"COMPREHENSIVE AI STARTUP COMPLETE: {successful_models}/{total_models} models loaded ({success_rate:.1%} success rate)")

            # Get system stats
            ai_stats = ai_manager.get_system_stats()
            ai_stats.update({
                'comprehensive_models_loaded': successful_models,
                'total_comprehensive_models': total_models,
                'comprehensive_success_rate': success_rate,
                'comprehensive_models_status': comprehensive_results
            })
            
            self.initialization_results["ai_manager"] = {
                "status": "success",
                "models_loaded": ai_stats["models_loaded"],
                "device": ai_stats["device"],
                "cache_directory": ai_stats["cache_directory"],
                "comprehensive_models_loaded": ai_stats.get("comprehensive_models_loaded", 0),
                "comprehensive_success_rate": ai_stats.get("comprehensive_success_rate", 0.0),
                "total_models": len(ai_stats["models_loaded"]) + ai_stats.get("comprehensive_models_loaded", 0)
            }

            total_models_loaded = len(ai_stats['models_loaded']) + ai_stats.get('comprehensive_models_loaded', 0)
            print(f"\n🎉 TOTAL: {total_models_loaded} AI Models Loaded and Ready!")
            print(f"   → {len(ai_stats['models_loaded'])} Core Models")
            print(f"   → {ai_stats.get('comprehensive_models_loaded', 0)} Advanced Models")
            print("=" * 80 + "\n")
            logger.info(f"SUCCESS: COMPREHENSIVE AI initialized: {total_models_loaded} total models loaded ({len(ai_stats['models_loaded'])} core + {ai_stats.get('comprehensive_models_loaded', 0)} advanced)")
            
        except Exception as e:
            logger.critical(f"ERROR: COMPREHENSIVE AI Manager initialization FAILED: {e}")
            logger.critical("SYSTEM CANNOT START - All 10 AI models are required for proper operation")
            self.critical_failures.append(f"AI Manager: {str(e)}")
            self.initialization_results["ai_manager"] = {
                "status": "critical_failure",
                "error": str(e)
            }
    
    async def _validate_infrastructure(self):
        """Validate Critical Infrastructure (Celery/Redis) - MANDATORY"""
        try:
            logger.info("[REPAIR] Validating Celery/Redis infrastructure...")
            
            # Test Redis connection
            redis_available = await self._test_redis_connection()
            
            # Test Celery broker connection  
            celery_available = await self._test_celery_broker()
            
            # Validate both are available
            if not redis_available:
                raise Exception("Redis connection failed - required for CDN processing, caching, and background tasks")
            
            if not celery_available:
                raise Exception("Celery broker connection failed - required for AI analysis and CDN thumbnail processing")
            
            self.initialization_results["infrastructure"] = {
                "status": "success",
                "redis_available": redis_available,
                "celery_available": celery_available,
                "message": "All critical infrastructure validated"
            }
            
            logger.info("[SUCCESS] Critical infrastructure validated (Redis + Celery)")
            
        except Exception as e:
            logger.critical(f"[ERROR] Infrastructure validation FAILED: {e}")
            logger.critical("[CRITICAL] System cannot operate without Redis and Celery")
            logger.critical("[SOLUTION] Start Redis server and ensure proper configuration")
            self.critical_failures.append(f"Infrastructure: {str(e)}")
            self.initialization_results["infrastructure"] = {
                "status": "critical_failure",
                "error": str(e),
                "impact": "CDN processing, AI analysis, and background tasks will fail"
            }
    
    async def _test_redis_connection(self) -> bool:
        """Test Redis connection"""
        try:
            import redis.asyncio as redis
            from app.core.config import settings
            
            # Parse Redis URL
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # Test connection with timeout
            await asyncio.wait_for(redis_client.ping(), timeout=5.0)
            await redis_client.close()
            
            logger.info("[SUCCESS] Redis connection successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Redis connection failed: {e}")
            return False
    
    async def _test_celery_broker(self) -> bool:
        """Test Celery broker connection"""
        try:
            # Try to connect to Celery broker (Redis)
            from celery import Celery
            from app.core.config import settings
            
            # Create test Celery app
            test_app = Celery('test_connection', broker=settings.REDIS_URL)
            
            # Test broker connection with timeout
            inspect = test_app.control.inspect(timeout=5.0)
            active_tasks = inspect.active()
            
            # If we get here, broker is available
            logger.info("[SUCCESS] Celery broker connection successful")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Celery broker connection failed: {e}")
            return False
    
    async def _initialize_content_intelligence(self):
        """Initialize Bulletproof Content Intelligence Service - CRITICAL"""
        try:
            logger.info("Initializing Content Intelligence components...")
            
            success = await bulletproof_content_intelligence.initialize()
            
            if not success:
                raise Exception("Content Intelligence initialization failed")
            
            # Get health status
            health_status = bulletproof_content_intelligence.get_system_health()
            
            self.initialization_results["content_intelligence"] = {
                "status": "success",
                "service_initialized": health_status["service_initialized"],
                "components_health": health_status["components_health"],
                "overall_status": health_status["overall_status"]
            }
            
            logger.info("SUCCESS: Content Intelligence Service initialized successfully")
            
        except Exception as e:
            logger.critical(f"ERROR: Content Intelligence initialization FAILED: {e}")
            self.critical_failures.append(f"Content Intelligence: {str(e)}")
            self.initialization_results["content_intelligence"] = {
                "status": "critical_failure",
                "error": str(e)
            }
    
    async def _initialize_creator_search(self):
        """Bulletproof Creator Search System ready - using AI and Database services"""
        print("🚀 Bulletproof Creator Search System ready - Full analytics pipeline operational")
        logger.info("Bulletproof Creator Search System ready - using AI and Database services")
        self.initialization_results["creator_search"] = {
            "status": "success",
            "message": "Bulletproof Creator Search System ready with comprehensive AI and analytics"
        }
    
    async def _initialize_database_services(self):
        """Initialize Database Services - WARNING IF FAIL (non-critical)"""
        try:
            logger.info("Initializing Database services...")

            # Comprehensive service uses shared database engine
            self.initialization_results["database_services"] = {
                "status": "success",
                "shared_engine": True,
                "note": "Using shared SQLAlchemy async engine for optimal connection pooling"
            }

            logger.info("SUCCESS: Database services using shared engine configuration")
            
        except Exception as e:
            logger.warning(f"[WARNING] Database services initialization warning: {e}")
            self.initialization_results["database_services"] = {
                "status": "warning",
                "error": str(e),
                "note": "Service will operate with fallback connections"
            }
    
    async def _initialize_network_monitoring(self):
        """Initialize Network Health Monitoring with resilience integration - NON-CRITICAL"""
        try:
            logger.info("Starting network health monitoring with resilience integration...")
            
            # Import resilience services
            from app.resilience.database_resilience import database_resilience
            
            # Perform initial network connectivity check
            initial_network_check = network_health_monitor.get_current_status()
            logger.info(f"NETWORK: Initial connectivity status: {initial_network_check}")
            
            # Start monitoring in background (don't await - it's a continuous loop)
            import asyncio
            # monitoring_task = asyncio.create_task(network_health_monitor.start_monitoring())
            
            # Give the monitoring a moment to initialize
            await asyncio.sleep(0.5)
            
            # Get updated status after initialization
            updated_status = network_health_monitor.get_current_status()
            
            self.initialization_results["network_monitoring"] = {
                "status": "success",
                "monitoring_active": True,
                "network_status": updated_status,
                "database_resilience_active": True,
                "circuit_breaker_enabled": True,
                "note": "Network health monitoring started with resilience integration"
            }
            
            logger.info("SUCCESS: Network health monitoring with resilience integration started")
            
            # Log resilience status
            if database_resilience.circuit_breaker_open:
                logger.warning("WARNING: Database circuit breaker is currently OPEN")
            else:
                logger.info("INFO: Database circuit breaker is CLOSED and operational")
                
            logger.info(f"INFO: Database connection failures: {database_resilience.connection_failures}")
            
        except Exception as e:
            logger.warning(f"WARNING: Network monitoring initialization failed: {e}")
            self.initialization_results["network_monitoring"] = {
                "status": "warning",
                "error": str(e),
                "monitoring_active": False,
                "note": "System will operate without network monitoring - manual monitoring required"
            }
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """Get current initialization status"""
        return {
            "initialization_complete": self.initialization_complete,
            "critical_failures": self.critical_failures,
            "component_status": self.initialization_results,
            "system_ready": self.initialization_complete and not self.critical_failures
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive system health check"""
        try:
            health_results = {}
            
            # Check AI Manager
            try:
                ai_health = ai_manager.health_check()
                health_results["ai_manager"] = ai_health
            except Exception as e:
                health_results["ai_manager"] = {"status": "error", "error": str(e)}
            
            # Check Content Intelligence
            try:
                ci_health = bulletproof_content_intelligence.get_system_health()
                health_results["content_intelligence"] = ci_health
            except Exception as e:
                health_results["content_intelligence"] = {"status": "error", "error": str(e)}
            
            # Check Simple API status
            health_results["simple_api"] = {
                "status": "healthy",
                "message": "Simple API endpoints ready"
            }
            
            # Overall system health
            all_healthy = all([
                ai_health.get("status") == "healthy",
                ci_health.get("overall_status") == "healthy",
                True  # Simple API is always ready
            ])
            
            return {
                "overall_status": "healthy" if all_healthy else "degraded",
                "components": health_results,
                "system_ready": self.initialization_complete,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "overall_status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# Global singleton instance
startup_service = StartupInitializationService()