# Test Data Management Strategy - AI Model Validation Platform

## Overview

Effective test data management is crucial for comprehensive testing of the AI Model Validation Platform. This strategy covers synthetic data generation, test data lifecycle management, data privacy compliance, and cross-environment data synchronization.

## Test Data Categories

### 1. Synthetic Video Generation
- **Purpose**: Create controlled test videos with known objects and scenarios
- **Requirements**: Various lighting conditions, object types, movement patterns
- **Volume**: Small (unit tests), Medium (integration), Large (performance)

### 2. Ground Truth Data
- **Purpose**: Provide expected detection results for validation testing
- **Requirements**: Time-synchronized annotations, confidence scores, bounding boxes
- **Format**: JSON with standardized schema

### 3. User and Project Data
- **Purpose**: Support authentication, authorization, and multi-tenancy testing
- **Requirements**: Realistic user profiles, project configurations, permissions
- **Privacy**: No real user data, anonymized patterns

### 4. Detection Events
- **Purpose**: Simulate Raspberry Pi detection streams for validation testing
- **Requirements**: Realistic timing, confidence distributions, false positives/negatives
- **Volume**: High-frequency streams for performance testing

## Synthetic Video Generation Framework

### Video Generator Implementation
```python
# tests/utils/video_generator.py

import cv2
import numpy as np
import json
import random
import math
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

class ObjectType(Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    VEHICLE = "vehicle"
    DISTRACTED_DRIVER = "distracted_driver"

class WeatherCondition(Enum):
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    NIGHT = "night"
    FOG = "fog"

class ScenarioType(Enum):
    HIGHWAY = "highway"
    URBAN_INTERSECTION = "urban_intersection"
    SCHOOL_ZONE = "school_zone"
    PARKING_LOT = "parking_lot"
    RESIDENTIAL = "residential"

@dataclass
class DetectionObject:
    """Represents a detectable object in the video."""
    object_id: int
    object_type: ObjectType
    start_frame: int
    end_frame: int
    trajectory: List[Tuple[int, int, int, int]]  # [(x, y, width, height), ...]
    confidence_base: float = 0.85
    visibility_pattern: List[float] = None  # Per-frame visibility (0-1)

@dataclass
class GroundTruthAnnotation:
    """Ground truth annotation for a detection object."""
    timestamp: float
    object_type: str
    bounding_box: Dict[str, int]
    confidence: float
    track_id: int
    visible: bool = True

class SyntheticVideoGenerator:
    """Generate synthetic test videos with controlled scenarios."""
    
    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.objects: List[DetectionObject] = []
        self.ground_truth: List[GroundTruthAnnotation] = []
        
        # Object appearance templates
        self.object_colors = {
            ObjectType.PEDESTRIAN: (0, 255, 0),      # Green
            ObjectType.CYCLIST: (255, 0, 0),         # Red
            ObjectType.VEHICLE: (0, 0, 255),         # Blue
            ObjectType.DISTRACTED_DRIVER: (255, 255, 0)  # Yellow
        }
        
        self.object_sizes = {
            ObjectType.PEDESTRIAN: (30, 80),
            ObjectType.CYCLIST: (40, 60),
            ObjectType.VEHICLE: (80, 40),
            ObjectType.DISTRACTED_DRIVER: (25, 25)
        }
    
    def add_moving_pedestrian(
        self, 
        start_time: float, 
        duration: float,
        start_pos: Tuple[int, int],
        end_pos: Tuple[int, int],
        confidence_base: float = 0.85
    ):
        """Add a moving pedestrian to the video."""
        start_frame = int(start_time * self.fps)
        end_frame = int((start_time + duration) * self.fps)
        
        # Calculate trajectory
        trajectory = []
        width, height = self.object_sizes[ObjectType.PEDESTRIAN]
        
        for frame in range(start_frame, end_frame):
            progress = (frame - start_frame) / (end_frame - start_frame)
            x = int(start_pos[0] + (end_pos[0] - start_pos[0]) * progress)
            y = int(start_pos[1] + (end_pos[1] - start_pos[1]) * progress)
            
            # Add some natural variation
            x += random.randint(-5, 5)
            y += random.randint(-2, 2)
            
            trajectory.append((x, y, width, height))
        
        # Create visibility pattern (objects might be occluded)
        visibility_pattern = []
        for frame in range(end_frame - start_frame):
            base_visibility = 1.0
            
            # Simulate occlusion
            if random.random() < 0.05:  # 5% chance of temporary occlusion
                base_visibility = random.uniform(0.2, 0.8)
            
            visibility_pattern.append(base_visibility)
        
        detection_object = DetectionObject(
            object_id=len(self.objects),
            object_type=ObjectType.PEDESTRIAN,
            start_frame=start_frame,
            end_frame=end_frame,
            trajectory=trajectory,
            confidence_base=confidence_base,
            visibility_pattern=visibility_pattern
        )
        
        self.objects.append(detection_object)
        
        # Generate ground truth annotations
        for frame, (x, y, w, h) in enumerate(trajectory):
            timestamp = (start_frame + frame) / self.fps
            visibility = visibility_pattern[frame]
            
            annotation = GroundTruthAnnotation(
                timestamp=timestamp,
                object_type=ObjectType.PEDESTRIAN.value,
                bounding_box={"x": x, "y": y, "width": w, "height": h},
                confidence=confidence_base * visibility,
                track_id=detection_object.object_id,
                visible=visibility > 0.5
            )
            
            self.ground_truth.append(annotation)
    
    def add_cyclist_crossing(
        self, 
        start_time: float, 
        crossing_duration: float,
        lane_y: int,
        confidence_base: float = 0.80
    ):
        """Add a cyclist crossing the frame."""
        start_frame = int(start_time * self.fps)
        end_frame = int((start_time + crossing_duration) * self.fps)
        
        trajectory = []
        width, height = self.object_sizes[ObjectType.CYCLIST]
        
        for frame in range(start_frame, end_frame):
            progress = (frame - start_frame) / (end_frame - start_frame)
            x = int(-width + (self.width + 2 * width) * progress)
            y = lane_y + random.randint(-10, 10)  # Some variation
            
            trajectory.append((x, y, width, height))
        
        detection_object = DetectionObject(
            object_id=len(self.objects),
            object_type=ObjectType.CYCLIST,
            start_frame=start_frame,
            end_frame=end_frame,
            trajectory=trajectory,
            confidence_base=confidence_base
        )
        
        self.objects.append(detection_object)
        
        # Generate ground truth
        for frame, (x, y, w, h) in enumerate(trajectory):
            # Only annotate when cyclist is visible in frame
            if 0 <= x <= self.width and 0 <= x + w <= self.width:
                timestamp = (start_frame + frame) / self.fps
                
                annotation = GroundTruthAnnotation(
                    timestamp=timestamp,
                    object_type=ObjectType.CYCLIST.value,
                    bounding_box={"x": x, "y": y, "width": w, "height": h},
                    confidence=confidence_base,
                    track_id=detection_object.object_id,
                    visible=True
                )
                
                self.ground_truth.append(annotation)
    
    def add_vehicle_sequence(
        self, 
        start_time: float, 
        count: int,
        lane_y: int,
        speed_variation: float = 0.2
    ):
        """Add a sequence of vehicles."""
        base_speed = self.width / 5  # pixels per second
        vehicle_spacing = 100  # pixels
        
        for i in range(count):
            vehicle_start_time = start_time + (i * vehicle_spacing / base_speed)
            speed = base_speed * (1 + random.uniform(-speed_variation, speed_variation))
            duration = (self.width + 160) / speed  # Time to cross frame
            
            start_frame = int(vehicle_start_time * self.fps)
            end_frame = int((vehicle_start_time + duration) * self.fps)
            
            trajectory = []
            width, height = self.object_sizes[ObjectType.VEHICLE]
            
            for frame in range(start_frame, end_frame):
                progress = (frame - start_frame) / (end_frame - start_frame)
                x = int(-width + (self.width + 2 * width) * progress)
                y = lane_y + random.randint(-5, 5)
                
                trajectory.append((x, y, width, height))
            
            detection_object = DetectionObject(
                object_id=len(self.objects),
                object_type=ObjectType.VEHICLE,
                start_frame=start_frame,
                end_frame=end_frame,
                trajectory=trajectory,
                confidence_base=0.90
            )
            
            self.objects.append(detection_object)
            
            # Generate ground truth
            for frame, (x, y, w, h) in enumerate(trajectory):
                if 0 <= x <= self.width:
                    timestamp = (start_frame + frame) / self.fps
                    
                    annotation = GroundTruthAnnotation(
                        timestamp=timestamp,
                        object_type=ObjectType.VEHICLE.value,
                        bounding_box={"x": x, "y": y, "width": w, "height": h},
                        confidence=0.90,
                        track_id=detection_object.object_id,
                        visible=True
                    )
                    
                    self.ground_truth.append(annotation)
    
    def apply_weather_effects(
        self, 
        frame: np.ndarray, 
        weather: WeatherCondition,
        intensity: float = 0.5
    ) -> np.ndarray:
        """Apply weather effects to frame."""
        if weather == WeatherCondition.RAINY:
            # Add rain effect
            rain_intensity = int(intensity * 1000)
            for _ in range(rain_intensity):
                x = random.randint(0, frame.shape[1] - 1)
                y = random.randint(0, frame.shape[0] - 1)
                cv2.circle(frame, (x, y), 1, (200, 200, 255), -1)
        
        elif weather == WeatherCondition.FOG:
            # Add fog effect by blending with white
            fog_overlay = np.ones_like(frame) * 255
            frame = cv2.addWeighted(frame, 1 - intensity * 0.6, fog_overlay, intensity * 0.6, 0)
        
        elif weather == WeatherCondition.NIGHT:
            # Darken the frame
            frame = cv2.convertScaleAbs(frame, alpha=1 - intensity * 0.7, beta=0)
        
        elif weather == WeatherCondition.CLOUDY:
            # Reduce brightness slightly
            frame = cv2.convertScaleAbs(frame, alpha=1 - intensity * 0.3, beta=0)
        
        return frame
    
    def generate_background(
        self, 
        scenario: ScenarioType,
        frame_number: int
    ) -> np.ndarray:
        """Generate background based on scenario."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        if scenario == ScenarioType.HIGHWAY:
            # Highway with lanes
            frame[:] = (50, 80, 50)  # Dark green background
            
            # Draw road
            road_y_start = self.height // 3
            road_y_end = self.height
            frame[road_y_start:road_y_end] = (60, 60, 60)  # Gray road
            
            # Lane markings
            for lane in range(2, self.width - 20, 40):
                cv2.line(frame, (lane, road_y_start + 20), 
                        (lane, road_y_end - 20), (255, 255, 255), 2)
        
        elif scenario == ScenarioType.URBAN_INTERSECTION:
            # Urban intersection
            frame[:] = (100, 100, 100)  # Gray background
            
            # Crosswalk
            for stripe in range(0, self.width, 20):
                cv2.rectangle(frame, (stripe, self.height//2 - 30), 
                             (stripe + 10, self.height//2 + 30), (255, 255, 255), -1)
        
        elif scenario == ScenarioType.SCHOOL_ZONE:
            # School zone with sidewalks
            frame[:] = (120, 150, 80)  # Light green
            
            # Sidewalk
            cv2.rectangle(frame, (0, 0), (self.width, 50), (200, 200, 200), -1)
            cv2.rectangle(frame, (0, self.height - 50), 
                         (self.width, self.height), (200, 200, 200), -1)
            
            # School zone sign
            cv2.rectangle(frame, (self.width - 100, 20), 
                         (self.width - 20, 80), (255, 255, 0), -1)
        
        return frame
    
    def render_objects_on_frame(
        self, 
        frame: np.ndarray, 
        frame_number: int
    ) -> np.ndarray:
        """Render all objects on the current frame."""
        for obj in self.objects:
            if obj.start_frame <= frame_number < obj.end_frame:
                trajectory_index = frame_number - obj.start_frame
                
                if trajectory_index < len(obj.trajectory):
                    x, y, w, h = obj.trajectory[trajectory_index]
                    
                    # Get visibility
                    visibility = 1.0
                    if obj.visibility_pattern and trajectory_index < len(obj.visibility_pattern):
                        visibility = obj.visibility_pattern[trajectory_index]
                    
                    if visibility > 0.1:  # Only render if somewhat visible
                        color = self.object_colors[obj.object_type]
                        
                        # Adjust color based on visibility
                        adjusted_color = tuple(int(c * visibility) for c in color)
                        
                        # Draw object
                        cv2.rectangle(frame, (x, y), (x + w, y + h), adjusted_color, -1)
                        
                        # Add object ID text
                        cv2.putText(frame, f"{obj.object_type.value[:3]}{obj.object_id}", 
                                  (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                                  (255, 255, 255), 1)
        
        return frame
    
    def generate_video(
        self, 
        output_path: Path,
        duration: float,
        scenario: ScenarioType = ScenarioType.HIGHWAY,
        weather: WeatherCondition = WeatherCondition.SUNNY,
        weather_intensity: float = 0.5
    ):
        """Generate complete synthetic video."""
        total_frames = int(duration * self.fps)
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, self.fps, (self.width, self.height))
        
        print(f"Generating {duration}s video with {len(self.objects)} objects...")
        
        for frame_number in range(total_frames):
            # Generate background
            frame = self.generate_background(scenario, frame_number)
            
            # Render objects
            frame = self.render_objects_on_frame(frame, frame_number)
            
            # Apply weather effects
            frame = self.apply_weather_effects(frame, weather, weather_intensity)
            
            # Write frame
            out.write(frame)
            
            if frame_number % (self.fps * 10) == 0:  # Progress every 10 seconds
                progress = (frame_number / total_frames) * 100
                print(f"Progress: {progress:.1f}%")
        
        out.release()
        print(f"Video generated: {output_path}")
    
    def save_ground_truth(self, output_path: Path):
        """Save ground truth annotations to JSON file."""
        ground_truth_data = {
            "video_metadata": {
                "width": self.width,
                "height": self.height,
                "fps": self.fps,
                "total_objects": len(self.objects)
            },
            "annotations": [asdict(annotation) for annotation in self.ground_truth]
        }
        
        with open(output_path, 'w') as f:
            json.dump(ground_truth_data, f, indent=2)
        
        print(f"Ground truth saved: {output_path} ({len(self.ground_truth)} annotations)")

# Test scenario generators
class TestScenarioGenerator:
    """Generate predefined test scenarios."""
    
    @staticmethod
    def highway_pedestrian_crossing(duration: float = 30.0) -> SyntheticVideoGenerator:
        """Generate highway scenario with pedestrian crossing."""
        generator = SyntheticVideoGenerator()
        
        # Add pedestrian crossing at 10 seconds
        generator.add_moving_pedestrian(
            start_time=10.0,
            duration=8.0,
            start_pos=(50, 300),
            end_pos=(600, 350),
            confidence_base=0.87
        )
        
        # Add vehicle sequence
        generator.add_vehicle_sequence(
            start_time=5.0,
            count=3,
            lane_y=400,
            speed_variation=0.1
        )
        
        return generator
    
    @staticmethod
    def urban_intersection_multi_object(duration: float = 45.0) -> SyntheticVideoGenerator:
        """Generate urban intersection with multiple objects."""
        generator = SyntheticVideoGenerator()
        
        # Multiple pedestrians
        for i in range(3):
            generator.add_moving_pedestrian(
                start_time=5.0 + i * 3,
                duration=6.0,
                start_pos=(100 + i * 150, 200),
                end_pos=(200 + i * 150, 500),
                confidence_base=0.85 - i * 0.05
            )
        
        # Cyclist crossing
        generator.add_cyclist_crossing(
            start_time=15.0,
            crossing_duration=4.0,
            lane_y=300,
            confidence_base=0.82
        )
        
        # Vehicle sequence
        generator.add_vehicle_sequence(
            start_time=20.0,
            count=5,
            lane_y=450,
            speed_variation=0.3
        )
        
        return generator
    
    @staticmethod
    def challenging_conditions(duration: float = 60.0) -> SyntheticVideoGenerator:
        """Generate challenging detection scenario."""
        generator = SyntheticVideoGenerator()
        
        # Partially occluded pedestrians
        generator.add_moving_pedestrian(
            start_time=10.0,
            duration=5.0,
            start_pos=(300, 250),
            end_pos=(400, 300),
            confidence_base=0.65  # Lower confidence due to occlusion
        )
        
        # Fast-moving cyclist (harder to detect)
        generator.add_cyclist_crossing(
            start_time=25.0,
            crossing_duration=2.0,  # Fast crossing
            lane_y=350,
            confidence_base=0.70
        )
        
        # Multiple overlapping vehicles
        generator.add_vehicle_sequence(
            start_time=5.0,
            count=8,
            lane_y=400,
            speed_variation=0.4
        )
        
        return generator
```

