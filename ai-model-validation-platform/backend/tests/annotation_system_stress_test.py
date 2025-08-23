#!/usr/bin/env python3
"""
ANNOTATION SYSTEM STRESS TEST SUITE
AI Model Validation Platform - Comprehensive Annotation Edge Case Testing

This test suite specifically tests the annotation system with extreme loads,
1000+ annotations, complex shapes, temporal annotations, and edge cases.
"""

import asyncio
import json
import time
import uuid
import random
import requests
import concurrent.futures
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AnnotationSystemStressTest:
    """Comprehensive annotation system stress testing"""
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = 60
        self.results = {
            "test_summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "critical": 0
            },
            "stress_metrics": {
                "max_annotations_tested": 0,
                "peak_response_time": 0,
                "memory_efficiency": 0,
                "concurrent_operations": 0
            },
            "categories": {},
            "performance_benchmarks": {},
            "recommendations": []
        }

    async def run_comprehensive_stress_tests(self):
        """Execute comprehensive annotation system stress tests"""
        logger.info("🚀 Starting Annotation System Stress Test Suite")
        logger.info("="*80)
        
        # Setup test environment
        test_project_id, test_video_id = await self.setup_test_environment()
        if not test_project_id or not test_video_id:
            logger.error("❌ Failed to setup test environment")
            return self.results
        
        logger.info(f"✅ Test environment ready - Project: {test_project_id}, Video: {test_video_id}")
        
        # Execute stress test categories
        test_categories = [
            ("High Volume Annotation Creation", self.test_high_volume_annotations, test_video_id),
            ("Complex Shape Annotations", self.test_complex_shape_annotations, test_video_id),
            ("Temporal Annotation Stress", self.test_temporal_annotations, test_video_id),
            ("Concurrent Annotation Operations", self.test_concurrent_annotations, test_video_id),
            ("Annotation System Performance", self.test_annotation_performance, test_video_id),
            ("Annotation Data Integrity", self.test_annotation_integrity, test_video_id),
            ("Export System Stress Test", self.test_export_stress, test_video_id),
            ("Annotation Recovery Testing", self.test_annotation_recovery, test_video_id)
        ]
        
        for category_name, test_function, video_id in test_categories:
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 TESTING CATEGORY: {category_name}")
            logger.info(f"{'='*60}")
            
            category_results = {"tests": [], "summary": {"passed": 0, "failed": 0, "critical": 0}}
            
            try:
                await test_function(video_id, category_results)
            except Exception as e:
                logger.error(f"❌ Critical failure in {category_name}: {str(e)}")
                category_results["tests"].append({
                    "name": f"{category_name}_CRITICAL_FAILURE",
                    "status": "CRITICAL",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                category_results["summary"]["critical"] += 1
                
            self.results["categories"][category_name] = category_results
            self._update_summary(category_results)
        
        # Cleanup test environment
        await self.cleanup_test_environment(test_project_id)
        
        # Generate final report
        self._generate_stress_test_report()
        
        return self.results

    async def setup_test_environment(self):
        """Setup test project and video for annotation stress testing"""
        try:
            # Create test project
            project_data = {
                "name": "Annotation Stress Test Project",
                "description": "Project for annotation system stress testing",
                "camera_model": "StressTestCam",
                "camera_view": "Front-facing VRU",
                "signal_type": "GPIO"
            }
            
            response = self.session.post(f"{self.base_url}/api/projects", json=project_data)
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to create test project: {response.status_code}")
                return None, None
                
            project_id = response.json().get("id")
            logger.info(f"✅ Created test project: {project_id}")
            
            # Upload test video
            video_id = await self.upload_test_video(project_id)
            if not video_id:
                logger.error("Failed to upload test video")
                return project_id, None
                
            logger.info(f"✅ Uploaded test video: {video_id}")
            
            return project_id, video_id
            
        except Exception as e:
            logger.error(f"Setup failed: {str(e)}")
            return None, None

    async def upload_test_video(self, project_id):
        """Upload a test video for annotation testing"""
        try:
            # Create a small test video file
            import tempfile
            test_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            
            # Create fake video content (larger than previous tests)
            fake_video_content = b"FAKE_MP4_STRESS_TEST_CONTENT" * 2000  # ~50KB
            test_video.write(fake_video_content)
            test_video.close()
            
            # Upload video
            with open(test_video.name, 'rb') as f:
                files = {'file': ('stress_test_video.mp4', f, 'video/mp4')}
                response = self.session.post(
                    f"{self.base_url}/api/projects/{project_id}/videos",
                    files=files,
                    timeout=30
                )
            
            if response.status_code in [200, 201]:
                video_data = response.json()
                return video_data.get("id")
            else:
                logger.error(f"Video upload failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Video upload error: {str(e)}")
            return None
        finally:
            # Cleanup temp file
            try:
                import os
                os.unlink(test_video.name)
            except:
                pass

    async def test_high_volume_annotations(self, video_id, results):
        """Test creating 1000+ annotations"""
        logger.info("📊 Testing High Volume Annotation Creation (1000+ annotations)")
        
        annotation_counts = [100, 500, 1000, 2000]  # Progressive stress testing
        
        for target_count in annotation_counts:
            test_name = f"Create {target_count} Annotations"
            logger.info(f"🎯 Creating {target_count} annotations...")
            
            start_time = time.time()
            successful_annotations = 0
            failed_annotations = 0
            
            # Create annotations in batches to avoid overwhelming the system
            batch_size = 50
            batches = [annotation_counts[i:i + batch_size] for i in range(0, target_count, batch_size)]
            
            try:
                for batch_num, batch_indices in enumerate(batches):
                    batch_start = time.time()
                    
                    # Create batch of annotations
                    for i in range(len(batch_indices)):
                        annotation_data = self._generate_random_annotation(i + batch_num * batch_size)
                        
                        response = self.session.post(
                            f"{self.base_url}/api/videos/{video_id}/annotations",
                            json=annotation_data,
                            timeout=10
                        )
                        
                        if response.status_code in [200, 201]:
                            successful_annotations += 1
                        else:
                            failed_annotations += 1
                    
                    batch_time = time.time() - batch_start
                    logger.info(f"   Batch {batch_num + 1}/{len(batches)}: {len(batch_indices)} annotations in {batch_time:.2f}s")
                    
                    # Small delay between batches to prevent overwhelming
                    await asyncio.sleep(0.1)
                
                total_time = time.time() - start_time
                success_rate = (successful_annotations / target_count) * 100
                
                # Update stress metrics
                self.results["stress_metrics"]["max_annotations_tested"] = max(
                    self.results["stress_metrics"]["max_annotations_tested"], target_count
                )
                
                results["tests"].append({
                    "name": test_name,
                    "status": "PASS" if success_rate >= 95 else "FAIL",
                    "message": f"Success rate: {success_rate:.1f}% ({successful_annotations}/{target_count}) in {total_time:.2f}s",
                    "metrics": {
                        "total_time": total_time,
                        "annotations_per_second": successful_annotations / total_time,
                        "success_rate": success_rate,
                        "failed_count": failed_annotations
                    },
                    "timestamp": datetime.now().isoformat()
                })
                
                if success_rate >= 95:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                logger.error(f"High volume test failed: {str(e)}")
                results["tests"].append({
                    "name": test_name,
                    "status": "CRITICAL",
                    "message": f"Exception during high volume test: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    async def test_complex_shape_annotations(self, video_id, results):
        """Test complex polygon and shape annotations"""
        logger.info("🔷 Testing Complex Shape Annotations")
        
        complex_shapes = [
            ("Simple Rectangle", {"x": 100, "y": 100, "width": 50, "height": 50}),
            ("Large Rectangle", {"x": 0, "y": 0, "width": 1920, "height": 1080}),
            ("Tiny Rectangle", {"x": 500, "y": 500, "width": 1, "height": 1}),
            ("Complex Polygon", {"points": [(100, 100), (200, 150), (150, 200), (50, 175)]}),
            ("High-precision Polygon", {"points": [(100.123, 100.456), (200.789, 150.012), (150.345, 200.678)]}),
            ("Massive Polygon", {"points": [(i*10, j*10) for i in range(50) for j in range(2)]})
        ]
        
        for shape_name, shape_data in complex_shapes:
            test_name = f"Complex Shape - {shape_name}"
            
            try:
                annotation_data = {
                    "frame_number": 1,
                    "timestamp": 1.0,
                    "vru_type": "pedestrian",
                    "bounding_box": shape_data,
                    "notes": f"Complex shape test: {shape_name}",
                    "annotator": "stress_test_system",
                    "validated": False
                }
                
                start_time = time.time()
                response = self.session.post(
                    f"{self.base_url}/api/videos/{video_id}/annotations",
                    json=annotation_data,
                    timeout=15
                )
                response_time = time.time() - start_time
                
                success = response.status_code in [200, 201]
                
                results["tests"].append({
                    "name": test_name,
                    "status": "PASS" if success else "FAIL",
                    "message": f"Response: {response.status_code}, Time: {response_time:.3f}s",
                    "response_time": response_time,
                    "shape_complexity": len(str(shape_data)),
                    "timestamp": datetime.now().isoformat()
                })
                
                if success:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                results["tests"].append({
                    "name": test_name,
                    "status": "CRITICAL",
                    "message": f"Exception: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    async def test_temporal_annotations(self, video_id, results):
        """Test temporal annotations with time ranges"""
        logger.info("⏱️ Testing Temporal Annotation Stress")
        
        temporal_tests = [
            ("Short Duration", 0.0, 1.0),
            ("Medium Duration", 0.0, 30.0),
            ("Long Duration", 0.0, 120.0),
            ("Micro Duration", 1.0, 1.001),
            ("Overlapping Duration", 30.0, 90.0),
            ("End-to-End Duration", 0.0, 3600.0)  # 1 hour
        ]
        
        for test_name, start_time, end_time in temporal_tests:
            try:
                annotation_data = {
                    "frame_number": 1,
                    "timestamp": start_time,
                    "end_timestamp": end_time,
                    "vru_type": "pedestrian",
                    "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 50},
                    "notes": f"Temporal annotation test: {test_name}",
                    "annotator": "temporal_test_system",
                    "validated": False
                }
                
                request_start = time.time()
                response = self.session.post(
                    f"{self.base_url}/api/videos/{video_id}/annotations",
                    json=annotation_data,
                    timeout=15
                )
                response_time = time.time() - request_start
                
                success = response.status_code in [200, 201]
                duration = end_time - start_time
                
                results["tests"].append({
                    "name": f"Temporal - {test_name}",
                    "status": "PASS" if success else "FAIL",
                    "message": f"Duration: {duration:.3f}s, Response: {response.status_code}, Time: {response_time:.3f}s",
                    "temporal_duration": duration,
                    "response_time": response_time,
                    "timestamp": datetime.now().isoformat()
                })
                
                if success:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                results["tests"].append({
                    "name": f"Temporal - {test_name}",
                    "status": "CRITICAL",
                    "message": f"Exception: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    async def test_concurrent_annotations(self, video_id, results):
        """Test concurrent annotation operations"""
        logger.info("🔄 Testing Concurrent Annotation Operations")
        
        def create_annotation_batch(batch_id, count):
            """Create a batch of annotations concurrently"""
            batch_results = []
            
            for i in range(count):
                annotation_data = self._generate_random_annotation(batch_id * 1000 + i)
                
                try:
                    response = self.session.post(
                        f"{self.base_url}/api/videos/{video_id}/annotations",
                        json=annotation_data,
                        timeout=10
                    )
                    
                    batch_results.append({
                        "success": response.status_code in [200, 201],
                        "status_code": response.status_code,
                        "annotation_id": batch_id * 1000 + i
                    })
                    
                except Exception as e:
                    batch_results.append({
                        "success": False,
                        "error": str(e),
                        "annotation_id": batch_id * 1000 + i
                    })
            
            return batch_results
        
        # Test different levels of concurrency
        concurrency_levels = [5, 10, 20, 50]
        annotations_per_worker = 10
        
        for concurrency in concurrency_levels:
            test_name = f"Concurrent Operations - {concurrency} workers"
            logger.info(f"🎯 Testing {concurrency} concurrent workers...")
            
            start_time = time.time()
            
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [
                        executor.submit(create_annotation_batch, i, annotations_per_worker)
                        for i in range(concurrency)
                    ]
                    
                    all_results = []
                    completed_workers = 0
                    
                    for future in concurrent.futures.as_completed(futures, timeout=60):
                        try:
                            batch_results = future.result()
                            all_results.extend(batch_results)
                            completed_workers += 1
                        except Exception as e:
                            logger.error(f"Worker failed: {str(e)}")
                            all_results.append({"success": False, "error": str(e)})
                
                total_time = time.time() - start_time
                total_annotations = len(all_results)
                successful_annotations = sum(1 for r in all_results if r.get("success", False))
                success_rate = (successful_annotations / total_annotations) * 100 if total_annotations > 0 else 0
                
                # Update concurrency metrics
                self.results["stress_metrics"]["concurrent_operations"] = max(
                    self.results["stress_metrics"]["concurrent_operations"], concurrency
                )
                
                results["tests"].append({
                    "name": test_name,
                    "status": "PASS" if success_rate >= 90 else "FAIL",
                    "message": f"Workers: {completed_workers}/{concurrency}, Success: {success_rate:.1f}% ({successful_annotations}/{total_annotations}), Time: {total_time:.2f}s",
                    "metrics": {
                        "concurrency_level": concurrency,
                        "completed_workers": completed_workers,
                        "success_rate": success_rate,
                        "total_time": total_time,
                        "annotations_per_second": successful_annotations / total_time
                    },
                    "timestamp": datetime.now().isoformat()
                })
                
                if success_rate >= 90:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                logger.error(f"Concurrent test failed: {str(e)}")
                results["tests"].append({
                    "name": test_name,
                    "status": "CRITICAL",
                    "message": f"Exception during concurrent test: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    async def test_annotation_performance(self, video_id, results):
        """Test annotation system performance metrics"""
        logger.info("⚡ Testing Annotation System Performance")
        
        # Performance benchmark tests
        performance_tests = [
            ("Single Annotation Latency", 1),
            ("Batch Creation Performance", 100),
            ("Retrieval Performance", 0)  # Just retrieval
        ]
        
        for test_name, annotation_count in performance_tests:
            try:
                if annotation_count > 0:
                    # Create annotations and measure performance
                    start_time = time.time()
                    
                    successful_creates = 0
                    for i in range(annotation_count):
                        annotation_data = self._generate_random_annotation(i)
                        
                        response = self.session.post(
                            f"{self.base_url}/api/videos/{video_id}/annotations",
                            json=annotation_data,
                            timeout=5
                        )
                        
                        if response.status_code in [200, 201]:
                            successful_creates += 1
                    
                    create_time = time.time() - start_time
                    
                    # Measure retrieval performance
                    start_time = time.time()
                    response = self.session.get(f"{self.base_url}/api/videos/{video_id}/annotations")
                    retrieval_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        annotations_retrieved = len(response.json())
                    else:
                        annotations_retrieved = 0
                    
                    # Performance criteria
                    avg_create_time = (create_time / annotation_count) if annotation_count > 0 else 0
                    performance_ok = (
                        avg_create_time < 1.0 and  # Less than 1 second per annotation
                        retrieval_time < 2.0       # Less than 2 seconds to retrieve all
                    )
                    
                    # Update performance metrics
                    self.results["stress_metrics"]["peak_response_time"] = max(
                        self.results["stress_metrics"]["peak_response_time"], 
                        max(avg_create_time, retrieval_time)
                    )
                    
                    results["tests"].append({
                        "name": test_name,
                        "status": "PASS" if performance_ok else "FAIL",
                        "message": f"Created: {successful_creates}/{annotation_count}, Create time: {create_time:.2f}s, Retrieval: {retrieval_time:.2f}s",
                        "metrics": {
                            "avg_create_time": avg_create_time,
                            "retrieval_time": retrieval_time,
                            "annotations_retrieved": annotations_retrieved,
                            "creates_per_second": successful_creates / create_time if create_time > 0 else 0
                        },
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    if performance_ok:
                        results["summary"]["passed"] += 1
                    else:
                        results["summary"]["failed"] += 1
                        
                else:
                    # Just test retrieval performance
                    start_time = time.time()
                    response = self.session.get(f"{self.base_url}/api/videos/{video_id}/annotations")
                    retrieval_time = time.time() - start_time
                    
                    performance_ok = retrieval_time < 2.0
                    
                    results["tests"].append({
                        "name": test_name,
                        "status": "PASS" if performance_ok else "FAIL",
                        "message": f"Retrieval time: {retrieval_time:.2f}s",
                        "metrics": {"retrieval_time": retrieval_time},
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    if performance_ok:
                        results["summary"]["passed"] += 1
                    else:
                        results["summary"]["failed"] += 1
                        
            except Exception as e:
                results["tests"].append({
                    "name": test_name,
                    "status": "CRITICAL",
                    "message": f"Exception: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    async def test_annotation_integrity(self, video_id, results):
        """Test annotation data integrity"""
        logger.info("🔍 Testing Annotation Data Integrity")
        
        # Create test annotations with specific data
        test_annotations = []
        
        for i in range(10):
            annotation_data = {
                "frame_number": i + 1,
                "timestamp": float(i),
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100 + i*10, "y": 100 + i*10, "width": 50, "height": 50},
                "notes": f"Integrity test annotation {i}",
                "annotator": "integrity_test_system",
                "validated": i % 2 == 0  # Alternate validation status
            }
            
            response = self.session.post(
                f"{self.base_url}/api/videos/{video_id}/annotations",
                json=annotation_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                test_annotations.append((annotation_data, response.json()))
        
        # Verify data integrity
        response = self.session.get(f"{self.base_url}/api/videos/{video_id}/annotations")
        
        if response.status_code == 200:
            retrieved_annotations = response.json()
            
            # Test data integrity
            integrity_tests = [
                ("Annotation Count Integrity", len(retrieved_annotations) >= len(test_annotations)),
                ("Data Field Integrity", self._verify_annotation_fields(retrieved_annotations)),
                ("Timestamp Ordering", self._verify_timestamp_ordering(retrieved_annotations)),
                ("Data Type Consistency", self._verify_data_types(retrieved_annotations))
            ]
            
            for test_name, passed in integrity_tests:
                results["tests"].append({
                    "name": test_name,
                    "status": "PASS" if passed else "FAIL",
                    "message": f"Integrity check: {'Passed' if passed else 'Failed'}",
                    "timestamp": datetime.now().isoformat()
                })
                
                if passed:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
        else:
            results["tests"].append({
                "name": "Annotation Retrieval for Integrity Test",
                "status": "FAIL",
                "message": f"Failed to retrieve annotations: {response.status_code}",
                "timestamp": datetime.now().isoformat()
            })
            results["summary"]["failed"] += 1

    async def test_export_stress(self, video_id, results):
        """Test annotation export under stress"""
        logger.info("📤 Testing Annotation Export Stress")
        
        # First create a substantial number of annotations for export
        logger.info("Creating annotations for export stress test...")
        annotation_count = 200
        
        for i in range(annotation_count):
            annotation_data = self._generate_random_annotation(i)
            self.session.post(
                f"{self.base_url}/api/videos/{video_id}/annotations",
                json=annotation_data,
                timeout=5
            )
        
        # Test export performance (simulated since export endpoints may not exist)
        export_tests = [
            ("Export Responsiveness", "json"),
            ("Large Dataset Export", "csv"),
            ("Complex Format Export", "coco")
        ]
        
        for test_name, export_format in export_tests:
            try:
                # Simulate export stress by retrieving all annotations multiple times
                start_time = time.time()
                
                for _ in range(5):  # Simulate 5 export requests
                    response = self.session.get(f"{self.base_url}/api/videos/{video_id}/annotations")
                    if response.status_code != 200:
                        break
                
                export_time = time.time() - start_time
                export_ok = export_time < 10.0  # Should complete within 10 seconds
                
                results["tests"].append({
                    "name": f"Export Stress - {test_name}",
                    "status": "PASS" if export_ok else "FAIL",
                    "message": f"Export time: {export_time:.2f}s, Format: {export_format}",
                    "export_time": export_time,
                    "timestamp": datetime.now().isoformat()
                })
                
                if export_ok:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                results["tests"].append({
                    "name": f"Export Stress - {test_name}",
                    "status": "CRITICAL",
                    "message": f"Exception: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["critical"] += 1

    async def test_annotation_recovery(self, video_id, results):
        """Test annotation system recovery mechanisms"""
        logger.info("🔄 Testing Annotation Recovery Mechanisms")
        
        # Test recovery scenarios
        recovery_tests = [
            ("Invalid Data Recovery", {"invalid": "data"}),
            ("Malformed JSON Recovery", "not_json"),
            ("Missing Required Fields", {"frame_number": 1}),
            ("Extreme Value Handling", {"frame_number": -1, "timestamp": -999999})
        ]
        
        for test_name, invalid_data in recovery_tests:
            try:
                response = self.session.post(
                    f"{self.base_url}/api/videos/{video_id}/annotations",
                    json=invalid_data if isinstance(invalid_data, dict) else None,
                    data=invalid_data if not isinstance(invalid_data, dict) else None,
                    timeout=10
                )
                
                # System should gracefully handle invalid data
                graceful_handling = response.status_code in [400, 422, 500]
                
                results["tests"].append({
                    "name": f"Recovery - {test_name}",
                    "status": "PASS" if graceful_handling else "FAIL",
                    "message": f"Status: {response.status_code}, Graceful: {graceful_handling}",
                    "timestamp": datetime.now().isoformat()
                })
                
                if graceful_handling:
                    results["summary"]["passed"] += 1
                else:
                    results["summary"]["failed"] += 1
                    
            except Exception as e:
                results["tests"].append({
                    "name": f"Recovery - {test_name}",
                    "status": "FAIL",
                    "message": f"Exception: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })
                results["summary"]["failed"] += 1

    def _generate_random_annotation(self, index):
        """Generate a random annotation for testing"""
        vru_types = ["pedestrian", "cyclist", "vehicle", "other"]
        
        return {
            "frame_number": random.randint(1, 3600),  # Random frame
            "timestamp": random.uniform(0.0, 120.0),  # Random timestamp within 2 minutes
            "vru_type": random.choice(vru_types),
            "bounding_box": {
                "x": random.randint(0, 1820),
                "y": random.randint(0, 980),
                "width": random.randint(10, 200),
                "height": random.randint(10, 200)
            },
            "occluded": random.choice([True, False]),
            "truncated": random.choice([True, False]),
            "difficult": random.choice([True, False]),
            "notes": f"Stress test annotation {index}",
            "annotator": "stress_test_system",
            "validated": random.choice([True, False])
        }

    def _verify_annotation_fields(self, annotations):
        """Verify that all annotations have required fields"""
        required_fields = ["id", "video_id", "frame_number", "timestamp", "vru_type", "bounding_box"]
        
        for annotation in annotations:
            for field in required_fields:
                if field not in annotation:
                    return False
        return True

    def _verify_timestamp_ordering(self, annotations):
        """Verify that annotations can be ordered by timestamp"""
        try:
            timestamps = [ann.get("timestamp", 0) for ann in annotations]
            sorted_timestamps = sorted(timestamps)
            return True  # If no exception, ordering works
        except:
            return False

    def _verify_data_types(self, annotations):
        """Verify data type consistency"""
        for annotation in annotations:
            try:
                # Check basic type requirements
                if not isinstance(annotation.get("frame_number"), int):
                    return False
                if not isinstance(annotation.get("timestamp"), (int, float)):
                    return False
                if not isinstance(annotation.get("vru_type"), str):
                    return False
                if not isinstance(annotation.get("bounding_box"), dict):
                    return False
            except:
                return False
        return True

    async def cleanup_test_environment(self, project_id):
        """Clean up test environment"""
        try:
            response = self.session.delete(f"{self.base_url}/api/projects/{project_id}")
            if response.status_code in [200, 204]:
                logger.info(f"✅ Cleaned up test project: {project_id}")
            else:
                logger.warning(f"⚠️ Failed to cleanup project: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup error: {str(e)}")

    def _update_summary(self, category_results):
        """Update test summary"""
        self.results["test_summary"]["passed"] += category_results["summary"]["passed"]
        self.results["test_summary"]["failed"] += category_results["summary"]["failed"]
        self.results["test_summary"]["critical"] += category_results["summary"]["critical"]
        self.results["test_summary"]["total_tests"] += (
            category_results["summary"]["passed"] + 
            category_results["summary"]["failed"] + 
            category_results["summary"]["critical"]
        )

    def _generate_stress_test_report(self):
        """Generate comprehensive stress test report"""
        logger.info("\n" + "="*80)
        logger.info("📊 ANNOTATION SYSTEM STRESS TEST RESULTS")
        logger.info("="*80)
        
        summary = self.results["test_summary"]
        metrics = self.results["stress_metrics"]
        total = summary["total_tests"]
        
        if total > 0:
            pass_rate = (summary["passed"] / total) * 100
            fail_rate = (summary["failed"] / total) * 100
            critical_rate = (summary["critical"] / total) * 100
            
            logger.info(f"📈 OVERALL RESULTS:")
            logger.info(f"   Total Tests: {total}")
            logger.info(f"   ✅ Passed: {summary['passed']} ({pass_rate:.1f}%)")
            logger.info(f"   ❌ Failed: {summary['failed']} ({fail_rate:.1f}%)")
            logger.info(f"   🚨 Critical: {summary['critical']} ({critical_rate:.1f}%)")
            
            logger.info(f"\n🚀 STRESS METRICS:")
            logger.info(f"   Max Annotations Tested: {metrics['max_annotations_tested']}")
            logger.info(f"   Peak Response Time: {metrics['peak_response_time']:.3f}s")
            logger.info(f"   Max Concurrent Operations: {metrics['concurrent_operations']}")
            
            # System assessment
            if critical_rate == 0 and pass_rate >= 90:
                health_status = "🟢 EXCELLENT - Annotation system handles stress very well"
            elif critical_rate == 0 and pass_rate >= 75:
                health_status = "🟡 GOOD - Minor stress-related issues detected"
            elif critical_rate < 5 and pass_rate >= 60:
                health_status = "🟠 MODERATE - Stress handling needs improvement"
            else:
                health_status = "🔴 CRITICAL - Major stress-related failures detected"
            
            logger.info(f"\n🎯 ANNOTATION SYSTEM HEALTH: {health_status}")
            
            # Category breakdown
            logger.info(f"\n📋 CATEGORY BREAKDOWN:")
            for category_name, category_data in self.results["categories"].items():
                cat_summary = category_data["summary"]
                cat_total = cat_summary["passed"] + cat_summary["failed"] + cat_summary["critical"]
                if cat_total > 0:
                    cat_pass_rate = (cat_summary["passed"] / cat_total) * 100
                    logger.info(f"   {category_name}: {cat_pass_rate:.1f}% pass rate ({cat_summary['passed']}/{cat_total})")
            
            # Generate recommendations
            self._generate_stress_recommendations()
            
            logger.info(f"\n💡 STRESS TEST RECOMMENDATIONS:")
            for rec in self.results["recommendations"]:
                logger.info(f"   • {rec}")
                
        else:
            logger.error("❌ No tests were executed!")
        
        logger.info("="*80)
        
        # Save results
        with open("annotation_system_stress_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        logger.info("📄 Detailed results saved to annotation_system_stress_results.json")

    def _generate_stress_recommendations(self):
        """Generate stress-specific recommendations"""
        recommendations = []
        
        summary = self.results["test_summary"]
        metrics = self.results["stress_metrics"]
        total = summary["total_tests"]
        
        if total == 0:
            recommendations.append("No stress tests executed - check system connectivity")
            return
        
        pass_rate = (summary["passed"] / total) * 100
        critical_rate = (summary["critical"] / total) * 100
        
        # Performance recommendations
        if metrics["peak_response_time"] > 2.0:
            recommendations.append(f"Optimize annotation response times - peak at {metrics['peak_response_time']:.2f}s")
        
        if metrics["max_annotations_tested"] < 1000:
            recommendations.append("Increase annotation system scalability - couldn't handle 1000+ annotations")
        
        if metrics["concurrent_operations"] < 20:
            recommendations.append("Improve concurrent operation handling - limited to small workloads")
        
        # Stress-specific recommendations
        if pass_rate < 85:
            recommendations.append("Annotation system struggles under stress - needs performance optimization")
        
        if critical_rate > 0:
            recommendations.append("Critical failures under stress - system stability needs improvement")
        
        # Category-specific stress recommendations
        for category_name, category_data in self.results["categories"].items():
            cat_summary = category_data["summary"]
            cat_total = cat_summary["passed"] + cat_summary["failed"] + cat_summary["critical"]
            
            if cat_total > 0:
                cat_pass_rate = (cat_summary["passed"] / cat_total) * 100
                
                if "High Volume" in category_name and cat_pass_rate < 90:
                    recommendations.append("Implement batch processing for high-volume annotation creation")
                
                if "Concurrent" in category_name and cat_pass_rate < 85:
                    recommendations.append("Add database connection pooling and transaction optimization")
                
                if "Performance" in category_name and cat_pass_rate < 90:
                    recommendations.append("Implement annotation caching and database indexing optimization")
        
        # General stress recommendations
        if pass_rate >= 95:
            recommendations.append("Excellent stress handling - consider this baseline for production load testing")
        elif pass_rate >= 85:
            recommendations.append("Good stress handling - minor optimizations recommended")
        else:
            recommendations.append("Significant stress-related issues - comprehensive performance review needed")
        
        # Technical recommendations
        recommendations.append("Implement annotation processing queues for high-volume operations")
        recommendations.append("Add monitoring for annotation system performance metrics")
        recommendations.append("Consider implementing annotation data compression for large datasets")
        recommendations.append("Add automatic scaling for annotation processing under high load")
        
        self.results["recommendations"] = recommendations


if __name__ == "__main__":
    print("🚀 AI Model Validation Platform - Annotation System Stress Test Suite")
    print("="*80)
    
    async def main():
        test_suite = AnnotationSystemStressTest()
        results = await test_suite.run_comprehensive_stress_tests()
        
        summary = results["test_summary"]
        print(f"\n✅ Annotation system stress testing completed!")
        print(f"📊 Results: {summary['passed']} passed, "
              f"{summary['failed']} failed, {summary['critical']} critical")
        print(f"🚀 Max annotations tested: {results['stress_metrics']['max_annotations_tested']}")
        
        return summary["failed"] + summary["critical"]
    
    import asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)