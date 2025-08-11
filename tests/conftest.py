"""
Global pytest configuration for Hive Mind testing framework.
Provides shared fixtures, test data, and common utilities.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import numpy as np
import cv2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import redis
from typing import Generator, Dict, Any
import json
import websocket
import threading
import time

# Test configuration
TEST_DATABASE_URL = "sqlite:///./test_hive_mind.db"
TEST_REDIS_URL = "redis://localhost:6379/1"
TEST_VIDEO_DIR = Path("tests/fixtures/videos")
TEST_IMAGES_DIR = Path("tests/fixtures/images")

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()

@pytest.fixture
def test_db_session(test_db_engine):
    """Create test database session."""
    TestSessionLocal = sessionmaker(bind=test_db_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.exists.return_value = False
    return redis_mock

@pytest.fixture
def test_video_path():
    """Provide path to test video file."""
    video_dir = TEST_VIDEO_DIR
    video_dir.mkdir(parents=True, exist_ok=True)
    
    # Create synthetic test video
    video_path = video_dir / "test_video.mp4"
    if not video_path.exists():
        create_test_video(video_path)
    
    return str(video_path)

@pytest.fixture
def test_image_path():
    """Provide path to test image file."""
    image_dir = TEST_IMAGES_DIR
    image_dir.mkdir(parents=True, exist_ok=True)
    
    # Create synthetic test image
    image_path = image_dir / "test_image.jpg"
    if not image_path.exists():
        create_test_image(image_path)
    
    return str(image_path)

@pytest.fixture
def mock_yolo_model():
    """Mock YOLO model for testing."""
    model = MagicMock()
    model.predict.return_value = [
        MagicMock(
            boxes=MagicMock(
                xyxy=np.array([[100, 100, 200, 200]]),
                conf=np.array([0.85]),
                cls=np.array([0])  # person class
            ),
            names={0: 'person', 1: 'bicycle', 2: 'car'}
        )
    ]
    return model

@pytest.fixture
def mock_raspberry_pi():
    """Mock Raspberry Pi interface."""
    pi_mock = MagicMock()
    pi_mock.capture_frame.return_value = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    pi_mock.is_connected.return_value = True
    pi_mock.get_status.return_value = {
        'temperature': 45.2,
        'cpu_usage': 25.6,
        'memory_usage': 512,
        'disk_usage': 75.3
    }
    return pi_mock

@pytest.fixture
def sample_ground_truth_data():
    """Sample ground truth data for testing."""
    return {
        "video_id": "test_video_001",
        "timestamp": "2024-01-15T10:30:00Z",
        "detections": [
            {
                "bbox": [100, 100, 200, 200],
                "class": "person",
                "confidence": 0.95,
                "track_id": 1
            },
            {
                "bbox": [300, 150, 400, 250],
                "class": "bicycle",
                "confidence": 0.87,
                "track_id": 2
            }
        ],
        "metadata": {
            "weather": "sunny",
            "time_of_day": "morning",
            "location": "intersection_001"
        }
    }

@pytest.fixture
def websocket_test_client():
    """WebSocket test client for real-time testing."""
    class WebSocketTestClient:
        def __init__(self):
            self.ws = None
            self.messages = []
            self.connected = False
            
        def connect(self, uri):
            def on_message(ws, message):
                self.messages.append(json.loads(message))
                
            def on_open(ws):
                self.connected = True
                
            def on_close(ws, close_status_code, close_msg):
                self.connected = False
                
            self.ws = websocket.WebSocketApp(
                uri,
                on_message=on_message,
                on_open=on_open,
                on_close=on_close
            )
            
            # Run in separate thread
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()
            
            # Wait for connection
            timeout = 5
            while not self.connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1
                
        def send(self, message):
            if self.ws and self.connected:
                self.ws.send(json.dumps(message))
                
        def get_messages(self):
            return self.messages.copy()
            
        def clear_messages(self):
            self.messages.clear()
            
        def close(self):
            if self.ws:
                self.ws.close()
                self.connected = False
    
    return WebSocketTestClient()

@pytest.fixture
def performance_monitor():
    """Performance monitoring utilities."""
    class PerformanceMonitor:
        def __init__(self):
            self.metrics = {}
            self.start_time = None
            
        def start_timer(self, name):
            self.start_time = time.perf_counter()
            
        def end_timer(self, name):
            if self.start_time:
                duration = time.perf_counter() - self.start_time
                self.metrics[name] = duration
                self.start_time = None
                return duration
            return None
            
        def memory_usage(self):
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
            
        def cpu_usage(self):
            import psutil
            return psutil.cpu_percent(interval=1)
            
        def get_metrics(self):
            return self.metrics.copy()
            
        def reset(self):
            self.metrics.clear()
    
    return PerformanceMonitor()

def create_test_video(output_path: Path, duration: int = 5, fps: int = 30):
    """Create synthetic test video with moving objects."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    height, width = 480, 640
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    
    total_frames = duration * fps
    for frame_idx in range(total_frames):
        # Create blank frame
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add moving rectangle (simulating person)
        x = int((frame_idx / total_frames) * (width - 100))
        cv2.rectangle(frame, (x, 200), (x + 50, 300), (0, 255, 0), -1)
        
        # Add static rectangle (simulating car)
        cv2.rectangle(frame, (400, 300), (500, 400), (255, 0, 0), -1)
        
        out.write(frame)
    
    out.release()

def create_test_image(output_path: Path):
    """Create synthetic test image with objects."""
    height, width = 480, 640
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Add person-like rectangle
    cv2.rectangle(image, (100, 100), (200, 300), (0, 255, 0), -1)
    
    # Add car-like rectangle
    cv2.rectangle(image, (300, 250), (450, 350), (255, 0, 0), -1)
    
    cv2.imwrite(str(output_path), image)

# Test markers for categorization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.performance = pytest.mark.performance
pytest.mark.slow = pytest.mark.slow
pytest.mark.hardware = pytest.mark.hardware