"""
Inference module for ML pipeline
"""

from .yolo_service import yolo_service, YOLODetectionService, Detection

__all__ = [
    "yolo_service",
    "YOLODetectionService", 
    "Detection"
]