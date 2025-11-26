"""
Prometheus Metrics for HIL Detection Pipeline

This module defines Prometheus metrics for monitoring the HIL detection pipeline,
including detection events, WebSocket emissions, queue operations, and performance.
"""

from prometheus_client import Counter, Histogram, Gauge

# Detection Pipeline Metrics
detections_total = Counter(
    'hil_detections_total',
    'Total detection events recorded',
    ['session_id', 'video_id', 'channel']
)

websocket_emissions = Counter(
    'hil_websocket_emissions_total',
    'Total WebSocket emissions sent',
    ['session_id', 'success']
)

queue_flushes = Counter(
    'hil_queue_flush_total',
    'Total queue flush operations',
    ['session_id', 'video_id', 'events_count']
)

detection_latency = Histogram(
    'hil_detection_latency_ms',
    'Detection processing latency in milliseconds',
    buckets=[10, 50, 100, 200, 500, 1000, 2000]
)

null_video_id_rate = Gauge(
    'hil_null_video_id_rate',
    'Percentage of detections with NULL video_id'
)

labjack_connection = Gauge(
    'hil_labjack_connection_status',
    'LabJack connection status (1=connected, 0=disconnected)'
)

# Queue Processing Metrics
queue_size = Gauge(
    'hil_queue_size',
    'Current number of events in detection queue',
    ['session_id']
)

queue_processing_time = Histogram(
    'hil_queue_processing_time_ms',
    'Time to process queue flush operations',
    buckets=[10, 50, 100, 250, 500, 1000]
)

# Video Lifecycle Metrics
video_starts = Counter(
    'hil_video_starts_total',
    'Total video start events',
    ['session_id', 'video_id']
)

video_ends = Counter(
    'hil_video_ends_total',
    'Total video end events',
    ['session_id', 'video_id']
)

# Timing Synchronization Metrics
timing_sync_quality = Gauge(
    'hil_timing_sync_quality',
    'Timing synchronization quality (0-1)',
    ['session_id', 'video_id']
)

calibration_offset = Gauge(
    'hil_calibration_offset_ms',
    'Timing calibration offset in milliseconds',
    ['session_id']
)

# Database Metrics
db_storage_success = Counter(
    'hil_db_storage_success_total',
    'Successful database storage operations',
    ['session_id']
)

db_storage_failures = Counter(
    'hil_db_storage_failures_total',
    'Failed database storage operations',
    ['session_id', 'error_type']
)

# Window Validation Metrics
window_validation_skipped_early = Counter(
    'hil_window_validation_skipped_early_total',
    'Detections skipped (too early)',
    ['session_id']
)

window_validation_skipped_late = Counter(
    'hil_window_validation_skipped_late_total',
    'Detections skipped (too late)',
    ['session_id']
)

window_validation_accepted = Counter(
    'hil_window_validation_accepted_total',
    'Detections accepted within valid window',
    ['session_id']
)
