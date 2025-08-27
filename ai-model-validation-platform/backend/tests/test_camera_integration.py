"""
Comprehensive Integration Tests for Camera Integration System
Tests all components of the camera integration and real-time validation system
"""
import asyncio
import pytest
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
import websockets
import httpx

# Import our camera integration components
import sys
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend/src')

from camera_integration_service import (
    CameraIntegrationService, CameraConfig, CameraFrame, ValidationResult,
    CameraSignalProcessor, ValidationEngine, CircularBuffer
)
from camera_config_manager import (
    CameraConfigManager, CompleteCameraConfig, CameraHardwareConfig,
    NetworkConfig, CameraConnectionConfig, CameraProcessingConfig
)
from camera_websocket_handlers import CameraWebSocketManager, CameraWebSocketHandler
from camera_integration_api import camera_api_router

@pytest.fixture
def camera_service():
    """Fixture for camera integration service"""
    return CameraIntegrationService()

@pytest.fixture
def config_manager():
    """Fixture for camera config manager"""
    return CameraConfigManager(storage_path="test_camera_configs", external_ip="155.138.239.131")

@pytest.fixture
def ws_manager():
    """Fixture for WebSocket manager"""
    return CameraWebSocketManager()

@pytest.fixture
def sample_camera_config():
    """Sample camera configuration for testing"""
    return CameraConfig(
        camera_id="test_camera_001",
        camera_type="ip_camera",
        connection_url="155.138.239.131:8080",
        format="mjpeg",
        resolution=(1920, 1080),
        fps=30,
        buffer_size=50,
        timeout_ms=5000,
        external_ip="155.138.239.131",
        enabled=True,
        validation_enabled=True
    )

@pytest.fixture
def sample_complete_config():
    """Sample complete camera configuration"""
    hardware = CameraHardwareConfig(
        camera_id="test_camera_complete",
        display_name="Test Camera Complete",
        camera_type="ip_camera",
        capabilities=["video_streaming", "real_time_processing"]
    )
    
    network = NetworkConfig(external_ip="155.138.239.131")
    
    connection = CameraConnectionConfig(
        connection_type="tcp",
        connection_url="155.138.239.131:8080",
        protocol="mjpeg"
    )
    
    processing = CameraProcessingConfig(
        validation_enabled=True,
        buffer_size=100,
        target_fps=30,
        resolution=(1920, 1080)
    )
    
    return CompleteCameraConfig(
        camera_id="test_camera_complete",
        hardware=hardware,
        network=network,
        connection=connection,
        processing=processing,
        enabled=True
    )

