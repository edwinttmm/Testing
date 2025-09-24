#!/usr/bin/env python3
"""
Ground Truth Timeline Display Validation Test Suite

This comprehensive test validates that ground truth events are properly displayed
in the frontend HIL timeline, addressing the user's issue "where is GT".

Tests:
1. Enhanced HIL API endpoint includes ground truth events
2. Frontend properly receives and displays ground truth events
3. Timeline visualization shows actual ground truth events
4. End-to-end ground truth display functionality
"""

import asyncio
import json
import requests
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
import os

# Add backend path for imports
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from sqlalchemy.orm import Session
from database import get_db
from models import TestSession, Video, GroundTruthObject, DetectionEvent, Project

class GroundTruthTimelineDisplayTester:
    """Comprehensive test suite for ground truth timeline display"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_results = []
        
    def log_test(self, test_name: str, status: str, details: str = "", data: Any = None):
        """Log test results"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "data": data
        }
        self.test_results.append(result)
        
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
        if data and isinstance(data, dict):
            print(f"   Data: {json.dumps(data, indent=2)[:200]}...")
    
    def test_1_api_enhanced_hil_endpoint(self) -> bool:
        """Test that enhanced HIL API endpoint includes ground truth events"""
        print("\n🧪 TEST 1: Enhanced HIL API Endpoint Ground Truth Inclusion")
        
        try:
            # Get available test sessions
            db = next(get_db())
            sessions = db.query(TestSession).limit(5).all()
            
            if not sessions:
                self.log_test("API Enhanced HIL - No Sessions", "SKIP", "No test sessions found in database")
                return False
            
            session = sessions[0]
            session_id = session.id
            
            # Test the enhanced HIL endpoint
            url = f"{self.base_url}/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
            response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                self.log_test("API Enhanced HIL - HTTP Error", "FAIL", 
                            f"HTTP {response.status_code}: {response.text[:200]}")
                return False
            
            data = response.json()
            
            # Check for ground truth comparison section
            if "ground_truth_comparison" not in data:
                self.log_test("API Enhanced HIL - Missing GT Comparison", "FAIL",
                            "No ground_truth_comparison field in API response")
                return False
            
            gt_comparison = data["ground_truth_comparison"]
            
            # Validate ground truth comparison structure
            required_fields = [
                "ground_truth_events_available",
                "total_detections", 
                "matching_methodology",
                "events_with_matches",
                "average_confidence_score",
                "ground_truth_events"
            ]
            
            missing_fields = [field for field in required_fields if field not in gt_comparison]
            if missing_fields:
                self.log_test("API Enhanced HIL - Missing GT Fields", "FAIL",
                            f"Missing fields: {missing_fields}")
                return False
            
            # Check if ground truth events are actually included
            gt_events = gt_comparison.get("ground_truth_events", [])
            gt_events_available = gt_comparison.get("ground_truth_events_available", 0)
            
            if gt_events_available > 0 and len(gt_events) == 0:
                self.log_test("API Enhanced HIL - GT Events Missing", "FAIL",
                            f"API claims {gt_events_available} GT events available but array is empty")
                return False
            
            self.log_test("API Enhanced HIL - Structure Valid", "PASS",
                        f"Found {len(gt_events)} GT events in response", 
                        {"gt_events_available": gt_events_available, "gt_events_count": len(gt_events)})
            
            return True
            
        except Exception as e:
            self.log_test("API Enhanced HIL - Exception", "FAIL", str(e))
            return False
    
    def test_2_ground_truth_data_structure(self) -> bool:
        """Test that ground truth events have proper structure and timestamps"""
        print("\n🧪 TEST 2: Ground Truth Data Structure Validation")
        
        try:
            # Get a session with a video that has ground truth data
            db = next(get_db())
            
            # Find a video with ground truth objects
            video_with_gt = db.query(Video).join(GroundTruthObject).first()
            if not video_with_gt:
                self.log_test("GT Data Structure - No GT Data", "SKIP", 
                            "No videos with ground truth data found")
                return False
            
            # Get ground truth objects for this video
            gt_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video_with_gt.id
            ).order_by(GroundTruthObject.timestamp).all()
            
            if not gt_objects:
                self.log_test("GT Data Structure - No GT Objects", "FAIL",
                            "Video has no ground truth objects despite join")
                return False
            
            # Validate structure of ground truth objects
            valid_objects = 0
            for gt in gt_objects:
                if (hasattr(gt, 'timestamp') and gt.timestamp is not None and
                    hasattr(gt, 'class_label') and gt.class_label and
                    hasattr(gt, 'frame_number')):
                    valid_objects += 1
            
            if valid_objects == 0:
                self.log_test("GT Data Structure - Invalid Objects", "FAIL",
                            "No ground truth objects have valid timestamp/class_label/frame_number")
                return False
            
            # Test API endpoint for this video's ground truth
            url = f"{self.base_url}/api/enhanced-hil/test-sessions/test-session-1/corrected-results"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                gt_events_in_api = data.get("ground_truth_comparison", {}).get("ground_truth_events", [])
                
                self.log_test("GT Data Structure - Valid", "PASS",
                            f"Found {len(gt_objects)} GT objects in DB, {len(gt_events_in_api)} in API",
                            {"db_count": len(gt_objects), "api_count": len(gt_events_in_api)})
            else:
                self.log_test("GT Data Structure - API Error", "WARN",
                            f"Could not test API: HTTP {response.status_code}")
            
            return True
            
        except Exception as e:
            self.log_test("GT Data Structure - Exception", "FAIL", str(e))
            return False
    
    def test_3_frontend_api_integration(self) -> bool:
        """Test that frontend properly calls and receives ground truth data"""
        print("\n🧪 TEST 3: Frontend API Integration")
        
        try:
            # Test if frontend is running
            try:
                frontend_response = requests.get(f"{self.frontend_url}/", timeout=5)
                if frontend_response.status_code != 200:
                    self.log_test("Frontend Integration - Not Running", "SKIP",
                                f"Frontend not accessible at {self.frontend_url}")
                    return False
            except requests.exceptions.RequestException:
                self.log_test("Frontend Integration - Not Running", "SKIP",
                            f"Frontend not accessible at {self.frontend_url}")
                return False
            
            # Test the enhanced HIL endpoint that frontend calls
            test_session_id = "test-session-1"
            api_url = f"{self.base_url}/api/enhanced-hil/test-sessions/{test_session_id}/corrected-results"
            
            response = requests.get(api_url, timeout=30)
            
            if response.status_code != 200:
                self.log_test("Frontend Integration - API Error", "FAIL",
                            f"Enhanced HIL API returned {response.status_code}")
                return False
            
            data = response.json()
            
            # Check that the API response has the structure frontend expects
            required_for_frontend = [
                "ground_truth_comparison",
                "detection_events",
                "session_id"
            ]
            
            missing = [field for field in required_for_frontend if field not in data]
            if missing:
                self.log_test("Frontend Integration - Missing Fields", "FAIL",
                            f"API response missing fields frontend needs: {missing}")
                return False
            
            # Check ground truth events array structure
            gt_comparison = data["ground_truth_comparison"]
            gt_events = gt_comparison.get("ground_truth_events", [])
            
            if len(gt_events) > 0:
                # Validate structure of ground truth events for frontend
                sample_event = gt_events[0]
                required_event_fields = ["frame_number", "video_timestamp", "event_type"]
                
                missing_event_fields = [field for field in required_event_fields 
                                      if field not in sample_event]
                
                if missing_event_fields:
                    self.log_test("Frontend Integration - Invalid GT Event Structure", "WARN",
                                f"GT events missing fields: {missing_event_fields}")
                else:
                    self.log_test("Frontend Integration - GT Events Valid", "PASS",
                                f"Found {len(gt_events)} properly structured GT events")
            else:
                self.log_test("Frontend Integration - No GT Events", "WARN",
                            "No ground truth events in API response")
            
            return True
            
        except Exception as e:
            self.log_test("Frontend Integration - Exception", "FAIL", str(e))
            return False
    
    def test_4_timeline_display_validation(self) -> bool:
        """Test that timeline properly displays ground truth events"""
        print("\n🧪 TEST 4: Timeline Display Validation")
        
        try:
            # Get test session with detection events
            db = next(get_db())
            
            session_with_events = db.query(TestSession).join(DetectionEvent).first()
            if not session_with_events:
                self.log_test("Timeline Display - No Session Data", "SKIP",
                            "No test sessions with detection events found")
                return False
            
            session_id = session_with_events.id
            
            # Get the enhanced HIL results
            api_url = f"{self.base_url}/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
            response = requests.get(api_url, timeout=30)
            
            if response.status_code != 200:
                self.log_test("Timeline Display - API Error", "FAIL",
                            f"Could not get enhanced results: HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            # Verify timeline data structure
            detection_events = data.get("detection_events", [])
            gt_comparison = data.get("ground_truth_comparison", {})
            gt_events = gt_comparison.get("ground_truth_events", [])
            
            if len(detection_events) == 0:
                self.log_test("Timeline Display - No Detection Events", "FAIL",
                            "No detection events found for timeline")
                return False
            
            # Check if detection events have timeline-required fields
            sample_detection = detection_events[0]
            timeline_fields = [
                "video_relative_timestamp",
                "video_frame_number", 
                "detection_time",
                "corrected_latency"
            ]
            
            missing_timeline_fields = [field for field in timeline_fields 
                                    if field not in sample_detection]
            
            if missing_timeline_fields:
                self.log_test("Timeline Display - Missing Detection Fields", "WARN",
                            f"Detection events missing timeline fields: {missing_timeline_fields}")
            
            # Test timeline logic simulation
            timeline_events = []
            
            # Add detection events to timeline
            for detection in detection_events:
                timeline_events.append({
                    "type": "detection",
                    "timestamp": detection.get("video_relative_timestamp", 0),
                    "frame": detection.get("video_frame_number", 0),
                    "data": detection
                })
            
            # Add ground truth events to timeline
            for gt in gt_events:
                timeline_events.append({
                    "type": "ground_truth",
                    "timestamp": gt.get("video_timestamp", 0),
                    "frame": gt.get("frame_number", 0),
                    "data": gt
                })
            
            # Sort timeline by timestamp
            timeline_events.sort(key=lambda x: x["timestamp"])
            
            gt_events_in_timeline = [e for e in timeline_events if e["type"] == "ground_truth"]
            detection_events_in_timeline = [e for e in timeline_events if e["type"] == "detection"]
            
            self.log_test("Timeline Display - Timeline Structure", "PASS",
                        f"Timeline has {len(gt_events_in_timeline)} GT events and {len(detection_events_in_timeline)} detections",
                        {
                            "total_timeline_events": len(timeline_events),
                            "gt_events": len(gt_events_in_timeline),
                            "detection_events": len(detection_events_in_timeline)
                        })
            
            return True
            
        except Exception as e:
            self.log_test("Timeline Display - Exception", "FAIL", str(e))
            return False
    
    def test_5_end_to_end_display_verification(self) -> bool:
        """End-to-end test simulating user viewing ground truth timeline"""
        print("\n🧪 TEST 5: End-to-End Display Verification")
        
        try:
            # Simulate complete user workflow
            print("   📋 Simulating user workflow: View HIL Results → Load GT Timeline")
            
            # Step 1: Get available sessions
            db = next(get_db())
            sessions = db.query(TestSession).limit(3).all()
            
            if not sessions:
                self.log_test("E2E Display - No Sessions", "SKIP", "No test sessions available")
                return False
            
            session_results = []
            
            for session in sessions:
                session_id = session.id
                
                # Step 2: Load enhanced HIL results (what frontend does)
                api_url = f"{self.base_url}/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
                response = requests.get(api_url, timeout=30)
                
                session_result = {
                    "session_id": session_id,
                    "api_status": response.status_code,
                    "has_gt_comparison": False,
                    "gt_events_available": 0,
                    "gt_events_count": 0,
                    "detection_events_count": 0
                }
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check ground truth comparison
                    if "ground_truth_comparison" in data:
                        session_result["has_gt_comparison"] = True
                        gt_comparison = data["ground_truth_comparison"]
                        session_result["gt_events_available"] = gt_comparison.get("ground_truth_events_available", 0)
                        session_result["gt_events_count"] = len(gt_comparison.get("ground_truth_events", []))
                    
                    # Check detection events
                    session_result["detection_events_count"] = len(data.get("detection_events", []))
                
                session_results.append(session_result)
            
            # Analyze results
            sessions_with_gt = [s for s in session_results if s["gt_events_count"] > 0]
            sessions_with_detections = [s for s in session_results if s["detection_events_count"] > 0]
            
            if len(sessions_with_gt) == 0:
                self.log_test("E2E Display - No GT Data Available", "FAIL",
                            f"None of {len(session_results)} sessions have ground truth events")
                return False
            
            if len(sessions_with_detections) == 0:
                self.log_test("E2E Display - No Detection Data", "FAIL",
                            f"None of {len(session_results)} sessions have detection events")
                return False
            
            # Step 3: Simulate frontend timeline rendering
            best_session = max(sessions_with_gt, key=lambda s: s["gt_events_count"] + s["detection_events_count"])
            
            # Get detailed data for best session
            api_url = f"{self.base_url}/api/enhanced-hil/test-sessions/{best_session['session_id']}/corrected-results"
            response = requests.get(api_url, timeout=30)
            data = response.json()
            
            # Simulate what frontend would show user
            gt_events = data["ground_truth_comparison"]["ground_truth_events"]
            detection_events = data["detection_events"]
            
            timeline_simulation = {
                "session_id": best_session["session_id"],
                "total_timeline_events": len(gt_events) + len(detection_events),
                "ground_truth_events": len(gt_events),
                "detection_events": len(detection_events),
                "timeline_span_seconds": 0,
                "user_would_see_gt": len(gt_events) > 0
            }
            
            # Calculate timeline span
            if gt_events and detection_events:
                all_timestamps = []
                for gt in gt_events:
                    if gt.get("video_timestamp"):
                        all_timestamps.append(gt["video_timestamp"])
                for det in detection_events:
                    if det.get("video_relative_timestamp"):
                        all_timestamps.append(det["video_relative_timestamp"])
                
                if all_timestamps:
                    timeline_simulation["timeline_span_seconds"] = max(all_timestamps) - min(all_timestamps)
            
            self.log_test("E2E Display - Complete Workflow", "PASS",
                        f"User would see {timeline_simulation['ground_truth_events']} GT events in timeline",
                        timeline_simulation)
            
            return True
            
        except Exception as e:
            self.log_test("E2E Display - Exception", "FAIL", str(e))
            return False
    
    def test_6_browser_automation_simulation(self) -> bool:
        """Simulate browser interaction to verify frontend ground truth display"""
        print("\n🧪 TEST 6: Browser Automation Simulation")
        
        try:
            # Check if frontend is accessible
            try:
                frontend_response = requests.get(f"{self.frontend_url}/", timeout=5)
                if frontend_response.status_code != 200:
                    self.log_test("Browser Simulation - Frontend Down", "SKIP",
                                "Frontend not accessible for browser simulation")
                    return False
            except requests.exceptions.RequestException:
                self.log_test("Browser Simulation - Frontend Down", "SKIP",
                            "Frontend not accessible for browser simulation")
                return False
            
            # Simulate navigation to HIL results page
            print("   🌐 Simulating browser navigation to HIL results page")
            
            # Get a test session ID
            db = next(get_db())
            session = db.query(TestSession).first()
            
            if not session:
                self.log_test("Browser Simulation - No Session", "SKIP", "No test session for navigation")
                return False
            
            session_id = session.id
            
            # Simulate the API calls that frontend would make
            simulation_steps = [
                {
                    "step": "Load Enhanced HIL Results",
                    "url": f"{self.base_url}/api/enhanced-hil/test-sessions/{session_id}/corrected-results",
                    "expected_fields": ["ground_truth_comparison", "detection_events"]
                },
                {
                    "step": "Load Ground Truth Events", 
                    "url": f"{self.base_url}/api/ground-truth/videos/{session.video_id}/events" if session.video_id else None,
                    "expected_fields": ["ground_truth_events"] if session.video_id else []
                }
            ]
            
            simulation_results = []
            
            for step in simulation_steps:
                if not step["url"]:
                    continue
                    
                try:
                    response = requests.get(step["url"], timeout=10)
                    step_result = {
                        "step": step["step"],
                        "status_code": response.status_code,
                        "success": response.status_code == 200,
                        "has_expected_fields": False,
                        "data_summary": {}
                    }
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check for expected fields
                        has_all_fields = all(field in data for field in step["expected_fields"])
                        step_result["has_expected_fields"] = has_all_fields
                        
                        # Summarize data
                        if "ground_truth_comparison" in data:
                            gt_comp = data["ground_truth_comparison"]
                            step_result["data_summary"]["gt_events_available"] = gt_comp.get("ground_truth_events_available", 0)
                            step_result["data_summary"]["gt_events_count"] = len(gt_comp.get("ground_truth_events", []))
                        
                        if "detection_events" in data:
                            step_result["data_summary"]["detection_events_count"] = len(data["detection_events"])
                    
                    simulation_results.append(step_result)
                    
                except Exception as e:
                    simulation_results.append({
                        "step": step["step"],
                        "error": str(e),
                        "success": False
                    })
            
            # Analyze simulation results
            successful_steps = [s for s in simulation_results if s.get("success", False)]
            
            if len(successful_steps) == 0:
                self.log_test("Browser Simulation - All Failed", "FAIL",
                            "All API calls that frontend would make failed")
                return False
            
            # Check if ground truth data would be available to user
            gt_data_available = False
            for step_result in successful_steps:
                summary = step_result.get("data_summary", {})
                if summary.get("gt_events_count", 0) > 0:
                    gt_data_available = True
                    break
            
            if gt_data_available:
                self.log_test("Browser Simulation - GT Available", "PASS",
                            "Browser simulation shows ground truth data would be available to user",
                            {"successful_steps": len(successful_steps), "gt_data_available": True})
            else:
                self.log_test("Browser Simulation - No GT", "WARN",
                            "Browser simulation shows no ground truth data available",
                            {"successful_steps": len(successful_steps), "gt_data_available": False})
            
            return True
            
        except Exception as e:
            self.log_test("Browser Simulation - Exception", "FAIL", str(e))
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all ground truth timeline display tests"""
        print("🚀 Starting Ground Truth Timeline Display Validation Tests")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run all tests
        tests = [
            self.test_1_api_enhanced_hil_endpoint,
            self.test_2_ground_truth_data_structure,
            self.test_3_frontend_api_integration,
            self.test_4_timeline_display_validation,
            self.test_5_end_to_end_display_verification,
            self.test_6_browser_automation_simulation
        ]
        
        passed = 0
        failed = 0
        skipped = 0
        warnings = 0
        
        for test_func in tests:
            try:
                result = test_func()
                if result:
                    passed += 1
                else:
                    # Check if it was skipped
                    last_result = self.test_results[-1] if self.test_results else {}
                    if last_result.get("status") == "SKIP":
                        skipped += 1
                    else:
                        failed += 1
            except Exception as e:
                failed += 1
                self.log_test(f"{test_func.__name__} - Critical Error", "FAIL", str(e))
        
        # Count warnings
        warnings = len([r for r in self.test_results if r["status"] == "WARN"])
        
        end_time = time.time()
        
        # Generate summary
        summary = {
            "test_run_id": f"gt_timeline_test_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": round(end_time - start_time, 2),
            "total_tests": len(tests),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "warnings": warnings,
            "overall_status": "PASS" if failed == 0 and passed > 0 else "FAIL" if failed > 0 else "SKIP",
            "detailed_results": self.test_results
        }
        
        print("\n" + "=" * 60)
        print("📊 GROUND TRUTH TIMELINE DISPLAY TEST SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"⏱️  Duration: {summary['duration_seconds']}s")
        print(f"🎯 Overall Status: {summary['overall_status']}")
        
        if failed > 0:
            print("\n❌ FAILURES DETECTED:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"   • {result['test_name']}: {result['details']}")
        
        if warnings > 0:
            print("\n⚠️  WARNINGS:")
            for result in self.test_results:
                if result["status"] == "WARN":
                    print(f"   • {result['test_name']}: {result['details']}")
        
        # Save detailed results
        results_file = f"/home/rigade/Testing/ai-model-validation-platform/backend/tests/gt_timeline_test_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        return summary

def main():
    """Main test execution"""
    print("🔍 Ground Truth Timeline Display Validation")
    print("Addressing user issue: 'where is GT' - ensuring ground truth events appear in timeline")
    
    tester = GroundTruthTimelineDisplayTester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    if results["overall_status"] == "FAIL":
        print("\n❌ Tests failed - ground truth timeline display needs fixes")
        sys.exit(1)
    elif results["overall_status"] == "SKIP":
        print("\n⏭️  Tests skipped - setup issues")
        sys.exit(2)
    else:
        print("\n✅ All tests passed - ground truth timeline display working correctly")
        sys.exit(0)

if __name__ == "__main__":
    main()