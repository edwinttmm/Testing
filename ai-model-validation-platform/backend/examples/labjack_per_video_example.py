#!/usr/bin/env python3
"""
Example: LabJack Per-Video Monitoring

Demonstrates the new per-video monitoring API for the refactored LabJack service.
This example shows how to:
1. Start monitoring for a specific video
2. Check monitoring status
3. Stop monitoring and get detection counts
4. Handle exceptions properly
"""

import time
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.services.dedicated_labjack_monitor import (
    DedicatedLabJackMonitor,
    MonitoringConfig,
    LabJackStateError,
    LabJackConnectionError,
    LabJackTimeoutError
)

def example_single_video():
    """Example 1: Monitor a single video"""
    print("=" * 80)
    print("EXAMPLE 1: Single Video Monitoring")
    print("=" * 80)

    # Configure monitor
    config = MonitoringConfig(
        session_id="test_session_001",
        sample_rate=10.0,
        voltage_threshold=3.0,
        channels=["AIN0"]
    )

    monitor = DedicatedLabJackMonitor(config)

    # Start monitoring with expected video start time
    video_id = "video_001"
    expected_start = time.time() + 0.3  # Video starts in 300ms

    try:
        print(f"\n🎬 Starting monitoring for {video_id}...")
        success, timestamps, vid = monitor.start_monitoring(
            video_id=video_id,
            expected_video_start_time=expected_start
        )

        if success:
            print(f"✅ Monitoring started successfully!")
            print(f"   Video ID: {vid}")
            print(f"   USB latency: {timestamps.initialization_latency_ms:.2f}ms")
            print(f"   Total startup: {timestamps.total_startup_latency_ms:.2f}ms")

            # Calculate drift
            drift_ms = (timestamps.command_sent - expected_start) * 1000
            print(f"   Timing drift: {drift_ms:+.2f}ms")

            # Check status
            status = monitor.get_monitoring_status()
            print(f"\n📊 Monitoring Status:")
            print(f"   Active: {status['is_monitoring']}")
            print(f"   Video: {status['current_video_id']}")
            print(f"   Detections: {status['detection_count']}")

            # Simulate video playback
            print(f"\n⏳ Simulating video playback (5 seconds)...")
            time.sleep(5)

            # Stop monitoring
            print(f"\n🛑 Stopping monitoring for {video_id}...")
            detection_count = monitor.stop_monitoring(video_id)
            print(f"✅ Monitoring stopped!")
            print(f"   Final detections: {detection_count}")

        else:
            print(f"❌ Failed to start monitoring")

    except LabJackStateError as e:
        print(f"❌ State Error: {e}")
    except LabJackConnectionError as e:
        print(f"❌ Connection Error: {e}")
        print(f"   Check USB connection and device availability")
    except LabJackTimeoutError as e:
        print(f"❌ Timeout Error: {e}")
        print(f"   USB latency exceeded 2 seconds")

    finally:
        monitor.stop()

