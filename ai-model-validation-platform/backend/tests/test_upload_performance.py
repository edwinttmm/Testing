"""
Upload Performance and Load Testing
===================================

Performance-focused tests for video upload system including:
- Throughput testing
- Concurrent upload handling
- Memory usage monitoring
- Response time validation
- System resource utilization
"""

import pytest
import time
import threading
import tempfile
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
import statistics

import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from main import app
from models import Video, Project
from database import SessionLocal
from config import settings

class TestUploadPerformance:
    """Performance testing suite for video uploads"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def test_project(self, db_session):
        project = Project(
            name="Performance Test Project",
            description="Testing performance scenarios",
            camera_model="PerfCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project
    
    @pytest.fixture
    def performance_test_files(self):
        """Create test files of various sizes for performance testing"""
        files = {}
        
        # Small file (1MB)
        small_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        small_file.write(b'x' * (1024 * 1024))  # 1MB
        small_file.close()
        files['small'] = small_file.name
        
        # Medium file (10MB)
        medium_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        medium_file.write(b'x' * (10 * 1024 * 1024))  # 10MB
        medium_file.close()
        files['medium'] = medium_file.name
        
        # Large file (50MB - if within limits)
        if settings.max_file_size >= 50 * 1024 * 1024:
            large_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            large_file.write(b'x' * (50 * 1024 * 1024))  # 50MB
            large_file.close()
            files['large'] = large_file.name
        
        yield files
        
        # Cleanup
        for file_path in files.values():
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass

    # Test 1: Single Upload Performance
    def test_single_upload_performance(self, client, test_project, performance_test_files):
        """Test performance of single file uploads"""
        performance_results = {}
        
        for size_type, file_path in performance_test_files.items():
            with open(file_path, 'rb') as f:
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (f"perf_test_{size_type}.mp4", f, "video/mp4")}
                )
                
                end_time = time.time()
                end_memory = psutil.Process().memory_info().rss
                
                file_size = os.path.getsize(file_path)
                duration = end_time - start_time
                memory_delta = end_memory - start_memory
                throughput = file_size / duration if duration > 0 else 0
                
                performance_results[size_type] = {
                    'duration': duration,
                    'file_size': file_size,
                    'throughput_bps': throughput,
                    'memory_delta': memory_delta,
                    'status_code': response.status_code
                }
        
        # Validate performance requirements
        for size_type, results in performance_results.items():
            assert results['status_code'] == 200, f"Upload failed for {size_type} file"
            
            # Performance thresholds (adjust based on requirements)
            if size_type == 'small':
                assert results['duration'] < 2.0, f"Small file upload too slow: {results['duration']}s"
            elif size_type == 'medium':
                assert results['duration'] < 10.0, f"Medium file upload too slow: {results['duration']}s"
            elif size_type == 'large':
                assert results['duration'] < 30.0, f"Large file upload too slow: {results['duration']}s"
            
            # Memory usage should be reasonable (not loading entire file into memory)
            max_memory_multiple = 3  # Allow up to 3x file size in memory
            assert results['memory_delta'] < results['file_size'] * max_memory_multiple, \
                f"Memory usage too high for {size_type}: {results['memory_delta']} bytes"

    # Test 2: Concurrent Upload Performance
    def test_concurrent_upload_performance(self, client, test_project):
        """Test system performance under concurrent upload load"""
        concurrent_uploads = 10
        file_size = 1024 * 1024  # 1MB each
        
        def upload_file(upload_id):
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b'x' * file_size)
                temp_file.seek(0)
                
                start_time = time.time()
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (f"concurrent_{upload_id}.mp4", temp_file, "video/mp4")}
                )
                end_time = time.time()
                
                return {
                    'upload_id': upload_id,
                    'duration': end_time - start_time,
                    'status_code': response.status_code,
                    'file_size': file_size
                }
        
        # Execute concurrent uploads
        start_total = time.time()
        with ThreadPoolExecutor(max_workers=concurrent_uploads) as executor:
            futures = [executor.submit(upload_file, i) for i in range(concurrent_uploads)]
            results = [future.result() for future in as_completed(futures)]
        end_total = time.time()
        
        # Analyze results
        successful_uploads = [r for r in results if r['status_code'] == 200]
        durations = [r['duration'] for r in successful_uploads]
        total_duration = end_total - start_total
        
        # Performance assertions
        success_rate = len(successful_uploads) / concurrent_uploads
        assert success_rate >= 0.9, f"Success rate too low: {success_rate:.2%}"
        
        if durations:
            avg_duration = statistics.mean(durations)
            max_duration = max(durations)
            
            # Average upload time should be reasonable
            assert avg_duration < 5.0, f"Average upload time too high: {avg_duration}s"
            # No single upload should take excessively long
            assert max_duration < 10.0, f"Maximum upload time too high: {max_duration}s"
        
        # Total time should show benefits of concurrency
        sequential_estimate = len(successful_uploads) * statistics.mean(durations) if durations else 0
        if sequential_estimate > 0:
            concurrency_benefit = sequential_estimate / total_duration
            assert concurrency_benefit > 1.5, f"Insufficient concurrency benefit: {concurrency_benefit:.2f}x"

    # Test 3: Memory Usage Under Load
    def test_memory_usage_under_load(self, client, test_project):
        """Test memory usage during high-load upload scenarios"""
        initial_memory = psutil.Process().memory_info().rss
        upload_count = 20
        file_size = 512 * 1024  # 512KB each
        
        memory_samples = [initial_memory]
        
        def upload_and_sample_memory(upload_id):
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b'x' * file_size)
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (f"memory_test_{upload_id}.mp4", temp_file, "video/mp4")}
                )
                
                # Sample memory after upload
                current_memory = psutil.Process().memory_info().rss
                memory_samples.append(current_memory)
                
                return response.status_code
        
        # Execute uploads with memory monitoring
        status_codes = []
        for i in range(upload_count):
            status_code = upload_and_sample_memory(i)
            status_codes.append(status_code)
            
            # Sample memory periodically
            if i % 5 == 0:
                time.sleep(0.1)  # Brief pause to let GC work
        
        final_memory = psutil.Process().memory_info().rss
        memory_samples.append(final_memory)
        
        # Analyze memory usage
        max_memory = max(memory_samples)
        memory_growth = final_memory - initial_memory
        peak_growth = max_memory - initial_memory
        
        successful_uploads = sum(1 for code in status_codes if code == 200)
        
        # Memory assertions
        total_data_processed = successful_uploads * file_size
        
        # Memory growth should be reasonable (not accumulating all uploaded data)
        max_reasonable_growth = total_data_processed * 0.5  # Allow 50% overhead
        assert memory_growth < max_reasonable_growth, \
            f"Memory growth too high: {memory_growth / 1024 / 1024:.1f}MB"
        
        # Peak memory should not be excessive
        max_reasonable_peak = initial_memory + (file_size * 10)  # Allow 10 files worth at peak
        assert peak_growth < max_reasonable_peak, \
            f"Peak memory usage too high: {peak_growth / 1024 / 1024:.1f}MB"

    # Test 4: Throughput Testing
    def test_upload_throughput(self, client, test_project):
        """Test system throughput for video uploads"""
        test_duration = 30  # seconds
        file_size = 1024 * 1024  # 1MB files
        
        upload_count = 0
        successful_uploads = 0
        total_bytes = 0
        errors = []
        
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            try:
                with tempfile.NamedTemporaryFile() as temp_file:
                    temp_file.write(b'x' * file_size)
                    temp_file.seek(0)
                    
                    upload_start = time.time()
                    response = client.post(
                        f"/api/projects/{test_project.id}/videos",
                        files={"file": (f"throughput_{upload_count}.mp4", temp_file, "video/mp4")}
                    )
                    upload_end = time.time()
                    
                    upload_count += 1
                    
                    if response.status_code == 200:
                        successful_uploads += 1
                        total_bytes += file_size
                    else:
                        errors.append({
                            'upload_id': upload_count,
                            'status_code': response.status_code,
                            'duration': upload_end - upload_start
                        })
                        
            except Exception as e:
                errors.append({
                    'upload_id': upload_count,
                    'error': str(e)
                })
        
        end_time = time.time()
        actual_duration = end_time - start_time
        
        # Calculate metrics
        uploads_per_second = successful_uploads / actual_duration
        bytes_per_second = total_bytes / actual_duration
        success_rate = successful_uploads / upload_count if upload_count > 0 else 0
        
        # Performance assertions
        assert uploads_per_second >= 1.0, f"Throughput too low: {uploads_per_second:.2f} uploads/sec"
        assert bytes_per_second >= 1024 * 1024, f"Data throughput too low: {bytes_per_second / 1024 / 1024:.2f} MB/sec"
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"
        
        # Log results for analysis
        print(f"Throughput Test Results:")
        print(f"  Duration: {actual_duration:.2f}s")
        print(f"  Total uploads: {upload_count}")
        print(f"  Successful: {successful_uploads}")
        print(f"  Uploads/sec: {uploads_per_second:.2f}")
        print(f"  MB/sec: {bytes_per_second / 1024 / 1024:.2f}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Errors: {len(errors)}")

    # Test 5: Response Time Distribution
    def test_response_time_distribution(self, client, test_project):
        """Test distribution of response times under normal load"""
        sample_size = 50
        file_size = 1024 * 1024  # 1MB
        response_times = []
        
        for i in range(sample_size):
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b'x' * file_size)
                temp_file.seek(0)
                
                start_time = time.time()
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (f"response_time_{i}.mp4", temp_file, "video/mp4")}
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    response_times.append(end_time - start_time)
        
        if response_times:
            # Statistical analysis
            mean_time = statistics.mean(response_times)
            median_time = statistics.median(response_times)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            p95_time = sorted(response_times)[int(0.95 * len(response_times))]
            p99_time = sorted(response_times)[int(0.99 * len(response_times))]
            
            # Performance requirements
            assert mean_time < 2.0, f"Mean response time too high: {mean_time:.3f}s"
            assert median_time < 1.5, f"Median response time too high: {median_time:.3f}s"
            assert p95_time < 3.0, f"95th percentile too high: {p95_time:.3f}s"
            assert p99_time < 5.0, f"99th percentile too high: {p99_time:.3f}s"
            
            # Response time should be consistent (low variance)
            coefficient_of_variation = std_dev / mean_time if mean_time > 0 else 0
            assert coefficient_of_variation < 0.5, f"Response time too variable: CV={coefficient_of_variation:.3f}"

    # Test 6: Resource Utilization
    def test_resource_utilization(self, client, test_project):
        """Test CPU and memory utilization during upload operations"""
        # Baseline measurements
        baseline_cpu = psutil.cpu_percent(interval=1)
        baseline_memory = psutil.Process().memory_info().rss
        
        upload_count = 25
        file_size = 2 * 1024 * 1024  # 2MB files
        
        # Monitor resources during uploads
        cpu_samples = []
        memory_samples = []
        
        def monitor_resources():
            while len(cpu_samples) < upload_count * 2:  # Sample more frequently than uploads
                cpu_samples.append(psutil.cpu_percent())
                memory_samples.append(psutil.Process().memory_info().rss)
                time.sleep(0.2)
        
        # Start monitoring in background
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()
        
        # Perform uploads
        for i in range(upload_count):
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b'x' * file_size)
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (f"resource_{i}.mp4", temp_file, "video/mp4")}
                )
                
                assert response.status_code == 200
        
        # Wait for monitoring to complete
        monitor_thread.join(timeout=5)
        
        if cpu_samples and memory_samples:
            # Analyze resource usage
            max_cpu = max(cpu_samples)
            avg_cpu = statistics.mean(cpu_samples)
            max_memory = max(memory_samples)
            avg_memory = statistics.mean(memory_samples)
            
            memory_growth = max_memory - baseline_memory
            
            # Resource utilization should be reasonable
            assert max_cpu < 90.0, f"CPU usage too high: {max_cpu}%"
            assert avg_cpu < 50.0, f"Average CPU usage too high: {avg_cpu}%"
            
            # Memory growth should be bounded
            reasonable_memory_growth = upload_count * file_size * 0.5  # 50% overhead
            assert memory_growth < reasonable_memory_growth, \
                f"Memory growth too high: {memory_growth / 1024 / 1024:.1f}MB"

    # Test 7: Scalability Testing
    def test_scalability_characteristics(self, client, test_project):
        """Test how system scales with increasing load"""
        load_levels = [1, 5, 10, 15]  # Different concurrent upload levels
        results = {}
        
        for concurrent_uploads in load_levels:
            def upload_worker(worker_id):
                with tempfile.NamedTemporaryFile() as temp_file:
                    temp_file.write(b'x' * (512 * 1024))  # 512KB
                    temp_file.seek(0)
                    
                    start_time = time.time()
                    response = client.post(
                        f"/api/projects/{test_project.id}/videos",
                        files={"file": (f"scale_{concurrent_uploads}_{worker_id}.mp4", temp_file, "video/mp4")}
                    )
                    end_time = time.time()
                    
                    return {
                        'duration': end_time - start_time,
                        'status_code': response.status_code
                    }
            
            # Execute concurrent uploads for this load level
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=concurrent_uploads) as executor:
                futures = [executor.submit(upload_worker, i) for i in range(concurrent_uploads)]
                upload_results = [future.result() for future in as_completed(futures)]
            end_time = time.time()
            
            successful = [r for r in upload_results if r['status_code'] == 200]
            if successful:
                avg_response_time = statistics.mean([r['duration'] for r in successful])
                throughput = len(successful) / (end_time - start_time)
                success_rate = len(successful) / len(upload_results)
                
                results[concurrent_uploads] = {
                    'avg_response_time': avg_response_time,
                    'throughput': throughput,
                    'success_rate': success_rate
                }
        
        # Analyze scalability
        if len(results) >= 2:
            load_levels_sorted = sorted(results.keys())
            
            # Response time should not degrade too rapidly
            for i in range(1, len(load_levels_sorted)):
                current_load = load_levels_sorted[i]
                previous_load = load_levels_sorted[i-1]
                
                current_response = results[current_load]['avg_response_time']
                previous_response = results[previous_load]['avg_response_time']
                
                # Response time shouldn't increase by more than 3x for reasonable load increases
                response_time_ratio = current_response / previous_response if previous_response > 0 else 1
                load_ratio = current_load / previous_load
                
                if load_ratio <= 3:  # For reasonable load increases
                    assert response_time_ratio < 3.0, \
                        f"Response time degraded too much: {response_time_ratio:.2f}x for {load_ratio:.2f}x load"
            
            # Success rate should remain high
            for load_level, result in results.items():
                assert result['success_rate'] >= 0.9, \
                    f"Success rate too low at load {load_level}: {result['success_rate']:.2%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])