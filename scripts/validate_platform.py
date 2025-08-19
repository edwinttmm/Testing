#!/usr/bin/env python3
"""
Comprehensive Platform Validation Script
Validates all aspects of the video processing platform
"""
import sys
import os
import asyncio
import requests
import time
from pathlib import Path
from typing import Dict, List, Any

# Add backend to path
backend_path = Path(__file__).parent.parent / "ai-model-validation-platform" / "backend"
sys.path.append(str(backend_path))

class PlatformValidator:
    """Comprehensive platform validation"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {"passed": 0, "failed": 0, "tests": []}
    
    def test_result(self, test_name: str, success: bool, message: str = ""):
        """Record test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"   {message}")
        
        self.results["tests"].append({
            "name": test_name,
            "success": success,
            "message": message
        })
        
        if success:
            self.results["passed"] += 1
        else:
            self.results["failed"] += 1
    
    def test_database_schema(self):
        """Test database schema"""
        print("\n🔍 Testing Database Schema...")
        
        try:
            from sqlalchemy import inspect
            from database import engine
            
            inspector = inspect(engine)
            
            # Test videos table
            if 'videos' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('videos')]
                required_cols = ['id', 'filename', 'processing_status', 'ground_truth_generated']
                
                missing_cols = [col for col in required_cols if col not in columns]
                if not missing_cols:
                    self.test_result("Database Schema - Videos Table", True, "All required columns present")
                else:
                    self.test_result("Database Schema - Videos Table", False, f"Missing columns: {missing_cols}")
            else:
                self.test_result("Database Schema - Videos Table", False, "Videos table not found")
            
            # Test ground_truth_objects table
            if 'ground_truth_objects' in inspector.get_table_names():
                gt_columns = [col['name'] for col in inspector.get_columns('ground_truth_objects')]
                required_gt_cols = ['id', 'video_id', 'timestamp', 'class_label', 'x', 'y', 'width', 'height']
                
                missing_gt_cols = [col for col in required_gt_cols if col not in gt_columns]
                if not missing_gt_cols:
                    self.test_result("Database Schema - Ground Truth Table", True, "All required columns present")
                else:
                    self.test_result("Database Schema - Ground Truth Table", False, f"Missing columns: {missing_gt_cols}")
            else:
                self.test_result("Database Schema - Ground Truth Table", False, "Ground truth table not found")
                
        except Exception as e:
            self.test_result("Database Schema", False, f"Error: {e}")
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        print("\n🌐 Testing API Endpoints...")
        
        try:
            # Test health check
            response = requests.get(f"{self.base_url}/")
            if response.status_code == 200:
                self.test_result("API Health Check", True, "Server responding")
            else:
                self.test_result("API Health Check", False, f"Status: {response.status_code}")
            
            # Test projects endpoint
            response = requests.get(f"{self.base_url}/projects/")
            if response.status_code == 200:
                self.test_result("Projects Endpoint", True, "Projects endpoint accessible")
            else:
                self.test_result("Projects Endpoint", False, f"Status: {response.status_code}")
            
            # Test videos endpoint
            response = requests.get(f"{self.base_url}/videos/")
            if response.status_code == 200:
                self.test_result("Videos Endpoint", True, "Videos endpoint accessible")
            else:
                self.test_result("Videos Endpoint", False, f"Status: {response.status_code}")
                
        except requests.ConnectionError:
            self.test_result("API Connection", False, "Cannot connect to server")
        except Exception as e:
            self.test_result("API Endpoints", False, f"Error: {e}")
    
    def test_models_import(self):
        """Test model imports"""
        print("\n📦 Testing Model Imports...")
        
        try:
            from models import Video, Project, GroundTruthObject
            self.test_result("Models Import", True, "All models imported successfully")
            
            # Test model attributes
            video_attrs = ['id', 'filename', 'processing_status', 'ground_truth_generated']
            missing_attrs = [attr for attr in video_attrs if not hasattr(Video, attr)]
            
            if not missing_attrs:
                self.test_result("Video Model Attributes", True, "All required attributes present")
            else:
                self.test_result("Video Model Attributes", False, f"Missing attributes: {missing_attrs}")
                
        except ImportError as e:
            self.test_result("Models Import", False, f"Import error: {e}")
        except Exception as e:
            self.test_result("Models Import", False, f"Error: {e}")
    
    def test_enhanced_schemas(self):
        """Test enhanced schemas"""
        print("\n📋 Testing Enhanced Schemas...")
        
        try:
            from schemas_enhanced import VideoResponse, ProcessingStatusEnum, VideoProcessingWorkflow
            self.test_result("Enhanced Schemas Import", True, "Enhanced schemas imported successfully")
            
            # Test enum values
            expected_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
            actual_statuses = [status.name for status in ProcessingStatusEnum]
            
            if all(status in actual_statuses for status in expected_statuses):
                self.test_result("Processing Status Enum", True, "All required status values present")
            else:
                missing = [s for s in expected_statuses if s not in actual_statuses]
                self.test_result("Processing Status Enum", False, f"Missing statuses: {missing}")
                
        except ImportError as e:
            self.test_result("Enhanced Schemas", False, f"Import error: {e}")
        except Exception as e:
            self.test_result("Enhanced Schemas", False, f"Error: {e}")
    
    def test_services(self):
        """Test service layer"""
        print("\n⚙️  Testing Services...")
        
        try:
            from services.video_processing_workflow import VideoProcessingWorkflow
            self.test_result("Video Processing Service", True, "Service imported successfully")
            
            # Test service instantiation
            from database import SessionLocal
            db = SessionLocal()
            workflow = VideoProcessingWorkflow(db)
            
            if hasattr(workflow, 'update_processing_status'):
                self.test_result("Service Methods", True, "Required methods available")
            else:
                self.test_result("Service Methods", False, "Missing required methods")
                
            db.close()
            
        except ImportError as e:
            self.test_result("Services", False, f"Import error: {e}")
        except Exception as e:
            self.test_result("Services", False, f"Error: {e}")
    
    def test_file_structure(self):
        """Test file structure"""
        print("\n📁 Testing File Structure...")
        
        expected_files = [
            "ai-model-validation-platform/backend/main.py",
            "ai-model-validation-platform/backend/models.py",
            "ai-model-validation-platform/backend/database.py",
            "ai-model-validation-platform/backend/schemas_enhanced.py",
            "ai-model-validation-platform/backend/services/video_processing_workflow.py",
            "scripts/database_migration.py",
            "scripts/fix_video_upload.py",
            "tests/test_video_processing.py"
        ]
        
        base_path = Path(__file__).parent.parent
        missing_files = []
        
        for file_path in expected_files:
            full_path = base_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if not missing_files:
            self.test_result("File Structure", True, "All required files present")
        else:
            self.test_result("File Structure", False, f"Missing files: {missing_files}")
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Comprehensive Platform Validation")
        print("=" * 60)
        
        # Run all test categories
        self.test_file_structure()
        self.test_models_import()
        self.test_enhanced_schemas()
        self.test_database_schema()
        self.test_services()
        self.test_api_endpoints()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.results['passed'] + self.results['failed']}")
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        
        success_rate = (self.results['passed'] / (self.results['passed'] + self.results['failed'])) * 100
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.results['failed'] == 0:
            print("\n🎉 ALL TESTS PASSED! Platform is ready for production.")
            return True
        else:
            print(f"\n⚠️  {self.results['failed']} tests failed. Please review and fix issues.")
            return False

def main():
    """Main validation runner"""
    validator = PlatformValidator()
    
    if validator.run_all_tests():
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())