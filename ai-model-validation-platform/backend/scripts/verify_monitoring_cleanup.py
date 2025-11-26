#!/usr/bin/env python3
"""
Manual Verification Script for Monitoring Cleanup Fix

This script manually tests that the monitoring service stops cleanly.
Run this to verify the fix before deploying to production.
"""

import sys
import time
import threading
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from services.labjack_monitoring_service import LabJackMonitoringService


def test_cleanup_fix():
    """Test that monitoring service stops cleanly"""
    print("\n" + "="*80)
    print("MONITORING CLEANUP FIX VERIFICATION")
    print("="*80 + "\n")

    service = LabJackMonitoringService()

    print("✅ Step 1: Create monitoring service instance")
    print(f"   - monitoring_active: {service.monitoring_active}")
    print(f"   - current_session_id: {service.current_session_id}")
    print(f"   - monitor_thread: {service.monitor_thread}")

    # Note: We can't actually start monitoring without signal_validation_service
    # But we can test the stop logic
    print("\n✅ Step 2: Test stop_monitoring() with no active session")
    service.stop_monitoring()
    print(f"   - monitoring_active: {service.monitoring_active}")
    print(f"   - current_session_id: {service.current_session_id}")
    print(f"   - Result: Should handle gracefully (no crash)")

    print("\n✅ Step 3: Simulate session lifecycle")
    print("   - Setting up simulated session state...")
    service.monitoring_active = True
    service.current_session_id = "test-session-123"
    service._stop_event.clear()

    # Create a mock thread
    def mock_monitor_loop():
        """Simulated monitoring loop"""
        print("   - Mock monitoring loop started")
        while service.monitoring_active and not service._stop_event.is_set():
            time.sleep(0.1)
        print("   - Mock monitoring loop exited cleanly")

    service.monitor_thread = threading.Thread(target=mock_monitor_loop, daemon=True)
    service.monitor_thread.start()

    print(f"   - monitoring_active: {service.monitoring_active}")
    print(f"   - thread alive: {service.monitor_thread.is_alive()}")

    print("\n✅ Step 4: Call stop_monitoring()")
    time.sleep(0.5)  # Let mock loop run briefly
    service.stop_monitoring()

    print(f"   - monitoring_active: {service.monitoring_active}")
    print(f"   - current_session_id: {service.current_session_id}")
    print(f"   - monitor_thread: {service.monitor_thread}")

    # Wait to verify thread stopped
    time.sleep(0.5)

    print("\n✅ Step 5: Verify thread termination")
    print(f"   - Thread should be None or not alive")

    if service.monitor_thread is None:
        print("   ✅ SUCCESS: Thread reference cleaned up (None)")
    elif not service.monitor_thread.is_alive():
        print("   ✅ SUCCESS: Thread terminated")
    else:
        print("   ❌ FAILURE: Thread still running!")
        return False

    print("\n✅ Step 6: Verify state cleanup")
    checks = {
        "monitoring_active is False": service.monitoring_active is False,
        "current_session_id is None": service.current_session_id is None,
        "monitor_thread is None": service.monitor_thread is None,
        "_was_high is False": service._was_high is False,
    }

    all_passed = True
    for check, result in checks.items():
        status = "✅" if result else "❌"
        print(f"   {status} {check}")
        if not result:
            all_passed = False

    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Monitoring cleanup fix is working correctly!")
    else:
        print("❌ SOME CHECKS FAILED - Fix may need adjustment")
    print("="*80 + "\n")

    return all_passed


if __name__ == "__main__":
    success = test_cleanup_fix()
    sys.exit(0 if success else 1)
