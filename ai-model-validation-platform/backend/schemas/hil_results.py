"""
Enhanced HIL Results Schemas - API Schema Standardization
Eliminates snake_case/camelCase duplication, standardizes on camelCase for all JSON responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from schemas import CamelCaseModel


class GroundTruthComparison(CamelCaseModel):
    """Ground truth comparison metrics - camelCase only"""
    true_positives: int = Field(alias='truePositives')
    false_positives: int = Field(alias='falsePositives')
    false_negatives: int = Field(alias='falseNegatives')
    precision: float
    recall: float
    f1_score: float = Field(alias='f1Score')
    total_ground_truth: Optional[int] = Field(None, alias='totalGroundTruth')
    average_confidence: Optional[float] = Field(None, alias='averageConfidence')


class DetectionEventSchema(CamelCaseModel):
    """Detection event schema - camelCase only"""
    id: str
    timestamp: float
    video_relative_timestamp: Optional[float] = Field(None, alias='videoRelativeTimestamp')
    latency_ms: Optional[float] = Field(None, alias='latencyMs')
    classification: Optional[str]
    voltage: float
    screenshot_url: Optional[str] = Field(None, alias='screenshotUrl')
    frame_number: Optional[int] = Field(None, alias='frameNumber')
    video_id: Optional[str] = Field(None, alias='videoId')
    validation_result: Optional[str] = Field(None, alias='validationResult')


class PerVideoResult(CamelCaseModel):
    """Per-video results - camelCase only"""
    video_id: str = Field(alias='videoId')
    position: int
    detection_count: int = Field(alias='detectionCount')
    ground_truth_comparison: GroundTruthComparison = Field(alias='groundTruthComparison')
    mean_latency_ms: Optional[float] = Field(None, alias='meanLatencyMs')
    video_name: Optional[str] = Field(None, alias='videoName')
    duration: Optional[float] = None
    status: Optional[str] = None


class EnhancedHILResultsResponse(CamelCaseModel):
    """
    Enhanced HIL results response with ONLY camelCase fields.
    No snake_case duplication.
    """
    session_id: str = Field(alias='sessionId')
    status: str
    outcome: Optional[str] = None  # NEW: 'PASS', 'CONDITIONAL_PASS', 'FAIL'
    outcome_reasons: Optional[List[str]] = Field(None, alias='outcomeReasons')  # NEW
    approval_status: Optional[str] = Field(None, alias='approvalStatus')  # NEW
    approved_by: Optional[str] = Field(None, alias='approvedBy')  # NEW
    approved_at: Optional[datetime] = Field(None, alias='approvedAt')  # NEW

    # Ground truth comparison (aggregated)
    ground_truth_comparison: GroundTruthComparison = Field(alias='groundTruthComparison')

    # Detection events
    detection_events: List[DetectionEventSchema] = Field(alias='detectionEvents')

    # Per-video results (for multi-video sessions)
    per_video_results: Optional[List[PerVideoResult]] = Field(None, alias='perVideoResults')

    # Session metadata
    project_name: Optional[str] = Field(None, alias='projectName')
    video_filename: Optional[str] = Field(None, alias='videoFilename')
    started_at: Optional[datetime] = Field(None, alias='startedAt')
    completed_at: Optional[datetime] = Field(None, alias='completedAt')

    # Test configuration
    has_video_sequence: bool = Field(alias='hasVideoSequence')
    total_videos: Optional[int] = Field(None, alias='totalVideos')


class ApprovalRequest(CamelCaseModel):
    """Request to approve/reject test results"""
    approver_id: str = Field(alias='approverId')
    comments: Optional[str] = None
    action: str  # 'approve' or 'reject'
    rejection_reason: Optional[str] = Field(None, alias='rejectionReason')


class ApprovalResponse(CamelCaseModel):
    """Response after approval/rejection"""
    session_id: str = Field(alias='sessionId')
    approval_status: str = Field(alias='approvalStatus')
    approved_by: str = Field(alias='approvedBy')
    approved_at: datetime = Field(alias='approvedAt')
    comments: Optional[str] = None
