# Data Transformation and Conversion Analysis

## Overview
This document provides comprehensive analysis of all data transformation points, conversion patterns, serialization/deserialization flows, and data mapping strategies throughout the AI Model Validation Platform.

## Data Transformation Architecture

```
┌─────────────────┐    Transform    ┌──────────────────┐    Transform    ┌─────────────────┐
│  Frontend Data  │ ◄─────────────► │  API Transport   │ ◄─────────────► │  Backend Data   │
│  (TypeScript)   │   camelCase     │   (JSON/HTTP)    │   snake_case    │   (Python)      │
└─────────────────┘  ◄─────────────► └──────────────────┘ ◄─────────────► └─────────────────┘
         │                                     │                                     │
    ┌────▼────┐                           ┌────▼────┐                           ┌────▼────┐
    │Component│                           │Schema   │                           │Database │
    │ State   │                           │Validation│                          │ Models  │
    └─────────┘                           └─────────┘                           └─────────┘
```

## Schema and Model Transformation Layers

### 1. Pydantic Schema Transformations

#### CamelCase Conversion Pattern
```python
# schemas.py - Base transformation class
from pydantic import BaseModel, Field
from typing import Dict, Any
import re

class CamelCaseModel(BaseModel):
    """Base model with automatic camelCase conversion"""
    
    class Config:
        # Convert snake_case to camelCase in JSON output
        alias_generator = lambda field_name: ''.join(
            word if i == 0 else word.capitalize() 
            for i, word in enumerate(field_name.split('_'))
        )
        populate_by_name = True  # Allow both snake_case and camelCase input
        
    def model_dump(self, by_alias: bool = True, **kwargs) -> Dict[str, Any]:
        """Override to ensure camelCase output"""
        return super().model_dump(by_alias=by_alias, **kwargs)

# Example schema with transformation
class ProjectResponse(CamelCaseModel):
    """Project response with automatic case conversion"""
    id: str
    name: str
    camera_view: CameraTypeEnum  # → "cameraView" in JSON
    signal_type: SignalTypeEnum  # → "signalType" in JSON  
    frame_rate: Optional[int] = Field(None, description="Video frame rate")  # → "frameRate"
    created_at: datetime  # → "createdAt"
    updated_at: datetime  # → "updatedAt"
    owner_id: str = Field(description="Project owner ID")  # → "ownerId"
    
    # Complex nested transformations
    video_links: List['VideoProjectLinkResponse'] = Field(default_factory=list)  # → "videoLinks"
    test_sessions: List['TestSessionResponse'] = Field(default_factory=list)  # → "testSessions"
```

#### Advanced Field Transformations
```python
# Complex data transformation with validation
class VideoResponse(CamelCaseModel):
    """Video response with enhanced transformations"""
    id: str
    filename: str
    file_path: Optional[str] = Field(None, alias="filePath")
    file_size: Optional[int] = Field(None, alias="fileSize")
    duration: Optional[float] = None
    fps: Optional[int] = Field(None, description="Frames per second")
    resolution: Optional[str] = None
    
    # URL transformation (computed field)
    @computed_field
    @property
    def video_url(self) -> Optional[str]:
        """Generate video URL with domain and path fixing"""
        if not self.file_path:
            return None
            
        # Handle path transformations
        if self.file_path.startswith('/'):
            relative_path = os.path.relpath(self.file_path, '/uploads')
        else:
            relative_path = self.file_path
            
        # Clean up path separators and fix common issues
        clean_path = relative_path.replace('\\', '/').replace('//', '/')
        
        return f"{settings.api_base_url}/uploads/{clean_path}"
    
    # Custom serialization for complex fields
    @field_serializer('created_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Ensure consistent datetime serialization"""
        return value.isoformat() if value else None
        
    @field_validator('file_size')
    @classmethod
    def validate_file_size(cls, v) -> Optional[int]:
        """Validate and transform file size"""
        if v is None:
            return None
        return max(0, int(v))  # Ensure non-negative
```

### 2. Database Model to Schema Mapping

