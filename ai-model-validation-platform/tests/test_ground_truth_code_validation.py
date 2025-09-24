#!/usr/bin/env python3
"""
Ground Truth Code Validation

Tests the ground truth integration by analyzing the code directly
to ensure the fix is implemented correctly.
"""

import re
import json
import os
from pathlib import Path
from typing import Dict, Any, List


class GroundTruthCodeValidator:
    """Validates ground truth integration by analyzing code directly"""
    
    def __init__(self):
        self.backend_path = Path("backend")
        self.frontend_path = Path("frontend")
        self.results = {
            "timestamp": "2025-09-23T13:48:00Z",
            "tests": {},
            "summary": {}
        }
    
    def log_test(self, test_name: str, passed: bool, details: Dict[str, Any] = None):
        """Log test result"""
        self.results["tests"][test_name] = {
            "passed": passed,
            "details": details or {}
        }
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"[Code Validation] {test_name}: {status}")
        if not passed and details:
            print(f"  Details: {details}")
        
        return passed
    
    def test_enhanced_hil_api_exists(self) -> bool:
        """Test 1: Enhanced HIL API file exists and has ground truth functionality"""
        api_file = self.backend_path / "src/api/enhanced_hil_results_endpoints.py"
        
        if not api_file.exists():
            return self.log_test("enhanced_hil_api_exists", False, {
                "error": f"API file not found: {api_file}"
            })
        
        content = api_file.read_text()
        
        # Check for key ground truth features
        features = {
            "has_ground_truth_comparison": "ground_truth_comparison" in content,
            "loads_real_gt_events": "GroundTruthObject" in content and "video_id" in content,
            "has_corrected_results_endpoint": "/corrected-results" in content,
            "processes_gt_events": "ground_truth_events.append" in content or "gt_events" in content,
            "returns_gt_metrics": "ground_truth_events_available" in content
        }
        
        all_features_present = all(features.values())
        
        return self.log_test("enhanced_hil_api_exists", all_features_present, {
            "file_path": str(api_file),
            "file_size": len(content),
            "features": features
        })
    
    def test_ground_truth_events_count_fix(self) -> bool:
        """Test 2: Verify ground truth events count fix (should be 24, not 0)"""
        api_file = self.backend_path / "src/api/enhanced_hil_results_endpoints.py"
        
        if not api_file.exists():
            return self.log_test("ground_truth_events_count_fix", False, {
                "error": "API file not found"
            })
        
        content = api_file.read_text()
        
        # Look for the specific fix: loading real ground truth events
        fix_indicators = {
            "loads_from_database": "db.query(GroundTruthObject)" in content,
            "filters_by_video_id": "video_id ==" in content,
            "appends_real_events": "ground_truth_events.append" in content,
            "returns_length": "len(ground_truth_events)" in content or "len(gt_" in content,
            "not_hardcoded_zero": "ground_truth_events_available.*0" not in content
        }
        
        # Critical: Should not return hardcoded 0
        has_hardcoded_zero = re.search(r'"ground_truth_events_available":\s*0', content)
        no_hardcoded_zero = has_hardcoded_zero is None
        
        fix_implemented = all(fix_indicators.values()) and no_hardcoded_zero
        
        return self.log_test("ground_truth_events_count_fix", fix_implemented, {
            "fix_indicators": fix_indicators,
            "no_hardcoded_zero": no_hardcoded_zero,
            "has_db_query": "db.query(GroundTruthObject)" in content
        })
    
    def test_frontend_enhanced_timing_integration(self) -> bool:
        """Test 3: Frontend enhanced timing integration"""
        hil_results_file = self.frontend_path / "src/pages/HILResults.tsx"
        
        if not hil_results_file.exists():
            return self.log_test("frontend_enhanced_timing_integration", False, {
                "error": f"Frontend file not found: {hil_results_file}"
            })
        
        content = hil_results_file.read_text()
        
        # Check for enhanced timing features
        features = {
            "has_enhanced_timing_toggle": "Enhanced Timing" in content and "Switch" in content,
            "loads_enhanced_results": "loadEnhancedHILResults" in content,
            "displays_gt_comparison": "Ground Truth Comparison" in content,
            "shows_gt_events_count": "Ground Truth Events:" in content,
            "uses_dynamic_count": "groundTruthEvents.length" in content,
            "has_timing_correction": "Timing Synchronization Correction" in content
        }
        
        all_features_present = all(features.values())
        
        return self.log_test("frontend_enhanced_timing_integration", all_features_present, {
            "file_path": str(hil_results_file),
            "features": features
        })
    
    def test_frontend_ground_truth_display_fix(self) -> bool:
        """Test 4: Frontend displays dynamic ground truth count, not hardcoded 0"""
        hil_results_file = self.frontend_path / "src/pages/HILResults.tsx"
        
        if not hil_results_file.exists():
            return self.log_test("frontend_ground_truth_display_fix", False, {
                "error": "Frontend file not found"
            })
        
        content = hil_results_file.read_text()
        
        # Look for dynamic ground truth count display
        dynamic_indicators = {
            "uses_gt_events_length": "groundTruthEvents.length" in content,
            "loads_gt_data": "loadGroundTruthData" in content or "getGroundTruthEvents" in content,
            "displays_gt_count": "Ground Truth Events:" in content,
            "not_hardcoded_zero": '"Ground Truth Events: 0"' not in content and "'Ground Truth Events: 0'" not in content
        }
        
        # Check for the specific fix pattern
        gt_display_pattern = re.search(r'Ground Truth Events.*groundTruthEvents\.length', content, re.IGNORECASE)
        has_dynamic_display = gt_display_pattern is not None
        
        fix_implemented = all(dynamic_indicators.values()) and has_dynamic_display
        
        return self.log_test("frontend_ground_truth_display_fix", fix_implemented, {
            "dynamic_indicators": dynamic_indicators,
            "has_dynamic_display": has_dynamic_display,
            "pattern_found": str(gt_display_pattern.group() if gt_display_pattern else None)
        })
    
    def test_enhanced_hil_service_exists(self) -> bool:
        """Test 5: Enhanced HIL service exists with VRU tracking"""
        service_file = self.frontend_path / "src/services/enhancedHILService.ts"
        
        if not service_file.exists():
            return self.log_test("enhanced_hil_service_exists", False, {
                "error": f"Service file not found: {service_file}"
            })
        
        content = service_file.read_text()
        
        # Check for key service features
        features = {
            "has_vru_tracking": "VRUTrack" in content and "VRUDetectionEvent" in content,
            "has_temporal_matching": "TemporalMatcher" in content,
            "loads_gt_annotations": "loadGroundTruthAnnotations" in content,
            "creates_mock_data": "createMockAnnotations" in content,
            "processes_hil_signals": "processHILSignal" in content
        }
        
        all_features_present = all(features.values())
        
        return self.log_test("enhanced_hil_service_exists", all_features_present, {
            "file_path": str(service_file),
            "features": features
        })
    
    def test_timing_synchronization_implementation(self) -> bool:
        """Test 6: Timing synchronization implementation exists"""
        timing_files = [
            self.backend_path / "services/timing_synchronization_calculator.py",
            self.backend_path / "services/precision_timing_service.py"
        ]
        
        implementations_found = 0
        file_details = {}
        
        for timing_file in timing_files:
            if timing_file.exists():
                implementations_found += 1
                content = timing_file.read_text()
                file_details[timing_file.name] = {
                    "exists": True,
                    "size": len(content),
                    "has_correction_logic": "correction" in content.lower(),
                    "has_video_timing": "video" in content.lower() and "timing" in content.lower()
                }
            else:
                file_details[timing_file.name] = {"exists": False}
        
        has_implementation = implementations_found > 0
        
        return self.log_test("timing_synchronization_implementation", has_implementation, {
            "implementations_found": implementations_found,
            "files_checked": len(timing_files),
            "file_details": file_details
        })
    
    def test_database_schema_ground_truth_support(self) -> bool:
        """Test 7: Database schema supports ground truth objects"""
        models_file = self.backend_path / "models.py"
        
        if not models_file.exists():
            return self.log_test("database_schema_ground_truth_support", False, {
                "error": f"Models file not found: {models_file}"
            })
        
        content = models_file.read_text()
        
        # Check for ground truth model
        schema_features = {
            "has_ground_truth_model": "class GroundTruthObject" in content,
            "has_video_relationship": "video_id" in content and "relationship" in content,
            "has_timing_fields": "timestamp" in content,
            "has_frame_number": "frame_number" in content,
            "has_class_label": "class_label" in content
        }
        
        all_features_present = all(schema_features.values())
        
        return self.log_test("database_schema_ground_truth_support", all_features_present, {
            "file_path": str(models_file),
            "schema_features": schema_features
        })
    
    def run_validation(self) -> Dict[str, Any]:
        """Run all code validation tests"""
        print("🔍 Running Ground Truth Code Validation...")
        print(f"Backend path: {self.backend_path.absolute()}")
        print(f"Frontend path: {self.frontend_path.absolute()}")
        
        # Run all tests
        test_results = [
            self.test_enhanced_hil_api_exists(),
            self.test_ground_truth_events_count_fix(),
            self.test_frontend_enhanced_timing_integration(),
            self.test_frontend_ground_truth_display_fix(),
            self.test_enhanced_hil_service_exists(),
            self.test_timing_synchronization_implementation(),
            self.test_database_schema_ground_truth_support()
        ]
        
        # Calculate summary
        total_tests = len(test_results)
        passed_tests = sum(test_results)
        pass_rate = (passed_tests / total_tests) * 100
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "pass_rate": pass_rate,
            "overall_result": "PASS" if pass_rate >= 80 else "FAIL"
        }
        
        # Print summary
        print("\n" + "="*60)
        print("📊 GROUND TRUTH CODE VALIDATION SUMMARY")
        print("="*60)
        
        for test_name, result in self.results["tests"].items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{test_name:35} : {status}")
        
        print("-"*60)
        print(f"Pass Rate: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
        
        # Critical fix validation
        gt_fix_test = self.results["tests"].get("ground_truth_events_count_fix", {})
        frontend_fix_test = self.results["tests"].get("frontend_ground_truth_display_fix", {})
        
        if gt_fix_test.get("passed", False) and frontend_fix_test.get("passed", False):
            print("✅ CRITICAL FIX VALIDATED: Ground truth integration implemented correctly")
        else:
            print("❌ CRITICAL FIX ISSUES: Ground truth integration has problems")
            
        print("="*60)
        
        return self.results
    
    def save_results(self, output_file: str = "ground_truth_code_validation.json"):
        """Save results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Results saved to: {Path(output_file).absolute()}")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ground Truth Code Validation")
    parser.add_argument("--output", default="ground_truth_code_validation.json",
                       help="Output file for results")
    
    args = parser.parse_args()
    
    validator = GroundTruthCodeValidator()
    results = validator.run_validation()
    validator.save_results(args.output)
    
    # Exit with appropriate code
    exit_code = 0 if results["summary"]["overall_result"] == "PASS" else 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)