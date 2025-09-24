#!/usr/bin/env python3
"""
Timing Regression Fix Verification Test

This test verifies that the timing regression causing -167ms, -125ms, -83ms
misalignments has been fixed and frame alignment now shows ~0ms.
"""

import time
import logging
from typing import Dict, Any, List

# Import timing services
from services.video_timing_service import get_video_timing_service
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
from database import SessionLocal

logger = logging.getLogger(__name__)

class TimingRegressionTest:
    """Test suite for timing regression fix verification"""
    
    def __init__(self):
        self.video_timing_service = get_video_timing_service()
        self.monitor = get_dedicated_labjack_monitor()
        self.db = SessionLocal()
        
    def test_frame_alignment_fix(self) -> bool:
        """
        Test that frame alignment now shows ~0ms instead of -167ms, -125ms, -83ms
        
        Returns:
            True if fix is successful, False if regression persists
        """
        try:
            logger.info("🧪 Testing timing regression fix...")
            
            # Test session setup
            session_id = "timing_regression_test"
            video_id = "test_video_24fps"
            
            # Test video metadata (24fps)
            video_metadata = {
                'fps': 24.0,
                'duration': 5.0,
                'resolution': '640x480'
            }
            
            # Start video timing
            video_start_time = self.video_timing_service.start_video_timing(
                session_id, video_id, self.db, video_metadata
            )
            
            if not video_start_time:
                logger.error("❌ Failed to start video timing")
                return False
                
            logger.info(f"✅ Video timing started: {video_start_time:.6f}")
            
            # Test frame alignment at expected times
            expected_frame_times = [
                (1, 0.042),  # Frame 1 at 42ms (24fps)
                (2, 0.083),  # Frame 2 at 83ms (24fps)  
                (3, 0.125),  # Frame 3 at 125ms (24fps)
            ]
            
            results = []
            
            for frame_num, expected_time in expected_frame_times:
                # Simulate detection at expected frame time
                detection_unix_time = video_start_time + expected_time
                
                # Calculate video-relative timing
                timing_result = self.video_timing_service.calculate_video_relative_latency(
                    session_id, detection_unix_time, self.db
                )
                
                if not timing_result:
                    logger.error(f"❌ Failed to calculate timing for frame {frame_num}")
                    return False
                
                # Get video-relative timestamp and latency
                video_relative_time = timing_result['video_relative_timestamp']
                latency_ms = timing_result['actual_latency_ms']
                
                # Calculate alignment error (should be ~0ms after fix)
                expected_video_time = expected_time
                alignment_error_ms = (video_relative_time - expected_video_time) * 1000
                
                results.append({
                    'frame': frame_num,
                    'expected_time': expected_time,
                    'video_relative_time': video_relative_time,
                    'alignment_error_ms': alignment_error_ms,
                    'latency_ms': latency_ms
                })
                
                # Check if fix is working
                if abs(alignment_error_ms) < 10:  # Within 10ms tolerance
                    logger.info(f"✅ Frame {frame_num}: {alignment_error_ms:.1f}ms alignment (FIXED)")
                else:
                    logger.error(f"❌ Frame {frame_num}: {alignment_error_ms:.1f}ms alignment (STILL BROKEN)")
            
            # Analyze results
            return self._analyze_fix_results(results)
            
        except Exception as e:
            logger.error(f"❌ Timing regression test failed: {e}")
            return False
        finally:
            self._cleanup(session_id)
    
    def _analyze_fix_results(self, results: List[Dict[str, Any]]) -> bool:
        """
        Analyze test results to determine if fix is successful
        
        Args:
            results: List of timing test results
            
        Returns:
            True if fix is successful, False if regression persists
        """
        logger.info("📊 Timing Regression Fix Analysis:")
        logger.info("=" * 60)
        
        passed = 0
        failed = 0
        
        for result in results:
            frame = result['frame']
            alignment_error = result['alignment_error_ms']
            
            # Check for the specific regression pattern
            if frame == 1 and abs(alignment_error + 167) < 5:
                logger.error(f"❌ Frame {frame}: {alignment_error:.1f}ms (REGRESSION: Still showing -167ms pattern)")
                failed += 1
            elif frame == 2 and abs(alignment_error + 125) < 5:
                logger.error(f"❌ Frame {frame}: {alignment_error:.1f}ms (REGRESSION: Still showing -125ms pattern)")
                failed += 1
            elif frame == 3 and abs(alignment_error + 83) < 5:
                logger.error(f"❌ Frame {frame}: {alignment_error:.1f}ms (REGRESSION: Still showing -83ms pattern)")
                failed += 1
            elif abs(alignment_error) < 10:
                logger.info(f"✅ Frame {frame}: {alignment_error:.1f}ms alignment (FIXED)")
                passed += 1
            else:
                logger.warning(f"⚠️ Frame {frame}: {alignment_error:.1f}ms alignment (UNKNOWN ISSUE)")
                failed += 1
        
        logger.info("=" * 60)
        logger.info(f"Results: {passed} passed, {failed} failed")
        
        if passed == len(results):
            logger.info("🎉 TIMING REGRESSION FIX SUCCESSFUL!")
            return True
        else:
            logger.error("💥 TIMING REGRESSION STILL PRESENT!")
            return False
    
    def test_duration_auto_stop_preserved(self) -> bool:
        """
        Test that duration auto-stop functionality is preserved after timing fix
        
        Returns:
            True if duration functionality still works, False if broken
        """
        try:
            logger.info("🧪 Testing duration auto-stop preservation...")
            
            session_id = "duration_test_session"
            
            # Short test duration for quick verification
            test_config = {
                'video_id': 'duration_test_video',
                'fps': 24,
                'duration': 2.0,  # 2 second test
                'channels': ['AIN0'],
                'voltage_threshold': 2.5
            }
            
            # Start monitoring with auto-stop
            success = self.monitor.start_monitoring_with_video_sync(session_id, test_config)
            
            if not success:
                logger.error("❌ Failed to start monitoring with duration")
                return False
            
            logger.info("⏱️ Waiting for auto-stop (should occur after 2s + grace period)...")
            
            # Wait for auto-stop (2s duration + grace period)
            time.sleep(3)
            
            # Check if monitoring stopped automatically
            stats = self.monitor.get_monitoring_statistics()
            active_sessions = stats.get('active_sessions', 0)
            
            if active_sessions == 0:
                logger.info("✅ Duration auto-stop preserved (monitoring stopped automatically)")
                return True
            else:
                logger.error("❌ Duration auto-stop broken (monitoring still active)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Duration preservation test failed: {e}")
            return False
        finally:
            # Force cleanup
            try:
                self.monitor.stop_monitoring(session_id)
            except:
                pass
    
    def _cleanup(self, session_id: str):
        """Cleanup test resources"""
        try:
            self.video_timing_service.clear_session_timing(session_id)
            self.monitor.cleanup_session_data(session_id)
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
    
    def run_full_test_suite(self) -> bool:
        """
        Run complete timing regression fix verification
        
        Returns:
            True if all tests pass, False if any test fails
        """
        logger.info("🚀 Starting timing regression fix verification suite")
        logger.info("=" * 80)
        
        tests = [
            ("Frame Alignment Fix", self.test_frame_alignment_fix),
            ("Duration Auto-Stop Preservation", self.test_duration_auto_stop_preserved)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            logger.info(f"\n📋 Running: {test_name}")
            try:
                if test_func():
                    logger.info(f"✅ {test_name}: PASSED")
                    passed += 1
                else:
                    logger.error(f"❌ {test_name}: FAILED")
                    failed += 1
            except Exception as e:
                logger.error(f"❌ {test_name}: ERROR - {e}")
                failed += 1
        
        logger.info("\n" + "=" * 80)
        logger.info(f"TIMING REGRESSION FIX VERIFICATION RESULTS:")
        logger.info(f"  Total Tests: {len(tests)}")
        logger.info(f"  Passed: {passed}")
        logger.info(f"  Failed: {failed}")
        
        if failed == 0:
            logger.info("🎉 ALL TESTS PASSED - TIMING REGRESSION FIX SUCCESSFUL!")
            return True
        else:
            logger.error("💥 SOME TESTS FAILED - TIMING REGRESSION STILL PRESENT!")
            return False


def main():
    """Main test execution"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        test_suite = TimingRegressionTest()
        success = test_suite.run_full_test_suite()
        exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Test suite execution failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()