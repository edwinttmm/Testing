"""
Real-time Validation Pass/Fail Scenario Tests
Testing real-time validation scenarios with WebSocket connections and live data processing
"""
import pytest
import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
import websockets
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import test configuration
import sys
sys.path.append('/home/user/Testing/tests/comprehensive-testing-framework/config')
from test_config import test_config

# Import application
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
from main import app
from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent
from socketio_server import sio


class TestRealTimeValidationScenarios:
    """Test suite for real-time validation pass/fail scenarios"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, test_db_session: Session):
        """Set up test environment for real-time testing"""
        self.db = test_db_session
        self.client = TestClient(app)
        
        # Create test project
        self.test_project = Project(
            name="Real-time Validation Test Project",
            description="Testing real-time validation scenarios",
            camera_model="RealTime TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        self.db.add(self.test_project)
        self.db.commit()
        
        # Create test video
        self.test_video = Video(
            filename="realtime_test_video.mp4",
            file_path="/test/path/realtime_test_video.mp4",
            file_size=31457280,  # 30MB
            duration=90.0,
            fps=30.0,
            resolution="1920x1080",
            project_id=self.test_project.id
        )
        self.db.add(self.test_video)
        self.db.commit()
        
        # Create test session
        self.test_session = TestSession(
            name="Real-time Validation Session",
            project_id=self.test_project.id,
            video_id=self.test_video.id,
            tolerance_ms=100
        )
        self.db.add(self.test_session)
        self.db.commit()
        
        # Real-time validation criteria
        self.validation_criteria = {
            "timing_tolerance_ms": 100,
            "min_confidence": 0.7,
            "max_false_positive_rate": 0.1,
            "min_true_positive_rate": 0.85,
            "max_response_time_ms": 500
        }
    
    @pytest.mark.asyncio
    async def test_pass_scenario_all_criteria_met(self):
        """Test scenario where all validation criteria are met (PASS)"""
        # Define test scenario with perfect detections
        test_scenario = {
            "name": "Perfect Detection Scenario",
            "ground_truth_events": [
                {"timestamp": 1.0, "type": "person", "bbox": {"x": 100, "y": 200, "width": 80, "height": 180}},
                {"timestamp": 3.5, "type": "vehicle", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
                {"timestamp": 6.2, "type": "bicycle", "bbox": {"x": 500, "y": 250, "width": 60, "height": 120}},
                {"timestamp": 8.8, "type": "person", "bbox": {"x": 150, "y": 180, "width": 85, "height": 185}}
            ],
            "ai_detections": [
                {"timestamp": 1.02, "type": "person", "confidence": 0.95, "bbox": {"x": 102, "y": 202, "width": 78, "height": 178}},
                {"timestamp": 3.48, "type": "vehicle", "confidence": 0.92, "bbox": {"x": 298, "y": 152, "width": 202, "height": 98}},
                {"timestamp": 6.18, "type": "bicycle", "confidence": 0.88, "bbox": {"x": 498, "y": 252, "width": 62, "height": 118}},
                {"timestamp": 8.82, "type": "person", "confidence": 0.91, "bbox": {"x": 148, "y": 182, "width": 87, "height": 183}}
            ]
        }
        
        # Start real-time validation session
        validation_session = await self._start_realtime_validation_session()
        
        # Process detections in real-time
        validation_results = await self._process_realtime_detections(
            validation_session,
            test_scenario["ground_truth_events"],
            test_scenario["ai_detections"]
        )
        
        # Validate PASS criteria
        assert validation_results["overall_result"] == "PASS"
        assert validation_results["timing_accuracy"] >= 0.95  # All within 100ms tolerance
        assert validation_results["detection_accuracy"] >= 0.9  # High accuracy
        assert validation_results["false_positive_rate"] <= 0.05  # Low false positives
        assert validation_results["true_positive_rate"] >= 0.95  # High true positives
        assert validation_results["average_response_time"] <= 200  # Fast response
        
        # Verify individual detection results
        for detection_result in validation_results["detection_results"]:
            assert detection_result["timing_valid"] is True
            assert detection_result["confidence"] >= self.validation_criteria["min_confidence"]
            assert detection_result["bbox_iou"] >= 0.8  # Good bounding box overlap
    
    @pytest.mark.asyncio
    async def test_fail_scenario_timing_violations(self):
        """Test scenario that fails due to timing violations (FAIL)"""
        test_scenario = {
            "name": "Timing Violation Scenario",
            "ground_truth_events": [
                {"timestamp": 1.0, "type": "person", "bbox": {"x": 100, "y": 200, "width": 80, "height": 180}},
                {"timestamp": 3.5, "type": "vehicle", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
                {"timestamp": 6.2, "type": "bicycle", "bbox": {"x": 500, "y": 250, "width": 60, "height": 120}}
            ],
            "ai_detections": [
                {"timestamp": 1.25, "type": "person", "confidence": 0.85, "bbox": {"x": 105, "y": 205, "width": 75, "height": 175}},  # 250ms late
                {"timestamp": 3.35, "type": "vehicle", "confidence": 0.90, "bbox": {"x": 295, "y": 155, "width": 205, "height": 95}},  # 150ms early
                {"timestamp": 6.45, "type": "bicycle", "confidence": 0.75, "bbox": {"x": 495, "y": 255, "width": 65, "height": 115}}  # 250ms late
            ]
        }
        
        # Start validation session
        validation_session = await self._start_realtime_validation_session()
        
        # Process detections
        validation_results = await self._process_realtime_detections(
            validation_session,
            test_scenario["ground_truth_events"],
            test_scenario["ai_detections"]
        )
        
        # Validate FAIL criteria due to timing
        assert validation_results["overall_result"] == "FAIL"
        assert validation_results["failure_reasons"]["timing_violations"] >= 2
        assert validation_results["timing_accuracy"] < 0.7  # Poor timing accuracy
        
        # Check specific timing violations
        timing_violations = validation_results["timing_violations"]
        assert len(timing_violations) >= 2
        
        for violation in timing_violations:
            assert violation["timing_error_ms"] > self.validation_criteria["timing_tolerance_ms"]
    
    @pytest.mark.asyncio
    async def test_fail_scenario_accuracy_violations(self):
        """Test scenario that fails due to accuracy violations (FAIL)"""
        test_scenario = {
            "name": "Accuracy Violation Scenario",
            "ground_truth_events": [
                {"timestamp": 1.0, "type": "person", "bbox": {"x": 100, "y": 200, "width": 80, "height": 180}},
                {"timestamp": 3.5, "type": "vehicle", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
                {"timestamp": 6.2, "type": "bicycle", "bbox": {"x": 500, "y": 250, "width": 60, "height": 120}},
                {"timestamp": 8.8, "type": "person", "bbox": {"x": 150, "y": 180, "width": 85, "height": 185}}
            ],
            "ai_detections": [
                {"timestamp": 1.02, "type": "vehicle", "confidence": 0.65, "bbox": {"x": 102, "y": 202, "width": 78, "height": 178}},  # Wrong class, low confidence
                {"timestamp": 3.48, "type": "vehicle", "confidence": 0.92, "bbox": {"x": 298, "y": 152, "width": 202, "height": 98}},  # Correct
                {"timestamp": 6.18, "type": "person", "confidence": 0.55, "bbox": {"x": 498, "y": 252, "width": 62, "height": 118}},  # Wrong class, low confidence
                {"timestamp": 9.5, "type": "bicycle", "confidence": 0.70, "bbox": {"x": 400, "y": 300, "width": 50, "height": 100}},  # False positive
                # Missing detection for person at 8.8s (false negative)
            ]
        }
        
        # Start validation session
        validation_session = await self._start_realtime_validation_session()
        
        # Process detections
        validation_results = await self._process_realtime_detections(
            validation_session,
            test_scenario["ground_truth_events"],
            test_scenario["ai_detections"]
        )
        
        # Validate FAIL criteria due to accuracy
        assert validation_results["overall_result"] == "FAIL"
        assert validation_results["detection_accuracy"] < 0.6  # Poor accuracy
        assert validation_results["false_positive_rate"] > 0.2  # High false positives
        assert validation_results["true_positive_rate"] < 0.5  # Low true positives
        
        # Check specific accuracy violations
        accuracy_violations = validation_results["accuracy_violations"]
        assert len(accuracy_violations) >= 2
        
        classification_errors = [v for v in accuracy_violations if v["type"] == "classification_error"]
        assert len(classification_errors) >= 2
    
    @pytest.mark.asyncio
    async def test_fail_scenario_confidence_violations(self):
        """Test scenario that fails due to low confidence detections (FAIL)"""
        test_scenario = {
            "name": "Low Confidence Scenario",
            "ground_truth_events": [
                {"timestamp": 1.0, "type": "person", "bbox": {"x": 100, "y": 200, "width": 80, "height": 180}},
                {"timestamp": 3.5, "type": "vehicle", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
                {"timestamp": 6.2, "type": "bicycle", "bbox": {"x": 500, "y": 250, "width": 60, "height": 120}}
            ],
            "ai_detections": [
                {"timestamp": 1.02, "type": "person", "confidence": 0.45, "bbox": {"x": 102, "y": 202, "width": 78, "height": 178}},  # Low confidence
                {"timestamp": 3.48, "type": "vehicle", "confidence": 0.52, "bbox": {"x": 298, "y": 152, "width": 202, "height": 98}},  # Low confidence
                {"timestamp": 6.18, "type": "bicycle", "confidence": 0.38, "bbox": {"x": 498, "y": 252, "width": 62, "height": 118}}  # Low confidence
            ]
        }
        
        # Start validation session
        validation_session = await self._start_realtime_validation_session()
        
        # Process detections
        validation_results = await self._process_realtime_detections(
            validation_session,
            test_scenario["ground_truth_events"],
            test_scenario["ai_detections"]
        )
        
        # Validate FAIL criteria due to low confidence
        assert validation_results["overall_result"] == "FAIL"
        assert validation_results["failure_reasons"]["confidence_violations"] == 3
        assert validation_results["average_confidence"] < self.validation_criteria["min_confidence"]
        
        # All detections should be flagged as low confidence
        for detection_result in validation_results["detection_results"]:
            assert detection_result["confidence"] < self.validation_criteria["min_confidence"]
            assert detection_result["confidence_valid"] is False
    
    @pytest.mark.asyncio
    async def test_mixed_scenario_partial_pass(self):
        """Test mixed scenario with some passes and some failures"""
        test_scenario = {
            "name": "Mixed Results Scenario",
            "ground_truth_events": [
                {"timestamp": 1.0, "type": "person", "bbox": {"x": 100, "y": 200, "width": 80, "height": 180}},
                {"timestamp": 3.5, "type": "vehicle", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
                {"timestamp": 6.2, "type": "bicycle", "bbox": {"x": 500, "y": 250, "width": 60, "height": 120}},
                {"timestamp": 8.8, "type": "person", "bbox": {"x": 150, "y": 180, "width": 85, "height": 185}}
            ],
            "ai_detections": [
                {"timestamp": 1.02, "type": "person", "confidence": 0.95, "bbox": {"x": 102, "y": 202, "width": 78, "height": 178}},  # PASS
                {"timestamp": 3.75, "type": "vehicle", "confidence": 0.88, "bbox": {"x": 298, "y": 152, "width": 202, "height": 98}},  # FAIL (timing)
                {"timestamp": 6.18, "type": "person", "confidence": 0.82, "bbox": {"x": 498, "y": 252, "width": 62, "height": 118}},  # FAIL (wrong class)
                {"timestamp": 8.82, "type": "person", "confidence": 0.91, "bbox": {"x": 148, "y": 182, "width": 87, "height": 183}}  # PASS
            ]
        }
        
        # Start validation session
        validation_session = await self._start_realtime_validation_session()
        
        # Process detections
        validation_results = await self._process_realtime_detections(
            validation_session,
            test_scenario["ground_truth_events"],
            test_scenario["ai_detections"]
        )
        
        # Validate mixed results
        assert validation_results["overall_result"] == "FAIL"  # Overall fails due to violations
        assert validation_results["pass_count"] == 2
        assert validation_results["fail_count"] == 2
        assert validation_results["pass_rate"] == 0.5
        
        # Check individual results
        individual_results = validation_results["detection_results"]
        pass_results = [r for r in individual_results if r["result"] == "PASS"]
        fail_results = [r for r in individual_results if r["result"] == "FAIL"]
        
        assert len(pass_results) == 2
        assert len(fail_results) == 2
    
    @pytest.mark.asyncio
    async def test_real_time_performance_validation(self):
        """Test real-time performance under load"""
        # Generate large number of concurrent detections
        concurrent_detections = []
        for i in range(100):
            detection = {
                "timestamp": i * 0.1,  # 100ms intervals
                "type": "person" if i % 3 == 0 else "vehicle" if i % 3 == 1 else "bicycle",
                "confidence": 0.8 + (i % 20) * 0.01,
                "bbox": {"x": 100 + i, "y": 200, "width": 80, "height": 180}
            }
            concurrent_detections.append(detection)
        
        # Start validation session
        validation_session = await self._start_realtime_validation_session()
        
        # Process all detections concurrently
        start_time = time.time()
        
        tasks = []
        for detection in concurrent_detections:
            task = self._process_single_detection(validation_session, detection)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        processing_time = time.time() - start_time
        
        # Validate performance
        assert processing_time < 5.0, f"Processing too slow: {processing_time}s for 100 detections"
        assert len(results) == 100
        
        # Check that all detections were processed
        successful_results = [r for r in results if r["processed"]]
        assert len(successful_results) >= 95  # At least 95% success rate
        
        # Check response times
        response_times = [r["response_time_ms"] for r in successful_results]
        average_response_time = sum(response_times) / len(response_times)
        
        assert average_response_time <= self.validation_criteria["max_response_time_ms"]
    
    @pytest.mark.asyncio
    async def test_websocket_real_time_updates(self):
        """Test real-time updates via WebSocket connections"""
        # Mock WebSocket connection
        websocket_messages = []
        
        async def mock_websocket_handler(websocket, path):
            async for message in websocket:
                data = json.loads(message)
                websocket_messages.append(data)
                
                # Send acknowledgment
                await websocket.send(json.dumps({
                    "type": "ack",
                    "message_id": data.get("id"),
                    "timestamp": time.time()
                }))
        
        # Start validation session with WebSocket monitoring
        validation_session = await self._start_realtime_validation_session(
            websocket_enabled=True
        )
        
        # Send test detections
        test_detections = [
            {"timestamp": 1.0, "type": "person", "confidence": 0.95},
            {"timestamp": 2.5, "type": "vehicle", "confidence": 0.88},
            {"timestamp": 4.2, "type": "bicycle", "confidence": 0.76}
        ]
        
        for detection in test_detections:
            await self._send_realtime_detection(validation_session, detection)
            await asyncio.sleep(0.1)  # Small delay between detections
        
        # Wait for WebSocket messages
        await asyncio.sleep(1.0)
        
        # Validate WebSocket updates
        assert len(websocket_messages) >= len(test_detections)
        
        # Check message format
        for message in websocket_messages:
            assert "type" in message
            assert "data" in message
            assert "timestamp" in message
            
            if message["type"] == "detection_result":
                assert "detection_id" in message["data"]
                assert "validation_result" in message["data"]
                assert "confidence" in message["data"]
    
    @pytest.mark.asyncio
    async def test_edge_case_scenarios(self):
        """Test edge cases in real-time validation"""
        edge_cases = [
            # Case 1: No detections (all false negatives)
            {
                "name": "No Detections",
                "ground_truth": [{"timestamp": 1.0, "type": "person"}],
                "detections": [],
                "expected_result": "FAIL"
            },
            
            # Case 2: All false positives
            {
                "name": "All False Positives",
                "ground_truth": [],
                "detections": [
                    {"timestamp": 1.0, "type": "person", "confidence": 0.8},
                    {"timestamp": 2.0, "type": "vehicle", "confidence": 0.9}
                ],
                "expected_result": "FAIL"
            },
            
            # Case 3: Duplicate detections
            {
                "name": "Duplicate Detections",
                "ground_truth": [{"timestamp": 1.0, "type": "person"}],
                "detections": [
                    {"timestamp": 1.02, "type": "person", "confidence": 0.95},
                    {"timestamp": 1.03, "type": "person", "confidence": 0.93},  # Duplicate
                    {"timestamp": 1.04, "type": "person", "confidence": 0.91}   # Duplicate
                ],
                "expected_result": "FAIL"  # Should fail due to duplicates
            },
            
            # Case 4: Out-of-order detections
            {
                "name": "Out-of-order Detections",
                "ground_truth": [
                    {"timestamp": 1.0, "type": "person"},
                    {"timestamp": 2.0, "type": "vehicle"},
                    {"timestamp": 3.0, "type": "bicycle"}
                ],
                "detections": [
                    {"timestamp": 2.02, "type": "vehicle", "confidence": 0.88},  # Arrives first
                    {"timestamp": 1.02, "type": "person", "confidence": 0.95},   # Arrives second (out of order)
                    {"timestamp": 3.02, "type": "bicycle", "confidence": 0.82}   # Arrives third
                ],
                "expected_result": "PASS"  # Should handle out-of-order gracefully
            }
        ]
        
        for case in edge_cases:
            validation_session = await self._start_realtime_validation_session()
            
            # Add ground truth if any
            for gt_event in case["ground_truth"]:
                await self._add_ground_truth_event(validation_session, gt_event)
            
            # Process detections
            validation_results = await self._process_realtime_detections(
                validation_session,
                case["ground_truth"],
                case["detections"]
            )
            
            assert validation_results["overall_result"] == case["expected_result"], \
                f"Edge case '{case['name']}' failed: expected {case['expected_result']}, got {validation_results['overall_result']}"
    
    # Helper methods for real-time validation testing
    
    async def _start_realtime_validation_session(self, websocket_enabled=False):
        """Start a real-time validation session"""
        session_config = {
            "session_id": self.test_session.id,
            "validation_criteria": self.validation_criteria,
            "websocket_enabled": websocket_enabled,
            "real_time_mode": True
        }
        
        # Mock session initialization
        return {
            "session_id": session_config["session_id"],
            "criteria": session_config["validation_criteria"],
            "start_time": time.time(),
            "detections": [],
            "ground_truth": [],
            "websocket_enabled": websocket_enabled
        }
    
    async def _process_realtime_detections(self, session, ground_truth_events, ai_detections):
        """Process detections in real-time and return validation results"""
        # Add ground truth events
        for gt_event in ground_truth_events:
            await self._add_ground_truth_event(session, gt_event)
        
        # Process AI detections
        detection_results = []
        for detection in ai_detections:
            result = await self._process_single_detection(session, detection)
            detection_results.append(result)
            
            # Simulate real-time delay
            await asyncio.sleep(0.01)
        
        # Calculate overall validation results
        return self._calculate_validation_results(session, detection_results)
    
    async def _add_ground_truth_event(self, session, gt_event):
        """Add ground truth event to session"""
        session["ground_truth"].append({
            "timestamp": gt_event["timestamp"],
            "type": gt_event["type"],
            "bbox": gt_event.get("bbox", {}),
            "added_at": time.time()
        })
    
    async def _process_single_detection(self, session, detection):
        """Process a single detection and return validation result"""
        start_time = time.time()
        
        # Find matching ground truth
        matching_gt = self._find_matching_ground_truth(session, detection)
        
        # Validate timing
        timing_valid = True
        timing_error = 0
        
        if matching_gt:
            timing_error = abs(detection["timestamp"] - matching_gt["timestamp"]) * 1000  # Convert to ms
            timing_valid = timing_error <= self.validation_criteria["timing_tolerance_ms"]
        
        # Validate confidence
        confidence_valid = detection["confidence"] >= self.validation_criteria["min_confidence"]
        
        # Validate classification
        classification_valid = matching_gt and detection["type"] == matching_gt["type"]
        
        # Calculate bounding box IoU if applicable
        bbox_iou = 0.0
        if matching_gt and "bbox" in detection and "bbox" in matching_gt:
            bbox_iou = self._calculate_iou(detection["bbox"], matching_gt["bbox"])
        
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Determine overall result
        overall_valid = (timing_valid and confidence_valid and classification_valid and 
                        (bbox_iou >= 0.5 if bbox_iou > 0 else True))
        
        result = {
            "detection": detection,
            "matching_ground_truth": matching_gt,
            "timing_valid": timing_valid,
            "timing_error_ms": timing_error,
            "confidence_valid": confidence_valid,
            "classification_valid": classification_valid,
            "bbox_iou": bbox_iou,
            "response_time_ms": processing_time,
            "result": "PASS" if overall_valid else "FAIL",
            "processed": True
        }
        
        session["detections"].append(result)
        return result
    
    def _find_matching_ground_truth(self, session, detection):
        """Find matching ground truth event for a detection"""
        tolerance_s = self.validation_criteria["timing_tolerance_ms"] / 1000.0
        
        for gt_event in session["ground_truth"]:
            time_diff = abs(detection["timestamp"] - gt_event["timestamp"])
            if time_diff <= tolerance_s and detection["type"] == gt_event["type"]:
                return gt_event
        
        return None
    
    def _calculate_iou(self, bbox1, bbox2):
        """Calculate Intersection over Union for two bounding boxes"""
        # Implementation similar to previous tests
        x1_1, y1_1 = bbox1["x"], bbox1["y"]
        x2_1, y2_1 = x1_1 + bbox1["width"], y1_1 + bbox1["height"]
        
        x1_2, y1_2 = bbox2["x"], bbox2["y"]
        x2_2, y2_2 = x1_2 + bbox2["width"], y1_2 + bbox2["height"]
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union
        area1 = bbox1["width"] * bbox1["height"]
        area2 = bbox2["width"] * bbox2["height"]
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_validation_results(self, session, detection_results):
        """Calculate overall validation results"""
        total_detections = len(detection_results)
        total_ground_truth = len(session["ground_truth"])
        
        if total_detections == 0:
            return {
                "overall_result": "FAIL",
                "reason": "No detections processed"
            }
        
        # Count passes and failures
        pass_count = sum(1 for r in detection_results if r["result"] == "PASS")
        fail_count = total_detections - pass_count
        
        # Calculate metrics
        pass_rate = pass_count / total_detections
        timing_violations = sum(1 for r in detection_results if not r["timing_valid"])
        confidence_violations = sum(1 for r in detection_results if not r["confidence_valid"])
        classification_errors = sum(1 for r in detection_results if not r["classification_valid"])
        
        # Calculate accuracy metrics
        true_positives = sum(1 for r in detection_results if r["matching_ground_truth"] and r["result"] == "PASS")
        false_positives = sum(1 for r in detection_results if not r["matching_ground_truth"])
        false_negatives = max(0, total_ground_truth - true_positives)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        
        false_positive_rate = false_positives / total_detections if total_detections > 0 else 0
        true_positive_rate = recall
        
        # Calculate timing and confidence metrics
        timing_errors = [r["timing_error_ms"] for r in detection_results if r["timing_error_ms"] > 0]
        average_timing_error = sum(timing_errors) / len(timing_errors) if timing_errors else 0
        timing_accuracy = 1 - (average_timing_error / self.validation_criteria["timing_tolerance_ms"])
        timing_accuracy = max(0, min(1, timing_accuracy))
        
        confidences = [r["detection"]["confidence"] for r in detection_results]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        response_times = [r["response_time_ms"] for r in detection_results]
        average_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Determine overall result
        overall_pass = (
            pass_rate >= 0.8 and
            false_positive_rate <= self.validation_criteria["max_false_positive_rate"] and
            true_positive_rate >= self.validation_criteria["min_true_positive_rate"] and
            average_response_time <= self.validation_criteria["max_response_time_ms"] and
            timing_violations == 0 and
            confidence_violations == 0
        )
        
        return {
            "overall_result": "PASS" if overall_pass else "FAIL",
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": pass_rate,
            "detection_accuracy": precision,
            "timing_accuracy": timing_accuracy,
            "false_positive_rate": false_positive_rate,
            "true_positive_rate": true_positive_rate,
            "average_confidence": average_confidence,
            "average_response_time": average_response_time,
            "detection_results": detection_results,
            "failure_reasons": {
                "timing_violations": timing_violations,
                "confidence_violations": confidence_violations,
                "classification_errors": classification_errors
            },
            "timing_violations": [r for r in detection_results if not r["timing_valid"]],
            "accuracy_violations": [r for r in detection_results if not r["classification_valid"]]
        }
    
    async def _send_realtime_detection(self, session, detection):
        """Send detection via WebSocket if enabled"""
        if session.get("websocket_enabled"):
            message = {
                "type": "detection",
                "data": detection,
                "session_id": session["session_id"],
                "timestamp": time.time()
            }
            
            # In a real implementation, this would send via actual WebSocket
            # For testing, we'll just simulate the send
            await asyncio.sleep(0.001)  # Simulate network delay


@pytest.fixture
def test_db_session():
    """Fixture providing test database session"""
    session = SessionLocal()
    yield session
    session.close()


# Test utilities for real-time scenarios
class RealTimeTestHarness:
    """Test harness for real-time validation scenarios"""
    
    def __init__(self, validation_criteria: Dict[str, Any]):
        self.criteria = validation_criteria
        self.sessions = {}
    
    async def create_scenario(self, name: str, ground_truth: List[Dict], detections: List[Dict]):
        """Create a test scenario with ground truth and AI detections"""
        return {
            "name": name,
            "ground_truth": ground_truth,
            "detections": detections,
            "created_at": time.time()
        }
    
    async def run_scenario(self, scenario: Dict) -> Dict[str, Any]:
        """Run a validation scenario and return results"""
        # Implementation would run the actual scenario
        pass
    
    def generate_realistic_detections(self, count: int, scenario_type: str = "normal"):
        """Generate realistic detection data for testing"""
        detections = []
        
        for i in range(count):
            if scenario_type == "normal":
                confidence = 0.7 + (i % 30) * 0.01  # Vary confidence
                timing_jitter = (i % 10) * 10  # Small timing variations
            elif scenario_type == "challenging":
                confidence = 0.5 + (i % 50) * 0.01  # Lower confidence
                timing_jitter = (i % 20) * 20  # Larger timing variations
            elif scenario_type == "perfect":
                confidence = 0.9 + (i % 10) * 0.01  # High confidence
                timing_jitter = (i % 5) * 5  # Minimal timing variations
            
            detection = {
                "timestamp": i * 1.0 + timing_jitter / 1000.0,
                "type": ["person", "vehicle", "bicycle"][i % 3],
                "confidence": min(0.99, confidence),
                "bbox": {
                    "x": 100 + i * 10,
                    "y": 200,
                    "width": 80,
                    "height": 180
                }
            }
            detections.append(detection)
        
        return detections