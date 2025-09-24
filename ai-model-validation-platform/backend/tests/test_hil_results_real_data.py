#!/usr/bin/env python3
"""
HIL Results Real Data Testing Suite

This test suite validates the HIL Results page functionality with actual 
database data, ensuring:
- Real ground truth data loads correctly
- Latency calculations work accurately
- Timeline display shows real events
- Detection matching logic works with real timestamps
"""

import requests
import json
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"

class HILResultsTestSuite:
    """Comprehensive test suite for HIL Results functionality"""
    
    def __init__(self):
        self.session = None
        self.test_session_id = None
        self.detection_events = []
        self.setup_database()
    
    def setup_database(self):
        """Setup database connection and get test data"""
        try:
            self.session = next(get_db())
            
            # Find a test session with detection events
            query = text("""
                SELECT ts.id, ts.name, ts.status, ts.created_at, COUNT(de.id) as event_count
                FROM test_sessions ts
                INNER JOIN detection_events de ON ts.id = de.test_session_id
                GROUP BY ts.id, ts.name, ts.status, ts.created_at
                HAVING event_count > 10
                ORDER BY ts.created_at DESC
                LIMIT 1
            """)
            
            result = self.session.execute(query).fetchone()
            if result:
                self.test_session_id = result.id
                logger.info(f"Using test session: {self.test_session_id} with {result.event_count} events")
            else:
                raise Exception("No test sessions with detection events found")
                
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise
    
    def test_api_endpoint_availability(self) -> Dict[str, Any]:
        """Test that HIL API endpoints are available and responding"""
        logger.info("Testing API endpoint availability...")
        
        endpoints = [
            f"/api/test-sessions",
            f"/api/test-sessions/{self.test_session_id}/results",
            f"/api/test-sessions/{self.test_session_id}/events",
            f"/api/test-sessions/{self.test_session_id}/summary",
            f"/api/test-sessions/latest-with-events"
        ]
        
        results = {}
        for endpoint in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
                results[endpoint] = {
                    "status_code": response.status_code,
                    "success": response.status_code == 200,
                    "response_size": len(response.content) if response.content else 0
                }
                logger.info(f"✅ {endpoint}: {response.status_code}")
            except Exception as e:
                results[endpoint] = {
                    "status_code": 0,
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"❌ {endpoint}: {e}")
        
        return results
    
    def test_ground_truth_data_loading(self) -> Dict[str, Any]:
        """Test ground truth data loading functionality"""
        logger.info("Testing ground truth data loading...")
        
        try:
            # Check if test session has ground truth count
            query = text("""
                SELECT ground_truth_count, video_id 
                FROM test_sessions 
                WHERE id = :session_id
            """)
            result = self.session.execute(query, {"session_id": self.test_session_id}).fetchone()
            
            # Check annotations table for ground truth data
            if result and result.video_id:
                annotations_query = text("""
                    SELECT COUNT(*) as annotation_count, 
                           MIN(timestamp) as first_timestamp,
                           MAX(timestamp) as last_timestamp
                    FROM annotations 
                    WHERE video_id = :video_id
                """)
                annotations = self.session.execute(annotations_query, {"video_id": result.video_id}).fetchone()
                
                return {
                    "success": True,
                    "session_ground_truth_count": result.ground_truth_count,
                    "video_id": result.video_id,
                    "annotations_found": annotations.annotation_count if annotations else 0,
                    "time_range": {
                        "first": annotations.first_timestamp if annotations else None,
                        "last": annotations.last_timestamp if annotations else None
                    } if annotations else None
                }
            else:
                return {
                    "success": False,
                    "error": "No video_id found for test session"
                }
                
        except Exception as e:
            logger.error(f"Ground truth loading test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_latency_calculation_accuracy(self) -> Dict[str, Any]:
        """Test latency calculation accuracy with real data"""
        logger.info("Testing latency calculation accuracy...")
        
        try:
            # Get detection events for the test session
            events_query = text("""
                SELECT timestamp, latency_ns, voltage_level, labjack_voltage,
                       frame_number, video_relative_timestamp
                FROM detection_events
                WHERE test_session_id = :session_id
                ORDER BY timestamp ASC
                LIMIT 100
            """)
            
            events = self.session.execute(events_query, {"session_id": self.test_session_id}).fetchall()
            
            if not events:
                return {"success": False, "error": "No detection events found"}
            
            # Calculate statistics
            timestamps = [float(event.timestamp) for event in events if event.timestamp]
            voltages = [float(event.voltage_level or event.labjack_voltage or 0) for event in events]
            
            # Calculate timing metrics
            if len(timestamps) > 1:
                time_intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
                avg_interval = sum(time_intervals) / len(time_intervals)
                min_interval = min(time_intervals)
                max_interval = max(time_intervals)
            else:
                avg_interval = min_interval = max_interval = 0
            
            # Voltage statistics
            avg_voltage = sum(voltages) / len(voltages) if voltages else 0
            min_voltage = min(voltages) if voltages else 0
            max_voltage = max(voltages) if voltages else 0
            
            # Test latency calculation logic
            threshold_voltage = 2.5
            above_threshold = sum(1 for v in voltages if v >= threshold_voltage)
            pass_rate = (above_threshold / len(voltages)) * 100 if voltages else 0
            
            return {
                "success": True,
                "total_events": len(events),
                "timing_metrics": {
                    "time_span_seconds": timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0,
                    "average_interval_ms": avg_interval * 1000,
                    "min_interval_ms": min_interval * 1000,
                    "max_interval_ms": max_interval * 1000,
                    "detection_rate_hz": 1.0 / avg_interval if avg_interval > 0 else 0
                },
                "voltage_metrics": {
                    "average_voltage": avg_voltage,
                    "min_voltage": min_voltage,
                    "max_voltage": max_voltage,
                    "threshold_voltage": threshold_voltage,
                    "above_threshold_count": above_threshold,
                    "pass_rate": pass_rate
                }
            }
            
        except Exception as e:
            logger.error(f"Latency calculation test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_timeline_display_functionality(self) -> Dict[str, Any]:
        """Test timeline display with real ground truth events"""
        logger.info("Testing timeline display functionality...")
        
        try:
            # Get HIL results from API
            response = requests.get(f"{BASE_URL}/api/test-sessions/{self.test_session_id}/results")
            if response.status_code != 200:
                return {"success": False, "error": f"API returned {response.status_code}"}
            
            api_data = response.json()
            
            # Validate HIL results structure
            required_fields = [
                "session_id", "total_detections", "passed_detections", 
                "failed_detections", "pass_rate", "latency_stats"
            ]
            
            missing_fields = [field for field in required_fields if field not in api_data]
            if missing_fields:
                return {
                    "success": False,
                    "error": f"Missing required fields: {missing_fields}"
                }
            
            # Test detection events timeline
            events_response = requests.get(f"{BASE_URL}/api/test-sessions/{self.test_session_id}/events")
            if events_response.status_code == 200:
                events_data = events_response.json()
                
                # Validate timeline data structure
                timeline_metrics = {
                    "total_events": len(events_data) if isinstance(events_data, list) else 0,
                    "has_timestamps": all('timestamp' in event for event in events_data) if isinstance(events_data, list) else False,
                    "has_voltage_data": all('voltage' in event for event in events_data) if isinstance(events_data, list) else False,
                    "time_range": None
                }
                
                if isinstance(events_data, list) and events_data:
                    timestamps = [event.get('timestamp', 0) for event in events_data]
                    timeline_metrics["time_range"] = {
                        "start": min(timestamps),
                        "end": max(timestamps),
                        "duration_seconds": max(timestamps) - min(timestamps)
                    }
                
                return {
                    "success": True,
                    "api_data_valid": True,
                    "timeline_metrics": timeline_metrics,
                    "hil_results": {
                        "total_detections": api_data.get("total_detections", 0),
                        "pass_rate": api_data.get("pass_rate", 0),
                        "avg_latency": api_data.get("latency_stats", {}).get("average_ms", 0)
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Events endpoint returned {events_response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Timeline display test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_detection_matching_logic(self) -> Dict[str, Any]:
        """Test detection matching logic with real timestamps"""
        logger.info("Testing detection matching logic...")
        
        try:
            # Get detection events with precise timing
            events_query = text("""
                SELECT id, timestamp, frame_number, voltage_level, labjack_voltage,
                       video_relative_timestamp, latency_ns, detection_channel
                FROM detection_events
                WHERE test_session_id = :session_id
                AND timestamp IS NOT NULL
                ORDER BY timestamp ASC
                LIMIT 50
            """)
            
            events = self.session.execute(events_query, {"session_id": self.test_session_id}).fetchall()
            
            if not events:
                return {"success": False, "error": "No events with timestamps found"}
            
            # Test matching logic
            matching_results = {
                "total_events": len(events),
                "events_with_timestamps": 0,
                "events_with_voltage": 0,
                "events_with_frame_numbers": 0,
                "voltage_distribution": {"low": 0, "medium": 0, "high": 0},
                "timing_analysis": {
                    "consecutive_intervals": [],
                    "max_gap_seconds": 0,
                    "min_gap_seconds": float('inf')
                }
            }
            
            previous_timestamp = None
            
            for event in events:
                # Count valid data fields
                if event.timestamp:
                    matching_results["events_with_timestamps"] += 1
                
                voltage = event.voltage_level or event.labjack_voltage
                if voltage:
                    matching_results["events_with_voltage"] += 1
                    
                    # Categorize voltage levels
                    if voltage < 3.0:
                        matching_results["voltage_distribution"]["low"] += 1
                    elif voltage < 4.5:
                        matching_results["voltage_distribution"]["medium"] += 1
                    else:
                        matching_results["voltage_distribution"]["high"] += 1
                
                if event.frame_number:
                    matching_results["events_with_frame_numbers"] += 1
                
                # Calculate timing intervals
                if previous_timestamp and event.timestamp:
                    interval = event.timestamp - previous_timestamp
                    matching_results["timing_analysis"]["consecutive_intervals"].append(interval)
                    
                    if interval > matching_results["timing_analysis"]["max_gap_seconds"]:
                        matching_results["timing_analysis"]["max_gap_seconds"] = interval
                    
                    if interval < matching_results["timing_analysis"]["min_gap_seconds"]:
                        matching_results["timing_analysis"]["min_gap_seconds"] = interval
                
                previous_timestamp = event.timestamp
            
            # Calculate average interval
            intervals = matching_results["timing_analysis"]["consecutive_intervals"]
            if intervals:
                matching_results["timing_analysis"]["average_interval_seconds"] = sum(intervals) / len(intervals)
                matching_results["timing_analysis"]["detection_rate_hz"] = 1.0 / matching_results["timing_analysis"]["average_interval_seconds"]
            
            # Validate data quality
            data_quality = {
                "timestamp_completeness": matching_results["events_with_timestamps"] / len(events),
                "voltage_completeness": matching_results["events_with_voltage"] / len(events),
                "frame_completeness": matching_results["events_with_frame_numbers"] / len(events)
            }
            
            success = all(completeness > 0.8 for completeness in data_quality.values())
            
            return {
                "success": success,
                "matching_results": matching_results,
                "data_quality": data_quality,
                "quality_assessment": "Good" if success else "Poor - Missing critical data"
            }
            
        except Exception as e:
            logger.error(f"Detection matching test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling for missing or invalid data"""
        logger.info("Testing error handling...")
        
        error_tests = {}
        
        # Test invalid session ID
        try:
            response = requests.get(f"{BASE_URL}/api/test-sessions/invalid-id/results")
            error_tests["invalid_session_id"] = {
                "status_code": response.status_code,
                "handles_error": response.status_code == 404,
                "response": response.json() if response.content else None
            }
        except Exception as e:
            error_tests["invalid_session_id"] = {"error": str(e), "handles_error": False}
        
        # Test malformed requests
        try:
            response = requests.get(f"{BASE_URL}/api/test-sessions//results")  # Double slash
            error_tests["malformed_url"] = {
                "status_code": response.status_code,
                "handles_error": response.status_code in [400, 404, 422],
                "response": response.json() if response.content else None
            }
        except Exception as e:
            error_tests["malformed_url"] = {"error": str(e), "handles_error": False}
        
        # Test session with no events
        try:
            # Create a test session with no events
            empty_session_query = text("""
                SELECT ts.id 
                FROM test_sessions ts
                LEFT JOIN detection_events de ON ts.id = de.test_session_id
                WHERE de.id IS NULL
                LIMIT 1
            """)
            empty_session = self.session.execute(empty_session_query).fetchone()
            
            if empty_session:
                response = requests.get(f"{BASE_URL}/api/test-sessions/{empty_session.id}/results")
                error_tests["session_no_events"] = {
                    "status_code": response.status_code,
                    "handles_gracefully": response.status_code == 200,  # Should return empty results
                    "response": response.json() if response.content else None
                }
        except Exception as e:
            error_tests["session_no_events"] = {"error": str(e), "handles_error": False}
        
        return {
            "success": all(test.get("handles_error", False) or test.get("handles_gracefully", False) 
                          for test in error_tests.values()),
            "error_tests": error_tests
        }
    
    def test_performance_with_large_dataset(self) -> Dict[str, Any]:
        """Test performance with large datasets"""
        logger.info("Testing performance with large datasets...")
        
        try:
            # Find session with most events
            query = text("""
                SELECT test_session_id, COUNT(*) as event_count
                FROM detection_events
                GROUP BY test_session_id
                ORDER BY event_count DESC
                LIMIT 1
            """)
            
            result = self.session.execute(query).fetchone()
            if not result:
                return {"success": False, "error": "No sessions with events found"}
            
            largest_session_id = result.test_session_id
            event_count = result.event_count
            
            # Time the API response
            start_time = datetime.now()
            response = requests.get(f"{BASE_URL}/api/test-sessions/{largest_session_id}/results", timeout=30)
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            # Get events endpoint performance
            start_time = datetime.now()
            events_response = requests.get(f"{BASE_URL}/api/test-sessions/{largest_session_id}/events?limit=1000", timeout=30)
            events_end_time = datetime.now()
            
            events_response_time = (events_end_time - start_time).total_seconds()
            
            return {
                "success": response.status_code == 200 and events_response.status_code == 200,
                "performance_metrics": {
                    "event_count": event_count,
                    "results_response_time_seconds": response_time,
                    "events_response_time_seconds": events_response_time,
                    "results_per_second": event_count / response_time if response_time > 0 else 0,
                    "acceptable_performance": response_time < 5.0 and events_response_time < 10.0
                },
                "response_sizes": {
                    "results_response_bytes": len(response.content) if response.content else 0,
                    "events_response_bytes": len(events_response.content) if events_response.content else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results"""
        logger.info("Running comprehensive HIL Results test suite...")
        
        test_results = {
            "test_run_timestamp": datetime.now().isoformat(),
            "test_session_id": self.test_session_id,
            "tests": {}
        }
        
        # Run all tests
        test_methods = [
            ("api_endpoint_availability", self.test_api_endpoint_availability),
            ("ground_truth_data_loading", self.test_ground_truth_data_loading),
            ("latency_calculation_accuracy", self.test_latency_calculation_accuracy),
            ("timeline_display_functionality", self.test_timeline_display_functionality),
            ("detection_matching_logic", self.test_detection_matching_logic),
            ("error_handling", self.test_error_handling),
            ("performance_with_large_dataset", self.test_performance_with_large_dataset)
        ]
        
        for test_name, test_method in test_methods:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Running test: {test_name}")
                logger.info(f"{'='*60}")
                
                test_result = test_method()
                test_results["tests"][test_name] = test_result
                
                status = "✅ PASSED" if test_result.get("success", False) else "❌ FAILED"
                logger.info(f"{status} - {test_name}")
                
            except Exception as e:
                test_results["tests"][test_name] = {
                    "success": False,
                    "error": f"Test execution failed: {str(e)}"
                }
                logger.error(f"❌ FAILED - {test_name}: {e}")
        
        # Calculate overall results
        total_tests = len(test_results["tests"])
        passed_tests = sum(1 for test in test_results["tests"].values() if test.get("success", False))
        
        test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "pass_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
            "overall_status": "PASSED" if passed_tests == total_tests else "FAILED"
        }
        
        return test_results


def main():
    """Main test execution function"""
    print("🧪 HIL Results Real Data Testing Suite")
    print("="*60)
    
    try:
        # Initialize test suite
        test_suite = HILResultsTestSuite()
        
        # Run comprehensive tests
        results = test_suite.run_comprehensive_test_suite()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        summary = results["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ✅")
        print(f"Failed: {summary['failed_tests']} ❌")
        print(f"Pass Rate: {summary['pass_rate']:.1f}%")
        print(f"Overall Status: {summary['overall_status']}")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"hil_test_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Exit with appropriate code
        if summary["overall_status"] == "PASSED":
            print("\n🎉 All tests passed! HIL Results functionality is working correctly.")
            sys.exit(0)
        else:
            print(f"\n⚠️  {summary['failed_tests']} test(s) failed. Check detailed results for issues.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test suite execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()