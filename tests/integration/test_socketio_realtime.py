"""
Integration tests for Socket.IO real-time notifications with database events
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, Mock


class TestSocketIORealTimeNotifications:
    """Test real-time notifications through Socket.IO"""
    
    @pytest.mark.asyncio
    async def test_video_upload_notification(self, socketio_test_client, test_client, created_project, sample_test_video_file, mock_socketio):
        """Test real-time notification when video is uploaded"""
        received_events = []
        
        # Mock socketio emit
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        # Upload video
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("realtime_test.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            with patch('socketio_server.sio', mock_socketio):
                response = test_client.post("/upload-video", files=files, data=data)
        
        assert response.status_code == 200
        
        # Verify notification was sent
        upload_events = [e for e in received_events if e['event'] == 'video_uploaded']
        assert len(upload_events) > 0
        
        upload_event = upload_events[0]
        assert 'data' in upload_event
        assert 'videoId' in upload_event['data']
        assert 'projectId' in upload_event['data']
    
    @pytest.mark.asyncio
    async def test_processing_status_notifications(self, mock_socketio, test_db_session, created_video):
        """Test notifications when processing status changes"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        # Simulate processing status changes
        with patch('socketio_server.sio', mock_socketio):
            # Change to processing
            created_video.processing_status = "processing"
            test_db_session.commit()
            
            # Manually trigger notification (in real app this would be automatic)
            from socketio_server import notify_processing_status_change
            await notify_processing_status_change(created_video.id, "processing")
            
            # Change to completed
            created_video.processing_status = "completed"
            created_video.ground_truth_generated = True
            test_db_session.commit()
            
            await notify_processing_status_change(created_video.id, "completed")
        
        # Verify notifications were sent
        status_events = [e for e in received_events if e['event'] == 'processing_status_update']
        assert len(status_events) >= 2
        
        processing_event = next((e for e in status_events if e['data']['status'] == 'processing'), None)
        completed_event = next((e for e in status_events if e['data']['status'] == 'completed'), None)
        
        assert processing_event is not None
        assert completed_event is not None
        assert completed_event['data']['groundTruthGenerated'] is True
    
    @pytest.mark.asyncio
    async def test_ground_truth_generation_notifications(self, mock_socketio, created_video):
        """Test notifications during ground truth generation"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Simulate ground truth generation start
            from socketio_server import notify_ground_truth_progress
            await notify_ground_truth_progress(created_video.id, "started", 0)
            
            # Simulate progress updates
            for progress in [25, 50, 75, 100]:
                await notify_ground_truth_progress(created_video.id, "processing", progress)
            
            # Simulate completion
            await notify_ground_truth_progress(created_video.id, "completed", 100)
        
        # Verify progress notifications
        progress_events = [e for e in received_events if e['event'] == 'ground_truth_progress']
        assert len(progress_events) >= 5  # start + 4 progress + completion
        
        # Check progress sequence
        start_event = progress_events[0]
        assert start_event['data']['status'] == 'started'
        assert start_event['data']['progress'] == 0
        
        completion_event = progress_events[-1]
        assert completion_event['data']['status'] == 'completed'
        assert completion_event['data']['progress'] == 100
    
    @pytest.mark.asyncio
    async def test_test_session_notifications(self, mock_socketio, test_db_session, created_test_session):
        """Test notifications for test session events"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Simulate test session start
            from socketio_server import notify_test_session_event
            await notify_test_session_event(created_test_session.id, "started")
            
            # Simulate detection events
            for i in range(5):
                await notify_test_session_event(
                    created_test_session.id, 
                    "detection", 
                    {"timestamp": i * 1.0, "confidence": 0.9 - i * 0.1}
                )
            
            # Simulate completion
            await notify_test_session_event(created_test_session.id, "completed")
        
        # Verify test session events
        session_events = [e for e in received_events if e['event'] == 'test_session_update']
        assert len(session_events) >= 7  # start + 5 detections + completion
        
        start_event = next((e for e in session_events if e['data']['type'] == 'started'), None)
        assert start_event is not None
        
        detection_events = [e for e in session_events if e['data']['type'] == 'detection']
        assert len(detection_events) == 5
    
    @pytest.mark.asyncio
    async def test_error_notifications(self, mock_socketio, created_video):
        """Test error notifications"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Simulate processing error
            from socketio_server import notify_error
            await notify_error(
                "processing_error", 
                "Failed to process video", 
                {"videoId": created_video.id}
            )
            
            # Simulate validation error
            await notify_error(
                "validation_error",
                "Invalid file format",
                {"filename": "invalid.txt"}
            )
        
        # Verify error notifications
        error_events = [e for e in received_events if e['event'] == 'error']
        assert len(error_events) == 2
        
        processing_error = next((e for e in error_events if e['data']['type'] == 'processing_error'), None)
        validation_error = next((e for e in error_events if e['data']['type'] == 'validation_error'), None)
        
        assert processing_error is not None
        assert validation_error is not None
        assert processing_error['data']['message'] == "Failed to process video"


class TestSocketIOConnectionManagement:
    """Test Socket.IO connection management"""
    
    @pytest.mark.asyncio
    async def test_client_connection_handling(self, mock_socketio):
        """Test client connection and disconnection"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        mock_socketio.enter_room = AsyncMock()
        mock_socketio.leave_room = AsyncMock()
        
        with patch('socketio_server.sio', mock_socketio):
            # Simulate client connection
            from socketio_server import handle_connect
            await handle_connect("session_123", environ={})
            
            # Simulate client joining project room
            from socketio_server import handle_join_project
            await handle_join_project("session_123", {"projectId": "project_456"})
            
            # Simulate client disconnection
            from socketio_server import handle_disconnect
            await handle_disconnect("session_123")
        
        # Verify room management
        mock_socketio.enter_room.assert_called()
        mock_socketio.leave_room.assert_called()
    
    @pytest.mark.asyncio
    async def test_room_based_notifications(self, mock_socketio, created_project):
        """Test room-based notification targeting"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Send project-specific notification
            from socketio_server import notify_project_event
            await notify_project_event(
                created_project.id, 
                "video_uploaded", 
                {"videoId": "video_123"}
            )
        
        # Verify room targeting
        project_events = [e for e in received_events if e['room'] == f"project_{created_project.id}"]
        assert len(project_events) == 1
        assert project_events[0]['event'] == 'video_uploaded'
    
    @pytest.mark.asyncio
    async def test_broadcast_notifications(self, mock_socketio):
        """Test broadcast notifications to all clients"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Send system-wide notification
            from socketio_server import notify_system_event
            await notify_system_event("maintenance", {"message": "System maintenance in 5 minutes"})
        
        # Verify broadcast
        system_events = [e for e in received_events if e['event'] == 'system_notification']
        assert len(system_events) == 1
        assert system_events[0]['data']['message'] == "System maintenance in 5 minutes"


