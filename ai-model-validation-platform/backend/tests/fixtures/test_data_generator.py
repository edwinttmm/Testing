#!/usr/bin/env python3
"""
VRU Test Data Generator
======================

Generates comprehensive test data for VRU platform testing including:
- Synthetic video files with VRU objects
- Ground truth annotations
- Test scenarios and edge cases
- Mock API responses
- Performance test datasets

Author: Test Data Generation Agent  
Date: 2025-08-27
"""

import cv2
import numpy as np
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import random
import logging

logger = logging.getLogger(__name__)

@dataclass
class VRUObject:
    """Represents a VRU (Vehicle-Road-User) object"""
    object_type: str  # pedestrian, cyclist, vehicle, motorcycle
    x: int
    y: int 
    width: int
    height: int
    confidence: float
    timestamp: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    track_id: Optional[int] = None

@dataclass
class TestScenario:
    """Test scenario configuration"""
    name: str
    duration_sec: int
    resolution: Tuple[int, int]
    fps: int
    objects: List[VRUObject]
    environmental_conditions: Dict[str, Any]
    complexity_level: str  # simple, medium, complex, extreme

class VRUTestDataGenerator:
    """Generates comprehensive test data for VRU platform"""
    
    def __init__(self):
        self.object_templates = self._load_object_templates()
        self.environmental_templates = self._load_environmental_templates()
        
    def _load_object_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load VRU object templates with realistic properties"""
        return {
            "pedestrian": {
                "typical_size": (40, 80),
                "size_variation": 0.3,
                "typical_speed": 1.4,  # m/s
                "color_range": [(50, 50, 50), (200, 200, 200)],
                "detection_difficulty": 0.7
            },
            "cyclist": {
                "typical_size": (60, 120),
                "size_variation": 0.25,
                "typical_speed": 4.2,  # m/s
                "color_range": [(100, 100, 100), (255, 255, 255)],
                "detection_difficulty": 0.8
            },
            "vehicle": {
                "typical_size": (120, 80),
                "size_variation": 0.4,
                "typical_speed": 8.3,  # m/s
                "color_range": [(0, 0, 0), (255, 255, 255)],
                "detection_difficulty": 0.9
            },
            "motorcycle": {
                "typical_size": (80, 100),
                "size_variation": 0.2,
                "typical_speed": 6.9,  # m/s
                "color_range": [(50, 50, 50), (255, 100, 100)],
                "detection_difficulty": 0.6
            }
        }
    
    def _load_environmental_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load environmental condition templates"""
        return {
            "sunny_day": {
                "lighting": 0.9,
                "contrast": 1.0,
                "noise_level": 0.1,
                "weather_effects": None
            },
            "overcast": {
                "lighting": 0.6,
                "contrast": 0.8,
                "noise_level": 0.15,
                "weather_effects": "low_visibility"
            },
            "rainy": {
                "lighting": 0.4,
                "contrast": 0.6,
                "noise_level": 0.3,
                "weather_effects": "rain_drops"
            },
            "night": {
                "lighting": 0.2,
                "contrast": 0.9,
                "noise_level": 0.25,
                "weather_effects": "artificial_lighting"
            },
            "snow": {
                "lighting": 0.8,
                "contrast": 0.5,
                "noise_level": 0.4,
                "weather_effects": "snow_particles"
            }
        }
    
    def generate_test_video_with_objects(
        self, 
        scenario: TestScenario,
        output_path: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Generate test video with VRU objects and return ground truth"""
        
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
            output_path = temp_file.name
            temp_file.close()
        
        # Video writer setup
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, scenario.fps, scenario.resolution)
        
        ground_truth_data = []
        total_frames = scenario.duration_sec * scenario.fps
        
        logger.info(f"Generating video: {scenario.name} ({total_frames} frames)")
        
        for frame_num in range(total_frames):
            current_time = frame_num / scenario.fps
            
            # Create base frame with environmental conditions
            frame = self._create_base_frame(scenario.resolution, scenario.environmental_conditions)
            
            # Add VRU objects to frame
            frame_objects = []
            for obj in scenario.objects:
                # Update object position based on velocity
                updated_obj = self._update_object_position(obj, current_time)
                
                # Check if object is visible in current frame
                if self._is_object_visible(updated_obj, current_time, scenario.duration_sec):
                    # Draw object on frame
                    frame = self._draw_vru_object(frame, updated_obj, scenario.environmental_conditions)
                    
                    # Add to ground truth
                    ground_truth_entry = {
                        "timestamp": current_time,
                        "frame_number": frame_num,
                        "object_class": updated_obj.object_type,
                        "bbox": {
                            "x": updated_obj.x,
                            "y": updated_obj.y, 
                            "width": updated_obj.width,
                            "height": updated_obj.height
                        },
                        "confidence": updated_obj.confidence,
                        "track_id": updated_obj.track_id,
                        "velocity": {
                            "x": updated_obj.velocity_x,
                            "y": updated_obj.velocity_y
                        }
                    }
                    ground_truth_data.append(ground_truth_entry)
                    frame_objects.append(updated_obj)
            
            # Add frame metadata
            self._add_frame_metadata(frame, frame_num, current_time, len(frame_objects))
            
            writer.write(frame)
        
        writer.release()
        logger.info(f"Video generated: {output_path} with {len(ground_truth_data)} ground truth annotations")
        
        return output_path, ground_truth_data
    
    def _create_base_frame(self, resolution: Tuple[int, int], env_conditions: Dict[str, Any]) -> np.ndarray:
        """Create base frame with environmental conditions"""
        width, height = resolution
        
        # Create base background
        base_color = int(255 * env_conditions.get("lighting", 0.8))
        frame = np.full((height, width, 3), base_color, dtype=np.uint8)
        
        # Add road/background elements
        self._add_road_elements(frame)
        
        # Apply environmental effects
        self._apply_environmental_effects(frame, env_conditions)
        
        return frame
    
    def _add_road_elements(self, frame: np.ndarray):
        """Add basic road elements to frame"""
        height, width = frame.shape[:2]
        
        # Add road surface (bottom half)
        road_start = height // 2
        cv2.rectangle(frame, (0, road_start), (width, height), (80, 80, 80), -1)
        
        # Add lane markings
        lane_color = (200, 200, 200)
        for y in range(road_start + 20, height, 40):
            for x in range(0, width, 60):
                cv2.rectangle(frame, (x, y), (x + 30, y + 5), lane_color, -1)
        
        # Add sidewalk
        sidewalk_color = (120, 120, 120)
        cv2.rectangle(frame, (0, road_start - 20), (width, road_start), sidewalk_color, -1)
    
    def _apply_environmental_effects(self, frame: np.ndarray, env_conditions: Dict[str, Any]):
        """Apply environmental effects to frame"""
        height, width = frame.shape[:2]
        
        # Apply lighting adjustment
        lighting = env_conditions.get("lighting", 1.0)
        if lighting != 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=lighting, beta=0)
        
        # Apply noise
        noise_level = env_conditions.get("noise_level", 0.0)
        if noise_level > 0:
            noise = np.random.normal(0, noise_level * 255, frame.shape).astype(np.float32)
            frame = np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        
        # Apply weather effects
        weather = env_conditions.get("weather_effects")
        if weather == "rain_drops":
            self._add_rain_effect(frame)
        elif weather == "snow_particles":
            self._add_snow_effect(frame)
    
    def _add_rain_effect(self, frame: np.ndarray):
        """Add rain effect to frame"""
        height, width = frame.shape[:2]
        
        # Add rain drops
        for _ in range(random.randint(50, 150)):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            length = random.randint(10, 25)
            cv2.line(frame, (x, y), (x + 2, y + length), (180, 180, 180), 1)
    
    def _add_snow_effect(self, frame: np.ndarray):
        """Add snow effect to frame"""
        height, width = frame.shape[:2]
        
        # Add snow particles
        for _ in range(random.randint(100, 300)):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            radius = random.randint(1, 3)
            cv2.circle(frame, (x, y), radius, (240, 240, 240), -1)
    
    def _update_object_position(self, obj: VRUObject, current_time: float) -> VRUObject:
        """Update object position based on velocity and time"""
        # Create updated object
        updated_obj = VRUObject(
            object_type=obj.object_type,
            x=int(obj.x + obj.velocity_x * current_time),
            y=int(obj.y + obj.velocity_y * current_time),
            width=obj.width,
            height=obj.height,
            confidence=obj.confidence,
            timestamp=current_time,
            velocity_x=obj.velocity_x,
            velocity_y=obj.velocity_y,
            track_id=obj.track_id
        )
        
        return updated_obj
    
    def _is_object_visible(self, obj: VRUObject, current_time: float, total_duration: float) -> bool:
        """Check if object is visible in current frame"""
        # Basic visibility check - object should be in frame bounds
        if obj.x < -obj.width or obj.x > 1920 or obj.y < -obj.height or obj.y > 1080:
            return False
        
        # Time-based visibility (object appears and disappears)
        return True  # Simplified - all objects visible for now
    
    def _draw_vru_object(self, frame: np.ndarray, obj: VRUObject, env_conditions: Dict[str, Any]) -> np.ndarray:
        """Draw VRU object on frame"""
        template = self.object_templates[obj.object_type]
        
        # Get object color based on type and environmental conditions
        color_range = template["color_range"]
        base_color = [
            random.randint(color_range[0][i], color_range[1][i]) for i in range(3)
        ]
        
        # Adjust color based on lighting
        lighting = env_conditions.get("lighting", 1.0)
        color = [int(c * lighting) for c in base_color]
        
        # Draw main object body
        cv2.rectangle(frame, (obj.x, obj.y), (obj.x + obj.width, obj.y + obj.height), color, -1)
        
        # Add object-specific details
        self._add_object_details(frame, obj, color)
        
        # Add motion blur if object is moving fast
        speed = (obj.velocity_x ** 2 + obj.velocity_y ** 2) ** 0.5
        if speed > 5.0:  # Fast moving object
            self._add_motion_blur(frame, obj)
        
        return frame
    
    def _add_object_details(self, frame: np.ndarray, obj: VRUObject, color: List[int]):
        """Add specific details based on object type"""
        if obj.object_type == "pedestrian":
            # Add head
            head_radius = obj.width // 4
            head_center = (obj.x + obj.width // 2, obj.y + head_radius)
            cv2.circle(frame, head_center, head_radius, color, -1)
            
            # Add legs
            leg_width = obj.width // 6
            leg_height = obj.height // 3
            cv2.rectangle(frame, 
                         (obj.x + obj.width // 3, obj.y + 2 * obj.height // 3),
                         (obj.x + obj.width // 3 + leg_width, obj.y + obj.height),
                         color, -1)
            cv2.rectangle(frame,
                         (obj.x + 2 * obj.width // 3, obj.y + 2 * obj.height // 3),
                         (obj.x + 2 * obj.width // 3 + leg_width, obj.y + obj.height),
                         color, -1)
        
        elif obj.object_type == "cyclist":
            # Add wheels
            wheel_radius = obj.height // 8
            wheel_y = obj.y + 3 * obj.height // 4
            cv2.circle(frame, (obj.x + obj.width // 4, wheel_y), wheel_radius, (50, 50, 50), -1)
            cv2.circle(frame, (obj.x + 3 * obj.width // 4, wheel_y), wheel_radius, (50, 50, 50), -1)
            
            # Add rider
            rider_width = obj.width // 3
            rider_height = obj.height // 2
            cv2.rectangle(frame,
                         (obj.x + obj.width // 3, obj.y),
                         (obj.x + obj.width // 3 + rider_width, obj.y + rider_height),
                         [c // 2 for c in color], -1)
        
        elif obj.object_type == "vehicle":
            # Add windows
            window_color = (100, 150, 200)
            window_width = int(obj.width * 0.8)
            window_height = int(obj.height * 0.4)
            cv2.rectangle(frame,
                         (obj.x + obj.width // 10, obj.y + obj.height // 10),
                         (obj.x + obj.width // 10 + window_width, obj.y + obj.height // 10 + window_height),
                         window_color, -1)
            
            # Add wheels
            wheel_radius = obj.height // 6
            wheel_y = obj.y + 4 * obj.height // 5
            cv2.circle(frame, (obj.x + obj.width // 6, wheel_y), wheel_radius, (30, 30, 30), -1)
            cv2.circle(frame, (obj.x + 5 * obj.width // 6, wheel_y), wheel_radius, (30, 30, 30), -1)
    
    def _add_motion_blur(self, frame: np.ndarray, obj: VRUObject):
        """Add motion blur effect for fast moving objects"""
        # Simple motion blur simulation by drawing semi-transparent trail
        speed = (obj.velocity_x ** 2 + obj.velocity_y ** 2) ** 0.5
        blur_length = min(10, int(speed))
        
        for i in range(1, blur_length):
            alpha = 1.0 - (i / blur_length)
            trail_x = int(obj.x - obj.velocity_x * i * 0.1)
            trail_y = int(obj.y - obj.velocity_y * i * 0.1)
            
            # Draw semi-transparent trail
            overlay = frame.copy()
            cv2.rectangle(overlay, (trail_x, trail_y), 
                         (trail_x + obj.width, trail_y + obj.height),
                         (128, 128, 128), -1)
            frame = cv2.addWeighted(frame, 1 - alpha * 0.3, overlay, alpha * 0.3, 0)
    
    def _add_frame_metadata(self, frame: np.ndarray, frame_num: int, timestamp: float, object_count: int):
        """Add metadata overlay to frame"""
        # Add timestamp
        timestamp_text = f"Time: {timestamp:.2f}s"
        cv2.putText(frame, timestamp_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add frame number
        frame_text = f"Frame: {frame_num}"
        cv2.putText(frame, frame_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add object count
        count_text = f"Objects: {object_count}"
        cv2.putText(frame, count_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    def generate_test_scenarios(self) -> List[TestScenario]:
        """Generate comprehensive test scenarios"""
        scenarios = []
        
        # Simple single object scenarios
        scenarios.extend(self._generate_single_object_scenarios())
        
        # Multi-object scenarios
        scenarios.extend(self._generate_multi_object_scenarios())
        
        # Edge case scenarios
        scenarios.extend(self._generate_edge_case_scenarios())
        
        # Performance test scenarios
        scenarios.extend(self._generate_performance_scenarios())
        
        return scenarios
    
    def _generate_single_object_scenarios(self) -> List[TestScenario]:
        """Generate single object test scenarios"""
        scenarios = []
        
        for obj_type in self.object_templates.keys():
            template = self.object_templates[obj_type]
            
            # Create object with typical properties
            obj = VRUObject(
                object_type=obj_type,
                x=100,
                y=400,
                width=template["typical_size"][0],
                height=template["typical_size"][1],
                confidence=0.95,
                timestamp=0.0,
                velocity_x=template["typical_speed"] * 10,  # pixels per second
                velocity_y=0,
                track_id=1
            )
            
            scenario = TestScenario(
                name=f"single_{obj_type}_sunny",
                duration_sec=10,
                resolution=(1280, 720),
                fps=30,
                objects=[obj],
                environmental_conditions=self.environmental_templates["sunny_day"],
                complexity_level="simple"
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _generate_multi_object_scenarios(self) -> List[TestScenario]:
        """Generate multi-object test scenarios"""
        scenarios = []
        
        # Mixed object types scenario
        objects = []
        track_id = 1
        
        for i, obj_type in enumerate(self.object_templates.keys()):
            template = self.object_templates[obj_type]
            
            obj = VRUObject(
                object_type=obj_type,
                x=50 + i * 200,
                y=350 + random.randint(-50, 50),
                width=template["typical_size"][0],
                height=template["typical_size"][1], 
                confidence=random.uniform(0.7, 0.95),
                timestamp=0.0,
                velocity_x=template["typical_speed"] * random.uniform(8, 12),
                velocity_y=random.uniform(-2, 2),
                track_id=track_id
            )
            objects.append(obj)
            track_id += 1
        
        scenario = TestScenario(
            name="multi_object_mixed",
            duration_sec=15,
            resolution=(1920, 1080),
            fps=30,
            objects=objects,
            environmental_conditions=self.environmental_templates["overcast"],
            complexity_level="medium"
        )
        scenarios.append(scenario)
        
        return scenarios
    
    def _generate_edge_case_scenarios(self) -> List[TestScenario]:
        """Generate edge case test scenarios"""
        scenarios = []
        
        # Partially occluded objects
        objects = []
        
        # Object partially off-screen
        obj1 = VRUObject(
            object_type="pedestrian",
            x=-20,  # Partially off-screen
            y=400,
            width=40,
            height=80,
            confidence=0.6,
            timestamp=0.0,
            velocity_x=20,
            velocity_y=0,
            track_id=1
        )
        
        # Very small object (distant)
        obj2 = VRUObject(
            object_type="cyclist",
            x=800,
            y=300,
            width=15,  # Very small
            height=30,
            confidence=0.4,
            timestamp=0.0,
            velocity_x=5,
            velocity_y=0,
            track_id=2
        )
        
        objects = [obj1, obj2]
        
        scenario = TestScenario(
            name="edge_cases_occlusion",
            duration_sec=12,
            resolution=(1280, 720),
            fps=30,
            objects=objects,
            environmental_conditions=self.environmental_templates["rainy"],
            complexity_level="complex"
        )
        scenarios.append(scenario)
        
        return scenarios
    
    def _generate_performance_scenarios(self) -> List[TestScenario]:
        """Generate performance testing scenarios"""
        scenarios = []
        
        # High object density scenario
        objects = []
        track_id = 1
        
        # Create many objects for stress testing
        for i in range(20):
            obj_type = random.choice(list(self.object_templates.keys()))
            template = self.object_templates[obj_type]
            
            obj = VRUObject(
                object_type=obj_type,
                x=random.randint(0, 1600),
                y=random.randint(300, 700),
                width=template["typical_size"][0],
                height=template["typical_size"][1],
                confidence=random.uniform(0.5, 0.9),
                timestamp=0.0,
                velocity_x=random.uniform(-30, 30),
                velocity_y=random.uniform(-10, 10),
                track_id=track_id
            )
            objects.append(obj)
            track_id += 1
        
        scenario = TestScenario(
            name="performance_high_density",
            duration_sec=20,
            resolution=(1920, 1080),
            fps=30,
            objects=objects,
            environmental_conditions=self.environmental_templates["night"],
            complexity_level="extreme"
        )
        scenarios.append(scenario)
        
        return scenarios
    
    def save_ground_truth_annotations(self, ground_truth_data: List[Dict[str, Any]], output_path: str):
        """Save ground truth annotations to JSON file"""
        annotations = {
            "metadata": {
                "created": datetime.now().isoformat(),
                "total_annotations": len(ground_truth_data),
                "format_version": "1.0"
            },
            "annotations": ground_truth_data
        }
        
        with open(output_path, 'w') as f:
            json.dump(annotations, f, indent=2)
        
        logger.info(f"Ground truth annotations saved to: {output_path}")
    
    def generate_mock_api_responses(self) -> Dict[str, Any]:
        """Generate mock API responses for testing"""
        return {
            "health_check": {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "database": "connected",
                "ml_service": "operational"
            },
            "project_list": {
                "projects": [
                    {
                        "id": "test_project_001",
                        "name": "VRU Test Project",
                        "status": "ACTIVE",
                        "created_at": datetime.now().isoformat()
                    }
                ]
            },
            "detection_results": {
                "session_id": "test_session_001",
                "detections": [
                    {
                        "timestamp": 1.5,
                        "object_class": "pedestrian",
                        "confidence": 0.89,
                        "bbox": {"x": 150, "y": 400, "width": 40, "height": 80}
                    },
                    {
                        "timestamp": 3.2,
                        "object_class": "cyclist",
                        "confidence": 0.92,
                        "bbox": {"x": 300, "y": 350, "width": 60, "height": 120}
                    }
                ],
                "total_detections": 2,
                "processing_time_sec": 0.45
            },
            "validation_results": {
                "test_session_id": "test_session_001",
                "metrics": {
                    "precision": 0.87,
                    "recall": 0.91,
                    "f1_score": 0.89,
                    "accuracy": 0.85
                },
                "confusion_matrix": {
                    "true_positives": 87,
                    "false_positives": 13,
                    "false_negatives": 9,
                    "true_negatives": 91
                }
            }
        }


def create_comprehensive_test_dataset(output_dir: str) -> Dict[str, Any]:
    """Create comprehensive test dataset for VRU platform"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    generator = VRUTestDataGenerator()
    
    logger.info("🎬 Generating comprehensive VRU test dataset")
    
    # Generate test scenarios
    scenarios = generator.generate_test_scenarios()
    
    dataset_info = {
        "created": datetime.now().isoformat(),
        "total_scenarios": len(scenarios),
        "output_directory": str(output_path),
        "scenarios": []
    }
    
    # Generate videos and annotations for each scenario
    for i, scenario in enumerate(scenarios):
        logger.info(f"Generating scenario {i+1}/{len(scenarios)}: {scenario.name}")
        
        # Generate video
        video_path = output_path / f"{scenario.name}.mp4"
        video_file, ground_truth = generator.generate_test_video_with_objects(
            scenario, str(video_path)
        )
        
        # Save ground truth annotations
        annotations_path = output_path / f"{scenario.name}_annotations.json"
        generator.save_ground_truth_annotations(ground_truth, str(annotations_path))
        
        # Save scenario metadata
        scenario_metadata = {
            "name": scenario.name,
            "video_file": str(video_path),
            "annotations_file": str(annotations_path),
            "duration_sec": scenario.duration_sec,
            "fps": scenario.fps,
            "resolution": scenario.resolution,
            "complexity_level": scenario.complexity_level,
            "object_count": len(scenario.objects),
            "total_annotations": len(ground_truth)
        }
        
        dataset_info["scenarios"].append(scenario_metadata)
    
    # Generate mock API responses
    mock_responses = generator.generate_mock_api_responses()
    mock_responses_path = output_path / "mock_api_responses.json"
    
    with open(mock_responses_path, 'w') as f:
        json.dump(mock_responses, f, indent=2)
    
    # Save dataset metadata
    dataset_metadata_path = output_path / "dataset_metadata.json"
    with open(dataset_metadata_path, 'w') as f:
        json.dump(dataset_info, f, indent=2)
    
    logger.info(f"✅ Comprehensive test dataset created in: {output_path}")
    logger.info(f"Generated {len(scenarios)} test scenarios with annotations")
    
    return dataset_info


if __name__ == "__main__":
    # Generate comprehensive test dataset
    output_directory = "/home/user/Testing/ai-model-validation-platform/backend/tests/fixtures/vru_test_data"
    dataset_info = create_comprehensive_test_dataset(output_directory)
    
    print("\n" + "="*80)
    print("VRU TEST DATASET GENERATION COMPLETE")
    print("="*80)
    print(f"Output Directory: {dataset_info['output_directory']}")
    print(f"Total Scenarios: {dataset_info['total_scenarios']}")
    print(f"Dataset Created: {dataset_info['created']}")
    print("="*80)