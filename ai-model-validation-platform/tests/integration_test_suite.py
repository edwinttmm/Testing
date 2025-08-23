#!/usr/bin/env python3
"""
Integration Test Suite for AI Model Validation Platform
Testing cross-feature interactions and real-world usage patterns
"""

import asyncio
import aiohttp
import pytest
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any
import tempfile
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegrationTestSuite:
    """Integration testing for cross-feature interactions"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        
    async def setup(self):
        self.session = aiohttp.ClientSession()
        logger.info("🔗 Integration Test Suite initialized")
        
    async def cleanup(self):
        if self.session:
            await self.session.close()

    async def test_video_upload_to_annotation_workflow(self) -> Dict[str, Any]:
        """Test complete workflow: Upload → Annotation → Export"""
        logger.info("🎬 Testing Video Upload to Annotation workflow...")
        
        results = {
            'workflow_name': 'Video Upload to Annotation',
            'steps_completed': [],
            'performance_metrics': {},
            'issues': []
        }
        
        try:
            # Step 1: Upload a test video
            upload_start = time.time()
            test_video_data = b"fake_video_data_for_testing"
            
            # Create multipart form data
            form_data = aiohttp.FormData()
            form_data.add_field('file', 
                              test_video_data, 
                              filename='test_video.mp4',
                              content_type='video/mp4')
            
            async with self.session.post(f"{self.base_url}/api/videos", 
                                       data=form_data) as response:
                upload_time = time.time() - upload_start
                results['performance_metrics']['upload_time'] = upload_time
                
                if response.status in [200, 201]:
                    video_data = await response.json()
                    video_id = video_data.get('id', 'test-video-id')
                    results['steps_completed'].append('Video Upload')
                    
                    # Step 2: Create annotation session
                    session_start = time.time()
                    async with self.session.post(f"{self.base_url}/api/annotation-sessions", 
                                               json={
                                                   'video_id': video_id,
                                                   'session_name': 'Integration Test Session'
                                               }) as session_response:
                        session_time = time.time() - session_start
                        results['performance_metrics']['session_creation_time'] = session_time
                        
                        if session_response.status in [200, 201]:
                            session_data = await session_response.json()
                            session_id = session_data.get('id', 'test-session-id')
                            results['steps_completed'].append('Annotation Session Creation')
                            
                            # Step 3: Add annotations
                            annotation_start = time.time()
                            test_annotation = {
                                'session_id': session_id,
                                'frame_number': 1,
                                'shapes': [{
                                    'type': 'rectangle',
                                    'bbox': [10, 10, 100, 100],
                                    'label': 'pedestrian',
                                    'confidence': 0.95
                                }]
                            }
                            
                            async with self.session.post(f"{self.base_url}/api/annotations",
                                                       json=test_annotation) as annotation_response:
                                annotation_time = time.time() - annotation_start
                                results['performance_metrics']['annotation_time'] = annotation_time
                                
                                if annotation_response.status in [200, 201]:
                                    results['steps_completed'].append('Annotation Creation')
                                    
                                    # Step 4: Export annotations
                                    export_start = time.time()
                                    async with self.session.post(f"{self.base_url}/api/annotations/export",
                                                               json={
                                                                   'session_id': session_id,
                                                                   'format': 'json'
                                                               }) as export_response:
                                        export_time = time.time() - export_start
                                        results['performance_metrics']['export_time'] = export_time
                                        
                                        if export_response.status == 200:
                                            results['steps_completed'].append('Annotation Export')
                                        else:
                                            results['issues'].append(f'Export failed: {export_response.status}')
                                else:
                                    results['issues'].append(f'Annotation creation failed: {annotation_response.status}')
                        else:
                            results['issues'].append(f'Session creation failed: {session_response.status}')
                else:
                    results['issues'].append(f'Video upload failed: {response.status}')
                    
            results['success'] = len(results['steps_completed']) == 4
            results['completion_rate'] = len(results['steps_completed']) / 4 * 100
            
        except Exception as e:
            results['issues'].append(f'Workflow error: {str(e)}')
            results['success'] = False
            results['completion_rate'] = len(results['steps_completed']) / 4 * 100
        
        return results

    async def test_project_creation_to_test_execution(self) -> Dict[str, Any]:
        """Test: Project Creation → Video Assignment → Test Execution"""
        logger.info("📁 Testing Project Creation to Test Execution workflow...")
        
        results = {
            'workflow_name': 'Project to Test Execution',
            'steps_completed': [],
            'performance_metrics': {},
            'issues': []
        }
        
        try:
            # Step 1: Create project
            project_start = time.time()
            project_data = {
                'name': 'Integration Test Project',
                'description': 'Test project for integration testing',
                'status': 'active'
            }
            
            async with self.session.post(f"{self.base_url}/api/projects",
                                       json=project_data) as response:
                project_time = time.time() - project_start
                results['performance_metrics']['project_creation_time'] = project_time
                
                if response.status in [200, 201]:
                    project = await response.json()
                    project_id = project.get('id', 'test-project-id')
                    results['steps_completed'].append('Project Creation')
                    
                    # Step 2: Assign videos to project (simulate)
                    assignment_start = time.time()
                    async with self.session.get(f"{self.base_url}/api/videos") as videos_response:
                        if videos_response.status == 200:
                            videos = await videos_response.json()
                            assignment_time = time.time() - assignment_start
                            results['performance_metrics']['video_assignment_time'] = assignment_time
                            results['steps_completed'].append('Video Assignment')
                            
                            # Step 3: Create test session
                            session_start = time.time()
                            test_session_data = {
                                'project_id': project_id,
                                'latency_threshold': 100
                            }
                            
                            async with self.session.post(f"{self.base_url}/api/test-sessions",
                                                       json=test_session_data) as session_response:
                                session_time = time.time() - session_start
                                results['performance_metrics']['test_session_time'] = session_time
                                
                                if session_response.status in [200, 201]:
                                    session = await session_response.json()
                                    session_id = session.get('id', 'test-session-id')
                                    results['steps_completed'].append('Test Session Creation')
                                    
                                    # Step 4: Check session status
                                    status_start = time.time()
                                    async with self.session.get(f"{self.base_url}/api/test-sessions/{session_id}") as status_response:
                                        status_time = time.time() - status_start
                                        results['performance_metrics']['status_check_time'] = status_time
                                        
                                        if status_response.status == 200:
                                            results['steps_completed'].append('Test Execution Status Check')
                                        else:
                                            results['issues'].append(f'Status check failed: {status_response.status}')
                                else:
                                    results['issues'].append(f'Test session creation failed: {session_response.status}')
                        else:
                            results['issues'].append(f'Video retrieval failed: {videos_response.status}')
                else:
                    results['issues'].append(f'Project creation failed: {response.status}')
                    
            results['success'] = len(results['steps_completed']) == 4
            results['completion_rate'] = len(results['steps_completed']) / 4 * 100
            
        except Exception as e:
            results['issues'].append(f'Workflow error: {str(e)}')
            results['success'] = False
            results['completion_rate'] = len(results['steps_completed']) / 4 * 100
        
        return results

    async def test_concurrent_user_simulation(self) -> Dict[str, Any]:
        """Test concurrent users performing various operations"""
        logger.info("👥 Testing Concurrent User Simulation...")
        
        results = {
            'workflow_name': 'Concurrent Users',
            'concurrent_operations': [],
            'performance_metrics': {},
            'issues': []
        }
        
        try:
            # Simulate 5 concurrent users
            concurrent_tasks = []
            
            # User 1: Dashboard access
            concurrent_tasks.append(self._simulate_dashboard_user())
            
            # User 2: Project management
            concurrent_tasks.append(self._simulate_project_user())
            
            # User 3: Annotation workflow
            concurrent_tasks.append(self._simulate_annotation_user())
            
            # User 4: Test execution
            concurrent_tasks.append(self._simulate_test_user())
            
            # User 5: File management
            concurrent_tasks.append(self._simulate_file_user())
            
            start_time = time.time()
            task_results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            results['performance_metrics']['total_concurrent_time'] = total_time
            results['performance_metrics']['average_response_time'] = total_time / len(concurrent_tasks)
            
            successful_operations = 0
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    results['issues'].append(f'User {i+1} failed: {str(result)}')
                else:
                    results['concurrent_operations'].append(result)
                    if result.get('success', False):
                        successful_operations += 1
            
            results['success_rate'] = successful_operations / len(concurrent_tasks) * 100
            results['success'] = successful_operations >= 3  # At least 3 out of 5 succeed
            
        except Exception as e:
            results['issues'].append(f'Concurrent simulation error: {str(e)}')
            results['success'] = False
        
        return results

    async def _simulate_dashboard_user(self) -> Dict[str, Any]:
        """Simulate user accessing dashboard"""
        try:
            start_time = time.time()
            async with self.session.get(f"{self.base_url}/api/dashboard/stats") as response:
                response_time = time.time() - start_time
                return {
                    'user_type': 'Dashboard User',
                    'success': response.status == 200,
                    'response_time': response_time,
                    'operations': ['dashboard_access']
                }
        except Exception as e:
            return {'user_type': 'Dashboard User', 'success': False, 'error': str(e)}

    async def _simulate_project_user(self) -> Dict[str, Any]:
        """Simulate user managing projects"""
        try:
            start_time = time.time()
            
            # Get projects
            async with self.session.get(f"{self.base_url}/api/projects") as response:
                if response.status == 200:
                    projects = await response.json()
                    response_time = time.time() - start_time
                    return {
                        'user_type': 'Project User',
                        'success': True,
                        'response_time': response_time,
                        'operations': ['list_projects'],
                        'data_count': len(projects) if isinstance(projects, list) else 0
                    }
                else:
                    return {
                        'user_type': 'Project User',
                        'success': False,
                        'response_time': time.time() - start_time,
                        'error': f'HTTP {response.status}'
                    }
        except Exception as e:
            return {'user_type': 'Project User', 'success': False, 'error': str(e)}

    async def _simulate_annotation_user(self) -> Dict[str, Any]:
        """Simulate user working with annotations"""
        try:
            start_time = time.time()
            
            # Try to get annotation sessions
            async with self.session.get(f"{self.base_url}/api/annotation-sessions") as response:
                response_time = time.time() - start_time
                return {
                    'user_type': 'Annotation User',
                    'success': response.status in [200, 404],  # 404 is OK for empty data
                    'response_time': response_time,
                    'operations': ['list_annotation_sessions']
                }
        except Exception as e:
            return {'user_type': 'Annotation User', 'success': False, 'error': str(e)}

    async def _simulate_test_user(self) -> Dict[str, Any]:
        """Simulate user executing tests"""
        try:
            start_time = time.time()
            
            # Try to get test sessions
            async with self.session.get(f"{self.base_url}/api/test-sessions") as response:
                response_time = time.time() - start_time
                return {
                    'user_type': 'Test User',
                    'success': response.status in [200, 404],  # 404 is OK for empty data
                    'response_time': response_time,
                    'operations': ['list_test_sessions']
                }
        except Exception as e:
            return {'user_type': 'Test User', 'success': False, 'error': str(e)}

    async def _simulate_file_user(self) -> Dict[str, Any]:
        """Simulate user managing files"""
        try:
            start_time = time.time()
            
            # Try to get videos (files)
            async with self.session.get(f"{self.base_url}/api/videos") as response:
                response_time = time.time() - start_time
                return {
                    'user_type': 'File User',
                    'success': response.status == 200,
                    'response_time': response_time,
                    'operations': ['list_videos']
                }
        except Exception as e:
            return {'user_type': 'File User', 'success': False, 'error': str(e)}

    async def test_data_consistency_across_features(self) -> Dict[str, Any]:
        """Test data consistency across different features"""
        logger.info("🔄 Testing Data Consistency across features...")
        
        results = {
            'workflow_name': 'Data Consistency',
            'consistency_checks': [],
            'performance_metrics': {},
            'issues': []
        }
        
        try:
            # Check 1: Project count consistency
            project_start = time.time()
            async with self.session.get(f"{self.base_url}/api/projects") as projects_response:
                if projects_response.status == 200:
                    projects = await projects_response.json()
                    project_count_api = len(projects) if isinstance(projects, list) else 0
                    
                    # Check dashboard stats
                    async with self.session.get(f"{self.base_url}/api/dashboard/stats") as stats_response:
                        if stats_response.status == 200:
                            stats = await stats_response.json()
                            project_count_dashboard = stats.get('total_projects', 0)
                            
                            consistency_time = time.time() - project_start
                            results['performance_metrics']['consistency_check_time'] = consistency_time
                            
                            if project_count_api == project_count_dashboard:
                                results['consistency_checks'].append({
                                    'check': 'Project Count Consistency',
                                    'status': 'PASS',
                                    'api_count': project_count_api,
                                    'dashboard_count': project_count_dashboard
                                })
                            else:
                                results['consistency_checks'].append({
                                    'check': 'Project Count Consistency',
                                    'status': 'FAIL',
                                    'api_count': project_count_api,
                                    'dashboard_count': project_count_dashboard
                                })
                                results['issues'].append('Project count mismatch between API and dashboard')
                        else:
                            results['issues'].append('Dashboard stats unavailable')
                else:
                    results['issues'].append('Projects API unavailable')
            
            # Check 2: Video count consistency
            video_start = time.time()
            async with self.session.get(f"{self.base_url}/api/videos") as videos_response:
                if videos_response.status == 200:
                    videos = await videos_response.json()
                    video_count = len(videos) if isinstance(videos, list) else 0
                    
                    results['consistency_checks'].append({
                        'check': 'Video Data Availability',
                        'status': 'PASS',
                        'count': video_count
                    })
                    
                    video_check_time = time.time() - video_start
                    results['performance_metrics']['video_consistency_time'] = video_check_time
                else:
                    results['consistency_checks'].append({
                        'check': 'Video Data Availability',
                        'status': 'FAIL',
                        'error': f'HTTP {videos_response.status}'
                    })
                    results['issues'].append('Video API unavailable')
            
            # Summary
            passed_checks = sum(1 for check in results['consistency_checks'] if check['status'] == 'PASS')
            total_checks = len(results['consistency_checks'])
            
            results['consistency_rate'] = (passed_checks / total_checks * 100) if total_checks > 0 else 0
            results['success'] = passed_checks == total_checks
            
        except Exception as e:
            results['issues'].append(f'Consistency check error: {str(e)}')
            results['success'] = False
        
        return results

    async def test_error_recovery_scenarios(self) -> Dict[str, Any]:
        """Test system behavior under error conditions"""
        logger.info("🛡️ Testing Error Recovery scenarios...")
        
        results = {
            'workflow_name': 'Error Recovery',
            'error_scenarios': [],
            'performance_metrics': {},
            'issues': []
        }
        
        try:
            # Scenario 1: Invalid API calls
            invalid_start = time.time()
            async with self.session.get(f"{self.base_url}/api/nonexistent-endpoint") as response:
                invalid_time = time.time() - invalid_start
                results['performance_metrics']['invalid_endpoint_response_time'] = invalid_time
                
                results['error_scenarios'].append({
                    'scenario': 'Invalid Endpoint',
                    'expected_status': 404,
                    'actual_status': response.status,
                    'handled_correctly': response.status == 404,
                    'response_time': invalid_time
                })
            
            # Scenario 2: Malformed data
            malformed_start = time.time()
            async with self.session.post(f"{self.base_url}/api/projects",
                                       json={'invalid': 'data', 'missing': 'required_fields'}) as response:
                malformed_time = time.time() - malformed_start
                results['performance_metrics']['malformed_data_response_time'] = malformed_time
                
                results['error_scenarios'].append({
                    'scenario': 'Malformed Data',
                    'expected_status_range': [400, 422],
                    'actual_status': response.status,
                    'handled_correctly': response.status in [400, 422],
                    'response_time': malformed_time
                })
            
            # Scenario 3: Non-existent resource access
            notfound_start = time.time()
            async with self.session.get(f"{self.base_url}/api/projects/nonexistent-id") as response:
                notfound_time = time.time() - notfound_start
                results['performance_metrics']['notfound_response_time'] = notfound_time
                
                results['error_scenarios'].append({
                    'scenario': 'Non-existent Resource',
                    'expected_status': 404,
                    'actual_status': response.status,
                    'handled_correctly': response.status == 404,
                    'response_time': notfound_time
                })
            
            # Summary
            properly_handled = sum(1 for scenario in results['error_scenarios'] 
                                 if scenario['handled_correctly'])
            total_scenarios = len(results['error_scenarios'])
            
            results['error_handling_rate'] = (properly_handled / total_scenarios * 100) if total_scenarios > 0 else 0
            results['success'] = properly_handled == total_scenarios
            
        except Exception as e:
            results['issues'].append(f'Error recovery test failed: {str(e)}')
            results['success'] = False
        
        return results

    async def run_comprehensive_integration_tests(self) -> Dict[str, Any]:
        """Run all integration tests"""
        logger.info("🔗 Starting Comprehensive Integration Testing...")
        
        await self.setup()
        
        try:
            # Run all integration test categories
            integration_tests = [
                self.test_video_upload_to_annotation_workflow(),
                self.test_project_creation_to_test_execution(),
                self.test_concurrent_user_simulation(),
                self.test_data_consistency_across_features(),
                self.test_error_recovery_scenarios()
            ]
            
            start_time = time.time()
            test_results = await asyncio.gather(*integration_tests, return_exceptions=True)
            total_execution_time = time.time() - start_time
            
            # Process results
            successful_tests = 0
            all_test_results = []
            all_issues = []
            
            for i, result in enumerate(test_results):
                if isinstance(result, Exception):
                    all_issues.append(f"Integration test {i+1} failed: {str(result)}")
                else:
                    all_test_results.append(result)
                    if result.get('success', False):
                        successful_tests += 1
                    all_issues.extend(result.get('issues', []))
            
            # Generate comprehensive report
            report = {
                'integration_test_summary': {
                    'total_tests': len(integration_tests),
                    'successful_tests': successful_tests,
                    'failed_tests': len(integration_tests) - successful_tests,
                    'success_rate': (successful_tests / len(integration_tests) * 100) if len(integration_tests) > 0 else 0,
                    'total_execution_time': total_execution_time
                },
                'workflow_results': all_test_results,
                'performance_analysis': self._analyze_integration_performance(all_test_results),
                'issues_summary': {
                    'total_issues': len(all_issues),
                    'critical_issues': [issue for issue in all_issues if any(word in issue.lower() 
                                                                             for word in ['failed', 'error', 'crash'])],
                    'all_issues': all_issues
                },
                'recommendations': self._generate_integration_recommendations(all_test_results, all_issues),
                'test_execution_metadata': {
                    'timestamp': time.time(),
                    'environment': 'Testing',
                    'concurrent_operations_tested': True,
                    'cross_feature_validation': True
                }
            }
            
            return report
            
        finally:
            await self.cleanup()

    def _analyze_integration_performance(self, test_results: List[Dict]) -> Dict[str, Any]:
        """Analyze performance across integration tests"""
        all_metrics = {}
        
        for result in test_results:
            metrics = result.get('performance_metrics', {})
            all_metrics.update(metrics)
        
        if not all_metrics:
            return {'status': 'No performance data available'}
        
        response_times = [v for k, v in all_metrics.items() if 'time' in k.lower()]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'average_response_time': avg_response_time,
            'total_operations': len(all_metrics),
            'performance_rating': 'EXCELLENT' if avg_response_time < 0.5 else 
                                'GOOD' if avg_response_time < 1.0 else 
                                'FAIR' if avg_response_time < 2.0 else 'NEEDS_IMPROVEMENT',
            'slowest_operations': sorted(all_metrics.items(), key=lambda x: x[1], reverse=True)[:3]
        }

    def _generate_integration_recommendations(self, test_results: List[Dict], issues: List[str]) -> List[str]:
        """Generate recommendations based on integration test results"""
        recommendations = []
        
        # Analyze workflow completion rates
        workflow_success_rates = []
        for result in test_results:
            if 'completion_rate' in result:
                workflow_success_rates.append(result['completion_rate'])
            elif 'success' in result:
                workflow_success_rates.append(100 if result['success'] else 0)
        
        if workflow_success_rates:
            avg_completion = sum(workflow_success_rates) / len(workflow_success_rates)
            if avg_completion < 80:
                recommendations.append(f"🔴 CRITICAL: Average workflow completion rate is {avg_completion:.1f}%. Investigate workflow failures.")
            elif avg_completion < 95:
                recommendations.append(f"🟡 WARNING: Workflow completion rate is {avg_completion:.1f}%. Some optimizations needed.")
        
        # Check for concurrent performance issues
        concurrent_results = [r for r in test_results if r.get('workflow_name') == 'Concurrent Users']
        if concurrent_results:
            concurrent_success = concurrent_results[0].get('success_rate', 0)
            if concurrent_success < 80:
                recommendations.append("⚡ CONCURRENCY: System struggles under concurrent load. Consider performance optimizations.")
        
        # Check data consistency
        consistency_results = [r for r in test_results if r.get('workflow_name') == 'Data Consistency']
        if consistency_results and not consistency_results[0].get('success', True):
            recommendations.append("🔄 DATA CONSISTENCY: Data inconsistencies detected across features. Review data synchronization.")
        
        # Check error handling
        error_results = [r for r in test_results if r.get('workflow_name') == 'Error Recovery']
        if error_results:
            error_handling_rate = error_results[0].get('error_handling_rate', 0)
            if error_handling_rate < 90:
                recommendations.append("🛡️ ERROR HANDLING: Improve error handling and user feedback mechanisms.")
        
        # General issue analysis
        critical_issues = len([issue for issue in issues if any(word in issue.lower() 
                                                              for word in ['failed', 'error', 'crash'])])
        if critical_issues > 3:
            recommendations.append(f"🐛 BUG FIXES: {critical_issues} critical issues found. Prioritize bug fixes.")
        
        if not recommendations:
            recommendations.append("✅ INTEGRATION: All integration tests performing well. Continue monitoring.")
        
        return recommendations

async def main():
    """Run comprehensive integration testing"""
    logger.info("🔗 Starting Integration Test Suite for AI Model Validation Platform")
    
    tester = IntegrationTestSuite()
    report = await tester.run_comprehensive_integration_tests()
    
    # Save report
    report_file = Path('/home/user/Testing/ai-model-validation-platform/tests/integration_test_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "="*80)
    print("🔗 INTEGRATION TESTING - EXECUTIVE SUMMARY")
    print("="*80)
    
    summary = report['integration_test_summary']
    print(f"📊 Integration Tests: {summary['total_tests']}")
    print(f"✅ Tests Passed: {summary['successful_tests']}")
    print(f"❌ Tests Failed: {summary['failed_tests']}")
    print(f"📈 Success Rate: {summary['success_rate']:.1f}%")
    print(f"⏱️  Execution Time: {summary['total_execution_time']:.2f}s")
    
    performance = report['performance_analysis']
    print(f"\n⚡ Performance Rating: {performance['performance_rating']}")
    print(f"📊 Average Response Time: {performance['average_response_time']:.3f}s")
    
    issues = report['issues_summary']
    print(f"\n🐛 Total Issues: {issues['total_issues']}")
    print(f"🔴 Critical Issues: {len(issues['critical_issues'])}")
    
    print("\n📋 KEY INTEGRATION RECOMMENDATIONS:")
    for i, rec in enumerate(report['recommendations'][:5], 1):
        print(f"  {i}. {rec}")
    
    print(f"\n📄 Detailed report: {report_file}")
    print("="*80)
    
    return report

if __name__ == "__main__":
    asyncio.run(main())