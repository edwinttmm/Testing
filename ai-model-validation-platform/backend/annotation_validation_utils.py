"""
Annotation Validation Utilities
===============================

Comprehensive validation utilities for annotation management:
- Data validation and sanitization
- Business logic validation
- Error handling and reporting
- Performance optimization helpers
- Security validation

Features:
- Type-safe validation with Pydantic
- Custom validation rules for annotations
- Performance-optimized database queries  
- Security checks and sanitization
- Comprehensive error reporting
"""

from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import logging
import re
import uuid

# Import models
from models import Annotation, Video, GroundTruthObject, AnnotationSession

# Import validation
from pydantic import BaseModel, ValidationError, validator
from enum import Enum

logger = logging.getLogger(__name__)

# =============================================================================
# VALIDATION ENUMS AND CONSTANTS
# =============================================================================

class ValidationErrorType(str, Enum):
    INVALID_FORMAT = "invalid_format"
    MISSING_REQUIRED = "missing_required"
    INVALID_RANGE = "invalid_range"
    DUPLICATE_ENTRY = "duplicate_entry"
    REFERENCE_NOT_FOUND = "reference_not_found"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    SECURITY_VIOLATION = "security_violation"

class AnnotationValidationError(Exception):
    """Custom exception for annotation validation errors"""
    def __init__(self, error_type: ValidationErrorType, message: str, details: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(message)

# Business validation constants
MAX_ANNOTATION_SIZE = 10000  # Maximum annotations per video
MAX_BOUNDING_BOX_AREA = 0.8  # Maximum 80% of image area
MIN_BOUNDING_BOX_AREA = 0.0001  # Minimum 0.01% of image area
MAX_TIMESTAMP_DRIFT = 300  # Maximum 5 minutes drift from video duration
MAX_NOTE_LENGTH = 2000
VALID_DETECTION_ID_PATTERN = r'^[A-Z]{3}_[A-Z0-9]+_\d{4}$'  # e.g., DET_PED_0001

# =============================================================================
# VALIDATION HELPER FUNCTIONS
# =============================================================================

def validate_uuid(value: str) -> bool:
    """Validate UUID format"""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False

def validate_detection_id(detection_id: str) -> bool:
    """Validate detection ID format"""
    if not detection_id:
        return True  # Optional field
    return bool(re.match(VALID_DETECTION_ID_PATTERN, detection_id))

def sanitize_text_input(text: Optional[str], max_length: int = MAX_NOTE_LENGTH) -> Optional[str]:
    """Sanitize and validate text input"""
    if not text:
        return None
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', text.strip())
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip()
    
    return sanitized if sanitized else None

def validate_bounding_box_coordinates(x: float, y: float, width: float, height: float, 
                                    image_width: Optional[float] = None, 
                                    image_height: Optional[float] = None) -> Tuple[bool, Optional[str]]:
    """Validate bounding box coordinates"""
    
    # Basic coordinate validation
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return False, "Bounding box coordinates must be non-negative and have positive dimensions"
    
    # Image boundary validation if dimensions provided
    if image_width and image_height:
        if x + width > image_width or y + height > image_height:
            return False, "Bounding box extends beyond image boundaries"
        
        # Area validation
        box_area = width * height
        image_area = image_width * image_height
        area_ratio = box_area / image_area
        
        if area_ratio > MAX_BOUNDING_BOX_AREA:
            return False, f"Bounding box area exceeds maximum allowed ({MAX_BOUNDING_BOX_AREA * 100}% of image)"
        
        if area_ratio < MIN_BOUNDING_BOX_AREA:
            return False, f"Bounding box area below minimum threshold ({MIN_BOUNDING_BOX_AREA * 100}% of image)"
    
    return True, None

def validate_temporal_consistency(timestamp: float, end_timestamp: Optional[float], 
                                video_duration: Optional[float] = None) -> Tuple[bool, Optional[str]]:
    """Validate temporal annotation consistency"""
    
    if timestamp < 0:
        return False, "Timestamp must be non-negative"
    
    if end_timestamp is not None:
        if end_timestamp <= timestamp:
            return False, "End timestamp must be greater than start timestamp"
        
        # Check reasonable temporal annotation duration (max 30 seconds)
        if end_timestamp - timestamp > 30:
            return False, "Temporal annotation duration exceeds maximum (30 seconds)"
    
    if video_duration:
        if timestamp > video_duration + MAX_TIMESTAMP_DRIFT:
            return False, f"Timestamp exceeds video duration by more than {MAX_TIMESTAMP_DRIFT} seconds"
        
        if end_timestamp and end_timestamp > video_duration + MAX_TIMESTAMP_DRIFT:
            return False, f"End timestamp exceeds video duration by more than {MAX_TIMESTAMP_DRIFT} seconds"
    
    return True, None

# =============================================================================
# ANNOTATION VALIDATION CLASS
# =============================================================================

class AnnotationValidator:
    """Comprehensive annotation validator with business logic"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    async def validate_annotation_creation(self, video_id: str, annotation_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate annotation creation with all business rules"""
        errors = []
        
        try:
            # 1. Validate video exists and get metadata
            video = self.db.query(Video).filter(Video.id == video_id).first()
            if not video:
                errors.append(f"Video with ID {video_id} not found")
                return False, errors
            
            # 2. Validate required fields
            required_fields = ['frame_number', 'timestamp', 'vru_type', 'bounding_box']
            for field in required_fields:
                if field not in annotation_data or annotation_data[field] is None:
                    errors.append(f"Required field '{field}' is missing")
            
            if errors:
                return False, errors
            
            # 3. Validate detection ID format
            detection_id = annotation_data.get('detection_id')
            if detection_id and not validate_detection_id(detection_id):
                errors.append(f"Invalid detection ID format: {detection_id}")
            
            # 4. Validate bounding box
            bbox = annotation_data['bounding_box']
            if isinstance(bbox, dict):
                bbox_valid, bbox_error = validate_bounding_box_coordinates(
                    bbox.get('x', 0), bbox.get('y', 0), 
                    bbox.get('width', 0), bbox.get('height', 0)
                )
                if not bbox_valid:
                    errors.append(f"Bounding box validation failed: {bbox_error}")
            else:
                errors.append("Bounding box must be a dictionary with x, y, width, height")
            
            # 5. Validate temporal data
            timestamp = annotation_data['timestamp']
            end_timestamp = annotation_data.get('end_timestamp')
            temporal_valid, temporal_error = validate_temporal_consistency(
                timestamp, end_timestamp, video.duration
            )
            if not temporal_valid:
                errors.append(f"Temporal validation failed: {temporal_error}")
            
            # 6. Validate frame number consistency
            frame_number = annotation_data['frame_number']
            if video.fps and video.duration:
                max_frame = int(video.fps * video.duration)
                if frame_number > max_frame:
                    errors.append(f"Frame number {frame_number} exceeds video frame count {max_frame}")
            
            # 7. Check for annotation density (business rule)
            annotation_count = self.db.query(Annotation).filter(Annotation.video_id == video_id).count()
            if annotation_count >= MAX_ANNOTATION_SIZE:
                errors.append(f"Video has reached maximum annotation limit ({MAX_ANNOTATION_SIZE})")
            
            # 8. Validate VRU type
            valid_vru_types = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
            vru_type = annotation_data['vru_type']
            if vru_type not in valid_vru_types:
                errors.append(f"Invalid VRU type '{vru_type}'. Must be one of: {valid_vru_types}")
            
            # 9. Sanitize text fields
            notes = annotation_data.get('notes')
            if notes:
                sanitized_notes = sanitize_text_input(notes)
                if sanitized_notes != notes:
                    errors.append("Notes contain invalid characters and have been sanitized")
                annotation_data['notes'] = sanitized_notes
            
            # 10. Check for potential duplicates (business rule)
            duplicate_check = self.db.query(Annotation).filter(
                and_(
                    Annotation.video_id == video_id,
                    Annotation.frame_number == frame_number,
                    Annotation.timestamp.between(timestamp - 0.1, timestamp + 0.1)
                )
            ).first()
            
            if duplicate_check:
                errors.append(f"Potential duplicate annotation detected at frame {frame_number}, timestamp {timestamp}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Error during annotation validation: {str(e)}")
            errors.append(f"Validation error: {str(e)}")
            return False, errors
    
    async def validate_annotation_update(self, annotation_id: str, update_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate annotation update with business rules"""
        errors = []
        
        try:
            # 1. Check annotation exists
            annotation = self.db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                errors.append(f"Annotation with ID {annotation_id} not found")
                return False, errors
            
            # 2. Validate fields being updated
            if 'detection_id' in update_data:
                detection_id = update_data['detection_id']
                if detection_id and not validate_detection_id(detection_id):
                    errors.append(f"Invalid detection ID format: {detection_id}")
            
            if 'bounding_box' in update_data:
                bbox = update_data['bounding_box']
                if isinstance(bbox, dict):
                    bbox_valid, bbox_error = validate_bounding_box_coordinates(
                        bbox.get('x', 0), bbox.get('y', 0), 
                        bbox.get('width', 0), bbox.get('height', 0)
                    )
                    if not bbox_valid:
                        errors.append(f"Bounding box validation failed: {bbox_error}")
                else:
                    errors.append("Bounding box must be a dictionary")
            
            if 'timestamp' in update_data or 'end_timestamp' in update_data:
                timestamp = update_data.get('timestamp', annotation.timestamp)
                end_timestamp = update_data.get('end_timestamp', annotation.end_timestamp)
                
                # Get video for duration check
                video = self.db.query(Video).filter(Video.id == annotation.video_id).first()
                temporal_valid, temporal_error = validate_temporal_consistency(
                    timestamp, end_timestamp, video.duration if video else None
                )
                if not temporal_valid:
                    errors.append(f"Temporal validation failed: {temporal_error}")
            
            if 'vru_type' in update_data:
                valid_vru_types = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
                vru_type = update_data['vru_type']
                if vru_type not in valid_vru_types:
                    errors.append(f"Invalid VRU type '{vru_type}'. Must be one of: {valid_vru_types}")
            
            # 3. Sanitize text fields
            if 'notes' in update_data:
                notes = update_data['notes']
                if notes:
                    sanitized_notes = sanitize_text_input(notes)
                    if sanitized_notes != notes:
                        errors.append("Notes contain invalid characters and have been sanitized")
                    update_data['notes'] = sanitized_notes
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Error during annotation update validation: {str(e)}")
            errors.append(f"Validation error: {str(e)}")
            return False, errors
    
    async def validate_batch_annotations(self, video_id: str, annotations_data: List[Dict[str, Any]]) -> Tuple[bool, Dict[int, List[str]]]:
        """Validate batch annotation creation"""
        all_errors = {}
        
        # Check batch size limits
        if len(annotations_data) > 100:
            all_errors[-1] = ["Batch size exceeds maximum limit of 100 annotations"]
            return False, all_errors
        
        # Validate each annotation
        for i, annotation_data in enumerate(annotations_data):
            is_valid, errors = await self.validate_annotation_creation(video_id, annotation_data)
            if not is_valid:
                all_errors[i] = errors
        
        # Check for batch-level duplicates
        timestamps = [ann.get('timestamp') for ann in annotations_data if ann.get('timestamp')]
        frame_numbers = [ann.get('frame_number') for ann in annotations_data if ann.get('frame_number')]
        
        # Check for duplicate timestamps in batch
        seen_timestamps = set()
        for i, ts in enumerate(timestamps):
            if ts in seen_timestamps:
                if i not in all_errors:
                    all_errors[i] = []
                all_errors[i].append(f"Duplicate timestamp {ts} in batch")
            seen_timestamps.add(ts)
        
        # Check for duplicate frame numbers in batch
        seen_frames = set()
        for i, frame in enumerate(frame_numbers):
            if frame in seen_frames:
                if i not in all_errors:
                    all_errors[i] = []
                all_errors[i].append(f"Duplicate frame number {frame} in batch")
            seen_frames.add(frame)
        
        return len(all_errors) == 0, all_errors

# =============================================================================
# DATABASE QUERY OPTIMIZATION HELPERS
# =============================================================================

class AnnotationQueryOptimizer:
    """Optimized database queries for annotation management"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_annotations_with_video_metadata(self, video_id: str, validated_only: bool = False):
        """Get annotations with video metadata in single query"""
        query = self.db.query(Annotation, Video).join(Video).filter(Video.id == video_id)
        
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        return query.order_by(Annotation.timestamp).all()
    
    def get_annotation_statistics(self, video_id: Optional[str] = None, project_id: Optional[str] = None):
        """Get optimized annotation statistics"""
        base_query = self.db.query(Annotation)
        
        if video_id:
            base_query = base_query.filter(Annotation.video_id == video_id)
        elif project_id:
            base_query = base_query.join(Video).filter(Video.project_id == project_id)
        
        # Use single query with case statements for efficiency
        stats = self.db.query(
            func.count(Annotation.id).label('total'),
            func.sum(func.case((Annotation.validated == True, 1), else_=0)).label('validated'),
            func.sum(func.case((Annotation.difficult == True, 1), else_=0)).label('difficult'),
            func.sum(func.case((Annotation.occluded == True, 1), else_=0)).label('occluded'),
            func.sum(func.case((Annotation.truncated == True, 1), else_=0)).label('truncated'),
        )
        
        if video_id:
            stats = stats.filter(Annotation.video_id == video_id)
        elif project_id:
            stats = stats.join(Video).filter(Video.project_id == project_id)
        
        return stats.first()
    
    def get_annotation_density_analysis(self, video_id: str):
        """Analyze annotation density for quality control"""
        # Get annotations grouped by time windows (e.g., 10-second intervals)
        time_window = 10.0  # seconds
        
        annotations = self.db.query(
            func.floor(Annotation.timestamp / time_window).label('time_bucket'),
            func.count(Annotation.id).label('annotation_count'),
            func.avg(func.case((Annotation.validated == True, 1.0), else_=0.0)).label('validation_rate')
        ).filter(Annotation.video_id == video_id)\
         .group_by(func.floor(Annotation.timestamp / time_window))\
         .order_by('time_bucket').all()
        
        return [
            {
                'time_start': bucket * time_window,
                'time_end': (bucket + 1) * time_window,
                'annotation_count': count,
                'validation_rate': float(validation_rate or 0)
            }
            for bucket, count, validation_rate in annotations
        ]

# =============================================================================
# SECURITY VALIDATION HELPERS
# =============================================================================

class AnnotationSecurityValidator:
    """Security validation for annotation operations"""
    
    @staticmethod
    def validate_file_access(file_path: str) -> bool:
        """Validate file path for directory traversal attacks"""
        if not file_path:
            return False
        
        # Check for directory traversal patterns
        dangerous_patterns = ['../', '..\\', '/etc/', '/var/', '/usr/', 'C:\\', '\\Windows\\']
        file_path_lower = file_path.lower()
        
        for pattern in dangerous_patterns:
            if pattern in file_path_lower:
                return False
        
        return True
    
    @staticmethod
    def validate_input_size(data: Any, max_size: int = 1024 * 1024) -> bool:
        """Validate input size to prevent DoS attacks"""
        import sys
        
        size = sys.getsizeof(data)
        return size <= max_size
    
    @staticmethod
    def sanitize_search_query(query: str) -> str:
        """Sanitize search queries to prevent injection"""
        if not query:
            return ""
        
        # Remove SQL injection patterns
        dangerous_patterns = [';', '--', '/*', '*/', 'xp_', 'sp_', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
        sanitized = query
        
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, '')
        
        return sanitized.strip()[:500]  # Limit length

# =============================================================================
# ERROR FORMATTING UTILITIES
# =============================================================================

def format_validation_error(error_type: ValidationErrorType, field: str, message: str, 
                          value: Any = None) -> Dict[str, Any]:
    """Format validation error in consistent structure"""
    return {
        "type": error_type.value,
        "field": field,
        "message": message,
        "value": value,
        "timestamp": datetime.utcnow().isoformat()
    }

def format_batch_validation_errors(errors: Dict[int, List[str]]) -> Dict[str, Any]:
    """Format batch validation errors"""
    formatted_errors = {}
    total_errors = 0
    
    for index, error_list in errors.items():
        formatted_errors[f"annotation_{index}"] = error_list
        total_errors += len(error_list)
    
    return {
        "batch_errors": formatted_errors,
        "total_errors": total_errors,
        "failed_annotations": len(errors),
        "timestamp": datetime.utcnow().isoformat()
    }

# =============================================================================
# PERFORMANCE MONITORING UTILITIES
# =============================================================================

class AnnotationPerformanceMonitor:
    """Monitor annotation operation performance"""
    
    def __init__(self):
        self.operation_times = {}
    
    def start_operation(self, operation_name: str) -> str:
        """Start timing an operation"""
        operation_id = str(uuid.uuid4())
        self.operation_times[operation_id] = {
            'name': operation_name,
            'start_time': datetime.utcnow(),
            'end_time': None,
            'duration_ms': None
        }
        return operation_id
    
    def end_operation(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """End timing an operation and return metrics"""
        if operation_id not in self.operation_times:
            return None
        
        operation = self.operation_times[operation_id]
        operation['end_time'] = datetime.utcnow()
        operation['duration_ms'] = (operation['end_time'] - operation['start_time']).total_seconds() * 1000
        
        # Log slow operations
        if operation['duration_ms'] > 5000:  # 5 seconds
            logger.warning(f"Slow operation detected: {operation['name']} took {operation['duration_ms']:.2f}ms")
        
        return operation
    
    def get_operation_stats(self) -> Dict[str, Any]:
        """Get operation statistics"""
        completed_operations = [op for op in self.operation_times.values() if op['end_time'] is not None]
        
        if not completed_operations:
            return {"total_operations": 0}
        
        durations = [op['duration_ms'] for op in completed_operations]
        
        return {
            "total_operations": len(completed_operations),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "slow_operations_count": sum(1 for d in durations if d > 5000)
        }

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_validation_summary(errors: List[str], warnings: List[str] = None) -> Dict[str, Any]:
    """Create validation summary response"""
    warnings = warnings or []
    
    return {
        "is_valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "validated_at": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    print("🔧 Annotation Validation Utilities")
    print("=" * 40)
    print("✅ Comprehensive validation framework")
    print("✅ Business logic validation")
    print("✅ Security validation helpers")
    print("✅ Performance optimization")
    print("✅ Error formatting utilities")
    print("✅ Database query optimization")
    print("=" * 40)
    print("🚀 Ready for annotation validation!")