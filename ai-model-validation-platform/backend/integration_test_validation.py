#!/usr/bin/env python3
"""
Integration Test Validation Agent
Tests the complete application flow to verify all fixes are working together.
"""
import asyncio
import aiohttp
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class IntegrationTestValidator:
    def __init__(self):
        self.results = {}
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.db_path = "dev_database.db"
        self.start_time = datetime.now()
        
    async def test_backend_api_health(self) -> Dict[str, Any]:
        """Test backend API endpoints return 200 OK"""
        print("🔍 Testing Backend API Health...")
        
        endpoints = [
            "/api/projects",
            "/api/videos", 
            "/health",
            "/api/dashboard/stats"
        ]
        
        results = {}
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    url = f"{self.backend_url}{endpoint}"
                    async with session.get(url, timeout=10) as response:
                        results[endpoint] = {
                            "status_code": response.status,
                            "success": response.status == 200,
                            "content_type": response.headers.get('content-type', ''),
                            "response_time": time.time()
                        }
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                results[endpoint]["has_data"] = len(data) > 0 if isinstance(data, list) else bool(data)
                            except:
                                results[endpoint]["has_data"] = False
                                
                        print(f"  ✅ {endpoint}: {response.status}")
                        
                except Exception as e:
                    results[endpoint] = {
                        "status_code": 0,
                        "success": False,
                        "error": str(e)
                    }
                    print(f"  ❌ {endpoint}: {e}")
                    
        return results
    
    async def test_frontend_accessibility(self) -> Dict[str, Any]:
        """Test frontend pages are accessible"""
        print("🔍 Testing Frontend Accessibility...")
        
        pages = [
            "/",
            "/#/projects", 
            "/#/ground-truth",
            "/#/dashboard"
        ]
        
        results = {}
        
        async with aiohttp.ClientSession() as session:
            for page in pages:
                try:
                    url = f"{self.frontend_url}{page}"
                    async with session.get(url, timeout=15) as response:
                        content = await response.text()
                        
                        results[page] = {
                            "status_code": response.status,
                            "success": response.status == 200,
                            "has_react_app": "React App" in content or "root" in content,
                            "has_bundle": "bundle.js" in content,
                            "content_length": len(content)
                        }
                        
                        print(f"  ✅ {page}: {response.status} ({len(content)} chars)")
                        
                except Exception as e:
                    results[page] = {
                        "status_code": 0,
                        "success": False,
                        "error": str(e)
                    }
                    print(f"  ❌ {page}: {e}")
                    
        return results
    
    def test_database_enum_consistency(self) -> Dict[str, Any]:
        """Verify database enum values are consistent"""
        print("🔍 Testing Database Enum Consistency...")
        
        results = {
            "connection": False,
            "enum_checks": {},
            "tables_verified": []
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            results["connection"] = True
            
            # Check project status enum
            cursor.execute("SELECT DISTINCT status FROM projects WHERE status IS NOT NULL")
            project_statuses = [row[0] for row in cursor.fetchall()]
            
            valid_project_statuses = ['Active', 'active', 'Inactive', 'inactive', 'Complete', 'complete']
            invalid_statuses = [s for s in project_statuses if s not in valid_project_statuses]
            
            results["enum_checks"]["project_status"] = {
                "values_found": project_statuses,
                "invalid_values": invalid_statuses,
                "valid": len(invalid_statuses) == 0
            }
            
            # Check video processing status
            cursor.execute("SELECT DISTINCT processing_status FROM videos WHERE processing_status IS NOT NULL")
            processing_statuses = [row[0] for row in cursor.fetchall()]
            
            valid_processing_statuses = ['pending', 'processing', 'completed', 'error', 'failed']
            invalid_processing = [s for s in processing_statuses if s not in valid_processing_statuses]
            
            results["enum_checks"]["processing_status"] = {
                "values_found": processing_statuses,
                "invalid_values": invalid_processing,
                "valid": len(invalid_processing) == 0
            }
            
            # Check signal types
            cursor.execute("SELECT DISTINCT signalType FROM projects WHERE signalType IS NOT NULL")
            signal_types = [row[0] for row in cursor.fetchall()]
            
            valid_signal_types = ['GPIO', 'Network Packet', 'Serial', 'CAN', 'ADC', 'PWM']
            invalid_signals = [s for s in signal_types if s not in valid_signal_types]
            
            results["enum_checks"]["signal_type"] = {
                "values_found": signal_types,
                "invalid_values": invalid_signals,
                "valid": len(invalid_signals) == 0
            }
            
            results["tables_verified"] = ["projects", "videos"]
            
            # Count total records
            cursor.execute("SELECT COUNT(*) FROM projects")
            results["project_count"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos") 
            results["video_count"] = cursor.fetchone()[0]
            
            conn.close()
            
            print(f"  ✅ Database connected, {results['project_count']} projects, {results['video_count']} videos")
            
            for check_name, check_data in results["enum_checks"].items():
                if check_data["valid"]:
                    print(f"  ✅ {check_name}: All values valid")
                else:
                    print(f"  ❌ {check_name}: Invalid values found: {check_data['invalid_values']}")
                    
        except Exception as e:
            results["error"] = str(e)
            print(f"  ❌ Database test failed: {e}")
            
        return results
    
    async def test_api_integration(self) -> Dict[str, Any]:
        """Test API integration with actual data flow"""
        print("🔍 Testing API Integration...")
        
        results = {}
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test projects API with data validation
                async with session.get(f"{self.backend_url}/api/projects") as response:
                    if response.status == 200:
                        projects = await response.json()
                        results["projects_api"] = {
                            "success": True,
                            "project_count": len(projects),
                            "has_required_fields": all(
                                all(field in project for field in ['id', 'name', 'status'])
                                for project in projects
                            ) if projects else True
                        }
                    else:
                        results["projects_api"] = {"success": False, "status": response.status}
                
                # Test dashboard stats
                try:
                    async with session.get(f"{self.backend_url}/api/dashboard/stats") as response:
                        if response.status == 200:
                            stats = await response.json()
                            results["dashboard_stats"] = {
                                "success": True,
                                "has_stats": isinstance(stats, dict) and len(stats) > 0
                            }
                        else:
                            results["dashboard_stats"] = {"success": False, "status": response.status}
                except Exception as e:
                    results["dashboard_stats"] = {"success": False, "error": str(e)}
                
        except Exception as e:
            results["error"] = str(e)
            print(f"  ❌ API integration test failed: {e}")
            
        return results
    
    def test_critical_file_structure(self) -> Dict[str, Any]:
        """Test that critical files exist and are readable"""
        print("🔍 Testing Critical File Structure...")
        
        critical_files = [
            "main.py",
            "config.py", 
            "models.py",
            "dev_database.db",
            "../frontend/package.json",
            "../frontend/src/App.tsx",
            "../frontend/src/pages/Projects.tsx",
            "../frontend/src/pages/GroundTruth.tsx"
        ]
        
        results = {"files_checked": {}, "all_critical_exist": True}
        
        for file_path in critical_files:
            path = Path(file_path)
            exists = path.exists()
            
            if exists:
                try:
                    size = path.stat().st_size
                    readable = path.is_file() and size > 0
                    results["files_checked"][file_path] = {
                        "exists": True,
                        "readable": readable,
                        "size": size
                    }
                    print(f"  ✅ {file_path}: {size} bytes")
                except:
                    results["files_checked"][file_path] = {"exists": True, "readable": False}
                    print(f"  ⚠️  {file_path}: exists but not readable")
            else:
                results["files_checked"][file_path] = {"exists": False, "readable": False}
                results["all_critical_exist"] = False
                print(f"  ❌ {file_path}: missing")
                
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all integration tests"""
        print("🚀 Starting Comprehensive Integration Test")
        print("=" * 60)
        
        # Run all tests
        backend_results = await self.test_backend_api_health()
        frontend_results = await self.test_frontend_accessibility() 
        database_results = self.test_database_enum_consistency()
        api_results = await self.test_api_integration()
        file_results = self.test_critical_file_structure()
        
        # Calculate overall health
        backend_health = all(r.get("success", False) for r in backend_results.values())
        frontend_health = all(r.get("success", False) for r in frontend_results.values())
        database_health = database_results.get("connection", False) and all(
            check.get("valid", False) for check in database_results.get("enum_checks", {}).values()
        )
        api_health = all(r.get("success", False) for r in api_results.values() if "error" not in api_results)
        file_health = file_results.get("all_critical_exist", False)
        
        overall_health = all([backend_health, frontend_health, database_health, api_health, file_health])
        
        # Compile final results
        final_results = {
            "test_metadata": {
                "timestamp": datetime.now().isoformat(),
                "test_duration_seconds": (datetime.now() - self.start_time).total_seconds(),
                "tester": "Integration Test Validation Agent"
            },
            "overall_health": {
                "status": "PASS" if overall_health else "FAIL",
                "backend_healthy": backend_health,
                "frontend_healthy": frontend_health,
                "database_healthy": database_health,
                "api_healthy": api_health,
                "files_healthy": file_health
            },
            "component_results": {
                "backend_api": backend_results,
                "frontend_pages": frontend_results,
                "database_enums": database_results,
                "api_integration": api_results,
                "file_structure": file_results
            }
        }
        
        # Print summary
        print("\n" + "=" * 60)
        print("📋 INTEGRATION TEST SUMMARY")
        print("=" * 60)
        
        status_symbol = "✅" if overall_health else "❌"
        print(f"{status_symbol} Overall System Health: {'PASS' if overall_health else 'FAIL'}")
        
        components = [
            ("Backend API", backend_health),
            ("Frontend Pages", frontend_health), 
            ("Database Enums", database_health),
            ("API Integration", api_health),
            ("File Structure", file_health)
        ]
        
        for name, health in components:
            symbol = "✅" if health else "❌"
            print(f"{symbol} {name}: {'HEALTHY' if health else 'ISSUES'}")
            
        if not overall_health:
            print("\n⚠️  ISSUES DETECTED:")
            if not backend_health:
                print("  - Backend API endpoints failing")
            if not frontend_health:
                print("  - Frontend pages not accessible")
            if not database_health:
                print("  - Database enum consistency issues")
            if not api_health:
                print("  - API integration problems")
            if not file_health:
                print("  - Critical files missing")
                
        print(f"\n📊 Test Duration: {(datetime.now() - self.start_time).total_seconds():.2f} seconds")
        print("=" * 60)
        
        return final_results

async def main():
    """Main test execution"""
    validator = IntegrationTestValidator()
    
    # Wait for servers to fully start
    print("⏳ Waiting for servers to fully initialize...")
    await asyncio.sleep(5)
    
    # Run comprehensive test
    results = await validator.run_comprehensive_test()
    
    # Save results to file
    results_file = f"integration_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Full results saved to: {results_file}")
    
    # Return exit code based on overall health
    exit_code = 0 if results["overall_health"]["status"] == "PASS" else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())