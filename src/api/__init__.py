"""
API modules for VRU Detection System
"""

from .project_router import router as project_router
from .video_router import router as video_router
from .detection_router import router as detection_router
from .signal_router import router as signal_router
from .validation_router import router as validation_router
from .health_router import router as health_router

__all__ = [
    "project_router",
    "video_router", 
    "detection_router",
    "signal_router",
    "validation_router",
    "health_router"
]