class TestSocketIOPerformance:
    """Test Socket.IO performance and scalability"""
    
    @pytest.mark.asyncio
    async def test_multiple_simultaneous_notifications(self, mock_socketio):
        """Test handling multiple simultaneous notifications"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
            # Simulate slight delay
            await asyncio.sleep(0.001)
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Send many notifications simultaneously
            from socketio_server import notify_processing_status_change
            
            tasks = []
            for i in range(100):
                task = notify_processing_status_change(f"video_{i}", "processing")
                tasks.append(task)
            
            await asyncio.gather(*tasks)
        
        # All notifications should be sent
        assert len(received_events) == 100
        assert all(e['event'] == 'processing_status_update' for e in received_events)
    
    @pytest.mark.asyncio
    async def test_notification_ordering(self, mock_socketio, created_video):
        """Test that notifications maintain proper ordering"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Send sequential status updates
            from socketio_server import notify_processing_status_change
            
            statuses = ["pending", "processing", "completed"]
            for status in statuses:
                await notify_processing_status_change(created_video.id, status)
        
        # Verify ordering
        assert len(received_events) == 3
        assert received_events[0]['data']['status'] == 'pending'
        assert received_events[1]['data']['status'] == 'processing'
        assert received_events[2]['data']['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_error_handling_in_notifications(self, mock_socketio):
        """Test error handling in notification system"""
        # Simulate socketio emit failure
        async def failing_emit(event, data, room=None):
            raise Exception("Socket.IO connection lost")
        
        mock_socketio.emit = failing_emit
        
        with patch('socketio_server.sio', mock_socketio):
            # Should not raise exception
            from socketio_server import notify_processing_status_change
            try:
                await notify_processing_status_change("video_123", "processing")
                # Should handle error gracefully
                assert True
            except Exception:
                pytest.fail("Notification error should be handled gracefully")


class TestSocketIODataIntegrity:
    """Test data integrity in Socket.IO notifications"""
    
    @pytest.mark.asyncio
    async def test_notification_data_structure(self, mock_socketio, created_video):
        """Test that notification data has correct structure"""
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({'event': event, 'data': data, 'room': room})
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            from socketio_server import notify_processing_status_change
            await notify_processing_status_change(created_video.id, "completed")
        
        # Verify data structure
        assert len(received_events) == 1
        event_data = received_events[0]['data']
        
        required_fields = ['videoId', 'status', 'timestamp']
        for field in required_fields:
            assert field in event_data, f"Missing required field: {field}"
        
        assert event_data['videoId'] == created_video.id
        assert event_data['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_notification_timestamp_accuracy(self, mock_socketio):
        """Test that notification timestamps are accurate"""
        import time
        received_events = []
        
        async def capture_emit(event, data, room=None):
            received_events.append({
                'event': event, 
                'data': data, 
                'room': room,
                'received_at': time.time()
            })
        
        mock_socketio.emit = capture_emit
        
        with patch('socketio_server.sio', mock_socketio):
            send_time = time.time()
            from socketio_server import notify_processing_status_change
            await notify_processing_status_change("video_123", "processing")
        
        # Verify timestamp accuracy
        event = received_events[0]
        notification_time = event['data']['timestamp']
        received_time = event['received_at']
        
        # Timestamps should be close (within 1 second)
        assert abs(notification_time - send_time) < 1.0
        assert abs(received_time - send_time) < 1.0