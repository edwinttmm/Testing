"""
Test Data Fixtures for Recall and Constant Voltage Mode Tests

Provides reusable mock data for testing both fixes.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any


# Session fa204ef2 Real Data
SESSION_FA204EF2_DATA = {
    "session_id": "fa204ef2-9d8b-4480-9692-86e338c1218a",
    "total_tp": 87,
    "total_fp": 33,
    "total_fn": 155,
    "total_gt": 242,
    "actual_recall": 0.3595,  # 35.95%
    "displayed_recall_bug": 1.0,  # 100% (BUG!)
    "videos": [
        {
            "video_id": "video-1",
            "tp": 10,
            "fp": 2,
            "fn": 0,
            "gt": 10,
            "recall": 1.0  # 100%
        },
        {
            "video_id": "video-2",
            "tp": 77,
            "fp": 31,
            "fn": 155,
            "gt": 232,
            "recall": 0.332  # 33.2%
        }
    ]
}


# Constant Voltage Detection Data
CONSTANT_VOLTAGE_SCENARIO = {
    "voltage": 4.2,  # Constant voltage
    "threshold": 3.0,
    "sample_rate": 1000,  # 1 kHz
    "fps": 24,
    "frame_duration_ms": 41.67,  # 1000 / 24
    "debounce_ms": 100,
    "before_fix": {
        "total_frames": 122,
        "detected_frames": 98,
        "detection_rate": 0.803  # 80.3%
    },
    "after_fix": {
        "total_frames": 122,
        "detected_frames": 122,
        "detection_rate": 1.0  # 100%
    }
}


# Frame Gap Pattern (User Reported)
FRAME_GAP_PATTERN = {
    "description": "Frame detection pattern with 100ms debounce at 24 FPS",
    "frame_duration_ms": 41.67,
    "debounce_ms": 100,
    "frames": [
        {"frame": 99, "timestamp_ms": 4125.00, "detected": True},
        {"frame": 100, "timestamp_ms": 4166.67, "detected": False},  # Blocked
        {"frame": 101, "timestamp_ms": 4208.34, "detected": False},  # Blocked
        {"frame": 102, "timestamp_ms": 4250.01, "detected": True},   # > 100ms
        {"frame": 103, "timestamp_ms": 4291.68, "detected": False},  # Blocked
        {"frame": 104, "timestamp_ms": 4333.35, "detected": True},   # > 100ms
        {"frame": 105, "timestamp_ms": 4375.02, "detected": False}   # Blocked
    ]
}


# Multi-Video Test Scenario
MULTI_VIDEO_TEST_SCENARIO = {
    "session_id": "multi-video-test-session",
    "videos": [
        {
            "video_id": "v1",
            "duration_seconds": 1.0,
            "fps": 24,
            "frames": 24,
            "gt_count": 10,
            "tp_count": 10,
            "fp_count": 2,
            "fn_count": 0,
            "recall": 1.0,
            "precision": 0.833
        },
        {
            "video_id": "v2",
            "duration_seconds": 5.0,
            "fps": 24,
            "frames": 120,
            "gt_count": 232,
            "tp_count": 77,
            "fp_count": 31,
            "fn_count": 155,
            "recall": 0.332,
            "precision": 0.713
        }
    ],
    "session_aggregate": {
        "total_frames": 144,
        "total_gt": 242,
        "total_tp": 87,
        "total_fp": 33,
        "total_fn": 155,
        "session_recall": 0.3595,  # 35.95% (NOT 100%!)
        "session_precision": 0.725  # 72.5%
    }
}


# Large Session Stress Test Data
LARGE_SESSION_STRESS_DATA = {
    "num_videos": 10,
    "fps": 24,
    "duration_per_video": 10.0,  # seconds
    "frames_per_video": 240,
    "total_frames": 2400,
    "sample_rate": 1000,
    "constant_voltage": 4.2,
    "threshold": 3.0
}


# High Frequency Sampling Data
HIGH_FREQUENCY_DATA = {
    "sample_rate": 10000,  # 10 kHz
    "duration_seconds": 1.0,
    "expected_samples": 10000,
    "constant_voltage": 4.2,
    "threshold": 3.0
}


# API Response Structure
API_RESPONSE_TEMPLATE = {
    "sessionId": "test-session",
    "sessionMetrics": {
        "recall": 36.0,  # Session-wide recall (CORRECT)
        "precision": 72.5,
        "f1Score": 48.1,
        "accuracy": 65.3,
        "totalDetections": 120,
        "truePositives": 87,
        "falsePositives": 33,
        "totalGroundTruth": 242,
        "falseNegatives": 155
    },
    "perVideoMetrics": [
        {
            "videoId": "video-1",
            "recall": 100.0,  # Per-video recall
            "precision": 83.3,
            "f1Score": 90.9,
            "truePositives": 10,
            "falsePositives": 2,
            "groundTruth": 10,
            "falseNegatives": 0
        },
        {
            "videoId": "video-2",
            "recall": 33.2,
            "precision": 71.3,
            "f1Score": 45.3,
            "truePositives": 77,
            "falsePositives": 31,
            "groundTruth": 232,
            "falseNegatives": 155
        }
    ],
    "detectionConfiguration": {
        "constantVoltageModeEnabled": True,
        "debounceMs": 100,
        "debounceBypassed": True,
        "sampleRate": 1000,
        "voltageThreshold": 3.0
    }
}


# Mock LabJack Data
MOCK_LABJACK_DATA = {
    "device_type": "T7",
    "channels": ["AIN0", "AIN1"],
    "constant_voltage_readings": [
        {"timestamp": "2025-11-24T10:00:00.000Z", "channel": "AIN0", "voltage": 4.2},
        {"timestamp": "2025-11-24T10:00:00.042Z", "channel": "AIN0", "voltage": 4.2},
        {"timestamp": "2025-11-24T10:00:00.083Z", "channel": "AIN0", "voltage": 4.2},
        {"timestamp": "2025-11-24T10:00:00.125Z", "channel": "AIN0", "voltage": 4.2},
        {"timestamp": "2025-11-24T10:00:00.167Z", "channel": "AIN0", "voltage": 4.2}
    ],
    "variable_voltage_readings": [
        {"timestamp": "2025-11-24T10:00:00.000Z", "channel": "AIN0", "voltage": 0.5},
        {"timestamp": "2025-11-24T10:00:00.042Z", "channel": "AIN0", "voltage": 4.5},
        {"timestamp": "2025-11-24T10:00:00.083Z", "channel": "AIN0", "voltage": 0.3},
        {"timestamp": "2025-11-24T10:00:00.125Z", "channel": "AIN0", "voltage": 4.3},
        {"timestamp": "2025-11-24T10:00:00.167Z", "channel": "AIN0", "voltage": 0.2}
    ]
}


def generate_constant_voltage_detections(
    duration_seconds: float,
    fps: int,
    voltage: float = 4.2,
    threshold: float = 3.0,
    constant_voltage_mode: bool = False,
    debounce_ms: int = 100
) -> List[Dict[str, Any]]:
    """
    Generate mock detection events for constant voltage scenario

    Args:
        duration_seconds: Duration to simulate
        fps: Frames per second
        voltage: Constant voltage value
        threshold: Detection threshold
        constant_voltage_mode: Enable constant voltage mode (bypass debounce)
        debounce_ms: Debounce period in milliseconds

    Returns:
        List of detection events
    """
    frame_duration_ms = 1000 / fps
    total_frames = int(duration_seconds * fps)
    detections = []
    last_detection_time = None

    for frame in range(total_frames):
        frame_time = frame * frame_duration_ms

        # Check if voltage exceeds threshold
        if voltage > threshold:
            # Apply debounce logic
            if constant_voltage_mode:
                # Bypass debounce - detect every frame
                detected = True
            else:
                # Normal mode - apply debounce
                if last_detection_time is None or (frame_time - last_detection_time) >= debounce_ms:
                    detected = True
                    last_detection_time = frame_time
                else:
                    detected = False

            if detected:
                detections.append({
                    "frame": frame,
                    "timestamp_ms": frame_time,
                    "voltage": voltage,
                    "threshold": threshold,
                    "detected": True,
                    "constant_voltage_mode": constant_voltage_mode
                })

    return detections


def generate_multi_video_ground_truth(
    num_videos: int,
    frames_per_video: int,
    gt_density: float = 0.5
) -> Dict[str, Any]:
    """
    Generate mock ground truth data for multi-video session

    Args:
        num_videos: Number of videos
        frames_per_video: Frames per video
        gt_density: Ground truth event density (0.0-1.0)

    Returns:
        Dictionary with video ground truth data
    """
    videos = []

    for video_idx in range(num_videos):
        video_id = f"video-{video_idx + 1}"
        gt_count = int(frames_per_video * gt_density)

        videos.append({
            "video_id": video_id,
            "frames": frames_per_video,
            "gt_count": gt_count,
            "gt_events": [
                {
                    "frame": frame,
                    "timestamp_ms": frame * (1000 / 24),
                    "object_type": "pedestrian"
                }
                for frame in range(0, frames_per_video, int(1 / gt_density))
            ][:gt_count]
        })

    return {
        "session_id": f"multi-video-{num_videos}",
        "num_videos": num_videos,
        "videos": videos,
        "total_gt": sum(v["gt_count"] for v in videos)
    }


# Export all fixtures
__all__ = [
    'SESSION_FA204EF2_DATA',
    'CONSTANT_VOLTAGE_SCENARIO',
    'FRAME_GAP_PATTERN',
    'MULTI_VIDEO_TEST_SCENARIO',
    'LARGE_SESSION_STRESS_DATA',
    'HIGH_FREQUENCY_DATA',
    'API_RESPONSE_TEMPLATE',
    'MOCK_LABJACK_DATA',
    'generate_constant_voltage_detections',
    'generate_multi_video_ground_truth'
]
