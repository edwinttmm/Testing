"""
WebSocket message formatting utilities to ensure consistent message formats 
between backend and frontend, matching TypeScript interface expectations.
"""

from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timezone
from enum import Enum
import json
import uuid
from pydantic import BaseModel, Field

# WebSocket Message Types matching frontend expectations
class WebSocketMessageType(str, Enum):
    # Detection events
    DETECTION_UPDATE = "detection_update"
    DETECTION_COMPLETED = "detection_completed"
    DETECTION_FAILED = "detection_failed"
    
    # Annotation events  
    ANNOTATION_CREATED = "annotation_created"
    ANNOTATION_UPDATED = "annotation_updated"
    ANNOTATION_VALIDATED = "annotation_validated"
    
    # Signal processing events
    SIGNAL_RECEIVED = "signal_received"
    SIGNAL_PROCESSED = "signal_processed"
    SIGNAL_FAILED = "signal_failed"
    
    # Test session events
    TEST_SESSION_STARTED = "test_session_started"
    TEST_SESSION_COMPLETED = "test_session_completed"
    TEST_SESSION_FAILED = "test_session_failed"
    TEST_SESSION_PROGRESS = "test_session_progress"
    
    # Video processing events
    VIDEO_PROCESSING_STARTED = "video_processing_started"
    VIDEO_PROCESSING_PROGRESS = "video_processing_progress"
    VIDEO_PROCESSING_COMPLETED = "video_processing_completed"
    VIDEO_PROCESSING_FAILED = "video_processing_failed"
    
    # General events
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    CONNECTION_STATUS = "connection_status"

class WebSocketMessage(BaseModel):
    """Standard WebSocket message format matching frontend TypeScript interfaces"""
    type: str = Field(description="Message type identifier")
    payload: Dict[str, Any] = Field(description="Message payload data")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique message ID")

    class Config:
        use_enum_values = True

# Specific message payload schemas
class DetectionEventData(BaseModel):
    """Detection event payload data"""
    id: Optional[str] = None
    video_id: Optional[str] = Field(None, alias="videoId") 
    detection_id: Optional[str] = Field(None, alias="detectionId")
    timestamp: Optional[float] = None
    frame_number: Optional[int] = Field(None, alias="frameNumber")
    vru_type: Optional[str] = Field(None, alias="vruType")
    confidence: Optional[float] = None
    bounding_box: Optional[Dict[str, Any]] = Field(None, alias="boundingBox")
    success: Optional[bool] = None
    processing_time: Optional[float] = Field(None, alias="processingTime")
    
    class Config:
        populate_by_name = True

class AnnotationEventData(BaseModel):
    """Annotation event payload data"""
    id: Optional[str] = None
    video_id: Optional[str] = Field(None, alias="videoId")
    annotation_id: Optional[str] = Field(None, alias="annotationId")
    detection_id: Optional[str] = Field(None, alias="detectionId")
    timestamp: Optional[float] = None
    frame_number: Optional[int] = Field(None, alias="frameNumber")
    vru_type: Optional[str] = Field(None, alias="vruType")
    bounding_box: Optional[Dict[str, Any]] = Field(None, alias="boundingBox")
    validated: Optional[bool] = None
    annotator: Optional[str] = None
    
    class Config:
        populate_by_name = True

class SignalProcessingEventData(BaseModel):
    """Signal processing event payload data"""
    id: Optional[str] = None
    signal_type: Optional[str] = Field(None, alias="signalType")
    success: Optional[bool] = None
    processing_time: Optional[float] = Field(None, alias="processingTime")
    timestamp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True

class TestSessionEventData(BaseModel):
    """Test session event payload data"""
    session_id: str = Field(alias="sessionId")
    project_id: Optional[str] = Field(None, alias="projectId")
    video_id: Optional[str] = Field(None, alias="videoId")
    status: str
    progress: Optional[float] = None  # 0.0 to 1.0
    current_video: Optional[int] = Field(None, alias="currentVideo")
    total_videos: Optional[int] = Field(None, alias="totalVideos")
    results_count: Optional[int] = Field(None, alias="resultsCount")
    message: Optional[str] = None
    
    class Config:
        populate_by_name = True

class VideoProcessingEventData(BaseModel):
    """Video processing event payload data"""
    video_id: str = Field(alias="videoId")
    filename: Optional[str] = None
    status: str
    progress: Optional[float] = None  # 0.0 to 1.0
    processing_step: Optional[str] = Field(None, alias="processingStep")
    detection_count: Optional[int] = Field(None, alias="detectionCount")
    ground_truth_count: Optional[int] = Field(None, alias="groundTruthCount")
    message: Optional[str] = None
    error: Optional[str] = None
    
    class Config:
        populate_by_name = True

