#!/usr/bin/env python3
"""
Comprehensive Deployment Verification Script
Tests all critical workflow components to ensure full functionality
"""
import asyncio
import sys
import logging
import requests
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/deployment_verification.log')
    ]
)
logger = logging.getLogger(__name__)

class DeploymentVerifier:
    """Comprehensive deployment verification"""
    
    def __init__(self, backend_url: str = "http://localhost:8000", frontend_url: str = "http://localhost:3000"):
        self.backend_url = backend_url.rstrip('/')
        self.frontend_url = frontend_url.rstrip('/')
        self.test_results = {
            "ml_dependencies": False,
            "backend_health": False,
            "frontend_health": False,
            "database_connection": False,
            "ground_truth_service": False,
            "detection_pipeline": False,
            "test_execution": False,
            "video_upload": False,
            "end_to_end_workflow": False
        }
        self.test_details = {}
    
    async def verify_all(self) -> Dict[str, Any]:
        """Run all verification tests"""
        logger.info("🚀 Starting comprehensive deployment verification...")
        
        # Test sequence
        tests = [
            ("ML Dependencies", self.verify_ml_dependencies),
            ("Backend Health", self.verify_backend_health),
            ("Frontend Health", self.verify_frontend_health),
            ("Database Connection", self.verify_database_connection),
            ("Ground Truth Service", self.verify_ground_truth_service),
            ("Detection Pipeline", self.verify_detection_pipeline),
            ("Test Execution Service", self.verify_test_execution),
            ("Video Upload", self.verify_video_upload),
            ("End-to-End Workflow", self.verify_end_to_end_workflow),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"🔍 Testing: {test_name}")
            try:
                result = await test_func()
                if result:
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
            except Exception as e:
                logger.error(f"💥 {test_name}: ERROR - {str(e)}")
                self.test_details[test_name] = str(e)
        
        return self.generate_report()
    
    async def verify_ml_dependencies(self) -> bool:
        """Verify ML dependencies are installed and working"""
        try:
            # Test PyTorch
            import torch
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f"PyTorch device: {device}")
            
            # Test tensor operations
            x = torch.randn(2, 2, device=device)
            y = x + 1
            
            # Test Ultralytics
            from ultralytics import YOLO
            model = YOLO('yolov8n.pt')  # This will download if needed
            
            # Test inference
            import numpy as np
            dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
            results = model(dummy_img, verbose=False)
            
            logger.info("✅ ML dependencies working correctly")
            self.test_results["ml_dependencies"] = True
            return True
            
        except ImportError as e:
            logger.error(f"❌ ML dependency missing: {e}")
            self.test_details["ml_dependencies"] = f"Import error: {e}"
            return False
        except Exception as e:
            logger.error(f"❌ ML functionality error: {e}")
            self.test_details["ml_dependencies"] = f"Runtime error: {e}"
            return False
    
    async def verify_backend_health(self) -> bool:
        """Verify backend API is running and healthy"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Backend health: {data}")
                self.test_results["backend_health"] = True
                return True
            else:
                logger.error(f"Backend health check failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Cannot connect to backend: {e}")
            self.test_details["backend_health"] = str(e)
            return False
    
    async def verify_frontend_health(self) -> bool:
        """Verify frontend is accessible"""
        try:
            response = requests.get(self.frontend_url, timeout=10)
            if response.status_code == 200:
                logger.info("Frontend is accessible")
                self.test_results["frontend_health"] = True
                return True
            else:
                logger.error(f"Frontend health check failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Cannot connect to frontend: {e}")
            self.test_details["frontend_health"] = str(e)
            return False
    
    async def verify_database_connection(self) -> bool:
        """Verify database connection"""
        try:
            response = requests.get(f"{self.backend_url}/api/projects", timeout=10)
            if response.status_code in [200, 404]:  # 404 is OK if no projects
                logger.info("Database connection working")
                self.test_results["database_connection"] = True
                return True
            else:
                logger.error(f"Database connection test failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Database connection error: {e}")
            self.test_details["database_connection"] = str(e)
            return False
    
    async def verify_ground_truth_service(self) -> bool:
        """Verify ground truth service functionality"""
        try:
            # Test ground truth service import
            sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
            from services.ground_truth_service import GroundTruthService
            
            service = GroundTruthService()
            
            if service.ml_available:
                logger.info("✅ Ground truth service with ML enabled")
                self.test_results["ground_truth_service"] = True
                return True
            else:
                logger.warning("⚠️  Ground truth service in fallback mode - ML dependencies not available")
                self.test_details["ground_truth_service"] = "ML dependencies not available"
                return False
                
        except Exception as e:
            logger.error(f"Ground truth service error: {e}")
            self.test_details["ground_truth_service"] = str(e)
            return False
    
    async def verify_detection_pipeline(self) -> bool:
        """Verify detection pipeline functionality"""
        try:
            sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
            from services.detection_pipeline_service import DetectionPipeline
            
            pipeline = DetectionPipeline()
            await pipeline.initialize()
            
            # Test model loading
            model = await pipeline.model_registry.get_active_model()
            
            # Test inference with dummy data
            import numpy as np
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            processed_frame = await pipeline.frame_processor.preprocess(dummy_frame)
            detections = await model.predict(processed_frame)
            
            logger.info(f"✅ Detection pipeline working - {len(detections)} detections from test frame")
            self.test_results["detection_pipeline"] = True
            return True
            
        except Exception as e:
            logger.error(f"Detection pipeline error: {e}")
            self.test_details["detection_pipeline"] = str(e)
            return False
    
    async def verify_test_execution(self) -> bool:
        """Verify test execution service"""
        try:
            sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
            from services.test_execution_service import TestExecutionService
            
            service = TestExecutionService()
            await service.initialize()
            
            logger.info("✅ Test execution service initialized")
            self.test_results["test_execution"] = True
            return True
            
        except Exception as e:
            logger.error(f"Test execution service error: {e}")
            self.test_details["test_execution"] = str(e)
            return False
    
    async def verify_video_upload(self) -> bool:
        """Verify video upload functionality"""
        try:
            # Create a small test video file
            test_video_path = '/tmp/test_video.mp4'
            
            # Create a minimal test video using ffmpeg if available
            try:
                subprocess.run([
                    'ffmpeg', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=320x240:rate=1',
                    '-pix_fmt', 'yuv420p', '-y', test_video_path
                ], check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Create a dummy file if ffmpeg not available
                with open(test_video_path, 'wb') as f:
                    f.write(b'\x00' * 1024)  # 1KB dummy file
            
            # Test upload endpoint
            if os.path.exists(test_video_path):
                with open(test_video_path, 'rb') as f:
                    files = {'file': ('test_video.mp4', f, 'video/mp4')}
                    response = requests.post(f"{self.backend_url}/api/videos/upload", files=files, timeout=30)
                
                if response.status_code == 200:
                    logger.info("✅ Video upload endpoint working")
                    self.test_results["video_upload"] = True
                    return True
                else:
                    logger.error(f"Video upload failed: {response.status_code} - {response.text}")
                    return False
            else:
                logger.error("Could not create test video file")
                return False
                
        except Exception as e:
            logger.error(f"Video upload test error: {e}")
            self.test_details["video_upload"] = str(e)
            return False
        finally:
            # Cleanup
            if os.path.exists(test_video_path):
                os.remove(test_video_path)
    
    async def verify_end_to_end_workflow(self) -> bool:
        """Verify complete end-to-end workflow"""
        try:
            # This would be a complete workflow test
            # For now, check that all previous tests passed
            critical_components = [
                "ml_dependencies",
                "backend_health", 
                "database_connection",
                "detection_pipeline",
                "ground_truth_service"
            ]
            
            all_passed = all(self.test_results.get(comp, False) for comp in critical_components)
            
            if all_passed:
                logger.info("✅ End-to-end workflow ready")
                self.test_results["end_to_end_workflow"] = True
                return True
            else:
                failed_components = [comp for comp in critical_components if not self.test_results.get(comp, False)]
                logger.error(f"❌ End-to-end workflow blocked by: {failed_components}")
                self.test_details["end_to_end_workflow"] = f"Blocked by: {failed_components}"
                return False
                
        except Exception as e:
            logger.error(f"End-to-end workflow test error: {e}")
            self.test_details["end_to_end_workflow"] = str(e)
            return False
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate final verification report"""
        passed_tests = sum(1 for result in self.test_results.values() if result)
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests) * 100
        
        status = "READY" if success_rate == 100 else "NEEDS_ATTENTION" if success_rate >= 70 else "CRITICAL_ISSUES"
        
        report = {
            "status": status,
            "success_rate": success_rate,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "test_results": self.test_results,
            "test_details": self.test_details,
            "recommendations": self.get_recommendations(),
            "timestamp": time.time()
        }
        
        return report
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations based on test results"""
        recommendations = []
        
        if not self.test_results.get("ml_dependencies", False):
            recommendations.append("Install ML dependencies: pip install torch ultralytics")
            recommendations.append("Run auto_install_ml.py for automated ML setup")
        
        if not self.test_results.get("backend_health", False):
            recommendations.append("Start backend server: uvicorn main:app --host 0.0.0.0 --port 8000")
        
        if not self.test_results.get("frontend_health", False):
            recommendations.append("Start frontend server: npm start")
        
        if not self.test_results.get("database_connection", False):
            recommendations.append("Check database connection and run migrations")
        
        if not self.test_results.get("ground_truth_service", False):
            recommendations.append("Fix ground truth service ML integration")
        
        if not self.test_results.get("detection_pipeline", False):
            recommendations.append("Fix detection pipeline configuration")
        
        return recommendations

async def main():
    """Main verification routine"""
    if len(sys.argv) > 1:
        backend_url = sys.argv[1]
    else:
        backend_url = "http://localhost:8000"
    
    if len(sys.argv) > 2:
        frontend_url = sys.argv[2]
    else:
        frontend_url = "http://localhost:3000"
    
    verifier = DeploymentVerifier(backend_url, frontend_url)
    report = await verifier.verify_all()
    
    # Print report
    print("\n" + "="*80)
    print("🔍 DEPLOYMENT VERIFICATION REPORT")
    print("="*80)
    print(f"Status: {report['status']}")
    print(f"Success Rate: {report['success_rate']:.1f}%")
    print(f"Tests Passed: {report['passed_tests']}/{report['total_tests']}")
    
    print("\n📊 Test Results:")
    for test_name, result in report['test_results'].items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:25} {status}")
        if not result and test_name in report['test_details']:
            print(f"    Error: {report['test_details'][test_name]}")
    
    if report['recommendations']:
        print("\n💡 Recommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "="*80)
    
    # Save detailed report
    with open('/tmp/deployment_verification_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📝 Detailed report saved to: /tmp/deployment_verification_report.json")
    
    # Exit code based on status
    if report['status'] == "READY":
        print("🎉 System is ready for production use!")
        return 0
    elif report['status'] == "NEEDS_ATTENTION":
        print("⚠️  System has some issues but core functionality works")
        return 1
    else:
        print("🚨 Critical issues detected - system not ready")
        return 2

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Verification cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        sys.exit(1)