#### ORM to Pydantic Transformation
```python
# crud.py - Data transformation utilities
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from models import Project, Video, TestSession, DetectionEvent
from schemas import ProjectResponse, VideoResponse, TestSessionResponse

class DataTransformationService:
    """Service for transforming data between layers"""
    
    @staticmethod
    def transform_project(db_project: Project) -> ProjectResponse:
        """Transform SQLAlchemy Project to Pydantic schema"""
        return ProjectResponse(
            id=db_project.id,
            name=db_project.name,
            camera_view=db_project.camera_view,
            signal_type=db_project.signal_type,
            frame_rate=db_project.frame_rate,
            created_at=db_project.created_at,
            updated_at=db_project.updated_at,
            owner_id=db_project.owner_id or "anonymous",
            
            # Transform related objects
            video_links=[
                DataTransformationService.transform_video_link(link) 
                for link in db_project.video_links
            ],
            test_sessions=[
                DataTransformationService.transform_test_session(session)
                for session in db_project.test_sessions
            ]
        )
    
    @staticmethod
    def transform_video_with_enhancements(db_video: Video) -> VideoResponse:
        """Transform Video with URL fixing and enhancements"""
        base_response = VideoResponse(
            id=db_video.id,
            filename=db_video.filename,
            file_path=db_video.file_path,
            file_size=db_video.file_size,
            duration=db_video.duration,
            fps=db_video.fps,
            resolution=db_video.resolution,
            created_at=db_video.created_at,
            updated_at=db_video.updated_at
        )
        
        # Apply URL transformations
        if base_response.file_path:
            base_response.video_url = DataTransformationService._fix_video_url(
                base_response.file_path
            )
            
        return base_response
    
    @staticmethod
    def _fix_video_url(file_path: str) -> str:
        """Apply consistent URL fixing transformations"""
        # Remove problematic prefixes
        cleaned_path = file_path.replace('ai-model-validation-platform/backend/', '')
        cleaned_path = cleaned_path.replace('uploads/', '')
        
        # Ensure proper path separators
        cleaned_path = cleaned_path.replace('\\', '/').replace('//', '/')
        
        # Handle special characters
        cleaned_path = cleaned_path.replace(' ', '%20')
        
        return f"{settings.api_base_url}/uploads/{cleaned_path}"
```

### 3. Frontend Data Transformation

#### TypeScript Type Transformations
```typescript
// types/api.ts - Frontend type definitions with transformations
export interface ApiVideo {
  id: string;
  filename: string;
  filePath?: string;
  fileSize?: number;
  duration?: number;
  fps?: number;
  resolution?: string;
  videoUrl?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ComponentVideo {
  id: string;
  filename: string;
  displayName: string;  // Transformed from filename
  filePath?: string;
  fileSize?: number;
  formattedSize?: string;  // Human-readable size
  duration?: number;
  formattedDuration?: string;  // Human-readable duration
  fps?: number;
  resolution?: string;
  videoUrl?: string;
  thumbnailUrl?: string;  // Generated thumbnail URL
  createdAt: Date;  // Parsed from ISO string
  updatedAt: Date;  // Parsed from ISO string
  status: 'loading' | 'ready' | 'error';  // UI state
}

// Data transformation utilities
export class DataTransformationUtils {
  /**
   * Transform API video response to component-ready format
   */
  static transformApiVideoToComponent(apiVideo: ApiVideo): ComponentVideo {
    return {
      ...apiVideo,
      displayName: this.formatVideoDisplayName(apiVideo.filename),
      formattedSize: apiVideo.fileSize ? this.formatFileSize(apiVideo.fileSize) : undefined,
      formattedDuration: apiVideo.duration ? this.formatDuration(apiVideo.duration) : undefined,
      thumbnailUrl: this.generateThumbnailUrl(apiVideo.id),
      createdAt: new Date(apiVideo.createdAt),
      updatedAt: new Date(apiVideo.updatedAt),
      status: 'ready'
    };
  }
  
  static formatVideoDisplayName(filename: string): string {
    // Remove file extension and format for display
    return filename
      .replace(/\.[^/.]+$/, '')  // Remove extension
      .replace(/[_-]/g, ' ')     // Replace underscores/hyphens with spaces
      .replace(/\b\w/g, l => l.toUpperCase());  // Title case
  }
  
  static formatFileSize(bytes: number): string {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  }
  
  static formatDuration(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    } else {
      return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
  }
  
  static generateThumbnailUrl(videoId: string): string {
    return `${getApiBaseUrl()}/api/videos/${videoId}/thumbnail`;
  }
}
```