class WebSocketFormatter:
    """Utility class for formatting WebSocket messages"""
    
    @staticmethod
    def create_message(
        message_type: Union[str, WebSocketMessageType],
        payload: Union[Dict[str, Any], BaseModel],
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a standardized WebSocket message"""
        
        # Convert enum to string if needed
        if isinstance(message_type, WebSocketMessageType):
            message_type = message_type.value
            
        # Convert pydantic model to dict if needed
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(by_alias=True, exclude_none=True)
            
        # Ensure camelCase keys in payload
        payload = WebSocketFormatter._convert_to_camel_case(payload)
        
        message = WebSocketMessage(
            type=message_type,
            payload=payload,
            id=message_id
        )
        
        return message.model_dump(by_alias=True, exclude_none=True)
    
    @staticmethod
    def create_detection_message(
        message_type: str,
        video_id: Optional[str] = None,
        detection_id: Optional[str] = None,
        timestamp: Optional[float] = None,
        frame_number: Optional[int] = None,
        vru_type: Optional[str] = None,
        confidence: Optional[float] = None,
        bounding_box: Optional[Dict[str, Any]] = None,
        success: Optional[bool] = None,
        processing_time: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a detection event WebSocket message"""
        
        payload = DetectionEventData(
            video_id=video_id,
            detection_id=detection_id,
            timestamp=timestamp,
            frame_number=frame_number,
            vru_type=vru_type,
            confidence=confidence,
            bounding_box=bounding_box,
            success=success,
            processing_time=processing_time,
            **kwargs
        )
        
        return WebSocketFormatter.create_message(message_type, payload)
    
    @staticmethod
    def create_annotation_message(
        message_type: str,
        video_id: Optional[str] = None,
        annotation_id: Optional[str] = None,
        detection_id: Optional[str] = None,
        timestamp: Optional[float] = None,
        frame_number: Optional[int] = None,
        vru_type: Optional[str] = None,
        bounding_box: Optional[Dict[str, Any]] = None,
        validated: Optional[bool] = None,
        annotator: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create an annotation event WebSocket message"""
        
        payload = AnnotationEventData(
            video_id=video_id,
            annotation_id=annotation_id,
            detection_id=detection_id,
            timestamp=timestamp,
            frame_number=frame_number,
            vru_type=vru_type,
            bounding_box=bounding_box,
            validated=validated,
            annotator=annotator,
            **kwargs
        )
        
        return WebSocketFormatter.create_message(message_type, payload)
    
    @staticmethod
    def create_test_session_message(
        message_type: str,
        session_id: str,
        project_id: Optional[str] = None,
        video_id: Optional[str] = None,
        status: str = "running",
        progress: Optional[float] = None,
        current_video: Optional[int] = None,
        total_videos: Optional[int] = None,
        results_count: Optional[int] = None,
        message: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a test session event WebSocket message"""
        
        payload = TestSessionEventData(
            session_id=session_id,
            project_id=project_id,
            video_id=video_id,
            status=status,
            progress=progress,
            current_video=current_video,
            total_videos=total_videos,
            results_count=results_count,
            message=message,
            **kwargs
        )
        
        return WebSocketFormatter.create_message(message_type, payload)
    
    @staticmethod
    def create_video_processing_message(
        message_type: str,
        video_id: str,
        filename: Optional[str] = None,
        status: str = "processing",
        progress: Optional[float] = None,
        processing_step: Optional[str] = None,
        detection_count: Optional[int] = None,
        ground_truth_count: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a video processing event WebSocket message"""
        
        payload = VideoProcessingEventData(
            video_id=video_id,
            filename=filename,
            status=status,
            progress=progress,
            processing_step=processing_step,
            detection_count=detection_count,
            ground_truth_count=ground_truth_count,
            message=message,
            error=error,
            **kwargs
        )
        
        return WebSocketFormatter.create_message(message_type, payload)
    
    @staticmethod
    def create_error_message(
        error_message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create an error WebSocket message"""
        
        payload = {
            "message": error_message,
            "code": error_code,
            "details": details
        }
        
        return WebSocketFormatter.create_message(WebSocketMessageType.ERROR, payload)
    
    @staticmethod
    def create_status_update(
        component: str,
        status: str,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a status update WebSocket message"""
        
        payload = {
            "component": component,
            "status": status,
            "message": message,
            "data": data or {}
        }
        
        return WebSocketFormatter.create_message(WebSocketMessageType.STATUS_UPDATE, payload)
    
    @staticmethod
    def _convert_to_camel_case(data: Union[Dict, list, Any]) -> Any:
        """Recursively convert dictionary keys from snake_case to camelCase"""
        if isinstance(data, dict):
            return {WebSocketFormatter._to_camel_case(key): WebSocketFormatter._convert_to_camel_case(value) 
                   for key, value in data.items()}
        elif isinstance(data, list):
            return [WebSocketFormatter._convert_to_camel_case(item) for item in data]
        else:
            return data
    
    @staticmethod
    def _to_camel_case(snake_str: str) -> str:
        """Convert snake_case to camelCase"""
        if not snake_str or snake_str.startswith('_'):
            return snake_str
        
        components = snake_str.split('_')
        return components[0] + ''.join(word.capitalize() for word in components[1:])

# Convenience functions for common WebSocket operations
def emit_detection_update(
    socketio_instance,
    video_id: str,
    detection_data: Dict[str, Any],
    room: Optional[str] = None
):
    """Emit a detection update WebSocket message"""
    message = WebSocketFormatter.create_detection_message(
        WebSocketMessageType.DETECTION_UPDATE,
        video_id=video_id,
        **detection_data
    )
    
    if room:
        socketio_instance.emit('message', message, room=room)
    else:
        socketio_instance.emit('message', message)

def emit_annotation_created(
    socketio_instance,
    video_id: str,
    annotation_data: Dict[str, Any],
    room: Optional[str] = None
):
    """Emit an annotation created WebSocket message"""
    message = WebSocketFormatter.create_annotation_message(
        WebSocketMessageType.ANNOTATION_CREATED,
        video_id=video_id,
        **annotation_data
    )
    
    if room:
        socketio_instance.emit('message', message, room=room)
    else:
        socketio_instance.emit('message', message)

def emit_test_session_progress(
    socketio_instance,
    session_id: str,
    progress_data: Dict[str, Any],
    room: Optional[str] = None
):
    """Emit a test session progress WebSocket message"""
    message = WebSocketFormatter.create_test_session_message(
        WebSocketMessageType.TEST_SESSION_PROGRESS,
        session_id=session_id,
        **progress_data
    )
    
    if room:
        socketio_instance.emit('message', message, room=room)
    else:
        socketio_instance.emit('message', message)