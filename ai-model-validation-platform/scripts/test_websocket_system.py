#!/usr/bin/env python3
"""
WebSocket System Testing Script
Comprehensive test of the real-time update system for HIL testing
"""

import asyncio
import sys
import os
import subprocess
import time
import signal
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))

def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"🔧 {title}")
    print("="*80)

def print_step(step: str):
    """Print formatted step"""
    print(f"\n📋 {step}")
    print("-" * len(f"📋 {step}"))

async def check_backend_health():
    """Check if backend is running and healthy"""
    print_step("Checking Backend Health")
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # Check main API health
            async with session.get("http://localhost:8000/health", timeout=5) as response:
                if response.status == 200:
                    print("✅ Backend API is healthy")
                else:
                    print(f"⚠️ Backend API health check returned status {response.status}")
                    return False
            
            # Check Socket.IO endpoint
            async with session.get("http://localhost:8001/socket.io/?EIO=4&transport=polling", timeout=5) as response:
                if response.status in [200, 400]:  # 400 is normal for Socket.IO polling without proper handshake
                    print("✅ Socket.IO server is responding")
                    return True
                else:
                    print(f"⚠️ Socket.IO server returned status {response.status}")
                    return False
                    
    except aiohttp.ClientError as e:
        print(f"❌ Backend health check failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during health check: {e}")
        return False

async def run_backend_websocket_tests():
    """Run backend WebSocket integration tests"""
    print_step("Running Backend WebSocket Tests")
    
    test_file = backend_path / "tests" / "test_websocket_hil_integration.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    try:
        # Run the WebSocket integration test
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(test_file),
            cwd=str(backend_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print("✅ Backend WebSocket tests passed")
            print("📊 Test output:")
            print(stdout.decode())
            return True
        else:
            print("❌ Backend WebSocket tests failed")
            print("📊 Error output:")
            print(stderr.decode())
            return False
            
    except Exception as e:
        print(f"❌ Error running backend tests: {e}")
        return False

def test_frontend_websocket_config():
    """Test frontend WebSocket configuration"""
    print_step("Testing Frontend WebSocket Configuration")
    
    frontend_path = Path(__file__).parent.parent / "frontend"
    
    # Check if WebSocket service exists
    websocket_service_path = frontend_path / "src" / "services" / "websocketService.ts"
    if websocket_service_path.exists():
        print("✅ WebSocket service file exists")
    else:
        print("❌ WebSocket service file missing")
        return False
    
    # Check if useWebSocket hook exists
    websocket_hook_path = frontend_path / "src" / "hooks" / "useWebSocket.ts"
    if websocket_hook_path.exists():
        print("✅ useWebSocket hook exists")
    else:
        print("❌ useWebSocket hook missing")
        return False
    
    # Check if HIL test component exists
    hil_test_path = frontend_path / "src" / "tests" / "HILWebSocketTest.tsx"
    if hil_test_path.exists():
        print("✅ HIL WebSocket test component exists")
    else:
        print("❌ HIL WebSocket test component missing")
        return False
    
    print("✅ Frontend WebSocket configuration looks good")
    return True

def create_websocket_diagnostic_report():
    """Create diagnostic report"""
    print_step("Creating WebSocket Diagnostic Report")
    
    report = {
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system_info": {
            "python_version": sys.version,
            "platform": os.name,
        },
        "backend_files": {
            "socketio_server.py": (backend_path / "socketio_server.py").exists(),
            "main.py": (backend_path / "main.py").exists(),
            "websocket_service.py": (backend_path / "services" / "websocket_service.py").exists(),
            "websocket_enhanced.py": (backend_path / "services" / "websocket_enhanced.py").exists(),
        },
        "frontend_files": {
            "websocketService.ts": (Path(__file__).parent.parent / "frontend" / "src" / "services" / "websocketService.ts").exists(),
            "useWebSocket.ts": (Path(__file__).parent.parent / "frontend" / "src" / "hooks" / "useWebSocket.ts").exists(),
            "HILWebSocketTest.tsx": (Path(__file__).parent.parent / "frontend" / "src" / "tests" / "HILWebSocketTest.tsx").exists(),
        },
        "test_files": {
            "backend_integration_test": (backend_path / "tests" / "test_websocket_hil_integration.py").exists(),
        }
    }
    
    # Check for required dependencies
    try:
        import socketio
        report["dependencies"] = {
            "python_socketio": socketio.__version__,
        }
    except ImportError:
        report["dependencies"] = {
            "python_socketio": "NOT_INSTALLED"
        }
    
    # Save report
    report_path = backend_path / "websocket_diagnostic_report.json"
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📊 Diagnostic report saved to: {report_path}")
    
    # Print summary
    print("\n📋 File Status Summary:")
    for category, files in report["backend_files"].items():
        status = "✅" if files else "❌"
        print(f"  {status} Backend: {category}")
    
    for category, files in report["frontend_files"].items():
        status = "✅" if files else "❌"
        print(f"  {status} Frontend: {category}")
    
    return report