#### API Service Data Transformation
```typescript
// services/api.ts - API service with data transformation
export class ApiTransformationService {
  /**
   * Transform request data before sending to API
   */
  static transformRequestData<T>(data: T): any {
    if (!data || typeof data !== 'object') return data;
    
    // Convert camelCase to snake_case for backend
    const transformed: any = {};
    
    for (const [key, value] of Object.entries(data)) {
      const snakeKey = this.camelToSnakeCase(key);
      
      if (value !== null && typeof value === 'object' && !Array.isArray(value) && !(value instanceof Date)) {
        // Recursively transform nested objects
        transformed[snakeKey] = this.transformRequestData(value);
      } else if (Array.isArray(value)) {
        // Transform array elements
        transformed[snakeKey] = value.map(item => 
          typeof item === 'object' ? this.transformRequestData(item) : item
        );
      } else {
        transformed[snakeKey] = value;
      }
    }
    
    return transformed;
  }
  
  /**
   * Transform response data after receiving from API
   */
  static transformResponseData<T>(data: any): T {
    if (!data || typeof data !== 'object') return data;
    
    // Convert snake_case to camelCase for frontend
    const transformed: any = {};
    
    for (const [key, value] of Object.entries(data)) {
      const camelKey = this.snakeToCamelCase(key);
      
      if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
        transformed[camelKey] = this.transformResponseData(value);
      } else if (Array.isArray(value)) {
        transformed[camelKey] = value.map(item => 
          typeof item === 'object' ? this.transformResponseData(item) : item
        );
      } else {
        transformed[camelKey] = value;
      }
    }
    
    return transformed as T;
  }
  
  private static camelToSnakeCase(str: string): string {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
  }
  
  private static snakeToCamelCase(str: string): string {
    return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
  }
}

// Enhanced API service with automatic transformation
export class EnhancedApiService {
  private async makeRequest<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any,
    options: RequestOptions = {}
  ): Promise<T> {
    try {
      // Transform request data
      const transformedData = data ? ApiTransformationService.transformRequestData(data) : undefined;
      
      const response = await this.httpClient.request({
        method,
        url: endpoint,
        data: transformedData,
        ...options
      });
      
      // Transform response data
      const transformedResponse = ApiTransformationService.transformResponseData<T>(response.data);
      
      return transformedResponse;
    } catch (error) {
      // Transform error responses as well
      if (axios.isAxiosError(error) && error.response?.data) {
        error.response.data = ApiTransformationService.transformResponseData(error.response.data);
      }
      throw error;
    }
  }
}
```

## Real-Time Data Transformation

### 1. WebSocket Message Transformation

#### Bidirectional Message Transformation
```typescript
// WebSocket message transformation for real-time data
export class WebSocketMessageTransformer {
  /**
   * Transform outgoing messages to backend format
   */
  static transformOutgoingMessage(eventType: string, data: any): any {
    const transformed = {
      event_type: eventType,
      timestamp: Date.now(),
      data: this.transformToSnakeCase(data)
    };
    
    // Add specific transformations for different event types
    switch (eventType) {
      case 'join_session':
        return {
          ...transformed,
          data: {
            session_id: data.sessionId,
            client_info: {
              user_agent: navigator.userAgent,
              screen_resolution: `${screen.width}x${screen.height}`
            }
          }
        };
        
      case 'detection_feedback':
        return {
          ...transformed,
          data: {
            detection_id: data.detectionId,
            feedback_type: data.feedbackType,
            confidence_score: data.confidenceScore,
            user_notes: data.userNotes || null
          }
        };
        
      default:
        return transformed;
    }
  }
  
  /**
   * Transform incoming messages from backend format
   */
  static transformIncomingMessage(message: any): any {
    const transformed = this.transformToCamelCase(message);
    
    // Add specific transformations for different message types
    if (transformed.eventType === 'detectionEvent') {
      return {
        ...transformed,
        data: {
          ...transformed.data,
          timestamp: new Date(transformed.data.timestamp),
          // Transform detection coordinates
          boundingBox: transformed.data.boundingBox ? {
            x: transformed.data.boundingBox.x,
            y: transformed.data.boundingBox.y,
            width: transformed.data.boundingBox.width,
            height: transformed.data.boundingBox.height,
            confidence: transformed.data.boundingBox.confidence
          } : null
        }
      };
    }
    
    return transformed;
  }
  
  private static transformToSnakeCase(obj: any): any {
    if (Array.isArray(obj)) {
      return obj.map(item => this.transformToSnakeCase(item));
    } else if (obj !== null && typeof obj === 'object') {
      const result: any = {};
      for (const [key, value] of Object.entries(obj)) {
        const snakeKey = key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
        result[snakeKey] = this.transformToSnakeCase(value);
      }
      return result;
    }
    return obj;
  }
  
  private static transformToCamelCase(obj: any): any {
    if (Array.isArray(obj)) {
      return obj.map(item => this.transformToCamelCase(item));
    } else if (obj !== null && typeof obj === 'object') {
      const result: any = {};
      for (const [key, value] of Object.entries(obj)) {
        const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
        result[camelKey] = this.transformToCamelCase(value);
      }
      return result;
    }
    return obj;
  }
}
```

