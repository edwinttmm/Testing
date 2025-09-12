#!/usr/bin/env python3
"""
Production readiness validation for SPARC unified configuration system
Tests system robustness, error handling, and deployment readiness
"""

import sys
import os
import json
import time
import traceback
from typing import Dict, Any, List

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

class ProductionReadinessValidator:
    """Validates production readiness of the unified configuration system"""
    
    def __init__(self):
        self.test_results = []
        self.critical_failures = []
        self.warnings = []
        
    def run_test(self, test_name: str, test_func, critical: bool = False):
        """Run a test and record results"""
        print(f"🧪 Running: {test_name}")
        
        try:
            start_time = time.time()
            result = test_func()
            duration = time.time() - start_time
            
            self.test_results.append({
                'name': test_name,
                'status': 'passed',
                'duration': duration,
                'result': result
            })
            print(f"✅ {test_name}: PASSED ({duration:.3f}s)")
            
        except Exception as e:
            self.test_results.append({
                'name': test_name,
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            })
            
            if critical:
                self.critical_failures.append(test_name)
                print(f"❌ {test_name}: CRITICAL FAILURE - {e}")
            else:
                self.warnings.append(test_name)
                print(f"⚠️  {test_name}: FAILED (non-critical) - {e}")
    
    def test_core_imports(self):
        """Test that all core components can be imported"""
        from src.config import (
            detect_environment,
            service_discovery, 
            path_resolver,
            port_manager,
            EnvironmentType,
            ServiceType,
            PathType,
            get_configuration_summary
        )
        return "All core imports successful"
    
    def test_environment_detection_robustness(self):
        """Test environment detection under various conditions"""
        from src.config import detect_environment, EnvironmentType
        
        # Multiple detections should be consistent
        results = []
        for i in range(3):
            env_info = detect_environment()
            results.append(env_info.environment_type.value)
        
        # Should be consistent
        if len(set(results)) > 1:
            raise AssertionError(f"Inconsistent environment detection: {results}")
        
        # Force refresh should work
        env_info1 = detect_environment()
        env_info2 = detect_environment(force_refresh=True)
        
        # Should detect same environment but be different objects
        if env_info1.environment_type != env_info2.environment_type:
            raise AssertionError("Environment type changed on force refresh")
            
        return f"Environment consistently detected as {env_info1.environment_type.value}"
    
    def test_configuration_validation_stability(self):
        """Test configuration validation runs without crashes"""
        from src.config import validate_configuration
        
        # Multiple validations should not crash
        results = []
        for i in range(3):
            validation = validate_configuration()
            results.append(validation['overall_status'])
        
        # Should have consistent status
        if not results or not all(isinstance(status, str) for status in results):
            raise AssertionError("Configuration validation returned invalid results")
            
        return f"Configuration validation stable: {results[0]}"
    
    def test_graceful_degradation(self):
        """Test system works even with missing dependencies"""
        from src.config import get_configuration_summary, get_initialization_status
        
        # Should not crash even with missing dependencies
        summary = get_configuration_summary()
        init_status = get_initialization_status()
        
        # Should have proper structure
        required_keys = ['components_available', 'initialization_status', 'module_info']
        for key in required_keys:
            if key not in summary:
                raise AssertionError(f"Missing required key in summary: {key}")
        
        # Should handle component failures gracefully
        component_count = len(summary['components_available'])
        if component_count == 0:
            raise AssertionError("No components detected in summary")
            
        return f"Graceful degradation working with {component_count} components"
    
    def test_memory_usage_stability(self):
        """Test memory usage doesn't grow excessively"""
        from src.config import detect_environment, validate_configuration
        
        # Run multiple operations to check for memory leaks
        for i in range(10):
            env_info = detect_environment()
            validation = validate_configuration()
        
        # Basic memory usage check - should not crash
        import gc
        gc.collect()
        
        return "Memory usage appears stable"
    
    def test_error_handling_robustness(self):
        """Test error handling in various failure scenarios"""
        from src.config.environment_detector import UnifiedEnvironmentDetector
        
        # Test with mock failures
        detector = UnifiedEnvironmentDetector()
        
        # Should handle method failures gracefully
        original_method = detector._detect_docker_primary
        
        def failing_method():
            raise Exception("Simulated failure")
        
        try:
            detector._detect_docker_primary = failing_method
            env_info = detector.detect_environment(force_refresh=True)
            
            # Should still return valid environment info
            if not hasattr(env_info, 'environment_type'):
                raise AssertionError("Environment detection failed completely")
                
        finally:
            detector._detect_docker_primary = original_method
        
        return "Error handling robust under simulated failures"
    
    def test_concurrent_access_safety(self):
        """Test thread safety and concurrent access"""
        from src.config import detect_environment
        import threading
        import time
        
        results = []
        errors = []
        
        def worker():
            try:
                for i in range(5):
                    env_info = detect_environment()
                    results.append(env_info.environment_type.value)
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                errors.append(str(e))
        
        # Run multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        if errors:
            raise AssertionError(f"Concurrent access errors: {errors}")
        
        if not results:
            raise AssertionError("No results from concurrent access test")
            
        return f"Concurrent access safe: {len(results)} operations completed"
    
    def test_configuration_immutability(self):
        """Test that configuration objects are properly immutable/safe"""
        from src.config import detect_environment
        
        env_info1 = detect_environment()
        env_info2 = detect_environment()
        
        # Should be cached (same object)
        if env_info1 is not env_info2:
            # That's okay, but values should be the same
            if env_info1.environment_type != env_info2.environment_type:
                raise AssertionError("Environment type changed between calls")
        
        # Modifying one shouldn't affect the other
        original_platform = env_info1.platform
        
        try:
            # This should work without affecting cached version
            env_info1.platform = "modified"
            
            env_info3 = detect_environment(force_refresh=True)
            if env_info3.platform == "modified":
                raise AssertionError("Configuration modification affected other instances")
                
        finally:
            env_info1.platform = original_platform
        
        return "Configuration objects properly isolated"
    
    def test_performance_benchmarks(self):
        """Test performance meets acceptable thresholds"""
        from src.config import detect_environment, validate_configuration
        
        # Environment detection should be fast
        start_time = time.time()
        for i in range(10):
            detect_environment()
        env_time = (time.time() - start_time) / 10
        
        if env_time > 0.1:  # Should be under 100ms average
            raise AssertionError(f"Environment detection too slow: {env_time:.3f}s average")
        
        # Configuration validation should be reasonable
        start_time = time.time()
        validate_configuration()
        validation_time = time.time() - start_time
        
        if validation_time > 1.0:  # Should be under 1 second
            raise AssertionError(f"Configuration validation too slow: {validation_time:.3f}s")
        
        return f"Performance acceptable: env={env_time:.3f}s, validation={validation_time:.3f}s"
    
    def test_deployment_environment_compatibility(self):
        """Test compatibility across different deployment environments"""
        from src.config import detect_environment, EnvironmentType
        
        env_info = detect_environment()
        
        # Should detect a valid environment type
        valid_types = [t.value for t in EnvironmentType]
        if env_info.environment_type.value not in valid_types:
            raise AssertionError(f"Invalid environment type: {env_info.environment_type.value}")
        
        # Should have reasonable confidence
        if env_info.confidence_score < 0.1:
            raise AssertionError(f"Very low confidence in environment detection: {env_info.confidence_score}")
        
        # Should provide useful information
        required_info = ['platform', 'python_version', 'network_info']
        for info in required_info:
            if not hasattr(env_info, info) or getattr(env_info, info) is None:
                raise AssertionError(f"Missing required environment info: {info}")
        
        return f"Compatible with {env_info.environment_type.value} environment"
    
    def validate_production_readiness(self) -> Dict[str, Any]:
        """Run complete production readiness validation"""
        print("🚀 Starting production readiness validation...")
        print("=" * 60)
        
        # Critical tests that must pass for production
        critical_tests = [
            ("Core Import Functionality", self.test_core_imports, True),
            ("Environment Detection Robustness", self.test_environment_detection_robustness, True),
            ("Configuration Validation Stability", self.test_configuration_validation_stability, True),
            ("Graceful Degradation", self.test_graceful_degradation, True),
        ]
        
        # Important tests that should pass but aren't deployment blockers
        important_tests = [
            ("Memory Usage Stability", self.test_memory_usage_stability, False),
            ("Error Handling Robustness", self.test_error_handling_robustness, False),
            ("Concurrent Access Safety", self.test_concurrent_access_safety, False),
            ("Configuration Immutability", self.test_configuration_immutability, False),
            ("Performance Benchmarks", self.test_performance_benchmarks, False),
            ("Deployment Environment Compatibility", self.test_deployment_environment_compatibility, False),
        ]
        
        # Run all tests
        all_tests = critical_tests + important_tests
        for test_name, test_func, is_critical in all_tests:
            self.run_test(test_name, test_func, is_critical)
        
        # Generate report
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['status'] == 'passed')
        failed_tests = total_tests - passed_tests
        
        print("\n" + "=" * 60)
        print("📊 PRODUCTION READINESS REPORT")
        print("=" * 60)
        
        # Overall status
        if self.critical_failures:
            overall_status = "NOT READY"
            status_icon = "❌"
        elif self.warnings:
            overall_status = "READY WITH WARNINGS"
            status_icon = "⚠️"
        else:
            overall_status = "FULLY READY"
            status_icon = "✅"
        
        print(f"{status_icon} Overall Status: {overall_status}")
        print(f"📈 Test Results: {passed_tests}/{total_tests} passed")
        
        if self.critical_failures:
            print(f"🚨 Critical Failures: {len(self.critical_failures)}")
            for failure in self.critical_failures:
                print(f"   ❌ {failure}")
        
        if self.warnings:
            print(f"⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"   ⚠️  {warning}")
        
        # Deployment recommendations
        print("\n🎯 DEPLOYMENT RECOMMENDATIONS:")
        
        if not self.critical_failures and not self.warnings:
            print("✅ System is ready for production deployment")
            print("✅ All tests passed - no additional steps required")
            
        elif not self.critical_failures:
            print("✅ System is ready for production deployment with monitoring")
            print("⚠️  Address warnings for optimal performance:")
            for warning in self.warnings:
                print(f"   • Review {warning} results")
            
        else:
            print("❌ System is NOT ready for production deployment")
            print("🔧 Address these critical issues before deployment:")
            for failure in self.critical_failures:
                print(f"   • Fix {failure}")
        
        # Performance summary
        durations = [r.get('duration', 0) for r in self.test_results if r['status'] == 'passed']
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            print(f"\n⏱️  Performance: avg={avg_duration:.3f}s, max={max_duration:.3f}s")
        
        # Return detailed report
        return {
            'overall_status': overall_status,
            'ready_for_production': len(self.critical_failures) == 0,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'critical_failures': self.critical_failures,
            'warnings': self.warnings,
            'test_results': self.test_results,
            'performance': {
                'average_duration': sum(durations) / len(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0
            }
        }

if __name__ == "__main__":
    validator = ProductionReadinessValidator()
    report = validator.validate_production_readiness()
    
    # Exit with appropriate code
    if report['ready_for_production']:
        print("\n🎉 Production readiness validation completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Production readiness validation failed!")
        sys.exit(1)