async def run_connection_test():
    """Run basic connection test"""
    print_step("Running Basic Connection Test")
    
    import socketio
    
    client = socketio.AsyncClient(logger=True)
    connected = False
    messages_received = []
    
    @client.event
    async def connect():
        nonlocal connected
        connected = True
        print("✅ Test client connected to Socket.IO server")
    
    @client.event
    async def connection_status(data):
        messages_received.append(("connection_status", data))
        print(f"📊 Received connection status: {data}")
    
    @client.event
    async def disconnect():
        print("🔌 Test client disconnected")
    
    try:
        # Connect to server
        await client.connect("http://localhost:8001", transports=['websocket', 'polling'])
        
        # Wait for connection
        await asyncio.sleep(2)
        
        if connected:
            print("✅ Successfully connected to Socket.IO server")
            
            # Test subscription
            await client.emit('subscribe_to_updates', {"type": "general"})
            await asyncio.sleep(1)
            
            # Test ping
            await client.emit('ping', {"timestamp": time.time(), "test": True})
            await asyncio.sleep(1)
            
            print(f"📊 Received {len(messages_received)} messages during test")
            
            await client.disconnect()
            return True
        else:
            print("❌ Failed to connect to Socket.IO server")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

async def main():
    """Main test runner"""
    print_header("WebSocket System Testing Suite")
    print("This script will test the real-time update system for HIL testing")
    print("Make sure the backend server is running on localhost:8000/8001")
    
    # Create diagnostic report first
    report = create_websocket_diagnostic_report()
    
    # Check backend health
    backend_healthy = await check_backend_health()
    
    if not backend_healthy:
        print("\n❌ Backend is not healthy. Please start the backend server first.")
        print("   Run: python main.py")
        return False
    
    # Test frontend configuration
    frontend_config_ok = test_frontend_websocket_config()
    
    # Run basic connection test
    connection_test_ok = await run_connection_test()
    
    # Run backend WebSocket tests (if backend is healthy)
    if backend_healthy:
        backend_tests_ok = await run_backend_websocket_tests()
    else:
        backend_tests_ok = False
    
    # Print final summary
    print_header("Test Summary")
    
    tests = [
        ("Backend Health", backend_healthy),
        ("Frontend Configuration", frontend_config_ok),
        ("Basic Connection", connection_test_ok),
        ("Backend Integration Tests", backend_tests_ok),
    ]
    
    passed_tests = sum(1 for _, result in tests if result)
    total_tests = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\n📊 Overall Score: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print("\n🎉 All WebSocket system tests passed! HIL real-time updates are ready.")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        print("\nNext steps:")
        if not backend_healthy:
            print("  1. Start the backend server: python main.py")
        if not frontend_config_ok:
            print("  2. Check frontend WebSocket configuration files")
        if not connection_test_ok:
            print("  3. Verify Socket.IO server is properly configured")
        if not backend_tests_ok:
            print("  4. Run backend tests manually and check for errors")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Testing failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)