### 2. Real-Time State Transformation

#### Component State Synchronization
```typescript
// Real-time state transformation for components
export class StateTransformationService {
  /**
   * Transform detection event for component state
   */
  static transformDetectionEventForState(
    event: WebSocketDetectionEvent
  ): ComponentDetectionEvent {
    return {
      id: event.eventId,
      sessionId: event.sessionId,
      timestamp: new Date(event.timestamp),
      latencyMs: event.latencyMs,
      validationResult: event.validationResult as 'PASS' | 'FAIL' | 'PENDING',
      confidence: event.detectionConfidence || 0,
      
      // UI-specific transformations
      displayTime: this.formatTimestamp(new Date(event.timestamp)),
      latencyStatus: this.getLatencyStatus(event.latencyMs),
      validationColor: this.getValidationColor(event.validationResult),
      
      // Performance metrics
      processingTime: event.processingTimeMs || 0,
      networkLatency: event.networkLatencyMs || 0,
      
      // Animation state
      isNew: true,  // For highlighting new events
      animationDelay: Math.random() * 500  // Stagger animations
    };
  }
  
  /**
   * Transform test session state for component
   */
  static transformTestSessionForState(
    session: ApiTestSession
  ): ComponentTestSession {
    return {
      ...session,
      startTime: new Date(session.startTime),
      endTime: session.endTime ? new Date(session.endTime) : null,
      
      // Computed properties
      isActive: session.status === 'running',
      duration: this.calculateDuration(session.startTime, session.endTime),
      formattedDuration: this.formatDuration(
        this.calculateDuration(session.startTime, session.endTime)
      ),
      
      // Statistics
      totalDetections: session.detectionEvents?.length || 0,
      successfulDetections: session.detectionEvents?.filter(e => 
        e.validationResult === 'PASS'
      ).length || 0,
      
      // UI state
      canStart: session.status === 'created',
      canStop: session.status === 'running',
      canRestart: ['completed', 'failed'].includes(session.status),
      
      // Progress calculation
      progressPercentage: this.calculateProgress(session)
    };
  }
  
  private static formatTimestamp(date: Date): string {
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3
    });
  }
  
  private static getLatencyStatus(latencyMs: number): 'excellent' | 'good' | 'poor' | 'critical' {
    if (latencyMs < 50) return 'excellent';
    if (latencyMs < 100) return 'good';
    if (latencyMs < 200) return 'poor';
    return 'critical';
  }
  
  private static getValidationColor(result: string): string {
    switch (result) {
      case 'PASS': return '#4CAF50';
      case 'FAIL': return '#F44336';
      case 'PENDING': return '#FF9800';
      default: return '#9E9E9E';
    }
  }
  
  private static calculateDuration(startTime: string, endTime: string | null): number {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    return Math.max(0, end.getTime() - start.getTime());
  }
  
  private static calculateProgress(session: ApiTestSession): number {
    if (session.status === 'completed') return 100;
    if (session.status === 'failed') return 0;
    if (session.status === 'created') return 0;
    
    // For running sessions, calculate based on time or detection count
    const expectedDuration = session.expectedDurationMs || 60000; // Default 1 minute
    const elapsed = this.calculateDuration(session.startTime, null);
    
    return Math.min(100, (elapsed / expectedDuration) * 100);
  }
}
```

