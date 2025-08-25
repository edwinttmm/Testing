#!/usr/bin/env python3
"""
Master Test Runner - All Connectivity Tests
==========================================

Orchestrates and runs all connectivity test suites for the AI Model Validation Platform.
Provides comprehensive testing of localhost and external IP accessibility.

Test Suites Included:
1. Comprehensive Connectivity Test
2. Frontend-Backend Integration Test  
3. Performance and Load Test
4. Continuous Health Monitoring (optional)

Author: AI Model Validation Platform
Date: 2025-08-24
"""

import asyncio
import json
import logging
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse

class MasterTestRunner:
    """Master test runner for all connectivity tests."""
    
    def __init__(self, config_file: str = 'test_config.json'):
        self.setup_logging()
        self.config = self.load_config(config_file)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_suites': {},
            'summary': {},
            'failed_tests': [],
            'recommendations': []
        }
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('master_connectivity_test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self, config_file: str) -> Dict:
        """Load test configuration."""
        default_config = {
            'test_suites': {
                'comprehensive_connectivity': {
                    'enabled': True,
                    'script': 'comprehensive_connectivity_test.py',
                    'timeout': 300,
                    'critical': True
                },
                'frontend_backend_integration': {
                    'enabled': True,
                    'script': 'frontend_backend_integration_test.py',
                    'timeout': 600,
                    'critical': True
                },
                'performance_load': {
                    'enabled': True,
                    'script': 'performance_load_test.py',
                    'timeout': 900,
                    'critical': False
                },
                'health_monitoring': {
                    'enabled': False,
                    'script': 'continuous_health_monitor.py',
                    'timeout': 60,
                    'critical': False
                }
            },
            'environments': {
                'localhost': {
                    'frontend_url': 'http://127.0.0.1:3000',
                    'backend_url': 'http://127.0.0.1:8000'
                },
                'external': {
                    'frontend_url': 'http://155.138.239.131:3000',
                    'backend_url': 'http://155.138.239.131:8000'
                }
            },
            'reporting': {
                'generate_html_report': True,
                'send_email_report': False,
                'save_json_results': True
            }
        }
        
        try:
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                # Merge with defaults
                default_config.update(loaded_config)
            else:
                # Create default config file
                with open(config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                self.logger.info(f"Created default config file: {config_file}")
                    
        except Exception as e:
            self.logger.warning(f"Could not load config file: {e}")
            
        return default_config
        
    def check_prerequisites(self) -> bool:
        """Check if all test prerequisites are met."""
        self.logger.info("🔍 Checking test prerequisites...")
        
        prerequisites_ok = True
        
        # Check if test scripts exist
        for suite_name, suite_config in self.config['test_suites'].items():
            if suite_config['enabled']:
                script_path = Path(suite_config['script'])
                if not script_path.exists():
                    self.logger.error(f"❌ Test script not found: {script_path}")
                    prerequisites_ok = False
                else:
                    self.logger.info(f"✅ Found test script: {script_path}")
                    
        # Check Python dependencies
        required_packages = [
            'requests', 'aiohttp', 'websocket-client', 
            'selenium', 'psutil', 'numpy', 'matplotlib'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
                
        if missing_packages:
            self.logger.warning(f"⚠️ Missing optional packages: {missing_packages}")
            self.logger.info("Some tests may be skipped. Install with: pip install " + " ".join(missing_packages))
            
        # Check network connectivity to test targets
        import requests
        
        for env_name, env_config in self.config['environments'].items():
            try:
                response = requests.get(
                    f"{env_config['backend_url']}/health", 
                    timeout=10, 
                    verify=False
                )
                if response.status_code < 400:
                    self.logger.info(f"✅ {env_name} backend is accessible")
                else:
                    self.logger.warning(f"⚠️ {env_name} backend returned status {response.status_code}")
                    
            except Exception as e:
                self.logger.warning(f"⚠️ Could not reach {env_name} backend: {e}")
                
        return prerequisites_ok
        
    async def run_test_suite(self, suite_name: str, suite_config: Dict) -> Dict[str, Any]:
        """Run a single test suite."""
        self.logger.info(f"\n🚀 Running test suite: {suite_name}")
        self.logger.info("=" * 60)
        
        result = {
            'suite_name': suite_name,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': 0,
            'success': False,
            'exit_code': None,
            'stdout': '',
            'stderr': '',
            'timeout': False,
            'error': None
        }
        
        try:
            script_path = Path(suite_config['script'])
            if not script_path.exists():
                raise FileNotFoundError(f"Test script not found: {script_path}")
                
            # Run the test script
            start_time = time.time()
            
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd()
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=suite_config['timeout']
                )
                
                exit_code = process.returncode
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                result['timeout'] = True
                result['error'] = f"Test suite timed out after {suite_config['timeout']} seconds"
                self.logger.error(f"❌ {suite_name} timed out")
                return result
                
            end_time = time.time()
            duration = end_time - start_time
            
            result.update({
                'end_time': datetime.now().isoformat(),
                'duration_seconds': round(duration, 2),
                'success': exit_code == 0,
                'exit_code': exit_code,
                'stdout': stdout.decode('utf-8', errors='replace'),
                'stderr': stderr.decode('utf-8', errors='replace')
            })
            
            if exit_code == 0:
                self.logger.info(f"✅ {suite_name} completed successfully ({duration:.1f}s)")
            else:
                self.logger.error(f"❌ {suite_name} failed with exit code {exit_code} ({duration:.1f}s)")
                if result['stderr']:
                    self.logger.error(f"Error output: {result['stderr'][:500]}...")
                    
        except Exception as e:
            result['error'] = str(e)
            result['end_time'] = datetime.now().isoformat()
            self.logger.error(f"❌ {suite_name} failed with exception: {e}")
            
        return result
        
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze all test results and generate summary."""
        summary = {
            'total_suites': 0,
            'successful_suites': 0,
            'failed_suites': 0,
            'timed_out_suites': 0,
            'critical_failures': 0,
            'total_duration': 0,
            'overall_success': True
        }
        
        failed_tests = []
        recommendations = []
        
        for suite_name, suite_result in self.results['test_suites'].items():
            summary['total_suites'] += 1
            summary['total_duration'] += suite_result.get('duration_seconds', 0)
            
            if suite_result.get('success'):
                summary['successful_suites'] += 1
            else:
                summary['failed_suites'] += 1
                failed_tests.append({
                    'suite': suite_name,
                    'error': suite_result.get('error'),
                    'exit_code': suite_result.get('exit_code'),
                    'timeout': suite_result.get('timeout', False)
                })
                
                # Check if this was a critical test
                suite_config = self.config['test_suites'].get(suite_name, {})
                if suite_config.get('critical', False):
                    summary['critical_failures'] += 1
                    summary['overall_success'] = False
                    
                if suite_result.get('timeout'):
                    summary['timed_out_suites'] += 1
                    
        # Generate recommendations based on failures
        if summary['critical_failures'] > 0:
            recommendations.append("🚨 CRITICAL: Fix failed connectivity tests before deployment")
            
        if summary['timed_out_suites'] > 0:
            recommendations.append("⏱️ Some tests timed out - check network connectivity and performance")
            
        if summary['failed_suites'] > 0 and summary['critical_failures'] == 0:
            recommendations.append("⚠️ Non-critical tests failed - investigate but deployment may proceed")
            
        if summary['overall_success']:
            recommendations.append("✅ All critical connectivity tests passed - system ready for deployment")
            
        self.results['summary'] = summary
        self.results['failed_tests'] = failed_tests
        self.results['recommendations'] = recommendations
        
        return summary
        
    def generate_html_report(self) -> str:
        """Generate HTML report."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Model Validation Platform - Connectivity Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
                .summary {{ background: white; padding: 20px; margin: 20px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .test-suite {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #ddd; }}
                .success {{ border-left-color: #27ae60; }}
                .failure {{ border-left-color: #e74c3c; }}
                .timeout {{ border-left-color: #f39c12; }}
                .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
                .metric-value {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
                .metric-label {{ color: #7f8c8d; }}
                .recommendations {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .log-output {{ background: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: scroll; }}
                pre {{ white-space: pre-wrap; word-wrap: break-word; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>AI Model Validation Platform</h1>
                <h2>Connectivity Test Report</h2>
                <p>Generated: {timestamp}</p>
            </div>
            
            <div class="summary">
                <h3>Test Summary</h3>
                <div class="metric">
                    <div class="metric-value">{total_suites}</div>
                    <div class="metric-label">Total Suites</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #27ae60;">{successful_suites}</div>
                    <div class="metric-label">Successful</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #e74c3c;">{failed_suites}</div>
                    <div class="metric-label">Failed</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="color: #f39c12;">{critical_failures}</div>
                    <div class="metric-label">Critical Failures</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{total_duration:.1f}s</div>
                    <div class="metric-label">Total Duration</div>
                </div>
            </div>
            
            <div class="recommendations">
                <h3>Recommendations</h3>
                <ul>
                    {recommendations_html}
                </ul>
            </div>
            
            <div>
                <h3>Test Suite Results</h3>
                {test_suites_html}
            </div>
        </body>
        </html>
        """
        
        # Build test suites HTML
        test_suites_html = ""
        for suite_name, suite_result in self.results['test_suites'].items():
            status_class = 'success' if suite_result.get('success') else ('timeout' if suite_result.get('timeout') else 'failure')
            status_icon = '✅' if suite_result.get('success') else ('⏱️' if suite_result.get('timeout') else '❌')
            
            stdout_preview = suite_result.get('stdout', '')[:1000]
            stderr_preview = suite_result.get('stderr', '')[:1000]
            
            test_suites_html += f"""
            <div class="test-suite {status_class}">
                <h4>{status_icon} {suite_name}</h4>
                <p><strong>Duration:</strong> {suite_result.get('duration_seconds', 0):.2f}s</p>
                <p><strong>Exit Code:</strong> {suite_result.get('exit_code', 'N/A')}</p>
                {f'<p><strong>Error:</strong> {suite_result.get("error", "")}</p>' if suite_result.get('error') else ''}
                
                {f'<details><summary>Standard Output</summary><div class="log-output"><pre>{stdout_preview}{"..." if len(suite_result.get("stdout", "")) > 1000 else ""}</pre></div></details>' if stdout_preview else ''}
                
                {f'<details><summary>Error Output</summary><div class="log-output"><pre>{stderr_preview}{"..." if len(suite_result.get("stderr", "")) > 1000 else ""}</pre></div></details>' if stderr_preview else ''}
            </div>
            """
            
        # Build recommendations HTML
        recommendations_html = ""
        for rec in self.results.get('recommendations', []):
            recommendations_html += f"<li>{rec}</li>"
            
        # Fill template
        summary = self.results['summary']
        html_content = html_template.format(
            timestamp=self.results['timestamp'],
            total_suites=summary['total_suites'],
            successful_suites=summary['successful_suites'], 
            failed_suites=summary['failed_suites'],
            critical_failures=summary['critical_failures'],
            total_duration=summary['total_duration'],
            recommendations_html=recommendations_html,
            test_suites_html=test_suites_html
        )
        
        return html_content
        
    def save_reports(self):
        """Save all reports to files."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON results
        if self.config['reporting']['save_json_results']:
            json_file = f"connectivity_test_results_{timestamp}.json"
            with open(json_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            self.logger.info(f"📊 Saved JSON results: {json_file}")
            
        # Save HTML report
        if self.config['reporting']['generate_html_report']:
            html_content = self.generate_html_report()
            html_file = f"connectivity_test_report_{timestamp}.html"
            with open(html_file, 'w') as f:
                f.write(html_content)
            self.logger.info(f"📄 Saved HTML report: {html_file}")
            
    async def run_all_tests(self, suites_to_run: Optional[List[str]] = None):
        """Run all enabled test suites."""
        start_time = time.time()
        
        self.logger.info("🚀 Starting Master Connectivity Test Runner")
        self.logger.info("=" * 80)
        self.logger.info(f"Target Environments:")
        for env_name, env_config in self.config['environments'].items():
            self.logger.info(f"  {env_name}: {env_config['frontend_url']}")
            
        # Check prerequisites
        if not self.check_prerequisites():
            self.logger.warning("⚠️ Some prerequisites not met, continuing with available tests...")
            
        # Determine which suites to run
        if suites_to_run:
            suites = {name: config for name, config in self.config['test_suites'].items() 
                     if name in suites_to_run and config['enabled']}
        else:
            suites = {name: config for name, config in self.config['test_suites'].items() 
                     if config['enabled']}
                     
        self.logger.info(f"\n📋 Running {len(suites)} test suites:")
        for suite_name in suites.keys():
            self.logger.info(f"  - {suite_name}")
            
        # Run test suites
        for suite_name, suite_config in suites.items():
            suite_result = await self.run_test_suite(suite_name, suite_config)
            self.results['test_suites'][suite_name] = suite_result
            
        # Analyze results
        summary = self.analyze_results()
        
        total_time = time.time() - start_time
        
        # Generate final report
        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 FINAL TEST RESULTS")
        self.logger.info("=" * 80)
        self.logger.info(f"Total Test Duration: {total_time:.2f} seconds")
        self.logger.info(f"Test Suites: {summary['successful_suites']}/{summary['total_suites']} passed")
        self.logger.info(f"Critical Failures: {summary['critical_failures']}")
        
        # Print recommendations
        if self.results['recommendations']:
            self.logger.info("\n📋 RECOMMENDATIONS:")
            for rec in self.results['recommendations']:
                self.logger.info(f"  {rec}")
                
        # Print failed tests
        if self.results['failed_tests']:
            self.logger.info("\n❌ FAILED TESTS:")
            for failed_test in self.results['failed_tests']:
                suite_name = failed_test['suite']
                error = failed_test.get('error', 'Unknown error')
                self.logger.info(f"  {suite_name}: {error}")
                
        # Save reports
        self.save_reports()
        
        # Overall result
        if summary['overall_success']:
            self.logger.info("\n✅ ALL CRITICAL TESTS PASSED - SYSTEM READY")
            return 0
        else:
            self.logger.error(f"\n❌ {summary['critical_failures']} CRITICAL TEST(S) FAILED")
            return 1


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='AI Model Validation Platform - Master Connectivity Test Runner'
    )
    
    parser.add_argument(
        '--config', 
        default='test_config.json',
        help='Configuration file path'
    )
    
    parser.add_argument(
        '--suites',
        nargs='+',
        help='Specific test suites to run (default: all enabled suites)',
        choices=[
            'comprehensive_connectivity',
            'frontend_backend_integration', 
            'performance_load',
            'health_monitoring'
        ]
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run only critical tests (skip performance tests)'
    )
    
    args = parser.parse_args()
    
    # Initialize test runner
    runner = MasterTestRunner(args.config)
    
    # Determine suites to run
    suites_to_run = args.suites
    
    if args.quick:
        # Only run critical tests
        suites_to_run = ['comprehensive_connectivity', 'frontend_backend_integration']
        runner.logger.info("🏃‍♂️ Quick mode: Running only critical tests")
        
    try:
        exit_code = await runner.run_all_tests(suites_to_run)
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        runner.logger.info("\n⏹️ Test execution interrupted by user")
        sys.exit(130)
        
    except Exception as e:
        runner.logger.error(f"\n💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())