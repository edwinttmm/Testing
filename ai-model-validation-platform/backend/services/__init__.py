"""
Services Package for AI Model Validation Platform

This package contains all service modules for the precision timing system
and HIL validation capabilities.
"""

# Import all timing services for easier access
from .precision_timing_service import (
    PrecisionTimingService,
    get_precision_timing_service,
    create_sync_point,
    measure_latency,
    get_monotonic_timestamp,
    validate_hil_timing_accuracy,
    HIL_TIMING_PRECISION_MS
)

from .video_timing_service import (
    VideoTimingService,
    get_video_timing_service
)

from .timing_validation_service import (
    TimingValidationService,
    get_timing_validation_service
)

from .frame_seeking_service import (
    FrameSeekingService,
    get_frame_seeking_service,
    seek_to_frame,
    seek_to_timestamp,
    preload_video_frames
)

__all__ = [
    'PrecisionTimingService',
    'get_precision_timing_service',
    'VideoTimingService', 
    'get_video_timing_service',
    'TimingValidationService',
    'get_timing_validation_service',
    'FrameSeekingService',
    'get_frame_seeking_service',
    'create_sync_point',
    'measure_latency',
    'get_monotonic_timestamp',
    'validate_hil_timing_accuracy',
    'validate_session_timing',
    'generate_timing_report',
    'seek_to_frame',
    'seek_to_timestamp',
    'preload_video_frames',
    'HIL_TIMING_PRECISION_MS'
]