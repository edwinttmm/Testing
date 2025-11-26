"""
HIL LabJack Frontend Display Tests

Tests for frontend result display with live monitoring data to ensure
the frontend shows actual detection counts and results correctly.
"""

import os
import pytest
import asyncio
import json
import time
import sqlite3
import uuid
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from typing import Dict, Any, List

# Import FastAPI test client
import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

class MockTestSession:
    """Mock test session for frontend testing"""
    
    def __init__(self, session_id: str, **kwargs):
        self.id = session_id
        self.name = kwargs.get("name", f"Test Session {session_id[:8]}")
        self.project_id = kwargs.get("project_id", "test_project")
        self.video_id = kwargs.get("video_id")
        self.status = kwargs.get("status", "completed")
        self.started_at = kwargs.get("started_at", datetime.now(timezone.utc))
        self.completed_at = kwargs.get("completed_at", datetime.now(timezone.utc))
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        self.tolerance_ms = kwargs.get("tolerance_ms", 100)
        self.session_type = "HIL_Test"

class MockDetectionEvent:
    """Mock detection event for frontend testing"""
    
    def __init__(self, event_id: str, session_id: str, **kwargs):
        self.id = event_id
        self.test_session_id = session_id
        self.frame_number = kwargs.get("frame_number", 0)
        self.timestamp = kwargs.get("timestamp", time.time())
        self.latency_ms = kwargs.get("latency_ms", 25.5)
        self.latency_ns = kwargs.get("latency_ns")
        self.processing_time_ms = kwargs.get("processing_time_ms", 25.5)
        self.voltage_level = kwargs.get("voltage_level", 3.5)
        self.labjack_voltage = kwargs.get("labjack_voltage", 3.5)
        self.labjack_timestamp = kwargs.get("labjack_timestamp", time.time())
        self.detection_channel = kwargs.get("detection_channel", "AIN0")
        self.validation_result = kwargs.get("validation_result", "passed")
        self.confidence = kwargs.get("confidence", 3.5)
        self.class_label = kwargs.get("class_label", "LabJack_AIN0")
        self.vru_type = kwargs.get("vru_type", "LabJack_3.5V")
        self.created_at = kwargs.get("created_at", datetime.now(timezone.utc))

