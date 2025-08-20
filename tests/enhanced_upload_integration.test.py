"""
Enhanced Upload Integration Tests

Tests for large file upload functionality including:
- Chunked uploads for files up to 1GB
- Progress tracking and timeout handling
- Memory optimization verification
- Retry mechanisms
- Error handling and recovery
"""

import os
import tempfile
import asyncio
import hashlib
import time
from typing import List, Dict, Any
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import requests

# Test configuration
class UploadTestConfig:
    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB
    CHUNK_SIZE = 64 * 1024  # 64KB
    TEST_API_URL = "http://localhost:8000"
    TIMEOUT_SECONDS = 300  # 5 minutes

class TestFile:
    """Helper class to create test files"""
    
    @staticmethod
    def create_test_file(size_mb: int, filename: str = None) -> str:
        """Create a test file with specified size"""
        if filename is None:
            filename = f"test_video_{size_mb}mb.mp4"
        
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'wb') as f:
            # Write in chunks to avoid memory issues
            chunk_size = 1024 * 1024  # 1MB chunks
            remaining = size_mb * 1024 * 1024
            
            while remaining > 0:
                write_size = min(chunk_size, remaining)
                # Write pseudo-random data for realistic testing
                data = bytes([i % 256 for i in range(write_size)])
                f.write(data)
                remaining -= write_size
        
        return file_path
    
    @staticmethod
    def calculate_file_checksum(file_path: str) -> str:
        """Calculate MD5 checksum of file"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            while chunk := f.read(64 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    @staticmethod
    def cleanup_file(file_path: str):
        """Clean up test file"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass

class UploadProgressTracker:
    """Track upload progress for testing"""
    
    def __init__(self):
        self.progress_updates: List[Dict[str, Any]] = []
        self.start_time = time.time()
    
    def update_progress(self, progress: Dict[str, Any]):
        """Record progress update"""
        progress_with_timestamp = {
            **progress,
            'timestamp': time.time(),
            'elapsed_time': time.time() - self.start_time
        }
        self.progress_updates.append(progress_with_timestamp)
    
    def get_final_progress(self) -> Dict[str, Any]:
        """Get final progress state"""
        return self.progress_updates[-1] if self.progress_updates else {}
    
    def verify_progress_consistency(self) -> bool:
        """Verify progress updates are consistent"""
        if len(self.progress_updates) < 2:
            return True
        
        for i in range(1, len(self.progress_updates)):
            current = self.progress_updates[i]
            previous = self.progress_updates[i-1]
            
            # Progress should be monotonically increasing
            if current['percentage'] < previous['percentage']:
                return False
                
            # Bytes uploaded should be monotonically increasing
            if current['bytes_uploaded'] < previous['bytes_uploaded']:
                return False
        
        return True

