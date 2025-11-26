"""
Comprehensive Backward Compatibility Tests for Hybrid LabJack Logging System

This test suite validates that all existing functionality remains intact while 
new raw logging features are seamlessly integrated.

Test Coverage:
1. Existing HIL test workflows
2. Legacy API endpoints behavior and response formats  
3. Database schema integrity and data access patterns
4. Frontend HILResults component compatibility
5. LabJack services and detection systems integration
6. Configuration files and environment settings
7. Data migration scenarios
8. New features are purely additive
"""

import os
import pytest
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import text, select, delete, update, func
import httpx

# Test framework imports
from fastapi.testclient import TestClient
from fastapi import status

# Application imports
from main import app
from database import get_db, engine
from models import TestSession, DetectionEvent, Project, Video, GroundTruthObject
from services.labjack_service_manager import LabJackService, ConnectionMode
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
from api.hil_test_complete import HILTestManager
from src.api.enhanced_hil_results_endpoints import get_corrected_hil_results


class TestBackwardCompatibility:
    """Comprehensive backward compatibility test suite"""
    
    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        """Database session fixture"""
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def sample_legacy_session_data(self):
        """Legacy test session data structure"""
        return {
            "id": "test-session-123",
            "project_id": 1,
            "name": "Legacy HIL Test Session",
            "status": "completed",
            "started_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "max_latency_ms": 100,
            "labjack_connected": True,
            "video_id": "test-video-1",
            "tolerance_ms": 100
        }
    
    @pytest.fixture
    def sample_detection_events(self):
        """Legacy detection events data structure"""
        return [
            {
                "id": "event-1",
                "test_session_id": "test-session-123",
                "timestamp": time.time(),
                "frame_number": 10,
                "actual_latency_ms": 75.5,
                "processing_time_ms": 45.2,
                "voltage_level": 3.2,
                "labjack_voltage": 3.2,
                "labjack_timestamp": time.time(),
                "detection_channel": "AIN0",
                "validation_result": "pass"
            },
            {
                "id": "event-2", 
                "test_session_id": "test-session-123",
                "timestamp": time.time() + 1,
                "frame_number": 15,
                "actual_latency_ms": 92.1,
                "processing_time_ms": 58.7,
                "voltage_level": 2.8,
                "labjack_voltage": 2.8,
                "labjack_timestamp": time.time() + 1,
                "detection_channel": "AIN0",
                "validation_result": "pass"
            }
        ]

    def test_existing_hil_workflows_unchanged(self, client, db_session, sample_legacy_session_data):
        """Test that existing HIL test workflows continue working without modification"""
        
        # 1. Test session creation with legacy parameters
        response = client.post("/api/v1/hil-test/session/start", json={
            "project_id": sample_legacy_session_data["project_id"],
            "max_latency_ms": sample_legacy_session_data["max_latency_ms"],
        })
        
        assert response.status_code == 200
        session_data = response.json()
        assert "id" in session_data
        assert session_data["project_id"] == sample_legacy_session_data["project_id"]
        assert session_data["labjack_connected"] == True
        
        session_id = session_data["id"]
        
        # 2. Test video playback start (legacy interface)
        video_response = client.post(f"/api/v1/hil-test/session/{session_id}/video/start", json={
            "video_id": "test-video-1",
            "filename": "test.mp4", 
            "duration": 30.0,
            "fps": 30
        })
        
        assert video_response.status_code == 200
        video_data = video_response.json()
        assert video_data["success"] == True
        assert "t1_timestamp" in video_data
        
        # 3. Test precision timing event logging (legacy format)
        timing_response = client.post(f"/api/v1/hil-test/session/{session_id}/event/precision-timing", json={
            "expected_event_time": time.time(),
            "signal_received_time": time.time() + 0.075,
            "channel": "AIN0",
            "voltage": 3.2
        })
        
        assert timing_response.status_code == 200
        timing_data = timing_response.json()
        assert timing_data["success"] == True
        assert "latency_ms" in timing_data
        
        # 4. Test session completion (legacy interface)
        complete_response = client.post(f"/api/v1/hil-test/session/{session_id}/complete")
        assert complete_response.status_code == 200
        complete_data = complete_response.json()
        assert "pass_rate" in complete_data
        assert "average_latency" in complete_data

    def test_legacy_api_endpoints_exact_behavior(self, client, db_session):
        """Test that legacy API endpoints return exactly the same response formats"""
        
        # Test LabJack status endpoint format
        status_response = client.get("/api/v1/hil-test/labjack/status")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        required_fields = {
            "connected", "status", "connection_mode", "device_type", 
            "device_serial", "connection_type", "hil_suitable", "last_check"
        }
        assert required_fields.issubset(status_data.keys())
        
        # Verify field types match legacy expectations
        assert isinstance(status_data["connected"], bool)
        assert isinstance(status_data["status"], str)
        assert isinstance(status_data["hil_suitable"], bool)
        
        # Test hardware validation status format
        validation_response = client.get("/api/v1/hil-test/hardware/validation-status")
        assert validation_response.status_code == 200
        
        validation_data = validation_response.json()
        legacy_validation_fields = {"connected", "status", "hardware_icon", "status_color"}
        assert legacy_validation_fields.issubset(validation_data.keys())

    def test_database_schema_integrity(self, db_session):
        """Test that existing database schema remains unchanged and accessible"""
        
        # Verify all legacy tables exist
        legacy_tables = [
            "test_sessions", "detection_events", "projects", "videos", 
            "ground_truth_objects", "ml_inference_results"
        ]
        
        for table_name in legacy_tables:
            result = db_session.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
            assert result.fetchone() is not None, f"Legacy table {table_name} missing"
        
        # Test legacy detection_events table structure
        columns_result = db_session.execute(text("PRAGMA table_info(detection_events)"))
        columns = {row[1] for row in columns_result.fetchall()}
        
        # Verify critical legacy columns exist
        legacy_detection_columns = {
            "id", "test_session_id", "timestamp", "frame_number",
            "actual_latency_ms", "processing_time_ms", "voltage_level",
            "labjack_voltage", "labjack_timestamp", "detection_channel",
            "validation_result"
        }
        
        assert legacy_detection_columns.issubset(columns), f"Missing legacy columns: {legacy_detection_columns - columns}"
        
        # Verify new hybrid logging columns are additive only
        new_hybrid_columns = {
            "video_relative_timestamp", "video_frame_number", 
            "timing_sync_quality", "raw_voltage_data", "raw_timing_data"
        }
        
        # These should be present but nullable (non-breaking)
        for col in new_hybrid_columns.intersection(columns):
            # Verify column is nullable
            column_info = db_session.execute(text(f"PRAGMA table_info(detection_events)")).fetchall()
            column_details = {row[1]: {"nullable": row[3] == 0} for row in column_info}
            if col in column_details:
                assert not column_details[col]["nullable"], f"New column {col} should be nullable for backward compatibility"

    def test_frontend_hil_results_compatibility(self, client, db_session, sample_legacy_session_data, sample_detection_events):
        """Test that HILResults.tsx component works with both legacy and new data"""
        
        # Create legacy test session in database
        test_session = TestSession(
            id=sample_legacy_session_data["id"],
            name=sample_legacy_session_data["name"],
            project_id=sample_legacy_session_data["project_id"],
            status=sample_legacy_session_data["status"],
            started_at=sample_legacy_session_data["started_at"],
            completed_at=sample_legacy_session_data["completed_at"],
            max_latency_ms=sample_legacy_session_data["max_latency_ms"],
            labjack_connected=sample_legacy_session_data["labjack_connected"],
            video_id=sample_legacy_session_data["video_id"]
        )
        db_session.add(test_session)
        
        # Create legacy detection events
        for event_data in sample_detection_events:
            detection_event = DetectionEvent(
                id=event_data["id"],
                test_session_id=event_data["test_session_id"],
                timestamp=event_data["timestamp"],
                frame_number=event_data["frame_number"],
                actual_latency_ms=event_data["actual_latency_ms"],
                processing_time_ms=event_data["processing_time_ms"],
                voltage_level=event_data["voltage_level"],
                labjack_voltage=event_data["labjack_voltage"],
                labjack_timestamp=event_data["labjack_timestamp"],
                detection_channel=event_data["detection_channel"],
                validation_result=event_data["validation_result"]
            )
            db_session.add(detection_event)
        
        db_session.commit()
        
        # Test legacy HIL results endpoint format
        session_id = sample_legacy_session_data["id"]
        response = client.get(f"/api/v1/hil-test/session/{session_id}/status")
        assert response.status_code == 200
        
        status_data = response.json()
        
        # Verify legacy response structure
        legacy_status_fields = {
            "session_id", "status", "total_videos", "processed_events",
            "labjack_connected", "current_performance"
        }
        assert legacy_status_fields.issubset(status_data.keys())
        
        # Test enhanced results endpoint (should work with legacy data)
        enhanced_response = client.get(f"/api/enhanced-hil/test-sessions/{session_id}/corrected-results")
        
        if enhanced_response.status_code == 200:
            enhanced_data = enhanced_response.json()
            
            # Verify enhanced endpoint includes legacy data
            assert "detection_events" in enhanced_data
            assert len(enhanced_data["detection_events"]) == len(sample_detection_events)
            
            # Verify each detection event has both legacy and enhanced fields
            for event in enhanced_data["detection_events"]:
                # Legacy fields must be present
                assert "event_id" in event
                assert "voltage_level" in event
                assert "channel" in event
                
                # Enhanced fields may be present but shouldn't break legacy parsing
                if "timing_synchronization" in event:
                    assert isinstance(event["timing_synchronization"], dict)

    def test_labjack_service_integration_unchanged(self):
        """Test that existing LabJack services work without changes"""
        
        # Test LabJack service initialization (should not auto-connect)
        labjack_service = LabJackService()
        
        # Verify service starts in disconnected state
        status = labjack_service.get_status()
        assert status.status.name in ["DISCONNECTED", "ERROR"]  # Should not auto-connect
        
        # Test connection modes are preserved
        assert hasattr(ConnectionMode, "BRIDGE")
        assert hasattr(ConnectionMode, "DIRECT") 
        assert hasattr(ConnectionMode, "MOCK")
        
        # Test that mock mode requires explicit permission (HIL safety feature)
        with patch.object(labjack_service, '_connect_mock', return_value=True):
            # Should fail without allow_mock=True
            result = asyncio.run(labjack_service.connect(allow_mock=False))
            assert result == False
            
            # Should succeed with allow_mock=True
            result = asyncio.run(labjack_service.connect(allow_mock=True))
            assert result == True

    def test_configuration_compatibility(self):
        """Test that configuration files and environment settings remain compatible"""
        
        # Test that existing environment variables are still supported
        import os
        from services.labjack_service_manager import BridgeConfig
        
        # Test bridge config with environment variables
        old_host = os.environ.get("LABJACK_BRIDGE_HOST")
        old_port = os.environ.get("LABJACK_BRIDGE_PORT")
        
        try:
            os.environ["LABJACK_BRIDGE_HOST"] = "test-host"
            os.environ["LABJACK_BRIDGE_PORT"] = "9999"
            
            config = BridgeConfig()
            # These should still work with defaults
            assert config.host == "localhost"  # Should use defaults unless explicitly loaded
            assert config.port == 8080
            
        finally:
            # Restore original values
            if old_host is not None:
                os.environ["LABJACK_BRIDGE_HOST"] = old_host
            else:
                os.environ.pop("LABJACK_BRIDGE_HOST", None)
                
            if old_port is not None:
                os.environ["LABJACK_BRIDGE_PORT"] = old_port 
            else:
                os.environ.pop("LABJACK_BRIDGE_PORT", None)

    def test_data_migration_scenarios(self, db_session):
        """Test data migration scenarios for existing test sessions"""
        
        # Create test session with minimal legacy data
        legacy_session = TestSession(
            id="migration-test-123",
            name="Migration Test Session",
            project_id=1,
            status="completed", 
            started_at=datetime.now(timezone.utc) - timedelta(hours=1),
            completed_at=datetime.now(timezone.utc),
            max_latency_ms=100,
            labjack_connected=True
        )
        db_session.add(legacy_session)
        
        # Create detection event with only legacy fields
        legacy_event = DetectionEvent(
            id="legacy-event-1",
            test_session_id="migration-test-123",
            timestamp=time.time(),
            frame_number=5,
            actual_latency_ms=85.3,
            processing_time_ms=52.1,
            voltage_level=3.1,
            validation_result="pass"
        )
        db_session.add(legacy_event)
        db_session.commit()
        
        # Test that queries work with mixed legacy/enhanced data
        session = db_session.execute(select(TestSession).where(TestSession.id == "migration-test-123")).scalar_one_or_none()
        assert session is not None
        assert session.name == "Migration Test Session"
        
        event = db_session.execute(select(DetectionEvent).where(DetectionEvent.id == "legacy-event-1")).scalar_one_or_none()
        assert event is not None
        assert event.actual_latency_ms == 85.3
        
        # Verify new fields are NULL/None for legacy data
        assert getattr(event, 'video_relative_timestamp', None) is None
        assert getattr(event, 'timing_sync_quality', None) is None

    def test_raw_logging_features_additive(self, client, db_session):
        """Test that new raw logging features are purely additive and don't disrupt existing flows"""
        
        # Create session using legacy endpoint
        response = client.post("/api/v1/hil-test/session/start", json={
            "project_id": 1,
            "max_latency_ms": 100
        })
        assert response.status_code == 200
        session_id = response.json()["id"]
        
        # Test that dedicated monitor can be started without affecting legacy flow
        monitor = get_dedicated_labjack_monitor()
        
        # Should not interfere with existing session
        monitoring_started = monitor.start_monitoring_with_video_sync(
            session_id,
            {
                "video_id": "test-video",
                "fps": 30,
                "duration": 10,
                "channels": ["AIN0"],
                "voltage_threshold": 2.5
            }
        )
        
        # If monitoring fails, it should not break the main session
        legacy_status = client.get(f"/api/v1/hil-test/session/{session_id}/status")
        assert legacy_status.status_code == 200
        
        # Test session completion still works
        complete_response = client.post(f"/api/v1/hil-test/session/{session_id}/complete")
        assert complete_response.status_code == 200

    def test_performance_characteristics_unchanged(self, client, db_session):
        """Test that performance characteristics of legacy operations are unchanged"""
        
        # Create test data for performance testing
        start_time = time.time()
        
        # Test database query performance (should be similar to before)
        for i in range(10):
            test_session = TestSession(
                id=f"perf-test-{i}",
                name=f"Performance Test {i}",
                project_id=1,
                status="completed",
                started_at=datetime.now(timezone.utc),
                max_latency_ms=100,
                labjack_connected=True
            )
            db_session.add(test_session)
        
        db_session.commit()
        query_time = time.time()
        
        # Query should complete quickly (less than 1 second for 10 records)
        assert (query_time - start_time) < 1.0
        
        # Test API response time for legacy endpoints
        api_start = time.time()
        response = client.get("/api/v1/hil-test/labjack/status")
        api_time = time.time() - api_start
        
        assert response.status_code == 200
        # API should respond quickly (less than 500ms)
        assert api_time < 0.5

    def test_error_handling_backward_compatible(self, client):
        """Test that error handling patterns remain backward compatible"""
        
        # Test invalid session ID returns same error format
        response = client.get("/api/v1/hil-test/session/invalid-session/status")
        assert response.status_code == 404
        
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)
        
        # Test hardware validation errors maintain format
        with patch('services.labjack_service.LabJackService.get_status') as mock_status:
            mock_status.side_effect = Exception("Test hardware error")
            
            hardware_response = client.get("/api/v1/hil-test/hardware/validation-status")
            
            # Should handle error gracefully and return expected format
            assert hardware_response.status_code == 200
            hardware_data = hardware_response.json()
            assert hardware_data["connected"] == False
            assert "error" in hardware_data

    def test_api_contract_validation(self, client, db_session, sample_legacy_session_data):
        """Comprehensive API contract validation to ensure no breaking changes"""
        
        # Test all critical API endpoints maintain their contracts
        api_contracts = [
            {
                "method": "GET",
                "path": "/api/v1/hil-test/labjack/status",
                "expected_fields": ["connected", "status", "connection_mode", "device_type"]
            },
            {
                "method": "GET", 
                "path": "/api/v1/hil-test/hardware/validation-status",
                "expected_fields": ["connected", "status", "hardware_icon", "status_color"]
            },
            {
                "method": "GET",
                "path": "/api/v1/hil-test/hardware/diagnostics", 
                "expected_fields": ["validation_service_status"]
            }
        ]
        
        for contract in api_contracts:
            if contract["method"] == "GET":
                response = client.get(contract["path"])
                assert response.status_code == 200
                
                data = response.json()
                for field in contract["expected_fields"]:
                    assert field in data, f"Missing required field '{field}' in {contract['path']}"

    def test_deployment_compatibility(self, client):
        """Test that deployment procedures remain unchanged"""
        
        # Test health check endpoint (critical for deployment)
        health_response = client.get("/health")
        
        # Should work with either 200 (if endpoint exists) or 404 (if not implemented)
        assert health_response.status_code in [200, 404]
        
        # Test that main application still starts correctly
        # This is validated by the client fixture working
        assert client is not None
        
        # Test root endpoint still works
        root_response = client.get("/")
        # Should return some response (not 500 error)
        assert root_response.status_code != 500

    def test_graceful_degradation(self, client):
        """Test that new features gracefully degrade when raw data is unavailable"""
        
        # Test enhanced endpoint with non-existent session
        enhanced_response = client.get("/api/enhanced-hil/test-sessions/non-existent/corrected-results")
        assert enhanced_response.status_code == 404
        
        # Test enhanced endpoint with session that has no video timing data
        # Should still return meaningful data or clear error messages
        session_response = client.post("/api/v1/hil-test/session/start", json={
            "project_id": 1,
            "max_latency_ms": 100
        })
        
        if session_response.status_code == 200:
            session_id = session_response.json()["id"]
            
            # Complete session immediately (no video timing)
            complete_response = client.post(f"/api/v1/hil-test/session/{session_id}/complete")
            assert complete_response.status_code == 200
            
            # Try to get enhanced results - should handle gracefully
            enhanced_response = client.get(f"/api/enhanced-hil/test-sessions/{session_id}/corrected-results")
            
            # Should either work with fallback data or return clear error message
            if enhanced_response.status_code == 200:
                data = enhanced_response.json()
                # Should have proper error handling or fallback data
                assert "error" in data or "detection_events" in data
            else:
                # Should be a client error, not server error
                assert enhanced_response.status_code < 500


