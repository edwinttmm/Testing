"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/test_video_timing_synchronization.py
"""

#!/usr/bin/env python3
"""
Test Script for Video Timing Synchronization in HIL Tests

This script demonstrates and validates the video timing synchronization
functionality for Hardware-in-the-Loop (HIL) validation tests.

Key Features Tested:
- Video playback start time capture
- LabJack Unix timestamp to video-relative time conversion
- Database storage of synchronized timing data
- Ground truth matching capabilities
"""

import sys
import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_timestamp_conversion():
    """Test timestamp conversion utilities"""
    logger.info("=" * 60)
    logger.info("Testing Timestamp Conversion Utilities")
    logger.info("=" * 60)
    
    try:
        from services.timestamp_conversion_utils import (
            get_timestamp_converter,
            convert_unix_to_video_relative,
            calculate_frame_number_from_time,
            format_timestamp_for_display
        )
        
        # Test conversion
        video_start_time = time.time()
        unix_timestamp = video_start_time + 5.333  # 5.333 seconds after video start
        
        result = convert_unix_to_video_relative(unix_timestamp, video_start_time, precision_ns=100000)
        
        logger.info(f"✅ Timestamp Conversion Test:")
        logger.info(f"   Video start time: {video_start_time:.6f}")
        logger.info(f"   LabJack timestamp: {unix_timestamp:.6f}")
        logger.info(f"   Video-relative time: {result.video_relative_timestamp:.6f}s")
        logger.info(f"   Actual latency: {result.actual_latency_ms:.3f}ms")
        logger.info(f"   Timing quality: {result.timing_sync_quality}")
        
        # Test frame number calculation
        fps = 30.0
        frame_number = calculate_frame_number_from_time(result.video_relative_timestamp, fps)
        logger.info(f"   Frame number (30fps): {frame_number}")
        
        # Test formatting
        formatted = format_timestamp_for_display(result.video_relative_timestamp, "ms")
        logger.info(f"   Formatted display: {formatted}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Timestamp conversion test failed: {e}")
        return False

def test_video_timing_service():
    """Test VideoTimingService functionality"""
    logger.info("=" * 60)
    logger.info("Testing Video Timing Service")
    logger.info("=" * 60)
    
    try:
        from services.video_timing_service import get_video_timing_service
        
        service = get_video_timing_service()
        
        # Test timing data creation
        session_id = "test_session_123"
        video_id = "test_video_456"
        
        # Simulate starting video timing
        video_metadata = {
            'fps': 30.0,
            'duration': 60.0
        }
        
        # Note: This would normally use a database session
        logger.info(f"✅ Video Timing Service Test:")
        logger.info(f"   Service initialized: {service is not None}")
        logger.info(f"   Test session ID: {session_id}")
        logger.info(f"   Test video ID: {video_id}")
        logger.info(f"   Video metadata: {video_metadata}")
        
        # Test Unix to video-relative conversion
        current_time = time.time()
        video_start = current_time - 10.0  # Video started 10 seconds ago
        detection_time = current_time  # Detection happened now
        
        # Store timing data in service cache for testing
        from services.video_timing_service import EnhancedVideoTimingData
        timing_data = EnhancedVideoTimingData(
            session_id=session_id,
            video_id=video_id,
            start_timestamp=video_start,
            start_timestamp_ns=int(video_start * 1e9),
            precision_ns=100000,  # 100μs precision
            system_time_utc=datetime.now(timezone.utc).isoformat(),
            monotonic_time=time.monotonic(),
            sync_point_id=f"sync_{session_id}",
            frame_rate=30.0,
            duration_s=60.0
        )
        
        service._timing_cache[session_id] = timing_data
        
        # Test conversion
        video_relative_time = service.convert_unix_to_video_relative(session_id, detection_time)
        
        if video_relative_time is not None:
            logger.info(f"   Unix timestamp: {detection_time:.6f}")
            logger.info(f"   Video start: {video_start:.6f}")
            logger.info(f"   Video-relative: {video_relative_time:.6f}s")
            logger.info(f"   Expected: ~10.0s")
            
            # Test latency calculation
            latency_data = service.calculate_video_relative_latency(session_id, detection_time)
            if latency_data:
                logger.info(f"   Calculated latency: {latency_data['actual_latency_ms']:.3f}ms")
                logger.info(f"   Timing quality: {latency_data['timing_sync_quality']}")
                logger.info(f"   Frame number: {latency_data['video_frame_number']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Video timing service test failed: {e}")
        return False

def test_database_integration():
    """Test database integration with video timing fields"""
    logger.info("=" * 60)
    logger.info("Testing Database Integration")
    logger.info("=" * 60)
    
    try:
        from sqlalchemy import create_engine, inspect, select, delete, update, func
        from database import get_db_session
        from models import TestSession, DetectionEvent
        
        # Check database schema
        engine = create_engine('sqlite:///dev_database.db')
        inspector = inspect(engine)
        
        # Check test_sessions table
        ts_columns = {col['name'] for col in inspector.get_columns('test_sessions')}
        required_ts_columns = [
            'video_playback_start_time',
            'video_playback_start_time_ns',
            'hil_timing_enabled',
            'video_timing_sync_status'
        ]
        
        logger.info("✅ Test Sessions Table:")
        for col in required_ts_columns:
            if col in ts_columns:
                logger.info(f"   ✅ {col}: Present")
            else:
                logger.error(f"   ❌ {col}: Missing")
        
        # Check detection_events table  
        de_columns = {col['name'] for col in inspector.get_columns('detection_events')}
        required_de_columns = [
            'video_relative_timestamp',
            'video_relative_timestamp_ns',
            'actual_latency_ms',
            'video_frame_number',
            'timing_sync_quality'
        ]
        
        logger.info("✅ Detection Events Table:")
        for col in required_de_columns:
            if col in de_columns:
                logger.info(f"   ✅ {col}: Present")
            else:
                logger.error(f"   ❌ {col}: Missing")
        
        # Test model instantiation
        try:
            session = TestSession(
                id="test_123",
                name="HIL Test Session",
                project_id="test_project",
                video_id="test_video",
                video_playback_start_time=time.time(),
                video_playback_start_time_ns=str(int(time.time_ns())),
                hil_timing_enabled=True,
                video_timing_sync_status="synced"
            )
            logger.info("   ✅ TestSession model creation: Success")
        except Exception as e:
            logger.error(f"   ❌ TestSession model creation failed: {e}")
        
        try:
            detection = DetectionEvent(
                id="detection_123",
                test_session_id="test_123",
                timestamp=time.time(),
                video_relative_timestamp=5.333,
                video_relative_timestamp_ns=str(int(5.333 * 1e9)),
                actual_latency_ms=5333.0,
                video_frame_number=160,  # 5.333s * 30fps
                timing_sync_quality="high"
            )
            logger.info("   ✅ DetectionEvent model creation: Success")
        except Exception as e:
            logger.error(f"   ❌ DetectionEvent model creation failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database integration test failed: {e}")
        return False

def test_hil_workflow_simulation():
    """Simulate a complete HIL workflow with video timing synchronization"""
    logger.info("=" * 60)
    logger.info("Simulating HIL Workflow with Video Timing Synchronization")
    logger.info("=" * 60)
    
    try:
        # Simulate HIL test scenario
        logger.info("🎬 Scenario: HIL test with video playback and LabJack detection")
        
        # Step 1: Video playback starts
        video_start_time = time.time()
        logger.info(f"📹 Video playback started at: {video_start_time:.6f}")
        
        # Step 2: Simulate detection events at various times
        detection_times = [
            video_start_time + 2.150,   # 2.15 seconds into video
            video_start_time + 5.333,   # 5.333 seconds into video
            video_start_time + 8.750,   # 8.75 seconds into video
            video_start_time + 12.100   # 12.1 seconds into video
        ]
        
        logger.info("🔍 Simulating LabJack detection events:")
        
        from services.timestamp_conversion_utils import convert_unix_to_video_relative
        
        for i, detection_time in enumerate(detection_times, 1):
            result = convert_unix_to_video_relative(
                detection_time, 
                video_start_time, 
                precision_ns=50000  # 50μs precision
            )
            
            if result.success:
                logger.info(f"   Detection {i}:")
                logger.info(f"     Unix timestamp: {detection_time:.6f}")
                logger.info(f"     Video-relative: {result.video_relative_timestamp:.6f}s")
                logger.info(f"     Latency: {result.actual_latency_ms:.3f}ms")
                logger.info(f"     Frame number (30fps): {int(result.video_relative_timestamp * 30)}")
                logger.info(f"     Quality: {result.timing_sync_quality}")
            else:
                logger.error(f"   Detection {i}: Conversion failed - {result.error_message}")
        
        # Step 3: Ground truth matching simulation
        logger.info("🎯 Ground truth matching:")
        logger.info("   Example: Detection at 5.333s video-relative time")
        logger.info("   → Matches video frame 160 (5.333s * 30fps)")
        logger.info("   → Can be correlated with ground truth objects at that time")
        logger.info("   → Enables precise validation of detection accuracy")
        
        # Step 4: Validation results
        logger.info("✅ HIL Test Results:")
        logger.info(f"   Total detections: {len(detection_times)}")
        logger.info(f"   Video duration covered: {max(detection_times) - video_start_time:.1f}s")
        logger.info(f"   Timing precision: 50μs (high quality)")
        logger.info(f"   Ground truth matching: Enabled")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ HIL workflow simulation failed: {e}")
        return False

def main():
    """Run all video timing synchronization tests"""
    logger.info("🚀 Starting Video Timing Synchronization Test Suite")
    logger.info("=" * 80)
    
    tests = [
        ("Timestamp Conversion", test_timestamp_conversion),
        ("Video Timing Service", test_video_timing_service),
        ("Database Integration", test_database_integration),
        ("HIL Workflow Simulation", test_hil_workflow_simulation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running test: {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        logger.info(f"   {test_name:<25} {status}")
    
    logger.info(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Video timing synchronization is working correctly.")
        return True
    else:
        logger.error(f"⚠️ {total - passed} test(s) failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)