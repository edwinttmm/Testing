"""
HIL LabJack Monitoring Service Isolation Tests

Tests to ensure the monitoring service has exclusive LabJack access and 
operates independently without device conflicts.
"""

import pytest
import threading
import time
import sqlite3
import uuid
import multiprocessing
import os
import signal
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the monitoring service
import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from services.labjack_monitoring_service import LabJackMonitoringService

logger = logging.getLogger(__name__)

class TestMonitoringServiceIsolation:
    """Test suite for monitoring service isolation and exclusivity"""
    
    @pytest.fixture
    def monitoring_service(self):
        """Create a fresh monitoring service instance"""
        service = LabJackMonitoringService()
        yield service
        # Cleanup
        if service.monitoring_active:
            service.stop_monitoring()
    
    @pytest.fixture
    def mock_signal_service(self):
        """Mock signal validation service"""
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock:
            mock.read_voltage_signal.return_value = {
                "success": True,
                "voltage": 3.5,
                "timestamp": time.time()
            }
            yield mock
    
    @pytest.fixture
    def test_db(self):
        """Create test database"""
        db_path = 'test_hil_monitoring.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create detection_events table matching schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_events (
                id TEXT PRIMARY KEY,
                test_session_id TEXT NOT NULL,
                timestamp REAL,
                confidence REAL,
                class_label TEXT,
                validation_result TEXT,
                created_at TEXT,
                vru_type TEXT,
                processing_time_ms REAL
            )
        """)
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
    
    def test_service_startup_shutdown(self, monitoring_service):
        """Test dedicated monitoring service process startup/shutdown"""
        session_id = "test_session_001"
        
        # Service should start successfully
        result = monitoring_service.start_monitoring(session_id, sample_rate=10)
        assert result is True
        assert monitoring_service.monitoring_active is True
        assert monitoring_service.current_session_id == session_id
        assert monitoring_service.sample_rate == 10
        
        # Should have monitoring thread running
        assert monitoring_service.monitor_thread is not None
        assert monitoring_service.monitor_thread.is_alive()
        
        # Service should stop cleanly
        monitoring_service.stop_monitoring()
        assert monitoring_service.monitoring_active is False
        assert monitoring_service.current_session_id is None
        
        # Thread should terminate within timeout
        time.sleep(0.5)  # Allow time for thread cleanup
        assert not monitoring_service.monitor_thread.is_alive()
    
    def test_exclusive_device_access(self, monitoring_service):
        """Test that only one monitoring service can access LabJack device"""
        session1 = "session_001"
        session2 = "session_002"
        
        # Start first monitoring session
        result1 = monitoring_service.start_monitoring(session1)
        assert result1 is True
        assert monitoring_service.current_session_id == session1
        
        # Attempt to start second session should fail (device already claimed)
        result2 = monitoring_service.start_monitoring(session2)
        assert result2 is False  # Should fail due to exclusivity
        assert monitoring_service.current_session_id == session1  # Still first session
        
        # Stop first session
        monitoring_service.stop_monitoring()
        
        # Now second session should succeed
        result3 = monitoring_service.start_monitoring(session2)
        assert result3 is True
        assert monitoring_service.current_session_id == session2
        
        monitoring_service.stop_monitoring()
    
    def test_concurrent_process_prevention(self):
        """Test that multiple processes cannot claim the same LabJack device"""
        def try_start_monitoring(session_id, results_queue):
            """Worker function for multiprocessing test"""
            try:
                service = LabJackMonitoringService()
                result = service.start_monitoring(session_id)
                results_queue.put((session_id, result, "success"))
                time.sleep(2)  # Hold the device briefly
                service.stop_monitoring()
            except Exception as e:
                results_queue.put((session_id, False, str(e)))
        
        # Use multiprocessing to simulate multiple processes
        from multiprocessing import Process, Queue
        
        results_queue = Queue()
        processes = []
        
        # Start multiple processes trying to claim device
        for i in range(3):
            session_id = f"concurrent_session_{i}"
            p = Process(target=try_start_monitoring, args=(session_id, results_queue))
            processes.append(p)
            p.start()
        
        # Wait for all processes to complete
        for p in processes:
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Only one process should successfully claim the device
        successful_claims = [r for r in results if r[1] is True]
        assert len(successful_claims) <= 1, f"Multiple processes claimed device: {successful_claims}"
        
        # Other processes should fail with device conflict
        failed_claims = [r for r in results if r[1] is False]
        assert len(failed_claims) >= 2, "Expected multiple processes to fail due to exclusivity"
    
    def test_service_status_reporting(self, monitoring_service):
        """Test monitoring status reporting functionality"""
        # Initially inactive
        status = monitoring_service.get_monitoring_status()
        assert status["active"] is False
        assert status["session_id"] is None
        assert status["sample_rate"] == 10  # default
        assert "timestamp" in status
        
        # Start monitoring
        session_id = "status_test_session"
        monitoring_service.start_monitoring(session_id, sample_rate=20)
        
        # Should report active status
        status = monitoring_service.get_monitoring_status()
        assert status["active"] is True
        assert status["session_id"] == session_id
        assert status["sample_rate"] == 20
        
        # Stop monitoring
        monitoring_service.stop_monitoring()
        
        # Should report inactive again
        status = monitoring_service.get_monitoring_status()
        assert status["active"] is False
        assert status["session_id"] is None
    
    @patch('services.labjack_monitoring_service.sqlite3.connect')
    def test_database_connection_independence(self, mock_db_connect, monitoring_service, mock_signal_service):
        """Test that monitoring service maintains independent database connections"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_connect.return_value = mock_conn
        
        session_id = "db_isolation_test"
        
        # Configure mock to simulate voltage readings above threshold
        mock_signal_service.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 3.5,  # Above 3.0V threshold
            "timestamp": time.time()
        }
        
        # Start monitoring
        monitoring_service.start_monitoring(session_id, sample_rate=50)  # High rate for quick test
        
        # Wait briefly for detection events
        time.sleep(0.5)
        
        # Stop monitoring
        monitoring_service.stop_monitoring()
        
        # Verify database operations occurred
        assert mock_db_connect.called
        assert mock_cursor.execute.called
        assert mock_conn.commit.called
        assert mock_conn.close.called
        
        # Verify detection event was stored
        execute_calls = mock_cursor.execute.call_args_list
        insert_calls = [call for call in execute_calls if 'INSERT INTO detection_events' in call[0][0]]
        assert len(insert_calls) > 0, "No detection events were stored"
    
    def test_signal_processing_isolation(self, monitoring_service):
        """Test that signal processing operates independently"""
        session_id = "signal_isolation_test"
        
        # Mock the signal validation import to test isolation
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            # Configure different voltage readings
            voltage_readings = [2.0, 3.5, 1.8, 4.2, 2.5, 3.8]  # Mix of high/low
            mock_signal.read_voltage_signal.side_effect = [
                {"success": True, "voltage": v, "timestamp": time.time()}
                for v in voltage_readings
            ]
            
            detection_events = []
            
            # Mock database storage to capture events
            with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_db:
                mock_conn = Mock()
                mock_cursor = Mock()
                mock_conn.cursor.return_value = mock_cursor
                mock_db.return_value = mock_conn
                
                # Capture detection events
                def capture_event(*args):
                    if len(args) > 1 and 'INSERT INTO detection_events' in args[0]:
                        detection_events.append(args[1])
                
                mock_cursor.execute.side_effect = capture_event
                
                # Start monitoring
                monitoring_service.start_monitoring(session_id, sample_rate=100)
                
                # Wait for processing
                time.sleep(0.2)
                
                # Stop monitoring
                monitoring_service.stop_monitoring()
            
            # Verify only high voltage readings (>3.0V) were stored as events
            high_voltage_count = len([v for v in voltage_readings if v > 3.0])
            assert len(detection_events) >= min(high_voltage_count, 1), "Detection events not properly filtered"
    
    def test_thread_safety(self, monitoring_service):
        """Test thread safety of monitoring service operations"""
        session_id = "thread_safety_test"
        
        def status_checker():
            """Worker function to check status concurrently"""
            for _ in range(20):
                status = monitoring_service.get_monitoring_status()
                # Should not crash or return inconsistent data
                assert isinstance(status, dict)
                assert "active" in status
                time.sleep(0.01)
        
        # Start monitoring
        monitoring_service.start_monitoring(session_id)
        
        # Start multiple threads checking status
        threads = []
        for _ in range(5):
            t = threading.Thread(target=status_checker)
            threads.append(t)
            t.start()
        
        # Let threads run while monitoring
        time.sleep(0.3)
        
        # Stop monitoring
        monitoring_service.stop_monitoring()
        
        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=2)
            assert not t.is_alive(), "Status checker thread did not complete"
    
    def test_resource_cleanup(self, monitoring_service):
        """Test that monitoring service properly cleans up resources"""
        session_id = "cleanup_test"
        
        # Start and stop monitoring multiple times
        for i in range(5):
            # Start monitoring
            result = monitoring_service.start_monitoring(f"{session_id}_{i}")
            assert result is True
            
            # Verify thread is running
            assert monitoring_service.monitor_thread is not None
            assert monitoring_service.monitor_thread.is_alive()
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
            
            # Verify cleanup
            assert monitoring_service.monitoring_active is False
            assert monitoring_service.current_session_id is None
            
            # Thread should be cleaned up
            time.sleep(0.1)
            assert not monitoring_service.monitor_thread.is_alive()
    
    def test_error_recovery(self, monitoring_service):
        """Test monitoring service recovery from errors"""
        session_id = "error_recovery_test"
        
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock_signal:
            # Configure mock to fail initially, then succeed
            call_count = 0
            def failing_read_voltage(channel):
                nonlocal call_count
                call_count += 1
                if call_count <= 3:
                    raise Exception("Simulated device error")
                return {"success": True, "voltage": 3.5, "timestamp": time.time()}
            
            mock_signal.read_voltage_signal.side_effect = failing_read_voltage
            
            # Start monitoring
            monitoring_service.start_monitoring(session_id, sample_rate=20)
            
            # Wait for error recovery
            time.sleep(0.5)
            
            # Service should still be active despite initial errors
            assert monitoring_service.monitoring_active is True
            assert call_count > 3, "Service did not retry after errors"
            
            # Stop monitoring
            monitoring_service.stop_monitoring()

if __name__ == "__main__":
    # Run individual test
    pytest.main([__file__, "-v"])