### Test Data Factory System

```python
# tests/utils/test_data_factory.py

import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import uuid
from dataclasses import dataclass
import numpy as np

@dataclass
class TestUser:
    """Test user data structure."""
    id: str
    email: str
    full_name: str
    password: str
    is_active: bool = True
    created_at: datetime = None

@dataclass
class TestProject:
    """Test project data structure."""
    id: str
    name: str
    description: str
    camera_model: str
    camera_view: str
    lens_type: str
    resolution: str
    frame_rate: int
    signal_type: str
    status: str
    owner_id: str
    created_at: datetime = None

@dataclass
class TestDetectionEvent:
    """Test detection event data structure."""
    id: str
    test_session_id: str
    timestamp: float
    confidence: float
    class_label: str
    validation_result: str
    created_at: datetime = None

class TestDataFactory:
    """Factory for generating consistent test data."""
    
    def __init__(self, seed: int = 42):
        """Initialize factory with random seed for reproducibility."""
        random.seed(seed)
        np.random.seed(seed)
        
        # Realistic data pools
        self.first_names = [
            "John", "Jane", "Michael", "Sarah", "David", "Emily", "Chris", "Lisa",
            "Robert", "Jennifer", "William", "Jessica", "James", "Ashley", "Daniel"
        ]
        
        self.last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
            "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez"
        ]
        
        self.camera_models = [
            "FLIR Blackfly S", "Basler acA1920-40uc", "Allied Vision Mako G-234",
            "Point Grey Grasshopper3", "IDS uEye CP", "Teledyne DALSA Genie",
            "Cognex In-Sight 7000", "Keyence CV-X Series"
        ]
        
        self.camera_views = [
            "Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior",
            "Side-facing Pedestrian", "360-degree Coverage"
        ]
        
        self.lens_types = [
            "Wide-angle", "Telephoto", "Standard", "Fish-eye", "Macro"
        ]
        
        self.resolutions = [
            "1920x1080", "2592x1944", "1280x720", "3840x2160", "1600x1200"
        ]
        
        self.signal_types = [
            "GPIO", "Network Packet", "Serial", "USB", "Ethernet"
        ]
        
        self.detection_classes = [
            "pedestrian", "cyclist", "vehicle", "distracted_driver", "motorcycle"
        ]
        
        self.project_statuses = ["Active", "Completed", "Draft", "Archived"]
        
    def generate_user(self, user_id: str = None, email: str = None) -> TestUser:
        """Generate a test user."""
        if not user_id:
            user_id = str(uuid.uuid4())
        
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        
        if not email:
            email = f"{first_name.lower()}.{last_name.lower()}@testdomain.com"
        
        return TestUser(
            id=user_id,
            email=email,
            full_name=f"{first_name} {last_name}",
            password="SecureTestPassword123!",
            is_active=random.choice([True, True, True, False]),  # Mostly active
            created_at=datetime.now() - timedelta(days=random.randint(1, 365))
        )
    
    def generate_project(self, owner_id: str, project_id: str = None) -> TestProject:
        """Generate a test project."""
        if not project_id:
            project_id = str(uuid.uuid4())
        
        # Generate realistic project names
        project_types = ["Highway", "Urban", "School Zone", "Parking", "Industrial"]
        detection_types = ["VRU Detection", "Driver Monitoring", "Traffic Analysis"]
        locations = ["Downtown", "Suburban", "Rural", "Campus", "Commercial"]
        
        name_parts = [
            random.choice(locations),
            random.choice(project_types),
            random.choice(detection_types)
        ]
        project_name = " ".join(name_parts)
        
        description = f"Test project for {name_parts[2].lower()} in {name_parts[0].lower()} {name_parts[1].lower()} environment."
        
        return TestProject(
            id=project_id,
            name=project_name,
            description=description,
            camera_model=random.choice(self.camera_models),
            camera_view=random.choice(self.camera_views),
            lens_type=random.choice(self.lens_types),
            resolution=random.choice(self.resolutions),
            frame_rate=random.choice([15, 30, 60]),
            signal_type=random.choice(self.signal_types),
            status=random.choice(self.project_statuses),
            owner_id=owner_id,
            created_at=datetime.now() - timedelta(days=random.randint(1, 180))
        )
    
    def generate_detection_events(
        self, 
        test_session_id: str,
        count: int,
        video_duration: float = 60.0,
        ground_truth_events: List[Dict] = None
    ) -> List[TestDetectionEvent]:
        """Generate realistic detection events for a test session."""
        events = []
        
        # If ground truth is provided, generate events based on it
        if ground_truth_events:
            for gt_event in ground_truth_events:
                # True positive (correct detection)
                if random.random() < 0.85:  # 85% detection rate
                    timestamp_variation = random.uniform(-0.1, 0.1)  # ±100ms variation
                    confidence_variation = random.uniform(-0.1, 0.1)
                    
                    event = TestDetectionEvent(
                        id=str(uuid.uuid4()),
                        test_session_id=test_session_id,
                        timestamp=gt_event["timestamp"] + timestamp_variation,
                        confidence=max(0.1, min(1.0, gt_event["confidence"] + confidence_variation)),
                        class_label=gt_event["object_type"],
                        validation_result="TP",
                        created_at=datetime.now()
                    )
                    events.append(event)
            
            # Add false positives (random detections)
            false_positive_count = int(len(ground_truth_events) * 0.15)  # 15% FP rate
            
            for _ in range(false_positive_count):
                event = TestDetectionEvent(
                    id=str(uuid.uuid4()),
                    test_session_id=test_session_id,
                    timestamp=random.uniform(0, video_duration),
                    confidence=random.uniform(0.3, 0.8),  # Lower confidence for FP
                    class_label=random.choice(self.detection_classes),
                    validation_result="FP",
                    created_at=datetime.now()
                )
                events.append(event)
        
        else:
            # Generate random events
            for _ in range(count):
                validation_results = ["TP", "FP", "FN"]
                weights = [0.7, 0.2, 0.1]  # Realistic distribution
                
                validation_result = random.choices(validation_results, weights=weights)[0]
                
                # Adjust confidence based on validation result
                if validation_result == "TP":
                    confidence = random.uniform(0.7, 0.95)
                elif validation_result == "FP":
                    confidence = random.uniform(0.3, 0.7)
                else:  # FN
                    confidence = random.uniform(0.1, 0.5)
                
                event = TestDetectionEvent(
                    id=str(uuid.uuid4()),
                    test_session_id=test_session_id,
                    timestamp=random.uniform(0, video_duration),
                    confidence=confidence,
                    class_label=random.choice(self.detection_classes),
                    validation_result=validation_result,
                    created_at=datetime.now()
                )
                events.append(event)
        
        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)
        
        return events
    
    def generate_test_dataset(
        self, 
        num_users: int = 10,
        projects_per_user: int = 3,
        sessions_per_project: int = 2,
        events_per_session: int = 50
    ) -> Dict[str, Any]:
        """Generate a complete test dataset."""
        dataset = {
            "users": [],
            "projects": [],
            "test_sessions": [],
            "detection_events": [],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "num_users": num_users,
                "num_projects": num_users * projects_per_user,
                "num_sessions": num_users * projects_per_user * sessions_per_project,
                "num_events": num_users * projects_per_user * sessions_per_project * events_per_session
            }
        }
        
        # Generate users
        users = []
        for i in range(num_users):
            user = self.generate_user()
            users.append(user)
            dataset["users"].append(user.__dict__)
        
        # Generate projects
        projects = []
        for user in users:
            for j in range(projects_per_user):
                project = self.generate_project(user.id)
                projects.append(project)
                dataset["projects"].append(project.__dict__)
        
        # Generate test sessions and events
        for project in projects:
            for k in range(sessions_per_project):
                session_id = str(uuid.uuid4())
                
                # Generate detection events for this session
                events = self.generate_detection_events(
                    test_session_id=session_id,
                    count=events_per_session
                )
                
                session_data = {
                    "id": session_id,
                    "name": f"Test Session {k + 1}",
                    "project_id": project.id,
                    "status": random.choice(["created", "running", "completed", "failed"]),
                    "tolerance_ms": random.choice([50, 100, 150, 200]),
                    "created_at": datetime.now().isoformat()
                }
                
                dataset["test_sessions"].append(session_data)
                
                for event in events:
                    dataset["detection_events"].append(event.__dict__)
        
        return dataset
    
    def save_dataset_to_files(self, dataset: Dict[str, Any], output_dir: Path):
        """Save dataset to separate JSON files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save each data type to separate files
        for data_type, data_list in dataset.items():
            if data_type != "metadata":
                output_file = output_dir / f"{data_type}.json"
                
                # Convert datetime objects to strings
                serializable_data = []
                for item in data_list:
                    if isinstance(item, dict):
                        serializable_item = {}
                        for key, value in item.items():
                            if isinstance(value, datetime):
                                serializable_item[key] = value.isoformat()
                            else:
                                serializable_item[key] = value
                        serializable_data.append(serializable_item)
                    else:
                        serializable_data.append(item)
                
                with open(output_file, 'w') as f:
                    json.dump(serializable_data, f, indent=2)
                
                print(f"Saved {len(serializable_data)} {data_type} to {output_file}")
        
        # Save metadata
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(dataset["metadata"], f, indent=2)
        
        print(f"Dataset saved to {output_dir}")
```

