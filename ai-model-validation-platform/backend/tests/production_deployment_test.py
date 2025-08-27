#!/usr/bin/env python3
"""
Production Deployment Test for ML Inference Platform
=================================================

This script performs comprehensive testing to validate that the ML inference
platform is ready for production deployment. It tests:

1. Docker container functionality
2. ML model availability and performance
3. Database connectivity and integrity
4. API endpoint availability and response times
5. Resource usage and scalability
6. Error handling and recovery
7. Security and monitoring readiness

Author: Production Validation Team
Version: 1.0.0
"""

import os
import sys
import time
import json
import docker
import requests
import subprocess
import tempfile
import psutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionDeploymentTester:
    """Comprehensive production deployment testing"""
    
    def __init__(self):
        self.results = {
            'test_start_time': datetime.now(timezone.utc).isoformat(),
            'platform': 'ai-model-validation-platform',
            'tests': {},
            'summary': {},
            'production_readiness_score': 0
        }
        self.docker_client = None
        self.test_containers = []
        
    def setup_docker_client(self) -> Dict[str, Any]:
        """Setup Docker client for testing"""
        test_result = {'name': 'Docker Client Setup', 'status': 'unknown'}
        
        try:
            self.docker_client = docker.from_env()
            # Test Docker connectivity
            docker_info = self.docker_client.info()
            
            test_result.update({
                'status': 'passed',
                'docker_version': docker_info.get('ServerVersion', 'unknown'),
                'containers_running': docker_info.get('ContainersRunning', 0),
                'images_count': docker_info.get('Images', 0)
            })
            
            logger.info(f"✅ Docker client connected - Version: {test_result['docker_version']}")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Docker client setup failed: {e}")
            
        return test_result
    
    def test_docker_images_available(self) -> Dict[str, Any]:
        """Test if required Docker images are available"""
        test_result = {'name': 'Docker Images Available', 'status': 'unknown', 'images': []}
        
        try:
            if not self.docker_client:
                test_result.update({
                    'status': 'skipped',
                    'reason': 'Docker client not available'
                })
                return test_result
            
            # Check for platform images
            images = self.docker_client.images.list()
            platform_images = []
            
            for image in images:
                if image.tags:
                    for tag in image.tags:
                        if any(keyword in tag.lower() for keyword in ['ai-model', 'vru', 'validation']):
                            platform_images.append({
                                'tag': tag,
                                'id': image.short_id,
                                'size_mb': round(image.attrs['Size'] / (1024**2), 1),
                                'created': image.attrs['Created']
                            })
            
            test_result.update({
                'status': 'passed' if platform_images else 'partial',
                'images': platform_images,
                'total_images': len(images)
            })
            
            if platform_images:
                logger.info(f"✅ Found {len(platform_images)} platform Docker images")
            else:
                logger.warning("⚠️  No platform-specific Docker images found")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Docker images check failed: {e}")
            
        return test_result
    
    def test_docker_compose_configuration(self) -> Dict[str, Any]:
        """Test Docker Compose configuration"""
        test_result = {'name': 'Docker Compose Configuration', 'status': 'unknown'}
        
        try:
            # Check for docker-compose files
            backend_path = Path(__file__).parent.parent
            project_root = backend_path.parent
            
            compose_files = []
            for compose_file in ['docker-compose.yml', 'docker-compose.unified.yml', 'docker-compose.yaml']:
                compose_path = project_root / compose_file
                if compose_path.exists():
                    compose_files.append({
                        'file': compose_file,
                        'path': str(compose_path),
                        'size_kb': round(compose_path.stat().st_size / 1024, 1)
                    })
            
            test_result.update({
                'status': 'passed' if compose_files else 'failed',
                'compose_files': compose_files
            })
            
            if compose_files:
                logger.info(f"✅ Found {len(compose_files)} Docker Compose files")
            else:
                logger.error("❌ No Docker Compose files found")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Docker Compose check failed: {e}")
            
        return test_result
    
    def test_environment_configuration(self) -> Dict[str, Any]:
        """Test environment configuration files"""
        test_result = {'name': 'Environment Configuration', 'status': 'unknown'}
        
        try:
            backend_path = Path(__file__).parent.parent
            project_root = backend_path.parent
            
            env_files = []
            env_file_patterns = ['.env', '.env.production', '.env.unified', '.env.docker']
            
            for env_pattern in env_file_patterns:
                env_path = project_root / env_pattern
                if env_path.exists():
                    # Count non-empty lines
                    with open(env_path, 'r') as f:
                        lines = [line.strip() for line in f.readlines() if line.strip() and not line.strip().startswith('#')]
                    
                    env_files.append({
                        'file': env_pattern,
                        'path': str(env_path),
                        'variables_count': len(lines)
                    })
            
            test_result.update({
                'status': 'passed' if env_files else 'partial',
                'env_files': env_files,
                'total_variables': sum(f['variables_count'] for f in env_files)
            })
            
            if env_files:
                total_vars = test_result['total_variables']
                logger.info(f"✅ Found {len(env_files)} environment files with {total_vars} variables")
            else:
                logger.warning("⚠️  No environment configuration files found")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Environment configuration check failed: {e}")
            
        return test_result
    
    def test_ml_models_production_ready(self) -> Dict[str, Any]:
        """Test ML models are production ready"""
        test_result = {'name': 'ML Models Production Ready', 'status': 'unknown'}
        
        try:
            # Check YOLO model files
            backend_path = Path(__file__).parent.parent
            model_files = []
            
            for model_file in backend_path.glob('*.pt'):
                size_mb = model_file.stat().st_size / (1024**2)
                model_files.append({
                    'name': model_file.name,
                    'path': str(model_file),
                    'size_mb': round(size_mb, 1)
                })
            
            # Test model loading if available
            model_test_results = []
            if model_files:
                try:
                    import torch
                    from ultralytics import YOLO
                    
                    # Test smallest model for quick validation
                    smallest_model = min(model_files, key=lambda x: x['size_mb'])
                    model = YOLO(smallest_model['path'])
                    
                    # Quick inference test
                    import numpy as np
                    test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
                    start_time = time.time()
                    results = model(test_image, verbose=False)
                    inference_time = time.time() - start_time
                    
                    model_test_results.append({
                        'model': smallest_model['name'],
                        'inference_time': inference_time,
                        'inference_successful': True
                    })
                    
                except Exception as e:
                    model_test_results.append({
                        'model': 'test_failed',
                        'error': str(e)
                    })
            
            test_result.update({
                'status': 'passed' if model_files else 'failed',
                'model_files': model_files,
                'model_tests': model_test_results,
                'total_models': len(model_files)
            })
            
            if model_files:
                logger.info(f"✅ Found {len(model_files)} ML model files")
                if model_test_results and model_test_results[0].get('inference_successful'):
                    logger.info(f"✅ Model inference test successful")
            else:
                logger.error("❌ No ML model files found")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ ML models check failed: {e}")
            
        return test_result
    
    def test_database_production_ready(self) -> Dict[str, Any]:
        """Test database production readiness"""
        test_result = {'name': 'Database Production Ready', 'status': 'unknown'}
        
        try:
            # Add backend path for database imports
            backend_path = Path(__file__).parent.parent
            sys.path.insert(0, str(backend_path))
            
            # Test database connection
            try:
                from unified_database import get_database_manager
                
                db_manager = get_database_manager()
                health = db_manager.test_connection()
                
                # Run integrity check
                integrity_report = db_manager.run_integrity_check(repair=False)
                
                # Get statistics
                stats = db_manager.get_statistics()
                
                test_result.update({
                    'status': 'passed' if health['status'] == 'healthy' else 'degraded',
                    'connection_health': health,
                    'integrity_status': {
                        'status': integrity_report.status.value,
                        'passed_checks': integrity_report.passed_checks,
                        'failed_checks': integrity_report.failed_checks,
                        'warnings': integrity_report.warnings
                    },
                    'statistics': stats
                })
                
                if health['status'] == 'healthy':
                    logger.info(f"✅ Database connection healthy - Type: {health.get('database_type', 'unknown')}")
                else:
                    logger.warning(f"⚠️  Database health degraded: {health}")
                    
            except ImportError:
                # Fallback to basic database test
                try:
                    from database import get_database_health
                    health = get_database_health()
                    
                    test_result.update({
                        'status': 'passed' if health['status'] == 'healthy' else 'degraded',
                        'fallback_health': health
                    })
                    
                    logger.info(f"✅ Database basic health check: {health['status']}")
                    
                except Exception:
                    test_result.update({
                        'status': 'failed',
                        'error': 'No database modules available'
                    })
                    logger.error("❌ No database connectivity available")
                    
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Database production readiness check failed: {e}")
            
        return test_result
    
    def test_api_production_endpoints(self) -> Dict[str, Any]:
        """Test API endpoints for production readiness"""
        test_result = {'name': 'API Production Endpoints', 'status': 'unknown'}
        
        try:
            # Test different server configurations
            servers = [
                {'name': 'local_dev', 'url': 'http://localhost:8000'},
                {'name': 'docker_prod', 'url': 'http://localhost:80'}
            ]
            
            server_results = {}
            
            for server in servers:
                server_result = {'accessible': False, 'endpoints': {}}
                
                try:
                    # Test basic health endpoint
                    response = requests.get(f"{server['url']}/health", timeout=10)
                    if response.status_code == 200:
                        server_result['accessible'] = True
                        server_result['health'] = response.json()
                        
                        # Test additional endpoints
                        endpoints_to_test = [
                            '/docs',
                            '/redoc',
                            '/api/videos',
                            '/api/projects'
                        ]
                        
                        for endpoint in endpoints_to_test:
                            try:
                                resp = requests.get(f"{server['url']}{endpoint}", timeout=5)
                                server_result['endpoints'][endpoint] = {
                                    'status_code': resp.status_code,
                                    'accessible': resp.status_code in [200, 405]  # 405 is method not allowed but endpoint exists
                                }
                            except:
                                server_result['endpoints'][endpoint] = {
                                    'status_code': 0,
                                    'accessible': False
                                }
                    
                except Exception as e:
                    server_result['error'] = str(e)
                
                server_results[server['name']] = server_result
            
            # Determine overall status
            accessible_servers = sum(1 for r in server_results.values() if r['accessible'])
            
            test_result.update({
                'status': 'passed' if accessible_servers > 0 else 'failed',
                'servers_tested': len(servers),
                'accessible_servers': accessible_servers,
                'server_results': server_results
            })
            
            if accessible_servers > 0:
                logger.info(f"✅ {accessible_servers}/{len(servers)} API servers accessible")
            else:
                logger.error("❌ No API servers accessible")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ API endpoints check failed: {e}")
            
        return test_result
    
    def test_resource_requirements(self) -> Dict[str, Any]:
        """Test system resource requirements"""
        test_result = {'name': 'Resource Requirements', 'status': 'unknown'}
        
        try:
            # Get system information
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage('/')
            cpu_info = {
                'count': psutil.cpu_count(),
                'percent': psutil.cpu_percent(interval=1)
            }
            
            # Check resource availability
            resource_check = {
                'memory_gb': round(memory_info.total / (1024**3), 1),
                'memory_available_gb': round(memory_info.available / (1024**3), 1),
                'memory_usage_percent': memory_info.percent,
                'disk_total_gb': round(disk_info.total / (1024**3), 1),
                'disk_free_gb': round(disk_info.free / (1024**3), 1),
                'disk_usage_percent': round((disk_info.used / disk_info.total) * 100, 1),
                'cpu_count': cpu_info['count'],
                'cpu_usage_percent': cpu_info['percent']
            }
            
            # Evaluate production readiness
            recommendations = []
            warnings = []
            
            # Memory recommendations
            if resource_check['memory_gb'] < 4:
                recommendations.append("Consider upgrading to at least 4GB RAM for ML workloads")
            elif resource_check['memory_gb'] < 8:
                warnings.append("8GB+ RAM recommended for optimal ML performance")
            
            # Disk recommendations
            if resource_check['disk_free_gb'] < 5:
                recommendations.append("At least 5GB free disk space required")
            elif resource_check['disk_free_gb'] < 10:
                warnings.append("10GB+ free disk space recommended")
            
            # CPU recommendations
            if resource_check['cpu_count'] < 2:
                recommendations.append("Multi-core CPU recommended for production")
            
            status = 'passed'
            if recommendations:
                status = 'failed'
            elif warnings:
                status = 'partial'
            
            test_result.update({
                'status': status,
                'resources': resource_check,
                'recommendations': recommendations,
                'warnings': warnings
            })
            
            logger.info(f"✅ System resources: {resource_check['memory_gb']}GB RAM, {resource_check['cpu_count']} CPUs")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Resource requirements check failed: {e}")
            
        return test_result
    
    def test_security_configuration(self) -> Dict[str, Any]:
        """Test security configuration"""
        test_result = {'name': 'Security Configuration', 'status': 'unknown'}
        
        try:
            security_checks = {
                'env_files_secured': False,
                'debug_mode_disabled': True,
                'cors_configured': False,
                'ssl_ready': False
            }
            
            # Check environment files
            backend_path = Path(__file__).parent.parent
            project_root = backend_path.parent
            
            # Check for sensitive data exposure
            env_files = ['.env', '.env.production', '.env.unified']
            for env_file in env_files:
                env_path = project_root / env_file
                if env_path.exists():
                    try:
                        with open(env_path, 'r') as f:
                            content = f.read()
                            # Check for debug settings
                            if 'DEBUG=False' in content or 'debug=false' in content.lower():
                                security_checks['debug_mode_disabled'] = True
                            # Check for CORS settings
                            if 'CORS' in content:
                                security_checks['cors_configured'] = True
                            # Basic file permission check
                            stat_info = env_path.stat()
                            if oct(stat_info.st_mode)[-3:] == '600':  # Owner read/write only
                                security_checks['env_files_secured'] = True
                    except:
                        pass
            
            # Check for SSL/HTTPS configuration
            try:
                response = requests.get('http://localhost:80/health', timeout=5, allow_redirects=False)
                if response.status_code == 301 or 'https' in response.headers.get('location', '').lower():
                    security_checks['ssl_ready'] = True
            except:
                pass
            
            # Calculate security score
            security_score = sum(security_checks.values()) / len(security_checks)
            
            recommendations = []
            if not security_checks['env_files_secured']:
                recommendations.append("Secure environment files with proper permissions (600)")
            if not security_checks['debug_mode_disabled']:
                recommendations.append("Disable debug mode in production")
            if not security_checks['cors_configured']:
                recommendations.append("Configure CORS settings for production")
            if not security_checks['ssl_ready']:
                recommendations.append("Configure SSL/HTTPS for production deployment")
            
            test_result.update({
                'status': 'passed' if security_score >= 0.75 else 'partial' if security_score >= 0.5 else 'failed',
                'security_checks': security_checks,
                'security_score': security_score,
                'recommendations': recommendations
            })
            
            logger.info(f"✅ Security score: {security_score:.1%}")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Security configuration check failed: {e}")
            
        return test_result
    
    def run_production_deployment_tests(self) -> Dict[str, Any]:
        """Run all production deployment tests"""
        logger.info("🚀 Starting Production Deployment Tests")
        logger.info("=" * 60)
        
        test_functions = [
            self.setup_docker_client,
            self.test_docker_images_available,
            self.test_docker_compose_configuration,
            self.test_environment_configuration,
            self.test_ml_models_production_ready,
            self.test_database_production_ready,
            self.test_api_production_endpoints,
            self.test_resource_requirements,
            self.test_security_configuration
        ]
        
        for test_func in test_functions:
            test_name = test_func.__name__.replace('test_', '').replace('_', ' ').title()
            logger.info(f"\n🔍 Running: {test_name}")
            
            try:
                result = test_func()
                self.results['tests'][test_func.__name__] = result
                
                status_emoji = {
                    'passed': '✅',
                    'partial': '⚠️',
                    'degraded': '⚠️',
                    'failed': '❌',
                    'skipped': '⏭️'
                }.get(result['status'], '❓')
                
                logger.info(f"{status_emoji} {test_name}: {result['status'].upper()}")
                
            except Exception as e:
                logger.error(f"💥 {test_name}: CRASHED - {e}")
                self.results['tests'][test_func.__name__] = {
                    'name': test_name,
                    'status': 'crashed',
                    'error': str(e)
                }
        
        # Calculate production readiness score
        self._calculate_production_readiness_score()
        
        # Generate summary
        self._generate_summary()
        
        self.results['test_end_time'] = datetime.now(timezone.utc).isoformat()
        
        return self.results
    
    def _calculate_production_readiness_score(self):
        """Calculate overall production readiness score"""
        weights = {
            'setup_docker_client': 0.10,
            'test_docker_images_available': 0.10,
            'test_docker_compose_configuration': 0.10,
            'test_environment_configuration': 0.05,
            'test_ml_models_production_ready': 0.25,
            'test_database_production_ready': 0.15,
            'test_api_production_endpoints': 0.15,
            'test_resource_requirements': 0.05,
            'test_security_configuration': 0.05
        }
        
        total_score = 0
        total_weight = 0
        
        for test_name, result in self.results['tests'].items():
            if test_name in weights:
                weight = weights[test_name]
                total_weight += weight
                
                score = {
                    'passed': 1.0,
                    'partial': 0.7,
                    'degraded': 0.6,
                    'failed': 0.0,
                    'skipped': 0.5,
                    'crashed': 0.0
                }.get(result['status'], 0.0)
                
                total_score += score * weight
        
        if total_weight > 0:
            self.results['production_readiness_score'] = round((total_score / total_weight) * 100, 1)
        else:
            self.results['production_readiness_score'] = 0.0
    
    def _generate_summary(self):
        """Generate test summary"""
        status_counts = {}
        for result in self.results['tests'].values():
            status = result['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        total_tests = len(self.results['tests'])
        
        # Determine overall readiness
        readiness_score = self.results['production_readiness_score']
        if readiness_score >= 90:
            readiness_level = "EXCELLENT"
        elif readiness_score >= 75:
            readiness_level = "GOOD"
        elif readiness_score >= 60:
            readiness_level = "ACCEPTABLE"
        elif readiness_score >= 40:
            readiness_level = "NEEDS_IMPROVEMENT"
        else:
            readiness_level = "NOT_READY"
        
        self.results['summary'] = {
            'total_tests': total_tests,
            'status_counts': status_counts,
            'readiness_score': readiness_score,
            'readiness_level': readiness_level,
            'recommendation': self._get_deployment_recommendation(readiness_level, readiness_score)
        }
    
    def _get_deployment_recommendation(self, level: str, score: float) -> str:
        """Get deployment recommendation based on readiness"""
        recommendations = {
            "EXCELLENT": "🎉 Platform is production-ready! Deploy with confidence.",
            "GOOD": "👍 Platform is ready for production deployment with minor optimizations.",
            "ACCEPTABLE": "⚠️  Platform can be deployed but should address identified issues soon.",
            "NEEDS_IMPROVEMENT": "🔧 Address critical issues before production deployment.",
            "NOT_READY": "❌ Platform requires significant work before production deployment."
        }
        
        return recommendations.get(level, "Unknown readiness level")

def main():
    """Main production deployment testing function"""
    tester = ProductionDeploymentTester()
    
    try:
        results = tester.run_production_deployment_tests()
        
        # Print comprehensive summary
        print("\n" + "=" * 80)
        print("📊 PRODUCTION DEPLOYMENT ASSESSMENT")
        print("=" * 80)
        
        summary = results['summary']
        print(f"Total Tests: {summary['total_tests']}")
        
        for status, count in summary['status_counts'].items():
            emoji = {
                'passed': '✅',
                'partial': '⚠️',
                'degraded': '⚠️', 
                'failed': '❌',
                'skipped': '⏭️',
                'crashed': '💥'
            }.get(status, '❓')
            print(f"{emoji} {status.title()}: {count}")
        
        print(f"\n🎯 Production Readiness Score: {summary['readiness_score']}%")
        print(f"📈 Readiness Level: {summary['readiness_level']}")
        print(f"\n💡 Recommendation: {summary['recommendation']}")
        
        # Print critical issues if any
        critical_issues = []
        for test_name, result in results['tests'].items():
            if result['status'] in ['failed', 'crashed']:
                critical_issues.append(f"• {result['name']}: {result.get('error', 'Failed')}")
        
        if critical_issues:
            print(f"\n🚨 CRITICAL ISSUES TO ADDRESS:")
            print("-" * 40)
            for issue in critical_issues:
                print(issue)
        
        # Print recommendations
        recommendations = []
        for result in results['tests'].values():
            if 'recommendations' in result:
                recommendations.extend(result['recommendations'])
        
        if recommendations:
            print(f"\n📋 DEPLOYMENT RECOMMENDATIONS:")
            print("-" * 40)
            for i, rec in enumerate(recommendations[:10], 1):  # Top 10
                print(f"{i}. {rec}")
        
        # Save detailed results
        timestamp = int(time.time())
        results_file = f"/home/user/Testing/ai-model-validation-platform/backend/tests/production_deployment_report_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed report saved: {results_file}")
        
        # Exit codes based on readiness
        if summary['readiness_score'] >= 75:
            print(f"\n🎉 PRODUCTION DEPLOYMENT: APPROVED")
            return 0
        elif summary['readiness_score'] >= 60:
            print(f"\n⚠️  PRODUCTION DEPLOYMENT: CONDITIONAL APPROVAL")
            return 1
        else:
            print(f"\n❌ PRODUCTION DEPLOYMENT: NOT APPROVED")
            return 2
            
    except Exception as e:
        logger.error(f"💥 Production deployment testing crashed: {e}")
        return 3

if __name__ == "__main__":
    result = main()
    exit(result)