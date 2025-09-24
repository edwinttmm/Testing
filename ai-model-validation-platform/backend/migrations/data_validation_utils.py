"""
Data Validation Utilities for HIL Ground Truth Timing System
============================================================

Comprehensive validation utilities for timing data, ground truth matching,
and database integrity checks for the HIL system.

Author: AI Backend Developer
Created: 2025-09-16
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

class ValidationSeverity(Enum):
    """Validation issue severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationIssue:
    """Represents a validation issue found during checks"""
    severity: ValidationSeverity
    category: str
    message: str
    details: Optional[Dict[str, Any]] = None
    suggested_fix: Optional[str] = None

class TimingValidator:
    """Validator for timing-related data"""
    
    def __init__(self, tolerance_ms: int = 100):
        self.tolerance_ms = tolerance_ms
        self.issues: List[ValidationIssue] = []
    
    def validate_video_timing(self, 
                            video_duration: float, 
                            fps: float, 
                            playback_start_time: Optional[float] = None,
                            playback_duration: Optional[float] = None) -> List[ValidationIssue]:
        """Validate video timing parameters"""
        issues = []
        
        # Validate video duration
        if video_duration <= 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="video_timing",
                message="Video duration must be positive",
                details={"video_duration": video_duration},
                suggested_fix="Check video file metadata and ensure duration is correctly extracted"
            ))
        elif video_duration > 7200:  # 2 hours
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="video_timing",
                message="Video duration is unusually long",
                details={"video_duration": video_duration},
                suggested_fix="Verify this is intentional for HIL testing"
            ))
        
        # Validate FPS
        if fps <= 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="video_timing",
                message="FPS must be positive",
                details={"fps": fps},
                suggested_fix="Check video file metadata and ensure FPS is correctly extracted"
            ))
        elif fps < 15:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="video_timing",
                message="Low FPS may affect timing accuracy",
                details={"fps": fps},
                suggested_fix="Consider using higher FPS videos for better timing precision"
            ))
        elif fps > 120:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="video_timing",
                message="Very high FPS detected",
                details={"fps": fps},
                suggested_fix="Verify FPS is correct and system can handle high frame rates"
            ))
        
        # Validate playback timing if provided
        if playback_start_time is not None:
            if playback_start_time < 946684800:  # Year 2000 timestamp
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="video_timing",
                    message="Playback start time seems too early",
                    details={"playback_start_time": playback_start_time},
                    suggested_fix="Verify timestamp is in Unix epoch format"
                ))
            
            future_threshold = datetime.now().timestamp() + 86400  # 24 hours in future
            if playback_start_time > future_threshold:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="video_timing",
                    message="Playback start time is in the future",
                    details={"playback_start_time": playback_start_time},
                    suggested_fix="Check system clock and timestamp generation"
                ))
        
        if playback_duration is not None:
            if playback_duration <= 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="video_timing",
                    message="Playback duration must be positive",
                    details={"playback_duration": playback_duration}
                ))
            elif abs(playback_duration - video_duration) > 5.0:  # 5 second tolerance
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="video_timing",
                    message="Playback duration differs significantly from video duration",
                    details={
                        "playback_duration": playback_duration,
                        "video_duration": video_duration,
                        "difference": abs(playback_duration - video_duration)
                    },
                    suggested_fix="Check if partial playback is intentional"
                ))
        
        return issues
    
    def validate_timestamp_alignment(self, 
                                   unix_timestamp: float,
                                   video_relative_timestamp: Optional[float],
                                   video_start_time: Optional[float]) -> List[ValidationIssue]:
        """Validate alignment between Unix and video-relative timestamps"""
        issues = []
        
        if video_relative_timestamp is not None and video_start_time is not None:
            expected_unix = video_start_time + video_relative_timestamp
            timestamp_diff = abs(unix_timestamp - expected_unix)
            
            if timestamp_diff > 1.0:  # 1 second tolerance
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="timestamp_alignment",
                    message="Unix and video-relative timestamps are misaligned",
                    details={
                        "unix_timestamp": unix_timestamp,
                        "video_relative_timestamp": video_relative_timestamp,
                        "video_start_time": video_start_time,
                        "expected_unix": expected_unix,
                        "difference_seconds": timestamp_diff
                    },
                    suggested_fix="Recalculate timestamps or check timing synchronization"
                ))
            elif timestamp_diff > 0.1:  # 100ms tolerance
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="timestamp_alignment",
                    message="Minor timestamp misalignment detected",
                    details={
                        "difference_seconds": timestamp_diff
                    },
                    suggested_fix="Check timing precision and synchronization"
                ))
        
        # Validate video relative timestamp bounds
        if video_relative_timestamp is not None:
            if video_relative_timestamp < 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="timestamp_alignment",
                    message="Video relative timestamp cannot be negative",
                    details={"video_relative_timestamp": video_relative_timestamp}
                ))
        
        return issues
    
    def validate_latency_measurement(self, 
                                   latency_ms: float,
                                   tolerance_ms: Optional[int] = None) -> List[ValidationIssue]:
        """Validate latency measurements"""
        issues = []
        tolerance = tolerance_ms or self.tolerance_ms
        
        # Check latency bounds
        if latency_ms < -1000:  # More than 1 second early
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="latency_validation",
                message="Latency indicates detection occurred too early",
                details={"latency_ms": latency_ms},
                suggested_fix="Check timing synchronization and ground truth timestamps"
            ))
        elif latency_ms > 10000:  # More than 10 seconds late
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="latency_validation",
                message="Latency indicates detection occurred too late",
                details={"latency_ms": latency_ms},
                suggested_fix="Check detection system performance and timing"
            ))
        
        # Check tolerance compliance
        if abs(latency_ms) > tolerance:
            severity = ValidationSeverity.WARNING if abs(latency_ms) < tolerance * 2 else ValidationSeverity.ERROR
            issues.append(ValidationIssue(
                severity=severity,
                category="latency_validation",
                message="Latency exceeds tolerance threshold",
                details={
                    "latency_ms": latency_ms,
                    "tolerance_ms": tolerance,
                    "excess_ms": abs(latency_ms) - tolerance
                },
                suggested_fix="Optimize detection system or adjust tolerance"
            ))
        
        return issues

