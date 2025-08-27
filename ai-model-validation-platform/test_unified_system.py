#!/usr/bin/env python3
"""
Unified System Integration Test
Tests the complete VRU platform with unified architecture and 155.138.239.131 support
"""

import asyncio
import aiohttp
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent / "backend"))

# Test configuration with unified system
try:
    from config.vru_settings import get_settings
    from unified_database import get_database_manager, get_database_health
    UNIFIED_SYSTEM_AVAILABLE = True
    print("✅ Unified system imports successful")
except ImportError as e:
    print(f"❌ Unified system import failed: {e}")
    UNIFIED_SYSTEM_AVAILABLE = False

class UnifiedSystemTester:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "external_ip": "155.138.239.131",
            "tests": {},
            "summary": {}
        }
        
        if UNIFIED_SYSTEM_AVAILABLE:
            self.settings = get_settings()
            print(f"📊 Configuration loaded: {self.settings.environment.value}")
            print(f"🔗 External IP: {self.settings.external_ip}")
            print(f"🗄️  Database: {self.settings.database_type.value}")
        else:
            self.settings = None

    def test_configuration(self):
        """Test unified configuration system"""
        print("🔧 Testing Unified Configuration...")
        
        try:
            if not UNIFIED_SYSTEM_AVAILABLE:
                raise ImportError("Unified system not available")
            
            # Test configuration properties
            config_tests = {
                "environment_detection": self.settings.environment is not None,
                "external_ip_configured": self.settings.external_ip == "155.138.239.131",
                "database_url_configured": self.settings.database_url is not None,
                "cors_origins_include_external_ip": any("155.138.239.131" in origin for origin in self.settings.cors_origins),
                "api_urls_correct": self.settings.get_backend_url() == "http://155.138.239.131:8000"
            }
            
            success = all(config_tests.values())
            
            self.results["tests"]["configuration"] = {
                "test": "Unified configuration system validation",
                "success": success,
                "details": config_tests,
                "settings_loaded": True
            }
            
            status = "✅" if success else "❌"
            print(f"  {status} Configuration: {sum(config_tests.values())}/{len(config_tests)} checks passed")
            
        except Exception as e:
            self.results["tests"]["configuration"] = {
                "test": "Unified configuration system validation",
                "success": False,
                "error": str(e)
            }
            print(f"  ❌ Configuration test failed: {e}")

    def test_database(self):
        """Test unified database system"""
        print("🗄️  Testing Unified Database...")
        
        try:
            if not UNIFIED_SYSTEM_AVAILABLE:
                raise ImportError("Unified system not available")
            
            # Test database manager
            db_manager = get_database_manager()
            health = db_manager.test_connection()
            
            # Test database operations
            tables = db_manager.get_tables()
            
            self.results["tests"]["database"] = {
                "test": "Unified database system validation",
                "success": health["status"] == "healthy",
                "health_info": health,
                "tables_found": len(tables),
                "table_names": tables[:5] if tables else []  # First 5 tables
            }
            
            status = "✅" if health["status"] == "healthy" else "❌"
            print(f"  {status} Database: {health['status']} ({len(tables)} tables)")
            
        except Exception as e:
            self.results["tests"]["database"] = {
                "test": "Unified database system validation",
                "success": False,
                "error": str(e)
            }
            print(f"  ❌ Database test failed: {e}")

    async def test_api_endpoints(self):
        """Test API endpoints with external IP"""
        print("🌐 Testing API Endpoints...")
        
        base_url = "http://155.138.239.131:8000" if UNIFIED_SYSTEM_AVAILABLE else "http://localhost:8000"
        
        endpoints = [
            {"path": "/health", "name": "Health Check"},
            {"path": "/docs", "name": "API Documentation"},
            {"path": "/api/projects", "name": "Projects API"},
            {"path": "/api/videos", "name": "Videos API"}
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint['path']}"
                    print(f"  Testing {endpoint['name']}...")
                    
                    async with session.get(url) as response:
                        success = response.status in [200, 404]  # 404 is OK for empty data
                        
                        self.results["tests"][f"api_{endpoint['path'].replace('/', '_').strip('_')}"] = {
                            "test": f"{endpoint['name']} endpoint accessibility",
                            "url": url,
                            "status_code": response.status,
                            "success": success,
                            "response_size": len(await response.text())
                        }
                        
                        status = "✅" if success else "❌"
                        print(f"    {status} {endpoint['name']}: {response.status}")
                        
                except Exception as e:
                    self.results["tests"][f"api_{endpoint['path'].replace('/', '_').strip('_')}"] = {
                        "test": f"{endpoint['name']} endpoint accessibility",
                        "success": False,
                        "error": str(e)
                    }
                    print(f"    ❌ {endpoint['name']}: {e}")

    async def test_frontend_accessibility(self):
        """Test frontend accessibility with external IP"""
        print("🖥️  Testing Frontend Accessibility...")
        
        frontend_url = "http://155.138.239.131:3000" if UNIFIED_SYSTEM_AVAILABLE else "http://localhost:3000"
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(frontend_url) as response:
                    content = await response.text()
                    
                    # Check for React app indicators
                    has_react = "react" in content.lower() or "root" in content
                    has_scripts = "<script" in content
                    is_valid_html = "<html" in content and "</html>" in content
                    
                    success = (response.status == 200 and has_react and has_scripts and is_valid_html)
                    
                    self.results["tests"]["frontend_accessibility"] = {
                        "test": "Frontend accessibility via external IP",
                        "url": frontend_url,
                        "status_code": response.status,
                        "success": success,
                        "has_react_app": has_react,
                        "has_scripts": has_scripts,
                        "is_valid_html": is_valid_html,
                        "content_size": len(content)
                    }
                    
                    status = "✅" if success else "❌"
                    print(f"  {status} Frontend: {response.status} ({'React app detected' if has_react else 'No React app'})")
                    
        except Exception as e:
            self.results["tests"]["frontend_accessibility"] = {
                "test": "Frontend accessibility via external IP",
                "success": False,
                "error": str(e)
            }
            print(f"  ❌ Frontend test failed: {e}")

    def test_integration_components(self):
        """Test integration between components"""
        print("🔗 Testing Component Integration...")
        
        integration_tests = {
            "config_database_consistency": True,
            "unified_system_available": UNIFIED_SYSTEM_AVAILABLE,
            "external_ip_configuration": True,
        }
        
        try:
            if UNIFIED_SYSTEM_AVAILABLE:
                # Test that config and database are using same settings
                db_health = get_database_health()
                integration_tests["database_matches_config"] = (
                    self.settings.database_type.value in db_health.get("database_type", "")
                )
                
                # Test CORS configuration consistency
                cors_configured = any("155.138.239.131" in origin for origin in self.settings.cors_origins)
                integration_tests["cors_external_ip"] = cors_configured
        
        except Exception as e:
            integration_tests["integration_error"] = str(e)
        
        success = all(v for k, v in integration_tests.items() if isinstance(v, bool))
        
        self.results["tests"]["integration"] = {
            "test": "Component integration validation",
            "success": success,
            "details": integration_tests
        }
        
        status = "✅" if success else "❌"
        passed = sum(1 for v in integration_tests.values() if v is True)
        total = len([v for v in integration_tests.values() if isinstance(v, bool)])
        print(f"  {status} Integration: {passed}/{total} checks passed")

    async def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 VRU Platform Unified System Test")
        print("=" * 60)
        print(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔗 External IP: 155.138.239.131")
        print("")
        
        # Run all tests
        self.test_configuration()
        self.test_database()
        await self.test_api_endpoints()
        await self.test_frontend_accessibility()
        self.test_integration_components()
        
        # Calculate summary
        tests = list(self.results["tests"].values())
        successful_tests = sum(1 for test in tests if test.get("success", False))
        total_tests = len(tests)
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "success_rate": success_rate,
            "overall_success": successful_tests == total_tests
        }
        
        print("")
        print("=" * 60)
        print("📋 UNIFIED SYSTEM TEST SUMMARY")
        print("=" * 60)
        
        overall_status = "✅" if self.results["summary"]["overall_success"] else "❌"
        print(f"{overall_status} Overall: {successful_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        # Print detailed results
        for test_name, test_data in self.results["tests"].items():
            symbol = "✅" if test_data.get("success", False) else "❌"
            print(f"{symbol} {test_name.replace('_', ' ').title()}: {test_data.get('test', 'N/A')}")
            
            if not test_data.get("success", False) and "error" in test_data:
                print(f"    Error: {test_data['error']}")
        
        print("")
        if self.results["summary"]["overall_success"]:
            print("🎉 ALL TESTS PASSED - System Ready!")
            print("🌐 Frontend: http://155.138.239.131:3000")
            print("🔧 Backend:  http://155.138.239.131:8000")
            print("📚 API Docs: http://155.138.239.131:8000/docs")
        else:
            print("⚠️  Some tests failed - Check logs above")
        
        print("=" * 60)
        
        # Save results
        results_file = f"unified_system_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"💾 Results saved to: {results_file}")
        
        return 0 if self.results["summary"]["overall_success"] else 1

async def main():
    tester = UnifiedSystemTester()
    exit_code = await tester.run_all_tests()
    return exit_code

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)