#!/usr/bin/env python3
"""
Detection Pipeline End-to-End Test

This script tests the complete detection pipeline from LabJack hardware
through to database storage, identifying exactly where the pipeline breaks.

Focus Areas:
1. Complete HIL test session simulation
2. Detection event capture and storage
3. Ground truth matching integration
4. Database persistence verification
5. Frontend data retrieval simulation
"""

import time
import logging
import sys
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HILTestSimulator:
    """Simulates a complete HIL test session to verify detection pipeline"""
    
    def __init__(self):
        self.session_id = f"pipeline_test_{int(time.time())}"
        self.test_results = {}
        
    def setup_test_environment(self) -> bool:
        """Setup test environment with database and services"""
        logger.info("=== PIPELINE TEST: Environment Setup ===")
        
        try:
            # Import required services
            from database import get_db
            from models import TestSession, Video, DetectionEvent
            
            # Create test database session
            db = next(get_db())
            
            try:
                # Check if we have required tables
                video_count = db.query(Video).count()
                session_count = db.query(TestSession).count()
                
                logger.info(f"📊 Database Status: {video_count} videos, {session_count} test sessions")
                
                # Create test session if needed
                test_session = TestSession(
                    id=self.session_id,
                    name=f"Pipeline Diagnostic Test {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    description="End-to-end pipeline diagnostic test",
                    status="running"
                )
                
                db.add(test_session)
                db.commit()
                
                logger.info(f"✅ Test session created: {self.session_id}")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Environment setup failed: {e}")
            return False
    
    def test_labjack_service_integration(self) -> bool:
        """Test LabJack service integration"""
        logger.info("=== PIPELINE TEST: LabJack Service Integration ===")
        
        try:
            from services.labjack_detection_service import get_detection_service
            detection_service = get_detection_service()
            
            # Add detection callback to capture events
            captured_events = []
            
            def capture_callback(event):
                logger.info(f"🎯 Detection captured via callback: {event}")
                captured_events.append(event)
            
            detection_service.add_detection_callback(capture_callback)
            
            # Start monitoring with realistic HIL parameters
            config = {
                'channels': ['AIN0'],
                'voltage_threshold': 2.5,
                'debounce_ms': 50,
                'sample_rate': 100,  # Higher sample rate for better detection
                'store_in_db': False,  # We'll handle database storage manually
                'enable_websocket': True
            }
            
            success = detection_service.start_monitoring(self.session_id, **config)
            
            if success:
                logger.info("✅ LabJack monitoring started")
                
                # Monitor for events
                logger.info("Monitoring for 10 seconds...")
                monitor_start = time.time()
                
                while time.time() - monitor_start < 10:
                    # Check for events
                    events = detection_service.get_detection_events(self.session_id, from_database=False)
                    if len(events) > len(captured_events):
                        logger.info(f"📊 Events detected: {len(events)} total, {len(captured_events)} via callback")
                    
                    time.sleep(0.5)
                
                # Stop monitoring
                detection_service.stop_monitoring(self.session_id)
                
                final_events = detection_service.get_detection_events(self.session_id, from_database=False)
                logger.info(f"📊 Final count: {len(final_events)} events, {len(captured_events)} callbacks")
                
                self.test_results['labjack_events'] = len(final_events)
                self.test_results['callback_events'] = len(captured_events)
                
                return len(final_events) > 0
            else:
                logger.error("❌ Failed to start LabJack monitoring")
                return False
                
        except Exception as e:
            logger.error(f"❌ LabJack service integration failed: {e}")
            return False
    
    def test_dedicated_monitor_pipeline(self) -> bool:
        """Test dedicated monitor with video timing"""
        logger.info("=== PIPELINE TEST: Dedicated Monitor Pipeline ===")
        
        try:
            from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor
            dedicated_monitor = get_dedicated_labjack_monitor()
            
            # Create realistic video timing configuration
            video_timing_config = {
                'video_id': 'test-video-diagnostic',
                'video_path': '/path/to/test/video.mp4',  # This would normally exist
                'fps': 30,
                'duration': 8,  # 8 seconds
                'channels': ['AIN0'],
                'voltage_threshold': 2.5,
                'debounce_ms': 50,
                'sample_rate': 100,
                'enable_websocket': True
            }
            
            logger.info("Starting dedicated monitor with video sync...")
            success = dedicated_monitor.start_monitoring_with_video_sync(
                self.session_id,
                video_timing_config
            )
            
            if success:
                logger.info("✅ Dedicated monitor started with video sync")
                
                # Monitor for events
                logger.info("Monitoring dedicated pipeline for 10 seconds...")
                monitor_start = time.time()
                
                while time.time() - monitor_start < 10:
                    events = dedicated_monitor.get_session_events(self.session_id)
                    stats = dedicated_monitor.get_monitoring_statistics()
                    
                    logger.info(f"📊 Stats: {stats['total_detections']} total, {len(events)} in session")
                    
                    time.sleep(1)
                
                # Get final statistics
                final_stats = dedicated_monitor.stop_monitoring(self.session_id)
                logger.info(f"📊 Final Statistics: {final_stats}")
                
                self.test_results['dedicated_detections'] = final_stats.get('detection_count', 0)
                self.test_results['average_latency'] = final_stats.get('average_latency_ms', 0)
                
                return final_stats.get('detection_count', 0) > 0
            else:
                logger.error("❌ Failed to start dedicated monitor")
                return False
                
        except Exception as e:
            logger.error(f"❌ Dedicated monitor pipeline failed: {e}")
            return False
    
    def test_database_persistence(self) -> bool:
        """Test database persistence of detection events"""
        logger.info("=== PIPELINE TEST: Database Persistence ===")
        
        try:
            from database import get_db
            from models import DetectionEvent
            
            db = next(get_db())
            
            try:
                # Query detection events for our test session
                detection_events = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == self.session_id
                ).all()
                
                logger.info(f"📊 Found {len(detection_events)} DetectionEvent records in database")
                
                for event in detection_events[:3]:  # Show first 3 events
                    logger.info(f"Event: ID={event.id}, timestamp={event.timestamp}, "
                               f"voltage={getattr(event, 'labjack_voltage', 'N/A')}, "
                               f"channel={getattr(event, 'detection_channel', 'N/A')}")
                
                self.test_results['database_events'] = len(detection_events)
                
                # Test if events have required HIL fields
                hil_fields_present = 0
                for event in detection_events:
                    if (hasattr(event, 'labjack_voltage') and event.labjack_voltage is not None and
                        hasattr(event, 'detection_channel') and event.detection_channel is not None):
                        hil_fields_present += 1
                
                logger.info(f"📊 {hil_fields_present}/{len(detection_events)} events have HIL fields")
                self.test_results['hil_fields_complete'] = hil_fields_present
                
                return len(detection_events) > 0
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Database persistence test failed: {e}")
            return False
    
    def test_api_endpoint_simulation(self) -> bool:
        """Test API endpoint data retrieval"""
        logger.info("=== PIPELINE TEST: API Endpoint Simulation ===")
        
        try:
            # Import required modules for API simulation
            from database import get_db
            from models import DetectionEvent
            import json
            
            db = next(get_db())
            
            try:
                # Simulate HIL results API call
                query = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == self.session_id
                )
                
                detection_events = query.all()
                
                # Convert to API response format
                api_response = {
                    'session_id': self.session_id,
                    'detection_count': len(detection_events),
                    'detections': []
                }
                
                for event in detection_events:
                    detection_data = {
                        'id': event.id,
                        'timestamp': event.timestamp,
                        'validation_result': getattr(event, 'validation_result', 'PENDING'),
                        'processing_time_ms': getattr(event, 'processing_time_ms', None),
                        'labjack_voltage': getattr(event, 'labjack_voltage', None),
                        'detection_channel': getattr(event, 'detection_channel', None),
                        'video_relative_timestamp': getattr(event, 'video_relative_timestamp', None),
                        'actual_latency_ms': getattr(event, 'actual_latency_ms', None)
                    }
                    api_response['detections'].append(detection_data)
                
                # Save API response for analysis
                response_file = f'pipeline_test_api_response_{int(time.time())}.json'
                with open(response_file, 'w') as f:
                    json.dump(api_response, f, indent=2)
                
                logger.info(f"📄 API response saved to: {response_file}")
                logger.info(f"📊 API Response Summary: {len(detection_events)} detections")
                
                # Check data completeness
                complete_detections = sum(1 for d in api_response['detections'] 
                                        if d['labjack_voltage'] is not None)
                
                logger.info(f"📊 Complete detections: {complete_detections}/{len(detection_events)}")
                
                self.test_results['api_response_events'] = len(detection_events)
                self.test_results['complete_events'] = complete_detections
                
                return len(detection_events) > 0
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ API endpoint simulation failed: {e}")
            return False
    
    def test_ground_truth_matching(self) -> bool:
        """Test ground truth matching functionality"""
        logger.info("=== PIPELINE TEST: Ground Truth Matching ===")
        
        try:
            from database import get_db
            from models import GroundTruthObject
            
            db = next(get_db())
            
            try:
                # Check if ground truth data exists
                ground_truth_count = db.query(GroundTruthObject).count()
                logger.info(f"📊 Ground truth objects in database: {ground_truth_count}")
                
                if ground_truth_count > 0:
                    # Sample some ground truth data
                    sample_gt = db.query(GroundTruthObject).limit(3).all()
                    
                    for gt in sample_gt:
                        logger.info(f"Ground Truth: ID={gt.id}, timestamp={gt.timestamp}, "
                                   f"vru_type={getattr(gt, 'vru_type', 'N/A')}")
                
                self.test_results['ground_truth_available'] = ground_truth_count > 0
                self.test_results['ground_truth_count'] = ground_truth_count
                
                return True  # Ground truth test is informational
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Ground truth matching test failed: {e}")
            return False
    
    def cleanup_test_session(self) -> bool:
        """Clean up test session and data"""
        logger.info("=== PIPELINE TEST: Cleanup ===")
        
        try:
            from database import get_db
            from models import TestSession, DetectionEvent
            
            db = next(get_db())
            
            try:
                # Clean up detection events
                detection_events = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == self.session_id
                ).all()
                
                for event in detection_events:
                    db.delete(event)
                
                # Clean up test session
                test_session = db.query(TestSession).filter(
                    TestSession.id == self.session_id
                ).first()
                
                if test_session:
                    db.delete(test_session)
                
                db.commit()
                
                logger.info(f"✅ Cleaned up {len(detection_events)} events and test session")
                return True
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return False
    
    def run_complete_pipeline_test(self) -> Dict[str, Any]:
        """Run complete end-to-end pipeline test"""
        logger.info("🚀 Starting Complete Detection Pipeline Test")
        logger.info("=" * 70)
        
        test_stages = [
            ("Environment Setup", self.setup_test_environment),
            ("LabJack Service Integration", self.test_labjack_service_integration),
            ("Dedicated Monitor Pipeline", self.test_dedicated_monitor_pipeline),
            ("Database Persistence", self.test_database_persistence),
            ("API Endpoint Simulation", self.test_api_endpoint_simulation),
            ("Ground Truth Matching", self.test_ground_truth_matching),
        ]
        
        stage_results = {}
        
        for stage_name, stage_func in test_stages:
            logger.info(f"\n{'=' * 70}")
            try:
                result = stage_func()
                stage_results[stage_name] = result
                status = "✅ PASS" if result else "❌ FAIL"
                logger.info(f"{stage_name}: {status}")
            except Exception as e:
                stage_results[stage_name] = False
                logger.error(f"{stage_name}: ❌ FAIL (Exception: {e})")
        
        # Always try cleanup
        try:
            self.cleanup_test_session()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        
        return {
            'session_id': self.session_id,
            'stage_results': stage_results,
            'test_metrics': self.test_results,
            'overall_success': sum(stage_results.values()) >= 4
        }

