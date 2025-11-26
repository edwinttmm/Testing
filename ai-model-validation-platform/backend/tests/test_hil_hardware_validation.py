"""
Test Suite for HIL Hardware Validation

This test suite validates the critical safety fix that prevents silent fallback
to simulation mode when real LabJack hardware is required for HIL testing.

CRITICAL TEST SCENARIOS:
1. HIL session start with no hardware connected - should FAIL
2. HIL session start with simulation mode - should FAIL  
3. HIL session start with real hardware - should SUCCEED
4. Connection validation before video playback
5. Error handling and user messaging
6. Frontend status display accuracy
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.labjack_service_manager import LabJackService, ConnectionMode, ConnectionStatus
from services.hil_validation_service import (
    HILValidationService, HILValidationError, HardwareRequirement, HILHardwareStatus
)
from api.hil_test_complete import validate_hil_hardware_requirements


class TestHILHardwareValidation:
    """Test HIL hardware validation scenarios"""
    
    @pytest.fixture
    def mock_labjack_service(self):
        """Create mock LabJack service"""
        mock_service = Mock(spec=LabJackService)
        return mock_service
    
    @pytest.fixture
    def hil_validation_service(self, mock_labjack_service):
        """Create HIL validation service with mock LabJack service"""
        return HILValidationService(mock_labjack_service)
    
    def test_validation_service_initialization(self, hil_validation_service):
        """Test HIL validation service initializes correctly"""
        assert hil_validation_service is not None
        assert hil_validation_service.cache_valid_seconds == 5
        assert hil_validation_service.validation_cache is None
    
    def test_hardware_connected_real_device_validation_passes(self, hil_validation_service, mock_labjack_service):
        """Test: Real hardware connected - validation should PASS"""
        # Mock real hardware connection
        mock_status = Mock()
        mock_status.connected = True
        mock_status.mode = ConnectionMode.DIRECT
        mock_status.device_info = {
            "device_type": "T7",
            "serial_number": "12345",
            "connection_type": "USB",
            "is_mock": False,
            "is_simulation": False,
            "hil_suitable": True
        }
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        # Validation should pass
        result = hil_validation_service.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
        
        assert result.is_connected == True
        assert result.is_simulation == False
        assert result.hil_suitable == True
        assert result.hardware_requirement_met == True
    
    def test_hardware_not_connected_validation_fails(self, hil_validation_service, mock_labjack_service):
        """Test: No hardware connected - validation should FAIL"""
        # Mock disconnected state
        mock_status = Mock()
        mock_status.connected = False
        mock_status.mode = ConnectionMode.DIRECT
        mock_status.device_info = {}
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        # Validation should fail
        with pytest.raises(HILValidationError) as exc_info:
            hil_validation_service.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
        
        assert "HIL testing requires LabJack hardware connection" in str(exc_info.value)
    
    def test_simulation_mode_validation_fails(self, hil_validation_service, mock_labjack_service):
        """Test: Simulation mode detected - validation should FAIL"""
        # Mock simulation mode
        mock_status = Mock()
        mock_status.connected = True
        mock_status.mode = ConnectionMode.MOCK
        mock_status.device_info = {
            "device_type": "T7_SIMULATED",
            "serial_number": "SIMULATION_ONLY",
            "connection_type": "MOCK_SIMULATION",
            "is_mock": True,
            "is_simulation": True,
            "hil_suitable": False
        }
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        # Validation should fail
        with pytest.raises(HILValidationError) as exc_info:
            hil_validation_service.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
        
        assert "simulation mode" in str(exc_info.value).lower()
    
    def test_mock_device_info_validation_fails(self, hil_validation_service, mock_labjack_service):
        """Test: Device info indicates mock - validation should FAIL"""
        # Mock device with is_mock flag
        mock_status = Mock()
        mock_status.connected = True
        mock_status.mode = ConnectionMode.DIRECT  # Mode looks real
        mock_status.device_info = {
            "device_type": "T7",
            "serial_number": "12345",
            "connection_type": "USB",
            "is_mock": True,  # But device info says it's mock
            "is_simulation": False,
            "hil_suitable": False
        }
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        # Validation should fail
        with pytest.raises(HILValidationError) as exc_info:
            hil_validation_service.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
        
        assert "simulation mode" in str(exc_info.value).lower()
    
    def test_hardware_requirement_levels(self, hil_validation_service, mock_labjack_service):
        """Test different hardware requirement levels"""
        # Mock disconnected state
        mock_status = Mock()
        mock_status.connected = False
        mock_status.mode = ConnectionMode.DIRECT
        mock_status.device_info = {}
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        # NONE requirement should always pass
        result = hil_validation_service.validate_hardware_for_hil(HardwareRequirement.NONE)
        assert result is not None
        
        # RECOMMENDED should pass but log warnings
        result = hil_validation_service.validate_hardware_for_hil(HardwareRequirement.RECOMMENDED)
        assert result is not None
        
        # REQUIRED should fail
        with pytest.raises(HILValidationError):
            hil_validation_service.validate_hardware_for_hil(HardwareRequirement.REQUIRED)
        
        # CRITICAL should fail
        with pytest.raises(HILValidationError):
            hil_validation_service.validate_hardware_for_hil(HardwareRequirement.CRITICAL)
    
    def test_validation_caching(self, hil_validation_service, mock_labjack_service):
        """Test validation result caching"""
        # Mock real hardware
        mock_status = Mock()
        mock_status.connected = True
        mock_status.mode = ConnectionMode.DIRECT
        mock_status.device_info = {
            "device_type": "T7",
            "serial_number": "12345",
            "connection_type": "USB",
            "is_mock": False,
            "is_simulation": False,
            "hil_suitable": True
        }
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        # First call should query service
        result1 = hil_validation_service._get_hardware_status()
        assert mock_labjack_service.get_status.call_count == 1
        
        # Second call within cache period should use cache
        result2 = hil_validation_service._get_hardware_status()
        assert mock_labjack_service.get_status.call_count == 1  # Still 1
        assert result1.device_type == result2.device_type
        
        # Clear cache and call again
        hil_validation_service.clear_validation_cache()
        result3 = hil_validation_service._get_hardware_status()
        assert mock_labjack_service.get_status.call_count == 2  # Now 2
    
    def test_ui_status_formatting(self, hil_validation_service, mock_labjack_service):
        """Test UI status formatting"""
        # Mock real hardware
        mock_status = Mock()
        mock_status.connected = True
        mock_status.mode = ConnectionMode.DIRECT
        mock_status.device_info = {
            "device_type": "T7",
            "serial_number": "12345",
            "connection_type": "USB",
            "is_mock": False,
            "is_simulation": False,
            "hil_suitable": True
        }
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        ui_status = hil_validation_service.get_hardware_status_for_ui()
        
        assert ui_status["connected"] == True
        assert ui_status["device_type"] == "T7"
        assert ui_status["serial_number"] == "12345"
        assert ui_status["is_simulation"] == False
        assert ui_status["hil_suitable"] == True
        assert ui_status["hardware_icon"] == "🔌"
        assert ui_status["status_color"] == "green"
    
    def test_simulation_ui_status_warnings(self, hil_validation_service, mock_labjack_service):
        """Test UI status shows simulation warnings"""
        # Mock simulation mode
        mock_status = Mock()
        mock_status.connected = True
        mock_status.mode = ConnectionMode.MOCK
        mock_status.device_info = {
            "device_type": "T7_SIMULATED",
            "serial_number": "SIMULATION_ONLY",
            "connection_type": "MOCK_SIMULATION",
            "is_mock": True,
            "is_simulation": True,
            "hil_suitable": False
        }
        mock_status.statistics = {}
        mock_labjack_service.get_status.return_value = mock_status
        
        ui_status = hil_validation_service.get_hardware_status_for_ui()
        
        assert ui_status["connected"] == True
        assert ui_status["is_simulation"] == True
        assert ui_status["hil_suitable"] == False
        assert ui_status["hardware_icon"] == "❌"
        assert ui_status["status_color"] == "orange"
        assert "simulation" in ui_status["status"].lower()


class TestLabJackServiceFailsafeModes:
    """Test LabJack service fail-safe connection modes"""
    
    @pytest.fixture
    def labjack_service(self):
        """Create LabJack service"""
        return LabJackService()
    
    @pytest.mark.asyncio
    async def test_connect_without_allow_mock_fails(self, labjack_service):
        """Test: Connection without allow_mock=True should fail if no hardware"""
        with patch.object(labjack_service, '_connect_direct', return_value=False), \
             patch.object(labjack_service, '_connect_bridge', return_value=False):
            
            # Should fail without allow_mock
            success = await labjack_service.connect(allow_mock=False)
            assert success == False
            assert labjack_service.status == ConnectionStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_connect_with_allow_mock_succeeds(self, labjack_service):
        """Test: Connection with allow_mock=True should use simulation if hardware fails"""
        with patch.object(labjack_service, '_connect_direct', return_value=False), \
             patch.object(labjack_service, '_connect_bridge', return_value=False), \
             patch.object(labjack_service, '_connect_mock', return_value=True):
            
            # Should succeed with allow_mock=True
            success = await labjack_service.connect(allow_mock=True)
            assert success == True
    
    @pytest.mark.asyncio
    async def test_forced_mock_mode_requires_allow_mock(self, labjack_service):
        """Test: Forced mock mode requires explicit allow_mock=True"""
        # Should fail without allow_mock
        success = await labjack_service.connect(force_mode=ConnectionMode.MOCK, allow_mock=False)
        assert success == False
        
        # Should succeed with allow_mock
        with patch.object(labjack_service, '_connect_mock', return_value=True):
            success = await labjack_service.connect(force_mode=ConnectionMode.MOCK, allow_mock=True)
            assert success == True


class TestHILAPIEndpointsValidation:
    """Test HIL API endpoints validation"""
    
    @pytest.mark.asyncio
    async def test_hil_session_start_validation_function(self):
        """Test the validate_hil_hardware_requirements function"""
        from fastapi import HTTPException
        
        # Mock validation service that fails
        with patch('api.hil_test_complete.hil_validation_service') as mock_service:
            mock_service.validate_hil_session_start.side_effect = HILValidationError("Hardware not connected")
            
            # Should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await validate_hil_hardware_requirements()
            
            assert exc_info.value.status_code == 503
            assert "Hardware not connected" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_hil_session_start_simulation_error(self):
        """Test HIL session start with simulation mode error"""
        from fastapi import HTTPException
        
        with patch('api.hil_test_complete.hil_validation_service') as mock_service:
            mock_service.validate_hil_session_start.side_effect = HILValidationError("simulation mode detected")
            
            with pytest.raises(HTTPException) as exc_info:
                await validate_hil_hardware_requirements()
            
            # Simulation errors should return 400 Bad Request
            assert exc_info.value.status_code == 400
            assert "simulation" in exc_info.value.detail.lower()


class TestConnectionFailureScenarios:
    """Test comprehensive connection failure scenarios"""
    
    def test_connection_failure_error_messages(self):
        """Test error messages for different connection failures"""
        service = HILValidationService(Mock())
        
        # Test not connected error
        status = HILHardwareStatus(
            is_connected=False,
            device_type="Unknown",
            serial_number="Unknown",
            connection_type="Unknown",
            is_simulation=False,
            hil_suitable=False,
            connection_mode="unknown",
            status_message="❌ Not Connected",
            warning_message=None,
            validation_timestamp=datetime.now(),
            hardware_requirement_met=False
        )
        
        error_msg = service._generate_validation_error(status, HardwareRequirement.REQUIRED)
        assert "LabJack hardware connection" in error_msg
        assert "Please connect a LabJack device" in error_msg
    
    def test_simulation_detected_error_message(self):
        """Test error message when simulation is detected"""
        service = HILValidationService(Mock())
        
        status = HILHardwareStatus(
            is_connected=True,
            device_type="T7_SIMULATED",
            serial_number="SIMULATION_ONLY",
            connection_type="MOCK_SIMULATION",
            is_simulation=True,
            hil_suitable=False,
            connection_mode="mock",
            status_message="⚠️ Simulation Mode",
            warning_message="This is simulated data",
            validation_timestamp=datetime.now(),
            hardware_requirement_met=False
        )
        
        error_msg = service._generate_validation_error(status, HardwareRequirement.REQUIRED)
        assert "simulation mode" in error_msg.lower()
        assert "Real LabJack hardware is required" in error_msg
    
    def test_hardware_not_suitable_error_message(self):
        """Test error message when hardware is not HIL suitable"""
        service = HILValidationService(Mock())
        
        status = HILHardwareStatus(
            is_connected=True,
            device_type="T7",
            serial_number="12345",
            connection_type="USB",
            is_simulation=False,
            hil_suitable=False,  # Not suitable for HIL
            connection_mode="direct",
            status_message="Connected but not HIL suitable",
            warning_message=None,
            validation_timestamp=datetime.now(),
            hardware_requirement_met=False
        )
        
        error_msg = service._generate_validation_error(status, HardwareRequirement.REQUIRED)
        assert "not suitable for HIL testing" in error_msg
        assert "T7 (S/N: 12345)" in error_msg


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])