"""
HIL LabJack Test Session Integration Tests

Tests for the complete session workflow: start→monitoring→completion→results
with proper coordination between test sessions and monitoring.
"""

import pytest
import time
import asyncio
import sqlite3
import json
import uuid
import logging
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from typing import Dict, Any, List

# Import services and models
import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from services.labjack_monitoring_service import LabJackMonitoringService

logger = logging.getLogger(__name__)

class MockDatabase:
    """Mock database for testing session integration"""
    
    def __init__(self):
        self.sessions = {}
        self.detection_events = []
        self.test_results = []
    
    def create_session(self, session_data):
        """Create a test session"""
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "name": session_data.get("name", f"Test Session {session_id[:8]}"),
            "project_id": session_data.get("project_id"),
            "status": "running",
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "tolerance_ms": session_data.get("tolerance_ms", 100),
            "session_type": "HIL_Test"
        }
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id):
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def update_session(self, session_id, updates):
        """Update session"""
        if session_id in self.sessions:
            self.sessions[session_id].update(updates)
            return self.sessions[session_id]
        return None
    
    def add_detection_event(self, event_data):
        """Add detection event"""
        event = {
            "id": str(uuid.uuid4()),
            "test_session_id": event_data["test_session_id"],
            "timestamp": event_data.get("timestamp", time.time()),
            "confidence": event_data.get("voltage", 0.0),
            "class_label": event_data.get("class_label", "LabJack_AIN0"),
            "validation_result": event_data.get("validation_result", "passed"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "vru_type": event_data.get("vru_type", "LabJack_Test"),
            "processing_time_ms": event_data.get("processing_time_ms", 5.0)
        }
        self.detection_events.append(event)
        return event
    
    def get_detection_events(self, session_id):
        """Get detection events for session"""
        return [e for e in self.detection_events if e["test_session_id"] == session_id]
    
    def create_test_result(self, session_id):
        """Create test result from session data"""
        session = self.get_session(session_id)
        events = self.get_detection_events(session_id)
        
        if not session:
            return None
        
        total_events = len(events)
        passed_events = len([e for e in events if e["validation_result"] == "passed"])
        
        result = {
            "id": str(uuid.uuid4()),
            "test_session_id": session_id,
            "validation_type": "HIL_LabJack",
            "total_detections": total_events,
            "passed_detections": passed_events,
            "failed_detections": total_events - passed_events,
            "pass_rate": (passed_events / max(1, total_events)) * 100,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed"
        }
        
        self.test_results.append(result)
        return result

class TestSessionIntegration:
    """Test suite for HIL test session integration"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database for testing"""
        return MockDatabase()
    
    @pytest.fixture
    def monitoring_service(self):
        """Create monitoring service"""
        service = LabJackMonitoringService()
        yield service
        if service.monitoring_active:
            service.stop_monitoring()
    
    @pytest.fixture
    def mock_signal_service(self):
        """Mock signal validation service"""
        with patch('services.labjack_monitoring_service.signal_validation_service') as mock:
            yield mock
    
    def test_session_start_monitoring_coordination(self, mock_database, monitoring_service, mock_signal_service):
        """Test coordination between session start and monitoring initialization"""
        # Create test session
        session_data = {
            "name": "Integration Test Session",
            "project_id": "test_project_001",
            "tolerance_ms": 100
        }
        
        session = mock_database.create_session(session_data)
        session_id = session["id"]
        
        # Configure mock signal service
        mock_signal_service.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 3.5,
            "timestamp": time.time()
        }
        
        # Mock database operations in monitoring service
        stored_events = []
        
        def mock_db_connect(path):
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            
            def capture_event(*args):
                if len(args) > 1 and isinstance(args[1], tuple):
                    event_data = {
                        "test_session_id": args[1][1],
                        "voltage": args[1][3],
                        "class_label": args[1][4],
                        "validation_result": args[1][5]
                    }
                    stored_events.append(event_data)
                    mock_database.add_detection_event(event_data)
            
            mock_cursor.execute.side_effect = capture_event
            return mock_conn
        
        with patch('services.labjack_monitoring_service.sqlite3.connect', mock_db_connect):
            # Start monitoring for session
            monitoring_result = monitoring_service.start_monitoring(session_id, sample_rate=10)
            assert monitoring_result is True
            
            # Verify monitoring is active
            status = monitoring_service.get_monitoring_status()
            assert status["active"] is True
            assert status["session_id"] == session_id
            
            # Wait for some monitoring activity
            time.sleep(0.3)
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Verify session-monitoring coordination
        assert len(stored_events) > 0, "No detection events were stored"
        
        # All events should be for the correct session
        for event in stored_events:
            assert event["test_session_id"] == session_id
            assert event["voltage"] > 3.0  # Above threshold
            assert event["validation_result"] == "passed"
    
    def test_session_completion_workflow(self, mock_database, monitoring_service, mock_signal_service):
        """Test complete session workflow from start to completion"""
        # Create and start session
        session_data = {
            "name": "Complete Workflow Test",
            "project_id": "workflow_project",
            "tolerance_ms": 50
        }
        
        session = mock_database.create_session(session_data)
        session_id = session["id"]
        
        # Configure varying voltage readings
        voltage_sequence = [2.0, 3.5, 1.8, 4.2, 2.5, 3.8, 1.5, 4.0]
        voltage_index = 0
        
        def voltage_provider(channel):
            nonlocal voltage_index
            if voltage_index < len(voltage_sequence):
                voltage = voltage_sequence[voltage_index]
                voltage_index += 1
            else:
                voltage = 2.0  # Default low
            
            return {
                "success": True,
                "voltage": voltage,
                "timestamp": time.time()
            }
        
        mock_signal_service.read_voltage_signal.side_effect = voltage_provider
        
        # Mock database for monitoring service
        with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            def store_event(*args):
                if len(args) > 1 and isinstance(args[1], tuple):
                    event_data = {
                        "test_session_id": args[1][1],
                        "voltage": args[1][3],
                        "validation_result": args[1][5],
                        "processing_time_ms": args[1][8]
                    }
                    mock_database.add_detection_event(event_data)
            
            mock_cursor.execute.side_effect = store_event
            
            # Execute complete workflow
            # 1. Start monitoring
            start_result = monitoring_service.start_monitoring(session_id, sample_rate=20)
            assert start_result is True
            
            # 2. Run monitoring for test duration
            time.sleep(0.5)  # Allow processing of voltage sequence
            
            # 3. Stop monitoring
            monitoring_service.stop_monitoring()
            
            # 4. Update session status
            mock_database.update_session(session_id, {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc)
            })
            
            # 5. Generate test results
            test_result = mock_database.create_test_result(session_id)
        
        # Verify workflow completion
        final_session = mock_database.get_session(session_id)
        assert final_session["status"] == "completed"
        assert final_session["completed_at"] is not None
        
        # Verify detection events were captured
        events = mock_database.get_detection_events(session_id)
        high_voltage_count = len([v for v in voltage_sequence if v > 3.0])
        assert len(events) >= min(high_voltage_count, 1), "Detection events not captured"
        
        # Verify test result generation
        assert test_result is not None
        assert test_result["validation_type"] == "HIL_LabJack"
        assert test_result["total_detections"] == len(events)
        assert test_result["passed_detections"] <= len(events)
        assert 0 <= test_result["pass_rate"] <= 100
    
    def test_multiple_session_coordination(self, mock_database, monitoring_service, mock_signal_service):
        """Test coordination with multiple sessions (sequential)"""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session_data = {
                "name": f"Multi Session Test {i+1}",
                "project_id": f"multi_project_{i+1}",
                "tolerance_ms": 100
            }
            session = mock_database.create_session(session_data)
            sessions.append(session)
        
        mock_signal_service.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 3.5,
            "timestamp": time.time()
        }
        
        session_events = {}
        
        # Mock database to track events per session
        with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            def track_events(*args):
                if len(args) > 1 and isinstance(args[1], tuple):
                    session_id = args[1][1]
                    if session_id not in session_events:
                        session_events[session_id] = []
                    session_events[session_id].append(args[1])
            
            mock_cursor.execute.side_effect = track_events
            
            # Run sessions sequentially
            for session in sessions:
                session_id = session["id"]
                
                # Start monitoring for this session
                start_result = monitoring_service.start_monitoring(session_id, sample_rate=15)
                assert start_result is True
                
                # Verify correct session is being monitored
                status = monitoring_service.get_monitoring_status()
                assert status["session_id"] == session_id
                
                # Run monitoring briefly
                time.sleep(0.2)
                
                # Stop monitoring
                monitoring_service.stop_monitoring()
                
                # Update session
                mock_database.update_session(session_id, {"status": "completed"})
        
        # Verify each session got its own events
        assert len(session_events) == len(sessions), "Not all sessions recorded events"
        
        for session in sessions:
            session_id = session["id"]
            assert session_id in session_events, f"No events for session {session_id}"
            assert len(session_events[session_id]) > 0, f"No events stored for session {session_id}"
    
    def test_session_error_handling(self, mock_database, monitoring_service, mock_signal_service):
        """Test session handling when errors occur during monitoring"""
        session_data = {
            "name": "Error Handling Test",
            "project_id": "error_project",
            "tolerance_ms": 100
        }
        
        session = mock_database.create_session(session_data)
        session_id = session["id"]
        
        # Configure mock to fail after some readings
        call_count = 0
        
        def failing_signal_provider(channel):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 3:
                # First few calls succeed
                return {
                    "success": True,
                    "voltage": 3.5,
                    "timestamp": time.time()
                }
            elif call_count <= 6:
                # Then fail
                return {
                    "success": False,
                    "error": "Simulated hardware error"
                }
            else:
                # Then recover
                return {
                    "success": True,
                    "voltage": 3.2,
                    "timestamp": time.time()
                }
        
        mock_signal_service.read_voltage_signal.side_effect = failing_signal_provider
        
        stored_events = []
        
        with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            def capture_successful_events(*args):
                if len(args) > 1 and isinstance(args[1], tuple):
                    stored_events.append(args[1])
            
            mock_cursor.execute.side_effect = capture_successful_events
            
            # Start monitoring
            start_result = monitoring_service.start_monitoring(session_id, sample_rate=10)
            assert start_result is True
            
            # Run through error sequence
            time.sleep(1.0)  # Allow time for errors and recovery
            
            # Monitoring should still be active (error resilient)
            status = monitoring_service.get_monitoring_status()
            assert status["active"] is True
            
            # Stop monitoring
            monitoring_service.stop_monitoring()
        
        # Verify that successful readings were stored despite errors
        assert len(stored_events) > 0, "No events stored despite some successful readings"
        
        # Verify error recovery
        assert call_count > 6, "Did not reach recovery phase"
        
        # Session should remain valid
        final_session = mock_database.get_session(session_id)
        assert final_session is not None
    
    def test_session_timeout_handling(self, mock_database, monitoring_service, mock_signal_service):
        """Test session timeout and cleanup"""
        session_data = {
            "name": "Timeout Test",
            "project_id": "timeout_project",
            "tolerance_ms": 100
        }
        
        session = mock_database.create_session(session_data)
        session_id = session["id"]
        
        mock_signal_service.read_voltage_signal.return_value = {
            "success": True,
            "voltage": 3.5,
            "timestamp": time.time()
        }
        
        with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            # Start monitoring
            start_result = monitoring_service.start_monitoring(session_id, sample_rate=10)
            assert start_result is True
            
            # Simulate session timeout (in real implementation, this would be handled by a background task)
            # For testing, we'll manually trigger timeout behavior
            time.sleep(0.2)
            
            # Verify monitoring is active before timeout
            status = monitoring_service.get_monitoring_status()
            assert status["active"] is True
            
            # Simulate timeout cleanup
            monitoring_service.stop_monitoring()
            
            # Update session with timeout status
            mock_database.update_session(session_id, {
                "status": "timeout",
                "completed_at": datetime.now(timezone.utc)
            })
        
        # Verify timeout handling
        final_session = mock_database.get_session(session_id)
        assert final_session["status"] == "timeout"
        assert final_session["completed_at"] is not None
        
        # Monitoring should be inactive
        final_status = monitoring_service.get_monitoring_status()
        assert final_status["active"] is False
    
    def test_session_data_consistency(self, mock_database, monitoring_service, mock_signal_service):
        """Test data consistency between session and monitoring data"""
        session_data = {
            "name": "Data Consistency Test",
            "project_id": "consistency_project",
            "tolerance_ms": 75
        }
        
        session = mock_database.create_session(session_data)
        session_id = session["id"]
        
        # Known voltage sequence for predictable results
        test_voltages = [3.1, 3.5, 2.0, 4.0, 1.5, 3.8, 2.5, 4.2]
        voltage_index = 0
        
        def consistent_voltage_provider(channel):
            nonlocal voltage_index
            if voltage_index < len(test_voltages):
                voltage = test_voltages[voltage_index]
                voltage_index += 1
                return {
                    "success": True,
                    "voltage": voltage,
                    "timestamp": time.time()
                }
            return {
                "success": True,
                "voltage": 2.0,
                "timestamp": time.time()
            }
        
        mock_signal_service.read_voltage_signal.side_effect = consistent_voltage_provider
        
        stored_events = []
        
        with patch('services.labjack_monitoring_service.sqlite3.connect') as mock_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn
            
            def store_consistent_events(*args):
                if len(args) > 1 and isinstance(args[1], tuple):
                    event_tuple = args[1]
                    event_data = {
                        "id": event_tuple[0],
                        "test_session_id": event_tuple[1],
                        "timestamp": event_tuple[2],
                        "voltage": event_tuple[3],  # confidence field
                        "class_label": event_tuple[4],
                        "validation_result": event_tuple[5],
                        "processing_time_ms": event_tuple[8]
                    }
                    stored_events.append(event_data)
                    mock_database.add_detection_event(event_data)
            
            mock_cursor.execute.side_effect = store_consistent_events
            
            # Run monitoring
            start_result = monitoring_service.start_monitoring(session_id, sample_rate=20)
            assert start_result is True
            
            time.sleep(0.5)  # Process all test voltages
            
            monitoring_service.stop_monitoring()
        
        # Verify data consistency
        expected_high_voltages = [v for v in test_voltages if v > 3.0]
        
        # Check stored events match expectations
        assert len(stored_events) >= len(expected_high_voltages), \
            f"Expected {len(expected_high_voltages)} events, got {len(stored_events)}"
        
        # Verify all stored events are above threshold
        for event in stored_events:
            assert event["voltage"] > 3.0, f"Event voltage {event['voltage']} not above threshold"
            assert event["test_session_id"] == session_id, "Event session ID mismatch"
            assert event["validation_result"] == "passed", "High voltage should result in 'passed'"
        
        # Create test result and verify consistency
        test_result = mock_database.create_test_result(session_id)
        db_events = mock_database.get_detection_events(session_id)
        
        assert test_result["total_detections"] == len(db_events), "Total detection count mismatch"
        assert test_result["passed_detections"] == len([e for e in db_events if e["validation_result"] == "passed"])
        
        # Pass rate calculation should be consistent
        expected_pass_rate = (test_result["passed_detections"] / max(1, test_result["total_detections"])) * 100
        assert abs(test_result["pass_rate"] - expected_pass_rate) < 0.1, "Pass rate calculation inconsistent"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])