class TestCameraIntegrationService:
    """Test camera integration service"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, camera_service):
        """Test service initialization"""
        await camera_service.initialize("155.138.239.131")
        
        assert camera_service.running == True
        assert camera_service.external_ip == "155.138.239.131"
        assert len(camera_service.cameras) > 0  # Default cameras should be added
        assert "main_camera" in camera_service.cameras
        assert "gpio_sensor" in camera_service.cameras
        assert "network_monitor" in camera_service.cameras
        
        await camera_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_add_remove_camera(self, camera_service, sample_camera_config):
        """Test adding and removing cameras"""
        await camera_service.initialize()
        
        # Test adding camera
        success = await camera_service.add_camera(sample_camera_config)
        assert success == True
        assert sample_camera_config.camera_id in camera_service.cameras
        assert sample_camera_config.camera_id in camera_service.buffers
        
        # Test removing camera
        success = await camera_service.remove_camera(sample_camera_config.camera_id)
        assert success == True
        assert sample_camera_config.camera_id not in camera_service.cameras
        assert sample_camera_config.camera_id not in camera_service.buffers
        
        await camera_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_camera_processing_loop(self, camera_service, sample_camera_config):
        """Test camera processing loop"""
        await camera_service.initialize()
        
        # Add camera
        await camera_service.add_camera(sample_camera_config)
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Check that frames are being processed
        buffer = camera_service.buffers[sample_camera_config.camera_id]
        stats = buffer.get_stats()
        
        assert stats["total_frames"] > 0
        assert stats["current_size"] >= 0
        
        # Check service stats
        service_stats = camera_service.get_service_stats()
        assert service_stats["total_frames_processed"] > 0
        assert service_stats["active_cameras"] > 0
        
        await camera_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_websocket_integration(self, camera_service):
        """Test WebSocket integration"""
        await camera_service.initialize()
        
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "127.0.0.1"
        
        # Test connection
        client_id = await camera_service.connect_websocket(mock_websocket)
        assert client_id is not None
        assert client_id in camera_service.websocket_clients
        
        # Test disconnection
        camera_service.disconnect_websocket(client_id)
        assert client_id not in camera_service.websocket_clients
        
        await camera_service.shutdown()

class TestCameraSignalProcessor:
    """Test camera signal processor"""
    
    @pytest.mark.asyncio
    async def test_gpio_signal_processing(self):
        """Test GPIO signal processing"""
        processor = CameraSignalProcessor()
        
        config = CameraConfig(
            camera_id="test_gpio",
            camera_type="gpio_trigger",
            connection_url="GPIO18",
            format="signal",
            external_ip="155.138.239.131"
        )
        
        # Test high signal
        frame = await processor.process_frame(config, b'\x01')
        assert frame.camera_id == "test_gpio"
        assert frame.signal_type == "GPIO"
        assert isinstance(frame.data, dict)
        assert frame.data["state"] == "high"
        
        # Test low signal
        frame = await processor.process_frame(config, b'\x00')
        assert frame.data["state"] == "low"
    
    @pytest.mark.asyncio
    async def test_network_signal_processing(self):
        """Test network signal processing"""
        processor = CameraSignalProcessor()
        
        config = CameraConfig(
            camera_id="test_network",
            camera_type="network_packet",
            connection_url="155.138.239.131:9090",
            format="signal",
            external_ip="155.138.239.131"
        )
        
        test_data = b"TEST_PACKET_DATA"
        frame = await processor.process_frame(config, test_data)
        
        assert frame.camera_id == "test_network"
        assert frame.signal_type == "Network"
        assert isinstance(frame.data, dict)
        assert frame.data["size"] == len(test_data)
        assert frame.data["source_ip"] == "155.138.239.131"
    
    @pytest.mark.asyncio
    async def test_ip_camera_processing(self):
        """Test IP camera frame processing"""
        processor = CameraSignalProcessor()
        
        config = CameraConfig(
            camera_id="test_ip_camera",
            camera_type="ip_camera",
            connection_url="155.138.239.131:8080",
            format="mjpeg",
            resolution=(1920, 1080),
            external_ip="155.138.239.131"
        )
        
        test_frame_data = b"FAKE_MJPEG_FRAME_DATA"
        frame = await processor.process_frame(config, test_frame_data)
        
        assert frame.camera_id == "test_ip_camera"
        assert frame.data == test_frame_data
        assert frame.metadata["source"] == "ip_camera"
        assert frame.metadata["external_ip"] == "155.138.239.131"

class TestValidationEngine:
    """Test validation engine"""
    
    @pytest.mark.asyncio
    async def test_signal_frame_validation(self):
        """Test signal frame validation"""
        engine = ValidationEngine()
        
        # Create test signal frame
        frame = CameraFrame(
            camera_id="test_signal",
            timestamp=time.time(),
            frame_id="test_frame_001",
            data={"signal_type": "GPIO", "state": "high"},
            metadata={"source": "gpio_trigger"},
            signal_type="GPIO"
        )
        
        result = await engine.validate_frame(frame)
        
        assert isinstance(result, ValidationResult)
        assert result.frame_id == "test_frame_001"
        assert result.camera_id == "test_signal"
        assert result.validation_passed == True
        assert result.confidence_score > 0.9
        assert len(result.detected_objects) > 0
    
    @pytest.mark.asyncio
    async def test_video_frame_validation(self):
        """Test video frame validation"""
        engine = ValidationEngine()
        
        # Create test video frame
        frame = CameraFrame(
            camera_id="test_video",
            timestamp=time.time(),
            frame_id="test_frame_002",
            data=b"FAKE_VIDEO_FRAME_DATA",
            metadata={"source": "ip_camera"}
        )
        
        result = await engine.validate_frame(frame)
        
        assert isinstance(result, ValidationResult)
        assert result.frame_id == "test_frame_002"
        assert result.camera_id == "test_video"
        assert isinstance(result.detected_objects, list)
        assert result.processing_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_validation_caching(self):
        """Test validation result caching"""
        engine = ValidationEngine()
        
        frame = CameraFrame(
            camera_id="test_cache",
            timestamp=time.time(),
            frame_id="test_cache_frame",
            data=b"TEST_DATA",
            metadata={"source": "test"}
        )
        
        # First validation
        start_time = time.time()
        result1 = await engine.validate_frame(frame)
        first_duration = time.time() - start_time
        
        # Second validation (should use cache)
        start_time = time.time()
        result2 = await engine.validate_frame(frame)
        second_duration = time.time() - start_time
        
        assert result1.frame_id == result2.frame_id
        assert result1.confidence_score == result2.confidence_score
        # Second call should be faster due to caching
        assert second_duration < first_duration

class TestCircularBuffer:
    """Test circular buffer implementation"""
    
    def test_buffer_operations(self):
        """Test buffer put/get operations"""
        buffer = CircularBuffer(maxsize=5)
        
        # Test putting frames
        for i in range(3):
            frame = CameraFrame(
                camera_id="test",
                timestamp=time.time(),
                frame_id=f"frame_{i}",
                data=f"data_{i}",
                metadata={}
            )
            success = buffer.put(frame)
            assert success == True
        
        stats = buffer.get_stats()
        assert stats["current_size"] == 3
        assert stats["total_frames"] == 3
        assert stats["dropped_frames"] == 0
        
        # Test getting frames
        frame = buffer.get()
        assert frame is not None
        assert frame.frame_id == "frame_0"
        
        stats = buffer.get_stats()
        assert stats["current_size"] == 2
    
    def test_buffer_overflow(self):
        """Test buffer overflow behavior"""
        buffer = CircularBuffer(maxsize=3)
        
        # Fill buffer beyond capacity
        for i in range(5):
            frame = CameraFrame(
                camera_id="test",
                timestamp=time.time(),
                frame_id=f"frame_{i}",
                data=f"data_{i}",
                metadata={}
            )
            buffer.put(frame)
        
        stats = buffer.get_stats()
        assert stats["current_size"] == 3  # Maximum size
        assert stats["total_frames"] == 5
        assert stats["dropped_frames"] == 2
        assert stats["drop_rate"] == 0.4  # 2/5
    
    def test_peek_latest(self):
        """Test peek latest functionality"""
        buffer = CircularBuffer(maxsize=5)
        
        # Empty buffer
        latest = buffer.peek_latest()
        assert latest is None
        
        # Add frames
        for i in range(3):
            frame = CameraFrame(
                camera_id="test",
                timestamp=time.time(),
                frame_id=f"frame_{i}",
                data=f"data_{i}",
                metadata={}
            )
            buffer.put(frame)
        
        # Peek should return latest frame without removing it
        latest = buffer.peek_latest()
        assert latest is not None
        assert latest.frame_id == "frame_2"
        
        # Buffer size should remain unchanged
        stats = buffer.get_stats()
        assert stats["current_size"] == 3

class TestCameraConfigManager:
    """Test camera configuration manager"""
    
    def test_create_default_config(self, config_manager):
        """Test creating default configuration"""
        config = config_manager.create_default_config("test_default", "ip_camera")
        
        assert config.camera_id == "test_default"
        assert config.hardware.camera_type == "ip_camera"
        assert config.network.external_ip == "155.138.239.131"
        assert config.enabled == True
        assert config.processing.validation_enabled == True
    
    def test_save_load_config(self, config_manager, sample_complete_config):
        """Test saving and loading configuration"""
        # Save config
        success, errors = config_manager.save_config(sample_complete_config)
        assert success == True
        assert len(errors) == 0
        
        # Load config
        loaded_config = config_manager.load_config(sample_complete_config.camera_id)
        assert loaded_config is not None
        assert loaded_config.camera_id == sample_complete_config.camera_id
        assert loaded_config.hardware.camera_type == sample_complete_config.hardware.camera_type
        assert loaded_config.network.external_ip == sample_complete_config.network.external_ip
    
    def test_config_validation(self, config_manager, sample_complete_config):
        """Test configuration validation"""
        # Valid config
        is_valid, errors = config_manager.validate_config(sample_complete_config)
        assert is_valid == True
        assert len(errors) == 0
        
        # Invalid config (empty camera ID)
        invalid_config = sample_complete_config
        invalid_config.camera_id = ""
        
        is_valid, errors = config_manager.validate_config(invalid_config)
        assert is_valid == False
        assert len(errors) > 0
    
    def test_list_cameras(self, config_manager, sample_complete_config):
        """Test listing cameras"""
        # Save test config
        config_manager.save_config(sample_complete_config)
        
        # List all cameras
        camera_ids = config_manager.list_cameras()
        assert sample_complete_config.camera_id in camera_ids
        
        # List enabled cameras only
        enabled_cameras = config_manager.list_cameras(enabled_only=True)
        assert sample_complete_config.camera_id in enabled_cameras
    
    def test_update_external_ip(self, config_manager, sample_complete_config):
        """Test updating external IP"""
        # Save initial config
        config_manager.save_config(sample_complete_config)
        
        # Update external IP
        updated_count = config_manager.update_external_ip("192.168.1.100")
        assert updated_count == 1
        
        # Verify update
        loaded_config = config_manager.load_config(sample_complete_config.camera_id)
        assert loaded_config.network.external_ip == "192.168.1.100"

class TestCameraWebSocketManager:
    """Test camera WebSocket manager"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, ws_manager):
        """Test WebSocket connection management"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "127.0.0.1"
        
        # Test connection
        client_id = await ws_manager.connect(mock_websocket)
        assert client_id is not None
        assert client_id in ws_manager.active_connections
        
        # Test disconnection
        ws_manager.disconnect(client_id)
        assert client_id not in ws_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_camera_subscription(self, ws_manager, camera_service, sample_camera_config):
        """Test camera subscription functionality"""
        # Initialize camera service with test camera
        await camera_service.initialize()
        await camera_service.add_camera(sample_camera_config)
        
        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        mock_websocket.client = MagicMock()
        mock_websocket.client.host = "127.0.0.1"
        
        client_id = await ws_manager.connect(mock_websocket)
        
        # Test subscription
        success = await ws_manager.subscribe_to_camera(client_id, sample_camera_config.camera_id)
        assert success == True
        assert client_id in ws_manager.get_camera_subscribers(sample_camera_config.camera_id)
        
        # Test unsubscription
        ws_manager._unsubscribe_from_camera(client_id, sample_camera_config.camera_id)
        assert client_id not in ws_manager.get_camera_subscribers(sample_camera_config.camera_id)
        
        await camera_service.shutdown()
    
    def test_websocket_stats(self, ws_manager):
        """Test WebSocket statistics"""
        stats = ws_manager.get_stats()
        
        assert "active_connections" in stats
        assert "camera_subscriptions" in stats
        assert "total_subscriptions" in stats
        assert "cameras_with_subscribers" in stats

class TestIntegrationScenarios:
    """Test end-to-end integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_full_camera_lifecycle(self, camera_service, config_manager):
        """Test complete camera lifecycle"""
        # Initialize service
        await camera_service.initialize("155.138.239.131")
        
        # Create and add camera configuration
        complete_config = config_manager.create_default_config("lifecycle_test", "ip_camera")
        config_manager.save_config(complete_config, "Lifecycle test")
        
        # Convert to legacy config for service
        legacy_config = CameraConfig(
            camera_id="lifecycle_test",
            camera_type="ip_camera",
            connection_url="155.138.239.131:8080",
            format="mjpeg",
            resolution=(1920, 1080),
            fps=30,
            buffer_size=100,
            external_ip="155.138.239.131"
        )
        
        # Add camera to service
        success = await camera_service.add_camera(legacy_config)
        assert success == True
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Check camera status
        status = await camera_service.get_camera_status("lifecycle_test")
        assert status["camera_id"] == "lifecycle_test"
        assert status["is_running"] == True
        
        # Check that frames are being processed
        buffer_stats = status["buffer_stats"]
        assert buffer_stats["total_frames"] > 0
        
        # Remove camera
        success = await camera_service.remove_camera("lifecycle_test")
        assert success == True
        
        # Clean up
        config_manager.delete_config("lifecycle_test")
        await camera_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_multi_camera_scenario(self, camera_service):
        """Test multiple cameras running simultaneously"""
        await camera_service.initialize()
        
        # Add multiple test cameras
        camera_configs = [
            CameraConfig(
                camera_id=f"multi_test_{i}",
                camera_type="ip_camera",
                connection_url=f"155.138.239.131:{8080+i}",
                format="mjpeg",
                external_ip="155.138.239.131"
            )
            for i in range(3)
        ]
        
        # Add all cameras
        for config in camera_configs:
            success = await camera_service.add_camera(config)
            assert success == True
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Check service stats
        stats = camera_service.get_service_stats()
        assert stats["active_cameras"] >= 3  # Default cameras + test cameras
        assert stats["total_frames_processed"] > 0
        
        # Check individual camera status
        for config in camera_configs:
            status = await camera_service.get_camera_status(config.camera_id)
            assert status["is_running"] == True
            assert status["buffer_stats"]["total_frames"] > 0
        
        # Remove test cameras
        for config in camera_configs:
            await camera_service.remove_camera(config.camera_id)
        
        await camera_service.shutdown()
    
    @pytest.mark.asyncio
    async def test_external_ip_integration(self, camera_service, config_manager):
        """Test external IP integration across components"""
        external_ip = "155.138.239.131"
        
        # Initialize with external IP
        await camera_service.initialize(external_ip)
        assert camera_service.external_ip == external_ip
        
        # Create configuration with external IP
        complete_config = config_manager.create_default_config("external_ip_test", "ip_camera")
        assert complete_config.network.external_ip == external_ip
        
        # Save and reload
        config_manager.save_config(complete_config)
        loaded_config = config_manager.load_config("external_ip_test")
        assert loaded_config.network.external_ip == external_ip
        
        # Update external IP
        new_ip = "192.168.1.200"
        updated_count = config_manager.update_external_ip(new_ip)
        assert updated_count >= 1
        
        # Verify update
        reloaded_config = config_manager.load_config("external_ip_test")
        assert reloaded_config.network.external_ip == new_ip
        
        # Clean up
        config_manager.delete_config("external_ip_test")
        await camera_service.shutdown()

