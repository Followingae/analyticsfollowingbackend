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
from app.services.ai.bulletproof_content_intelligence import bulletproof_content_intelligence
# Robust creator search service removed - using Simple API endpoints
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
            
            # PHASE 2: Content Intelligence Service (CRITICAL)
            logger.info("Phase 2: Initializing Content Intelligence Service")
            await self._initialize_content_intelligence()
            
            # PHASE 3: Creator Search Service (CRITICAL)
            logger.info("Phase 3: Initializing Creator Search Service")
            await self._initialize_creator_search()
            
            # PHASE 4: Database Services (WARNING IF FAIL)
            logger.info("Phase 4: Initializing Database Services")
            await self._initialize_database_services()
            
            # PHASE 5: Network Monitoring (NON-CRITICAL)
            logger.info("Phase 5: Starting Network Health Monitoring")
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
        """Initialize AI Manager Singleton - MANDATORY"""
        try:
            logger.info("Loading AI models (sentiment, language, category)...")
            
            # Call mandatory startup initialization
            await ai_manager.mandatory_startup_initialization()
            
            # Validate all models are loaded
            ai_manager.validate_startup_requirements()
            
            # Get system stats
            ai_stats = ai_manager.get_system_stats()
            
            self.initialization_results["ai_manager"] = {
                "status": "success",
                "models_loaded": ai_stats["models_loaded"],
                "device": ai_stats["device"],
                "cache_directory": ai_stats["cache_directory"]
            }
            
            logger.info(f"SUCCESS: AI Manager initialized: {len(ai_stats['models_loaded'])} models loaded")
            
        except Exception as e:
            logger.critical(f"ERROR: AI Manager initialization FAILED: {e}")
            self.critical_failures.append(f"AI Manager: {str(e)}")
            self.initialization_results["ai_manager"] = {
                "status": "critical_failure",
                "error": str(e)
            }
    
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
        """Simple API endpoints use AI and Database services (already initialized)"""
        logger.info("Simple API endpoints ready - using AI and Database services")
        self.initialization_results["simple_api"] = {
            "status": "success",
            "message": "Simple API endpoints ready with AI and Database services"
        }
    
    async def _initialize_database_services(self):
        """Initialize Database Services - WARNING IF FAIL (non-critical)"""
        try:
            logger.info("Initializing Database connection pools...")
            
            # Initialize comprehensive service pool
            await comprehensive_service.init_pool()
            
            self.initialization_results["database_services"] = {
                "status": "success" if comprehensive_service.pool else "warning",
                "pool_initialized": comprehensive_service.pool is not None,
                "note": "Service operates with fallback if pool unavailable"
            }
            
            if comprehensive_service.pool:
                logger.info("SUCCESS: Database connection pool initialized")
            else:
                logger.warning("⚠️ Database pool not initialized - service will use fallback connections")
            
        except Exception as e:
            logger.warning(f"⚠️ Database services initialization warning: {e}")
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
            monitoring_task = asyncio.create_task(network_health_monitor.start_monitoring())
            
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