## File and Media Transformation

### 1. Video File Processing

#### Video Metadata Transformation
```python
# services/video_processing_service.py - Video file transformations
import cv2
import os
from typing import Optional, Dict, Any
from pathlib import Path

class VideoTransformationService:
    """Service for video file transformations and metadata extraction"""
    
    @staticmethod
    def extract_video_metadata(file_path: str) -> Dict[str, Any]:
        """Extract comprehensive video metadata"""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return {"error": "Cannot open video file"}
            
            # Extract basic properties
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 else 0
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            cap.release()
            
            return {
                "duration": round(duration, 2),
                "fps": round(fps, 2),
                "frame_count": frame_count,
                "resolution": f"{width}x{height}",
                "width": width,
                "height": height,
                "file_size": file_size,
                "aspect_ratio": round(width / height, 2) if height > 0 else 0,
                
                # Derived properties
                "is_hd": width >= 1280,
                "is_4k": width >= 3840,
                "bitrate_estimate": round(file_size * 8 / duration / 1000) if duration > 0 else 0,  # kbps
                "quality_score": VideoTransformationService._calculate_quality_score(
                    width, height, fps, file_size, duration
                )
            }
        except Exception as e:
            return {"error": f"Failed to extract metadata: {str(e)}"}
    
    @staticmethod
    def _calculate_quality_score(width: int, height: int, fps: float, 
                               file_size: int, duration: float) -> float:
        """Calculate a quality score based on video properties"""
        try:
            # Resolution score (0-40 points)
            pixels = width * height
            resolution_score = min(40, pixels / (1920 * 1080) * 30)
            
            # FPS score (0-20 points)
            fps_score = min(20, fps / 60 * 20)
            
            # Bitrate score (0-40 points)
            if duration > 0:
                bitrate = file_size * 8 / duration / 1000  # kbps
                bitrate_score = min(40, bitrate / 5000 * 40)  # Assume 5Mbps is good
            else:
                bitrate_score = 0
            
            return round(resolution_score + fps_score + bitrate_score, 1)
        except:
            return 0.0
    
    @staticmethod
    def generate_thumbnail(video_path: str, output_path: str, 
                         timestamp: float = None) -> bool:
        """Generate thumbnail from video at specific timestamp"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False
            
            # Set timestamp or use middle of video
            if timestamp is None:
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                timestamp = (frame_count / fps) / 2 if fps > 0 else 0
            
            # Seek to timestamp
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            
            ret, frame = cap.read()
            if ret:
                # Resize to thumbnail size
                height, width = frame.shape[:2]
                thumbnail_width = 320
                thumbnail_height = int((thumbnail_width / width) * height)
                
                thumbnail = cv2.resize(frame, (thumbnail_width, thumbnail_height))
                success = cv2.imwrite(output_path, thumbnail)
                cap.release()
                return success
            
            cap.release()
            return False
            
        except Exception:
            return False
```

### 2. File Upload Transformation