@pytest.mark.asyncio
async def test_performance_benchmarks():
    """Performance benchmarks for camera integration system"""
    camera_service = CameraIntegrationService()
    await camera_service.initialize()
    
    # Benchmark frame processing
    config = CameraConfig(
        camera_id="perf_test",
        camera_type="ip_camera",
        connection_url="155.138.239.131:8080",
        format="mjpeg",
        fps=60,  # High FPS for performance test
        external_ip="155.138.239.131"
    )
    
    await camera_service.add_camera(config)
    
    # Run for performance measurement
    start_time = time.time()
    await asyncio.sleep(5)  # 5 seconds of processing
    end_time = time.time()
    
    # Check performance metrics
    stats = camera_service.get_service_stats()
    buffer_stats = camera_service.buffers["perf_test"].get_stats()
    
    processing_time = end_time - start_time
    frames_per_second = buffer_stats["total_frames"] / processing_time
    
    print(f"\nPerformance Benchmark Results:")
    print(f"Processing Time: {processing_time:.2f} seconds")
    print(f"Total Frames: {buffer_stats['total_frames']}")
    print(f"Frames per Second: {frames_per_second:.2f}")
    print(f"Drop Rate: {buffer_stats['drop_rate']:.4f}")
    print(f"Total Validations: {stats['total_validations']}")
    
    # Performance assertions
    assert frames_per_second > 10  # Should process at least 10 FPS
    assert buffer_stats["drop_rate"] < 0.1  # Drop rate should be less than 10%
    
    await camera_service.shutdown()

if __name__ == "__main__":
    # Run specific test or all tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])