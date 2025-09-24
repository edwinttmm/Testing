#!/usr/bin/env python3
"""
Validation script for latency decomposition implementation.

This script validates that the latency decomposition service correctly
separates camera latency from system overhead and provides accurate results.
"""

import sys
import os
import asyncio
import time
import json
from typing import Dict, Any, List

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.latency_decomposition_service import get_latency_decomposition_service
from services.timing_synchronization_calculator import get_timing_synchronization_calculator

class LatencyDecompositionValidator:
    """Validator for latency decomposition functionality"""
    
    def __init__(self):
        self.decomposition_service = get_latency_decomposition_service()
        self.timing_calc = get_timing_synchronization_calculator()
        self.validation_results = []
    
    def validate_baseline_calibration(self) -> Dict[str, Any]:
        """Validate system baseline calibration"""
        print("🔍 Validating system baseline calibration...")
        
        # Calibrate baseline
        start_time = time.time()
        baseline_profile = self.decomposition_service.calibrate_system_baseline()
        calibration_time = time.time() - start_time
        
        # Validation checks
        checks = {
            "calibration_completed": baseline_profile is not None,
            "reasonable_calibration_time": calibration_time < 30,  # Should complete in under 30 seconds
            "baseline_within_bounds": 1 <= baseline_profile.total_baseline_ns / 1e6 <= 100,  # 1-100ms
            "positive_components": all([
                baseline_profile.os_overhead_ns > 0,
                baseline_profile.hardware_overhead_ns > 0,
                baseline_profile.timing_precision_ns > 0
            ]),
            "reasonable_confidence": baseline_profile.measurement_confidence > 0.3,
            "system_info_available": len(baseline_profile.system_info) > 0
        }
        
        result = {
            "test_name": "Baseline Calibration",
            "passed": all(checks.values()),
            "details": checks,
            "baseline_ms": baseline_profile.total_baseline_ns / 1e6,
            "confidence": baseline_profile.measurement_confidence,
            "calibration_time_s": calibration_time
        }
        
        self.validation_results.append(result)
        return result
    
    def validate_decomposition_accuracy(self) -> Dict[str, Any]:
        """Validate latency decomposition accuracy"""
        print("🔍 Validating latency decomposition accuracy...")
        
        # Test scenarios with known expected outcomes
        test_cases = [
            {
                "name": "Low overhead scenario",
                "total_latency": 30.0,
                "metadata": {'detection_algorithm': 'SSD', 'image_resolution': '320x240', 'communication_method': 'local'},
                "expected_camera_ratio": 0.7,  # Expect 70% camera, 30% overhead
                "tolerance": 0.2
            },
            {
                "name": "High overhead scenario", 
                "total_latency": 150.0,
                "metadata": {'detection_algorithm': 'YOLO', 'image_resolution': '4K', 'communication_method': 'tcp', 'preprocessing_enabled': True},
                "expected_camera_ratio": 0.5,  # Expect 50% camera, 50% overhead
                "tolerance": 0.3
            }
        ]
        
        decomposition_checks = []
        
        for i, case in enumerate(test_cases):
            decomposition = self.decomposition_service.decompose_latency(
                session_id="validation_test",
                detection_id=f"test_{i}",
                total_latency_ms=case["total_latency"],
                detection_metadata=case["metadata"]
            )
            
            actual_camera_ratio = decomposition.camera_latency_ms / decomposition.total_latency_ms
            expected_ratio = case["expected_camera_ratio"]
            tolerance = case["tolerance"]
            
            case_checks = {
                "decomposition_completed": decomposition is not None,
                "camera_ratio_reasonable": abs(actual_camera_ratio - expected_ratio) <= tolerance,
                "positive_latencies": all([
                    decomposition.camera_latency_ms >= 0,
                    decomposition.system_baseline_ms >= 0,
                    decomposition.processing_overhead_ms >= 0
                ]),
                "components_sum_to_total": abs(
                    (decomposition.camera_latency_ms + decomposition.system_baseline_ms + 
                     decomposition.processing_overhead_ms + decomposition.network_overhead_ms + 
                     decomposition.sync_overhead_ms + decomposition.unknown_overhead_ms) - 
                    decomposition.total_latency_ms
                ) < 0.1,  # Within 0.1ms
                "reasonable_confidence": decomposition.decomposition_confidence > 0.3
            }
            
            decomposition_checks.append({
                "case": case["name"],
                "checks": case_checks,
                "actual_camera_ratio": actual_camera_ratio,
                "expected_camera_ratio": expected_ratio,
                "decomposition": {
                    "camera_ms": decomposition.camera_latency_ms,
                    "system_ms": decomposition.system_baseline_ms,
                    "processing_ms": decomposition.processing_overhead_ms,
                    "confidence": decomposition.decomposition_confidence
                }
            })
        
        all_passed = all(
            all(case["checks"].values()) for case in decomposition_checks
        )
        
        result = {
            "test_name": "Decomposition Accuracy",
            "passed": all_passed,
            "test_cases": decomposition_checks,
            "total_cases": len(test_cases),
            "passed_cases": sum(1 for case in decomposition_checks if all(case["checks"].values()))
        }
        
        self.validation_results.append(result)
        return result
    
    def validate_timing_integration(self) -> Dict[str, Any]:
        """Validate integration with timing synchronization calculator"""
        print("🔍 Validating timing synchronization integration...")
        
        from services.timing_synchronization_calculator import VideoTimingMetadata
        
        # Create test video metadata
        video_metadata = VideoTimingMetadata(
            startup_delay_ms=1500.0,
            fps=30.0,
            duration=10.0,
            timing_sync_status="synced",
            timing_accuracy_ns=1000
        )
        
        # Test timing calculation with decomposition
        try:
            result = self.timing_calc.calculate_corrected_latency(
                session_id="integration_validation",
                detection_id="integration_test_001",
                detection_system_time=1234567890.100,
                ground_truth_frame=90,  # 3 seconds into video
                ground_truth_video_time=3.0,
                video_timing_metadata=video_metadata,
                labjack_start_time=1234567880.0
            )
            
            integration_checks = {
                "calculation_completed": result is not None,
                "decomposition_included": hasattr(result, 'camera_only_latency_ms'),
                "decomposition_values_present": all([
                    result.camera_only_latency_ms >= 0,
                    result.system_overhead_ms >= 0,
                    result.processing_overhead_ms >= 0,
                    result.decomposition_confidence >= 0
                ]),
                "real_latency_calculated": result.real_latency_ms > 0,
                "camera_less_than_total": result.camera_only_latency_ms <= result.real_latency_ms,
                "timing_quality_assessed": result.timing_quality in ["excellent", "good", "fair", "poor"]
            }
            
            integration_result = {
                "test_name": "Timing Integration",
                "passed": all(integration_checks.values()),
                "details": integration_checks,
                "result_summary": {
                    "real_latency_ms": result.real_latency_ms,
                    "camera_only_ms": result.camera_only_latency_ms,
                    "system_overhead_ms": result.system_overhead_ms,
                    "processing_overhead_ms": result.processing_overhead_ms,
                    "decomposition_confidence": result.decomposition_confidence,
                    "timing_quality": result.timing_quality
                }
            }
            
        except Exception as e:
            integration_result = {
                "test_name": "Timing Integration",
                "passed": False,
                "error": str(e),
                "details": {"integration_failed": True}
            }
        
        self.validation_results.append(integration_result)
        return integration_result
    
    def validate_api_endpoints(self) -> Dict[str, Any]:
        """Validate API endpoint structure"""
        print("🔍 Validating API endpoint structure...")
        
        try:
            # Import the router to check it loads correctly
            from routers.latency_analysis import router
            
            # Check if endpoints are defined
            endpoint_checks = {
                "router_imported": router is not None,
                "router_has_routes": len(router.routes) > 0,
                "expected_endpoints_count": len(router.routes) >= 6  # Expected number of endpoints
            }
            
            # Get endpoint paths
            endpoint_paths = [route.path for route in router.routes if hasattr(route, 'path')]
            expected_paths = [
                "/decompose/{session_id}",
                "/decomposition/{session_id}", 
                "/baseline/calibrate",
                "/baseline/status",
                "/analysis/{session_id}/camera-only",
                "/comparison/{session_id}"
            ]
            
            endpoint_checks["all_expected_paths_present"] = all(
                any(expected in path for path in endpoint_paths) 
                for expected in expected_paths
            )
            
            api_result = {
                "test_name": "API Endpoints",
                "passed": all(endpoint_checks.values()),
                "details": endpoint_checks,
                "endpoint_count": len(router.routes),
                "endpoint_paths": endpoint_paths
            }
            
        except Exception as e:
            api_result = {
                "test_name": "API Endpoints",
                "passed": False,
                "error": str(e),
                "details": {"import_failed": True}
            }
        
        self.validation_results.append(api_result)
        return api_result
    
    def validate_service_configuration(self) -> Dict[str, Any]:
        """Validate service configuration and settings"""
        print("🔍 Validating service configuration...")
        
        service_status = self.decomposition_service.get_service_status()
        
        config_checks = {
            "service_initialized": service_status.get("service") == "LatencyDecompositionService",
            "config_loaded": "config" in service_status,
            "baseline_measurement_samples": service_status.get("config", {}).get("baseline_measurement_samples", 0) >= 100,
            "camera_latency_bounds_set": "camera_latency_bounds_ms" in service_status.get("config", {}),
            "system_baseline_max_set": "system_baseline_max_ms" in service_status.get("config", {}),
            "confidence_threshold_set": "baseline_confidence_threshold" in service_status.get("config", {})
        }
        
        config_result = {
            "test_name": "Service Configuration",
            "passed": all(config_checks.values()),
            "details": config_checks,
            "service_status": service_status
        }
        
        self.validation_results.append(config_result)
        return config_result
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        total_tests = len(self.validation_results)
        passed_tests = sum(1 for result in self.validation_results if result["passed"])
        
        report = {
            "validation_summary": {
                "timestamp": time.time(),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "overall_status": "PASSED" if passed_tests == total_tests else "FAILED"
            },
            "test_results": self.validation_results,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        for result in self.validation_results:
            if not result["passed"]:
                test_name = result["test_name"]
                
                if test_name == "Baseline Calibration":
                    recommendations.append("Check system performance and timing precision")
                elif test_name == "Decomposition Accuracy":
                    recommendations.append("Review latency estimation algorithms and metadata handling")
                elif test_name == "Timing Integration":
                    recommendations.append("Verify timing synchronization calculator integration")
                elif test_name == "API Endpoints":
                    recommendations.append("Check router imports and endpoint definitions")
                elif test_name == "Service Configuration":
                    recommendations.append("Verify service configuration and initialization")
        
        if not recommendations:
            recommendations.append("All validation tests passed - system is ready for production use")
        
        return recommendations

async def run_validation():
    """Run complete validation suite"""
    print("🚀 Starting Latency Decomposition Validation Suite")
    print("=" * 80)
    
    validator = LatencyDecompositionValidator()
    
    # Run all validation tests
    tests = [
        validator.validate_service_configuration,
        validator.validate_baseline_calibration,
        validator.validate_decomposition_accuracy,
        validator.validate_timing_integration,
        validator.validate_api_endpoints
    ]
    
    for test in tests:
        try:
            result = test()
            status = "✅ PASSED" if result["passed"] else "❌ FAILED"
            print(f"{status} - {result['test_name']}")
        except Exception as e:
            print(f"❌ FAILED - {test.__name__}: {e}")
    
    # Generate final report
    report = validator.generate_validation_report()
    
    print("\n" + "=" * 80)
    print("🏁 VALIDATION SUMMARY")
    print("=" * 80)
    
    summary = report["validation_summary"]
    print(f"Overall Status: {summary['overall_status']}")
    print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']} ({summary['success_rate']:.1f}%)")
    
    if summary["failed_tests"] > 0:
        print(f"\n🔧 Recommendations:")
        for rec in report["recommendations"]:
            print(f"   • {rec}")
    
    # Save detailed report
    report_file = "latency_decomposition_validation_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    return summary["overall_status"] == "PASSED"

if __name__ == "__main__":
    success = asyncio.run(run_validation())
    sys.exit(0 if success else 1)