### Test Data Pipeline

```python
# tests/utils/data_pipeline.py

import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, List, Any
import json
import logging
from video_generator import SyntheticVideoGenerator, TestScenarioGenerator, ScenarioType, WeatherCondition
from test_data_factory import TestDataFactory

class TestDataPipeline:
    """Automated test data generation pipeline."""
    
    def __init__(self, output_dir: Path = Path("tests/fixtures")):
        self.output_dir = output_dir
        self.video_dir = output_dir / "videos"
        self.ground_truth_dir = output_dir / "ground_truth"
        self.data_dir = output_dir / "data"
        self.factory = TestDataFactory()
        
        # Create directories
        for directory in [self.video_dir, self.ground_truth_dir, self.data_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    async def generate_video_suite(self):
        """Generate complete suite of test videos."""
        video_specs = [
            {
                "name": "highway_simple",
                "generator": TestScenarioGenerator.highway_pedestrian_crossing,
                "duration": 30.0,
                "scenario": ScenarioType.HIGHWAY,
                "weather": WeatherCondition.SUNNY,
                "description": "Simple highway scenario with pedestrian crossing"
            },
            {
                "name": "urban_complex",
                "generator": TestScenarioGenerator.urban_intersection_multi_object,
                "duration": 45.0,
                "scenario": ScenarioType.URBAN_INTERSECTION,
                "weather": WeatherCondition.CLOUDY,
                "description": "Complex urban intersection with multiple objects"
            },
            {
                "name": "challenging_weather",
                "generator": TestScenarioGenerator.challenging_conditions,
                "duration": 60.0,
                "scenario": ScenarioType.HIGHWAY,
                "weather": WeatherCondition.RAINY,
                "description": "Challenging conditions with rain and low visibility"
            },
            {
                "name": "night_conditions",
                "generator": TestScenarioGenerator.highway_pedestrian_crossing,
                "duration": 30.0,
                "scenario": ScenarioType.HIGHWAY,
                "weather": WeatherCondition.NIGHT,
                "description": "Night conditions with reduced visibility"
            },
            {
                "name": "performance_test_long",
                "generator": TestScenarioGenerator.challenging_conditions,
                "duration": 120.0,
                "scenario": ScenarioType.URBAN_INTERSECTION,
                "weather": WeatherCondition.SUNNY,
                "description": "Long duration video for performance testing"
            }
        ]
        
        generation_tasks = []
        
        for spec in video_specs:
            task = self._generate_single_video(spec)
            generation_tasks.append(task)
        
        # Generate videos concurrently
        await asyncio.gather(*generation_tasks)
        
        self.logger.info(f"Generated {len(video_specs)} test videos")
    
    async def _generate_single_video(self, spec: Dict[str, Any]):
        """Generate a single test video."""
        video_name = spec["name"]
        video_path = self.video_dir / f"{video_name}.mp4"
        ground_truth_path = self.ground_truth_dir / f"{video_name}_gt.json"
        
        # Skip if video already exists
        if video_path.exists() and ground_truth_path.exists():
            self.logger.info(f"Video {video_name} already exists, skipping")
            return
        
        self.logger.info(f"Generating video: {video_name}")
        
        # Create generator
        generator = spec["generator"](spec["duration"])
        
        # Generate video
        await asyncio.get_event_loop().run_in_executor(
            None,
            generator.generate_video,
            video_path,
            spec["duration"],
            spec["scenario"],
            spec["weather"],
            0.5  # weather intensity
        )
        
        # Save ground truth
        generator.save_ground_truth(ground_truth_path)
        
        # Create metadata file
        metadata = {
            "video_name": video_name,
            "file_path": str(video_path),
            "ground_truth_path": str(ground_truth_path),
            "duration": spec["duration"],
            "scenario": spec["scenario"].value,
            "weather": spec["weather"].value,
            "description": spec["description"],
            "object_count": len(generator.objects),
            "annotation_count": len(generator.ground_truth)
        }
        
        metadata_path = self.data_dir / f"{video_name}_metadata.json"
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
        
        self.logger.info(f"Completed video: {video_name}")
    
    async def generate_database_fixtures(self):
        """Generate database test fixtures."""
        fixture_specs = [
            {
                "name": "small_dataset",
                "users": 5,
                "projects_per_user": 2,
                "sessions_per_project": 1,
                "events_per_session": 25,
                "description": "Small dataset for unit tests"
            },
            {
                "name": "medium_dataset", 
                "users": 20,
                "projects_per_user": 3,
                "sessions_per_project": 2,
                "events_per_session": 50,
                "description": "Medium dataset for integration tests"
            },
            {
                "name": "large_dataset",
                "users": 100,
                "projects_per_user": 5,
                "sessions_per_project": 3,
                "events_per_session": 100,
                "description": "Large dataset for performance tests"
            }
        ]
        
        for spec in fixture_specs:
            fixture_dir = self.data_dir / spec["name"]
            
            if fixture_dir.exists():
                self.logger.info(f"Fixture {spec['name']} already exists, skipping")
                continue
            
            self.logger.info(f"Generating fixture: {spec['name']}")
            
            dataset = self.factory.generate_test_dataset(
                num_users=spec["users"],
                projects_per_user=spec["projects_per_user"],
                sessions_per_project=spec["sessions_per_project"],
                events_per_session=spec["events_per_session"]
            )
            
            self.factory.save_dataset_to_files(dataset, fixture_dir)
            
            # Save fixture metadata
            fixture_metadata = {
                "name": spec["name"],
                "description": spec["description"],
                "directory": str(fixture_dir),
                "statistics": dataset["metadata"]
            }
            
            metadata_path = fixture_dir / "fixture_metadata.json"
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(fixture_metadata, indent=2))
        
        self.logger.info("Database fixtures generation completed")
    
    async def generate_all_test_data(self):
        """Generate complete test data suite."""
        self.logger.info("Starting test data generation pipeline")
        
        # Generate videos and database fixtures concurrently
        await asyncio.gather(
            self.generate_video_suite(),
            self.generate_database_fixtures()
        )
        
        # Generate summary report
        await self.generate_summary_report()
        
        self.logger.info("Test data generation pipeline completed")
    
    async def generate_summary_report(self):
        """Generate summary report of all test data."""
        report = {
            "generation_timestamp": datetime.now().isoformat(),
            "output_directory": str(self.output_dir),
            "videos": [],
            "datasets": [],
            "total_size_mb": 0
        }
        
        # Collect video information
        for video_file in self.video_dir.glob("*.mp4"):
            metadata_file = self.data_dir / f"{video_file.stem}_metadata.json"
            
            if metadata_file.exists():
                async with aiofiles.open(metadata_file, 'r') as f:
                    metadata = json.loads(await f.read())
                
                video_size_mb = video_file.stat().st_size / (1024 * 1024)
                metadata["size_mb"] = round(video_size_mb, 2)
                report["videos"].append(metadata)
                report["total_size_mb"] += video_size_mb
        
        # Collect dataset information
        for dataset_dir in self.data_dir.glob("*_dataset"):
            metadata_file = dataset_dir / "fixture_metadata.json"
            
            if metadata_file.exists():
                async with aiofiles.open(metadata_file, 'r') as f:
                    metadata = json.loads(await f.read())
                report["datasets"].append(metadata)
        
        report["total_size_mb"] = round(report["total_size_mb"], 2)
        
        # Save summary report
        summary_path = self.output_dir / "test_data_summary.json"
        async with aiofiles.open(summary_path, 'w') as f:
            await f.write(json.dumps(report, indent=2))
        
        self.logger.info(f"Test data summary saved to {summary_path}")

# CLI script for pipeline execution
async def main():
    """Main pipeline execution function."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    pipeline = TestDataPipeline()
    await pipeline.generate_all_test_data()

if __name__ == "__main__":
    asyncio.run(main())
```