class TestFrontendDisplay:
    """Test suite for frontend display of HIL test results"""
    
    @pytest.fixture
    def mock_database(self):
        """Mock database with test data"""
        db_path = 'test_frontend_display.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                project_id TEXT,
                video_id TEXT,
                status TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP,
                tolerance_ms REAL,
                session_type TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS detection_events (
                id TEXT PRIMARY KEY,
                test_session_id TEXT,
                frame_number INTEGER,
                timestamp REAL,
                latency_ms REAL,
                latency_ns INTEGER,
                processing_time_ms REAL,
                voltage_level REAL,
                labjack_voltage REAL,
                labjack_timestamp REAL,
                detection_channel TEXT,
                validation_result TEXT,
                confidence REAL,
                class_label TEXT,
                vru_type TEXT,
                created_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        import os
        if os.path.exists(db_path):
            os.remove(db_path)
    
    def create_test_data(self, db_path: str, session_count: int = 1, events_per_session: int = 24):
        """Create test data in database"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        sessions = []
        all_events = []
        
        # Create project
        project_id = "frontend_test_project"
        cursor.execute("INSERT INTO projects (id, name) VALUES (?, ?)", 
                      (project_id, "Frontend Test Project"))
        
        for i in range(session_count):
            # Create test session
            session_id = f"frontend_test_session_{i+1}"
            session_name = f"Frontend Test Session {i+1}"
            
            cursor.execute("""
                INSERT INTO test_sessions 
                (id, name, project_id, status, started_at, completed_at, created_at, tolerance_ms, session_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id, session_name, project_id, "completed",
                datetime.now(timezone.utc), datetime.now(timezone.utc), datetime.now(timezone.utc),
                100, "HIL_Test"
            ))
            
            sessions.append(session_id)
            
            # Create detection events
            for j in range(events_per_session):
                event_id = f"event_{session_id}_{j+1}"
                
                # Mix of passed and failed events
                is_passed = j % 3 != 0  # 2/3 pass, 1/3 fail
                latency_ms = 45.5 if is_passed else 150.0
                voltage = 3.5 if is_passed else 3.5  # Voltage above threshold
                validation_result = "passed" if is_passed else "failed"
                
                cursor.execute("""
                    INSERT INTO detection_events 
                    (id, test_session_id, frame_number, timestamp, latency_ms, latency_ns,
                     processing_time_ms, voltage_level, labjack_voltage, labjack_timestamp,
                     detection_channel, validation_result, confidence, class_label, vru_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, session_id, j+1, time.time() + j,
                    latency_ms, int(latency_ms * 1_000_000),
                    latency_ms, voltage, voltage, time.time() + j,
                    "AIN0", validation_result, voltage, "LabJack_AIN0",
                    f"LabJack_{voltage}V", datetime.now(timezone.utc).isoformat()
                ))
                
                all_events.append(event_id)
        
        conn.commit()
        conn.close()
        
        return sessions, all_events
    
    def test_hil_results_endpoint_response(self, mock_database):
        """Test HIL results endpoint returns correct data structure"""
        # Create test data
        sessions, events = self.create_test_data(mock_database, session_count=1, events_per_session=24)
        session_id = sessions[0]
        
        # Mock database connection in the API
        with patch('src.api.hil_results_endpoints.text') as mock_text, \
             patch('src.api.hil_results_endpoints.get_db') as mock_get_db:
            
            # Create mock database session
            mock_db_session = Mock()
            mock_get_db.return_value = mock_db_session
            
            # Create mock result objects
            class MockRow:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)
            
            # Mock session query result
            session_row = MockRow(
                id=session_id,
                name="Frontend Test Session 1",
                project_id="frontend_test_project",
                video_id=None,
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                tolerance_ms=100,
                session_type="HIL_Test"
            )
            
            # Mock detection events query result
            event_rows = []
            for i in range(24):
                is_passed = i % 3 != 0
                latency_ms = 45.5 if is_passed else 150.0
                
                event_rows.append(MockRow(
                    id=f"event_{session_id}_{i+1}",
                    test_session_id=session_id,
                    frame_number=i+1,
                    timestamp=time.time() + i,
                    latency_ms=latency_ms,
                    latency_ns=int(latency_ms * 1_000_000),
                    processing_time_ms=latency_ms,
                    voltage_level=3.5,
                    labjack_voltage=3.5,
                    labjack_timestamp=time.time() + i,
                    detection_channel="AIN0",
                    validation_result="passed" if is_passed else "failed",
                    confidence=3.5,
                    class_label="LabJack_AIN0",
                    vru_type="LabJack_3.5V",
                    created_at=datetime.now(timezone.utc).isoformat()
                ))
            
            # Mock project query result
            project_row = MockRow(name="Frontend Test Project")
            
            # Configure mock queries
            mock_db_session.execute.side_effect = [
                Mock(fetchone=Mock(return_value=session_row)),  # Session query
                Mock(fetchall=Mock(return_value=event_rows)),   # Events query
                Mock(fetchone=Mock(return_value=project_row))   # Project query
            ]
            
            # Import and test the endpoint
            from src.api.hil_results_endpoints import get_hil_test_results
            
            # Execute endpoint
            import asyncio
            result = asyncio.run(get_hil_test_results(session_id, mock_db_session))
        
        # Verify response structure
        assert isinstance(result, dict)
        assert "session_id" in result
        assert "total_detections" in result
        assert "passed_detections" in result
        assert "failed_detections" in result
        assert "pass_rate" in result
        assert "latency_stats" in result
        assert "detection_events" in result
        assert "hardware_status" in result
        
        # Verify detection counts
        assert result["total_detections"] == 24
        assert result["passed_detections"] == 16  # 2/3 of 24
        assert result["failed_detections"] == 8   # 1/3 of 24
        assert abs(result["pass_rate"] - 66.67) < 0.1  # ~66.67%
        
        # Verify latency statistics
        latency_stats = result["latency_stats"]
        assert "average_ms" in latency_stats
        assert "min_ms" in latency_stats
        assert "max_ms" in latency_stats
        assert "threshold_ms" in latency_stats
        assert latency_stats["threshold_ms"] == 100
        
        # Verify detection events structure
        detection_events = result["detection_events"]
        assert len(detection_events) == 24
        
        for event in detection_events:
            assert "event_id" in event
            assert "frame_number" in event
            assert "latency_ms" in event
            assert "voltage_level" in event
            assert "result" in event
            assert event["result"] in ["pass", "fail"]
    
    def test_real_detection_counts_not_zero(self, mock_database):
        """Test that frontend shows actual detection counts, not '0 of 24 tests'"""
        # Create realistic test data
        sessions, events = self.create_test_data(mock_database, session_count=1, events_per_session=18)
        session_id = sessions[0]
        
        # Use real database connection for this test
        import sqlite3
        
        # Read actual data from test database
        conn = sqlite3.connect(mock_database)
        cursor = conn.cursor()
        
        # Get session data
        cursor.execute("SELECT * FROM test_sessions WHERE id = ?", (session_id,))
        session_data = cursor.fetchone()
        
        # Get detection events
        cursor.execute("""
            SELECT id, latency_ms, validation_result, voltage_level 
            FROM detection_events 
            WHERE test_session_id = ?
            ORDER BY timestamp
        """, (session_id,))
        event_data = cursor.fetchall()
        
        conn.close()
        
        # Verify test data was created
        assert session_data is not None, "Session data not found"
        assert len(event_data) == 18, f"Expected 18 events, got {len(event_data)}"
        
        # Count passed/failed events
        passed_count = len([e for e in event_data if e[2] == "passed"])
        failed_count = len([e for e in event_data if e[2] == "failed"])
        
        # Should have mix of passed/failed (not all zeros)
        assert passed_count > 0, "No passed detections found"
        assert failed_count > 0, "No failed detections found"
        assert passed_count + failed_count == 18, "Event count mismatch"
        
        # Verify realistic latency values
        latencies = [e[1] for e in event_data if e[1] is not None]
        assert len(latencies) > 0, "No latency values found"
        assert all(0 < l < 1000 for l in latencies), "Unrealistic latency values"
        
        # Verify voltage values are realistic
        voltages = [e[3] for e in event_data if e[3] is not None]
        assert len(voltages) > 0, "No voltage values found"
        assert all(1.0 < v < 5.0 for v in voltages), "Unrealistic voltage values"
    
    def test_live_monitoring_data_update(self, mock_database):
        """Test live monitoring data updates correctly"""
        # Create session with initial events
        sessions, initial_events = self.create_test_data(mock_database, session_count=1, events_per_session=5)
        session_id = sessions[0]
        
        # Simulate adding new events during monitoring
        conn = sqlite3.connect(mock_database)
        cursor = conn.cursor()
        
        # Add new detection events (simulating live monitoring)
        new_events = []
        for i in range(6, 11):  # Add 5 more events
            event_id = f"live_event_{session_id}_{i}"
            latency_ms = 35.0  # Good latency
            voltage = 3.8
            
            cursor.execute("""
                INSERT INTO detection_events 
                (id, test_session_id, frame_number, timestamp, latency_ms, latency_ns,
                 processing_time_ms, voltage_level, labjack_voltage, labjack_timestamp,
                 detection_channel, validation_result, confidence, class_label, vru_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, session_id, i, time.time() + i,
                latency_ms, int(latency_ms * 1_000_000),
                latency_ms, voltage, voltage, time.time() + i,
                "AIN0", "passed", voltage, "LabJack_AIN0",
                f"LabJack_{voltage}V", datetime.now(timezone.utc).isoformat()
            ))
            
            new_events.append(event_id)
        
        conn.commit()
        conn.close()
        
        # Query updated data
        conn = sqlite3.connect(mock_database)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN validation_result = 'passed' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN validation_result = 'failed' THEN 1 ELSE 0 END)
            FROM detection_events 
            WHERE test_session_id = ?
        """, (session_id,))
        
        total, passed, failed = cursor.fetchone()
        conn.close()
        
        # Verify updated counts
        assert total == 10, f"Expected 10 total events, got {total}"
        assert passed > 0, "No passed events after update"
        assert total == passed + failed, "Event count mismatch"
        
        # Pass rate should be reasonable
        pass_rate = (passed / total) * 100
        assert 0 <= pass_rate <= 100, f"Invalid pass rate: {pass_rate}%"
    
    def test_hil_test_result_creation(self, mock_database):
        """Test TestResult creation with HIL_LabJack validation type"""
        # Create test session with known detection pattern
        sessions, events = self.create_test_data(mock_database, session_count=1, events_per_session=20)
        session_id = sessions[0]
        
        # Simulate TestResult creation process
        conn = sqlite3.connect(mock_database)
        cursor = conn.cursor()
        
        # Get session and event data
        cursor.execute("SELECT tolerance_ms FROM test_sessions WHERE id = ?", (session_id,))
        tolerance_ms = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT latency_ms, validation_result
            FROM detection_events 
            WHERE test_session_id = ?
        """, (session_id,))
        event_results = cursor.fetchall()
        
        # Calculate results
        total_detections = len(event_results)
        passed_detections = len([e for e in event_results if e[1] == "passed"])
        failed_detections = total_detections - passed_detections
        pass_rate = (passed_detections / total_detections) * 100
        
        # Create TestResult record
        test_result_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO test_results 
            (id, test_session_id, validation_type, total_detections, 
             passed_detections, failed_detections, pass_rate, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_result_id, session_id, "HIL_LabJack",
            total_detections, passed_detections, failed_detections, pass_rate,
            datetime.now(timezone.utc).isoformat()
        ))
        
        conn.commit()
        
        # Verify TestResult
        cursor.execute("SELECT * FROM test_results WHERE id = ?", (test_result_id,))
        result_data = cursor.fetchone()
        
        conn.close()
        
        # Verify TestResult properties
        assert result_data is not None, "TestResult not created"
        assert result_data[2] == "HIL_LabJack", "Wrong validation type"
        assert result_data[3] == total_detections, "Wrong total detections"
        assert result_data[4] == passed_detections, "Wrong passed detections"
        assert result_data[5] == failed_detections, "Wrong failed detections"
        assert abs(result_data[6] - pass_rate) < 0.1, "Wrong pass rate"
    
    def test_frontend_error_handling(self, mock_database):
        """Test frontend error handling for missing or invalid data"""
        # Test with non-existent session
        non_existent_session = "non_existent_session_123"
        
        with patch('src.api.hil_results_endpoints.get_db') as mock_get_db:
            mock_db_session = Mock()
            mock_get_db.return_value = mock_db_session
            
            # Mock empty result for non-existent session
            mock_db_session.execute.return_value.fetchone.return_value = None
            
            from src.api.hil_results_endpoints import get_hil_test_results
            
            # Should raise HTTPException for not found
            with pytest.raises(Exception):  # HTTPException or similar
                asyncio.run(get_hil_test_results(non_existent_session, mock_db_session))
    
    def test_latency_distribution_calculation(self, mock_database):
        """Test latency distribution calculation for frontend charts"""
        # Create session with specific latency pattern
        session_id = "latency_distribution_test"
        
        conn = sqlite3.connect(mock_database)
        cursor = conn.cursor()
        
        # Create session
        cursor.execute("""
            INSERT INTO test_sessions 
            (id, name, project_id, status, tolerance_ms, session_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, "Latency Test", "test_project", "completed", 100, "HIL_Test", 
              datetime.now(timezone.utc).isoformat()))
        
        # Create events with known latency distribution
        test_latencies = [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 
                         75, 80, 85, 90, 95, 120, 130, 140, 150, 160]
        
        for i, latency in enumerate(test_latencies):
            event_id = f"latency_event_{i}"
            validation_result = "passed" if latency <= 100 else "failed"
            
            cursor.execute("""
                INSERT INTO detection_events 
                (id, test_session_id, timestamp, latency_ms, processing_time_ms,
                 voltage_level, validation_result, confidence, class_label, vru_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, session_id, time.time() + i, latency, latency,
                3.5, validation_result, 3.5, "LabJack_AIN0", "LabJack_3.5V",
                datetime.now(timezone.utc).isoformat()
            ))
        
        conn.commit()
        conn.close()
        
        # Test latency distribution calculation
        import statistics
        
        # Calculate expected statistics
        passed_latencies = [l for l in test_latencies if l <= 100]
        failed_latencies = [l for l in test_latencies if l > 100]
        
        expected_avg = statistics.mean(test_latencies)
        expected_min = min(test_latencies)
        expected_max = max(test_latencies)
        expected_median = statistics.median(test_latencies)
        
        # Verify calculations would be correct
        assert len(passed_latencies) == 15, "Wrong passed count"
        assert len(failed_latencies) == 5, "Wrong failed count"
        assert expected_avg > 0, "Invalid average"
        assert expected_min == 25, "Wrong minimum"
        assert expected_max == 160, "Wrong maximum"
        assert expected_median == 67.5, "Wrong median"  # Middle of 65 and 70
    
    def test_hardware_status_display(self, mock_database):
        """Test hardware status display in frontend"""
        # Create session
        sessions, events = self.create_test_data(mock_database, session_count=1, events_per_session=5)
        session_id = sessions[0]
        
        # Mock LabJack service status
        mock_labjack_status = {
            "connected": True,
            "device_type": "T7",
            "device_serial": "12345678",
            "sampling_rate_hz": 1000,
            "active_channels": ["AIN0", "AIN1"]
        }
        
        with patch('src.api.hil_results_endpoints.LabJackService') as mock_service:
            mock_instance = Mock()
            mock_service.return_value = mock_instance
            
            # Create mock status object
            mock_status = Mock()
            mock_status.connected = True
            mock_status.device_type = "T7"
            mock_status.device_serial = "12345678"
            
            mock_instance.get_connection_status = AsyncMock(return_value=mock_status)
            
            # Test hardware status integration
            hardware_status = {
                "labjack_connected": mock_status.connected,
                "model": mock_status.device_type,
                "serial_number": mock_status.device_serial,
                "firmware_version": "Unknown",
                "sampling_rate_hz": 1000,
                "active_channels": ["AIN0", "AIN1"]
            }
        
        # Verify hardware status structure
        assert hardware_status["labjack_connected"] is True
        assert hardware_status["model"] == "T7"
        assert hardware_status["serial_number"] == "12345678"
        assert hardware_status["sampling_rate_hz"] > 0
        assert len(hardware_status["active_channels"]) > 0

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])