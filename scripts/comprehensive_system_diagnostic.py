#!/usr/bin/env python3
"""
Comprehensive System Diagnostic Script
Diagnoses and fixes common system issues to prevent them from recurring

Usage: python scripts/comprehensive_system_diagnostic.py [--fix-all]
"""

import asyncio
import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, List
import json
from datetime import datetime

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemDiagnostic:
    """
    Comprehensive system health diagnostic and repair tool
    """
    
    def __init__(self, auto_fix: bool = False):
        self.auto_fix = auto_fix
        self.issues_found = []
        self.fixes_applied = []
        self.warnings = []
        
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """
        Run complete system diagnostic
        """
        print("=" * 80)
        print("ANALYTICS FOLLOWING BACKEND - COMPREHENSIVE SYSTEM DIAGNOSTIC")
        print("=" * 80)
        print(f"Diagnostic Mode: {'AUTO-FIX ENABLED' if self.auto_fix else 'ANALYSIS ONLY'}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()
        
        diagnostic_report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "auto_fix" if self.auto_fix else "analysis",
            "tests": {},
            "overall_status": "unknown",
            "issues_found": [],
            "fixes_applied": [],
            "recommendations": []
        }
        
        # 1. Database Connectivity Test
        print("🔍 1. TESTING DATABASE CONNECTIVITY...")
        db_result = await self._test_database_connectivity()
        diagnostic_report["tests"]["database_connectivity"] = db_result
        self._print_test_result("Database Connectivity", db_result)
        
        # 2. Missing API Endpoints Test
        print("🔍 2. CHECKING API ENDPOINTS...")
        api_result = await self._check_api_endpoints()
        diagnostic_report["tests"]["api_endpoints"] = api_result
        self._print_test_result("API Endpoints", api_result)
        
        # 3. Circuit Breaker Status
        print("🔍 3. CHECKING CIRCUIT BREAKER STATUS...")
        cb_result = await self._check_circuit_breaker()
        diagnostic_report["tests"]["circuit_breaker"] = cb_result
        self._print_test_result("Circuit Breaker", cb_result)
        
        # 4. Database Schema Validation
        print("🔍 4. VALIDATING DATABASE SCHEMA...")
        schema_result = await self._validate_database_schema()
        diagnostic_report["tests"]["database_schema"] = schema_result
        self._print_test_result("Database Schema", schema_result)
        
        # 5. Redis/Cache Connectivity
        print("🔍 5. TESTING CACHE CONNECTIVITY...")
        cache_result = await self._test_cache_connectivity()
        diagnostic_report["tests"]["cache_connectivity"] = cache_result
        self._print_test_result("Cache Connectivity", cache_result)
        
        # 6. AI Services Health
        print("🔍 6. TESTING AI SERVICES...")
        ai_result = await self._test_ai_services()
        diagnostic_report["tests"]["ai_services"] = ai_result
        self._print_test_result("AI Services", ai_result)
        
        # 7. Environment Configuration
        print("🔍 7. VALIDATING ENVIRONMENT CONFIGURATION...")
        env_result = await self._validate_environment()
        diagnostic_report["tests"]["environment"] = env_result
        self._print_test_result("Environment Config", env_result)
        
        # Compile final report
        diagnostic_report["issues_found"] = self.issues_found
        diagnostic_report["fixes_applied"] = self.fixes_applied
        diagnostic_report["warnings"] = self.warnings
        
        # Determine overall status
        test_results = [test["status"] for test in diagnostic_report["tests"].values()]
        if "critical" in test_results:
            diagnostic_report["overall_status"] = "critical"
        elif "warning" in test_results:
            diagnostic_report["overall_status"] = "warning"
        else:
            diagnostic_report["overall_status"] = "healthy"
        
        # Generate recommendations
        diagnostic_report["recommendations"] = self._generate_recommendations()
        
        # Print final report
        self._print_final_report(diagnostic_report)
        
        return diagnostic_report
    
    async def _test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity and fix common issues"""
        try:
            from app.database.connection import init_database, get_session
            from sqlalchemy import text
            
            # Initialize database
            await init_database()
            
            # Test basic connectivity
            async with get_session() as session:
                result = await session.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value == 1:
                    # Test critical tables
                    critical_tables = ["profiles", "posts", "users", "credit_wallets"]
                    table_results = {}
                    
                    for table in critical_tables:
                        try:
                            await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                            table_results[table] = "accessible"
                        except Exception as e:
                            table_results[table] = f"error: {str(e)}"
                            self.issues_found.append(f"Table {table} not accessible: {e}")
                    
                    return {
                        "status": "healthy",
                        "message": "Database connectivity successful",
                        "details": {
                            "connection_test": "passed",
                            "table_access": table_results
                        }
                    }
                else:
                    self.issues_found.append("Database connection test returned unexpected result")
                    return {
                        "status": "critical",
                        "message": "Database connection test failed",
                        "error": f"Expected 1, got {test_value}"
                    }
                    
        except Exception as e:
            self.issues_found.append(f"Database connectivity failed: {str(e)}")
            
            # Try to fix common issues
            if self.auto_fix:
                fix_result = await self._fix_database_connectivity(str(e))
                if fix_result["success"]:
                    self.fixes_applied.append(fix_result["action"])
                    return {
                        "status": "warning",
                        "message": "Database connectivity fixed",
                        "fix_applied": fix_result["action"]
                    }
            
            return {
                "status": "critical",
                "message": "Database connectivity failed",
                "error": str(e)
            }
    
    async def _check_api_endpoints(self) -> Dict[str, Any]:
        """Check for missing API endpoints"""
        try:
            from app.api.simple_creator_search_routes import router as simple_router
            
            # Check if critical endpoints exist
            required_endpoints = [
                "/creator/system/stats",
                "/creator/unlocked",
                "/creator/search/{username}"
            ]
            
            endpoint_status = {}
            missing_endpoints = []
            
            # Get router paths
            router_paths = [route.path for route in simple_router.routes]
            
            for endpoint in required_endpoints:
                # Convert template to check format
                check_path = endpoint.replace("{username}", "{param}")
                if any(check_path in path or endpoint.split("/")[-1] in path for path in router_paths):
                    endpoint_status[endpoint] = "found"
                else:
                    endpoint_status[endpoint] = "missing"
                    missing_endpoints.append(endpoint)
                    self.issues_found.append(f"Missing API endpoint: {endpoint}")
            
            if missing_endpoints:
                if self.auto_fix:
                    # Auto-fix would require code generation, so just warn
                    self.warnings.append("Missing endpoints detected - manual code review required")
                
                return {
                    "status": "warning",
                    "message": f"Missing {len(missing_endpoints)} endpoints",
                    "details": {
                        "missing_endpoints": missing_endpoints,
                        "all_endpoints": endpoint_status
                    }
                }
            else:
                return {
                    "status": "healthy",
                    "message": "All required endpoints found",
                    "details": endpoint_status
                }
                
        except Exception as e:
            self.issues_found.append(f"API endpoint check failed: {str(e)}")
            return {
                "status": "critical",
                "message": "Could not check API endpoints",
                "error": str(e)
            }
    
    async def _check_circuit_breaker(self) -> Dict[str, Any]:
        """Check and fix circuit breaker issues"""
        try:
            from app.resilience.database_resilience import database_resilience
            
            status = database_resilience.get_status()
            
            if status["circuit_breaker_open"]:
                self.issues_found.append("Circuit breaker is open")
                
                if self.auto_fix:
                    database_resilience.reset_circuit_breaker()
                    self.fixes_applied.append("Circuit breaker reset")
                    return {
                        "status": "warning",
                        "message": "Circuit breaker was open - reset applied",
                        "fix_applied": "Circuit breaker reset",
                        "details": status
                    }
                else:
                    return {
                        "status": "critical",
                        "message": "Circuit breaker is open",
                        "details": status,
                        "recommendation": "Run with --fix-all to reset circuit breaker"
                    }
            else:
                return {
                    "status": "healthy",
                    "message": "Circuit breaker operational",
                    "details": status
                }
                
        except Exception as e:
            self.issues_found.append(f"Circuit breaker check failed: {str(e)}")
            return {
                "status": "critical", 
                "message": "Could not check circuit breaker",
                "error": str(e)
            }
    
    async def _validate_database_schema(self) -> Dict[str, Any]:
        """Validate database schema integrity"""
        try:
            from app.database.connection import get_session
            from sqlalchemy import text
            
            async with get_session() as session:
                # Check critical table columns
                table_checks = {
                    "profiles": ["username", "followers_count", "ai_primary_content_type"],
                    "posts": ["caption", "likes_count", "ai_content_category"],
                    "users": ["email", "role", "credits"],
                    "credit_wallets": ["user_id", "current_balance"]
                }
                
                schema_issues = []
                
                for table, columns in table_checks.items():
                    try:
                        # Check if table exists and has required columns
                        result = await session.execute(text(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = '{table}'
                        """))
                        
                        existing_columns = [row[0] for row in result.fetchall()]
                        missing_columns = [col for col in columns if col not in existing_columns]
                        
                        if missing_columns:
                            schema_issues.append(f"Table {table} missing columns: {missing_columns}")
                        
                    except Exception as e:
                        schema_issues.append(f"Could not check table {table}: {str(e)}")
                
                if schema_issues:
                    self.issues_found.extend(schema_issues)
                    return {
                        "status": "warning",
                        "message": f"Schema issues found: {len(schema_issues)}",
                        "details": {"issues": schema_issues}
                    }
                else:
                    return {
                        "status": "healthy",
                        "message": "Database schema validation passed"
                    }
                    
        except Exception as e:
            self.issues_found.append(f"Schema validation failed: {str(e)}")
            return {
                "status": "critical",
                "message": "Could not validate database schema",
                "error": str(e)
            }
    
    async def _test_cache_connectivity(self) -> Dict[str, Any]:
        """Test Redis cache connectivity"""
        try:
            import redis
            import os
            
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            r = redis.from_url(redis_url)
            
            # Test connection
            r.ping()
            
            # Test basic operations
            r.set("diagnostic_test", "success", ex=60)
            test_value = r.get("diagnostic_test")
            r.delete("diagnostic_test")
            
            if test_value and test_value.decode() == "success":
                return {
                    "status": "healthy",
                    "message": "Cache connectivity successful",
                    "details": {"redis_url": redis_url.split('@')[0] if '@' in redis_url else redis_url}
                }
            else:
                self.issues_found.append("Cache read/write test failed")
                return {
                    "status": "warning",
                    "message": "Cache connectivity issues",
                    "details": {"test_result": str(test_value)}
                }
                
        except Exception as e:
            self.warnings.append(f"Cache unavailable: {str(e)}")
            return {
                "status": "warning",
                "message": "Cache unavailable - system will function with reduced performance",
                "error": str(e)
            }
    
    async def _test_ai_services(self) -> Dict[str, Any]:
        """Test AI services functionality"""
        try:
            from app.services.ai.bulletproof_content_intelligence import BulletproofContentIntelligence
            
            ai_service = BulletproofContentIntelligence()
            
            # Test sentiment analysis
            test_result = await ai_service.analyze_sentiment("This is a test message")
            
            if test_result and test_result.get("success"):
                return {
                    "status": "healthy",
                    "message": "AI services operational",
                    "details": {"test_result": test_result}
                }
            else:
                self.warnings.append("AI services test failed")
                return {
                    "status": "warning",
                    "message": "AI services may be degraded",
                    "details": {"test_result": test_result}
                }
                
        except Exception as e:
            self.warnings.append(f"AI services unavailable: {str(e)}")
            return {
                "status": "warning", 
                "message": "AI services unavailable - basic functionality will continue",
                "error": str(e)
            }
    
    async def _validate_environment(self) -> Dict[str, Any]:
        """Validate environment configuration"""
        required_env_vars = [
            "DATABASE_URL",
            "SUPABASE_URL", 
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_ROLE_KEY"
        ]
        
        missing_vars = []
        placeholder_vars = []
        
        for var in required_env_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            elif "[YOUR-" in value or "placeholder" in value.lower():
                placeholder_vars.append(var)
        
        issues = missing_vars + placeholder_vars
        
        if issues:
            self.issues_found.extend([f"Environment variable issue: {var}" for var in issues])
            return {
                "status": "critical" if missing_vars else "warning",
                "message": f"Environment configuration issues: {len(issues)}",
                "details": {
                    "missing_vars": missing_vars,
                    "placeholder_vars": placeholder_vars
                }
            }
        else:
            return {
                "status": "healthy",
                "message": "Environment configuration valid"
            }
    
    async def _fix_database_connectivity(self, error_message: str) -> Dict[str, Any]:
        """Attempt to fix common database connectivity issues"""
        try:
            # Reset circuit breaker
            from app.resilience.database_resilience import database_resilience
            database_resilience.reset_circuit_breaker()
            
            # Re-initialize database
            from app.database.connection import init_database
            await init_database()
            
            return {
                "success": True,
                "action": "Database connectivity reset and re-initialized"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on diagnostic results"""
        recommendations = []
        
        if self.issues_found:
            recommendations.append(f"🚨 CRITICAL: {len(self.issues_found)} issues found requiring attention")
            
            if not self.auto_fix:
                recommendations.append("💡 TIP: Run with --fix-all flag to automatically fix resolvable issues")
        
        if self.warnings:
            recommendations.append(f"⚠️ WARNING: {len(self.warnings)} warnings - system will function but performance may be reduced")
        
        if self.fixes_applied:
            recommendations.append(f"✅ SUCCESS: {len(self.fixes_applied)} fixes applied automatically")
        
        # Specific recommendations
        if any("circuit breaker" in issue.lower() for issue in self.issues_found):
            recommendations.append("🔧 SUGGESTION: Consider implementing automatic circuit breaker reset in production")
        
        if any("endpoint" in issue.lower() for issue in self.issues_found):
            recommendations.append("🔧 SUGGESTION: Review API routing configuration and endpoint implementations")
        
        if not recommendations:
            recommendations.append("✅ EXCELLENT: System is healthy and operating normally")
        
        return recommendations
    
    def _print_test_result(self, test_name: str, result: Dict[str, Any]):
        """Print formatted test result"""
        status = result["status"]
        message = result["message"]
        
        status_symbols = {
            "healthy": "✅",
            "warning": "⚠️", 
            "critical": "❌"
        }
        
        symbol = status_symbols.get(status, "❓")
        print(f"   {symbol} {test_name}: {message}")
        
        if "error" in result:
            print(f"      Error: {result['error']}")
        
        if "fix_applied" in result:
            print(f"      🔧 Fix Applied: {result['fix_applied']}")
        
        print()
    
    def _print_final_report(self, report: Dict[str, Any]):
        """Print comprehensive final report"""
        print("=" * 80)
        print("DIAGNOSTIC REPORT SUMMARY")
        print("=" * 80)
        print(f"Overall Status: {report['overall_status'].upper()}")
        print(f"Issues Found: {len(report['issues_found'])}")
        print(f"Fixes Applied: {len(report['fixes_applied'])}")
        print(f"Warnings: {len(report['warnings'])}")
        print()
        
        if report["issues_found"]:
            print("🚨 ISSUES FOUND:")
            for i, issue in enumerate(report["issues_found"], 1):
                print(f"   {i}. {issue}")
            print()
        
        if report["fixes_applied"]:
            print("✅ FIXES APPLIED:")
            for i, fix in enumerate(report["fixes_applied"], 1):
                print(f"   {i}. {fix}")
            print()
        
        if report["warnings"]:
            print("⚠️ WARNINGS:")
            for i, warning in enumerate(report["warnings"], 1):
                print(f"   {i}. {warning}")
            print()
        
        print("📋 RECOMMENDATIONS:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"   {i}. {rec}")
        print()
        
        print("=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)

async def main():
    """Main diagnostic function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive System Diagnostic")
    parser.add_argument("--fix-all", action="store_true", help="Automatically fix resolvable issues")
    parser.add_argument("--save-report", type=str, help="Save diagnostic report to file")
    
    args = parser.parse_args()
    
    # Run diagnostic
    diagnostic = SystemDiagnostic(auto_fix=args.fix_all)
    report = await diagnostic.run_full_diagnostic()
    
    # Save report if requested
    if args.save_report:
        with open(args.save_report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"📄 Report saved to: {args.save_report}")
    
    # Exit with appropriate code
    if report["overall_status"] == "critical":
        sys.exit(1)
    elif report["overall_status"] == "warning":
        sys.exit(2)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())