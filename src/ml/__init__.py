"""
ML Pipeline for VRU (Vulnerable Road User) Detection

This package provides a comprehensive machine learning pipeline for detecting
and tracking vulnerable road users including:
- Pedestrians
- Cyclists  
- Motorcyclists
- Wheelchairs
- Scooters

Architecture:
- YOLOv8-based detection
- Temporal tracking with Kalman filters
- Performance optimization for <50ms inference
- GPU acceleration with CPU fallback
- Real-time monitoring and metrics
"""

from .inference.yolo_service import YOLODetectionService
from .models.model_manager import ModelManager
from .api.ml_endpoints import MLRouter
from .monitoring.performance_monitor import PerformanceMonitor

__version__ = "1.0.0"

__all__ = [
    "YOLODetectionService",
    "ModelManager", 
    "MLRouter",
    "PerformanceMonitor"
]