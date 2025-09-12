# Complete PRD Schemas - All missing schemas for 100% compliance

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Video Library Management Schemas - PRD Module 1.4
class VideoLibraryStats(BaseModel):
    total_videos: int
    pending_annotation: int
    pending_validation: int
    validated: int
    processing: int
    error: int

class VideoStatusUpdate(BaseModel):
    status: str = Field(..., description="New video status")
    user_id: Optional[int] = Field(None, description="User making the change")

# Project Management Schemas - PRD Module 2.1
class ProjectDeletionResponse(BaseModel):
    success: bool
    message: str
    deleted_project_id: int
    deleted_at: str

class ProjectVideoListResponse(BaseModel):
    project_id: int
    project_name: str
    total_videos: int
    videos: List[Dict[str, Any]]

class VideoAssignmentRequest(BaseModel):
    video_ids: List[int]
    sequence_order: Optional[List[int]] = None

# HIL Test Execution Schemas - PRD Module 3.1 & 3.2
class HILTestStatusResponse(BaseModel):
    session_id: int
    status: str
    current_video_index: int = 0
    total_videos: int = 0
    processed_events: int = 0
    total_expected_events: int = 0
    labjack_connected: bool
    elapsed_time_ms: float
    current_performance: Dict[str, Any]

class PrecisionTimingEvent(BaseModel):
    ground_truth_object_id: int
    expected_event_time: datetime
    signal_received_time: Optional[datetime] = None
    signal_type: str = "ttl"
    signal_value: Optional[float] = None
    labjack_channel: Optional[str] = None
    signal_voltage: Optional[float] = None

# Automated Analysis Schemas - PRD Module 4.1
class TestSessionAnalysis(BaseModel):
    session_id: int
    analysis_timestamp: str
    total_events: int
    passed_events: int
    failed_events: int
    pass_rate: float
    threshold_ms: int
    latency_distribution: Optional[Dict[str, Any]] = None
    temporal_patterns: Optional[Dict[str, Any]] = None
    failure_classification: Optional[Dict[str, Any]] = None
    performance_trends: Optional[Dict[str, Any]] = None
    statistical_validation: Optional[Dict[str, Any]] = None

class PerformanceMetrics(BaseModel):
    mean_latency_ms: float
    median_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    std_deviation: float
    coefficient_of_variation: float

class LatencyAnalysis(BaseModel):
    distribution_type: str
    performance_metrics: PerformanceMetrics
    outlier_count: int
    stability_score: float

class OutcomeClassification(BaseModel):
    pass_count: int
    fail_high_latency_count: int
    fail_missed_detection_count: int
    hardware_failure_count: int
    systematic_failure_count: int
    intermittent_failure_count: int

class FailureAnalysis(BaseModel):
    critical_failures: int
    high_severity_failures: int
    medium_severity_failures: int
    low_severity_failures: int
    failure_patterns: List[str]
    recommended_actions: List[str]

class TestReportSummary(BaseModel):
    session_id: int
    project_id: int
    test_date: datetime
    duration_minutes: float
    total_events: int
    passed_events: int
    failed_events: int
    pass_rate: float
    average_latency_ms: float
    max_latency_threshold: int
    performance_summary: Dict[str, Any]
    failure_analysis: Dict[str, Any]
    recommendations: List[str]
    detailed_analysis: Dict[str, Any]

# Enhanced Test Configuration Schemas
class FullScreenTestConfig(BaseModel):
    auto_switch: bool = True
    switch_delay_ms: int = 100
    exit_on_completion: bool = True

class LabjackConnectionConfig(BaseModel):
    device_type: str = "U6"
    connection_type: str = "USB"
    mock_mode: bool = False
    timeout_seconds: int = 30

class TestExecutionConfig(BaseModel):
    max_latency_ms: int = Field(..., ge=1, le=10000)
    precision_timing: bool = True
    fullscreen_config: FullScreenTestConfig
    labjack_config: LabjackConnectionConfig
    auto_analysis: bool = True