class GroundTruthValidator:
    """Validator for ground truth data"""
    
    def validate_bounding_box(self, bbox: Dict[str, float], 
                            image_width: Optional[int] = None,
                            image_height: Optional[int] = None) -> List[ValidationIssue]:
        """Validate bounding box coordinates"""
        issues = []
        
        required_keys = {'x', 'y', 'width', 'height'}
        if not all(key in bbox for key in required_keys):
            missing_keys = required_keys - set(bbox.keys())
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="bounding_box",
                message="Missing required bounding box coordinates",
                details={"missing_keys": list(missing_keys)},
                suggested_fix="Ensure all bounding box coordinates (x, y, width, height) are provided"
            ))
            return issues
        
        x, y, width, height = bbox['x'], bbox['y'], bbox['width'], bbox['height']
        
        # Validate positive dimensions
        if width <= 0 or height <= 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="bounding_box",
                message="Bounding box dimensions must be positive",
                details={"width": width, "height": height}
            ))
        
        # Validate coordinates
        if x < 0 or y < 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="bounding_box",
                message="Bounding box coordinates are negative",
                details={"x": x, "y": y},
                suggested_fix="Check if coordinates are relative or absolute"
            ))
        
        # Validate against image dimensions if provided
        if image_width and image_height:
            if x + width > image_width:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="bounding_box",
                    message="Bounding box extends beyond image width",
                    details={"bbox_right": x + width, "image_width": image_width}
                ))
            
            if y + height > image_height:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="bounding_box",
                    message="Bounding box extends beyond image height",
                    details={"bbox_bottom": y + height, "image_height": image_height}
                ))
        
        return issues
    
    def validate_confidence_score(self, confidence: float) -> List[ValidationIssue]:
        """Validate confidence scores"""
        issues = []
        
        if not 0.0 <= confidence <= 1.0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="confidence_validation",
                message="Confidence score must be between 0.0 and 1.0",
                details={"confidence": confidence}
            ))
        elif confidence < 0.1:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="confidence_validation",
                message="Very low confidence score",
                details={"confidence": confidence},
                suggested_fix="Consider filtering low-confidence detections"
            ))
        
        return issues