class TestLargeFileUploads:
    """Test suite for large file uploads"""
    
    def setup_method(self):
        """Setup for each test"""
        self.test_files = []
        self.progress_tracker = UploadProgressTracker()
    
    def teardown_method(self):
        """Cleanup after each test"""
        for file_path in self.test_files:
            TestFile.cleanup_file(file_path)
    
    def test_79mb_video_upload_traditional(self):
        """Test uploading a 79MB video file using traditional upload"""
        # Create 79MB test file (the original failing case)
        file_path = TestFile.create_test_file(79, "test_79mb_video.mp4")
        self.test_files.append(file_path)
        
        # Verify file was created correctly
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) == 79 * 1024 * 1024
        
        # Calculate expected checksum
        expected_checksum = TestFile.calculate_file_checksum(file_path)
        
        # Test traditional upload
        with TestClient(app) as client:
            with open(file_path, 'rb') as f:
                files = {'file': ('test_79mb_video.mp4', f, 'video/mp4')}
                
                response = client.post(
                    '/api/v2/videos/upload/traditional',
                    files=files,
                    timeout=300  # 5 minute timeout
                )
        
        # Verify successful upload
        assert response.status_code == 200
        result = response.json()
        
        assert result['status'] == 'completed'
        assert result['file_size'] == 79 * 1024 * 1024
        assert 'checksum' in result
        assert result['filename'] == 'test_79mb_video.mp4'
        
        # Verify uploaded file integrity
        uploaded_file_path = result['file_path']
        assert os.path.exists(uploaded_file_path)
        uploaded_checksum = TestFile.calculate_file_checksum(uploaded_file_path)
        assert uploaded_checksum == expected_checksum
    
    def test_200mb_video_chunked_upload(self):
        """Test uploading a 200MB video file using chunked upload"""
        # Create 200MB test file
        file_path = TestFile.create_test_file(200, "test_200mb_video.mp4")
        self.test_files.append(file_path)
        
        file_size = os.path.getsize(file_path)
        expected_checksum = TestFile.calculate_file_checksum(file_path)
        
        with TestClient(app) as client:
            # Step 1: Initialize chunked upload
            init_response = client.post(
                '/api/v2/videos/upload/init',
                json={
                    'filename': 'test_200mb_video.mp4',
                    'file_size': file_size,
                    'chunk_size': UploadTestConfig.CHUNK_SIZE
                }
            )
            
            assert init_response.status_code == 200
            init_data = init_response.json()
            
            upload_session_id = init_data['upload_session_id']
            total_chunks = init_data['total_chunks']
            chunk_size = init_data['chunk_size']
            
            # Step 2: Upload chunks
            with open(file_path, 'rb') as f:
                for chunk_index in range(total_chunks):
                    # Read chunk data
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    # Calculate chunk checksum
                    chunk_checksum = hashlib.md5(chunk_data).hexdigest()
                    
                    # Upload chunk
                    files = {'chunk': ('chunk', chunk_data, 'application/octet-stream')}
                    data = {
                        'chunk_index': chunk_index,
                        'checksum': chunk_checksum
                    }
                    
                    chunk_response = client.post(
                        f'/api/v2/videos/upload/chunk/{upload_session_id}',
                        files=files,
                        data=data
                    )
                    
                    assert chunk_response.status_code == 200
                    chunk_result = chunk_response.json()
                    
                    # Track progress
                    if 'progress' in chunk_result:
                        self.progress_tracker.update_progress(chunk_result['progress'])
                    
                    # Verify chunk upload status
                    if chunk_index < total_chunks - 1:
                        assert chunk_result['status'] == 'chunk_uploaded'
                        assert chunk_result['chunk_index'] == chunk_index
                    else:
                        # Last chunk should complete the upload
                        assert chunk_result['status'] == 'upload_completed'
        
        # Verify progress tracking worked correctly
        assert len(self.progress_tracker.progress_updates) > 0
        assert self.progress_tracker.verify_progress_consistency()
        
        final_progress = self.progress_tracker.get_final_progress()
        assert final_progress['percentage'] == 100.0
        assert final_progress['bytes_uploaded'] == file_size
    
    def test_500mb_video_chunked_upload_with_retry(self):
        """Test uploading a 500MB video with simulated network failures"""
        # Create 500MB test file
        file_path = TestFile.create_test_file(500, "test_500mb_video.mp4")
        self.test_files.append(file_path)
        
        file_size = os.path.getsize(file_path)
        
        with TestClient(app) as client:
            # Initialize chunked upload
            init_response = client.post(
                '/api/v2/videos/upload/init',
                json={
                    'filename': 'test_500mb_video.mp4',
                    'file_size': file_size
                }
            )
            
            assert init_response.status_code == 200
            init_data = init_response.json()
            upload_session_id = init_data['upload_session_id']
            total_chunks = init_data['total_chunks']
            chunk_size = init_data['chunk_size']
            
            # Track failed chunks for retry testing
            failed_chunks = set()
            max_failures_per_chunk = 2
            
            with open(file_path, 'rb') as f:
                chunk_index = 0
                while chunk_index < total_chunks:
                    # Read chunk data
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    # Simulate network failure for some chunks
                    should_fail = (
                        chunk_index % 10 == 0 and  # Fail every 10th chunk
                        failed_chunks.count(chunk_index) < max_failures_per_chunk
                    )
                    
                    if should_fail:
                        failed_chunks.add(chunk_index)
                        # Simulate timeout or network error
                        time.sleep(0.1)  # Brief delay to simulate network issue
                        continue
                    
                    # Calculate chunk checksum
                    chunk_checksum = hashlib.md5(chunk_data).hexdigest()
                    
                    # Upload chunk
                    files = {'chunk': ('chunk', chunk_data, 'application/octet-stream')}
                    data = {
                        'chunk_index': chunk_index,
                        'checksum': chunk_checksum
                    }
                    
                    chunk_response = client.post(
                        f'/api/v2/videos/upload/chunk/{upload_session_id}',
                        files=files,
                        data=data
                    )
                    
                    if chunk_response.status_code == 200:
                        chunk_index += 1
                    else:
                        # Handle retry logic
                        failed_chunks.add(chunk_index)
                        if failed_chunks.count(chunk_index) >= max_failures_per_chunk:
                            chunk_index += 1  # Give up on this chunk
        
        # Verify that we handled retries correctly
        assert len(failed_chunks) > 0, "Expected some simulated failures for retry testing"
    
    def test_file_size_limit_enforcement(self):
        """Test that file size limits are properly enforced"""
        # Create file larger than allowed limit (simulate 2GB file metadata)
        oversized_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        
        with TestClient(app) as client:
            response = client.post(
                '/api/v2/videos/upload/init',
                json={
                    'filename': 'test_oversized_video.mp4',
                    'file_size': oversized_file_size
                }
            )
            
            assert response.status_code == 413  # Request Entity Too Large
            error_data = response.json()
            assert 'File too large' in error_data['message']
    
    def test_invalid_file_type_rejection(self):
        """Test that invalid file types are rejected"""
        # Create a text file instead of video
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        temp_file.write(b'This is not a video file')
        temp_file.close()
        self.test_files.append(temp_file.name)
        
        with TestClient(app) as client:
            with open(temp_file.name, 'rb') as f:
                files = {'file': ('test.txt', f, 'text/plain')}
                
                response = client.post(
                    '/api/v2/videos/upload/traditional',
                    files=files
                )
            
            assert response.status_code == 400
            error_data = response.json()
            assert 'Unsupported file type' in error_data['message'] or 'not allowed' in error_data['message']
    
    def test_memory_usage_during_large_upload(self):
        """Test that memory usage remains reasonable during large file uploads"""
        import psutil
        import threading
        
        # Create 100MB test file
        file_path = TestFile.create_test_file(100, "test_memory_usage.mp4")
        self.test_files.append(file_path)
        
        # Monitor memory usage during upload
        memory_samples = []
        monitoring = True
        
        def memory_monitor():
            process = psutil.Process()
            while monitoring:
                memory_mb = process.memory_info().rss / 1024 / 1024  # MB
                memory_samples.append(memory_mb)
                time.sleep(0.1)  # Sample every 100ms
        
        monitor_thread = threading.Thread(target=memory_monitor)
        monitor_thread.start()
        
        try:
            with TestClient(app) as client:
                with open(file_path, 'rb') as f:
                    files = {'file': ('test_memory_usage.mp4', f, 'video/mp4')}
                    
                    response = client.post(
                        '/api/v2/videos/upload/traditional',
                        files=files,
                        timeout=300
                    )
                
                assert response.status_code == 200
        
        finally:
            monitoring = False
            monitor_thread.join()
        
        # Verify memory usage didn't spike excessively
        if memory_samples:
            max_memory_mb = max(memory_samples)
            avg_memory_mb = sum(memory_samples) / len(memory_samples)
            
            # Memory usage should not exceed 200MB for 100MB file
            # (allowing for some overhead but ensuring chunked processing works)
            assert max_memory_mb < 200, f"Memory usage too high: {max_memory_mb}MB"
            
            print(f"Memory usage - Max: {max_memory_mb:.1f}MB, Avg: {avg_memory_mb:.1f}MB")
    
    def test_upload_cancellation(self):
        """Test that uploads can be cancelled properly"""
        # Create 50MB test file
        file_path = TestFile.create_test_file(50, "test_cancellation.mp4")
        self.test_files.append(file_path)
        
        file_size = os.path.getsize(file_path)
        
        with TestClient(app) as client:
            # Initialize chunked upload
            init_response = client.post(
                '/api/v2/videos/upload/init',
                json={
                    'filename': 'test_cancellation.mp4',
                    'file_size': file_size
                }
            )
            
            assert init_response.status_code == 200
            init_data = init_response.json()
            upload_session_id = init_data['upload_session_id']
            
            # Upload a few chunks
            with open(file_path, 'rb') as f:
                for chunk_index in range(min(5, init_data['total_chunks'])):
                    chunk_data = f.read(init_data['chunk_size'])
                    
                    files = {'chunk': ('chunk', chunk_data, 'application/octet-stream')}
                    data = {'chunk_index': chunk_index}
                    
                    client.post(
                        f'/api/v2/videos/upload/chunk/{upload_session_id}',
                        files=files,
                        data=data
                    )
            
            # Cancel the upload
            cancel_response = client.delete(f'/api/v2/videos/upload/{upload_session_id}')
            assert cancel_response.status_code == 200
            
            # Verify upload session is cancelled
            status_response = client.get(f'/api/v2/videos/upload/status/{upload_session_id}')
            assert status_response.status_code == 404  # Session should be deleted
    
    def test_concurrent_uploads(self):
        """Test that multiple concurrent uploads work correctly"""
        # Create multiple test files
        file_paths = []
        for i in range(3):
            file_path = TestFile.create_test_file(30, f"test_concurrent_{i}.mp4")
            file_paths.append(file_path)
            self.test_files.append(file_path)
        
        results = []
        
        def upload_file(file_path: str):
            with TestClient(app) as client:
                with open(file_path, 'rb') as f:
                    files = {'file': (os.path.basename(file_path), f, 'video/mp4')}
                    
                    response = client.post(
                        '/api/v2/videos/upload/traditional',
                        files=files,
                        timeout=300
                    )
                    
                    results.append({
                        'file_path': file_path,
                        'status_code': response.status_code,
                        'response': response.json() if response.status_code == 200 else None
                    })
        
        # Start concurrent uploads
        threads = []
        for file_path in file_paths:
            thread = threading.Thread(target=upload_file, args=(file_path,))
            threads.append(thread)
            thread.start()
        
        # Wait for all uploads to complete
        for thread in threads:
            thread.join()
        
        # Verify all uploads succeeded
        assert len(results) == 3
        for result in results:
            assert result['status_code'] == 200
            assert result['response']['status'] == 'completed'
    
    def test_upload_resume_functionality(self):
        """Test that interrupted uploads can be resumed"""
        # Create 100MB test file
        file_path = TestFile.create_test_file(100, "test_resume.mp4")
        self.test_files.append(file_path)
        
        file_size = os.path.getsize(file_path)
        
        with TestClient(app) as client:
            # Initialize chunked upload
            init_response = client.post(
                '/api/v2/videos/upload/init',
                json={
                    'filename': 'test_resume.mp4',
                    'file_size': file_size
                }
            )
            
            assert init_response.status_code == 200
            init_data = init_response.json()
            upload_session_id = init_data['upload_session_id']
            total_chunks = init_data['total_chunks']
            chunk_size = init_data['chunk_size']
            
            # Upload first half of chunks
            chunks_to_upload = total_chunks // 2
            
            with open(file_path, 'rb') as f:
                for chunk_index in range(chunks_to_upload):
                    chunk_data = f.read(chunk_size)
                    
                    files = {'chunk': ('chunk', chunk_data, 'application/octet-stream')}
                    data = {'chunk_index': chunk_index}
                    
                    chunk_response = client.post(
                        f'/api/v2/videos/upload/chunk/{upload_session_id}',
                        files=files,
                        data=data
                    )
                    assert chunk_response.status_code == 200
            
            # Check upload status (should show partial progress)
            status_response = client.get(f'/api/v2/videos/upload/status/{upload_session_id}')
            assert status_response.status_code == 200
            status_data = status_response.json()
            
            assert len(status_data['missing_chunks']) == total_chunks - chunks_to_upload
            assert status_data['progress']['chunks_completed'] == chunks_to_upload
            
            # Resume upload - upload remaining chunks
            with open(file_path, 'rb') as f:
                for chunk_index in range(chunks_to_upload, total_chunks):
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    files = {'chunk': ('chunk', chunk_data, 'application/octet-stream')}
                    data = {'chunk_index': chunk_index}
                    
                    chunk_response = client.post(
                        f'/api/v2/videos/upload/chunk/{upload_session_id}',
                        files=files,
                        data=data
                    )
                    assert chunk_response.status_code == 200
                    
                    # Last chunk should complete the upload
                    if chunk_index == total_chunks - 1:
                        chunk_result = chunk_response.json()
                        assert chunk_result['status'] == 'upload_completed'
    
    @pytest.mark.slow
    def test_1gb_file_upload_stress_test(self):
        """Stress test with 1GB file (marked as slow test)"""
        # Only run this test if explicitly requested
        if not os.environ.get('RUN_STRESS_TESTS'):
            pytest.skip("Stress tests not enabled")
        
        # Create 1GB test file
        file_path = TestFile.create_test_file(1024, "test_1gb_video.mp4")
        self.test_files.append(file_path)
        
        file_size = os.path.getsize(file_path)
        start_time = time.time()
        
        with TestClient(app) as client:
            # Use chunked upload for 1GB file
            init_response = client.post(
                '/api/v2/videos/upload/init',
                json={
                    'filename': 'test_1gb_video.mp4',
                    'file_size': file_size
                }
            )
            
            assert init_response.status_code == 200
            init_data = init_response.json()
            upload_session_id = init_data['upload_session_id']
            total_chunks = init_data['total_chunks']
            chunk_size = init_data['chunk_size']
            
            # Upload all chunks
            with open(file_path, 'rb') as f:
                for chunk_index in range(total_chunks):
                    if chunk_index % 100 == 0:  # Progress logging
                        elapsed = time.time() - start_time
                        percentage = (chunk_index / total_chunks) * 100
                        print(f"1GB upload progress: {percentage:.1f}% ({chunk_index}/{total_chunks}) - {elapsed:.1f}s")
                    
                    chunk_data = f.read(chunk_size)
                    
                    files = {'chunk': ('chunk', chunk_data, 'application/octet-stream')}
                    data = {'chunk_index': chunk_index}
                    
                    chunk_response = client.post(
                        f'/api/v2/videos/upload/chunk/{upload_session_id}',
                        files=files,
                        data=data,
                        timeout=30  # 30 second timeout per chunk
                    )
                    assert chunk_response.status_code == 200
        
        total_time = time.time() - start_time
        upload_speed_mbps = (file_size / (1024 * 1024)) / total_time
        
        print(f"1GB upload completed in {total_time:.1f}s ({upload_speed_mbps:.1f} MB/s)")
        
        # Verify reasonable upload speed (should be at least 1MB/s on local testing)
        assert upload_speed_mbps > 1.0, f"Upload too slow: {upload_speed_mbps:.1f} MB/s"

if __name__ == '__main__':
    # Run specific tests for development
    pytest.main([__file__, '-v', '-s'])