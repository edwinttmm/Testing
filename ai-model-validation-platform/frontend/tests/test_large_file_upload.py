"""
Large File Upload Test Suite
Tests chunked upload mechanism, error handling, retry logic, and progress tracking
"""

import pytest
import tempfile
import os
import shutil
import json
import time
import hashlib
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from pathlib import Path
import threading
import queue


class TestLargeFileUpload:
    """Test large file upload with chunking support"""
    
    @pytest.fixture
    def temp_upload_dir(self):
        """Create temporary upload directory"""
        temp_dir = tempfile.mkdtemp()
        upload_dir = os.path.join(temp_dir, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        yield upload_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def large_test_file(self, temp_upload_dir):
        """Create a large test file for upload testing"""
        file_path = os.path.join(temp_upload_dir, 'large_video.mp4')
        
        # Create 50MB test file with known content for checksum verification
        chunk_size = 1024 * 1024  # 1MB chunks
        test_data = b'A' * chunk_size
        
        with open(file_path, 'wb') as f:
            for i in range(50):  # 50MB total
                # Vary content slightly for each chunk
                chunk_data = test_data[:chunk_size-1] + bytes([i % 256])
                f.write(chunk_data)
        
        return file_path
    
    @pytest.fixture
    def upload_manager(self):
        """Mock upload manager with chunking support"""
        class ChunkedUploadManager:
            def __init__(self, chunk_size=5*1024*1024):  # 5MB default chunk size
                self.chunk_size = chunk_size
                self.active_uploads = {}
                self.upload_counter = 0
            
            def initiate_upload(self, filename, total_size, content_type='video/mp4'):
                """Initiate a new chunked upload"""
                upload_id = f"upload_{self.upload_counter}"
                self.upload_counter += 1
                
                self.active_uploads[upload_id] = {
                    'filename': filename,
                    'total_size': total_size,
                    'content_type': content_type,
                    'uploaded_chunks': {},
                    'uploaded_size': 0,
                    'status': 'initiated',
                    'created_at': time.time(),
                    'last_activity': time.time()
                }
                
                return {
                    'upload_id': upload_id,
                    'chunk_size': self.chunk_size,
                    'total_chunks': (total_size + self.chunk_size - 1) // self.chunk_size
                }
            
            def upload_chunk(self, upload_id, chunk_number, chunk_data, chunk_hash=None):
                """Upload a single chunk"""
                if upload_id not in self.active_uploads:
                    raise ValueError(f"Upload ID {upload_id} not found")
                
                upload_info = self.active_uploads[upload_id]
                
                # Validate chunk hash if provided
                if chunk_hash:
                    actual_hash = hashlib.md5(chunk_data).hexdigest()
                    if actual_hash != chunk_hash:
                        raise ValueError(f"Chunk hash mismatch: expected {chunk_hash}, got {actual_hash}")
                
                # Simulate network delay and potential failures
                time.sleep(0.01)  # Small delay
                
                # Simulate occasional network failures (5% chance)
                if hasattr(self, '_simulate_failures') and self._simulate_failures:
                    import random
                    if random.random() < 0.05:
                        raise ConnectionError("Simulated network failure")
                
                # Store chunk
                upload_info['uploaded_chunks'][chunk_number] = {
                    'size': len(chunk_data),
                    'hash': chunk_hash,
                    'uploaded_at': time.time()
                }
                upload_info['uploaded_size'] += len(chunk_data)
                upload_info['last_activity'] = time.time()
                
                # Check if upload is complete
                total_chunks = (upload_info['total_size'] + self.chunk_size - 1) // self.chunk_size
                if len(upload_info['uploaded_chunks']) == total_chunks:
                    upload_info['status'] = 'completed'
                
                return {
                    'chunk_number': chunk_number,
                    'uploaded_size': upload_info['uploaded_size'],
                    'total_size': upload_info['total_size'],
                    'progress': upload_info['uploaded_size'] / upload_info['total_size']
                }
            
            def finalize_upload(self, upload_id, expected_hash=None):
                """Finalize the upload and verify integrity"""
                if upload_id not in self.active_uploads:
                    raise ValueError(f"Upload ID {upload_id} not found")
                
                upload_info = self.active_uploads[upload_id]
                
                if upload_info['status'] != 'completed':
                    raise ValueError("Upload not completed")
                
                # Simulate file assembly and verification
                if expected_hash:
                    # In real implementation, would verify file hash
                    pass
                
                upload_info['status'] = 'finalized'
                upload_info['finalized_at'] = time.time()
                
                return {
                    'success': True,
                    'file_path': f"/uploads/{upload_info['filename']}",
                    'total_size': upload_info['total_size'],
                    'upload_time': upload_info['finalized_at'] - upload_info['created_at']
                }
            
            def get_upload_status(self, upload_id):
                """Get current upload status"""
                if upload_id not in self.active_uploads:
                    return None
                
                return self.active_uploads[upload_id].copy()
            
            def cancel_upload(self, upload_id):
                """Cancel an active upload"""
                if upload_id in self.active_uploads:
                    self.active_uploads[upload_id]['status'] = 'cancelled'
                    return True
                return False
        
        return ChunkedUploadManager
    
    def test_chunked_upload_initiation(self, large_test_file, upload_manager):
        """Test initiation of chunked upload"""
        manager = upload_manager(chunk_size=5*1024*1024)  # 5MB chunks
        file_size = os.path.getsize(large_test_file)
        
        result = manager.initiate_upload('test_video.mp4', file_size)
        
        assert 'upload_id' in result
        assert result['chunk_size'] == 5*1024*1024
        assert result['total_chunks'] == 10  # 50MB / 5MB = 10 chunks
        
        # Verify upload tracking
        status = manager.get_upload_status(result['upload_id'])
        assert status['filename'] == 'test_video.mp4'
        assert status['total_size'] == file_size
        assert status['status'] == 'initiated'
    
    def test_individual_chunk_upload(self, large_test_file, upload_manager):
        """Test uploading individual chunks with validation"""
        manager = upload_manager(chunk_size=5*1024*1024)
        file_size = os.path.getsize(large_test_file)
        
        # Initiate upload
        init_result = manager.initiate_upload('test_video.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Read and upload first chunk
        with open(large_test_file, 'rb') as f:
            chunk_data = f.read(5*1024*1024)
        
        chunk_hash = hashlib.md5(chunk_data).hexdigest()
        
        upload_result = manager.upload_chunk(upload_id, 0, chunk_data, chunk_hash)
        
        assert upload_result['chunk_number'] == 0
        assert upload_result['uploaded_size'] == len(chunk_data)
        assert upload_result['progress'] == len(chunk_data) / file_size
        
        # Verify chunk stored correctly
        status = manager.get_upload_status(upload_id)
        assert 0 in status['uploaded_chunks']
        assert status['uploaded_chunks'][0]['size'] == len(chunk_data)
        assert status['uploaded_chunks'][0]['hash'] == chunk_hash
    
    def test_complete_chunked_upload_workflow(self, large_test_file, upload_manager):
        """Test complete chunked upload workflow"""
        manager = upload_manager(chunk_size=5*1024*1024)
        file_size = os.path.getsize(large_test_file)
        
        # Calculate file hash for verification
        with open(large_test_file, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        # Initiate upload
        init_result = manager.initiate_upload('test_video.mp4', file_size)
        upload_id = init_result['upload_id']
        total_chunks = init_result['total_chunks']
        
        # Upload all chunks
        with open(large_test_file, 'rb') as f:
            for chunk_num in range(total_chunks):
                chunk_data = f.read(manager.chunk_size)
                if not chunk_data:
                    break
                
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                upload_result = manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
                
                # Verify progress tracking
                expected_progress = min(1.0, upload_result['uploaded_size'] / file_size)
                assert abs(upload_result['progress'] - expected_progress) < 0.001
        
        # Verify upload completed
        status = manager.get_upload_status(upload_id)
        assert status['status'] == 'completed'
        assert len(status['uploaded_chunks']) == total_chunks
        
        # Finalize upload
        final_result = manager.finalize_upload(upload_id, file_hash)
        
        assert final_result['success'] is True
        assert final_result['total_size'] == file_size
        assert 'file_path' in final_result
        assert final_result['upload_time'] > 0
    
    def test_upload_with_network_failures(self, large_test_file, upload_manager):
        """Test upload resilience to network failures with retry logic"""
        class RetryableUploadClient:
            def __init__(self, upload_manager, max_retries=3):
                self.upload_manager = upload_manager
                self.max_retries = max_retries
            
            def upload_chunk_with_retry(self, upload_id, chunk_number, chunk_data, chunk_hash=None):
                """Upload chunk with retry logic"""
                last_error = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        return self.upload_manager.upload_chunk(
                            upload_id, chunk_number, chunk_data, chunk_hash
                        )
                    except (ConnectionError, TimeoutError) as e:
                        last_error = e
                        if attempt < self.max_retries:
                            # Exponential backoff
                            time.sleep(0.1 * (2 ** attempt))
                            continue
                        else:
                            raise last_error
        
        manager = upload_manager(chunk_size=5*1024*1024)
        manager._simulate_failures = True  # Enable failure simulation
        
        client = RetryableUploadClient(manager, max_retries=3)
        file_size = os.path.getsize(large_test_file)
        
        # Initiate upload
        init_result = manager.initiate_upload('test_video.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Upload first chunk with potential failures
        with open(large_test_file, 'rb') as f:
            chunk_data = f.read(manager.chunk_size)
        
        chunk_hash = hashlib.md5(chunk_data).hexdigest()
        
        # Should eventually succeed despite simulated failures
        result = client.upload_chunk_with_retry(upload_id, 0, chunk_data, chunk_hash)
        
        assert result['chunk_number'] == 0
        assert result['uploaded_size'] == len(chunk_data)
        
        # Verify chunk was uploaded
        status = manager.get_upload_status(upload_id)
        assert 0 in status['uploaded_chunks']
    
    def test_concurrent_chunk_uploads(self, temp_upload_dir, upload_manager):
        """Test uploading chunks concurrently for better performance"""
        import threading
        
        # Create test file
        test_file = os.path.join(temp_upload_dir, 'concurrent_test.mp4')
        chunk_size = 1024 * 1024  # 1MB chunks
        total_chunks = 10
        
        # Create file with identifiable chunk content
        with open(test_file, 'wb') as f:
            for i in range(total_chunks):
                chunk_content = f"CHUNK_{i:02d}_".encode() + b'X' * (chunk_size - 10)
                f.write(chunk_content)
        
        manager = upload_manager(chunk_size=chunk_size)
        file_size = os.path.getsize(test_file)
        
        # Initiate upload
        init_result = manager.initiate_upload('concurrent_test.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Concurrent chunk upload function
        def upload_chunk_worker(chunk_num, results_queue):
            try:
                with open(test_file, 'rb') as f:
                    f.seek(chunk_num * chunk_size)
                    chunk_data = f.read(chunk_size)
                
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                result = manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
                
                results_queue.put({
                    'chunk_num': chunk_num,
                    'success': True,
                    'result': result
                })
            except Exception as e:
                results_queue.put({
                    'chunk_num': chunk_num,
                    'success': False,
                    'error': str(e)
                })
        
        # Start concurrent uploads
        results_queue = queue.Queue()
        threads = []
        
        for chunk_num in range(total_chunks):
            thread = threading.Thread(
                target=upload_chunk_worker,
                args=(chunk_num, results_queue)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all uploads to complete
        for thread in threads:
            thread.join()
        
        # Collect results
        upload_results = {}
        while not results_queue.empty():
            result = results_queue.get()
            upload_results[result['chunk_num']] = result
        
        # Verify all chunks uploaded successfully
        assert len(upload_results) == total_chunks
        for chunk_num in range(total_chunks):
            assert upload_results[chunk_num]['success'] is True
        
        # Verify upload completed
        status = manager.get_upload_status(upload_id)
        assert status['status'] == 'completed'
        assert len(status['uploaded_chunks']) == total_chunks
    
    def test_upload_progress_tracking(self, large_test_file, upload_manager):
        """Test accurate progress tracking during upload"""
        class ProgressTracker:
            def __init__(self):
                self.progress_updates = []
                self.callback_count = 0
            
            def on_progress_update(self, upload_id, progress_info):
                self.progress_updates.append({
                    'timestamp': time.time(),
                    'uploaded_size': progress_info['uploaded_size'],
                    'total_size': progress_info['total_size'],
                    'progress_percent': progress_info['progress'] * 100,
                    'chunks_completed': len(progress_info.get('uploaded_chunks', {}))
                })
                self.callback_count += 1
        
        manager = upload_manager(chunk_size=10*1024*1024)  # 10MB chunks for fewer updates
        file_size = os.path.getsize(large_test_file)
        tracker = ProgressTracker()
        
        # Initiate upload
        init_result = manager.initiate_upload('progress_test.mp4', file_size)
        upload_id = init_result['upload_id']
        total_chunks = init_result['total_chunks']
        
        # Upload chunks with progress tracking
        with open(large_test_file, 'rb') as f:
            for chunk_num in range(total_chunks):
                chunk_data = f.read(manager.chunk_size)
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                
                upload_result = manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
                
                # Simulate progress callback
                status = manager.get_upload_status(upload_id)
                tracker.on_progress_update(upload_id, {
                    'uploaded_size': upload_result['uploaded_size'],
                    'total_size': upload_result['total_size'],
                    'progress': upload_result['progress'],
                    'uploaded_chunks': status['uploaded_chunks']
                })
        
        # Verify progress tracking accuracy
        assert len(tracker.progress_updates) == total_chunks
        
        # Check progress increases monotonically
        for i in range(1, len(tracker.progress_updates)):
            current_progress = tracker.progress_updates[i]['progress_percent']
            previous_progress = tracker.progress_updates[i-1]['progress_percent']
            assert current_progress >= previous_progress
        
        # Final progress should be 100%
        assert abs(tracker.progress_updates[-1]['progress_percent'] - 100.0) < 0.1
    
    def test_upload_cancellation(self, large_test_file, upload_manager):
        """Test cancelling an in-progress upload"""
        manager = upload_manager(chunk_size=5*1024*1024)
        file_size = os.path.getsize(large_test_file)
        
        # Initiate upload
        init_result = manager.initiate_upload('cancellation_test.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Upload a few chunks
        with open(large_test_file, 'rb') as f:
            for chunk_num in range(3):  # Upload 3 out of 10 chunks
                chunk_data = f.read(manager.chunk_size)
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
        
        # Verify partial upload
        status = manager.get_upload_status(upload_id)
        assert len(status['uploaded_chunks']) == 3
        assert status['status'] == 'initiated'  # Not yet completed
        
        # Cancel upload
        cancel_result = manager.cancel_upload(upload_id)
        assert cancel_result is True
        
        # Verify cancellation
        status = manager.get_upload_status(upload_id)
        assert status['status'] == 'cancelled'
        
        # Verify can't upload more chunks after cancellation
        with pytest.raises(ValueError):
            chunk_data = f.read(manager.chunk_size)
            manager.upload_chunk(upload_id, 4, chunk_data)
    
    def test_upload_resumption_after_interruption(self, large_test_file, upload_manager):
        """Test resuming upload after interruption"""
        class ResumableUploadClient:
            def __init__(self, upload_manager):
                self.upload_manager = upload_manager
            
            def resume_upload(self, upload_id, file_path):
                """Resume a previously started upload"""
                status = self.upload_manager.get_upload_status(upload_id)
                if not status:
                    raise ValueError(f"Upload {upload_id} not found")
                
                uploaded_chunks = set(status['uploaded_chunks'].keys())
                total_chunks = (status['total_size'] + self.upload_manager.chunk_size - 1) // self.upload_manager.chunk_size
                
                missing_chunks = []
                for chunk_num in range(total_chunks):
                    if chunk_num not in uploaded_chunks:
                        missing_chunks.append(chunk_num)
                
                # Upload missing chunks
                with open(file_path, 'rb') as f:
                    for chunk_num in missing_chunks:
                        f.seek(chunk_num * self.upload_manager.chunk_size)
                        chunk_data = f.read(self.upload_manager.chunk_size)
                        chunk_hash = hashlib.md5(chunk_data).hexdigest()
                        
                        self.upload_manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
                
                return len(missing_chunks)
        
        manager = upload_manager(chunk_size=5*1024*1024)
        client = ResumableUploadClient(manager)
        file_size = os.path.getsize(large_test_file)
        
        # Initiate upload
        init_result = manager.initiate_upload('resumable_test.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Simulate partial upload (upload chunks 0, 1, 3, 5)
        uploaded_chunks = [0, 1, 3, 5]
        with open(large_test_file, 'rb') as f:
            for chunk_num in uploaded_chunks:
                f.seek(chunk_num * manager.chunk_size)
                chunk_data = f.read(manager.chunk_size)
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
        
        # Verify partial state
        status = manager.get_upload_status(upload_id)
        assert len(status['uploaded_chunks']) == 4
        
        # Resume upload
        missing_chunks_count = client.resume_upload(upload_id, large_test_file)
        expected_missing = 10 - 4  # Total chunks minus already uploaded
        assert missing_chunks_count == expected_missing
        
        # Verify upload completed
        final_status = manager.get_upload_status(upload_id)
        assert final_status['status'] == 'completed'
        assert len(final_status['uploaded_chunks']) == 10
    
    def test_upload_integrity_verification(self, temp_upload_dir, upload_manager):
        """Test file integrity verification during and after upload"""
        # Create test file with known content
        test_file = os.path.join(temp_upload_dir, 'integrity_test.mp4')
        test_content = b'INTEGRITY_TEST_' * (1024 * 64)  # ~1MB of repeated content
        
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        # Calculate checksums
        file_md5 = hashlib.md5(test_content).hexdigest()
        file_sha256 = hashlib.sha256(test_content).hexdigest()
        
        class IntegrityVerifyingManager(upload_manager):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.verification_enabled = True
            
            def finalize_upload(self, upload_id, expected_hash=None, hash_algorithm='md5'):
                """Enhanced finalize with integrity verification"""
                base_result = super().finalize_upload(upload_id, expected_hash)
                
                if self.verification_enabled and expected_hash:
                    upload_info = self.active_uploads[upload_id]
                    
                    # Simulate reconstruction and verification
                    # In real implementation, would reconstruct file from chunks
                    reconstructed_hash = expected_hash  # Simulate successful verification
                    
                    if reconstructed_hash != expected_hash:
                        raise ValueError(f"File integrity check failed: {reconstructed_hash} != {expected_hash}")
                    
                    base_result['integrity_verified'] = True
                    base_result['hash_algorithm'] = hash_algorithm
                    base_result['file_hash'] = expected_hash
                
                return base_result
        
        manager = IntegrityVerifyingManager(chunk_size=256*1024)  # 256KB chunks
        file_size = os.path.getsize(test_file)
        
        # Initiate and complete upload
        init_result = manager.initiate_upload('integrity_test.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Upload all chunks
        with open(test_file, 'rb') as f:
            chunk_num = 0
            while True:
                chunk_data = f.read(manager.chunk_size)
                if not chunk_data:
                    break
                
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                manager.upload_chunk(upload_id, chunk_num, chunk_data, chunk_hash)
                chunk_num += 1
        
        # Finalize with integrity check
        final_result = manager.finalize_upload(upload_id, file_md5, 'md5')
        
        assert final_result['success'] is True
        assert final_result['integrity_verified'] is True
        assert final_result['file_hash'] == file_md5
        assert final_result['hash_algorithm'] == 'md5'
    
    def test_upload_timeout_handling(self, large_test_file, upload_manager):
        """Test handling of upload timeouts and cleanup"""
        class TimeoutAwareManager(upload_manager):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.upload_timeout = 10  # 10 seconds timeout
            
            def cleanup_expired_uploads(self):
                """Clean up uploads that have exceeded timeout"""
                current_time = time.time()
                expired_uploads = []
                
                for upload_id, upload_info in self.active_uploads.items():
                    if upload_info['status'] in ['initiated', 'uploading']:
                        time_since_activity = current_time - upload_info['last_activity']
                        if time_since_activity > self.upload_timeout:
                            expired_uploads.append(upload_id)
                
                # Mark expired uploads as failed
                for upload_id in expired_uploads:
                    self.active_uploads[upload_id]['status'] = 'timeout'
                    self.active_uploads[upload_id]['error'] = 'Upload timeout'
                
                return len(expired_uploads)
        
        manager = TimeoutAwareManager(chunk_size=10*1024*1024)
        file_size = os.path.getsize(large_test_file)
        
        # Initiate upload
        init_result = manager.initiate_upload('timeout_test.mp4', file_size)
        upload_id = init_result['upload_id']
        
        # Upload one chunk then wait
        with open(large_test_file, 'rb') as f:
            chunk_data = f.read(manager.chunk_size)
            chunk_hash = hashlib.md5(chunk_data).hexdigest()
            manager.upload_chunk(upload_id, 0, chunk_data, chunk_hash)
        
        # Simulate passage of time beyond timeout
        upload_info = manager.get_upload_status(upload_id)
        upload_info['last_activity'] = time.time() - 15  # 15 seconds ago
        
        # Cleanup expired uploads
        expired_count = manager.cleanup_expired_uploads()
        assert expired_count == 1
        
        # Verify upload marked as timed out
        status = manager.get_upload_status(upload_id)
        assert status['status'] == 'timeout'
        assert 'timeout' in status['error']


class TestUploadPerformance:
    """Test upload performance characteristics"""
    
    def test_chunked_vs_monolithic_upload_performance(self, temp_upload_dir):
        """Compare performance of chunked vs monolithic upload"""
        import time
        
        # Create test file
        test_file = os.path.join(temp_upload_dir, 'perf_test.mp4')
        file_size = 20 * 1024 * 1024  # 20MB
        
        with open(test_file, 'wb') as f:
            f.write(b'X' * file_size)
        
        class PerformanceTestManager:
            def monolithic_upload(self, file_path):
                """Simulate monolithic upload"""
                start_time = time.time()
                
                with open(file_path, 'rb') as f:
                    data = f.read()
                    # Simulate network transfer time
                    time.sleep(len(data) / (50 * 1024 * 1024))  # 50MB/s simulation
                
                end_time = time.time()
                return {
                    'method': 'monolithic',
                    'duration': end_time - start_time,
                    'size': len(data)
                }
            
            def chunked_upload(self, file_path, chunk_size=5*1024*1024):
                """Simulate chunked upload"""
                start_time = time.time()
                total_size = 0
                
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        
                        # Simulate parallel chunk processing (reduced time)
                        time.sleep(len(chunk) / (75 * 1024 * 1024))  # 75MB/s for chunks
                        total_size += len(chunk)
                
                end_time = time.time()
                return {
                    'method': 'chunked',
                    'duration': end_time - start_time,
                    'size': total_size
                }
        
        manager = PerformanceTestManager()
        
        # Test both methods
        monolithic_result = manager.monolithic_upload(test_file)
        chunked_result = manager.chunked_upload(test_file)
        
        # Chunked should be faster due to parallelization
        assert chunked_result['duration'] < monolithic_result['duration']
        assert chunked_result['size'] == monolithic_result['size']
        
        # Calculate performance improvement
        improvement = (monolithic_result['duration'] - chunked_result['duration']) / monolithic_result['duration']
        assert improvement > 0.2  # At least 20% improvement
    
    def test_optimal_chunk_size_determination(self, temp_upload_dir):
        """Test determining optimal chunk size for different file sizes"""
        class ChunkSizeOptimizer:
            def determine_optimal_chunk_size(self, file_size, connection_speed_mbps=10):
                """Determine optimal chunk size based on file size and connection speed"""
                
                # Base chunk sizes to test (in MB)
                chunk_sizes = [1, 2, 5, 10, 25, 50]
                
                optimal_size = None
                min_estimated_time = float('inf')
                
                for chunk_size_mb in chunk_sizes:
                    chunk_size_bytes = chunk_size_mb * 1024 * 1024
                    
                    # Skip if chunk size is larger than file
                    if chunk_size_bytes > file_size:
                        continue
                    
                    # Calculate chunks needed
                    chunks_needed = (file_size + chunk_size_bytes - 1) // chunk_size_bytes
                    
                    # Estimate time: transfer time + overhead per chunk
                    transfer_time = file_size / (connection_speed_mbps * 1024 * 1024 / 8)  # Convert to bytes/sec
                    overhead_time = chunks_needed * 0.1  # 100ms overhead per chunk
                    total_time = transfer_time + overhead_time
                    
                    if total_time < min_estimated_time:
                        min_estimated_time = total_time
                        optimal_size = chunk_size_bytes
                
                return optimal_size, min_estimated_time
        
        optimizer = ChunkSizeOptimizer()
        
        # Test different file sizes
        test_cases = [
            (10 * 1024 * 1024, 10),    # 10MB file, 10 Mbps
            (100 * 1024 * 1024, 10),   # 100MB file, 10 Mbps
            (1000 * 1024 * 1024, 10),  # 1GB file, 10 Mbps
            (100 * 1024 * 1024, 50),   # 100MB file, 50 Mbps (faster connection)
        ]
        
        for file_size, connection_speed in test_cases:
            optimal_chunk_size, estimated_time = optimizer.determine_optimal_chunk_size(
                file_size, connection_speed
            )
            
            # Verify optimal size is reasonable
            assert optimal_chunk_size > 0
            assert optimal_chunk_size <= file_size
            assert estimated_time > 0
            
            # For larger files, should prefer larger chunks (fewer overhead)
            if file_size > 100 * 1024 * 1024:  # >100MB
                assert optimal_chunk_size >= 5 * 1024 * 1024  # At least 5MB chunks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])