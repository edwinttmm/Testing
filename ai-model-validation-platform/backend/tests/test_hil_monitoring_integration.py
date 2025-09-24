"""
HIL Monitoring Integration Tests
===============================

Tests for the fixed HIL test session workflow with dedicated monitoring service.
Verifies that sessions properly integrate with monitoring and create detection events.
"""

import pytest
import asyncio
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

# Test imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.dedicated_monitoring_service import DedicatedMonitoringService, MonitoringServiceIPC
from services.monitoring_service_client import MonitoringServiceClient, MonitoringServiceManager
from services.monitoring_process_manager import MonitoringProcessManager
from routers.test_sessions_fixed import start_test_session, complete_test_session

class TestMonitoringServiceIPC:
    """Test IPC communication between main app and monitoring service"""
    
    @pytest.mark.asyncio
    async def test_ipc_message_handling(self):
        """Test basic IPC message handling"""
        service = DedicatedMonitoringService()
        
        # Test get_status command
        response = await service.handle_ipc_message({"command": "get_status"})
        assert "monitoring_active" in response
        assert "timestamp" in response
        
    @pytest.mark.asyncio
    async def test_start_monitoring_command(self):
        """Test start monitoring IPC command"""
        service = DedicatedMonitoringService()
        session_id = str(uuid.uuid4())
        
        # Mock signal service
        service.signal_service = Mock()
        service.signal_service.read_voltage_signal.return_value = {"success": True, "voltage": 4.2}
        
        # Start monitoring
        response = await service.handle_ipc_message({
            "command": "start_monitoring",
            "session_id": session_id,
            "sample_rate": 10
        })
        
        assert response["status"] == "started"
        assert response["session_id"] == session_id
        assert service.monitoring_active == True
        
        # Stop monitoring
        stop_response = await service.handle_ipc_message({"command": "stop_monitoring"})
        assert stop_response["status"] == "stopped"
        assert service.monitoring_active == False

