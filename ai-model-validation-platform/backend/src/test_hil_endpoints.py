#!/usr/bin/env python3
"""
Test script for HIL Results API endpoints

Tests the new HIL test results endpoints to ensure they work correctly
and provide the expected data structure for the frontend.
"""

import requests
import json
import sys
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"

def test_endpoint(url: str, description: str) -> Dict[str, Any]:
    """Test a single endpoint and return response data"""
    try:
        logger.info(f"Testing {description}: {url}")
        response = requests.get(url, timeout=30)
        
        logger.info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ SUCCESS: {description}")
            return {"success": True, "data": data, "status": response.status_code}
        else:
            logger.error(f"❌ FAILED: {description} - Status: {response.status_code}")
            try:
                error_data = response.json()
                logger.error(f"Error details: {error_data}")
                return {"success": False, "error": error_data, "status": response.status_code}
            except:
                logger.error(f"Error text: {response.text}")
                return {"success": False, "error": response.text, "status": response.status_code}
                
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ NETWORK ERROR: {description} - {e}")
        return {"success": False, "error": str(e), "status": 0}

def validate_hil_results_structure(data: Dict[str, Any]) -> bool:
    """Validate the HIL results data structure matches frontend expectations"""
    required_fields = [
        "session_id", "test_session_id", "validation_type",
        "total_detections", "passed_detections", "failed_detections",
        "pass_rate", "status", "session_info", "latency_stats",
        "latency_distribution", "hardware_status", "detection_events"
    ]
    
    logger.info("Validating HIL results data structure...")
    
    for field in required_fields:
        if field not in data:
            logger.error(f"❌ Missing required field: {field}")
            return False
        logger.info(f"✅ Found field: {field}")
    
    # Validate session_info structure
    session_info_fields = ["project_name", "operator", "start_time", "end_time", "duration_seconds"]
    for field in session_info_fields:
        if field not in data["session_info"]:
            logger.error(f"❌ Missing session_info field: {field}")
            return False
    
    # Validate latency_stats structure
    latency_stats_fields = ["average_ms", "min_ms", "max_ms", "median_ms", "std_dev_ms", "threshold_ms"]
    for field in latency_stats_fields:
        if field not in data["latency_stats"]:
            logger.error(f"❌ Missing latency_stats field: {field}")
            return False
    
    # Validate hardware_status structure
    hardware_status_fields = ["labjack_connected", "model", "serial_number", "firmware_version", "sampling_rate_hz", "active_channels"]
    for field in hardware_status_fields:
        if field not in data["hardware_status"]:
            logger.error(f"❌ Missing hardware_status field: {field}")
            return False
    
    # Validate detection_events structure (if any events exist)
    if data["detection_events"] and len(data["detection_events"]) > 0:
        event_fields = ["event_id", "frame_number", "timestamp", "detection_time", "latency_ms", "latency_ns", "voltage_level", "channel", "result"]
        for field in event_fields:
            if field not in data["detection_events"][0]:
                logger.error(f"❌ Missing detection_event field: {field}")
                return False
    
    logger.info("✅ All required fields validated successfully!")
    return True

def main():
    """Main test function"""
    logger.info("Starting HIL Test Results API endpoint testing...")
    
    results = []
    
    # Test 1: List test sessions
    logger.info("\n" + "="*50)
    logger.info("TEST 1: List Test Sessions")
    logger.info("="*50)
    
    result = test_endpoint(f"{BASE_URL}/test-sessions", "List test sessions")
    results.append(("List Sessions", result))
    
    test_session_id = None
    
    if result["success"] and "sessions" in result["data"]:
        sessions = result["data"]["sessions"]
        logger.info(f"Found {len(sessions)} test sessions")
        
        if sessions:
            test_session_id = sessions[0]["session_id"]
            logger.info(f"Using test session ID: {test_session_id}")
        else:
            logger.warning("No test sessions found. Creating a mock session ID for testing.")
            test_session_id = "00000000-0000-0000-0000-000000000000"
    
    # Test 2: Get HIL test results (main endpoint)
    if test_session_id:
        logger.info("\n" + "="*50)
        logger.info("TEST 2: Get HIL Test Results")
        logger.info("="*50)
        
        result = test_endpoint(f"{BASE_URL}/test-sessions/{test_session_id}/results", "HIL test results")
        results.append(("HIL Results", result))
        
        if result["success"]:
            # Validate the data structure
            if validate_hil_results_structure(result["data"]):
                logger.info("✅ HIL results data structure validation passed!")
            else:
                logger.error("❌ HIL results data structure validation failed!")
        
        # Test 3: Alternative HIL results endpoint
        logger.info("\n" + "="*50)
        logger.info("TEST 3: Alternative HIL Results Endpoint")
        logger.info("="*50)
        
        result = test_endpoint(f"{BASE_URL}/test-sessions/{test_session_id}/hil-results", "Alternative HIL results")
        results.append(("Alternative HIL Results", result))
        
        # Test 4: Session summary
        logger.info("\n" + "="*50)
        logger.info("TEST 4: Session Summary")
        logger.info("="*50)
        
        result = test_endpoint(f"{BASE_URL}/test-sessions/{test_session_id}/summary", "Session summary")
        results.append(("Session Summary", result))
        
        # Test 5: Session events
        logger.info("\n" + "="*50)
        logger.info("TEST 5: Session Detection Events")
        logger.info("="*50)
        
        result = test_endpoint(f"{BASE_URL}/test-sessions/{test_session_id}/events", "Detection events")
        results.append(("Detection Events", result))
    
    # Print summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if result["success"])
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
        
        if not result["success"]:
            logger.info(f"    Error: {result.get('error', 'Unknown error')}")
    
    logger.info(f"\nResults: {passed_tests}/{total_tests} tests passed")
    
    if failed_tests > 0:
        logger.error(f"❌ {failed_tests} tests failed!")
        sys.exit(1)
    else:
        logger.info("✅ All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()