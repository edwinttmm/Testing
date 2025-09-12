#!/usr/bin/env python3
"""
Path Management Test Runner
Comprehensive test runner for all path management tests with reporting
"""

import pytest
import os
import sys
import time
import json
from datetime import datetime
import subprocess
import argparse

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend/src'))


class PathManagementTestRunner:
    """Test runner for path management test suite"""
    
    def __init__(self):
        self.test_dir = os.path.dirname(__file__)
        self.results_dir = os.path.join(self.test_dir, 'results')
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.test_categories = {
            'unit': [
                'test_path_resolver.py',
                'test_environment_detector.py',
                'test_path_validation_normalization.py'
            ],
            'integration': [
                'test_ground_truth_path_processing.py',
                'test_working_directory_contexts.py',
                'test_error_handling_missing_files.py',
                'test_path_migration.py',
                'test_container_deployment_simulation.py',
                'test_cross_platform_compatibility.py'
            ]
        }
    
    def run_test_category(self, category, verbose=True, capture_output=True):
        """Run tests for a specific category"""
        print(f"\n{'='*60}")
        print(f"Running {category.upper()} Tests")
        print(f"{'='*60}")
        
        test_files = self.test_categories.get(category, [])
        if not test_files:
            print(f"No tests found for category: {category}")
            return {'status': 'error', 'message': 'No tests found'}
        
        results = {}
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        
        for test_file in test_files:
            test_path = os.path.join(self.test_dir, test_file)
            
            if not os.path.exists(test_path):
                print(f"⚠️  Test file not found: {test_file}")
                continue
            
            print(f"\n📋 Running: {test_file}")
            print("-" * 40)
            
            # Build pytest command
            cmd = [
                sys.executable, '-m', 'pytest', 
                test_path,
                '-v' if verbose else '-q',
                '--tb=short',
                f'--junit-xml={self.results_dir}/{test_file}.xml'
            ]
            
            if not capture_output:
                cmd.append('-s')  # Don't capture output
            
            # Run the test
            start_time = time.time()
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=capture_output,
                    text=True,
                    cwd=self.test_dir
                )
                end_time = time.time()
                
                duration = end_time - start_time
                
                # Parse results from pytest output
                if result.returncode == 0:
                    status = "✅ PASSED"
                elif result.returncode == 1:
                    status = "❌ FAILED" 
                elif result.returncode == 2:
                    status = "🔧 ERROR"
                else:
                    status = f"❓ UNKNOWN ({result.returncode})"
                
                # Extract test statistics from output
                output = result.stdout if result.stdout else result.stderr
                passed = output.count(' PASSED')
                failed = output.count(' FAILED')
                skipped = output.count(' SKIPPED')
                
                total_passed += passed
                total_failed += failed
                total_skipped += skipped
                
                results[test_file] = {
                    'status': status,
                    'duration': duration,
                    'passed': passed,
                    'failed': failed,
                    'skipped': skipped,
                    'output': output[:1000] if len(output) > 1000 else output  # Truncate long output
                }
                
                print(f"Status: {status}")
                print(f"Duration: {duration:.2f}s")
                print(f"Tests: {passed} passed, {failed} failed, {skipped} skipped")
                
                if not capture_output and result.stdout:
                    print("\nOutput:")
                    print(result.stdout)
                
                if result.stderr:
                    print("\nErrors:")
                    print(result.stderr)
            
            except Exception as e:
                print(f"❌ Error running {test_file}: {e}")
                results[test_file] = {
                    'status': '❌ ERROR',
                    'duration': 0,
                    'passed': 0,
                    'failed': 1,
                    'skipped': 0,
                    'error': str(e)
                }
                total_failed += 1
        
        # Category summary
        print(f"\n{'='*40}")
        print(f"{category.upper()} TESTS SUMMARY")
        print(f"{'='*40}")
        print(f"Total Passed:  {total_passed}")
        print(f"Total Failed:  {total_failed}")
        print(f"Total Skipped: {total_skipped}")
        print(f"Success Rate:  {(total_passed / (total_passed + total_failed) * 100):.1f}%" if (total_passed + total_failed) > 0 else "N/A")
        
        return {
            'status': 'success',
            'category': category,
            'results': results,
            'summary': {
                'passed': total_passed,
                'failed': total_failed,
                'skipped': total_skipped,
                'total': total_passed + total_failed + total_skipped
            }
        }
    
    def run_all_tests(self, verbose=True, capture_output=True):
        """Run all test categories"""
        print("🧪 PATH MANAGEMENT COMPREHENSIVE TEST SUITE")
        print("=" * 60)
        
        start_time = time.time()
        all_results = {}
        
        # Run each category
        for category in self.test_categories.keys():
            category_results = self.run_test_category(category, verbose, capture_output)
            all_results[category] = category_results
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Overall summary
        total_passed = sum(r['summary']['passed'] for r in all_results.values() if 'summary' in r)
        total_failed = sum(r['summary']['failed'] for r in all_results.values() if 'summary' in r)
        total_skipped = sum(r['summary']['skipped'] for r in all_results.values() if 'summary' in r)
        
        print(f"\n🏆 OVERALL TEST RESULTS")
        print("=" * 60)
        print(f"Duration:      {total_duration:.2f}s")
        print(f"Total Passed:  {total_passed}")
        print(f"Total Failed:  {total_failed}")
        print(f"Total Skipped: {total_skipped}")
        print(f"Success Rate:  {(total_passed / (total_passed + total_failed) * 100):.1f}%" if (total_passed + total_failed) > 0 else "N/A")
        
        # Save detailed results
        self.save_results(all_results, total_duration)
        
        return all_results
    
    def save_results(self, results, duration):
        """Save test results to JSON file"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'duration': duration,
            'results': results,
            'environment': {
                'platform': sys.platform,
                'python_version': sys.version,
                'working_directory': os.getcwd()
            }
        }
        
        results_file = os.path.join(self.results_dir, f'test_results_{int(time.time())}.json')
        
        try:
            with open(results_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"\n📊 Results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Failed to save results: {e}")
    
    def run_specific_tests(self, test_pattern, verbose=True):
        """Run tests matching a specific pattern"""
        print(f"🔍 Running tests matching pattern: {test_pattern}")
        
        cmd = [
            sys.executable, '-m', 'pytest',
            self.test_dir,
            '-k', test_pattern,
            '-v' if verbose else '-q',
            '--tb=short'
        ]
        
        try:
            result = subprocess.run(cmd, cwd=self.test_dir)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return False
    
    def run_by_markers(self, markers, verbose=True):
        """Run tests by pytest markers"""
        print(f"🏷️  Running tests with markers: {', '.join(markers)}")
        
        cmd = [
            sys.executable, '-m', 'pytest',
            self.test_dir,
            '-v' if verbose else '-q',
            '--tb=short'
        ]
        
        # Add marker filters
        for marker in markers:
            cmd.extend(['-m', marker])
        
        try:
            result = subprocess.run(cmd, cwd=self.test_dir)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return False
    
    def validate_test_environment(self):
        """Validate test environment and dependencies"""
        print("🔍 Validating test environment...")
        
        validation_results = {
            'python_version': sys.version_info >= (3, 8),
            'pytest_available': False,
            'backend_modules': False,
            'test_files': False
        }
        
        # Check pytest
        try:
            import pytest
            validation_results['pytest_available'] = True
            print("✅ pytest is available")
        except ImportError:
            print("❌ pytest is not available")
        
        # Check backend modules
        try:
            from config.path_resolver import PathResolver
            from config.environment_detector import UnifiedEnvironmentDetector
            validation_results['backend_modules'] = True
            print("✅ Backend modules are importable")
        except ImportError as e:
            print(f"❌ Backend modules not available: {e}")
        
        # Check test files
        total_test_files = sum(len(files) for files in self.test_categories.values())
        existing_files = 0
        
        for category, files in self.test_categories.items():
            for test_file in files:
                test_path = os.path.join(self.test_dir, test_file)
                if os.path.exists(test_path):
                    existing_files += 1
        
        validation_results['test_files'] = existing_files == total_test_files
        print(f"📁 Test files: {existing_files}/{total_test_files} found")
        
        # Overall validation
        all_valid = all(validation_results.values())
        
        if all_valid:
            print("✅ Test environment is ready")
        else:
            print("❌ Test environment has issues")
            for check, valid in validation_results.items():
                if not valid:
                    print(f"  ❌ {check}")
        
        return all_valid


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Path Management Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_runner.py                    # Run all tests
  python test_runner.py --unit             # Run only unit tests
  python test_runner.py --integration      # Run only integration tests
  python test_runner.py --pattern "path"   # Run tests matching "path"
  python test_runner.py --markers unit     # Run tests with 'unit' marker
  python test_runner.py --validate         # Validate test environment
        """
    )
    
    parser.add_argument('--unit', action='store_true',
                       help='Run only unit tests')
    parser.add_argument('--integration', action='store_true',
                       help='Run only integration tests')
    parser.add_argument('--pattern', type=str,
                       help='Run tests matching pattern')
    parser.add_argument('--markers', nargs='+',
                       help='Run tests with specific markers')
    parser.add_argument('--validate', action='store_true',
                       help='Validate test environment')
    parser.add_argument('--quiet', action='store_true',
                       help='Quiet output (less verbose)')
    parser.add_argument('--no-capture', action='store_true',
                       help='Don\'t capture test output')
    
    args = parser.parse_args()
    
    runner = PathManagementTestRunner()
    
    # Validate environment if requested
    if args.validate:
        is_valid = runner.validate_test_environment()
        return 0 if is_valid else 1
    
    verbose = not args.quiet
    capture_output = not args.no_capture
    
    try:
        # Run specific test categories
        if args.unit:
            results = runner.run_test_category('unit', verbose, capture_output)
        elif args.integration:
            results = runner.run_test_category('integration', verbose, capture_output)
        elif args.pattern:
            success = runner.run_specific_tests(args.pattern, verbose)
            return 0 if success else 1
        elif args.markers:
            success = runner.run_by_markers(args.markers, verbose)
            return 0 if success else 1
        else:
            # Run all tests
            results = runner.run_all_tests(verbose, capture_output)
        
        # Return appropriate exit code
        if isinstance(results, dict):
            if 'summary' in results:
                return 0 if results['summary']['failed'] == 0 else 1
            else:
                # Multiple categories
                total_failed = sum(r['summary']['failed'] for r in results.values() if 'summary' in r)
                return 0 if total_failed == 0 else 1
        
        return 0
    
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1


if __name__ == '__main__':
    exit(main())