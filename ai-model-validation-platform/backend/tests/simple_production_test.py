#!/usr/bin/env python3
"""
Simple Production Readiness Test for ML Inference Platform
========================================================

This script performs essential production readiness checks without complex
dependencies to validate deployment readiness.

Author: Production Validation Team
Version: 1.0.0
"""

import os
import sys
import time
import json
import requests
import subprocess
import psutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleProductionTester:
    """Simple production readiness testing"""
    
    def __init__(self):
        self.results = {
            'test_start_time': datetime.now(timezone.utc).isoformat(),
            'platform': 'ai-model-validation-platform',
            'tests': {},
            'summary': {},
            'production_readiness_score': 0
        }
        
    def test_file_structure(self) -> Dict[str, Any]:
        """Test project file structure"""
        test_result = {'name': 'Project File Structure', 'status': 'unknown'}
        
        try:
            backend_path = Path(__file__).parent.parent
            project_root = backend_path.parent
            
            # Check critical files
            critical_files = {
                'docker_compose': ['docker-compose.yml', 'docker-compose.unified.yml'],
                'environment': ['.env', '.env.production', '.env.unified'],
                'requirements': ['requirements.txt'],
                'models': ['yolo*.pt', 'yolo11*.pt'],
                'main_app': ['main.py', 'production_server.py'],
                'database': ['database.py', 'unified_database.py'],
                'ml_engine': ['src/ml_inference_engine.py', 'src/enhanced_ml_inference_engine.py']
            }
            
            found_files = {}
            missing_files = {}
            
            for category, file_patterns in critical_files.items():
                found_files[category] = []
                missing_files[category] = []
                
                for pattern in file_patterns:
                    if '*' in pattern:
                        # Handle glob patterns
                        matches = list(backend_path.glob(pattern)) + list(project_root.glob(pattern))
                        if matches:
                            found_files[category].extend([str(m) for m in matches])
                        else:
                            missing_files[category].append(pattern)
                    else:
                        # Handle exact file names
                        file_path = backend_path / pattern
                        if not file_path.exists():
                            file_path = project_root / pattern
                        
                        if file_path.exists():
                            found_files[category].append(str(file_path))
                        else:
                            missing_files[category].append(pattern)
            
            # Calculate completeness score
            total_categories = len(critical_files)
            complete_categories = sum(1 for files in found_files.values() if files)
            completeness_score = complete_categories / total_categories
            
            test_result.update({
                'status': 'passed' if completeness_score >= 0.8 else 'partial' if completeness_score >= 0.6 else 'failed',
                'found_files': found_files,
                'missing_files': missing_files,
                'completeness_score': completeness_score,
                'complete_categories': complete_categories,
                'total_categories': total_categories
            })
            
            logger.info(f"✅ File structure: {complete_categories}/{total_categories} categories complete")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ File structure check failed: {e}")
            
        return test_result
    
    def test_ml_models_availability(self) -> Dict[str, Any]:
        """Test ML models availability and functionality"""
        test_result = {'name': 'ML Models Availability', 'status': 'unknown'}
        
        try:
            backend_path = Path(__file__).parent.parent
            
            # Find YOLO models
            model_files = []
            for pattern in ['*.pt', 'yolo*.pt']:
                model_files.extend(backend_path.glob(pattern))
            
            model_info = []
            for model_file in model_files:
                size_mb = model_file.stat().st_size / (1024**2)
                model_info.append({
                    'name': model_file.name,
                    'path': str(model_file),
                    'size_mb': round(size_mb, 1)
                })
            
            # Test model loading if possible
            model_test_success = False
            inference_time = None
            
            try:
                import torch
                from ultralytics import YOLO
                import numpy as np
                
                if model_info:
                    # Use smallest model for testing
                    test_model = min(model_info, key=lambda x: x['size_mb'])
                    model = YOLO(test_model['path'])
                    
                    # Quick inference test
                    test_image = np.random.randint(0, 255, (416, 416, 3), dtype=np.uint8)
                    start_time = time.time()
                    results = model(test_image, verbose=False)
                    inference_time = time.time() - start_time
                    
                    model_test_success = True
                    
            except ImportError:
                logger.warning("PyTorch/Ultralytics not available for model testing")
            except Exception as e:
                logger.warning(f"Model inference test failed: {e}")
            
            test_result.update({
                'status': 'passed' if model_info and model_test_success else 'partial' if model_info else 'failed',
                'model_files': model_info,
                'model_count': len(model_info),
                'inference_test_success': model_test_success,
                'inference_time': inference_time
            })
            
            if model_info:
                total_size = sum(m['size_mb'] for m in model_info)
                logger.info(f"✅ Found {len(model_info)} ML models ({total_size:.1f}MB total)")
                if model_test_success:
                    logger.info(f"✅ Model inference test successful ({inference_time:.3f}s)")
            else:
                logger.error("❌ No ML model files found")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ ML models check failed: {e}")
            
        return test_result
    
    def test_database_functionality(self) -> Dict[str, Any]:
        """Test database functionality"""
        test_result = {'name': 'Database Functionality', 'status': 'unknown'}
        
        try:
            backend_path = Path(__file__).parent.parent
            sys.path.insert(0, str(backend_path))
            
            database_available = False
            connection_healthy = False
            
            # Try unified database first
            try:
                from unified_database import get_database_manager
                
                db_manager = get_database_manager()
                health = db_manager.test_connection()
                
                database_available = True
                connection_healthy = health['status'] == 'healthy'
                
                test_result.update({
                    'database_type': 'unified',
                    'connection_health': health
                })
                
            except ImportError:
                # Fallback to basic database
                try:
                    from database import get_database_health
                    
                    health = get_database_health()
                    database_available = True
                    connection_healthy = health['status'] == 'healthy'
                    
                    test_result.update({
                        'database_type': 'basic',
                        'connection_health': health
                    })
                    
                except ImportError:
                    logger.warning("No database modules available")
                except Exception as e:
                    logger.warning(f"Database connection test failed: {e}")
            
            test_result.update({
                'status': 'passed' if connection_healthy else 'partial' if database_available else 'failed',
                'database_available': database_available,
                'connection_healthy': connection_healthy
            })
            
            if connection_healthy:
                logger.info("✅ Database connection healthy")
            elif database_available:
                logger.warning("⚠️  Database available but connection issues")
            else:
                logger.error("❌ Database not available")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Database functionality check failed: {e}")
            
        return test_result
    
    def test_server_functionality(self) -> Dict[str, Any]:
        """Test server functionality"""
        test_result = {'name': 'Server Functionality', 'status': 'unknown'}
        
        try:
            servers_to_test = [
                {'name': 'Development Server', 'url': 'http://localhost:8000'},
                {'name': 'Production Server', 'url': 'http://localhost:80'}
            ]
            
            server_results = {}
            accessible_count = 0
            
            for server in servers_to_test:
                server_result = {
                    'accessible': False,
                    'response_time': None,
                    'status_code': None
                }
                
                try:
                    start_time = time.time()
                    response = requests.get(f"{server['url']}/health", timeout=10)
                    response_time = time.time() - start_time
                    
                    server_result.update({
                        'accessible': response.status_code == 200,
                        'response_time': response_time,
                        'status_code': response.status_code
                    })
                    
                    if response.status_code == 200:
                        accessible_count += 1
                        try:
                            server_result['health_data'] = response.json()
                        except:
                            server_result['health_data'] = response.text
                    
                except requests.exceptions.RequestException as e:
                    server_result['error'] = str(e)
                
                server_results[server['name']] = server_result
            
            test_result.update({
                'status': 'passed' if accessible_count > 0 else 'failed',
                'servers_tested': len(servers_to_test),
                'accessible_servers': accessible_count,
                'server_results': server_results
            })
            
            if accessible_count > 0:
                logger.info(f"✅ {accessible_count}/{len(servers_to_test)} servers accessible")
            else:
                logger.error("❌ No servers accessible")
                
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Server functionality check failed: {e}")
            
        return test_result
    
    def test_system_resources(self) -> Dict[str, Any]:
        """Test system resource requirements"""
        test_result = {'name': 'System Resources', 'status': 'unknown'}
        
        try:
            # Get system information
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage('/')
            cpu_count = psutil.cpu_count()
            
            resources = {
                'memory_gb': round(memory_info.total / (1024**3), 1),
                'memory_available_gb': round(memory_info.available / (1024**3), 1),
                'memory_usage_percent': memory_info.percent,
                'disk_total_gb': round(disk_info.total / (1024**3), 1),
                'disk_free_gb': round(disk_info.free / (1024**3), 1),
                'disk_usage_percent': round((disk_info.used / disk_info.total) * 100, 1),
                'cpu_count': cpu_count
            }
            
            # Evaluate resource adequacy
            issues = []
            warnings = []
            
            # Memory checks
            if resources['memory_gb'] < 2:
                issues.append("Insufficient RAM: At least 2GB required for basic operation")
            elif resources['memory_gb'] < 4:
                warnings.append("Low RAM: 4GB+ recommended for optimal ML performance")
            
            # Disk checks
            if resources['disk_free_gb'] < 2:
                issues.append("Insufficient disk space: At least 2GB free space required")
            elif resources['disk_free_gb'] < 5:
                warnings.append("Low disk space: 5GB+ recommended for logs and temporary files")
            
            # CPU checks
            if resources['cpu_count'] < 2:
                warnings.append("Single CPU: Multi-core recommended for better performance")
            
            # Overall assessment
            if issues:
                status = 'failed'
            elif warnings:
                status = 'partial'
            else:
                status = 'passed'
            
            test_result.update({
                'status': status,
                'resources': resources,
                'issues': issues,
                'warnings': warnings
            })
            
            logger.info(f"✅ System resources: {resources['memory_gb']}GB RAM, {cpu_count} CPUs, {resources['disk_free_gb']}GB free")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ System resources check failed: {e}")
            
        return test_result
    
    def test_dependencies_availability(self) -> Dict[str, Any]:
        """Test critical dependencies availability"""
        test_result = {'name': 'Dependencies Availability', 'status': 'unknown'}
        
        try:
            dependencies = {
                'core': ['numpy', 'opencv-python', 'fastapi', 'uvicorn'],
                'ml': ['torch', 'ultralytics'],
                'database': ['sqlalchemy', 'sqlite3'],
                'web': ['requests', 'aiofiles']
            }
            
            dependency_status = {}
            total_deps = 0
            available_deps = 0
            
            for category, deps in dependencies.items():
                category_results = {}
                for dep in deps:
                    total_deps += 1
                    try:
                        if dep == 'sqlite3':
                            import sqlite3
                        elif dep == 'opencv-python':
                            import cv2
                        else:
                            __import__(dep)
                        
                        category_results[dep] = True
                        available_deps += 1
                    except ImportError:
                        category_results[dep] = False
                
                dependency_status[category] = category_results
            
            availability_score = available_deps / total_deps if total_deps > 0 else 0
            
            test_result.update({
                'status': 'passed' if availability_score >= 0.9 else 'partial' if availability_score >= 0.7 else 'failed',
                'dependency_status': dependency_status,
                'availability_score': availability_score,
                'available_dependencies': available_deps,
                'total_dependencies': total_deps
            })
            
            logger.info(f"✅ Dependencies: {available_deps}/{total_deps} available ({availability_score:.1%})")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Dependencies check failed: {e}")
            
        return test_result
    
    def test_configuration_files(self) -> Dict[str, Any]:
        """Test configuration files"""
        test_result = {'name': 'Configuration Files', 'status': 'unknown'}
        
        try:
            backend_path = Path(__file__).parent.parent
            project_root = backend_path.parent
            
            config_files = {
                'environment': ['.env', '.env.production', '.env.unified'],
                'docker': ['docker-compose.yml', 'docker-compose.unified.yml'],
                'python': ['requirements.txt', 'requirements-ml.txt'],
                'application': ['config.py', 'main.py', 'production_server.py']
            }
            
            found_configs = {}
            missing_configs = {}
            config_score = 0
            
            for category, files in config_files.items():
                found_configs[category] = []
                missing_configs[category] = []
                
                for config_file in files:
                    file_path = project_root / config_file
                    if not file_path.exists():
                        file_path = backend_path / config_file
                    
                    if file_path.exists():
                        found_configs[category].append(str(file_path))
                        config_score += 1
                    else:
                        missing_configs[category].append(config_file)
            
            total_configs = sum(len(files) for files in config_files.values())
            completeness = config_score / total_configs if total_configs > 0 else 0
            
            test_result.update({
                'status': 'passed' if completeness >= 0.7 else 'partial' if completeness >= 0.5 else 'failed',
                'found_configs': found_configs,
                'missing_configs': missing_configs,
                'config_score': config_score,
                'total_configs': total_configs,
                'completeness': completeness
            })
            
            logger.info(f"✅ Configuration: {config_score}/{total_configs} files found ({completeness:.1%})")
            
        except Exception as e:
            test_result.update({
                'status': 'failed',
                'error': str(e)
            })
            logger.error(f"❌ Configuration files check failed: {e}")
            
        return test_result
    
    def run_production_tests(self) -> Dict[str, Any]:
        """Run all production readiness tests"""
        logger.info("🚀 Simple Production Readiness Assessment")
        logger.info("=" * 60)
        
        test_functions = [
            self.test_file_structure,
            self.test_ml_models_availability,
            self.test_database_functionality,
            self.test_server_functionality,
            self.test_system_resources,
            self.test_dependencies_availability,
            self.test_configuration_files
        ]
        
        for test_func in test_functions:
            test_name = test_func.__name__.replace('test_', '').replace('_', ' ').title()
            logger.info(f"\n🔍 Testing: {test_name}")
            
            try:
                result = test_func()
                self.results['tests'][test_func.__name__] = result
                
                status_emoji = {
                    'passed': '✅',
                    'partial': '⚠️',
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
        self._calculate_readiness_score()
        
        # Generate summary
        self._generate_summary()
        
        self.results['test_end_time'] = datetime.now(timezone.utc).isoformat()
        
        return self.results
    
    def _calculate_readiness_score(self):
        """Calculate overall readiness score"""
        weights = {
            'test_file_structure': 0.15,
            'test_ml_models_availability': 0.25,
            'test_database_functionality': 0.20,
            'test_server_functionality': 0.20,
            'test_system_resources': 0.10,
            'test_dependencies_availability': 0.05,
            'test_configuration_files': 0.05
        }
        
        total_score = 0
        total_weight = 0
        
        for test_name, result in self.results['tests'].items():
            if test_name in weights:
                weight = weights[test_name]
                total_weight += weight
                
                score = {
                    'passed': 1.0,
                    'partial': 0.6,
                    'failed': 0.0,
                    'skipped': 0.3,
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
        
        readiness_score = self.results['production_readiness_score']
        
        if readiness_score >= 85:
            readiness_level = "EXCELLENT"
            recommendation = "🎉 Platform is production-ready! Deploy with confidence."
        elif readiness_score >= 70:
            readiness_level = "GOOD"
            recommendation = "👍 Platform is ready for production with minor optimizations."
        elif readiness_score >= 55:
            readiness_level = "ACCEPTABLE"
            recommendation = "⚠️  Platform can be deployed but should address issues soon."
        elif readiness_score >= 40:
            readiness_level = "NEEDS_WORK"
            recommendation = "🔧 Address critical issues before production deployment."
        else:
            readiness_level = "NOT_READY"
            recommendation = "❌ Platform requires significant work before production."
        
        self.results['summary'] = {
            'total_tests': len(self.results['tests']),
            'status_counts': status_counts,
            'readiness_score': readiness_score,
            'readiness_level': readiness_level,
            'recommendation': recommendation
        }

def main():
    """Main production testing function"""
    tester = SimpleProductionTester()
    
    try:
        results = tester.run_production_tests()
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 PRODUCTION READINESS ASSESSMENT")
        print("=" * 70)
        
        summary = results['summary']
        print(f"Total Tests: {summary['total_tests']}")
        
        for status, count in summary['status_counts'].items():
            emoji = {
                'passed': '✅',
                'partial': '⚠️',
                'failed': '❌',
                'skipped': '⏭️',
                'crashed': '💥'
            }.get(status, '❓')
            print(f"{emoji} {status.title()}: {count}")
        
        print(f"\n🎯 Production Readiness Score: {summary['readiness_score']}%")
        print(f"📈 Readiness Level: {summary['readiness_level']}")
        print(f"\n💡 {summary['recommendation']}")
        
        # Print detailed results
        print(f"\n📋 DETAILED TEST RESULTS")
        print("-" * 70)
        for test_name, result in results['tests'].items():
            status = result['status']
            emoji = {
                'passed': '✅',
                'partial': '⚠️',
                'failed': '❌',
                'skipped': '⏭️',
                'crashed': '💥'
            }.get(status, '❓')
            
            test_display = result['name']
            print(f"{emoji} {test_display}: {status.upper()}")
            
            # Show key metrics
            if status == 'passed' and 'score' in str(result):
                for key, value in result.items():
                    if 'score' in key or 'count' in key:
                        print(f"   → {key}: {value}")
        
        # Save detailed results
        timestamp = int(time.time())
        results_file = f"/home/user/Testing/ai-model-validation-platform/backend/tests/simple_production_report_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Detailed report saved: {results_file}")
        
        # Exit code based on readiness
        if summary['readiness_score'] >= 70:
            print(f"\n🎉 PRODUCTION DEPLOYMENT: APPROVED")
            return 0
        elif summary['readiness_score'] >= 55:
            print(f"\n⚠️  PRODUCTION DEPLOYMENT: CONDITIONAL APPROVAL")
            return 1
        else:
            print(f"\n❌ PRODUCTION DEPLOYMENT: REQUIRES IMPROVEMENT")
            return 2
            
    except Exception as e:
        logger.error(f"💥 Production testing crashed: {e}")
        return 3

if __name__ == "__main__":
    result = main()
    exit(result)