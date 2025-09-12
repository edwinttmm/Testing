# API Contracts and Type Compatibility Matrix

## Overview
This document provides comprehensive documentation of the API contracts between frontend TypeScript interfaces and backend Pydantic schemas, including type compatibility matrices, data transformation patterns, and version alignment strategies.

## Table of Contents
- [Contract Architecture](#contract-architecture)
- [Type Alignment Matrix](#type-alignment-matrix)
- [Enum Compatibility](#enum-compatibility)
- [Data Transformation Patterns](#data-transformation-patterns)
- [Field Name Mapping](#field-name-mapping)
- [Validation Contract Alignment](#validation-contract-alignment)
- [API Response Contracts](#api-response-contracts)
- [Error Contract Alignment](#error-contract-alignment)
- [WebSocket Contract Specifications](#websocket-contract-specifications)
- [Version Compatibility Strategy](#version-compatibility-strategy)

## Contract Architecture

### Serialization Strategy
The platform employs a sophisticated serialization system to ensure seamless data flow between TypeScript frontend and Python backend:

#### Backend: Automatic CamelCase Conversion
```python
def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

class CamelCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Generate camelCase aliases
        populate_by_name=True,           # Accept both formats
        by_alias=True,                   # Serialize with aliases
        from_attributes=True             # SQLAlchemy integration
    )
```

#### Frontend: Status Mapping Utilities
```typescript
export const mapToLegacyStatus = (status: VideoValidationStatus): string => {
  const statusMap: Record<VideoValidationStatus, string> = {
    [VideoValidationStatus.UPLOADED]: "uploaded",
    [VideoValidationStatus.PROCESSING]: "processing",
    [VideoValidationStatus.ANNOTATED]: "completed",
    // ... complete mapping
  };
  return statusMap[status] || "uploaded";
};
```

## Type Alignment Matrix

### Core Entity Contracts

| Entity | Frontend Interface | Backend Schema | Alignment Status | Notes |
|--------|-------------------|----------------|------------------|-------|
| **Project** | `Project` | `ProjectResponse` | ✅ Full | camelCase auto-conversion |
| **Video** | `VideoFile` | `VideoResponse` | ✅ Full | Extended compatibility fields |
| **Detection** | `Detection` | `DetectionEventResponse` | ✅ Full | LabJack timing integration |
| **Annotation** | `GroundTruthAnnotation` | `AnnotationResponse` | ✅ Full | Alias-based serialization |
| **TestSession** | `TestSession` | `TestSessionResponse` | ✅ Full | Status enum alignment |
| **User** | `User` | `AuthUser` | ⚠️ Partial | Limited exposure for security |

### Field-Level Compatibility Matrix

#### Project Contract
| Frontend Field | Backend Field | Type Match | Transformation | Status |
|----------------|---------------|------------|----------------|---------|
| `id` | `id` | ✅ string | None | Perfect |
| `name` | `name` | ✅ string | None | Perfect |
| `cameraView` | `camera_view` | ✅ enum | camelCase | Perfect |
| `signalType` | `signal_type` | ✅ enum | camelCase | Perfect |
| `createdAt` | `created_at` | ✅ datetime | camelCase + ISO | Perfect |
| `testsCount` | computed | ✅ number | Backend calculation | Perfect |
| `ownerId` | `owner_id` | ✅ string | camelCase | Perfect |

#### Video Contract
| Frontend Field | Backend Field | Type Match | Transformation | Status |
|----------------|---------------|------------|----------------|---------|
| `id` | `id` | ✅ string | None | Perfect |
| `filename` | `filename` | ✅ string | None | Perfect |
| `status` | `status` | ✅ enum | VideoValidationStatus | Perfect |
| `validationStatus` | `validation_status` | ✅ enum | camelCase | Perfect |
| `hilTestingReady` | `hil_testing_ready` | ✅ boolean | camelCase | Perfect |
| `groundTruthCount` | `ground_truth_count` | ✅ number | camelCase | Perfect |
| `fileSize` | `file_size` | ✅ number | camelCase | Perfect |
| `uploadedAt` | `created_at` | ✅ datetime | Property mapping | Perfect |
| `processing_status` | computed | ✅ string | Legacy compatibility | Perfect |
| `ground_truth_generated` | `ground_truth_generated` | ✅ boolean | Legacy field | Perfect |

#### Detection Contract
| Frontend Field | Backend Field | Type Match | Transformation | Status |
|----------------|---------------|------------|----------------|---------|
| `id` | `id` | ✅ string | None | Perfect |
| `videoId` | `video_id` | ✅ string | camelCase | Perfect |
| `frameNumber` | `frame_number` | ✅ number | camelCase | Perfect |
| `timestamp` | `timestamp` | ✅ number | None | Perfect |
| `vruType` | `vru_type` | ✅ enum | camelCase | Perfect |
| `boundingBox` | `bounding_box_*` | ✅ object | Coordinate mapping | Perfect |
| `confidence` | `confidence` | ✅ number | None | Perfect |
| `validationStatus` | `validation_result` | ✅ enum | Field mapping | Perfect |
| `isGroundTruth` | computed | ✅ boolean | Backend logic | Perfect |
| `latencyMs` | `latency_ms` | ✅ number | LabJack timing | Perfect |

## Enum Compatibility

### Camera Type Alignment
```typescript
// Frontend
export enum CameraType {
  FRONT_FACING = "front_facing",
  FRONT_FACING_VRU = "front_facing_vru",
  SIDE_VIEW = "side_view", 
  REAR_VIEW = "rear_view"
}
```

```python
# Backend
class CameraTypeEnum(str, Enum):
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU" 
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE_SCENARIOS = "Multi-angle"
```

**Contract Status**: ⚠️ **Partial Alignment**
- **Issue**: Different enum values and naming conventions
- **Solution**: Backend serializer converts to frontend-compatible values
- **Mapping**: `"Front-facing VRU"` → `"front_facing_vru"`

### VRU Type Alignment
```typescript
// Frontend  
export enum VRUType {
  PEDESTRIAN = "pedestrian",
  CYCLIST = "cyclist",
  MOTORCYCLIST = "motorcyclist",
  WHEELCHAIR = "wheelchair", 
  SCOOTER = "scooter"
}
```

```python
# Backend
class VRUType(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist" 
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
```

**Contract Status**: ✅ **Perfect Alignment**
- **Compatibility**: Exact string value match
- **Usage**: Direct serialization without transformation

### Video Validation Status Alignment
```typescript
// Frontend
export enum VideoValidationStatus {
  UPLOADED = "uploaded",
  PROCESSING = "processing", 
  ANNOTATED = "annotated",
  VALIDATED = "validated",
  READY_FOR_TESTING = "ready_for_testing",
  // ... complete enum
}
```

```python
# Backend
class VideoValidationStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    ANNOTATED = "annotated" 
    VALIDATED = "validated"
    READY_FOR_TESTING = "ready_for_testing"
    # ... complete enum
```

**Contract Status**: ✅ **Perfect Alignment**
- **Compatibility**: Exact enum value match
- **Serialization**: Direct value transmission

### Signal Type Alignment
```typescript
// Frontend
export enum SignalType {
  TTL = "ttl",
  GPIO = "gpio",
  ANALOG = "analog", 
  DIGITAL = "digital"
}
```

```python
# Backend  
class SignalTypeEnum(str, Enum):
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"
```

**Contract Status**: ⚠️ **Partial Alignment**
- **Issue**: Different enum values and casing
- **Solution**: Backend serializer provides conversion
- **Mapping**: `"GPIO"` → `"gpio"`, with additional frontend values

## Data Transformation Patterns

### Snake Case to CamelCase Conversion

#### Backend Serialization
```python
class ProjectResponse(CamelCaseModel):
    camera_model: str      # Serializes as "cameraModel"
    camera_view: str       # Serializes as "cameraView" 
    signal_type: str       # Serializes as "signalType"
    created_at: datetime   # Serializes as "createdAt"
    updated_at: datetime   # Serializes as "updatedAt"
```

#### Frontend Reception
```typescript
interface Project {
  cameraModel: string;    // Matches serialized "cameraModel"
  cameraView: CameraType; // Matches serialized "cameraView"
  signalType: SignalType; // Matches serialized "signalType"
  createdAt: string;      // Matches serialized "createdAt"
  updatedAt?: string;     // Matches serialized "updatedAt"
}
```

### Bounding Box Transformation

#### Backend Storage (Normalized)
```python
class DetectionEvent(Base):
    bounding_box_x = Column(Float)      # Individual coordinates
    bounding_box_y = Column(Float)
    bounding_box_width = Column(Float) 
    bounding_box_height = Column(Float)
    
    @property
    def bounding_box(self):
        """Construct bounding_box dict for API compatibility"""
        if self.bounding_box_x is not None:
            return {
                "x": self.bounding_box_x,
                "y": self.bounding_box_y, 
                "width": self.bounding_box_width,
                "height": self.bounding_box_height
            }
        return None
```

#### Frontend Interface (Object)
```typescript
interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
  // Computed fields
  area?: number;
  centerX?: number;
  centerY?: number;
}
```

### Timestamp Transformation

#### Backend Handling
```python
class CamelCaseModel(BaseModel):
    created_at: datetime
    
    def model_dump(self, by_alias=True):
        """Convert datetime to ISO string for frontend"""
        data = super().model_dump(by_alias=by_alias)
        if 'createdAt' in data and data['createdAt']:
            data['createdAt'] = data['createdAt'].isoformat()
        return data
```

#### Frontend Processing
```typescript
interface Project {
  createdAt: string;  // ISO datetime string
  updatedAt?: string;
}

// Utility function for date parsing
const parseApiDate = (dateStr: string): Date => {
  return new Date(dateStr);
};
```

## Field Name Mapping

### Comprehensive Field Mapping Table

| Domain | Frontend Field | Backend Field | Transformation | Notes |
|---------|----------------|---------------|----------------|-------|
| **Projects** | | | |
| | `cameraModel` | `camera_model` | snake_to_camel | Automatic |
| | `cameraView` | `camera_view` | snake_to_camel | Automatic |
| | `frameRate` | `frame_rate` | snake_to_camel | Automatic |
| | `signalType` | `signal_type` | snake_to_camel | Automatic |
| | `createdAt` | `created_at` | snake_to_camel + ISO | Automatic |
| | `updatedAt` | `updated_at` | snake_to_camel + ISO | Automatic |
| | `ownerId` | `owner_id` | snake_to_camel | Automatic |
| **Videos** | | | |
| | `fileSize` | `file_size` | snake_to_camel | Automatic |
| | `filePath` | `file_path` | snake_to_camel | Automatic |
| | `frameRate` | `fps` | Direct mapping | Different names |
| | `validationStatus` | `validation_status` | snake_to_camel | Automatic |
| | `validationType` | `validation_type` | snake_to_camel | Automatic |
| | `validatedAt` | `validated_at` | snake_to_camel + ISO | Automatic |
| | `validatedBy` | `validated_by` | snake_to_camel | Automatic |
| | `hilTestingReady` | `hil_testing_ready` | snake_to_camel | Automatic |
| | `groundTruthGenerated` | `ground_truth_generated` | snake_to_camel | Automatic |
| | `groundTruthCount` | `ground_truth_count` | snake_to_camel | Automatic |
| | `uploadedAt` | `created_at` | Property mapping | Legacy compatibility |
| **Detections** | | | |
| | `videoId` | `video_id` | snake_to_camel | Automatic |
| | `detectionId` | `detection_id` | snake_to_camel | Automatic |
| | `frameNumber` | `frame_number` | snake_to_camel | Automatic |
| | `vruType` | `vru_type` | snake_to_camel | Automatic |
| | `boundingBox` | `bounding_box_*` | Object construction | Complex mapping |
| | `groundTruthMatchId` | `ground_truth_match_id` | snake_to_camel | Automatic |
| | `isGroundTruth` | computed | Backend logic | Derived field |
| | `latencyMs` | `latency_ms` | snake_to_camel | LabJack timing |
| | `labjackTimestamp` | `labjack_timestamp` | snake_to_camel | LabJack timing |
| **Test Sessions** | | | |
| | `projectId` | `project_id` | snake_to_camel | Automatic |
| | `videoId` | `video_id` | snake_to_camel | Automatic |
| | `toleranceMs` | `tolerance_ms` | snake_to_camel | Automatic |
| | `startedAt` | `started_at` | snake_to_camel + ISO | Automatic |
| | `completedAt` | `completed_at` | snake_to_camel + ISO | Automatic |
| | `latencyThresholdMs` | `latency_threshold_ms` | snake_to_camel | LabJack timing |

### Legacy Compatibility Fields

#### Video Compatibility Layer
```typescript
// Frontend supports both new and legacy field names
interface VideoFile {
  // New unified fields
  fileSize: number;
  frameRate?: number;
  status: VideoValidationStatus;
  
  // Legacy compatibility fields
  file_size?: number;           // snake_case alias
  fps?: number;                 // Alternative frame rate
  frame_rate?: number;          // snake_case frame rate
  size?: number;                // Alternative file size
  processing_status?: string;    // Legacy status field
  ground_truth_generated?: boolean; // Legacy ground truth flag
  groundTruthStatus?: string;   // Computed legacy status
  ground_truth_status?: string; // snake_case alias
  detection_count?: number;     // Legacy detection count
  originalName?: string;        // Alternative filename
  url?: string;                 // File access URL
  
  // Additional metadata fields
  bitrate?: number;
  format?: string;
  codec?: string;
  mimeType?: string;
  thumbnailUrl?: string;
  metadata?: Record<string, unknown>;
}
```

## Validation Contract Alignment

### Input Validation Contracts

#### Project Creation Validation
```typescript
// Frontend Validation
interface ProjectCreate {
  name: string;                    // Required, non-empty
  description: string;             // Required
  cameraModel: string;             // Required
  cameraView: CameraType;          // Enum validation
  signalType: SignalType;          // Enum validation
}
```

```python
# Backend Validation
class ProjectCreate(ProjectBase):
    name: str                          # Required via Pydantic
    camera_model: str                  # Required via Pydantic  
    camera_view: CameraTypeEnum        # Enum validation
    signal_type: SignalTypeEnum        # Enum validation
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Project name cannot be empty')
        return v.strip()
```

**Contract Status**: ✅ **Aligned Validation**
- **Frontend**: TypeScript type checking + form validation
- **Backend**: Pydantic validation + custom validators
- **Consistency**: Matching validation rules

#### Annotation Validation Contracts
```typescript
// Frontend
interface AnnotationCreate {
  frameNumber: number;             // >= 0
  timestamp: number;               // >= 0
  vruType: VRUType;               // Enum validation
  boundingBox: BoundingBox;        // Object validation
}

interface BoundingBox {
  x: number;                       // >= 0
  y: number;                       // >= 0  
  width: number;                   // > 0
  height: number;                  // > 0
  confidence?: number;             // 0-1 range
}
```

```python
# Backend
class AnnotationCreate(BaseModel):
    frame_number: int = Field(..., ge=0)              # >= 0
    timestamp: float = Field(..., ge=0)               # >= 0  
    vru_type: VRUTypeEnum                             # Enum validation
    bounding_box: BoundingBox                         # Object validation

class BoundingBox(BaseModel):
    x: float = Field(..., ge=0)                       # >= 0
    y: float = Field(..., ge=0)                       # >= 0
    width: float = Field(..., gt=0)                   # > 0  
    height: float = Field(..., gt=0)                  # > 0
    confidence: Optional[float] = Field(None, ge=0, le=1) # 0-1 range
```

**Contract Status**: ✅ **Perfect Validation Alignment**
- **Range Validation**: Matching numeric constraints
- **Enum Validation**: Consistent enum checking  
- **Required Fields**: Matching required/optional fields
- **Type Safety**: Strong typing on both sides

### Validation Criteria Contracts

#### Video Validation Criteria
```typescript
// Frontend
interface VideoValidationCriteria {
  minDetectionCount: number;        // >= 0
  minConfidenceThreshold: number;   // 0.0-1.0
  minFrameCoveragePercent: number;  // 0.0-100.0
  minDurationSeconds: number;       // >= 1.0  
  maxDurationSeconds: number;       // > minDuration
  requiredResolutionMin: string;    // Format: "640x480"
  minFps: number;                   // >= 1.0
  requiredVruTypes?: string[];      // Valid VRU types
  minSceneComplexityScore: number;  // 0.0-1.0
}
```

```python
# Backend
class ValidationCriteriaRequest(BaseModel):
    min_detection_count: int = Field(5, ge=0, le=1000)
    min_confidence_threshold: float = Field(0.7, ge=0.0, le=1.0)
    min_frame_coverage_percent: float = Field(80.0, ge=0.0, le=100.0)
    min_duration_seconds: float = Field(10.0, ge=1.0, le=3600.0)
    max_duration_seconds: float = Field(300.0, ge=10.0, le=7200.0)  
    required_resolution_min: str = Field("640x480", pattern=r'^\d+x\d+$')
    min_fps: float = Field(24.0, ge=1.0, le=120.0)
    required_vru_types: Optional[List[str]] = Field(
        default=["pedestrian", "cyclist", "motorcyclist"],
        max_items=10
    )
    min_scene_complexity_score: float = Field(0.5, ge=0.0, le=1.0)
    
    @field_validator('max_duration_seconds')
    def validate_duration_range(cls, v, values):
        min_duration = values.get('min_duration_seconds', 10.0)
        if v <= min_duration:
            raise ValueError('Max duration must be greater than min duration')
        return v
```

**Contract Status**: ✅ **Advanced Validation Alignment**
- **Range Constraints**: Matching field ranges
- **Pattern Validation**: Resolution format validation
- **Cross-Field Validation**: Duration range validation
- **List Constraints**: VRU type array validation
- **Default Values**: Consistent default values

## API Response Contracts

### Standard Response Wrapper
```typescript
// Frontend Generic Response
interface ApiResponse<T = unknown> {
  data?: T;
  message?: string;
  error?: string;
  status?: number;
  success?: boolean;
  timestamp?: string;
}
```

```python
# Backend Response Pattern
class StandardResponse(BaseModel):
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None  
    status: Optional[int] = None
    success: bool = True
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

**Contract Status**: ✅ **Response Wrapper Alignment**

### Specific Response Contracts

#### Project Response Contract
```typescript
// Frontend Interface
interface Project {
  id: string;
  name: string;
  cameraModel: string;
  cameraView: CameraType;
  signalType: SignalType;
  createdAt: string;
  status: ProjectStatus;
  ownerId: string;
}
```

```python
# Backend Schema
class ProjectResponse(ProjectBase):
    id: str
    status: str
    owner_id: str                    # Serializes as "ownerId"
    created_at: datetime             # Serializes as "createdAt" (ISO)
    updated_at: Optional[datetime]   # Serializes as "updatedAt" (ISO)
```

**Contract Status**: ✅ **Perfect Response Contract**

#### Video Response Contract
```typescript
// Frontend Interface  
interface VideoFile {
  id: string;
  filename: string;
  fileSize: number;
  status: VideoValidationStatus;
  validationStatus: ValidationStatus;
  hilTestingReady: boolean;
  groundTruthCount: number;
  createdAt: string;
  // ... extensive compatibility fields
}
```

```python
# Backend Schema
class VideoResponse(VideoBase):
    id: str
    project_id: str                  # Serializes as "projectId" 
    status: str                      # VideoValidationStatus values
    ground_truth_generated: bool     # Serializes as "groundTruthGenerated"
    created_at: datetime             # Serializes as "createdAt" (ISO)
    detection_count: Optional[int]   # Serializes as "detectionCount"
```

**Contract Status**: ✅ **Enhanced Response Contract with Legacy Support**

## Error Contract Alignment

### Error Response Structure
```typescript
// Frontend Error Interface
interface ApiErrorResponse {
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, unknown>;
  timestamp?: string;
}
```

```python
# Backend Error Schema
class ValidationError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    field: Optional[str] = None
    
# FastAPI Exception Handler
@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    return JSONResponse(
        status_code=400,
        content={
            "message": str(exc),
            "code": "VALIDATION_ERROR", 
            "status": 400,
            "timestamp": datetime.utcnow().isoformat(),
            "details": exc.details if hasattr(exc, 'details') else None
        }
    )
```

**Contract Status**: ✅ **Error Contract Alignment**

### Validation Error Patterns
```typescript
// Frontend Error Handling
interface ValidationErrorDetail {
  field: string;
  message: string;
  code: string;
}

const handleValidationError = (error: ApiErrorResponse) => {
  if (error.code === 'VALIDATION_ERROR' && error.details) {
    const fieldErrors = error.details.field_errors || {};
    // Process field-specific errors
  }
};
```

```python
# Backend Validation Error Response
{
  "message": "Validation failed",
  "code": "VALIDATION_ERROR",
  "status": 400,
  "timestamp": "2024-01-15T10:30:00Z",
  "details": {
    "field_errors": {
      "min_detection_count": ["Value must be greater than 0"],
      "required_vru_types": ["Invalid VRU types: {'invalid_type'}"]
    }
  }
}
```

**Contract Status**: ✅ **Detailed Validation Error Alignment**

## WebSocket Contract Specifications

### Base Message Contract
```typescript
// Frontend WebSocket Message
interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;    // ISO timestamp
  id?: string;
}
```

```python
# Backend WebSocket Message
class WebSocketMessage(BaseModel):
    type: str
    payload: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    id: Optional[str] = None
```

**Contract Status**: ✅ **WebSocket Base Contract Alignment**

### Detection Event WebSocket
```typescript
// Frontend Detection WebSocket
interface DetectionWebSocketMessage extends WebSocketMessage<DetectionEventData> {
  type: 'detection_update' | 'detection_completed' | 'detection_failed';
}

interface DetectionEventData {
  videoId?: string;
  detectionId?: string;
  timestamp?: number;
  vruType?: VRUType;
  confidence?: number;
  boundingBox?: BoundingBox;
  processingTime?: number;
}
```

```python
# Backend Detection WebSocket
class DetectionEventWebSocket(WebSocketMessage):
    type: Literal['detection_update', 'detection_completed', 'detection_failed']
    payload: DetectionEventData

class DetectionEventData(BaseModel):
    video_id: Optional[str] = None        # Serializes as "videoId"
    detection_id: Optional[str] = None    # Serializes as "detectionId"  
    timestamp: Optional[float] = None
    vru_type: Optional[VRUType] = None    # Serializes as "vruType"
    confidence: Optional[float] = None
    bounding_box: Optional[Dict[str, float]] = None  # Serializes as "boundingBox"
    processing_time: Optional[float] = None          # Serializes as "processingTime"
```

**Contract Status**: ✅ **WebSocket Event Contract Alignment**

## Version Compatibility Strategy

### Backward Compatibility Approach

#### Frontend Compatibility Layer
```typescript
// Frontend handles multiple field variations
interface VideoFile {
  // Primary fields (current version)
  fileSize: number;
  frameRate?: number;
  createdAt: string;
  
  // Legacy compatibility (v1.x)  
  file_size?: number;
  fps?: number;
  created_at?: string;
  
  // Alternative names (v2.x)
  size?: number;
  frame_rate?: number;
  uploadedAt?: string;
}

// Utility function for field normalization
const normalizeVideoData = (video: any): VideoFile => {
  return {
    ...video,
    fileSize: video.fileSize || video.file_size || video.size || 0,
    frameRate: video.frameRate || video.fps || video.frame_rate,
    createdAt: video.createdAt || video.created_at || video.uploadedAt,
  };
};
```

#### Backend Version Support
```python
# Backend supports multiple API versions
class VideoResponse(CamelCaseModel):
    # Primary fields
    file_size: Optional[int] = None        # Serializes as "fileSize"
    
    # Legacy compatibility methods
    @property  
    def size(self) -> Optional[int]:
        """Legacy size field"""
        return self.file_size
        
    @property
    def fps(self) -> Optional[float]:
        """Legacy fps field"""
        return self.frame_rate
        
    def model_dump(self, by_alias=True, exclude_unset=False):
        """Enhanced serialization with legacy fields"""
        data = super().model_dump(by_alias=by_alias, exclude_unset=exclude_unset)
        
        # Add legacy fields for v1.x compatibility
        if self.file_size is not None:
            data['size'] = self.file_size
            data['file_size'] = self.file_size  # snake_case version
            
        if self.frame_rate is not None:
            data['fps'] = self.frame_rate
            data['frame_rate'] = self.frame_rate  # snake_case version
            
        return data
```

### API Versioning Strategy

#### URL-Based Versioning
```python
# Backend API Versioning
@app.get("/api/v1/projects")    # Legacy v1 API
@app.get("/api/v2/projects")    # Current v2 API  
@app.get("/projects")           # Latest API (v2)

# Version-specific response schemas
class ProjectResponseV1(BaseModel):
    # v1.x fields only
    pass
    
class ProjectResponseV2(CamelCaseModel):
    # v2.x fields with camelCase
    pass
```

#### Header-Based Versioning
```typescript
// Frontend API Version Headers
const apiClient = axios.create({
  headers: {
    'API-Version': '2.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
  }
});
```

### Migration Strategy

#### Gradual Field Deprecation
```python
# Backend Field Deprecation
class VideoResponse(CamelCaseModel):
    # Current field
    processing_status: str = Field(
        description="Current processing status"
    )
    
    # Deprecated field (maintained for compatibility)
    ground_truth_status: Optional[str] = Field(
        None, 
        deprecated=True,
        description="Deprecated: Use processing_status instead"
    )
    
    @field_validator('ground_truth_status', mode='before')
    @classmethod
    def map_deprecated_status(cls, v, values):
        """Map deprecated field to current field"""
        if not v and 'processing_status' in values:
            return values['processing_status']
        return v
```

#### Frontend Migration Warnings
```typescript
// Frontend Deprecation Handling
interface VideoFile {
  processingStatus: string;
  
  /** @deprecated Use processingStatus instead */
  groundTruthStatus?: string;
}

// Migration helper
const migrateVideoData = (video: any): VideoFile => {
  if (video.groundTruthStatus && !video.processingStatus) {
    console.warn('groundTruthStatus is deprecated, use processingStatus');
    video.processingStatus = video.groundTruthStatus;
  }
  return video;
};
```

## Contract Testing Strategy

### Automated Contract Testing
```python
# Backend Contract Tests
def test_project_response_contract():
    """Test that ProjectResponse matches frontend Project interface"""
    project = create_test_project()
    response_data = ProjectResponse.model_validate(project).model_dump(by_alias=True)
    
    # Verify required fields are present
    assert 'id' in response_data
    assert 'name' in response_data
    assert 'cameraModel' in response_data  # camelCase conversion
    assert 'cameraView' in response_data   # camelCase conversion
    assert 'signalType' in response_data   # camelCase conversion
    assert 'createdAt' in response_data    # camelCase conversion
    assert 'ownerId' in response_data      # camelCase conversion
    
    # Verify data types
    assert isinstance(response_data['id'], str)
    assert isinstance(response_data['name'], str)
    assert isinstance(response_data['createdAt'], str)  # ISO datetime
```

```typescript
// Frontend Contract Tests
describe('API Contract Tests', () => {
  test('Project response matches interface', async () => {
    const response = await api.get<Project>('/projects/123');
    const project: Project = response.data;
    
    // TypeScript ensures compile-time type checking
    expect(typeof project.id).toBe('string');
    expect(typeof project.name).toBe('string');
    expect(typeof project.cameraModel).toBe('string');
    expect(Object.values(CameraType)).toContain(project.cameraView);
    expect(Object.values(SignalType)).toContain(project.signalType);
    expect(typeof project.createdAt).toBe('string');
  });
});
```

### Contract Documentation Generation
```python
# Backend OpenAPI Schema Generation
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title="AI Model Validation Platform API",
        version="2.0.0",
        description="Complete API documentation with contract specifications",
        routes=app.routes,
    )
    
    # Add contract information
    openapi_schema["info"]["x-contract-version"] = "2.0"
    openapi_schema["info"]["x-frontend-compatibility"] = ["TypeScript 5.0+"]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

This comprehensive contract system ensures seamless integration between frontend and backend with strong type safety, backward compatibility, and clear migration paths.