class DatabaseIntegrityValidator:
    """Validator for database integrity and relationships"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def validate_test_session_data(self, test_session_id: str) -> List[ValidationIssue]:
        """Validate test session data integrity"""
        issues = []
        
        # Check if test session exists
        test_session = self.session.execute(text("""
            SELECT ts.*, v.duration, v.fps, v.filename
            FROM test_sessions ts
            JOIN videos v ON ts.video_id = v.id
            WHERE ts.id = :session_id
        """), {"session_id": test_session_id}).fetchone()
        
        if not test_session:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="database_integrity",
                message="Test session not found",
                details={"test_session_id": test_session_id}
            ))
            return issues
        
        # Validate ground truth count
        if test_session.ground_truth_count is not None:
            actual_gt_count = self.session.execute(text("""
                SELECT COUNT(*) FROM ground_truth_objects 
                WHERE video_id = :video_id
            """), {"video_id": test_session.video_id}).fetchone()[0]
            
            if actual_gt_count != test_session.ground_truth_count:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="database_integrity",
                    message="Ground truth count mismatch",
                    details={
                        "recorded_count": test_session.ground_truth_count,
                        "actual_count": actual_gt_count
                    },
                    suggested_fix="Update ground_truth_count field or verify ground truth data"
                ))
        
        # Validate video playback duration
        if test_session.video_playback_duration is not None and test_session.duration is not None:
            duration_diff = abs(test_session.video_playback_duration - test_session.duration)
            if duration_diff > 5.0:  # 5 second tolerance
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="database_integrity",
                    message="Playback duration differs from video duration",
                    details={
                        "playback_duration": test_session.video_playback_duration,
                        "video_duration": test_session.duration,
                        "difference": duration_diff
                    }
                ))
        
        return issues
    
    def validate_detection_matching(self, test_session_id: str) -> List[ValidationIssue]:
        """Validate detection event matching integrity"""
        issues = []
        
        # Check for orphaned detection comparisons
        orphaned_comparisons = self.session.execute(text("""
            SELECT dc.id, dc.detection_event_id, dc.ground_truth_object_id
            FROM detection_comparisons dc
            LEFT JOIN detection_events de ON dc.detection_event_id = de.id
            LEFT JOIN ground_truth_objects gto ON dc.ground_truth_object_id = gto.id
            WHERE dc.test_session_id = :session_id
            AND (de.id IS NULL OR gto.id IS NULL)
        """), {"session_id": test_session_id}).fetchall()
        
        if orphaned_comparisons:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="database_integrity",
                message="Found orphaned detection comparisons",
                details={"orphaned_count": len(orphaned_comparisons)},
                suggested_fix="Clean up orphaned comparisons or restore missing references"
            ))
        
        # Check for inconsistent matching flags
        inconsistent_matches = self.session.execute(text("""
            SELECT dc.id, dc.is_matched, dc.matching_confidence
            FROM detection_comparisons dc
            WHERE dc.test_session_id = :session_id
            AND ((dc.is_matched = true AND dc.matching_confidence < 0.5)
                OR (dc.is_matched = false AND dc.matching_confidence > 0.8))
        """), {"session_id": test_session_id}).fetchall()
        
        if inconsistent_matches:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="database_integrity",
                message="Found inconsistent matching flags and confidence scores",
                details={"inconsistent_count": len(inconsistent_matches)},
                suggested_fix="Review matching logic and update flags or confidence scores"
            ))
        
        return issues
    
    def validate_timing_consistency(self, test_session_id: str) -> List[ValidationIssue]:
        """Validate timing consistency across related records"""
        issues = []
        
        # Check for detection events outside video duration
        out_of_bounds = self.session.execute(text("""
            SELECT de.id, de.video_relative_timestamp, v.duration
            FROM detection_events de
            JOIN test_sessions ts ON de.test_session_id = ts.id
            JOIN videos v ON ts.video_id = v.id
            WHERE ts.id = :session_id
            AND de.video_relative_timestamp IS NOT NULL
            AND (de.video_relative_timestamp < 0 OR de.video_relative_timestamp > v.duration)
        """), {"session_id": test_session_id}).fetchall()
        
        if out_of_bounds:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="timing_consistency",
                message="Detection events with timestamps outside video duration",
                details={"out_of_bounds_count": len(out_of_bounds)},
                suggested_fix="Check timestamp calculation or video duration metadata"
            ))
        
        # Check for unrealistic latency values
        extreme_latencies = self.session.execute(text("""
            SELECT dc.id, dc.latency_ms
            FROM detection_comparisons dc
            WHERE dc.test_session_id = :session_id
            AND dc.latency_ms IS NOT NULL
            AND (dc.latency_ms < -5000 OR dc.latency_ms > 30000)
        """), {"session_id": test_session_id}).fetchall()
        
        if extreme_latencies:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="timing_consistency",
                message="Found extreme latency values",
                details={"extreme_count": len(extreme_latencies)},
                suggested_fix="Review latency calculation or filter extreme outliers"
            ))
        
        return issues

class ComprehensiveValidator:
    """Main validator that orchestrates all validation checks"""
    
    def __init__(self, session: Session, tolerance_ms: int = 100):
        self.session = session
        self.timing_validator = TimingValidator(tolerance_ms)
        self.gt_validator = GroundTruthValidator()
        self.db_validator = DatabaseIntegrityValidator(session)
        self.all_issues: List[ValidationIssue] = []
    
    def validate_test_session_complete(self, test_session_id: str) -> Dict[str, Any]:
        """Run comprehensive validation for a test session"""
        logger.info(f"Running comprehensive validation for test session: {test_session_id}")
        
        validation_start = datetime.now()
        self.all_issues = []
        
        # Database integrity checks
        db_issues = self.db_validator.validate_test_session_data(test_session_id)
        self.all_issues.extend(db_issues)
        
        matching_issues = self.db_validator.validate_detection_matching(test_session_id)
        self.all_issues.extend(matching_issues)
        
        timing_issues = self.db_validator.validate_timing_consistency(test_session_id)
        self.all_issues.extend(timing_issues)
        
        # Get test session details for validation
        test_session = self.session.execute(text("""
            SELECT ts.*, v.duration, v.fps
            FROM test_sessions ts
            JOIN videos v ON ts.video_id = v.id
            WHERE ts.id = :session_id
        """), {"session_id": test_session_id}).fetchone()
        
        if test_session:
            # Validate video timing
            video_timing_issues = self.timing_validator.validate_video_timing(
                video_duration=test_session.duration or 0,
                fps=test_session.fps or 30,
                playback_start_time=test_session.video_playback_start_time,
                playback_duration=test_session.video_playback_duration
            )
            self.all_issues.extend(video_timing_issues)
            
            # Validate detection events
            detection_events = self.session.execute(text("""
                SELECT * FROM detection_events 
                WHERE test_session_id = :session_id
            """), {"session_id": test_session_id}).fetchall()
            
            for event in detection_events:
                # Validate timestamp alignment
                if event.video_relative_timestamp is not None and test_session.video_playback_start_time:
                    alignment_issues = self.timing_validator.validate_timestamp_alignment(
                        unix_timestamp=event.timestamp,
                        video_relative_timestamp=event.video_relative_timestamp,
                        video_start_time=test_session.video_playback_start_time
                    )
                    self.all_issues.extend(alignment_issues)
                
                # Validate latency if available
                if event.actual_latency_ms is not None:
                    latency_issues = self.timing_validator.validate_latency_measurement(
                        latency_ms=event.actual_latency_ms,
                        tolerance_ms=test_session.tolerance_ms
                    )
                    self.all_issues.extend(latency_issues)
                
                # Validate confidence
                if hasattr(event, 'confidence') and event.confidence is not None:
                    confidence_issues = self.gt_validator.validate_confidence_score(event.confidence)
                    self.all_issues.extend(confidence_issues)
        
        validation_end = datetime.now()
        validation_duration = (validation_end - validation_start).total_seconds()
        
        # Summarize results
        issues_by_severity = {}
        issues_by_category = {}
        
        for issue in self.all_issues:
            # Count by severity
            severity_key = issue.severity.value
            issues_by_severity[severity_key] = issues_by_severity.get(severity_key, 0) + 1
            
            # Count by category
            issues_by_category[issue.category] = issues_by_category.get(issue.category, 0) + 1
        
        # Determine overall health
        critical_count = issues_by_severity.get('critical', 0)
        error_count = issues_by_severity.get('error', 0)
        warning_count = issues_by_severity.get('warning', 0)
        
        if critical_count > 0:
            overall_health = 'critical'
        elif error_count > 0:
            overall_health = 'poor'
        elif warning_count > 5:
            overall_health = 'fair'
        elif warning_count > 0:
            overall_health = 'good'
        else:
            overall_health = 'excellent'
        
        results = {
            'test_session_id': test_session_id,
            'validation_timestamp': validation_start.isoformat(),
            'validation_duration_seconds': validation_duration,
            'overall_health': overall_health,
            'total_issues': len(self.all_issues),
            'issues_by_severity': issues_by_severity,
            'issues_by_category': issues_by_category,
            'detailed_issues': [
                {
                    'severity': issue.severity.value,
                    'category': issue.category,
                    'message': issue.message,
                    'details': issue.details,
                    'suggested_fix': issue.suggested_fix
                }
                for issue in self.all_issues
            ]
        }
        
        logger.info(f"Validation completed: {overall_health} health with {len(self.all_issues)} issues")
        return results

def validate_hil_system_health(session: Session, tolerance_ms: int = 100) -> Dict[str, Any]:
    """Validate overall HIL system health"""
    validator = ComprehensiveValidator(session, tolerance_ms)
    
    # Get all active test sessions
    active_sessions = session.execute(text("""
        SELECT id FROM test_sessions 
        WHERE status IN ('running', 'completed')
        ORDER BY created_at DESC
        LIMIT 10
    """)).fetchall()
    
    overall_results = {
        'validation_timestamp': datetime.now().isoformat(),
        'sessions_validated': len(active_sessions),
        'session_results': [],
        'system_summary': {
            'total_issues': 0,
            'critical_issues': 0,
            'error_issues': 0,
            'warning_issues': 0,
            'healthy_sessions': 0
        }
    }
    
    for session_row in active_sessions:
        session_result = validator.validate_test_session_complete(session_row.id)
        overall_results['session_results'].append(session_result)
        
        # Update summary
        overall_results['system_summary']['total_issues'] += session_result['total_issues']
        overall_results['system_summary']['critical_issues'] += session_result['issues_by_severity'].get('critical', 0)
        overall_results['system_summary']['error_issues'] += session_result['issues_by_severity'].get('error', 0)
        overall_results['system_summary']['warning_issues'] += session_result['issues_by_severity'].get('warning', 0)
        
        if session_result['overall_health'] in ['excellent', 'good']:
            overall_results['system_summary']['healthy_sessions'] += 1
    
    # Determine overall system health
    healthy_percentage = (overall_results['system_summary']['healthy_sessions'] / 
                         max(len(active_sessions), 1)) * 100
    
    if overall_results['system_summary']['critical_issues'] > 0:
        overall_results['system_health'] = 'critical'
    elif overall_results['system_summary']['error_issues'] > 0:
        overall_results['system_health'] = 'degraded'
    elif healthy_percentage >= 80:
        overall_results['system_health'] = 'healthy'
    else:
        overall_results['system_health'] = 'fair'
    
    overall_results['healthy_session_percentage'] = healthy_percentage
    
    return overall_results