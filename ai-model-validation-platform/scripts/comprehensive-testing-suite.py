#!/usr/bin/env python3
"""
Comprehensive Testing Suite for AI Model Validation Platform
Monitors all features, logs interactions, and generates detailed error reports
"""

import asyncio
import json
import logging
import subprocess
import time
import threading
import requests
import websocket
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import os

class ComprehensiveMonitor:
    def __init__(self):
        self.log_dir = Path("/home/rigade/Testing/ai-model-validation-platform/logs/comprehensive-test")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "backend_status": {},
            "frontend_status": {},
            "page_tests": {},
            "feature_tests": {},
            "errors": [],
            "warnings": [],
            "performance_metrics": {},
            "user_journey_results": {}
        }
        
        # Setup comprehensive logging
        self.setup_logging()
        
        # API endpoints to test
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        
        # Test videos and sample data
        self.test_video_path = "/home/rigade/Testing/ai-model-validation-platform/tests/test_video.mp4"
        
    def setup_logging(self):
        """Setup comprehensive logging system"""
        # Main test log
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_dir / 'comprehensive-test.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('ComprehensiveMonitor')
        
        # Separate logs for different components
        self.backend_logger = self.create_logger('backend')
        self.frontend_logger = self.create_logger('frontend')
        self.api_logger = self.create_logger('api')
        self.websocket_logger = self.create_logger('websocket')
        self.ui_logger = self.create_logger('ui')
        
    def create_logger(self, name: str) -> logging.Logger:
        """Create a dedicated logger for specific component"""
        logger = logging.getLogger(name)
        handler = logging.FileHandler(self.log_dir / f'{name}-test.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        return logger
        
    def log_error(self, component: str, error: str, details: Dict = None):
        """Log error with full context"""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "error": error,
            "details": details or {}
        }
        self.test_results["errors"].append(error_entry)
        self.logger.error(f"[{component}] {error}: {details}")
        
    def log_warning(self, component: str, warning: str, details: Dict = None):
        """Log warning with context"""
        warning_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "warning": warning,
            "details": details or {}
        }
        self.test_results["warnings"].append(warning_entry)
        self.logger.warning(f"[{component}] {warning}: {details}")

    def test_backend_startup(self):
        """Test backend server startup and capture all errors"""
        self.backend_logger.info("Starting backend server test...")
        backend_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend")
        
        try:
            # Change to backend directory
            os.chdir(backend_dir)
            
            # Test Python imports first
            self.backend_logger.info("Testing Python imports...")
            import_test = subprocess.run(
                [sys.executable, "-c", "import main, models, crud, schemas"],
                cwd=backend_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if import_test.returncode != 0:
                self.log_error("backend_imports", import_test.stderr, {
                    "stdout": import_test.stdout,
                    "return_code": import_test.returncode
                })
            
            # Start backend server
            self.backend_logger.info("Starting FastAPI server...")
            self.backend_process = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor backend logs in real-time
            backend_thread = threading.Thread(target=self.monitor_backend_logs)
            backend_thread.daemon = True
            backend_thread.start()
            
            # Wait for server to start
            time.sleep(10)
            
            # Test basic connectivity
            self.test_backend_connectivity()
            
        except Exception as e:
            self.log_error("backend_startup", str(e), {"exception_type": type(e).__name__})
            
    def monitor_backend_logs(self):
        """Monitor backend process logs in real-time"""
        if not hasattr(self, 'backend_process'):
            return
            
        while True:
            try:
                if self.backend_process.poll() is not None:
                    break
                    
                # Read stdout
                if self.backend_process.stdout:
                    line = self.backend_process.stdout.readline()
                    if line:
                        self.backend_logger.info(f"STDOUT: {line.strip()}")
                        
                # Read stderr
                if self.backend_process.stderr:
                    line = self.backend_process.stderr.readline()
                    if line:
                        self.backend_logger.error(f"STDERR: {line.strip()}")
                        self.log_error("backend_runtime", line.strip())
                        
            except Exception as e:
                self.backend_logger.error(f"Error monitoring backend: {e}")
                break
                
    def test_backend_connectivity(self):
        """Test backend API endpoints"""
        self.api_logger.info("Testing backend API endpoints...")
        
        endpoints = [
            "/",
            "/health",
            "/docs",
            "/api/projects",
            "/api/datasets",
            "/api/videos",
            "/api/detections"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.backend_url}{endpoint}"
                self.api_logger.info(f"Testing endpoint: {url}")
                
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    self.api_logger.info(f"✓ {endpoint}: OK")
                    self.test_results["backend_status"][endpoint] = {
                        "status": "success",
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds()
                    }
                else:
                    self.log_error("api_endpoint", f"{endpoint} returned {response.status_code}", {
                        "url": url,
                        "status_code": response.status_code,
                        "response": response.text[:500]
                    })
                    
            except Exception as e:
                self.log_error("api_connectivity", f"Failed to connect to {endpoint}", {
                    "endpoint": endpoint,
                    "error": str(e)
                })

    def test_frontend_startup(self):
        """Test frontend application startup"""
        self.frontend_logger.info("Starting frontend application test...")
        frontend_dir = Path("/home/rigade/Testing/ai-model-validation-platform/frontend")
        
        try:
            # Change to frontend directory
            os.chdir(frontend_dir)
            
            # Install dependencies if needed
            self.frontend_logger.info("Checking npm dependencies...")
            npm_install = subprocess.run(
                ["npm", "install"],
                cwd=frontend_dir,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if npm_install.returncode != 0:
                self.log_error("npm_install", npm_install.stderr, {
                    "stdout": npm_install.stdout
                })
            
            # Test TypeScript compilation
            self.frontend_logger.info("Testing TypeScript compilation...")
            tsc_test = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=frontend_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if tsc_test.returncode != 0:
                self.log_error("typescript_compilation", tsc_test.stderr, {
                    "stdout": tsc_test.stdout
                })
            
            # Start React development server
            self.frontend_logger.info("Starting React development server...")
            env = os.environ.copy()
            env['BROWSER'] = 'none'  # Prevent auto-opening browser
            
            self.frontend_process = subprocess.Popen(
                ["npm", "start"],
                cwd=frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # Monitor frontend logs
            frontend_thread = threading.Thread(target=self.monitor_frontend_logs)
            frontend_thread.daemon = True
            frontend_thread.start()
            
            # Wait for React server to start
            time.sleep(30)
            
            # Test frontend connectivity
            self.test_frontend_connectivity()
            
        except Exception as e:
            self.log_error("frontend_startup", str(e), {"exception_type": type(e).__name__})
            
    def monitor_frontend_logs(self):
        """Monitor frontend process logs in real-time"""
        if not hasattr(self, 'frontend_process'):
            return
            
        while True:
            try:
                if self.frontend_process.poll() is not None:
                    break
                    
                # Read stdout
                if self.frontend_process.stdout:
                    line = self.frontend_process.stdout.readline()
                    if line:
                        self.frontend_logger.info(f"STDOUT: {line.strip()}")
                        
                        # Check for specific errors
                        if "error" in line.lower() or "failed" in line.lower():
                            self.log_error("frontend_runtime", line.strip())
                        
                # Read stderr
                if self.frontend_process.stderr:
                    line = self.frontend_process.stderr.readline()
                    if line:
                        self.frontend_logger.error(f"STDERR: {line.strip()}")
                        self.log_error("frontend_runtime", line.strip())
                        
            except Exception as e:
                self.frontend_logger.error(f"Error monitoring frontend: {e}")
                break

    def test_frontend_connectivity(self):
        """Test frontend pages accessibility"""
        self.ui_logger.info("Testing frontend pages...")
        
        pages = [
            "/",
            "/projects",
            "/datasets", 
            "/results",
            "/ground-truth",
            "/project-detail"
        ]
        
        for page in pages:
            try:
                url = f"{self.frontend_url}{page}"
                self.ui_logger.info(f"Testing page: {url}")
                
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    self.ui_logger.info(f"✓ {page}: OK")
                    self.test_results["frontend_status"][page] = {
                        "status": "success",
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds()
                    }
                    
                    # Check for JavaScript errors in response
                    self.check_page_for_errors(page, response.text)
                else:
                    self.log_error("frontend_page", f"{page} returned {response.status_code}", {
                        "url": url,
                        "status_code": response.status_code
                    })
                    
            except Exception as e:
                self.log_error("frontend_connectivity", f"Failed to access {page}", {
                    "page": page,
                    "error": str(e)
                })

    def check_page_for_errors(self, page: str, html_content: str):
        """Analyze page HTML for potential JavaScript errors"""
        error_indicators = [
            "Uncaught",
            "TypeError",
            "ReferenceError", 
            "SyntaxError",
            "Cannot read property",
            "is not defined"
        ]
        
        for indicator in error_indicators:
            if indicator in html_content:
                self.log_warning("javascript_error", f"Potential JS error on {page}", {
                    "indicator": indicator,
                    "page": page
                })

    def test_user_journeys(self):
        """Test complete user journeys and log every interaction"""
        self.logger.info("Starting comprehensive user journey tests...")
        
        journeys = [
            self.test_project_creation_journey,
            self.test_video_upload_journey, 
            self.test_detection_pipeline_journey,
            self.test_annotation_journey,
            self.test_results_viewing_journey
        ]
        
        for journey in journeys:
            try:
                journey_name = journey.__name__
                self.logger.info(f"Testing journey: {journey_name}")
                
                start_time = time.time()
                result = journey()
                end_time = time.time()
                
                self.test_results["user_journey_results"][journey_name] = {
                    "status": "completed" if result else "failed",
                    "duration": end_time - start_time,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.log_error("user_journey", f"Journey {journey_name} failed", {
                    "error": str(e),
                    "journey": journey_name
                })

    def test_project_creation_journey(self) -> bool:
        """Test creating a new project"""
        self.logger.info("Testing project creation journey...")
        
        try:
            # Test POST /api/projects
            project_data = {
                "name": "Test Project",
                "description": "Automated test project",
                "created_by": "test_user"
            }
            
            response = requests.post(
                f"{self.backend_url}/api/projects",
                json=project_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.logger.info("✓ Project creation successful")
                return True
            else:
                self.log_error("project_creation", f"Failed with status {response.status_code}", {
                    "response": response.text,
                    "data": project_data
                })
                return False
                
        except Exception as e:
            self.log_error("project_creation", str(e))
            return False

    def test_video_upload_journey(self) -> bool:
        """Test video upload pipeline"""
        self.logger.info("Testing video upload journey...")
        
        try:
            # Check if test video exists
            if not Path(self.test_video_path).exists():
                self.log_warning("video_upload", "Test video not found", {
                    "path": self.test_video_path
                })
                return False
            
            # Test video upload endpoint
            with open(self.test_video_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(
                    f"{self.backend_url}/api/videos/upload",
                    files=files,
                    timeout=30
                )
                
            if response.status_code in [200, 201]:
                self.logger.info("✓ Video upload successful")
                return True
            else:
                self.log_error("video_upload", f"Upload failed with status {response.status_code}", {
                    "response": response.text
                })
                return False
                
        except Exception as e:
            self.log_error("video_upload", str(e))
            return False

    def test_detection_pipeline_journey(self) -> bool:
        """Test ML detection pipeline"""
        self.logger.info("Testing detection pipeline...")
        
        try:
            # Test detection endpoint
            detection_data = {
                "video_id": "test_video",
                "model_type": "yolov8",
                "confidence_threshold": 0.5
            }
            
            response = requests.post(
                f"{self.backend_url}/api/detections/run",
                json=detection_data,
                timeout=60
            )
            
            if response.status_code in [200, 202]:
                self.logger.info("✓ Detection pipeline initiated")
                return True
            else:
                self.log_error("detection_pipeline", f"Failed with status {response.status_code}", {
                    "response": response.text,
                    "data": detection_data
                })
                return False
                
        except Exception as e:
            self.log_error("detection_pipeline", str(e))
            return False

    def test_annotation_journey(self) -> bool:
        """Test annotation features"""
        self.logger.info("Testing annotation journey...")
        
        try:
            # Test annotation endpoints
            annotation_data = {
                "video_id": "test_video",
                "frame_number": 1,
                "annotations": [
                    {
                        "x": 100,
                        "y": 100,
                        "width": 50,
                        "height": 50,
                        "label": "test_object"
                    }
                ]
            }
            
            response = requests.post(
                f"{self.backend_url}/api/annotations",
                json=annotation_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.logger.info("✓ Annotation creation successful")
                return True
            else:
                self.log_error("annotation", f"Failed with status {response.status_code}", {
                    "response": response.text,
                    "data": annotation_data
                })
                return False
                
        except Exception as e:
            self.log_error("annotation", str(e))
            return False

    def test_results_viewing_journey(self) -> bool:
        """Test results viewing and data retrieval"""
        self.logger.info("Testing results viewing journey...")
        
        try:
            # Test results endpoints
            endpoints = [
                "/api/projects",
                "/api/videos", 
                "/api/detections",
                "/api/annotations"
            ]
            
            all_success = True
            for endpoint in endpoints:
                response = requests.get(f"{self.backend_url}{endpoint}", timeout=10)
                if response.status_code != 200:
                    self.log_error("results_viewing", f"Failed to get {endpoint}", {
                        "status_code": response.status_code,
                        "response": response.text
                    })
                    all_success = False
                    
            if all_success:
                self.logger.info("✓ Results viewing successful")
                
            return all_success
            
        except Exception as e:
            self.log_error("results_viewing", str(e))
            return False

    def test_websocket_features(self):
        """Test WebSocket real-time features"""
        self.websocket_logger.info("Testing WebSocket features...")
        
        try:
            # Test WebSocket connection
            ws_url = "ws://localhost:8000/ws"
            
            def on_message(ws, message):
                self.websocket_logger.info(f"Received message: {message}")
                
            def on_error(ws, error):
                self.log_error("websocket", str(error))
                
            def on_open(ws):
                self.websocket_logger.info("WebSocket connection opened")
                # Send test message
                ws.send(json.dumps({"type": "test", "data": "hello"}))
                
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error
            )
            
            # Run WebSocket test for 10 seconds
            ws.run_forever(timeout=10)
            
        except Exception as e:
            self.log_error("websocket_test", str(e))

    def generate_comprehensive_report(self):
        """Generate detailed error report"""
        self.logger.info("Generating comprehensive test report...")
        
        # Performance summary
        self.test_results["summary"] = {
            "total_errors": len(self.test_results["errors"]),
            "total_warnings": len(self.test_results["warnings"]),
            "backend_endpoints_tested": len(self.test_results["backend_status"]),
            "frontend_pages_tested": len(self.test_results["frontend_status"]),
            "user_journeys_tested": len(self.test_results["user_journey_results"]),
            "test_duration": (datetime.now() - datetime.fromisoformat(self.test_results["timestamp"])).total_seconds()
        }
        
        # Save detailed report
        report_file = self.log_dir / f"comprehensive-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
            
        self.logger.info(f"Comprehensive report saved to: {report_file}")
        
        # Generate summary report
        self.generate_summary_report()
        
    def generate_summary_report(self):
        """Generate human-readable summary report"""
        summary_file = self.log_dir / f"summary-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        with open(summary_file, 'w') as f:
            f.write("# AI Model Validation Platform - Comprehensive Test Report\n\n")
            f.write(f"**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Test Duration:** {self.test_results['summary']['test_duration']:.2f} seconds\n\n")
            
            # Summary stats
            f.write("## Summary\n\n")
            f.write(f"- **Total Errors:** {self.test_results['summary']['total_errors']}\n")
            f.write(f"- **Total Warnings:** {self.test_results['summary']['total_warnings']}\n")
            f.write(f"- **Backend Endpoints Tested:** {self.test_results['summary']['backend_endpoints_tested']}\n")
            f.write(f"- **Frontend Pages Tested:** {self.test_results['summary']['frontend_pages_tested']}\n")
            f.write(f"- **User Journeys Tested:** {self.test_results['summary']['user_journeys_tested']}\n\n")
            
            # Critical errors
            f.write("## Critical Errors\n\n")
            critical_components = ["backend_startup", "frontend_startup", "api_connectivity", "frontend_connectivity"]
            critical_errors = [e for e in self.test_results["errors"] if e["component"] in critical_components]
            
            if critical_errors:
                for error in critical_errors:
                    f.write(f"### {error['component'].title()}\n")
                    f.write(f"**Error:** {error['error']}\n")
                    f.write(f"**Time:** {error['timestamp']}\n")
                    if error['details']:
                        f.write(f"**Details:** {error['details']}\n")
                    f.write("\n")
            else:
                f.write("No critical errors found.\n\n")
                
            # Feature test results
            f.write("## Feature Test Results\n\n")
            for journey, result in self.test_results["user_journey_results"].items():
                status_icon = "✅" if result["status"] == "completed" else "❌"
                f.write(f"- {status_icon} **{journey}**: {result['status']} ({result['duration']:.2f}s)\n")
            f.write("\n")
            
            # API endpoint status
            f.write("## API Endpoint Status\n\n")
            for endpoint, status in self.test_results["backend_status"].items():
                status_icon = "✅" if status["status"] == "success" else "❌"
                f.write(f"- {status_icon} **{endpoint}**: {status['status']} ({status.get('response_time', 0):.2f}s)\n")
            f.write("\n")
            
            # Frontend page status
            f.write("## Frontend Page Status\n\n")
            for page, status in self.test_results["frontend_status"].items():
                status_icon = "✅" if status["status"] == "success" else "❌"
                f.write(f"- {status_icon} **{page}**: {status['status']} ({status.get('response_time', 0):.2f}s)\n")
            f.write("\n")
            
            # All errors
            f.write("## All Errors\n\n")
            for error in self.test_results["errors"]:
                f.write(f"**[{error['component']}]** {error['error']} - {error['timestamp']}\n")
                if error['details']:
                    f.write(f"Details: {error['details']}\n")
                f.write("\n")
                
        self.logger.info(f"Summary report saved to: {summary_file}")

    def cleanup(self):
        """Clean up processes and resources"""
        self.logger.info("Cleaning up test environment...")
        
        # Terminate backend process
        if hasattr(self, 'backend_process') and self.backend_process:
            self.backend_process.terminate()
            self.backend_process.wait(timeout=10)
            
        # Terminate frontend process  
        if hasattr(self, 'frontend_process') and self.frontend_process:
            self.frontend_process.terminate()
            self.frontend_process.wait(timeout=10)
            
        self.logger.info("Cleanup completed")

    async def run_comprehensive_test(self):
        """Run the complete test suite"""
        self.logger.info("Starting comprehensive test suite...")
        
        try:
            # Phase 1: Start and test backend
            self.test_backend_startup()
            await asyncio.sleep(5)
            
            # Phase 2: Start and test frontend
            self.test_frontend_startup()
            await asyncio.sleep(5)
            
            # Phase 3: Test user journeys
            self.test_user_journeys()
            await asyncio.sleep(2)
            
            # Phase 4: Test WebSocket features
            self.test_websocket_features()
            await asyncio.sleep(2)
            
            # Phase 5: Generate reports
            self.generate_comprehensive_report()
            
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    monitor = ComprehensiveMonitor()
    
    try:
        asyncio.run(monitor.run_comprehensive_test())
        print(f"\n✅ Comprehensive testing completed!")
        print(f"📊 Reports saved to: {monitor.log_dir}")
        print(f"🔍 Check the logs for detailed analysis")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        monitor.cleanup()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        monitor.cleanup()

if __name__ == "__main__":
    main()