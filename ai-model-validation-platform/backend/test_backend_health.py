"""
Comprehensive Backend Health and Functionality Test
Tests all major backend components and endpoints
"""
import logging
import asyncio
import sys
import os
import traceback
from datetime import datetime
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BackendHealthChecker:
    """Comprehensive backend health checker"""
    
    def __init__(self):
        self.test_results = {}
        self.passed_tests = 0
        self.failed_tests = 0
    
    def run_test(self, test_name: str, test_func):
        """Run a test and record results"""
        try:
            logger.info(f"🧪 Running test: {test_name}")
            result = test_func()
            self.test_results[test_name] = {
                "status": "PASS",
                "result": result,
                "error": None
            }
            self.passed_tests += 1
            logger.info(f"✅ {test_name} - PASSED")
            return True
        except Exception as e:
            self.test_results[test_name] = {
                "status": "FAIL", 
                "result": None,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            self.failed_tests += 1
            logger.error(f"❌ {test_name} - FAILED: {str(e)}")
            return False
    
    async def run_async_test(self, test_name: str, test_func):
        """Run an async test and record results"""
        try:
            logger.info(f"🧪 Running async test: {test_name}")
            result = await test_func()
            self.test_results[test_name] = {
                "status": "PASS",
                "result": result,
                "error": None
            }
            self.passed_tests += 1
            logger.info(f"✅ {test_name} - PASSED")
            return True
        except Exception as e:
            self.test_results[test_name] = {
                "status": "FAIL",
                "result": None, 
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            self.failed_tests += 1
            logger.error(f"❌ {test_name} - FAILED: {str(e)}")
            return False
    
    def test_imports(self):
        """Test all critical imports"""
        results = {}
        
        # Core imports
        try:
            from main import app
            results["FastAPI App"] = "✅ OK"
        except Exception as e:
            results["FastAPI App"] = f"❌ FAIL: {str(e)}"
        
        try:
            from database import engine, SessionLocal, get_db
            results["Database"] = "✅ OK"
        except Exception as e:
            results["Database"] = f"❌ FAIL: {str(e)}"
        
        try:
            from models import Project, Video, TestSession, DetectionEvent
            results["Models"] = "✅ OK"
        except Exception as e:
            results["Models"] = f"❌ FAIL: {str(e)}"
        
        try:
            from schemas import ProjectCreate, VideoUploadResponse
            results["Schemas"] = "✅ OK"
        except Exception as e:
            results["Schemas"] = f"❌ FAIL: {str(e)}"
        
        try:
            from crud import create_project, get_projects
            results["CRUD Operations"] = "✅ OK" 
        except Exception as e:
            results["CRUD Operations"] = f"❌ FAIL: {str(e)}"
        
        try:
            from socketio_server import sio, create_socketio_app
            results["SocketIO"] = "✅ OK"
        except Exception as e:
            results["SocketIO"] = f"❌ FAIL: {str(e)}"
        
        try:
            from services.websocket_service import websocket_manager
            results["WebSocket Manager"] = "✅ OK"
        except Exception as e:
            results["WebSocket Manager"] = f"❌ FAIL: {str(e)}"
        
        try:
            from services.video_annotation_service import VideoAnnotationService
            results["Video Annotation Service"] = "✅ OK"
        except Exception as e:
            results["Video Annotation Service"] = f"❌ FAIL: {str(e)}"
        
        try:
            from services.camera_validation_service import CameraValidationService
            results["Camera Validation Service"] = "✅ OK"
        except Exception as e:
            results["Camera Validation Service"] = f"❌ FAIL: {str(e)}"
        
        return results
    
    def test_database_connection(self):
        """Test database connectivity"""
        from database import get_database_health
        return get_database_health()
    
    def test_database_models(self):
        """Test database model creation"""
        from database import engine
        from models import Base
        
        # Test table creation
        Base.metadata.create_all(bind=engine)
        
        # Test basic operations
        from database import SessionLocal
        db = SessionLocal()
        
        try:
            from models import Project
            from sqlalchemy import text
            
            # Test basic query
            result = db.execute(text("SELECT COUNT(*) FROM projects")).scalar()
            
            return {
                "tables_created": "✅ OK",
                "project_count": result,
                "connection": "✅ OK"
            }
        finally:
            db.close()
    
    def test_crud_operations(self):
        """Test CRUD operations"""
        from database import SessionLocal
        from crud import create_project, get_projects, get_project
        from schemas import ProjectCreate
        from models import Project
        
        db = SessionLocal()
        
        try:
            # Test project creation
            project_data = ProjectCreate(
                name="Health Check Test Project",
                description="Test project for backend health check",
                camera_model="Test Camera",
                camera_view="Front-facing VRU",
                signal_type="GPIO"
            )
            
            # Create project
            project = create_project(db, project_data)
            
            # Test retrieval
            retrieved_project = get_project(db, project.id)
            
            # Test listing
            projects = get_projects(db, limit=5)
            
            return {
                "create_project": "✅ OK",
                "get_project": "✅ OK" if retrieved_project else "❌ FAIL",
                "list_projects": f"✅ OK ({len(projects)} projects)",
                "project_id": project.id
            }
        finally:
            db.close()
    
    def test_api_routes(self):
        """Test API route registration"""
        from main import app
        
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods)
                })
        
        # Check for critical endpoints
        critical_endpoints = [
            "/api/projects",
            "/api/videos", 
            "/api/test-sessions",
            "/api/dashboard/stats",
            "/health"
        ]
        
        found_endpoints = []
        for endpoint in critical_endpoints:
            found = any(route["path"] == endpoint for route in routes)
            found_endpoints.append({
                "endpoint": endpoint,
                "found": found
            })
        
        return {
            "total_routes": len(routes),
            "critical_endpoints": found_endpoints,
            "sample_routes": routes[:10]  # First 10 routes
        }
    
    def test_file_operations(self):
        """Test file upload capabilities"""
        import tempfile
        import os
        
        from config import settings
        
        # Test upload directory creation
        upload_dir = settings.upload_directory
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)
        
        # Test temporary file operations
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_file.write(b"test video content")
            temp_path = temp_file.name
        
        try:
            # Test file exists
            file_exists = os.path.exists(temp_path)
            
            # Test file size
            file_size = os.path.getsize(temp_path)
            
            return {
                "upload_directory": f"✅ OK ({upload_dir})",
                "temp_file_creation": "✅ OK" if file_exists else "❌ FAIL",
                "file_size": file_size,
                "max_file_size": settings.max_file_size
            }
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    async def test_websocket_functionality(self):
        """Test WebSocket functionality"""
        from services.websocket_service import websocket_manager
        
        # Test WebSocket manager initialization
        connection_count = websocket_manager.get_connection_count()
        
        # Test room creation
        test_room = "test_room_health_check"
        websocket_manager.create_room(test_room)
        
        room_exists = test_room in websocket_manager.rooms
        
        return {
            "websocket_manager": "✅ OK",
            "connection_count": connection_count,
            "room_creation": "✅ OK" if room_exists else "❌ FAIL",
            "active_rooms": len(websocket_manager.rooms)
        }
    
    async def test_service_initialization(self):
        """Test service initialization"""
        results = {}
        
        try:
            from services.video_annotation_service import VideoAnnotationService
            video_service = VideoAnnotationService()
            results["Video Annotation Service"] = "✅ OK"
        except Exception as e:
            results["Video Annotation Service"] = f"❌ FAIL: {str(e)}"
        
        try:
            from services.camera_validation_service import CameraValidationService
            camera_service = CameraValidationService()
            results["Camera Validation Service"] = "✅ OK"
        except Exception as e:
            results["Camera Validation Service"] = f"❌ FAIL: {str(e)}"
        
        try:
            from services.ground_truth_service import GroundTruthService
            gt_service = GroundTruthService()
            results["Ground Truth Service"] = "✅ OK"
        except Exception as e:
            results["Ground Truth Service"] = f"❌ FAIL: {str(e)}"
        
        try:
            from services.detection_pipeline_service import DetectionPipeline
            detection_service = DetectionPipeline()
            results["Detection Pipeline Service"] = "✅ OK"
        except Exception as e:
            results["Detection Pipeline Service"] = f"❌ FAIL: {str(e)}"
        
        return results
    
    def test_ml_dependencies(self):
        """Test ML dependencies"""
        results = {}
        
        # Test PyTorch
        try:
            import torch
            results["PyTorch"] = f"✅ OK (version: {torch.__version__})"
        except ImportError:
            results["PyTorch"] = "⚠️ NOT INSTALLED"
        
        # Test OpenCV
        try:
            import cv2
            results["OpenCV"] = f"✅ OK (version: {cv2.__version__})"
        except ImportError:
            results["OpenCV"] = "⚠️ NOT INSTALLED"
        
        # Test Ultralytics (YOLO)
        try:
            import ultralytics
            results["Ultralytics"] = "✅ OK"
        except ImportError:
            results["Ultralytics"] = "⚠️ NOT INSTALLED"
        
        # Test LabJack (optional)
        try:
            import labjack
            results["LabJack"] = "✅ OK"
        except ImportError:
            results["LabJack"] = "⚠️ NOT INSTALLED (optional)"
        
        return results
    
    async def run_comprehensive_health_check(self):
        """Run all health checks"""
        logger.info("🚀 Starting comprehensive backend health check...")
        
        # Import tests
        self.run_test("Critical Imports", self.test_imports)
        
        # Database tests
        self.run_test("Database Connection", self.test_database_connection)
        self.run_test("Database Models", self.test_database_models)
        self.run_test("CRUD Operations", self.test_crud_operations)
        
        # API tests
        self.run_test("API Routes", self.test_api_routes)
        
        # File operation tests
        self.run_test("File Operations", self.test_file_operations)
        
        # WebSocket tests
        await self.run_async_test("WebSocket Functionality", self.test_websocket_functionality)
        
        # Service tests
        await self.run_async_test("Service Initialization", self.test_service_initialization)
        
        # Dependency tests
        self.run_test("ML Dependencies", self.test_ml_dependencies)
        
        # Generate summary report
        self.generate_health_report()
    
    def generate_health_report(self):
        """Generate comprehensive health report"""
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print("\n" + "="*80)
        print("🏥 BACKEND HEALTH CHECK REPORT")
        print("="*80)
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   ✅ Passed: {self.passed_tests}")
        print(f"   ❌ Failed: {self.failed_tests}")
        print(f"   📈 Success Rate: {success_rate:.1f}%")
        print(f"   🕐 Report Time: {datetime.utcnow().isoformat()}")
        
        print(f"\n📋 Detailed Results:")
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"   {status_icon} {test_name}: {result['status']}")
            
            if result["status"] == "FAIL":
                print(f"      Error: {result['error']}")
            elif isinstance(result["result"], dict):
                for key, value in result["result"].items():
                    print(f"      {key}: {value}")
        
        print("\n🔧 Recommendations:")
        if self.failed_tests == 0:
            print("   🎉 All tests passed! Backend is fully operational.")
        else:
            print("   ⚠️ Some tests failed. Review errors above and fix issues.")
            print("   🔍 Check logs for detailed error information.")
            
            # Specific recommendations based on failures
            failed_tests = [name for name, result in self.test_results.items() if result["status"] == "FAIL"]
            
            if any("Import" in test for test in failed_tests):
                print("   📦 Fix import errors by installing missing dependencies")
            if any("Database" in test for test in failed_tests):
                print("   🗄️ Check database configuration and connectivity")
            if any("WebSocket" in test for test in failed_tests):
                print("   🔌 Review WebSocket configuration and dependencies")
        
        print("="*80)
        
        # Return summary for programmatic use
        return {
            "total_tests": total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "success_rate": success_rate,
            "status": "HEALTHY" if self.failed_tests == 0 else "UNHEALTHY",
            "report_time": datetime.utcnow().isoformat()
        }

async def main():
    """Main health check function"""
    checker = BackendHealthChecker()
    summary = await checker.run_comprehensive_health_check()
    
    # Exit with appropriate code
    if summary["failed_tests"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())