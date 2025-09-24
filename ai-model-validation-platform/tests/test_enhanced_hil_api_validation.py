#!/usr/bin/env python3
"""
Enhanced HIL API Validation Tests

Specifically tests that the enhanced HIL API endpoint returns ground truth data
and validates the critical fix: Ground Truth Events should show 24, not 0.
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any, List


class EnhancedHILAPIValidator:
    """Validates Enhanced HIL API for ground truth integration"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_session_id = "b8a345a5-582a-4a55-a409-c7a8a06408f9"  # Known session with data
        
    def test_enhanced_hil_endpoint_exists(self) -> Dict[str, Any]:
        """Test that the enhanced HIL endpoint exists and responds"""
        try:
            response = requests.get(
                f"{self.base_url}/api/enhanced-hil/test-sessions/{self.test_session_id}/corrected-results",
                timeout=30
            )
            
            return {
                "passed": response.status_code == 200,
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "content_length": len(response.content) if response.content else 0
            }
        except Exception as e:
            return {
                "passed": False,
                "error": str(e)
            }
    
    def test_ground_truth_comparison_section(self) -> Dict[str, Any]:
        """Test that response includes ground_truth_comparison section"""
        try:
            response = requests.get(
                f"{self.base_url}/api/enhanced-hil/test-sessions/{self.test_session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                return {"passed": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            has_gt_comparison = "ground_truth_comparison" in data
            
            result = {
                "passed": has_gt_comparison,
                "has_ground_truth_comparison": has_gt_comparison,
                "response_keys": list(data.keys())
            }
            
            if has_gt_comparison:
                gt_comparison = data["ground_truth_comparison"]
                result["ground_truth_comparison_keys"] = list(gt_comparison.keys())
                result["ground_truth_events_available"] = gt_comparison.get("ground_truth_events_available", 0)
            
            return result
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def test_ground_truth_events_count(self) -> Dict[str, Any]:
        """Test that ground truth events count is 24, not 0 (critical fix validation)"""
        try:
            response = requests.get(
                f"{self.base_url}/api/enhanced-hil/test-sessions/{self.test_session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                return {"passed": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            
            if "ground_truth_comparison" not in data:
                return {"passed": False, "error": "Missing ground_truth_comparison section"}
            
            gt_comparison = data["ground_truth_comparison"]
            gt_events = gt_comparison.get("ground_truth_events_available", 0)
            
            # Critical validation: Should be 24, not 0
            expected_gt_events = 24
            is_correct = gt_events == expected_gt_events
            
            return {
                "passed": is_correct,
                "expected_gt_events": expected_gt_events,
                "actual_gt_events": gt_events,
                "fix_validated": is_correct,
                "total_detections": gt_comparison.get("total_detections", 0),
                "methodology": gt_comparison.get("matching_methodology", ""),
                "was_zero": gt_events == 0  # Flag if we still have the bug
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def test_timing_synchronization_results(self) -> Dict[str, Any]:
        """Test timing synchronization results show events with matches"""
        try:
            response = requests.get(
                f"{self.base_url}/api/enhanced-hil/test-sessions/{self.test_session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                return {"passed": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            gt_comparison = data.get("ground_truth_comparison", {})
            timing_sync = gt_comparison.get("timing_synchronization_results", {})
            
            events_with_matches = timing_sync.get("events_with_matches", 0)
            avg_confidence = timing_sync.get("average_confidence_score", 0)
            
            # Should have 39/39 events with matches and reasonable confidence
            expected_matches = 39
            has_correct_matches = events_with_matches == expected_matches
            has_confidence = avg_confidence > 0.5
            
            return {
                "passed": has_correct_matches and has_confidence,
                "expected_matches": expected_matches,
                "actual_matches": events_with_matches,
                "average_confidence_score": avg_confidence,
                "timing_quality_distribution": timing_sync.get("timing_quality_distribution", {}),
                "matches_correct": has_correct_matches,
                "confidence_adequate": has_confidence
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def test_detection_events_timing_data(self) -> Dict[str, Any]:
        """Test that detection events contain timing synchronization data"""
        try:
            response = requests.get(
                f"{self.base_url}/api/enhanced-hil/test-sessions/{self.test_session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                return {"passed": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            detection_events = data.get("detection_events", [])
            
            if not detection_events:
                return {"passed": False, "error": "No detection events found"}
            
            # Check timing synchronization data in events
            events_with_timing = 0
            events_with_corrected_latency = 0
            events_with_confidence = 0
            
            for event in detection_events:
                if "timing_synchronization" in event:
                    events_with_timing += 1
                    timing_sync = event["timing_synchronization"]
                    if "confidence_score" in timing_sync:
                        events_with_confidence += 1
                
                if "corrected_latency" in event and "real_latency_ms" in event["corrected_latency"]:
                    events_with_corrected_latency += 1
            
            total_events = len(detection_events)
            timing_coverage = events_with_timing / total_events
            latency_coverage = events_with_corrected_latency / total_events
            confidence_coverage = events_with_confidence / total_events
            
            # Should have high coverage of timing data
            good_coverage = timing_coverage >= 0.8 and latency_coverage >= 0.8
            
            return {
                "passed": good_coverage,
                "total_detection_events": total_events,
                "events_with_timing_sync": events_with_timing,
                "events_with_corrected_latency": events_with_corrected_latency,
                "events_with_confidence": events_with_confidence,
                "timing_coverage": timing_coverage,
                "latency_coverage": latency_coverage,
                "confidence_coverage": confidence_coverage,
                "sample_event": detection_events[0] if detection_events else None
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def test_video_timing_data(self) -> Dict[str, Any]:
        """Test video timing metadata is included"""
        try:
            response = requests.get(
                f"{self.base_url}/api/enhanced-hil/test-sessions/{self.test_session_id}/corrected-results",
                timeout=30
            )
            
            if response.status_code != 200:
                return {"passed": False, "error": f"HTTP {response.status_code}"}
            
            data = response.json()
            video_timing = data.get("video_timing", {})
            
            has_startup_delay = "startup_delay_ms" in video_timing
            has_timing_status = "timing_sync_status" in video_timing
            has_fps = "fps" in video_timing
            
            startup_delay = video_timing.get("startup_delay_ms", 0)
            timing_status = video_timing.get("timing_sync_status", "unknown")
            
            return {
                "passed": has_startup_delay and has_timing_status,
                "has_startup_delay": has_startup_delay,
                "has_timing_status": has_timing_status,
                "has_fps": has_fps,
                "startup_delay_ms": startup_delay,
                "timing_sync_status": timing_status,
                "video_timing_data": video_timing
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def run_validation(self) -> Dict[str, Any]:
        """Run all API validation tests"""
        print("🔍 Running Enhanced HIL API Validation...")
        print(f"Testing endpoint: {self.base_url}/api/enhanced-hil/...")
        print(f"Session ID: {self.test_session_id}")
        
        tests = {
            "endpoint_exists": self.test_enhanced_hil_endpoint_exists(),
            "ground_truth_comparison": self.test_ground_truth_comparison_section(),
            "gt_events_count": self.test_ground_truth_events_count(),
            "timing_synchronization": self.test_timing_synchronization_results(),
            "detection_events_timing": self.test_detection_events_timing_data(),
            "video_timing": self.test_video_timing_data()
        }
        
        # Summary
        passed_tests = sum(1 for result in tests.values() if result.get("passed", False))
        total_tests = len(tests)
        pass_rate = (passed_tests / total_tests) * 100
        
        print("\n" + "="*50)
        print("📊 ENHANCED HIL API VALIDATION RESULTS")
        print("="*50)
        
        for test_name, result in tests.items():
            status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
            print(f"{test_name:25} : {status}")
            
            if not result.get("passed", False) and "error" in result:
                print(f"  Error: {result['error']}")
        
        print("-"*50)
        print(f"Pass Rate: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        
        # Specific validation for the critical fix
        gt_test = tests.get("gt_events_count", {})
        if gt_test.get("passed", False):
            print(f"✅ CRITICAL FIX VALIDATED: Ground Truth Events = {gt_test.get('actual_gt_events', 0)} (not 0)")
        else:
            print(f"❌ CRITICAL FIX FAILED: Ground Truth Events = {gt_test.get('actual_gt_events', 0)}")
            if gt_test.get("was_zero", False):
                print("   🚨 BUG STILL PRESENT: Still showing 0 events!")
        
        print("="*50)
        
        return {
            "test_results": tests,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "pass_rate": pass_rate,
                "overall_result": "PASS" if pass_rate >= 80 else "FAIL"
            },
            "critical_fix_validated": gt_test.get("passed", False),
            "timestamp": datetime.now().isoformat()
        }


def main():
    """Main test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced HIL API Validation")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend API base URL")
    parser.add_argument("--output", default="enhanced_hil_api_validation.json", help="Output file")
    
    args = parser.parse_args()
    
    validator = EnhancedHILAPIValidator(args.base_url)
    results = validator.run_validation()
    
    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Results saved to: {args.output}")
    
    # Exit code
    exit_code = 0 if results["summary"]["overall_result"] == "PASS" else 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)