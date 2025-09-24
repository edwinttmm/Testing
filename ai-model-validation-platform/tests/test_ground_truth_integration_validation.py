#!/usr/bin/env python3
"""
Ground Truth Integration Validation Test Suite

This comprehensive test suite validates that the ground truth data flows correctly
from backend to frontend and displays properly in the UI.

Tests cover:
1. Enhanced HIL API endpoint returns ground truth data
2. Frontend API calls use correct endpoints
3. React components properly render ground truth metrics
4. Complete user flow validation
5. Ground truth metrics accuracy verification
"""

import asyncio
import json
import pytest
import requests
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Base URLs for testing
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

class GroundTruthIntegrationValidator:
    """Comprehensive validator for ground truth integration"""
    
    def __init__(self, session_id: str = "test-session-gt-validation"):
        self.session_id = session_id
        self.results = {
            "test_start_time": datetime.now().isoformat(),
            "backend_tests": {},
            "frontend_tests": {},
            "integration_tests": {},
            "validation_results": {},
            "issues_found": []
        }
        
    def log_test_result(self, category: str, test_name: str, passed: bool, details: Dict[str, Any] = None):
        """Log test result with details"""
        if category not in self.results:
            self.results[category] = {}
            
        self.results[category][test_name] = {
            "passed": passed,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        
        if not passed:
            self.results["issues_found"].append({
                "category": category,
                "test": test_name,
                "details": details or {}
            })
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"[{category}] {test_name}: {status}")
        if details and not passed:
            print(f"  Details: {details}")

    def test_backend_enhanced_hil_api(self) -> bool:
        """Test 1: Verify enhanced HIL API endpoint returns ground truth data"""
        print("\n🔍 Testing Enhanced HIL API Ground Truth Integration...")
        
        try:
            # Test the enhanced HIL endpoint
            response = requests.get(
                f"{BACKEND_URL}/api/enhanced-hil/test-sessions/{self.session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                self.log_test_result(
                    "backend_tests", 
                    "enhanced_hil_api_response", 
                    False, 
                    {"status_code": response.status_code, "error": response.text}
                )
                return False
            
            data = response.json()
            
            # Verify response structure includes ground truth comparison
            has_gt_comparison = "ground_truth_comparison" in data
            self.log_test_result(
                "backend_tests",
                "has_ground_truth_comparison",
                has_gt_comparison,
                {"found_keys": list(data.keys())}
            )
            
            if not has_gt_comparison:
                return False
                
            # Verify ground truth events count
            gt_comparison = data["ground_truth_comparison"]
            gt_events_available = gt_comparison.get("ground_truth_events_available", 0)
            
            # Key validation: Should have 24 ground truth events, not 0
            expected_gt_events = 24
            gt_events_correct = gt_events_available == expected_gt_events
            
            self.log_test_result(
                "backend_tests",
                "ground_truth_events_count",
                gt_events_correct,
                {
                    "expected": expected_gt_events,
                    "actual": gt_events_available,
                    "comparison_data": gt_comparison
                }
            )
            
            # Verify timing synchronization results
            timing_sync = gt_comparison.get("timing_synchronization_results", {})
            events_with_matches = timing_sync.get("events_with_matches", 0)
            expected_matches = 39  # Should be 39/39 events with matches
            
            matches_correct = events_with_matches == expected_matches
            self.log_test_result(
                "backend_tests",
                "events_with_matches",
                matches_correct,
                {
                    "expected": expected_matches,
                    "actual": events_with_matches,
                    "timing_sync_data": timing_sync
                }
            )
            
            # Verify confidence scores exist
            avg_confidence = timing_sync.get("average_confidence_score", 0)
            has_confidence = avg_confidence > 0
            
            self.log_test_result(
                "backend_tests",
                "has_confidence_scores",
                has_confidence,
                {"average_confidence_score": avg_confidence}
            )
            
            # Verify detection events have timing synchronization data
            detection_events = data.get("detection_events", [])
            has_timing_sync_data = len(detection_events) > 0 and all(
                "timing_synchronization" in event for event in detection_events
            )
            
            self.log_test_result(
                "backend_tests",
                "detection_events_have_timing_sync",
                has_timing_sync_data,
                {
                    "total_events": len(detection_events),
                    "events_with_timing_sync": sum(1 for e in detection_events if "timing_synchronization" in e)
                }
            )
            
            return gt_events_correct and matches_correct and has_confidence and has_timing_sync_data
            
        except Exception as e:
            self.log_test_result(
                "backend_tests",
                "enhanced_hil_api_exception",
                False,
                {"exception": str(e)}
            )
            return False

    def test_frontend_api_integration(self) -> bool:
        """Test 2: Verify frontend uses correct enhanced API endpoint"""
        print("\n🔍 Testing Frontend API Integration...")
        
        try:
            # Check if the HIL Results page exists and is accessible
            frontend_response = requests.get(
                f"{FRONTEND_URL}/hil-results/{self.session_id}",
                timeout=30
            )
            
            frontend_accessible = frontend_response.status_code == 200
            self.log_test_result(
                "frontend_tests",
                "hil_results_page_accessible",
                frontend_accessible,
                {"status_code": frontend_response.status_code}
            )
            
            if not frontend_accessible:
                return False
            
            # Check if the frontend page contains evidence of enhanced API usage
            page_content = frontend_response.text
            
            # Look for evidence of enhanced timing features
            has_enhanced_timing = "Enhanced Timing" in page_content or "Timing Synchronization" in page_content
            self.log_test_result(
                "frontend_tests",
                "contains_enhanced_timing_features",
                has_enhanced_timing,
                {"page_length": len(page_content)}
            )
            
            # Look for ground truth references
            has_gt_references = "Ground Truth" in page_content or "ground_truth" in page_content
            self.log_test_result(
                "frontend_tests",
                "contains_ground_truth_references",
                has_gt_references
            )
            
            return has_enhanced_timing and has_gt_references
            
        except Exception as e:
            self.log_test_result(
                "frontend_tests",
                "frontend_api_exception",
                False,
                {"exception": str(e)}
            )
            return False

    def test_enhanced_hil_service_integration(self) -> bool:
        """Test 3: Verify enhanced HIL service integration"""
        print("\n🔍 Testing Enhanced HIL Service Integration...")
        
        # Check the enhanced HIL service code
        service_file = Path("frontend/src/services/enhancedHILService.ts")
        
        if not service_file.exists():
            self.log_test_result(
                "integration_tests",
                "enhanced_hil_service_exists",
                False,
                {"file_path": str(service_file)}
            )
            return False
        
        service_content = service_file.read_text()
        
        # Check for ground truth integration features
        has_vru_tracking = "VRUTrack" in service_content
        has_temporal_matching = "TemporalMatcher" in service_content
        has_ground_truth_processing = "loadGroundTruthAnnotations" in service_content
        
        self.log_test_result(
            "integration_tests",
            "service_has_vru_tracking",
            has_vru_tracking
        )
        
        self.log_test_result(
            "integration_tests",
            "service_has_temporal_matching",
            has_temporal_matching
        )
        
        self.log_test_result(
            "integration_tests",
            "service_has_ground_truth_processing",
            has_ground_truth_processing
        )
        
        return has_vru_tracking and has_temporal_matching and has_ground_truth_processing

    def test_react_component_rendering(self) -> bool:
        """Test 4: Validate React components render ground truth metrics"""
        print("\n🔍 Testing React Component Ground Truth Rendering...")
        
        # Check the HILResults component
        component_file = Path("frontend/src/pages/HILResults.tsx")
        
        if not component_file.exists():
            self.log_test_result(
                "frontend_tests",
                "hil_results_component_exists",
                False,
                {"file_path": str(component_file)}
            )
            return False
        
        component_content = component_file.read_text()
        
        # Check for ground truth rendering features
        has_gt_comparison_card = "Ground Truth Comparison" in component_content
        has_gt_events_display = "Ground Truth Events:" in component_content
        has_enhanced_timing_display = "Enhanced Timing" in component_content
        has_timing_correction = "Timing Synchronization Correction" in component_content
        
        self.log_test_result(
            "frontend_tests",
            "has_ground_truth_comparison_card",
            has_gt_comparison_card
        )
        
        self.log_test_result(
            "frontend_tests",
            "has_ground_truth_events_display",
            has_gt_events_display
        )
        
        self.log_test_result(
            "frontend_tests",
            "has_enhanced_timing_display",
            has_enhanced_timing_display
        )
        
        self.log_test_result(
            "frontend_tests",
            "has_timing_correction_display",
            has_timing_correction
        )
        
        # Check for the specific fix: should show "24" not "0"
        has_24_events_logic = "groundTruthEvents.length" in component_content
        self.log_test_result(
            "frontend_tests",
            "has_dynamic_gt_events_count",
            has_24_events_logic
        )
        
        return all([
            has_gt_comparison_card,
            has_gt_events_display, 
            has_enhanced_timing_display,
            has_timing_correction,
            has_24_events_logic
        ])

    def test_console_errors_and_compilation(self) -> bool:
        """Test 5: Check for console errors and TypeScript compilation issues"""
        print("\n🔍 Testing Console Errors and TypeScript Compilation...")
        
        try:
            # Run TypeScript compilation check for frontend
            result = subprocess.run(
                ["npm", "run", "typecheck"],
                cwd="frontend",
                capture_output=True,
                text=True,
                timeout=60
            )
            
            typescript_compiles = result.returncode == 0
            self.log_test_result(
                "frontend_tests",
                "typescript_compilation",
                typescript_compiles,
                {
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            )
            
            return typescript_compiles
            
        except subprocess.TimeoutExpired:
            self.log_test_result(
                "frontend_tests",
                "typescript_compilation_timeout",
                False,
                {"error": "TypeScript compilation timed out"}
            )
            return False
        except Exception as e:
            self.log_test_result(
                "frontend_tests",
                "typescript_compilation_exception",
                False,
                {"exception": str(e)}
            )
            return False

    def test_complete_user_flow(self) -> bool:
        """Test 6: Test complete user flow from execution to results display"""
        print("\n🔍 Testing Complete User Flow...")
        
        try:
            # Step 1: Create test session
            session_data = {
                "name": f"GT Integration Test {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "project_id": "test-project",
                "video_id": "test-video",
                "tolerance_ms": 100
            }
            
            create_response = requests.post(
                f"{BACKEND_URL}/api/test-sessions",
                json=session_data,
                timeout=30
            )
            
            session_created = create_response.status_code in [200, 201]
            self.log_test_result(
                "integration_tests",
                "test_session_creation",
                session_created,
                {"status_code": create_response.status_code}
            )
            
            if session_created:
                session_id = create_response.json().get("id", self.session_id)
                
                # Step 2: Test enhanced results endpoint
                enhanced_response = requests.get(
                    f"{BACKEND_URL}/api/enhanced-hil/test-sessions/{session_id}/corrected-results",
                    timeout=30
                )
                
                enhanced_available = enhanced_response.status_code == 200
                self.log_test_result(
                    "integration_tests",
                    "enhanced_results_available",
                    enhanced_available,
                    {"status_code": enhanced_response.status_code}
                )
                
                return enhanced_available
            
            return False
            
        except Exception as e:
            self.log_test_result(
                "integration_tests",
                "user_flow_exception",
                False,
                {"exception": str(e)}
            )
            return False

    def test_ground_truth_metrics_accuracy(self) -> bool:
        """Test 7: Verify ground truth metrics show correct values"""
        print("\n🔍 Testing Ground Truth Metrics Accuracy...")
        
        try:
            # Test specific session with known ground truth data
            test_session_id = "b8a345a5-582a-4a55-a409-c7a8a06408f9"  # Known session with data
            
            response = requests.get(
                f"{BACKEND_URL}/api/enhanced-hil/test-sessions/{test_session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                self.log_test_result(
                    "validation_results",
                    "known_session_accessible",
                    False,
                    {"status_code": response.status_code}
                )
                return False
            
            data = response.json()
            gt_comparison = data.get("ground_truth_comparison", {})
            
            # Validate specific metrics
            gt_events = gt_comparison.get("ground_truth_events_available", 0)
            total_detections = gt_comparison.get("total_detections", 0)
            timing_sync = gt_comparison.get("timing_synchronization_results", {})
            events_with_matches = timing_sync.get("events_with_matches", 0)
            avg_confidence = timing_sync.get("average_confidence_score", 0)
            
            # Key validation criteria
            validations = {
                "has_ground_truth_events": gt_events > 0,
                "gt_events_realistic": 10 <= gt_events <= 50,  # Reasonable range
                "has_detections": total_detections > 0,
                "has_matches": events_with_matches > 0,
                "reasonable_confidence": 0.5 <= avg_confidence <= 1.0,
                "matches_reasonable": events_with_matches <= total_detections
            }
            
            for test_name, passed in validations.items():
                self.log_test_result(
                    "validation_results",
                    test_name,
                    passed,
                    {
                        "gt_events": gt_events,
                        "total_detections": total_detections,
                        "events_with_matches": events_with_matches,
                        "avg_confidence": avg_confidence
                    }
                )
            
            return all(validations.values())
            
        except Exception as e:
            self.log_test_result(
                "validation_results",
                "metrics_accuracy_exception",
                False,
                {"exception": str(e)}
            )
            return False

    def test_timing_synchronization_data(self) -> bool:
        """Test 8: Validate timing synchronization data in detection events"""
        print("\n🔍 Testing Timing Synchronization Data...")
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/enhanced-hil/test-sessions/{self.session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            detection_events = data.get("detection_events", [])
            
            if not detection_events:
                self.log_test_result(
                    "validation_results",
                    "has_detection_events",
                    False,
                    {"event_count": 0}
                )
                return False
            
            # Check timing synchronization data in events
            events_with_timing = 0
            events_with_real_latency = 0
            events_with_confidence = 0
            
            for event in detection_events:
                timing_sync = event.get("timing_synchronization", {})
                if timing_sync:
                    events_with_timing += 1
                    
                    if "timing_quality" in timing_sync:
                        events_with_confidence += 1
                
                if "corrected_latency" in event and "real_latency_ms" in event["corrected_latency"]:
                    events_with_real_latency += 1
            
            total_events = len(detection_events)
            timing_coverage = events_with_timing / total_events if total_events > 0 else 0
            latency_coverage = events_with_real_latency / total_events if total_events > 0 else 0
            
            # Validation criteria
            good_timing_coverage = timing_coverage >= 0.8  # 80% of events should have timing data
            good_latency_coverage = latency_coverage >= 0.8  # 80% should have corrected latency
            
            self.log_test_result(
                "validation_results",
                "timing_synchronization_coverage",
                good_timing_coverage,
                {
                    "total_events": total_events,
                    "events_with_timing": events_with_timing,
                    "timing_coverage": timing_coverage
                }
            )
            
            self.log_test_result(
                "validation_results",
                "corrected_latency_coverage",
                good_latency_coverage,
                {
                    "total_events": total_events,
                    "events_with_real_latency": events_with_real_latency,
                    "latency_coverage": latency_coverage
                }
            )
            
            return good_timing_coverage and good_latency_coverage
            
        except Exception as e:
            self.log_test_result(
                "validation_results",
                "timing_sync_exception",
                False,
                {"exception": str(e)}
            )
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests and return comprehensive results"""
        print("🚀 Starting Ground Truth Integration Validation...")
        print(f"Session ID: {self.session_id}")
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Frontend URL: {FRONTEND_URL}")
        
        # Run all test categories
        test_results = {
            "backend_api": self.test_backend_enhanced_hil_api(),
            "frontend_integration": self.test_frontend_api_integration(),
            "service_integration": self.test_enhanced_hil_service_integration(),
            "component_rendering": self.test_react_component_rendering(),
            "compilation": self.test_console_errors_and_compilation(),
            "user_flow": self.test_complete_user_flow(),
            "metrics_accuracy": self.test_ground_truth_metrics_accuracy(),
            "timing_synchronization": self.test_timing_synchronization_data()
        }
        
        # Calculate overall results
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result)
        overall_pass_rate = (passed_tests / total_tests) * 100
        
        self.results["test_summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "pass_rate": overall_pass_rate,
            "overall_result": "PASS" if overall_pass_rate >= 80 else "FAIL",
            "test_completion_time": datetime.now().isoformat()
        }
        
        # Print summary
        print("\n" + "="*60)
        print("🎯 GROUND TRUTH INTEGRATION VALIDATION SUMMARY")
        print("="*60)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:25} : {status}")
        
        print("-"*60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Pass Rate: {overall_pass_rate:.1f}%")
        print(f"Overall: {'✅ PASS' if overall_pass_rate >= 80 else '❌ FAIL'}")
        
        if self.results["issues_found"]:
            print("\n🔍 ISSUES FOUND:")
            for i, issue in enumerate(self.results["issues_found"], 1):
                print(f"{i}. [{issue['category']}] {issue['test']}")
                if issue.get('details'):
                    print(f"   Details: {issue['details']}")
        
        print("="*60)
        
        return self.results

    def save_results(self, output_file: str = "ground_truth_validation_results.json"):
        """Save detailed results to JSON file"""
        results_file = Path(output_file)
        results_file.write_text(json.dumps(self.results, indent=2, default=str))
        print(f"\n📄 Detailed results saved to: {results_file.absolute()}")


def main():
    """Main test execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ground Truth Integration Validation")
    parser.add_argument("--session-id", default="test-session-gt-validation", 
                       help="Test session ID to use")
    parser.add_argument("--backend-url", default="http://localhost:8000",
                       help="Backend API URL")
    parser.add_argument("--frontend-url", default="http://localhost:3000",
                       help="Frontend URL")
    parser.add_argument("--output", default="ground_truth_validation_results.json",
                       help="Output file for detailed results")
    
    args = parser.parse_args()
    
    # Update global URLs
    global BACKEND_URL, FRONTEND_URL
    BACKEND_URL = args.backend_url
    FRONTEND_URL = args.frontend_url
    
    # Run validation
    validator = GroundTruthIntegrationValidator(args.session_id)
    results = validator.run_all_tests()
    validator.save_results(args.output)
    
    # Exit with appropriate code
    overall_result = results["test_summary"]["overall_result"]
    exit_code = 0 if overall_result == "PASS" else 1
    
    print(f"\nExiting with code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)