class TestMonitoringServiceClient:
    """Test monitoring service client functionality"""
    
    @pytest.mark.asyncio
    async def test_client_command_sending(self):
        """Test client IPC command sending with mock socket"""
        client = MonitoringServiceClient()
        
        # Mock socket communication
        mock_response = {"status": "started", "session_id": "test-123"}
        
        with patch('socket.socket') as mock_socket:
            mock_conn = Mock()
            mock_conn.recv.return_value = json.dumps(mock_response).encode('utf-8')
            mock_socket.return_value = mock_conn
            
            response = await client.start_monitoring("test-123", sample_rate=10)
            
            assert response == mock_response
            mock_conn.send.assert_called_once()
            mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio  
    async def test_service_availability_check(self):
        """Test service availability checking"""
        manager = MonitoringServiceManager()
        
        # Mock successful health check
        with patch.object(manager.client, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"service_status": "healthy"}
            
            available = await manager.client.is_service_available()
            assert available == True
            
        # Mock failed health check
        with patch.object(manager.client, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.side_effect = Exception("Service not available")
            
            available = await manager.client.is_service_available()
            assert available == False

class TestProcessManager:
    """Test monitoring service process management"""
    
    @pytest.mark.asyncio
    async def test_process_lifecycle(self):
        """Test process start/stop lifecycle"""
        manager = MonitoringProcessManager()
        
        # Mock subprocess
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process running
        
        with patch('subprocess.Popen', return_value=mock_process):
            with patch.object(manager.client, 'wait_for_service', new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = True
                
                # Test start
                result = await manager.start_service()
                assert result["success"] == True
                assert result["pid"] == 12345
                
        # Test stop
        with patch('os.killpg') as mock_kill:
            mock_process.wait.return_value = None
            
            result = await manager.stop_service()
            assert result["success"] == True

class TestSessionIntegration:
    """Test complete HIL session integration"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        from sqlalchemy.orm import Session
        from models import TestSession, Project
        
        session = Mock(spec=Session)
        
        # Mock test session
        test_session = Mock()
        test_session.id = "test-session-123"
        test_session.status = "created"
        test_session.project_id = "project-123"
        test_session.started_at = None
        test_session.completed_at = None
        
        # Mock project
        project = Mock()
        project.id = "project-123"
        project.name = "Test Project"
        
        session.query.return_value.filter.return_value.first.return_value = test_session
        session.commit.return_value = None
        
        return session, test_session
    
    @pytest.mark.asyncio
    async def test_session_start_with_monitoring(self, mock_db_session):
        """Test session start with monitoring service integration"""
        db_session, test_session = mock_db_session
        
        # Mock monitoring service manager
        with patch('routers.test_sessions_fixed.monitoring_service_manager') as mock_manager:
            mock_manager.start_session_monitoring = AsyncMock(return_value={
                "success": True,
                "session_id": "test-session-123",
                "message": "Monitoring started"
            })
            
            # Mock background tasks
            background_tasks = Mock()
            
            # Start session
            response = await start_test_session(
                session_id="test-session-123",
                background_tasks=background_tasks,
                db=db_session
            )
            
            # Verify response
            assert response["status"] == "running"
            assert response["session_id"] == "test-session-123"
            assert response["monitoring"]["dedicated_service"] == True
            
            # Verify session was updated
            assert test_session.status == "running"
            assert test_session.started_at is not None
            
            # Verify monitoring was started
            mock_manager.start_session_monitoring.assert_called_once_with(
                session_id="test-session-123",
                sample_rate=10,
                wait_for_service=True
            )
    
    @pytest.mark.asyncio
    async def test_session_completion_with_detections(self, mock_db_session):
        """Test session completion with detection events and TestResult creation"""
        db_session, test_session = mock_db_session
        
        # Set session as running
        test_session.status = "running"
        test_session.started_at = datetime.utcnow()
        
        # Mock detection events query
        from models import DetectionEvent
        mock_detections = [
            Mock(validation_result="passed", processing_time_ms=5.0),
            Mock(validation_result="passed", processing_time_ms=4.8),
            Mock(validation_result="failed", processing_time_ms=5.2),
        ]
        
        db_session.query.return_value.filter.return_value.scalar.return_value = 3  # detection count
        db_session.query.return_value.filter.return_value.all.return_value = mock_detections
        
        # Mock monitoring service manager
        with patch('routers.test_sessions_fixed.monitoring_service_manager') as mock_manager:
            mock_manager.stop_session_monitoring = AsyncMock(return_value={
                "success": True,
                "session_id": "test-session-123",
                "detection_count": 3,
                "message": "Monitoring stopped"
            })
            
            # Complete session
            response = await complete_test_session(
                session_id="test-session-123",
                db=db_session
            )
            
            # Verify response
            assert response["status"] == "completed"
            assert response["total_detections"] == 3
            assert response["test_result_created"] == True
            assert response["monitoring_service"] == "dedicated"
            
            # Verify session was updated
            assert test_session.status == "completed"
            assert test_session.completed_at is not None
            
            # Verify TestResult was created
            db_session.add.assert_called_once()
            test_result = db_session.add.call_args[0][0]
            assert test_result.total_detections == 3
            assert test_result.passed_detections == 2
            assert test_result.failed_detections == 1
    
    @pytest.mark.asyncio
    async def test_monitoring_service_fallback(self, mock_db_session):
        """Test fallback to legacy monitoring when dedicated service fails"""
        db_session, test_session = mock_db_session
        
        # Mock dedicated monitoring failure
        with patch('routers.test_sessions_fixed.monitoring_service_manager') as mock_manager:
            mock_manager.start_session_monitoring = AsyncMock(return_value={
                "success": False,
                "error": "Service not available",
                "fallback": "Session proceeding without monitoring"
            })
            
            # Mock legacy monitoring success
            with patch('routers.test_sessions_fixed.labjack_monitoring_service') as mock_legacy:
                mock_legacy.start_monitoring.return_value = True
                
                background_tasks = Mock()
                
                # Start session
                response = await start_test_session(
                    session_id="test-session-123",
                    background_tasks=background_tasks,
                    db=db_session
                )
                
                # Verify fallback was used
                assert response["monitoring"]["dedicated_service"] == False
                assert response["monitoring"]["fallback_active"] == True
                assert response["monitoring"]["error"] is not None

class TestDetectionEventStorage:
    """Test detection event storage in monitoring service"""
    
    def test_detection_event_storage(self):
        """Test that detection events are stored correctly"""
        service = DedicatedMonitoringService()
        
        # Mock database connection
        import sqlite3
        with patch('sqlite3.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            # Store detection event
            service._store_detection_event(
                session_id="test-session-123",
                voltage=4.2,
                timestamp=time.time(),
                channel="AIN0"
            )
            
            # Verify database insert
            mock_cursor.execute.assert_called_once()
            sql, params = mock_cursor.execute.call_args
            
            assert "INSERT INTO detection_events" in sql[0]
            assert params[1] == "test-session-123"  # session_id
            assert params[3] == 4.2  # voltage stored as confidence
            assert "passed" in params[5]  # validation_result for 4.2V > 3.0V

class TestHealthMonitoring:
    """Test health monitoring and recovery functionality"""
    
    @pytest.mark.asyncio
    async def test_health_check_monitoring(self):
        """Test health check and auto-restart functionality"""
        manager = MonitoringProcessManager()
        
        # Mock process running but service unresponsive
        manager.process = Mock()
        manager.process.poll.return_value = None  # Process running
        
        with patch.object(manager.client, 'health_check', new_callable=AsyncMock) as mock_health:
            mock_health.side_effect = [
                Exception("Service not responding"),  # First check fails
                Exception("Service not responding"),  # Second check fails  
                Exception("Service not responding"),  # Third check fails
            ]
            
            with patch.object(manager, 'restart_service', new_callable=AsyncMock) as mock_restart:
                mock_restart.return_value = {"success": True}
                
                # Start health monitoring task
                manager._health_check_interval = 0.1  # Fast for testing
                task = asyncio.create_task(manager._health_monitor_loop())
                
                # Let it run briefly
                await asyncio.sleep(0.5)
                task.cancel()
                
                # Verify restart was called due to consecutive failures
                mock_restart.assert_called()

# Integration test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])