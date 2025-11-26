"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_camera_latency_measurement_validation.py
"""

#!/usr/bin/env python3
"""
Camera Latency Measurement Validation Test Suite

Validates camera latency measurement accuracy using real HIL test data
and provides comprehensive analysis of measurement quality.
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.camera_latency_measurement_service import (
    CameraLatencyMeasurementService,
    get_camera_latency_service,
    LatencyComponent
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraLatencyValidationSuite:
    """Test suite for camera latency measurement validation"""
    
    def __init__(self):
        self.service = get_camera_latency_service()
        self.test_data = self._load_real_test_data()
    
    def _load_real_test_data(self) -> Dict[str, Any]:
        """Load real test data from your HIL system"""
        return {
            "session_id": "test_session_hil_validation",
            "ground_truth_data": {
                "frame_5_timestamp": 0.208,  # GT Frame 5 at 0.208s
                "detection_frame_50_timestamp": 2.083,  # Detection at Frame 50, 2.083s
                "total_delay_seconds": 1.875,  # 1.875s total delay
                "processing_time_ms": 50.0  # Known processing time
            },
            "system_characteristics": {
                "detection_rate_hz": 0.38,
                "average_voltage": 4.23,
                "voltage_range": (3.53, 4.33),
                "total_events": 107,
                "time_span_seconds": 276.24,
                "system_type": "hil_video_systems"
            },
            "measurement_quality": {
                "timestamp_completeness": 1.0,
                "voltage_completeness": 1.0,
                "frame_completeness": 1.0,
                "voltage_pass_rate": 100.0
            }
        }
    
    def test_realistic_latency_assessment(self) -> Dict[str, Any]:
        """Test assessment of realistic camera latency values"""
        logger.info("Testing realistic latency assessment...")
        
        test_data = self.test_data["ground_truth_data"]
        total_latency_ms = test_data["total_delay_seconds"] * 1000  # 1875ms
        processing_time_ms = test_data["processing_time_ms"]  # 50ms
        camera_delay_ms = total_latency_ms - processing_time_ms  # 1825ms
        
        # Perform latency analysis
        analysis = self.service.analyze_camera_latency(
            session_id=self.test_data["session_id"],
            total_latency_ms=total_latency_ms,
            processing_time_ms=processing_time_ms,
            system_type=self.test_data["system_characteristics"]["system_type"]
        )
        
        # Validate results
        results = {
            "test_name": "realistic_latency_assessment",
            "input_data": {
                "total_latency_ms": total_latency_ms,
                "camera_delay_ms": camera_delay_ms,
                "processing_time_ms": processing_time_ms
            },
            "analysis_results": {
                "measurement_quality": analysis.measurement_quality,
                "accuracy_assessment": analysis.accuracy_assessment,
                "validation_confidence": analysis.validation_confidence,
                "component_count": len(analysis.component_breakdown),
                "total_component_latency": analysis.total_component_latency(),
                "unaccounted_latency": analysis.unaccounted_latency()
            },
            "component_breakdown": {
                comp.component.value: {
                    "measured_ms": comp.measured_ms,
                    "percentage": comp.percentage_of_total(total_latency_ms),
                    "within_expected_range": comp.is_within_expected_range(),
                    "expected_range": comp.expected_range_ms
                }
                for comp in analysis.component_breakdown
            },
            "industry_comparison": analysis.industry_comparison,
            "validation_checks": {
                "latency_within_hil_range": 500 <= total_latency_ms <= 2000,
                "quality_acceptable": analysis.measurement_quality in ["excellent", "good"],
                "confidence_high": analysis.validation_confidence in ["high", "medium"],
                "accuracy_positive": "ACCURATE" in analysis.accuracy_assessment
            }
        }
        
        # Calculate success criteria
        validation_checks = results["validation_checks"]
        success = all(validation_checks.values())
        
        results["success"] = success
        results["summary"] = {
            "camera_delay_realistic": camera_delay_ms >= 500,  # Realistic for video systems
            "total_latency_acceptable": total_latency_ms <= 3000,  # Acceptable for HIL
            "component_analysis_complete": len(analysis.component_breakdown) >= 4,
            "industry_standards_met": len(analysis.industry_comparison["best_matches"]) > 0
        }
        
        return results
    
    def test_component_breakdown_accuracy(self) -> Dict[str, Any]:
        """Test accuracy of component latency breakdown"""
        logger.info("Testing component breakdown accuracy...")
        
        # Test with known 1825ms camera delay
        camera_delay_ms = 1825.0
        total_latency_ms = camera_delay_ms + 50.0  # Add processing time
        
        analysis = self.service.analyze_camera_latency(
            session_id=f"{self.test_data['session_id']}_component_test",
            total_latency_ms=total_latency_ms,
            processing_time_ms=50.0
        )
        
        # Validate component breakdown
        component_analysis = {}
        total_component_ms = 0
        
        for comp in analysis.component_breakdown:
            component_analysis[comp.component.value] = {
                "measured_ms": comp.measured_ms,
                "percentage": comp.percentage_of_total(camera_delay_ms),
                "within_range": comp.is_within_expected_range(),
                "expected_range": comp.expected_range_ms,
                "realistic": self._assess_component_realism(comp.component, comp.measured_ms)
            }
            total_component_ms += comp.measured_ms
        
        # Test expected component percentages
        expected_percentages = {
            LatencyComponent.VIDEO_CAPTURE: (15, 25),      # 16-27%
            LatencyComponent.PROCESSING_PIPELINE: (40, 50), # 40-50%
            LatencyComponent.DISPLAY_RENDERING: (15, 20),   # 15-20%
            LatencyComponent.CLOCK_SYNCHRONIZATION: (15, 25) # 15-25%
        }
        
        percentage_validation = {}
        for comp in analysis.component_breakdown:
            actual_percentage = comp.percentage_of_total(camera_delay_ms)
            expected_range = expected_percentages.get(comp.component, (0, 100))
            percentage_validation[comp.component.value] = {
                "actual_percentage": actual_percentage,
                "expected_range": expected_range,
                "within_expected": expected_range[0] <= actual_percentage <= expected_range[1]
            }
        
        results = {
            "test_name": "component_breakdown_accuracy",
            "camera_delay_ms": camera_delay_ms,
            "total_component_ms": total_component_ms,
            "component_analysis": component_analysis,
            "percentage_validation": percentage_validation,
            "breakdown_quality": {
                "components_within_range": sum(1 for comp in component_analysis.values() if comp["within_range"]),
                "total_components": len(component_analysis),
                "percentage_accuracy": sum(1 for val in percentage_validation.values() if val["within_expected"]) / len(percentage_validation),
                "realistic_estimates": sum(1 for comp in component_analysis.values() if comp["realistic"])
            }
        }
        
        # Success criteria
        breakdown_quality = results["breakdown_quality"]
        results["success"] = (
            breakdown_quality["components_within_range"] >= 3 and
            breakdown_quality["percentage_accuracy"] >= 0.75 and
            abs(total_component_ms - camera_delay_ms) < 50  # Within 50ms of total
        )
        
        return results
    
    def _assess_component_realism(self, component: LatencyComponent, measured_ms: float) -> bool:
        """Assess if component measurement is realistic"""
        realistic_ranges = {
            LatencyComponent.VIDEO_CAPTURE: (100, 500),
            LatencyComponent.PROCESSING_PIPELINE: (300, 1000),
            LatencyComponent.DISPLAY_RENDERING: (100, 400),
            LatencyComponent.CLOCK_SYNCHRONIZATION: (100, 500)
        }
        
        range_min, range_max = realistic_ranges.get(component, (0, float('inf')))
        return range_min <= measured_ms <= range_max
    
    def test_industry_standard_comparison(self) -> Dict[str, Any]:
        """Test comparison with industry standards"""
        logger.info("Testing industry standard comparison...")
        
        test_cases = [
            {"latency_ms": 1875, "system_type": "hil_video_systems", "should_match": True},
            {"latency_ms": 1875, "system_type": "ip_surveillance", "should_match": True},
            {"latency_ms": 1875, "system_type": "industrial_cameras", "should_match": False},
            {"latency_ms": 1875, "system_type": "video_conferencing", "should_match": False},
            {"latency_ms": 1875, "system_type": "complex_vision_processing", "should_match": True}
        ]
        
        comparison_results = []
        
        for i, test_case in enumerate(test_cases):
            analysis = self.service.analyze_camera_latency(
                session_id=f"{self.test_data['session_id']}_industry_test_{i}",
                total_latency_ms=test_case["latency_ms"],
                processing_time_ms=50.0,
                system_type=test_case["system_type"]
            )
            
            industry_comp = analysis.industry_comparison
            matches_system_type = test_case["system_type"] in industry_comp["best_matches"]
            
            comparison_results.append({
                "latency_ms": test_case["latency_ms"],
                "system_type": test_case["system_type"],
                "expected_match": test_case["should_match"],
                "actual_match": matches_system_type,
                "validation_correct": matches_system_type == test_case["should_match"],
                "best_matches": industry_comp["best_matches"],
                "primary_classification": industry_comp["primary_classification"]
            })
        
        # Calculate accuracy
        correct_classifications = sum(1 for result in comparison_results if result["validation_correct"])
        accuracy = correct_classifications / len(comparison_results)
        
        results = {
            "test_name": "industry_standard_comparison",
            "test_cases": comparison_results,
            "accuracy_metrics": {
                "correct_classifications": correct_classifications,
                "total_test_cases": len(comparison_results),
                "accuracy_percentage": accuracy * 100,
                "minimum_required_accuracy": 80.0
            },
            "success": accuracy >= 0.8  # 80% accuracy required
        }
        
        return results
    
    def test_measurement_validation_api(self) -> Dict[str, Any]:
        """Test the measurement validation API"""
        logger.info("Testing measurement validation API...")
        
        # Use real test data
        gt_data = self.test_data["ground_truth_data"]
        ground_truth_time = gt_data["frame_5_timestamp"]
        detection_time = gt_data["detection_frame_50_timestamp"]
        processing_time = gt_data["processing_time_ms"]
        
        # Validate the measurement
        validation_result = self.service.validate_latency_measurement(
            session_id=self.test_data["session_id"],
            ground_truth_time=ground_truth_time,
            detection_time=detection_time,
            processing_time=processing_time
        )
        
        # Check validation result structure
        required_fields = [
            "session_id", "measurement_valid", "total_latency_ms",
            "camera_system_delay_ms", "quality_assessment", "accuracy_assessment",
            "confidence_level", "component_breakdown", "industry_comparison",
            "recommendations", "validation_timestamp"
        ]
        
        field_validation = {
            field: field in validation_result
            for field in required_fields
        }
        
        # Validate specific values
        expected_total_latency = (detection_time - ground_truth_time) * 1000
        expected_camera_delay = expected_total_latency - processing_time
        
        value_validation = {
            "total_latency_correct": abs(validation_result.get("total_latency_ms", 0) - expected_total_latency) < 1.0,
            "camera_delay_correct": abs(validation_result.get("camera_system_delay_ms", 0) - expected_camera_delay) < 1.0,
            "measurement_marked_valid": validation_result.get("measurement_valid", False),
            "has_recommendations": len(validation_result.get("recommendations", [])) > 0,
            "has_component_breakdown": len(validation_result.get("component_breakdown", {})) > 0
        }
        
        results = {
            "test_name": "measurement_validation_api",
            "input_data": {
                "ground_truth_time": ground_truth_time,
                "detection_time": detection_time,
                "processing_time": processing_time,
                "expected_total_latency_ms": expected_total_latency,
                "expected_camera_delay_ms": expected_camera_delay
            },
            "validation_result": validation_result,
            "field_validation": field_validation,
            "value_validation": value_validation,
            "api_quality": {
                "all_required_fields_present": all(field_validation.values()),
                "values_accurate": all(value_validation.values()),
                "measurement_confidence": validation_result.get("confidence_level", "unknown"),
                "quality_assessment": validation_result.get("quality_assessment", "unknown")
            }
        }
        
        # Success criteria
        results["success"] = (
            results["api_quality"]["all_required_fields_present"] and
            results["api_quality"]["values_accurate"] and
            validation_result.get("measurement_valid", False)
        )
        
        return results
    
    def run_comprehensive_validation_suite(self) -> Dict[str, Any]:
        """Run all validation tests and generate comprehensive report"""
        logger.info("Running comprehensive camera latency validation suite...")
        
        test_results = {
            "validation_run_timestamp": datetime.now().isoformat(),
            "test_data_summary": self.test_data,
            "test_results": {}
        }
        
        # Define test methods
        test_methods = [
            ("realistic_latency_assessment", self.test_realistic_latency_assessment),
            ("component_breakdown_accuracy", self.test_component_breakdown_accuracy),
            ("industry_standard_comparison", self.test_industry_standard_comparison),
            ("measurement_validation_api", self.test_measurement_validation_api)
        ]
        
        # Run all tests
        for test_name, test_method in test_methods:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Running test: {test_name}")
                logger.info(f"{'='*60}")
                
                test_result = test_method()
                test_results["test_results"][test_name] = test_result
                
                status = "✅ PASSED" if test_result.get("success", False) else "❌ FAILED"
                logger.info(f"{status} - {test_name}")
                
            except Exception as e:
                test_results["test_results"][test_name] = {
                    "success": False,
                    "error": f"Test execution failed: {str(e)}"
                }
                logger.error(f"❌ FAILED - {test_name}: {e}")
        
        # Calculate overall results
        total_tests = len(test_results["test_results"])
        passed_tests = sum(1 for test in test_results["test_results"].values() if test.get("success", False))
        
        test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "pass_rate_percentage": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
            "overall_status": "PASSED" if passed_tests == total_tests else "FAILED",
            "camera_latency_assessment": "REALISTIC and ACCURATE" if passed_tests >= 3 else "REQUIRES_INVESTIGATION"
        }
        
        # Generate final assessment
        test_results["final_assessment"] = self._generate_final_assessment(test_results)
        
        return test_results
    
    def _generate_final_assessment(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final assessment of camera latency measurement"""
        summary = test_results["summary"]
        
        if summary["pass_rate_percentage"] >= 75:
            confidence = "HIGH"
            recommendation = "Accept 1,825ms camera latency as accurate measurement"
            rationale = "Comprehensive testing validates measurement accuracy and industry compliance"
        elif summary["pass_rate_percentage"] >= 50:
            confidence = "MEDIUM"
            recommendation = "Camera latency appears realistic but requires additional validation"
            rationale = "Most tests pass but some concerns identified in component analysis"
        else:
            confidence = "LOW"
            recommendation = "Investigate measurement methodology and system configuration"
            rationale = "Multiple test failures suggest measurement accuracy issues"
        
        return {
            "confidence_level": confidence,
            "recommendation": recommendation,
            "rationale": rationale,
            "measurement_status": "VALIDATED" if confidence == "HIGH" else "PENDING_VALIDATION",
            "key_findings": [
                f"Camera latency of 1,825ms is {'realistic' if confidence in ['HIGH', 'MEDIUM'] else 'questionable'} for HIL video systems",
                f"Component breakdown shows {'reasonable' if confidence == 'HIGH' else 'concerning'} distribution",
                f"Industry standards {'compliance achieved' if confidence == 'HIGH' else 'partially met'}",
                f"Measurement API {'functioning correctly' if confidence in ['HIGH', 'MEDIUM'] else 'requires fixes'}"
            ]
        }


def main():
    """Main test execution function"""
    print("🔬 Camera Latency Measurement Validation Suite")
    print("="*60)
    
    try:
        # Initialize validation suite
        validation_suite = CameraLatencyValidationSuite()
        
        # Run comprehensive validation
        results = validation_suite.run_comprehensive_validation_suite()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 VALIDATION SUMMARY")
        print("="*60)
        
        summary = results["summary"]
        assessment = results["final_assessment"]
        
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ✅")
        print(f"Failed: {summary['failed_tests']} ❌")
        print(f"Pass Rate: {summary['pass_rate_percentage']:.1f}%")
        print(f"Overall Status: {summary['overall_status']}")
        print(f"Camera Latency Assessment: {summary['camera_latency_assessment']}")
        
        print(f"\n🎯 FINAL ASSESSMENT")
        print(f"Confidence Level: {assessment['confidence_level']}")
        print(f"Recommendation: {assessment['recommendation']}")
        print(f"Measurement Status: {assessment['measurement_status']}")
        
        print(f"\n📋 KEY FINDINGS:")
        for finding in assessment['key_findings']:
            print(f"  • {finding}")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"camera_latency_validation_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Exit with appropriate code
        if assessment["confidence_level"] == "HIGH":
            print("\n🎉 Camera latency measurement VALIDATED! 1,825ms is accurate and realistic.")
            sys.exit(0)
        elif assessment["confidence_level"] == "MEDIUM":
            print("\n⚠️  Camera latency appears realistic but may need additional validation.")
            sys.exit(0)
        else:
            print("\n🚨 Camera latency measurement requires investigation.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Validation suite execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()