def main():
    """Run complete pipeline test"""
    simulator = HILTestSimulator()
    results = simulator.run_complete_pipeline_test()
    
    # Generate summary report
    logger.info(f"\n{'=' * 70}")
    logger.info("📋 COMPLETE PIPELINE TEST REPORT")
    logger.info("=" * 70)
    
    stage_results = results['stage_results']
    test_metrics = results['test_metrics']
    
    passed_stages = sum(stage_results.values())
    total_stages = len(stage_results)
    
    logger.info(f"Session ID: {results['session_id']}")
    logger.info(f"Overall Result: {passed_stages}/{total_stages} stages passed")
    
    logger.info("\nStage Results:")
    for stage, result in stage_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {stage:30}: {status}")
    
    logger.info("\nTest Metrics:")
    for metric, value in test_metrics.items():
        logger.info(f"  {metric:30}: {value}")
    
    # Critical analysis
    logger.info(f"\n{'=' * 70}")
    logger.info("🔍 CRITICAL ANALYSIS")
    logger.info("=" * 70)
    
    if test_metrics.get('labjack_events', 0) == 0:
        logger.error("🚨 CRITICAL: No LabJack events detected - Hardware/Service issue")
    
    if test_metrics.get('database_events', 0) == 0:
        logger.error("🚨 CRITICAL: No database events - Storage pipeline broken")
    
    if test_metrics.get('hil_fields_complete', 0) == 0:
        logger.error("🚨 CRITICAL: No HIL fields in database - Field mapping broken")
    
    if results['overall_success']:
        logger.info("🎉 PIPELINE TEST SUCCESSFUL - Detection system is working")
    else:
        logger.error("🚨 PIPELINE TEST FAILED - Detection system needs repair")
    
    # Save detailed report
    report_file = f'pipeline_diagnostic_report_{int(time.time())}.json'
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"📄 Detailed report saved to: {report_file}")
    
    return results['overall_success']

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)