## Test Data Lifecycle Management

### Data Versioning and Migration

```python
# tests/utils/data_versioning.py

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import hashlib

@dataclass
class DataVersion:
    """Test data version information."""
    version: str
    created_at: str
    description: str
    checksum: str
    files: List[str]

class TestDataVersionManager:
    """Manage test data versions and migrations."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.versions_dir = data_dir / ".versions"
        self.versions_dir.mkdir(exist_ok=True)
        self.current_version = self._get_current_version()
    
    def _calculate_directory_checksum(self, directory: Path) -> str:
        """Calculate checksum for directory contents."""
        md5_hash = hashlib.md5()
        
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith('.'):
                with open(file_path, 'rb') as f:
                    md5_hash.update(f.read())
        
        return md5_hash.hexdigest()
    
    def _get_current_version(self) -> str:
        """Get current data version."""
        version_file = self.versions_dir / "current_version.txt"
        
        if version_file.exists():
            return version_file.read_text().strip()
        else:
            return "1.0.0"
    
    def create_version(self, version: str, description: str):
        """Create new version of test data."""
        version_dir = self.versions_dir / version
        version_dir.mkdir(exist_ok=True)
        
        # Copy current data to version directory
        for item in self.data_dir.iterdir():
            if item.name != ".versions":
                if item.is_dir():
                    shutil.copytree(item, version_dir / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, version_dir / item.name)
        
        # Create version metadata
        checksum = self._calculate_directory_checksum(version_dir)
        files = [str(p.relative_to(version_dir)) for p in version_dir.rglob("*") if p.is_file()]
        
        version_info = DataVersion(
            version=version,
            created_at=datetime.now().isoformat(),
            description=description,
            checksum=checksum,
            files=files
        )
        
        # Save version info
        version_info_file = self.versions_dir / f"{version}.json"
        with open(version_info_file, 'w') as f:
            json.dump(version_info.__dict__, f, indent=2)
        
        # Update current version
        current_version_file = self.versions_dir / "current_version.txt"
        current_version_file.write_text(version)
        
        self.current_version = version
        print(f"Created test data version {version}")
    
    def restore_version(self, version: str):
        """Restore specific version of test data."""
        version_dir = self.versions_dir / version
        
        if not version_dir.exists():
            raise ValueError(f"Version {version} does not exist")
        
        # Backup current data
        backup_dir = self.versions_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir()
        
        for item in self.data_dir.iterdir():
            if item.name != ".versions":
                if item.is_dir():
                    shutil.move(str(item), str(backup_dir / item.name))
                else:
                    shutil.move(str(item), str(backup_dir / item.name))
        
        # Restore version data
        for item in version_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, self.data_dir / item.name)
            else:
                shutil.copy2(item, self.data_dir / item.name)
        
        # Update current version
        current_version_file = self.versions_dir / "current_version.txt"
        current_version_file.write_text(version)
        
        self.current_version = version
        print(f"Restored test data to version {version}")
    
    def list_versions(self) -> List[DataVersion]:
        """List all available versions."""
        versions = []
        
        for version_file in self.versions_dir.glob("*.json"):
            with open(version_file, 'r') as f:
                version_data = json.load(f)
                versions.append(DataVersion(**version_data))
        
        return sorted(versions, key=lambda v: v.created_at, reverse=True)
    
    def cleanup_old_versions(self, keep_count: int = 5):
        """Clean up old versions, keeping only the most recent ones."""
        versions = self.list_versions()
        
        if len(versions) > keep_count:
            versions_to_remove = versions[keep_count:]
            
            for version in versions_to_remove:
                version_dir = self.versions_dir / version.version
                version_info_file = self.versions_dir / f"{version.version}.json"
                
                if version_dir.exists():
                    shutil.rmtree(version_dir)
                
                if version_info_file.exists():
                    version_info_file.unlink()
                
                print(f"Removed old version {version.version}")
```

This comprehensive test data management strategy ensures reliable, consistent, and scalable test data for the AI Model Validation Platform across all testing phases and environments.