#### Secure File Processing
```python
# File upload with transformation and validation
from werkzeug.utils import secure_filename
import magic

class FileTransformationService:
    """Service for secure file transformations during upload"""
    
    ALLOWED_VIDEO_TYPES = {
        'video/mp4': ['.mp4'],
        'video/avi': ['.avi'],
        'video/quicktime': ['.mov'],
        'video/x-msvideo': ['.avi'],
        'video/webm': ['.webm']
    }
    
    @staticmethod
    def transform_uploaded_file(file: UploadFile, project_id: str) -> Dict[str, Any]:
        """Transform and validate uploaded file"""
        try:
            # Security: Generate safe filename
            original_filename = file.filename or "unknown"
            safe_filename = secure_filename(original_filename)
            
            # Generate unique filename to prevent conflicts
            file_id = str(uuid.uuid4())
            file_extension = Path(safe_filename).suffix.lower()
            final_filename = f"{file_id}{file_extension}"
            
            # Validate MIME type
            file_content = file.file.read(2048)  # Read first 2KB for type detection
            file.file.seek(0)  # Reset file pointer
            
            detected_type = magic.from_buffer(file_content, mime=True)
            
            if detected_type not in FileTransformationService.ALLOWED_VIDEO_TYPES:
                raise ValidationError(f"Invalid file type: {detected_type}")
            
            # Validate file extension matches MIME type
            allowed_extensions = FileTransformationService.ALLOWED_VIDEO_TYPES[detected_type]
            if file_extension not in allowed_extensions:
                raise ValidationError(f"File extension {file_extension} doesn't match type {detected_type}")
            
            # Determine storage path
            storage_dir = Path(settings.upload_directory) / project_id
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = storage_dir / final_filename
            
            # Store file with size limit checking
            file_size = 0
            with open(file_path, "wb") as buffer:
                while chunk := file.file.read(8192):  # 8KB chunks
                    file_size += len(chunk)
                    if file_size > settings.max_file_size:
                        os.remove(file_path)  # Clean up partial file
                        raise ValidationError(f"File too large: {file_size} bytes")
                    buffer.write(chunk)
            
            return {
                "original_filename": original_filename,
                "safe_filename": safe_filename,
                "final_filename": final_filename,
                "file_path": str(file_path),
                "relative_path": f"{project_id}/{final_filename}",
                "file_size": file_size,
                "mime_type": detected_type,
                "file_extension": file_extension,
                "file_id": file_id
            }
            
        except Exception as e:
            # Clean up on error
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
            raise
```

## Error Response Transformation

### 1. Error Standardization

#### Consistent Error Format
```python
# Error response transformation
class ErrorTransformationService:
    """Service for standardizing error responses"""
    
    @staticmethod
    def transform_validation_error(error: ValidationError) -> Dict[str, Any]:
        """Transform Pydantic validation errors"""
        return {
            "error_type": "validation_error",
            "message": "Request validation failed",
            "details": [
                {
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "invalid_value": err.get("input"),
                    "error_type": err["type"]
                }
                for err in error.errors()
            ],
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 422
        }
    
    @staticmethod
    def transform_database_error(error: SQLAlchemyError) -> Dict[str, Any]:
        """Transform database errors to user-friendly format"""
        if isinstance(error, IntegrityError):
            return {
                "error_type": "data_integrity_error",
                "message": "Data integrity constraint violated",
                "details": {
                    "constraint": ErrorTransformationService._extract_constraint_name(error),
                    "suggestion": "Please check for duplicate or invalid data"
                },
                "timestamp": datetime.utcnow().isoformat(),
                "status_code": 400
            }
        elif isinstance(error, OperationalError):
            return {
                "error_type": "database_operational_error", 
                "message": "Database operation failed",
                "details": {
                    "suggestion": "Please try again later or contact support"
                },
                "timestamp": datetime.utcnow().isoformat(),
                "status_code": 503
            }
        else:
            return {
                "error_type": "database_error",
                "message": "Database error occurred",
                "details": {
                    "error_class": type(error).__name__
                },
                "timestamp": datetime.utcnow().isoformat(),
                "status_code": 500
            }
    
    @staticmethod
    def _extract_constraint_name(error: IntegrityError) -> Optional[str]:
        """Extract constraint name from database error"""
        error_msg = str(error.orig) if error.orig else str(error)
        
        # Common constraint patterns
        patterns = [
            r'UNIQUE constraint failed: (\w+\.\w+)',
            r'FOREIGN KEY constraint failed',
            r'NOT NULL constraint failed: (\w+\.\w+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_msg)
            if match:
                return match.group(1) if match.groups() else "unknown"
        
        return None
```

## Performance Optimization Transformations

### 1. Lazy Loading Transformations

