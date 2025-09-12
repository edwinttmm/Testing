"""
Video Timing Service Usage Examples

This file demonstrates how to use the VideoTimingService for precise
latency measurement with LabJack detection events.

Usage Examples:
1. Basic video timing start/stop
2. Latency calculation
3. LabJack synchronization
4. API endpoint usage
"""

import time
import uuid
from typing import Optional

# Example usage patterns (without actual imports for documentation)

def example_basic_usage():
    """Example: Basic video timing usage"""
    
    print("=== Basic Video Timing Usage ===")
    
    # In your application, you would import:
    # from services.video_timing_service import get_video_timing_service
    
    # Get service instance
    # timing_service = get_video_timing_service()
    
    session_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())
    
    print(f"Session ID: {session_id}")
    print(f"Video ID: {video_id}")
    
    # Start video timing when video playback begins
    # start_timestamp = timing_service.start_video_timing(session_id, video_id, db_session)
    start_timestamp = time.time()  # Simulated
    
    print(f"Video started at: {start_timestamp:.6f}")
    
    # Simulate video playing for some time...
    time.sleep(0.1)  # 100ms
    
    # Simulate LabJack detection event
    detection_timestamp = time.time()
    
    # Calculate latency
    # measurement = timing_service.calculate_latency(session_id, detection_timestamp, db_session)
    latency_ms = (detection_timestamp - start_timestamp) * 1000
    
    print(f"Detection at: {detection_timestamp:.6f}")
    print(f"Calculated latency: {latency_ms:.3f}ms")


def example_api_usage():
    """Example: Using API endpoints"""
    
    print("\n=== API Endpoint Usage ===")
    
    session_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())
    
    # Example API calls (using requests or httpx)
    
    # 1. Start video timing
    start_payload = {
        "video_id": video_id,
        "sync_labjack": True
    }
    print(f"POST /api/sessions/{session_id}/start-video")
    print(f"Payload: {start_payload}")
    
    # 2. Get timing data
    print(f"GET /api/sessions/{session_id}/video-timing")
    
    # 3. Calculate latency
    latency_payload = {
        "detection_timestamp": time.time() + 0.075  # 75ms later
    }
    print(f"POST /api/sessions/{session_id}/calculate-latency")
    print(f"Payload: {latency_payload}")
    
    # 4. Get timing statistics
    print(f"GET /api/sessions/{session_id}/timing-stats")
    
    # 5. Clear timing data
    print(f"DELETE /api/sessions/{session_id}/clear-timing")


def example_labjack_integration():
    """Example: LabJack service integration"""
    
    print("\n=== LabJack Integration Example ===")
    
    # In your application:
    # from services.video_timing_service import get_video_timing_service
    # from services.labjack_service import get_labjack_service
    
    session_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())
    
    print(f"Integrating video timing with LabJack for session: {session_id}")
    
    # Step 1: Start video timing
    # timing_service = get_video_timing_service()
    # video_start_time = timing_service.start_video_timing(session_id, video_id, db)
    video_start_time = time.time()
    
    print(f"Video timing started: {video_start_time:.6f}")
    
    # Step 2: Synchronize with LabJack
    # labjack_service = get_labjack_service()
    # sync_success = timing_service.synchronize_with_labjack(session_id, labjack_service)
    sync_success = True  # Simulated
    
    print(f"LabJack synchronization: {'✓' if sync_success else '✗'}")
    
    # Step 3: Simulate LabJack detection
    detection_delay = 0.125  # 125ms detection latency
    detection_time = video_start_time + detection_delay
    
    # Step 4: Calculate precise latency
    # measurement = timing_service.calculate_latency(session_id, detection_time, db)
    calculated_latency = detection_delay * 1000  # Convert to ms
    
    print(f"Detection timestamp: {detection_time:.6f}")
    print(f"Measured latency: {calculated_latency:.3f}ms")
    
    # Step 5: Validate against tolerance
    tolerance_ms = 100
    is_within_tolerance = calculated_latency <= tolerance_ms
    
    print(f"Tolerance: {tolerance_ms}ms")
    print(f"Result: {'PASS' if is_within_tolerance else 'FAIL'}")


def example_precision_analysis():
    """Example: Timer precision analysis"""
    
    print("\n=== Timer Precision Analysis ===")
    
    # Analyze system timer precision
    samples = []
    for i in range(100):
        t1 = time.time_ns()
        t2 = time.time_ns()
        if t2 > t1:
            samples.append(t2 - t1)
    
    if samples:
        min_precision = min(samples)
        avg_precision = sum(samples) / len(samples)
        max_precision = max(samples)
        
        print(f"Timer precision analysis (100 samples):")
        print(f"- Minimum: {min_precision}ns")
        print(f"- Average: {avg_precision:.1f}ns")
        print(f"- Maximum: {max_precision}ns")
        
        # Precision classification
        if min_precision < 1000:  # < 1μs
            precision_class = "excellent"
        elif min_precision < 10000:  # < 10μs
            precision_class = "high"
        elif min_precision < 100000:  # < 100μs
            precision_class = "standard"
        else:
            precision_class = "low"
        
        print(f"- Precision class: {precision_class}")
        print(f"- Suitable for latency measurement: {'✓' if min_precision < 50000 else '✗'}")


def example_error_handling():
    """Example: Error handling patterns"""
    
    print("\n=== Error Handling Examples ===")
    
    # 1. Session not found
    fake_session_id = str(uuid.uuid4())
    print(f"Testing with non-existent session: {fake_session_id}")
    
    # API would return 404
    print("Expected API response: 404 Not Found")
    
    # 2. No video timing data
    print("Testing latency calculation without video timing:")
    print("Expected result: None (no measurement possible)")
    
    # 3. LabJack service unavailable
    print("Testing LabJack synchronization when service unavailable:")
    print("Expected result: False (synchronization failed)")
    
    # 4. Database connection issues
    print("Testing with database connection issues:")
    print("Expected behavior: Fallback to cache, log errors")


def example_performance_optimization():
    """Example: Performance optimization techniques"""
    
    print("\n=== Performance Optimization ===")
    
    # 1. Batch operations
    print("Batch multiple video timing operations:")
    session_count = 5
    
    for i in range(session_count):
        session_id = f"session_{i}"
        video_id = f"video_{i}"
        start_time = time.time()
        
        print(f"  Session {i}: {start_time:.6f}")
    
    # 2. Memory management
    print("\nMemory management:")
    print("- Clear timing data after test completion")
    print("- Use database for persistence across sessions")
    print("- Monitor cache size and active sessions")
    
    # 3. Thread safety
    print("\nThread safety:")
    print("- Service uses threading.RLock for concurrent access")
    print("- Singleton pattern for service instance")
    print("- Atomic operations for timestamp recording")


def main():
    """Run all examples"""
    
    print("Video Timing Service Usage Examples")
    print("=" * 50)
    
    example_basic_usage()
    example_api_usage()
    example_labjack_integration()
    example_precision_analysis()
    example_error_handling()
    example_performance_optimization()
    
    print("\n" + "=" * 50)
    print("Examples completed successfully!")
    print("See video_timing_service.py for full implementation details.")


if __name__ == "__main__":
    main()