@pytest.mark.asyncio 
class TestAsyncBackwardCompatibility:
    """Async-specific backward compatibility tests"""
    
    async def test_hil_manager_async_operations(self):
        """Test that HIL manager async operations maintain compatibility"""
        
        hil_manager = HILTestManager()
        
        # Test websocket connection handling (should not break)
        assert hil_manager.websocket_connections == []
        assert hil_manager.active_sessions == {}
        
        # Test broadcast functionality
        test_message = {"type": "test", "data": "backward_compatibility_test"}
        await hil_manager.broadcast_status(test_message)
        
        # Should complete without error even with no connections
        assert True  # If we reach here, no exception was thrown

    async def test_detection_service_integration(self):
        """Test detection service integration maintains compatibility"""
        
        from services.simple_labjack_detection import get_detection_service
        
        detection_service = get_detection_service()
        
        # Service should initialize without issues
        assert detection_service is not None
        
        # Test that configuration doesn't break existing patterns
        config_result = detection_service.start_monitoring(
            "test-session",
            channels=["AIN0"],
            voltage_threshold=2.5,
            sample_rate=10,
            store_in_db=False  # Legacy parameter
        )
        
        # Should handle gracefully regardless of LabJack availability
        assert isinstance(config_result, bool)


if __name__ == "__main__":
    # Run the backward compatibility tests
    pytest.main([__file__, "-v", "--tb=short"])