#!/usr/bin/env python3
"""
Test API Endpoint with Camera Processing Fix

This script tests the actual API endpoint to verify the camera processing fix is working.
"""

import sys
import os
import json
import asyncio
import logging
from unittest.mock import Mock

# Add the backend directory to Python path
sys.path.insert(0, os.path.abspath('.'))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_enhanced_hil_results_endpoint():
    """Test the enhanced HIL results endpoint with camera processing fix"""
    print("🧪 Testing Enhanced HIL Results API Endpoint")
    print("=" * 60)
    
    try:
        # Import the API function
        from src.api.enhanced_hil_results_endpoints import get_corrected_hil_results
        from database import get_db
        from models import TestSession, DetectionEvent
        
        # Create mock database session
        mock_db = Mock()
        
        # Create mock test session
        mock_session = Mock()
        mock_session.id = "test_session_001" 
        mock_session.status = "completed"
        mock_session.started_at = "2024-01-01T10:00:00Z"
        mock_session.completed_at = "2024-01-01T10:05:00Z"
        mock_session.tolerance_ms = 100.0
        mock_session.filename = "test_video.mp4"
        
        # Create mock detection events with realistic data
        mock_detection_1 = Mock()
        mock_detection_1.id = 1
        mock_detection_1.test_session_id = "test_session_001"
        mock_detection_1.frame_number = 150
        mock_detection_1.video_relative_timestamp = 2.3
        mock_detection_1.video_frame_number = 150
        mock_detection_1.timestamp = "2024-01-01T10:02:30Z"
        mock_detection_1.labjack_timestamp = 1735065750.0
        mock_detection_1.processing_time_ms = 52.0
        mock_detection_1.actual_latency_ms = 350.0
        mock_detection_1.voltage_level = 4.25
        mock_detection_1.detection_channel = "AIN0"
        mock_detection_1.validation_result = "pass"
        mock_detection_1.labjack_voltage = 4.25
        
        mock_detection_events = [mock_detection_1]
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_detection_events
        mock_db.execute.return_value.fetchall.return_value = []  # Ground truth events
        
        # Mock timing calculator with realistic corrected results
        from services.timing_synchronization_calculator import TimingSynchronizationResult
        
        corrected_result = TimingSynchronizationResult(
            session_id="test_session_001",
            detection_id="1",
            detection_system_time=1735065750.0,
            video_start_system_time=1735065748.5,  
            gt_video_time=2.3,
            video_startup_delay_ms=1500.0,
            apparent_latency_ms=1850.0,
            real_latency_ms=350.0,
            latency_correction_ms=-1500.0,
            matches_processing_time=True,
            expected_processing_time_ms=75.0,
            timing_quality="good",
            calculation_timestamp=1735065750.0,
            confidence_score=0.75,
            camera_only_latency_ms=280.0,  # This should now appear in the API response
            system_overhead_ms=52.0,
            processing_overhead_ms=18.0,
            decomposition_confidence=0.8
        )
        
        # Mock timing calculator service
        from services.timing_synchronization_calculator import get_timing_synchronization_calculator
        timing_calc = get_timing_synchronization_calculator()
        timing_calc.calculations = {"test_session_001": [corrected_result]}
        
        # Mock session statistics
        def mock_get_session_stats(session_id):
            return {
                "session_id": session_id,
                "total_calculations": 1,
                "real_latency_stats": {"average_ms": 350.0, "median_ms": 350.0},
                "apparent_latency_stats": {"average_ms": 1850.0, "median_ms": 1850.0},
                "correction_stats": {"average_correction_ms": -1500.0},
                "validation": {
                    "detections_matching_processing_time": 1,
                    "percentage_matching": 100.0,
                    "average_confidence_score": 0.75,
                    "average_decomposition_confidence": 0.8,
                    "timing_quality_distribution": {"good": 1}
                },
                "timing_synchronization": {
                    "latency_improvement": {
                        "average_apparent_ms": 1850.0,
                        "average_real_ms": 350.0,
                        "improvement_ms": 1500.0,
                        "improvement_percentage": 81.1
                    }
                }
            }
        
        timing_calc.get_session_statistics = mock_get_session_stats
        
        print("📊 Calling API endpoint...")
        
        # Call the API endpoint
        response = await get_corrected_hil_results("test_session_001", mock_db)
        
        print("✅ API endpoint returned successfully")
        print()
        
        # Extract and verify camera processing measurement
        detection_events = response.get("detection_events", [])
        if detection_events:
            detection = detection_events[0]
            measured_breakdown = detection.get("measured_breakdown", {})
            
            # Test the fixed values
            camera_processing_ms = measured_breakdown.get("camera_processing_ms", "NOT_FOUND")
            system_processing_ms = measured_breakdown.get("system_processing_ms", "NOT_FOUND")
            total_measured_ms = measured_breakdown.get("total_measured_latency_ms", "NOT_FOUND")
            measurement_note = measured_breakdown.get("measurement_note", "NOT_FOUND")
            
            print("🔧 Camera Processing Fix Results:")
            print(f"   Camera Processing: {camera_processing_ms}ms ✅")
            print(f"   System Processing: {system_processing_ms}ms ✅")
            print(f"   Total Measured: {total_measured_ms}ms ✅")
            print(f"   Measurement Note: {measurement_note}")
            print()
            
            # Check validation quality
            validation_quality = response.get("validation_quality", {})
            measurement_quality = validation_quality.get("measurement_quality", "NOT_FOUND")
            average_confidence = validation_quality.get("average_confidence_score", "NOT_FOUND")
            
            print("📈 Quality Assessment:")
            print(f"   Overall Quality: {measurement_quality}")
            print(f"   Average Confidence: {average_confidence}")
            print()
            
            # Validation checks
            print("🔍 Validation Checks:")
            
            # Check 1: Camera processing is now a number, not "Cannot measure directly"
            camera_is_number = isinstance(camera_processing_ms, (int, float)) and camera_processing_ms > 0
            print(f"   ✅ Camera processing is measurable: {camera_is_number}")
            
            # Check 2: Total measured is not 0
            total_not_zero = isinstance(total_measured_ms, (int, float)) and total_measured_ms > 0
            print(f"   ✅ Total measured is not zero: {total_not_zero}")
            
            # Check 3: No "Cannot measure" in measurement note
            no_cannot_measure = "Cannot measure" not in str(measurement_note)
            print(f"   ✅ No 'Cannot measure' messages: {no_cannot_measure}")
            
            # Check 4: Quality improved
            quality_improved = "poor (confidence: 20%)" not in str(measurement_quality)
            print(f"   ✅ Quality assessment improved: {quality_improved}")
            
            print()
            
            if camera_is_number and total_not_zero and no_cannot_measure and quality_improved:
                print("🎉 ALL CHECKS PASSED: Camera Processing Fix is working!")
                return True
            else:
                print("❌ Some checks failed - fix needs more work")
                return False
        else:
            print("❌ No detection events found in response")
            return False
            
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 API Endpoint Test for Camera Processing Fix")
    print("Testing: Enhanced HIL Results API endpoint")
    print("="*80)
    
    # Run async test
    success = asyncio.run(test_enhanced_hil_results_endpoint())
    
    print("="*80)
    if success:
        print("✅ CAMERA PROCESSING FIX: SUCCESS")
        print("   The API now properly calculates and displays:")
        print("   • Camera Processing: Actual measured value (not 'Cannot measure directly')")
        print("   • Total Measured: Sum of all components (not 0ms)")
        print("   • Quality Assessment: Improved confidence scoring")
    else:
        print("❌ CAMERA PROCESSING FIX: NEEDS MORE WORK")
        print("   Some validation checks failed - review the implementation")