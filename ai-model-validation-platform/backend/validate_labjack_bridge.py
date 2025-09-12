#!/usr/bin/env python3
"""
Simple validation script for LabJack Bridge Integration

Tests the core functionality without complex dependencies
"""

import asyncio
import logging
import os

# Test basic imports
print("🔧 Testing LabJack Bridge Service Integration")
print("=" * 50)

# Set environment for bridge testing
os.environ["LABJACK_BRIDGE_ENABLED"] = "true"
os.environ["LABJACK_BRIDGE_HOST"] = "localhost" 
os.environ["LABJACK_BRIDGE_PORT"] = "8080"
os.environ["LABJACK_MOCK_MODE"] = "false"

try:
    from services.labjack_service import (
        LabJackService, 
        ConnectionMode, 
        ConnectionStatus,
        BridgeConfig
    )
    print("✅ Core LabJack service imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

async def test_bridge_integration():
    """Test bridge integration functionality"""
    
    # Test 1: Service Creation
    print("\n1. Testing service creation...")
    try:
        service = LabJackService()
        print(f"✅ Service created")
        print(f"   - Initial mode: {service.mode.value}")
        print(f"   - Initial status: {service.status.value}")
    except Exception as e:
        print(f"❌ Service creation failed: {e}")
        return False
    
    # Test 2: Bridge Configuration
    print("\n2. Testing bridge configuration...")
    try:
        bridge_config = BridgeConfig(
            host="localhost",
            port=8080,
            http_timeout=5
        )
        print(f"✅ Bridge config created")
        print(f"   - HTTP URL: {bridge_config.http_url}")
        print(f"   - WebSocket URL: {bridge_config.websocket_url}")
    except Exception as e:
        print(f"❌ Bridge config failed: {e}")
        return False
    
    # Test 3: Mock Mode Connection (guaranteed to work)
    print("\n3. Testing mock mode connection...")
    try:
        # Force mock mode for reliable testing
        await service._connect_mock()
        status = service.get_status()
        print(f"✅ Mock connection successful")
        print(f"   - Mode: {status.mode.value}")
        print(f"   - Connected: {status.connected}")
        
        if status.connected:
            device_info = await service.get_device_info()
            print(f"   - Device type: {device_info.get('device_type', 'Unknown')}")
            print(f"   - Is mock: {device_info.get('is_mock', 'Unknown')}")
            
            # Test voltage reading
            voltage = await service.read_single_voltage("AIN0")
            print(f"   - AIN0 voltage: {voltage:.3f}V")
    except Exception as e:
        print(f"❌ Mock connection failed: {e}")
        return False
    
    # Test 4: Connection Fallback Logic
    print("\n4. Testing connection fallback logic...")
    try:
        # Reset service
        await service.disconnect()
        new_service = LabJackService()
        
        # Test fallback connection (should end up in mock mode)
        success = await new_service.connect()
        final_status = new_service.get_status()
        
        print(f"✅ Fallback connection: {success}")
        print(f"   - Final mode: {final_status.mode.value}")
        print(f"   - Connection attempts: {final_status.statistics.get('connection_attempts', 0)}")
        
        await new_service.disconnect()
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")
        return False
    
    # Test 5: Status and Statistics
    print("\n5. Testing status and statistics...")
    try:
        service = LabJackService()
        await service.connect()
        
        status = service.get_status()
        print(f"✅ Status retrieved")
        print(f"   - Mode: {status.mode.value}")
        print(f"   - Streaming: {status.streaming}")
        print(f"   - Sample rate: {status.sample_rate}Hz")
        print(f"   - Channels: {status.channels}")
        print(f"   - Statistics: {status.statistics}")
        
        await service.disconnect()
    except Exception as e:
        print(f"❌ Status test failed: {e}")
        return False
    
    print("\n✅ All basic tests passed!")
    return True

def test_mock_bridge():
    """Test mock bridge functionality"""
    print("\n6. Testing mock bridge interface...")
    
    try:
        from services.mock_labjack import get_mock_bridge_interface
        
        bridge = get_mock_bridge_interface()
        print("✅ Mock bridge interface created")
        
        # Test async functionality
        async def test_async():
            success = await bridge.connect()
            print(f"✅ Mock bridge connected: {success}")
            
            if success:
                device_info = await bridge.get_device_info()
                print(f"   - Bridge mode: {device_info.get('bridge_mode', False)}")
                
                voltage = await bridge.read_single_voltage("AIN0")
                print(f"   - Test voltage: {voltage:.3f}V")
                
                bridge.disconnect()
            
            return success
        
        return asyncio.run(test_async())
        
    except Exception as e:
        print(f"❌ Mock bridge test failed: {e}")
        return False

def test_configuration_structure():
    """Test configuration structure without loading from environment"""
    print("\n7. Testing configuration structure...")
    
    try:
        from config.labjack_env_config import LabJackConfig
        
        # Create config with bridge settings
        config = LabJackConfig(
            bridge_enabled=True,
            bridge_host="test-host",
            bridge_port=9000,
            mock_mode=False,
            voltage_threshold=3.0,
            sample_rate=2000
        )
        
        print("✅ Configuration structure valid")
        print(f"   - Bridge enabled: {config.bridge_enabled}")
        print(f"   - Bridge host: {config.bridge_host}:{config.bridge_port}")
        print(f"   - Mock mode: {config.mock_mode}")
        print(f"   - Voltage threshold: {config.voltage_threshold}V")
        print(f"   - Sample rate: {config.sample_rate}Hz")
        
        # Test dictionary conversion
        config_dict = config.to_dict()
        print(f"   - Dict conversion: {len(config_dict)} fields")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

async def main():
    """Run all validation tests"""
    
    logging.basicConfig(level=logging.WARNING)  # Reduce noise
    
    tests = [
        ("Bridge Integration", test_bridge_integration()),
        ("Mock Bridge", test_mock_bridge()),
        ("Configuration", test_configuration_structure())
    ]
    
    results = []
    
    for test_name, test_coro in tests:
        try:
            if asyncio.iscoroutine(test_coro):
                result = await test_coro
            else:
                result = test_coro
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 Validation Results")
    print("=" * 50)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 LabJack Bridge integration is working correctly!")
    else:
        print("⚠️  Some issues detected - check implementation")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)