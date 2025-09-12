# Data Transformation Patterns Documentation

## Overview
This document comprehensively documents all data transformation patterns used throughout the AI Model Validation Platform, including field name conversions, data format transformations, type mappings, serialization patterns, and compatibility layers between frontend and backend systems.

## Table of Contents
- [Transformation Architecture](#transformation-architecture)
- [Field Name Transformations](#field-name-transformations)
- [Data Format Transformations](#data-format-transformations)
- [Type System Mappings](#type-system-mappings)
- [Serialization Patterns](#serialization-patterns)
- [Legacy Compatibility Transformations](#legacy-compatibility-transformations)
- [Real-time Data Transformations](#real-time-data-transformations)
- [Performance Optimizations](#performance-optimizations)
- [Error Handling in Transformations](#error-handling-in-transformations)

## Transformation Architecture

### Multi-Layer Transformation System
```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (TypeScript)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Input Validation Layer                     │   │
│  │  • Form validation • API request preparation           │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            Data Normalization Layer                     │   │
│  │  • camelCase conversion • Type coercion • Defaults     │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                      API Boundary                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            Request/Response Transformation              │   │
│  │  • JSON serialization • Field mapping • Error format  │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                    Backend (Python)                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Pydantic Validation Layer                 │   │
│  │  • Schema validation • Field conversion • Constraints  │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │             Database Mapping Layer                      │   │
│  │  • SQLAlchemy ORM • Column mapping • Relationship mgmt │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Core Transformation Principles
1. **Bidirectional Conversion**: Support both directions of data flow
2. **Loss-less Transformation**: Preserve data integrity during conversion
3. **Performance Optimization**: Minimize transformation overhead
4. **Error Recovery**: Graceful handling of transformation failures
5. **Version Compatibility**: Support multiple data format versions

## Field Name Transformations

### Snake Case ↔ CamelCase Conversion

#### Backend: Automatic CamelCase Generation
```python
def snake_to_camel(snake_str: str) -> str:
    """
    Convert snake_case to camelCase for frontend compatibility
    
    Examples:
    - 'created_at' → 'createdAt'
    - 'camera_model' → 'cameraModel'  
    - 'ground_truth_generated' → 'groundTruthGenerated'
    - 'hil_testing_ready' → 'hilTestingReady'
    """
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

class CamelCaseModel(BaseModel):
    """Base model with automatic snake_case to camelCase conversion"""
    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,  # Accept both formats
        by_alias=True,          # Serialize with aliases
        from_attributes=True    # SQLAlchemy integration
    )

# Example schema with automatic conversion
class ProjectResponse(CamelCaseModel):
    camera_model: str          # Serialized as "cameraModel"
    camera_view: str           # Serialized as "cameraView"
    signal_type: str           # Serialized as "signalType"
    created_at: datetime       # Serialized as "createdAt"
    updated_at: datetime       # Serialized as "updatedAt"
    owner_id: str             # Serialized as "ownerId"
```

#### Frontend: Field Name Mapping
```typescript
// Comprehensive field name mappings for different scenarios
const FIELD_NAME_MAPPINGS = {
  // Project fields
  'camera_model': 'cameraModel',
  'camera_view': 'cameraView', 
  'signal_type': 'signalType',
  'frame_rate': 'frameRate',
  'lens_type': 'lensType',
  'owner_id': 'ownerId',
  'created_at': 'createdAt',
  'updated_at': 'updatedAt',
  
  // Video fields
  'file_size': 'fileSize',
  'file_path': 'filePath',
  'validation_status': 'validationStatus',
  'validation_type': 'validationType',
  'validated_at': 'validatedAt',
  'validated_by': 'validatedBy',
  'hil_testing_ready': 'hilTestingReady',
  'hil_testing_approved_by': 'hilTestingApprovedBy',
  'hil_testing_approved_at': 'hilTestingApprovedAt',
  'ground_truth_generated': 'groundTruthGenerated',
  'ground_truth_count': 'groundTruthCount',
  'ground_truth_quality_score': 'groundTruthQualityScore',
  'ground_truth_completed_at': 'groundTruthCompletedAt',
  
  // Detection fields
  'video_id': 'videoId',
  'detection_id': 'detectionId',
  'frame_number': 'frameNumber',
  'vru_type': 'vruType',
  'bounding_box': 'boundingBox',
  'ground_truth_match_id': 'groundTruthMatchId',
  'is_ground_truth': 'isGroundTruth',
  
  // Test session fields
  'project_id': 'projectId',
  'test_session_id': 'testSessionId',
  'tolerance_ms': 'toleranceMs',
  'started_at': 'startedAt',
  'completed_at': 'completedAt',
  'latency_threshold_ms': 'latencyThresholdMs',
  'video_start_timestamp': 'videoStartTimestamp',
  
  // LabJack timing fields
  'latency_ms': 'latencyMs',
  'labjack_timestamp': 'labjackTimestamp',
  'video_start_time': 'videoStartTime',
  'labjack_voltage': 'labjackVoltage',
  'latency_result': 'latencyResult',
  'voltage_level': 'voltageLevel',
  'detection_channel': 'detectionChannel'
} as const;

// Utility function for field name conversion
const convertFieldNames = <T extends Record<string, any>>(
  obj: T,
  mappings: Record<string, string>
): Record<string, any> => {
  const converted: Record<string, any> = {};
  
  Object.entries(obj).forEach(([key, value]) => {
    const convertedKey = mappings[key] || key;
    converted[convertedKey] = value;
  });
  
  return converted;
};

// Bidirectional conversion utilities
const toCamelCase = (obj: Record<string, any>): Record<string, any> =>
  convertFieldNames(obj, FIELD_NAME_MAPPINGS);

const toSnakeCase = (obj: Record<string, any>): Record<string, any> => {
  const reversedMappings = Object.fromEntries(
    Object.entries(FIELD_NAME_MAPPINGS).map(([snake, camel]) => [camel, snake])
  );
  return convertFieldNames(obj, reversedMappings);
};
```

### Complex Field Mappings

#### Bounding Box Coordinate Transformation
```python
# Backend: Individual coordinate fields to object
class DetectionEvent(Base):
    bounding_box_x = Column(Float, nullable=True)
    bounding_box_y = Column(Float, nullable=True) 
    bounding_box_width = Column(Float, nullable=True)
    bounding_box_height = Column(Float, nullable=True)
    
    @property
    def bounding_box(self) -> Optional[Dict[str, float]]:
        """Construct bounding box object from individual coordinates"""
        if self.bounding_box_x is not None:
            return {
                "x": self.bounding_box_x,
                "y": self.bounding_box_y,
                "width": self.bounding_box_width,
                "height": self.bounding_box_height
            }
        return None
    
    @bounding_box.setter
    def bounding_box(self, value: Optional[Dict[str, float]]) -> None:
        """Decompose bounding box object to individual coordinates"""
        if value is None:
            self.bounding_box_x = None
            self.bounding_box_y = None
            self.bounding_box_width = None
            self.bounding_box_height = None
        else:
            self.bounding_box_x = value.get("x")
            self.bounding_box_y = value.get("y")
            self.bounding_box_width = value.get("width")
            self.bounding_box_height = value.get("height")
```

```typescript
// Frontend: Bounding box validation and transformation
interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
  
  // Computed properties
  area?: number;
  centerX?: number;
  centerY?: number;
}

const transformBoundingBox = (raw: any): BoundingBox => {
  // Handle different input formats
  if (Array.isArray(raw)) {
    // Handle [x, y, width, height] format
    const [x, y, width, height] = raw;
    return { x, y, width, height };
  } else if (typeof raw === 'object' && raw !== null) {
    // Handle object format with validation
    const bbox: BoundingBox = {
      x: Number(raw.x || 0),
      y: Number(raw.y || 0),
      width: Number(raw.width || 0),
      height: Number(raw.height || 0)
    };
    
    // Add computed properties
    bbox.area = bbox.width * bbox.height;
    bbox.centerX = bbox.x + bbox.width / 2;
    bbox.centerY = bbox.y + bbox.height / 2;
    
    // Add confidence if present
    if (typeof raw.confidence === 'number') {
      bbox.confidence = raw.confidence;
    }
    
    return bbox;
  }
  
  throw new Error('Invalid bounding box format');
};

// Validation for bounding box coordinates
const validateBoundingBox = (bbox: BoundingBox): boolean => {
  return bbox.x >= 0 &&
         bbox.y >= 0 &&
         bbox.width > 0 &&
         bbox.height > 0 &&
         (bbox.confidence === undefined || (bbox.confidence >= 0 && bbox.confidence <= 1));
};
```

## Data Format Transformations

### Timestamp Transformations

#### Backend: DateTime Handling
```python
from datetime import datetime, timezone
import pytz

class DateTimeTransformer:
    """Comprehensive datetime transformation utilities"""
    
    @staticmethod
    def to_utc_iso(dt: datetime) -> str:
        """Convert datetime to UTC ISO string for frontend"""
        if dt.tzinfo is None:
            # Assume local timezone if not specified
            dt = pytz.utc.localize(dt)
        else:
            # Convert to UTC
            dt = dt.astimezone(pytz.utc)
        
        return dt.isoformat().replace('+00:00', 'Z')
    
    @staticmethod
    def from_iso_string(iso_str: str) -> datetime:
        """Parse ISO string to datetime object"""
        try:
            # Handle various ISO formats
            if iso_str.endswith('Z'):
                iso_str = iso_str[:-1] + '+00:00'
            
            return datetime.fromisoformat(iso_str)
        except ValueError:
            # Fallback for other formats
            from dateutil.parser import parse
            return parse(iso_str)
    
    @staticmethod
    def to_timestamp(dt: datetime) -> float:
        """Convert datetime to Unix timestamp"""
        return dt.timestamp()
    
    @staticmethod
    def from_timestamp(ts: float) -> datetime:
        """Convert Unix timestamp to datetime"""
        return datetime.fromtimestamp(ts, tz=timezone.utc)

# Usage in Pydantic models
class TimestampModel(CamelCaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def model_dump(self, **kwargs):
        """Custom serialization with datetime conversion"""
        data = super().model_dump(**kwargs)
        
        # Convert datetime fields to ISO strings
        if 'createdAt' in data and data['createdAt']:
            data['createdAt'] = DateTimeTransformer.to_utc_iso(self.created_at)
        
        if 'updatedAt' in data and data['updatedAt']:
            data['updatedAt'] = DateTimeTransformer.to_utc_iso(self.updated_at)
        
        return data
```

#### Frontend: Date Processing
```typescript
// Comprehensive date handling utilities
class DateTransformer {
  /**
   * Parse API date string to Date object
   */
  static parseApiDate(dateStr: string): Date {
    if (!dateStr) {
      throw new Error('Date string is required');
    }
    
    // Handle various date formats from API
    const date = new Date(dateStr);
    
    if (isNaN(date.getTime())) {
      throw new Error(`Invalid date format: ${dateStr}`);
    }
    
    return date;
  }
  
  /**
   * Format date for API request
   */
  static formatForApi(date: Date): string {
    return date.toISOString();
  }
  
  /**
   * Format date for display
   */
  static formatForDisplay(date: Date | string): string {
    const dateObj = typeof date === 'string' ? this.parseApiDate(date) : date;
    
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    }).format(dateObj);
  }
  
  /**
   * Calculate relative time (e.g., "2 hours ago")
   */
  static getRelativeTime(date: Date | string): string {
    const dateObj = typeof date === 'string' ? this.parseApiDate(date) : date;
    const now = new Date();
    const diffMs = now.getTime() - dateObj.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin} minute${diffMin > 1 ? 's' : ''} ago`;
    if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
    if (diffDay < 30) return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
    
    return this.formatForDisplay(dateObj);
  }
  
  /**
   * Convert timestamp to date
   */
  static fromTimestamp(timestamp: number): Date {
    return new Date(timestamp * 1000); // Convert seconds to milliseconds
  }
  
  /**
   * Convert date to timestamp
   */
  static toTimestamp(date: Date): number {
    return Math.floor(date.getTime() / 1000); // Convert milliseconds to seconds
  }
}

// Usage in components
const VideoCard: React.FC<{ video: VideoFile }> = ({ video }) => {
  const createdDate = DateTransformer.parseApiDate(video.createdAt);
  const relativeTime = DateTransformer.getRelativeTime(createdDate);
  const formattedDate = DateTransformer.formatForDisplay(createdDate);
  
  return (
    <div>
      <h3>{video.filename}</h3>
      <p title={formattedDate}>{relativeTime}</p>
    </div>
  );
};
```

### File Size Transformations

#### Consistent File Size Formatting
```typescript
// Frontend: Human-readable file size formatting
class FileSizeTransformer {
  /**
   * Convert bytes to human-readable format
   */
  static formatBytes(bytes: number, decimals: number = 2): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
  }
  
  /**
   * Parse human-readable size to bytes
   */
  static parseSize(sizeStr: string): number {
    const units = {
      'B': 1, 'BYTES': 1,
      'KB': 1024, 'K': 1024,
      'MB': 1024 * 1024, 'M': 1024 * 1024,
      'GB': 1024 * 1024 * 1024, 'G': 1024 * 1024 * 1024,
      'TB': 1024 * 1024 * 1024 * 1024, 'T': 1024 * 1024 * 1024 * 1024
    };
    
    const regex = /^(\d*\.?\d+)\s*([KMGT]?B?|BYTES?)$/i;
    const match = sizeStr.trim().toUpperCase().match(regex);
    
    if (!match) {
      throw new Error(`Invalid size format: ${sizeStr}`);
    }
    
    const value = parseFloat(match[1]);
    const unit = match[2] || 'B';
    const multiplier = units[unit as keyof typeof units];
    
    if (!multiplier) {
      throw new Error(`Unknown size unit: ${unit}`);
    }
    
    return Math.round(value * multiplier);
  }
  
  /**
   * Validate file size constraints
   */
  static validateSize(bytes: number, maxSize: number = 100 * 1024 * 1024): boolean {
    return bytes > 0 && bytes <= maxSize;
  }
  
  /**
   * Get file size category
   */
  static getSizeCategory(bytes: number): 'small' | 'medium' | 'large' | 'huge' {
    if (bytes < 1024 * 1024) return 'small';      // < 1MB
    if (bytes < 10 * 1024 * 1024) return 'medium'; // < 10MB
    if (bytes < 100 * 1024 * 1024) return 'large'; // < 100MB
    return 'huge';                                  // >= 100MB
  }
}

// Backend: File size validation and processing
class FileSizeValidator:
    """Backend file size validation and processing"""
    
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    @staticmethod
    def validate_file_size(file_size: int) -> bool:
        """Validate file size within limits"""
        return 0 < file_size <= FileSizeValidator.MAX_FILE_SIZE
    
    @staticmethod
    def format_size(bytes_size: int) -> str:
        """Format file size for logging/display"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"
    
    @staticmethod
    def get_size_constraints() -> Dict[str, int]:
        """Get file size constraints for API documentation"""
        return {
            "min_size": 1,
            "max_size": FileSizeValidator.MAX_FILE_SIZE,
            "recommended_max": 50 * 1024 * 1024  # 50MB
        }
```

## Type System Mappings

### Enum Value Mappings

#### Camera Type Transformation
```python
# Backend: Camera type enum
class CameraTypeEnum(str, Enum):
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE_SCENARIOS = "Multi-angle"

# Transformation to frontend format
CAMERA_TYPE_MAPPING = {
    "Front-facing VRU": "front_facing_vru",
    "Rear-facing VRU": "rear_facing_vru", 
    "In-Cab Driver Behavior": "in_cab_driver_behavior",
    "Multi-angle": "multi_angle"
}

def transform_camera_type_for_frontend(backend_value: str) -> str:
    """Transform backend camera type to frontend format"""
    return CAMERA_TYPE_MAPPING.get(backend_value, backend_value.lower().replace(" ", "_").replace("-", "_"))
```

```typescript
// Frontend: Camera type enum and mapping
export enum CameraType {
  FRONT_FACING = "front_facing",
  FRONT_FACING_VRU = "front_facing_vru",
  SIDE_VIEW = "side_view",
  REAR_VIEW = "rear_view",
  IN_CAB_DRIVER_BEHAVIOR = "in_cab_driver_behavior",
  MULTI_ANGLE = "multi_angle"
}

// Mapping from backend values
const BACKEND_CAMERA_TYPE_MAPPING: Record<string, CameraType> = {
  "Front-facing VRU": CameraType.FRONT_FACING_VRU,
  "Rear-facing VRU": CameraType.REAR_VIEW,
  "In-Cab Driver Behavior": CameraType.IN_CAB_DRIVER_BEHAVIOR,
  "Multi-angle": CameraType.MULTI_ANGLE
};

const transformCameraTypeFromBackend = (backendValue: string): CameraType => {
  const mapped = BACKEND_CAMERA_TYPE_MAPPING[backendValue];
  if (mapped) return mapped;
  
  // Fallback transformation
  const normalized = backendValue
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/-/g, '_');
    
  return Object.values(CameraType).find(type => type === normalized) || CameraType.FRONT_FACING;
};
```

### Status System Mappings

#### Video Status Transformation Matrix
```typescript
// Comprehensive status transformation system
interface StatusTransformation {
  // New unified status system
  status: VideoValidationStatus;
  validationStatus: ValidationStatus;
  
  // Legacy status fields
  legacyStatus?: string;
  processingStatus?: string;
  groundTruthStatus?: string;
  
  // Computed flags
  groundTruthGenerated?: boolean;
  hilTestingReady?: boolean;
}

class StatusTransformer {
  // Status transformation matrix
  private static readonly STATUS_MATRIX: Record<VideoValidationStatus, StatusTransformation> = {
    [VideoValidationStatus.UPLOADED]: {
      status: VideoValidationStatus.UPLOADED,
      validationStatus: ValidationStatus.PENDING,
      legacyStatus: "uploaded",
      processingStatus: "pending",
      groundTruthStatus: "pending",
      groundTruthGenerated: false,
      hilTestingReady: false
    },
    
    [VideoValidationStatus.PROCESSING]: {
      status: VideoValidationStatus.PROCESSING,
      validationStatus: ValidationStatus.PROCESSING,
      legacyStatus: "processing",
      processingStatus: "processing",
      groundTruthStatus: "processing",
      groundTruthGenerated: false,
      hilTestingReady: false
    },
    
    [VideoValidationStatus.PROCESSING_FAILED]: {
      status: VideoValidationStatus.PROCESSING_FAILED,
      validationStatus: ValidationStatus.FAILED,
      legacyStatus: "error",
      processingStatus: "failed",
      groundTruthStatus: "failed",
      groundTruthGenerated: false,
      hilTestingReady: false
    },
    
    [VideoValidationStatus.ANNOTATED]: {
      status: VideoValidationStatus.ANNOTATED,
      validationStatus: ValidationStatus.PENDING_VALIDATION,
      legacyStatus: "completed",
      processingStatus: "completed",
      groundTruthStatus: "completed",
      groundTruthGenerated: true,
      hilTestingReady: false
    },
    
    [VideoValidationStatus.VALIDATING]: {
      status: VideoValidationStatus.VALIDATING,
      validationStatus: ValidationStatus.VALIDATING,
      legacyStatus: "processing",
      processingStatus: "validating",
      groundTruthStatus: "validating",
      groundTruthGenerated: true,
      hilTestingReady: false
    },
    
    [VideoValidationStatus.VALIDATED]: {
      status: VideoValidationStatus.VALIDATED,
      validationStatus: ValidationStatus.VALIDATED,
      legacyStatus: "validated",
      processingStatus: "completed",
      groundTruthStatus: "validated",
      groundTruthGenerated: true,
      hilTestingReady: false
    },
    
    [VideoValidationStatus.READY_FOR_TESTING]: {
      status: VideoValidationStatus.READY_FOR_TESTING,
      validationStatus: ValidationStatus.VALIDATED,
      legacyStatus: "completed",
      processingStatus: "completed",
      groundTruthStatus: "ready_for_testing",
      groundTruthGenerated: true,
      hilTestingReady: true
    },
    
    [VideoValidationStatus.IN_TESTING]: {
      status: VideoValidationStatus.IN_TESTING,
      validationStatus: ValidationStatus.VALIDATED,
      legacyStatus: "completed",
      processingStatus: "testing",
      groundTruthStatus: "in_testing",
      groundTruthGenerated: true,
      hilTestingReady: true
    },
    
    [VideoValidationStatus.TESTED]: {
      status: VideoValidationStatus.TESTED,
      validationStatus: ValidationStatus.VALIDATED,
      legacyStatus: "completed",
      processingStatus: "completed",
      groundTruthStatus: "tested",
      groundTruthGenerated: true,
      hilTestingReady: true
    },
    
    [VideoValidationStatus.ARCHIVED]: {
      status: VideoValidationStatus.ARCHIVED,
      validationStatus: ValidationStatus.VALIDATED,
      legacyStatus: "archived",
      processingStatus: "archived",
      groundTruthStatus: "archived",
      groundTruthGenerated: true,
      hilTestingReady: true
    },
    
    [VideoValidationStatus.ERROR]: {
      status: VideoValidationStatus.ERROR,
      validationStatus: ValidationStatus.FAILED,
      legacyStatus: "error",
      processingStatus: "error",
      groundTruthStatus: "error",
      groundTruthGenerated: false,
      hilTestingReady: false
    }
  };
  
  /**
   * Transform video data with comprehensive status mapping
   */
  static transformVideoWithStatus(videoData: any): VideoFile {
    const primaryStatus = videoData.status as VideoValidationStatus;
    const statusInfo = this.STATUS_MATRIX[primaryStatus];
    
    return {
      ...videoData,
      status: primaryStatus,
      validationStatus: statusInfo.validationStatus,
      
      // Legacy compatibility fields
      processingStatus: statusInfo.processingStatus,
      processing_status: statusInfo.processingStatus, // snake_case
      groundTruthStatus: statusInfo.groundTruthStatus,
      ground_truth_status: statusInfo.groundTruthStatus, // snake_case
      groundTruthGenerated: statusInfo.groundTruthGenerated,
      ground_truth_generated: statusInfo.groundTruthGenerated, // snake_case
      hilTestingReady: statusInfo.hilTestingReady,
      hil_testing_ready: statusInfo.hilTestingReady // snake_case
    };
  }
  
  /**
   * Get legacy status from unified status
   */
  static toLegacyStatus(status: VideoValidationStatus): string {
    return this.STATUS_MATRIX[status]?.legacyStatus || "unknown";
  }
  
  /**
   * Convert legacy status to unified status
   */
  static fromLegacyStatus(legacyStatus: string): VideoValidationStatus {
    for (const [status, info] of Object.entries(this.STATUS_MATRIX)) {
      if (info.legacyStatus === legacyStatus) {
        return status as VideoValidationStatus;
      }
    }
    return VideoValidationStatus.UPLOADED; // Default fallback
  }
  
  /**
   * Check if status transition is valid
   */
  static isValidTransition(from: VideoValidationStatus, to: VideoValidationStatus): boolean {
    const validTransitions: Record<VideoValidationStatus, VideoValidationStatus[]> = {
      [VideoValidationStatus.UPLOADED]: [
        VideoValidationStatus.PROCESSING,
        VideoValidationStatus.ERROR
      ],
      [VideoValidationStatus.PROCESSING]: [
        VideoValidationStatus.ANNOTATED,
        VideoValidationStatus.PROCESSING_FAILED
      ],
      [VideoValidationStatus.ANNOTATED]: [
        VideoValidationStatus.VALIDATING,
        VideoValidationStatus.VALIDATED
      ],
      [VideoValidationStatus.VALIDATING]: [
        VideoValidationStatus.VALIDATED,
        VideoValidationStatus.VALIDATION_FAILED
      ],
      [VideoValidationStatus.VALIDATED]: [
        VideoValidationStatus.READY_FOR_TESTING
      ],
      [VideoValidationStatus.READY_FOR_TESTING]: [
        VideoValidationStatus.IN_TESTING
      ],
      [VideoValidationStatus.IN_TESTING]: [
        VideoValidationStatus.TESTED
      ],
      [VideoValidationStatus.TESTED]: [
        VideoValidationStatus.ARCHIVED
      ],
      // Error states can transition back to processing
      [VideoValidationStatus.PROCESSING_FAILED]: [
        VideoValidationStatus.PROCESSING
      ],
      [VideoValidationStatus.VALIDATION_FAILED]: [
        VideoValidationStatus.VALIDATING
      ],
      [VideoValidationStatus.ERROR]: [
        VideoValidationStatus.PROCESSING
      ],
      [VideoValidationStatus.ARCHIVED]: [] // Terminal state
    };
    
    return validTransitions[from]?.includes(to) || false;
  }
}
```

## Serialization Patterns

### API Response Serialization

#### Backend Response Serialization
```python
class EnhancedResponseSerializer:
    """Advanced response serialization with transformation support"""
    
    @staticmethod
    def serialize_project(project: Project) -> Dict[str, Any]:
        """Serialize project with comprehensive field mapping"""
        base_data = ProjectResponse.model_validate(project).model_dump(by_alias=True)
        
        # Add computed fields
        base_data.update({
            'videoCount': len(project.videos) if project.videos else 0,
            'testsCount': len(project.test_sessions) if project.test_sessions else 0,
            'totalAnnotations': sum(
                len(video.annotations) for video in project.videos
            ) if project.videos else 0,
            'averageAccuracy': EnhancedResponseSerializer._calculate_average_accuracy(project)
        })
        
        return base_data
    
    @staticmethod
    def serialize_video(video: Video) -> Dict[str, Any]:
        """Serialize video with status transformation and compatibility"""
        base_data = VideoResponse.model_validate(video).model_dump(by_alias=True)
        
        # Add status transformations
        status_info = StatusTransformer.STATUS_MATRIX.get(video.status, {})
        base_data.update({
            'processingStatus': status_info.get('processingStatus', 'unknown'),
            'processing_status': status_info.get('processingStatus', 'unknown'),
            'groundTruthStatus': status_info.get('groundTruthStatus', 'unknown'),
            'ground_truth_status': status_info.get('groundTruthStatus', 'unknown'),
            'hilTestingReady': video.hil_testing_ready,
            'hil_testing_ready': video.hil_testing_ready
        })
        
        # Add legacy compatibility fields
        base_data.update({
            'uploadedAt': video.created_at.isoformat() if video.created_at else None,
            'uploaded_at': video.created_at.isoformat() if video.created_at else None,
            'size': video.file_size,
            'fps': video.fps,
            'frame_rate': video.fps,
            'originalName': video.filename,
            'original_name': video.filename,
            'name': video.filename,
            'url': f"/api/videos/{video.id}/stream" if video.file_path else None
        })
        
        return base_data
    
    @staticmethod
    def serialize_detection(detection: DetectionEvent) -> Dict[str, Any]:
        """Serialize detection with bounding box and LabJack data"""
        base_data = {
            'id': detection.id,
            'videoId': detection.video_id,
            'video_id': detection.video_id,
            'detectionId': detection.detection_id,
            'detection_id': detection.detection_id,
            'testSessionId': detection.test_session_id,
            'test_session_id': detection.test_session_id,
            'timestamp': detection.timestamp,
            'frameNumber': detection.frame_number,
            'frame_number': detection.frame_number,
            'vruType': detection.vru_type,
            'vru_type': detection.vru_type,
            'classLabel': detection.class_label,  # Legacy field
            'class_label': detection.class_label,
            'confidence': detection.confidence,
            'validationStatus': detection.validation_result,
            'validation_result': detection.validation_result,
            'createdAt': detection.created_at.isoformat() if detection.created_at else None,
            'created_at': detection.created_at.isoformat() if detection.created_at else None
        }
        
        # Add bounding box transformation
        if detection.bounding_box:
            base_data.update({
                'boundingBox': detection.bounding_box,
                'bounding_box': detection.bounding_box
            })
        
        # Add LabJack timing data
        if detection.latency_ms is not None:
            base_data.update({
                'latencyMs': detection.latency_ms,
                'latency_ms': detection.latency_ms,
                'labjackTimestamp': detection.labjack_timestamp,
                'labjack_timestamp': detection.labjack_timestamp,
                'voltageLevel': detection.voltage_level,
                'voltage_level': detection.voltage_level,
                'detectionChannel': detection.detection_channel,
                'detection_channel': detection.detection_channel,
                'latencyResult': detection.latency_result,
                'latency_result': detection.latency_result
            })
        
        return base_data
```

#### Frontend Request Serialization
```typescript
class RequestSerializer {
  /**
   * Serialize project creation request
   */
  static serializeProjectCreate(project: ProjectCreate): Record<string, any> {
    return {
      name: project.name,
      description: project.description,
      camera_model: project.cameraModel, // Convert to snake_case
      camera_view: project.cameraView,
      signal_type: project.signalType,    // Convert to snake_case
      lens_type: project.lensType,        // Convert to snake_case
      resolution: project.resolution,
      frame_rate: project.frameRate       // Convert to snake_case
    };
  }
  
  /**
   * Serialize annotation creation request
   */
  static serializeAnnotationCreate(annotation: any): Record<string, any> {
    return {
      detection_id: annotation.detectionId,
      frame_number: annotation.frameNumber,
      timestamp: annotation.timestamp,
      end_timestamp: annotation.endTimestamp,
      vru_type: annotation.vruType,
      bounding_box: {
        x: annotation.boundingBox.x,
        y: annotation.boundingBox.y,
        width: annotation.boundingBox.width,
        height: annotation.boundingBox.height,
        confidence: annotation.boundingBox.confidence
      },
      occluded: annotation.occluded || false,
      truncated: annotation.truncated || false,
      difficult: annotation.difficult || false,
      notes: annotation.notes,
      annotator: annotation.annotator,
      validated: annotation.validated || false
    };
  }
  
  /**
   * Serialize test session creation request
   */
  static serializeTestSessionCreate(session: TestSessionCreate): Record<string, any> {
    return {
      name: session.name,
      project_id: session.projectId,      // Convert to snake_case
      video_id: session.videoId,          // Convert to snake_case
      tolerance_ms: session.toleranceMs,  // Convert to snake_case
      config: session.config
    };
  }
}
```

## Legacy Compatibility Transformations

### Backward Compatibility Layer

#### Multi-Version Field Support
```typescript
// Support for multiple API versions and field naming conventions
interface LegacyVideoFile extends VideoFile {
  // v1.0 compatibility
  file_size?: number;           // snake_case file size
  fps?: number;                 // alternative to frameRate
  created_at?: string;          // snake_case created timestamp
  processing_status?: string;   // legacy processing status
  
  // v1.5 compatibility  
  ground_truth_generated?: boolean;  // snake_case ground truth flag
  ground_truth_status?: string;      // legacy ground truth status
  detection_count?: number;          // snake_case detection count
  
  // v2.0 compatibility
  size?: number;                     // alternative file size field
  frame_rate?: number;               // snake_case frame rate
  original_name?: string;            // snake_case original name
  uploaded_at?: string;              // legacy upload timestamp
  
  // Alternative naming
  name?: string;                     // alternative to filename
  url?: string;                      // file access URL
}

class LegacyCompatibilityTransformer {
  /**
   * Transform modern VideoFile to legacy format
   */
  static toLegacyFormat(video: VideoFile): LegacyVideoFile {
    return {
      ...video,
      
      // v1.0 compatibility
      file_size: video.fileSize,
      fps: video.frameRate,
      created_at: video.createdAt,
      processing_status: StatusTransformer.toLegacyStatus(video.status),
      
      // v1.5 compatibility
      ground_truth_generated: video.groundTruthGenerated,
      ground_truth_status: this.mapToLegacyGroundTruthStatus(video.status),
      detection_count: video.detectionCount,
      
      // v2.0 compatibility
      size: video.fileSize,
      frame_rate: video.frameRate,
      original_name: video.originalName || video.filename,
      uploaded_at: video.createdAt,
      
      // Alternative naming
      name: video.filename,
      url: `/api/videos/${video.id}/stream`
    };
  }
  
  /**
   * Transform legacy format to modern VideoFile
   */
  static fromLegacyFormat(legacyVideo: any): VideoFile {
    return {
      id: legacyVideo.id,
      filename: legacyVideo.filename || legacyVideo.name,
      fileSize: legacyVideo.fileSize || legacyVideo.file_size || legacyVideo.size || 0,
      status: this.mapFromLegacyStatus(legacyVideo.processing_status || legacyVideo.status),
      validationStatus: this.mapFromLegacyValidationStatus(legacyVideo.ground_truth_status),
      groundTruthGenerated: legacyVideo.groundTruthGenerated || legacyVideo.ground_truth_generated || false,
      groundTruthCount: legacyVideo.groundTruthCount || legacyVideo.detection_count || 0,
      detectionCount: legacyVideo.detectionCount || legacyVideo.detection_count || 0,
      annotationCount: legacyVideo.annotationCount || 0,
      frameRate: legacyVideo.frameRate || legacyVideo.fps || legacyVideo.frame_rate,
      createdAt: legacyVideo.createdAt || legacyVideo.created_at || legacyVideo.uploaded_at || new Date().toISOString(),
      updatedAt: legacyVideo.updatedAt || legacyVideo.updated_at,
      
      // Modern fields with defaults
      hilTestingReady: legacyVideo.hilTestingReady || false,
      validationType: legacyVideo.validationType,
      validatedAt: legacyVideo.validatedAt,
      validatedBy: legacyVideo.validatedBy,
      projectId: legacyVideo.projectId || legacyVideo.project_id,
      
      // Optional fields
      filePath: legacyVideo.filePath || legacyVideo.file_path,
      duration: legacyVideo.duration,
      width: legacyVideo.width,
      height: legacyVideo.height,
      originalName: legacyVideo.originalName || legacyVideo.original_name
    };
  }
  
  private static mapToLegacyGroundTruthStatus(status: VideoValidationStatus): string {
    const statusMap: Record<VideoValidationStatus, string> = {
      [VideoValidationStatus.UPLOADED]: "pending",
      [VideoValidationStatus.PROCESSING]: "processing",
      [VideoValidationStatus.PROCESSING_FAILED]: "failed",
      [VideoValidationStatus.ANNOTATED]: "completed",
      [VideoValidationStatus.VALIDATING]: "validating",
      [VideoValidationStatus.VALIDATION_FAILED]: "failed",
      [VideoValidationStatus.VALIDATED]: "validated",
      [VideoValidationStatus.READY_FOR_TESTING]: "ready",
      [VideoValidationStatus.IN_TESTING]: "testing",
      [VideoValidationStatus.TESTED]: "completed",
      [VideoValidationStatus.ARCHIVED]: "archived",
      [VideoValidationStatus.ERROR]: "error"
    };
    
    return statusMap[status] || "unknown";
  }
  
  private static mapFromLegacyStatus(legacyStatus?: string): VideoValidationStatus {
    const statusMap: Record<string, VideoValidationStatus> = {
      "uploaded": VideoValidationStatus.UPLOADED,
      "processing": VideoValidationStatus.PROCESSING,
      "completed": VideoValidationStatus.ANNOTATED,
      "validated": VideoValidationStatus.VALIDATED,
      "failed": VideoValidationStatus.PROCESSING_FAILED,
      "error": VideoValidationStatus.ERROR
    };
    
    return statusMap[legacyStatus || ""] || VideoValidationStatus.UPLOADED;
  }
  
  private static mapFromLegacyValidationStatus(legacyValidationStatus?: string): ValidationStatus {
    const statusMap: Record<string, ValidationStatus> = {
      "pending": ValidationStatus.PENDING,
      "processing": ValidationStatus.PROCESSING,
      "validating": ValidationStatus.VALIDATING,
      "validated": ValidationStatus.VALIDATED,
      "failed": ValidationStatus.FAILED,
      "error": ValidationStatus.FAILED
    };
    
    return statusMap[legacyValidationStatus || ""] || ValidationStatus.PENDING;
  }
}
```

## Real-time Data Transformations

### WebSocket Message Transformations

#### Bidirectional WebSocket Data Conversion
```typescript
// WebSocket message transformation for real-time updates
class WebSocketMessageTransformer {
  /**
   * Transform incoming WebSocket message
   */
  static transformIncomingMessage<T>(rawMessage: any): WebSocketMessage<T> {
    // Validate message structure
    if (!rawMessage || typeof rawMessage !== 'object') {
      throw new Error('Invalid WebSocket message format');
    }
    
    const baseMessage: WebSocketMessage<T> = {
      type: rawMessage.type || 'unknown',
      payload: rawMessage.payload || {},
      timestamp: rawMessage.timestamp || new Date().toISOString(),
      id: rawMessage.id
    };
    
    // Transform payload based on message type
    switch (baseMessage.type) {
      case 'detection_update':
        baseMessage.payload = this.transformDetectionPayload(rawMessage.payload);
        break;
        
      case 'video_status_update':
        baseMessage.payload = this.transformVideoStatusPayload(rawMessage.payload);
        break;
        
      case 'annotation_created':
        baseMessage.payload = this.transformAnnotationPayload(rawMessage.payload);
        break;
        
      case 'test_session_update':
        baseMessage.payload = this.transformTestSessionPayload(rawMessage.payload);
        break;
        
      default:
        // Generic payload transformation
        baseMessage.payload = this.transformGenericPayload(rawMessage.payload);
    }
    
    return baseMessage;
  }
  
  /**
   * Transform detection update payload
   */
  private static transformDetectionPayload(payload: any): DetectionEventData {
    return {
      videoId: payload.video_id || payload.videoId,
      detectionId: payload.detection_id || payload.detectionId,
      timestamp: payload.timestamp,
      vruType: payload.vru_type || payload.vruType,
      confidence: payload.confidence,
      boundingBox: payload.bounding_box || payload.boundingBox ? {
        x: payload.bounding_box?.x || payload.boundingBox?.x || 0,
        y: payload.bounding_box?.y || payload.boundingBox?.y || 0,
        width: payload.bounding_box?.width || payload.boundingBox?.width || 0,
        height: payload.bounding_box?.height || payload.boundingBox?.height || 0
      } : undefined,
      success: payload.success,
      processingTime: payload.processing_time || payload.processingTime,
      latencyMs: payload.latency_ms || payload.latencyMs,
      labjackTimestamp: payload.labjack_timestamp || payload.labjackTimestamp
    };
  }
  
  /**
   * Transform video status update payload  
   */
  private static transformVideoStatusPayload(payload: any): VideoStatusUpdateData {
    return {
      videoId: payload.video_id || payload.videoId,
      status: payload.status,
      validationStatus: payload.validation_status || payload.validationStatus,
      progress: payload.progress,
      message: payload.message,
      processingStatus: payload.processing_status || payload.processingStatus,
      groundTruthGenerated: payload.ground_truth_generated || payload.groundTruthGenerated,
      detectionCount: payload.detection_count || payload.detectionCount
    };
  }
  
  /**
   * Transform outgoing WebSocket message
   */
  static transformOutgoingMessage(message: WebSocketMessage): any {
    const transformed = {
      type: message.type,
      timestamp: message.timestamp,
      id: message.id
    };
    
    // Convert payload to snake_case for backend
    if (message.payload && typeof message.payload === 'object') {
      transformed.payload = this.convertToSnakeCase(message.payload);
    } else {
      transformed.payload = message.payload;
    }
    
    return transformed;
  }
  
  /**
   * Convert object keys to snake_case
   */
  private static convertToSnakeCase(obj: any): any {
    if (Array.isArray(obj)) {
      return obj.map(item => this.convertToSnakeCase(item));
    }
    
    if (obj && typeof obj === 'object') {
      const converted: any = {};
      
      Object.entries(obj).forEach(([key, value]) => {
        const snakeKey = key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
        converted[snakeKey] = this.convertToSnakeCase(value);
      });
      
      return converted;
    }
    
    return obj;
  }
}

// Usage in WebSocket connection
class WebSocketConnection {
  private ws: WebSocket;
  
  constructor(url: string) {
    this.ws = new WebSocket(url);
    this.setupEventHandlers();
  }
  
  private setupEventHandlers(): void {
    this.ws.onmessage = (event) => {
      try {
        const rawMessage = JSON.parse(event.data);
        const transformedMessage = WebSocketMessageTransformer.transformIncomingMessage(rawMessage);
        this.handleMessage(transformedMessage);
      } catch (error) {
        console.error('Failed to transform WebSocket message:', error);
      }
    };
  }
  
  private handleMessage<T>(message: WebSocketMessage<T>): void {
    // Handle transformed message
    switch (message.type) {
      case 'detection_update':
        this.handleDetectionUpdate(message as WebSocketMessage<DetectionEventData>);
        break;
      case 'video_status_update':
        this.handleVideoStatusUpdate(message as WebSocketMessage<VideoStatusUpdateData>);
        break;
      // Handle other message types...
    }
  }
  
  sendMessage<T>(message: WebSocketMessage<T>): void {
    const transformedMessage = WebSocketMessageTransformer.transformOutgoingMessage(message);
    this.ws.send(JSON.stringify(transformedMessage));
  }
}
```

## Performance Optimizations

### Transformation Caching
```typescript
// Cache frequently transformed data to improve performance
class TransformationCache {
  private static readonly cache = new Map<string, any>();
  private static readonly maxCacheSize = 1000;
  private static readonly cacheTTL = 5 * 60 * 1000; // 5 minutes
  
  /**
   * Get cached transformation result
   */
  static get<T>(key: string): T | null {
    const cached = this.cache.get(key);
    
    if (!cached) {
      return null;
    }
    
    // Check TTL
    if (Date.now() - cached.timestamp > this.cacheTTL) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.data;
  }
  
  /**
   * Set cached transformation result
   */
  static set<T>(key: string, data: T): void {
    // Prevent cache from growing too large
    if (this.cache.size >= this.maxCacheSize) {
      // Remove oldest entries (simple LRU)
      const oldestKey = this.cache.keys().next().value;
      this.cache.delete(oldestKey);
    }
    
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }
  
  /**
   * Clear cache
   */
  static clear(): void {
    this.cache.clear();
  }
  
  /**
   * Generate cache key from object
   */
  static generateKey(prefix: string, obj: any): string {
    const objStr = JSON.stringify(obj, Object.keys(obj).sort());
    return `${prefix}:${this.hashCode(objStr)}`;
  }
  
  private static hashCode(str: string): string {
    let hash = 0;
    if (str.length === 0) return hash.toString();
    
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    
    return hash.toString();
  }
}

// Usage with caching
class CachedTransformer {
  static transformVideoWithCache(videoData: any): VideoFile {
    const cacheKey = TransformationCache.generateKey('video_transform', videoData);
    let transformed = TransformationCache.get<VideoFile>(cacheKey);
    
    if (!transformed) {
      transformed = StatusTransformer.transformVideoWithStatus(videoData);
      TransformationCache.set(cacheKey, transformed);
    }
    
    return transformed;
  }
}
```

### Batch Transformations
```typescript
// Optimize transformations for large datasets
class BatchTransformer {
  /**
   * Transform multiple videos efficiently
   */
  static transformVideoBatch(videos: any[]): VideoFile[] {
    // Pre-compile transformation functions
    const statusMatrix = StatusTransformer.STATUS_MATRIX;
    
    return videos.map(video => {
      // Direct transformation without function calls for performance
      const primaryStatus = video.status as VideoValidationStatus;
      const statusInfo = statusMatrix[primaryStatus];
      
      return {
        id: video.id,
        filename: video.filename,
        fileSize: video.file_size || video.fileSize || 0,
        status: primaryStatus,
        validationStatus: statusInfo?.validationStatus || ValidationStatus.PENDING,
        
        // Direct field mapping
        groundTruthGenerated: statusInfo?.groundTruthGenerated || false,
        hilTestingReady: statusInfo?.hilTestingReady || false,
        createdAt: video.created_at || video.createdAt,
        
        // Computed fields
        processingStatus: statusInfo?.processingStatus || 'unknown',
        groundTruthStatus: statusInfo?.groundTruthStatus || 'unknown',
        
        // Additional fields...
        detectionCount: video.detection_count || video.detectionCount || 0,
        annotationCount: video.annotation_count || video.annotationCount || 0,
        projectId: video.project_id || video.projectId
      } as VideoFile;
    });
  }
  
  /**
   * Transform detection events in batches
   */
  static transformDetectionBatch(detections: any[]): Detection[] {
    return detections.map(detection => ({
      id: detection.id,
      videoId: detection.video_id || detection.videoId,
      detectionId: detection.detection_id || detection.detectionId,
      frameNumber: detection.frame_number || detection.frameNumber || 0,
      timestamp: detection.timestamp || 0,
      classId: detection.class_id || detection.classId || 0,
      className: detection.class_label || detection.className || 'unknown',
      vruType: detection.vru_type || detection.vruType || VRUType.PEDESTRIAN,
      confidence: detection.confidence || 0,
      boundingBox: this.transformBoundingBoxDirect(detection),
      validationStatus: detection.validation_result || detection.validationStatus || 'pending',
      createdAt: detection.created_at || detection.createdAt || new Date().toISOString()
    }));
  }
  
  private static transformBoundingBoxDirect(detection: any): BoundingBox {
    if (detection.bounding_box || detection.boundingBox) {
      const bbox = detection.bounding_box || detection.boundingBox;
      return {
        x: bbox.x || 0,
        y: bbox.y || 0,
        width: bbox.width || 0,
        height: bbox.height || 0,
        confidence: bbox.confidence
      };
    }
    
    // Handle individual coordinate fields
    return {
      x: detection.bounding_box_x || detection.boundingBoxX || 0,
      y: detection.bounding_box_y || detection.boundingBoxY || 0,
      width: detection.bounding_box_width || detection.boundingBoxWidth || 0,
      height: detection.bounding_box_height || detection.boundingBoxHeight || 0
    };
  }
}
```

## Error Handling in Transformations

### Robust Error Recovery
```typescript
// Comprehensive error handling for data transformations
class TransformationErrorHandler {
  /**
   * Safe transformation with error recovery
   */
  static safeTransform<T, R>(
    data: T,
    transformer: (data: T) => R,
    fallback: R | (() => R),
    errorHandler?: (error: Error, data: T) => void
  ): R {
    try {
      return transformer(data);
    } catch (error) {
      // Log error details
      console.error('Transformation failed:', {
        error: error instanceof Error ? error.message : 'Unknown error',
        data: data,
        transformer: transformer.name
      });
      
      // Call custom error handler if provided
      if (errorHandler) {
        errorHandler(error instanceof Error ? error : new Error('Unknown transformation error'), data);
      }
      
      // Return fallback value
      return typeof fallback === 'function' ? (fallback as () => R)() : fallback;
    }
  }
  
  /**
   * Transform array with partial error recovery
   */
  static safeTransformArray<T, R>(
    items: T[],
    transformer: (item: T) => R,
    fallback?: R | ((item: T, error: Error) => R)
  ): R[] {
    return items.map((item, index) => {
      try {
        return transformer(item);
      } catch (error) {
        console.warn(`Failed to transform item at index ${index}:`, error);
        
        if (fallback) {
          return typeof fallback === 'function'
            ? (fallback as (item: T, error: Error) => R)(item, error instanceof Error ? error : new Error('Unknown error'))
            : fallback;
        }
        
        // Skip failed items
        return null;
      }
    }).filter(item => item !== null) as R[];
  }
  
  /**
   * Validate transformation result
   */
  static validateTransformationResult<T>(
    result: T,
    validator: (result: T) => boolean,
    errorMessage: string = 'Transformation result validation failed'
  ): T {
    if (!validator(result)) {
      throw new Error(errorMessage);
    }
    
    return result;
  }
}

// Usage examples
const safeVideoTransformation = (rawVideo: any): VideoFile => {
  return TransformationErrorHandler.safeTransform(
    rawVideo,
    StatusTransformer.transformVideoWithStatus,
    {
      // Fallback video object
      id: rawVideo.id || 'unknown',
      filename: rawVideo.filename || 'unknown.mp4',
      fileSize: 0,
      status: VideoValidationStatus.UPLOADED,
      validationStatus: ValidationStatus.PENDING,
      groundTruthGenerated: false,
      groundTruthCount: 0,
      detectionCount: 0,
      annotationCount: 0,
      hilTestingReady: false,
      createdAt: new Date().toISOString()
    } as VideoFile,
    (error, data) => {
      // Custom error handling
      console.error('Video transformation failed for:', data.id || 'unknown', error);
    }
  );
};
```

This comprehensive data transformation system ensures seamless, performant, and error-resistant data flow between all components of the platform while maintaining backward compatibility and supporting multiple data format versions.