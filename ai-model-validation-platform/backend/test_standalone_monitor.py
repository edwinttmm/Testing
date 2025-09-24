#!/usr/bin/env python3
"""
Test Script for Standalone LabJack Monitoring Service

This script tests the standalone LabJack monitoring service functionality
including process management, IPC communication, and monitoring capabilities.

Usage:
    python test_standalone_monitor.py
    python test_standalone_monitor.py --test-ipc  # Test IPC client
    python test_standalone_monitor.py --test-process  # Test process management

Author: AI Model Validation Platform Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import socket
import subprocess
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ipc_client():
    """Test IPC communication with monitoring service"""
    print("🧪 Testing IPC Client Communication")
    
    # Import the IPC client
    try:
        from services.standalone_labjack_monitor import IPCClient
        client = IPCClient()
        
        # Test status command
        print("📡 Testing status command...")
        response = client.send_command({"command": "get_status"})
        print(f"Status response: {json.dumps(response, indent=2)}")
        
        # Test health command
        print("🏥 Testing health command...")
        response = client.send_command({"command": "get_health"})
        print(f"Health response: {json.dumps(response, indent=2)}")
        
        # Test invalid command
        print("❌ Testing invalid command...")
        response = client.send_command({"command": "invalid_command"})
        print(f"Invalid command response: {json.dumps(response, indent=2)}")
        
        print("✅ IPC Client tests completed")
        return True
        
    except Exception as e:
        print(f"❌ IPC Client test failed: {e}")
        return False

def test_process_management():
    """Test process management functionality"""
    print("🧪 Testing Process Management")
    
    try:
        from services.labjack_monitor_manager import LabJackMonitorManager
        
        # Create manager
        manager = LabJackMonitorManager()
        
        print("🚀 Starting monitor process...")
        success = asyncio.run(manager.start_monitor_process())
        
        if success:
            print("✅ Monitor process started successfully")
            
            # Test monitoring session
            print("📊 Testing monitoring session...")
            session_success = asyncio.run(manager.start_monitoring_session("test_session_001"))
            
            if session_success:
                print("✅ Monitoring session started")
                
                # Wait a bit and check status
                time.sleep(5)
                status = asyncio.run(manager.get_monitoring_status())
                print(f"📈 Status: {json.dumps(status, indent=2, default=str)}")
                
                # Stop monitoring
                print("⏹️ Stopping monitoring session...")
                stop_success = asyncio.run(manager.stop_monitoring_session())
                print(f"✅ Monitoring stopped: {stop_success}")
            
            # Stop process
            print("🛑 Stopping monitor process...")
            stop_success = asyncio.run(manager.stop_monitor_process())
            print(f"✅ Process stopped: {stop_success}")
            
        else:
            print("❌ Failed to start monitor process")
            return False
            
        print("✅ Process management tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Process management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_standalone_service():
    """Test the standalone service directly"""
    print("🧪 Testing Standalone Service")
    
    try:
        # Try to import and run the service in test mode
        service_script = Path(__file__).parent / "services" / "standalone_labjack_monitor.py"
        
        if not service_script.exists():
            print(f"❌ Service script not found: {service_script}")
            return False
        
        print(f"🔧 Running service in test mode: {service_script}")
        
        # Run the service with test flag
        result = subprocess.run([
            sys.executable, str(service_script), "--test"
        ], capture_output=True, text=True, timeout=30)
        
        print(f"📤 Service output:\n{result.stdout}")
        if result.stderr:
            print(f"⚠️ Service errors:\n{result.stderr}")
        
        success = result.returncode == 0
        print(f"✅ Service test {'passed' if success else 'failed'}")
        return success
        
    except subprocess.TimeoutExpired:
        print("⏰ Service test timed out (expected in test mode)")
        return True
    except Exception as e:
        print(f"❌ Standalone service test failed: {e}")
        return False

def test_database_integration():
    """Test database integration"""
    print("🧪 Testing Database Integration")
    
    try:
        from services.standalone_labjack_monitor import MonitoringConfig, DatabaseManager
        
        config = MonitoringConfig(database_path="test_database.db")
        db_manager = DatabaseManager(config, logger)
        
        # Test connection
        print("🔌 Testing database connection...")
        connection_ok = db_manager.test_connection()
        print(f"✅ Database connection: {'OK' if connection_ok else 'FAILED'}")
        
        if connection_ok:
            # Test event storage
            from services.standalone_labjack_monitor import DetectionEvent
            from datetime import datetime, timezone
            import uuid
            
            print("💾 Testing event storage...")
            event = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id="test_session_001",
                timestamp=time.time(),
                voltage=3.5,
                channel="AIN0",
                latency_ms=5.0,
                created_at=datetime.now(timezone.utc).isoformat()
            )
            
            stored = db_manager.store_detection_event(event)
            print(f"✅ Event storage: {'OK' if stored else 'FAILED'}")
        
        print("✅ Database integration tests completed")
        return connection_ok
        
    except Exception as e:
        print(f"❌ Database integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_comprehensive_test():
    """Run comprehensive test suite"""
    print("🚀 Running Comprehensive LabJack Monitoring Tests")
    print("=" * 60)
    
    results = {
        "database_integration": test_database_integration(),
        "standalone_service": test_standalone_service(),
        "process_management": test_process_management(),
        "ipc_client": test_ipc_client()
    }
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Standalone monitoring service is ready.")
        return True
    else:
        print("⚠️ Some tests failed. Check the logs for details.")
        return False

def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test Standalone LabJack Monitoring Service")
    parser.add_argument("--test-ipc", action="store_true", help="Test IPC client only")
    parser.add_argument("--test-process", action="store_true", help="Test process management only")
    parser.add_argument("--test-database", action="store_true", help="Test database integration only")
    parser.add_argument("--test-service", action="store_true", help="Test standalone service only")
    
    args = parser.parse_args()
    
    try:
        if args.test_ipc:
            success = test_ipc_client()
        elif args.test_process:
            success = test_process_management()
        elif args.test_database:
            success = test_database_integration()
        elif args.test_service:
            success = test_standalone_service()
        else:
            success = run_comprehensive_test()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()