def example_multiple_videos():
    """Example 2: Monitor multiple videos sequentially"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Multiple Video Monitoring")
    print("=" * 80)

    # Configure monitor
    config = MonitoringConfig(
        session_id="test_session_002",
        sample_rate=10.0,
        voltage_threshold=3.0,
        channels=["AIN0"]
    )

    monitor = DedicatedLabJackMonitor(config)

    # List of videos to process
    videos = [
        {"id": "video_001", "duration": 3.0},
        {"id": "video_002", "duration": 4.0},
        {"id": "video_003", "duration": 2.0}
    ]

    print(f"\n📹 Processing {len(videos)} videos...")

    for idx, video in enumerate(videos, 1):
        video_id = video["id"]
        duration = video["duration"]

        print(f"\n--- Video {idx}/{len(videos)}: {video_id} ---")

        # Calculate expected start time (300ms preroll)
        expected_start = time.time() + 0.3

        try:
            # Start monitoring
            success, timestamps, vid = monitor.start_monitoring(
                video_id=video_id,
                expected_video_start_time=expected_start
            )

            if not success:
                print(f"❌ Failed to start monitoring for {video_id}")
                continue

            print(f"✅ Monitoring started (USB: {timestamps.initialization_latency_ms:.2f}ms)")

            # Simulate video playback
            print(f"⏳ Playing video ({duration}s)...")
            time.sleep(duration)

            # Stop monitoring
            detection_count = monitor.stop_monitoring(video_id)
            print(f"✅ Monitoring stopped - {detection_count} detections")

        except LabJackStateError as e:
            print(f"❌ State error: {e}")
            continue
        except LabJackConnectionError as e:
            print(f"❌ Connection error: {e}")
            break  # Fatal - stop processing
        except LabJackTimeoutError as e:
            print(f"❌ Timeout error: {e}")
            continue  # Retry next video

    monitor.stop()
    print(f"\n✅ Processed all videos successfully!")

def example_error_handling():
    """Example 3: Demonstrate error handling"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Error Handling")
    print("=" * 80)

    config = MonitoringConfig(
        session_id="test_session_003",
        sample_rate=10.0,
        voltage_threshold=3.0,
        channels=["AIN0"]
    )

    monitor = DedicatedLabJackMonitor(config)

    # Error 1: Start monitoring twice
    print("\n🧪 Test 1: Starting monitoring twice")
    try:
        monitor.start_monitoring("video_001")
        print("✅ First start successful")

        monitor.start_monitoring("video_002")  # Should fail
        print("❌ Second start succeeded (unexpected!)")

    except LabJackStateError as e:
        print(f"✅ Expected error caught: {e}")

    # Error 2: Stop with wrong video_id
    print("\n🧪 Test 2: Stopping with wrong video_id")
    try:
        monitor.stop_monitoring("video_002")  # Wrong video
        print("❌ Stop succeeded with wrong video_id (unexpected!)")

    except LabJackStateError as e:
        print(f"✅ Expected error caught: {e}")

    # Cleanup
    try:
        monitor.stop_monitoring("video_001")  # Correct video
        print("✅ Cleanup successful")
    except:
        pass

    # Error 3: Stop when not monitoring
    print("\n🧪 Test 3: Stopping when not monitoring")
    try:
        monitor.stop_monitoring("video_001")  # Nothing active
        print("❌ Stop succeeded when not monitoring (unexpected!)")

    except LabJackStateError as e:
        print(f"✅ Expected error caught: {e}")

    monitor.stop()
    print("\n✅ Error handling tests complete!")

def example_status_checking():
    """Example 4: Monitor status checking"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Status Checking")
    print("=" * 80)

    config = MonitoringConfig(
        session_id="test_session_004",
        sample_rate=10.0,
        voltage_threshold=3.0,
        channels=["AIN0"]
    )

    monitor = DedicatedLabJackMonitor(config)

    # Check status before monitoring
    print("\n📊 Status before monitoring:")
    status = monitor.get_monitoring_status()
    print(f"   Active: {status['is_monitoring']}")
    print(f"   Video: {status['current_video_id']}")
    print(f"   Detections: {status['detection_count']}")

    # Start monitoring
    try:
        monitor.start_monitoring("video_001")

        # Check status during monitoring
        print("\n📊 Status during monitoring:")
        status = monitor.get_monitoring_status()
        print(f"   Active: {status['is_monitoring']}")
        print(f"   Video: {status['current_video_id']}")
        print(f"   Start time: {status['start_time']:.6f}")
        print(f"   Session ID: {status['session_id']}")
        print(f"   Sample rate: {status['sample_rate']} Hz")

        # Wait a bit
        time.sleep(2)

        # Check status again
        print("\n📊 Status after 2 seconds:")
        status = monitor.get_monitoring_status()
        duration = time.time() - status['start_time']
        print(f"   Active: {status['is_monitoring']}")
        print(f"   Video: {status['current_video_id']}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Detections: {status['detection_count']}")

        # Stop monitoring
        monitor.stop_monitoring("video_001")

        # Check status after monitoring
        print("\n📊 Status after monitoring:")
        status = monitor.get_monitoring_status()
        print(f"   Active: {status['is_monitoring']}")
        print(f"   Video: {status['current_video_id']}")

    except Exception as e:
        print(f"❌ Error: {e}")

    monitor.stop()
    print("\n✅ Status checking complete!")

def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("LABJACK PER-VIDEO MONITORING EXAMPLES")
    print("=" * 80)

    # Note: These examples will fail without actual LabJack hardware
    # They demonstrate the API usage patterns

    try:
        example_single_video()
        example_multiple_videos()
        example_error_handling()
        example_status_checking()

        print("\n" + "=" * 80)
        print("✅ ALL EXAMPLES COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
