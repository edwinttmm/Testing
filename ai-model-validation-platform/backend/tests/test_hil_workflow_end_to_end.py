"""
End-to-End HIL Workflow Integration Tests

Tests the complete HIL (Hardware-in-the-Loop) workflow from session start to completion,
including video timing capture, LabJack detection monitoring, ground truth matching,
and comprehensive result generation.

Test Coverage:
- Complete session lifecycle with ground truth matching
- Real-time detection processing and validation
- Session completion with accurate metrics calculation
- Integration between all HIL components
- Error handling and edge cases
"""

import pytest
import sys
import time
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the models and services
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')
from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    DetectionComparison, GroundTruthObject, Base
)
from src.services.session_completion_service import SessionCompletionService
from src.services.ground_truth_service import GroundTruthService


class TestHILWorkflowEndToEnd:
    """Test suite for complete HIL workflow integration"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def test_project(self, db_session: Session):
        """Create a comprehensive test project"""
        project = Project(
            name="HIL End-to-End Test Project",
            description="Complete HIL workflow testing with 24 ground truth objects",
            camera_model="HIL Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO",
            status="active",
            resolution="1920x1080",
            frame_rate=60
        )
        db_session.add(project)
        db_session.commit()
        return project
    
    @pytest.fixture
    def test_video_with_ground_truth(self, db_session: Session, test_project):
        """Create a test video with realistic ground truth scenario"""
        video = Video(
            filename="hil_test_scenario.mp4",
            file_path="/test/hil_test_scenario.mp4",
            file_size=50000000,  # 50MB video file
            duration=12.0,       # 12 second test scenario
            fps=60.0,
            resolution="1920x1080",
            status="validated",
            project_id=test_project.id,
            ground_truth_generated=True,
            ground_truth_count=24,  # Realistic HIL test scenario
            hil_testing_ready=True
        )
        db_session.add(video)
        db_session.commit()
        return video
    
    def create_realistic_ground_truth_scenario(self, db_session: Session, video):
        """
        Create a realistic HIL test scenario with 24 ground truth objects
        Simulates various VRU detection scenarios with different complexities
        """
        ground_truth_objects = []
        
        # Scenario: Urban intersection with various VRU types and movement patterns
        scenarios = [
            # Pedestrians crossing at different speeds
            {"timestamp": 0.5, "class": "pedestrian", "complexity": "simple"},
            {"timestamp": 1.2, "class": "pedestrian", "complexity": "moderate"},
            {"timestamp": 2.1, "class": "pedestrian", "complexity": "simple"},
            {"timestamp": 2.8, "class": "pedestrian", "complexity": "difficult"},  # Partially occluded
            {"timestamp": 3.5, "class": "pedestrian", "complexity": "simple"},
            
            # Cyclists appearing and disappearing
            {"timestamp": 1.8, "class": "cyclist", "complexity": "moderate"},
            {"timestamp": 4.2, "class": "cyclist", "complexity": "simple"},
            {"timestamp": 5.6, "class": "cyclist", "complexity": "difficult"},  # Fast moving
            {"timestamp": 6.9, "class": "cyclist", "complexity": "moderate"},
            
            # Motorcyclists with varying visibility
            {"timestamp": 3.2, "class": "motorcyclist", "complexity": "simple"},
            {"timestamp": 7.1, "class": "motorcyclist", "complexity": "moderate"},
            {"timestamp": 8.8, "class": "motorcyclist", "complexity": "difficult"},
            
            # Wheelchair users (challenging detection)
            {"timestamp": 4.8, "class": "wheelchair", "complexity": "difficult"},
            {"timestamp": 9.2, "class": "wheelchair", "complexity": "moderate"},
            
            # Scooter riders
            {"timestamp": 5.9, "class": "scooter", "complexity": "simple"},
            {"timestamp": 10.1, "class": "scooter", "complexity": "moderate"},
            
            # Animals (edge cases)\n            {"timestamp": 6.6, "class": "animal", "complexity": "difficult"},
            {"timestamp": 11.1, "class": "animal", "complexity": "simple"},
            
            # Group scenarios (multiple VRUs close together)\n            {"timestamp": 7.8, "class": "pedestrian", "complexity": "difficult"},  # In group
            {"timestamp": 7.85, "class": "pedestrian", "complexity": "difficult"}, # In same group
            {"timestamp": 9.9, "class": "cyclist", "complexity": "moderate"},
            {"timestamp": 10.7, "class": "pedestrian", "complexity": "simple"},
            
            # Late scenario VRUs
            {"timestamp": 11.3, "class": "pedestrian", "complexity": "simple"},
            {"timestamp": 11.8, "class": "cyclist", "complexity": "moderate"}
        ]
        
        for i, scenario in enumerate(scenarios):
            # Calculate realistic bounding box based on VRU type and complexity
            base_width, base_height = self._get_vru_dimensions(scenario["class"])
            complexity_factor = self._get_complexity_factor(scenario["complexity"])
            
            # Add some randomness for realistic positioning
            x_pos = 100 + (i % 8) * 200  # Spread across image width
            y_pos = 200 + (i % 3) * 100  # Different height levels
            
            gt = GroundTruthObject(
                video_id=video.id,
                tracking_id=f"vru_{scenario['class']}_{i+1}",
                frame_number=int(scenario["timestamp"] * video.fps),
                timestamp=scenario["timestamp"],
                class_label=scenario["class"],
                x=x_pos,
                y=y_pos,
                width=base_width * complexity_factor,
                height=base_height * complexity_factor,
                confidence=self._get_confidence_by_complexity(scenario["complexity"]),
                validated=True,
                difficult=(scenario["complexity"] == "difficult")
            )
            ground_truth_objects.append(gt)
            db_session.add(gt)
        
        db_session.commit()
        return ground_truth_objects
    
    def _get_vru_dimensions(self, vru_class: str) -> tuple:
        """Get typical bounding box dimensions for VRU types"""
        dimensions = {
            "pedestrian": (60, 120),
            "cyclist": (80, 100),
            "motorcyclist": (90, 110),
            "wheelchair": (70, 90),
            "scooter": (50, 90),
            "animal": (40, 60)
        }
        return dimensions.get(vru_class, (60, 100))
    
    def _get_complexity_factor(self, complexity: str) -> float:
        """Get size factor based on detection complexity"""
        factors = {
            "simple": 1.0,      # Full visibility
            "moderate": 0.8,    # Partially visible
            "difficult": 0.6    # Highly occluded or small
        }
        return factors.get(complexity, 1.0)
    
    def _get_confidence_by_complexity(self, complexity: str) -> float:
        """Get confidence score based on detection complexity"""
        confidence_scores = {
            "simple": 0.95,
            "moderate": 0.85,
            "difficult": 0.75
        }
        return confidence_scores.get(complexity, 0.90)
    
    def create_realistic_labjack_detections(self, db_session: Session, test_session, 
                                            video_start_time: datetime, scenario_type: str = "mixed_performance"):
        """
        Create realistic LabJack detection patterns based on different performance scenarios
        """
        scenarios = {
            "perfect_system": {
                "description": "Perfect detection system with minimal latency",
                "detection_rate": 1.0,  # Detects 100% of ground truth
                "latency_pattern": "low",  # 0-20ms latency
                "false_positive_rate": 0.0
            },
            "good_system": {
                "description": "Good detection system with occasional misses",
                "detection_rate": 0.92,  # Detects 92% of ground truth
                "latency_pattern": "moderate",  # 10-60ms latency
                "false_positive_rate": 0.05
            },
            "realistic_system": {
                "description": "Realistic system with typical performance",
                "detection_rate": 0.85,  # Detects 85% of ground truth
                "latency_pattern": "mixed",  # 5-100ms latency
                "false_positive_rate": 0.08
            },
            "challenging_system": {
                "description": "System under challenging conditions",
                "detection_rate": 0.75,  # Detects 75% of ground truth
                "latency_pattern": "high",  # 20-150ms latency
                "false_positive_rate": 0.12
            },
            "mixed_performance": {
                "description": "Mixed performance for comprehensive testing",
                "detection_rate": 0.83,  # Detects 83% overall
                "latency_pattern": "variable",  # Highly variable latency
                "false_positive_rate": 0.10
            }
        }
        
        scenario = scenarios.get(scenario_type, scenarios["mixed_performance"])
        
        # Get ground truth objects to base detections on
        ground_truth_objects = db_session.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == test_session.video_id
        ).order_by(GroundTruthObject.timestamp).all()
        
        detection_events = []
        detection_count = 0
        
        for gt in ground_truth_objects:
            # Determine if this ground truth will be detected
            import random
            random.seed(hash(gt.id) % 1000)  # Deterministic randomness
            
            if random.random() <= scenario["detection_rate"]:
                # Calculate latency based on pattern
                latency_ms = self._calculate_realistic_latency(gt, scenario["latency_pattern"])
                
                # Create detection event
                detection_time = video_start_time + timedelta(seconds=gt.timestamp, milliseconds=latency_ms)
                
                detection = DetectionEvent(
                    test_session_id=test_session.id,
                    video_id=None,  # LabJack doesn't know video context initially
                    timestamp=detection_time,
                    signal_type="GPIO",
                    signal_value=1,
                    gpio_pin=2,
                    validation_result=None,  # To be determined by matching
                    latency_ms=None,  # To be calculated during matching
                    event_metadata={\n                        "detection_source": "labjack",
                        "ground_truth_id": gt.id,
                        "expected_latency_ms": latency_ms,
                        "vru_class": gt.class_label,
                        "complexity": "difficult" if gt.difficult else "simple",
                        "scenario_type": scenario_type\n                    }
                )
                detection_events.append(detection)
                detection_count += 1
        
        # Add some false positives based on scenario
        if scenario["false_positive_rate"] > 0:
            fp_count = int(detection_count * scenario["false_positive_rate"])
            for i in range(fp_count):
                # Create false positive at random time
                random_time = random.uniform(0.5, 11.5)  # Within video duration
                fp_detection_time = video_start_time + timedelta(seconds=random_time)
                
                fp_detection = DetectionEvent(
                    test_session_id=test_session.id,
                    video_id=None,
                    timestamp=fp_detection_time,
                    signal_type="GPIO",
                    signal_value=1,
                    gpio_pin=2,
                    validation_result=None,
                    latency_ms=None,
                    event_metadata={
                        "detection_source": "labjack",
                        "false_positive": True,
                        "scenario_type": scenario_type
                    }
                )
                detection_events.append(fp_detection)
        
        # Add all detections to database
        for detection in detection_events:
            db_session.add(detection)
        
        db_session.commit()
        return detection_events, scenario
    
    def _calculate_realistic_latency(self, ground_truth, latency_pattern: str) -> float:
        """Calculate realistic latency based on VRU characteristics and system performance"""
        import random
        
        # Base latency patterns (in milliseconds)
        patterns = {
            "low": (0, 20),       # High-performance system
            "moderate": (10, 60),  # Good system
            "mixed": (5, 100),     # Variable performance
            "high": (20, 150),     # Challenging conditions
            "variable": (0, 200)   # Highly variable system
        }
        
        min_latency, max_latency = patterns.get(latency_pattern, (10, 80))
        
        # Adjust latency based on VRU characteristics
        complexity_factor = 1.0
        if ground_truth.difficult:
            complexity_factor = 1.5  # Difficult detections have higher latency
        
        class_factor = {
            "pedestrian": 1.0,      # Baseline
            "cyclist": 1.2,         # Faster moving, slight delay
            "motorcyclist": 1.3,    # Fast and small
            "wheelchair": 1.4,      # Lower profile, harder to detect
            "scooter": 1.1,         # Small but distinctive
            "animal": 1.6           # Unpredictable movement
        }.get(ground_truth.class_label, 1.0)
        
        # Calculate final latency
        base_latency = random.uniform(min_latency, max_latency)
        adjusted_latency = base_latency * complexity_factor * class_factor
        
        # Add some realistic jitter
        jitter = random.uniform(-5, 5)  # ±5ms jitter
        
        return max(0, adjusted_latency + jitter)
    
    @pytest.mark.asyncio
    async def test_complete_hil_workflow_realistic_scenario(self, db_session: Session, test_project, test_video_with_ground_truth):
        """
        Test complete HIL workflow with realistic 24-object scenario
        Validates the entire pipeline from session start to completion
        """
        # Step 1: Create realistic ground truth scenario
        ground_truth_objects = self.create_realistic_ground_truth_scenario(db_session, test_video_with_ground_truth)
        assert len(ground_truth_objects) == 24, "Should have exactly 24 ground truth objects"
        
        # Step 2: Create HIL test session with video timing capture
        session_start_time = datetime.utcnow()
        
        session = TestSession(
            name="Realistic HIL End-to-End Test",
            project_id=test_project.id,
            status="running",
            started_at=session_start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": session_start_time.timestamp(),
                    "video_id": test_video_with_ground_truth.id,
                    "fps": test_video_with_ground_truth.fps,
                    "duration_seconds": test_video_with_ground_truth.duration,
                    "sync_method": "hardware_trigger"
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,  # 100ms tolerance window
                    "enabled": True,
                    "matching_algorithm": "closest_temporal"
                },
                "hil_test_parameters": {
                    "expected_detection_rate": 0.85,
                    "max_acceptable_latency_ms": 150,
                    "min_acceptable_precision": 0.80
                }
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Step 3: Generate realistic LabJack detections
        detections, scenario_config = self.create_realistic_labjack_detections(
            db_session, session, session_start_time, "realistic_system"
        )
        
        print(f"Created {len(detections)} LabJack detections for {len(ground_truth_objects)} ground truth objects")
        print(f"Scenario: {scenario_config['description']}")
        
        # Step 4: Complete session and trigger ground truth matching
        completion_service = SessionCompletionService(db_session)
        
        # Measure completion processing time
        start_time = time.time()
        result = completion_service.complete_test_session(session.id)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Step 5: Validate session completion results
        assert result["success"] is True, f"Session completion failed: {result}"
        assert processing_time < 1.0, f"Session completion took {processing_time:.2f}s, expected <1s"
        
        # Step 6: Verify session status and metadata
        completed_session = db_session.query(TestSession).filter(TestSession.id == session.id).first()
        assert completed_session.status == "completed"
        assert completed_session.completed_at is not None
        assert "completion_metadata" in completed_session.configuration
        
        # Step 7: Validate test results
        test_result = db_session.query(TestResult).filter(TestResult.test_session_id == session.id).first()
        assert test_result is not None, "TestResult should be created"
        
        # Verify basic metrics
        assert test_result.total_detections > 0, "Should have recorded detections"
        assert test_result.avg_latency_ms is not None, "Should calculate average latency"
        assert 0 <= test_result.pass_rate <= 100, "Pass rate should be between 0-100%"
        
        # Step 8: Validate ground truth matching accuracy
        matched_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id,
            DetectionEvent.validation_result == "Pass"
        ).all()
        
        failed_detections = db_session.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session.id,
            DetectionEvent.validation_result == "Fail"
        ).all()
        
        # Calculate expected metrics based on scenario
        expected_detection_rate = scenario_config["detection_rate"]
        expected_detections = int(24 * expected_detection_rate)
        
        # Allow for some tolerance in detection matching
        assert len(matched_detections) >= expected_detections * 0.8, \
            f"Too few successful matches: {len(matched_detections)}, expected ≥{expected_detections * 0.8}"
        
        # Step 9: Verify latency calculations
        total_latency = 0
        latency_count = 0
        
        for detection in matched_detections:
            if detection.latency_ms is not None:
                assert detection.latency_ms >= 0, "Latency should not be negative"
                assert detection.latency_ms <= 200, "Latency should be reasonable (<200ms)"
                total_latency += detection.latency_ms
                latency_count += 1
        
        if latency_count > 0:
            avg_latency = total_latency / latency_count
            assert avg_latency < 100, f"Average latency {avg_latency:.1f}ms too high"
            
            # Verify latency matches test result
            assert abs(test_result.avg_latency_ms - avg_latency) < 1.0, \
                "TestResult latency doesn't match calculated average"
        
        # Step 10: Validate precision and recall calculations
        total_detections = len(matched_detections) + len(failed_detections)
        true_positives = len(matched_detections)
        false_negatives = 24 - len([gt for gt in ground_truth_objects 
                                   if any(d.event_metadata.get("ground_truth_id") == gt.id 
                                         for d in matched_detections)])
        
        if total_detections > 0:
            precision = true_positives / total_detections
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            
            print(f"Final Metrics:")
            print(f"  Total Detections: {total_detections}")
            print(f"  True Positives: {true_positives}")
            print(f"  False Negatives: {false_negatives}")
            print(f"  Precision: {precision:.3f}")
            print(f"  Recall: {recall:.3f}")
            print(f"  Average Latency: {avg_latency:.1f}ms")
            print(f"  Processing Time: {processing_time:.2f}s")
            
            # Validate against expected performance
            assert precision >= 0.7, f"Precision {precision:.3f} below minimum threshold"
            assert recall >= 0.6, f"Recall {recall:.3f} below minimum threshold"
        
        return {
            "session_id": session.id,
            "processing_time": processing_time,
            "total_detections": total_detections,
            "true_positives": true_positives,
            "precision": precision,
            "recall": recall,
            "avg_latency_ms": avg_latency,
            "test_result_id": test_result.id
        }
    
    @pytest.mark.parametrize("scenario_type", [
        "perfect_system",
        "good_system", 
        "realistic_system",
        "challenging_system"
    ])
    def test_hil_workflow_different_performance_scenarios(self, db_session: Session, 
                                                         test_project, test_video_with_ground_truth, scenario_type):
        """
        Test HIL workflow under different system performance scenarios
        Validates robustness across various detection system capabilities
        """
        # Create ground truth
        ground_truth_objects = self.create_realistic_ground_truth_scenario(db_session, test_video_with_ground_truth)
        
        # Create session
        session_start_time = datetime.utcnow()
        session = TestSession(
            name=f"HIL Test - {scenario_type}",
            project_id=test_project.id,
            status="running",
            started_at=session_start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": session_start_time.timestamp(),
                    "video_id": test_video_with_ground_truth.id,
                    "fps": test_video_with_ground_truth.fps,
                    "duration_seconds": test_video_with_ground_truth.duration
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,
                    "enabled": True
                },
                "test_scenario": scenario_type
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Generate scenario-specific detections
        detections, scenario_config = self.create_realistic_labjack_detections(
            db_session, session, session_start_time, scenario_type
        )
        
        # Complete session
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        
        # Validate results based on scenario expectations
        assert result["success"] is True
        
        test_result = db_session.query(TestResult).filter(TestResult.test_session_id == session.id).first()
        
        # Scenario-specific validations
        if scenario_type == "perfect_system":
            assert test_result.pass_rate >= 95, "Perfect system should have >95% pass rate"
            assert test_result.avg_latency_ms <= 30, "Perfect system should have low latency"
        
        elif scenario_type == "challenging_system":
            assert test_result.pass_rate >= 60, "Challenging system should still achieve >60% pass rate"
            # More lenient latency requirements for challenging scenarios
        
        print(f"Scenario {scenario_type}: Pass Rate = {test_result.pass_rate:.1f}%, Avg Latency = {test_result.avg_latency_ms:.1f}ms")
    
    def test_hil_workflow_error_handling(self, db_session: Session, test_project, test_video_with_ground_truth):
        """
        Test HIL workflow error handling and recovery
        """
        # Test scenario with missing video timing
        session = TestSession(
            name="Error Handling Test",
            project_id=test_project.id,
            status="running",
            started_at=datetime.utcnow(),
            configuration={}  # Missing video timing configuration
        )
        db_session.add(session)
        db_session.commit()
        
        # Should handle missing configuration gracefully
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id, force_completion=True)
        
        assert result["success"] is True
        
        completed_session = db_session.query(TestSession).filter(TestSession.id == session.id).first()
        assert completed_session.status in ["completed", "completed_with_errors"]
    
    def test_hil_workflow_performance_benchmarks(self, db_session: Session, test_project, test_video_with_ground_truth):
        """
        Test HIL workflow performance under load
        Validates system can handle large datasets efficiently
        """
        # Create large ground truth dataset (100 objects)
        large_ground_truth = []
        for i in range(100):
            gt = GroundTruthObject(
                video_id=test_video_with_ground_truth.id,
                tracking_id=f"perf_test_vru_{i}",
                frame_number=i * 5,
                timestamp=i * 0.1,  # Every 100ms
                class_label="pedestrian",
                x=100 + (i % 10) * 50,
                y=200,
                width=60,
                height=120,
                confidence=0.90,
                validated=True
            )
            large_ground_truth.append(gt)
            db_session.add(gt)
        
        db_session.commit()
        
        # Create session with large dataset
        session_start_time = datetime.utcnow()
        session = TestSession(
            name="Performance Benchmark Test",
            project_id=test_project.id,
            status="running",
            started_at=session_start_time,
            configuration={
                "video_timing": {
                    "video_start_unix_time": session_start_time.timestamp(),
                    "video_id": test_video_with_ground_truth.id,
                    "fps": test_video_with_ground_truth.fps,
                    "duration_seconds": 12.0
                },
                "ground_truth_matching": {
                    "tolerance_ms": 100,
                    "enabled": True
                },
                "performance_test": True
            }
        )
        db_session.add(session)
        db_session.commit()
        
        # Create many detections
        for i in range(500):  # 500 detections
            detection_time = session_start_time + timedelta(seconds=i * 0.02)  # Every 20ms
            detection = DetectionEvent(
                test_session_id=session.id,
                timestamp=detection_time,
                signal_type="GPIO",
                signal_value=1,
                gpio_pin=2,
                event_metadata={"performance_test": True}
            )
            db_session.add(detection)
        
        db_session.commit()
        
        # Measure completion performance
        start_time = time.time()
        completion_service = SessionCompletionService(db_session)
        result = completion_service.complete_test_session(session.id)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Performance requirements
        assert result["success"] is True
        assert processing_time < 5.0, f"Large dataset processing took {processing_time:.2f}s, expected <5s"
        
        print(f"Performance test: Processed 100 ground truth + 500 detections in {processing_time:.2f}s")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])