#### Efficient Data Loading
```python
# Optimized data transformation with lazy loading
class OptimizedTransformationService:
    """Service for performance-optimized data transformations"""
    
    @staticmethod
    def transform_project_list_optimized(
        db_projects: List[Project], 
        include_videos: bool = False,
        include_stats: bool = False
    ) -> List[ProjectResponse]:
        """Optimized project list transformation"""
        
        if not db_projects:
            return []
        
        # Base transformation
        results = []
        for project in db_projects:
            project_dict = {
                "id": project.id,
                "name": project.name,
                "camera_view": project.camera_view,
                "signal_type": project.signal_type,
                "frame_rate": project.frame_rate,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
                "owner_id": project.owner_id or "anonymous"
            }
            
            # Conditionally include expensive transformations
            if include_videos:
                project_dict["video_links"] = [
                    OptimizedTransformationService._transform_video_link_minimal(link)
                    for link in project.video_links
                ]
            
            if include_stats:
                project_dict["statistics"] = {
                    "video_count": len(project.video_links),
                    "test_session_count": len(project.test_sessions),
                    "last_activity": max(
                        project.updated_at,
                        max((session.updated_at for session in project.test_sessions), 
                            default=project.updated_at)
                    ).isoformat()
                }
            
            results.append(project_dict)
        
        return results
    
    @staticmethod
    def _transform_video_link_minimal(link: VideoProjectLink) -> Dict[str, Any]:
        """Minimal video link transformation for list views"""
        return {
            "video_id": link.video_id,
            "filename": link.video.filename if link.video else "Unknown",
            "file_size": link.video.file_size if link.video else None,
            "created_at": link.created_at.isoformat()
        }
```

### 2. Caching Transformations

#### Cached Data Transformation
```typescript
// Frontend caching with transformed data
export class CachedTransformationService {
  private static transformationCache = new Map<string, any>();
  private static cacheTimestamps = new Map<string, number>();
  private static readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes
  
  /**
   * Get cached transformed data or transform and cache
   */
  static getCachedTransformation<T>(
    cacheKey: string,
    rawData: any,
    transformFn: (data: any) => T
  ): T {
    const now = Date.now();
    const cachedData = this.transformationCache.get(cacheKey);
    const cacheTime = this.cacheTimestamps.get(cacheKey);
    
    // Return cached data if valid
    if (cachedData && cacheTime && (now - cacheTime) < this.CACHE_TTL) {
      return cachedData;
    }
    
    // Transform and cache new data
    const transformedData = transformFn(rawData);
    this.transformationCache.set(cacheKey, transformedData);
    this.cacheTimestamps.set(cacheKey, now);
    
    // Cleanup old cache entries periodically
    if (Math.random() < 0.01) { // 1% chance per call
      this.cleanupExpiredCache();
    }
    
    return transformedData;
  }
  
  /**
   * Invalidate cache for specific pattern
   */
  static invalidateCache(pattern: string): void {
    const regex = new RegExp(pattern);
    
    for (const key of this.transformationCache.keys()) {
      if (regex.test(key)) {
        this.transformationCache.delete(key);
        this.cacheTimestamps.delete(key);
      }
    }
  }
  
  private static cleanupExpiredCache(): void {
    const now = Date.now();
    
    for (const [key, timestamp] of this.cacheTimestamps.entries()) {
      if ((now - timestamp) > this.CACHE_TTL) {
        this.transformationCache.delete(key);
        this.cacheTimestamps.delete(key);
      }
    }
  }
}

// Usage example
export const useTransformedProjects = (projects: ApiProject[]) => {
  return useMemo(() => {
    return CachedTransformationService.getCachedTransformation(
      `projects-${projects.length}-${projects.map(p => p.updatedAt).join(',')}`,
      projects,
      DataTransformationUtils.transformProjectsForDisplay
    );
  }, [projects]);
};
```

## Future Transformation Enhancements

### Planned Improvements

1. **Schema Evolution Support**
   - Backward compatibility handling
   - Version-aware transformations
   - Migration utilities

2. **Advanced Validation**
   - Custom validation rules
   - Cross-field validation
   - Conditional transformations

3. **Performance Optimizations**
   - Streaming transformations
   - Parallel processing
   - Memory-efficient transformations

4. **Type Safety Enhancements**
   - Runtime type checking
   - Schema validation
   - Automatic type generation

5. **Monitoring and Analytics**
   - Transformation performance metrics
   - Error rate tracking
   - Transformation usage analytics