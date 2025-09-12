# ADAS Camera HIL Testing Platform - Global Variables Reference

**Last Updated**: 2025-01-10
**Purpose**: Ensure consistent naming across frontend, backend, and database

## 🎯 PRD-Aligned Terminology

### Core System Entities

#### Video Processing States
```typescript
// PRD Status Flow: Raw → Pending Annotation → Pending Validation → Validated
enum VideoStatus {
  PENDING_ANNOTATION = "pending_annotation",
  PENDING_VALIDATION = "pending_validation", 
  VALIDATED = "validated",
  PROCESSING = "processing",
  ERROR = "error"
}
```

#### VRU (Vulnerable Road Users) Types
```typescript
// PRD Requirement: VRU detection and classification
enum VRUType {
  PEDESTRIAN = "pedestrian",
  CYCLIST = "cyclist",
  MOTORCYCLIST = "motorcyclist",
  WHEELCHAIR = "wheelchair",
  SCOOTER = "scooter"
}
```

#### Camera Configuration
```typescript
// PRD Context: ADAS Camera Testing
enum CameraType {
  FRONT_FACING = "front_facing",
  FRONT_FACING_VRU = "front_facing_vru",
  SIDE_VIEW = "side_view",
  REAR_VIEW = "rear_view"
}
```

#### Hardware Signal Types
```typescript
// PRD Requirement: LabJack DAQ TTL Signal Detection
enum SignalType {
  TTL = "ttl",
  GPIO = "gpio",
  ANALOG = "analog",
  DIGITAL = "digital"
}
```

#### Test Execution Outcomes
```typescript
// PRD Module 4: Analysis & Reporting
enum DetectionOutcome {
  PASS = "pass",                    // Signal within latency threshold
  FAIL_HIGH_LATENCY = "fail_high_latency",  // Signal too slow
  FAIL_MISSED_DETECTION = "fail_missed_detection"  // No signal received
}
```

### Database Schema Alignment

#### Video Table
```sql
-- PRD Module 1: Data Management
CREATE TABLE videos (
  id SERIAL PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  file_path TEXT NOT NULL,
  file_size BIGINT,
  status video_status_enum DEFAULT 'pending_annotation',
  processing_status TEXT,
  ground_truth_generated BOOLEAN DEFAULT false,
  detection_count INTEGER DEFAULT 0,
  annotation_count INTEGER DEFAULT 0,
  project_id INTEGER REFERENCES projects(id),
  uploaded_at TIMESTAMP DEFAULT NOW(),
  validated_at TIMESTAMP,
  duration_ms INTEGER,
  frame_rate DECIMAL(10,3),
  resolution_width INTEGER,
  resolution_height INTEGER
);
```

#### Ground Truth Objects
```sql
-- PRD Module 1: Annotation Validation
CREATE TABLE ground_truth_objects (
  id SERIAL PRIMARY KEY,
  video_id INTEGER REFERENCES videos(id),
  vru_id VARCHAR(50),  -- Persistent tracking ID
  vru_type vru_type_enum,
  frame_number INTEGER,
  timestamp_ms DECIMAL(10,3),
  bbox_x DECIMAL(10,3),
  bbox_y DECIMAL(10,3),
  bbox_width DECIMAL(10,3),
  bbox_height DECIMAL(10,3),
  confidence DECIMAL(5,3),
  validated BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### Test Sessions (HIL Execution)
```sql
-- PRD Module 3: Test Execution
CREATE TABLE test_sessions (
  id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  test_start_time TIMESTAMP(6),  -- High precision
  max_latency_ms INTEGER,
  labjack_connected BOOLEAN,
  total_events INTEGER,
  passed_events INTEGER,
  failed_events INTEGER,
  missed_detections INTEGER,
  average_latency_ms DECIMAL(10,3),
  status test_session_status_enum,
  completed_at TIMESTAMP(6)
);
```

#### Hardware Detection Events
```sql
-- PRD Module 3: Precision Time & Signal Logging
CREATE TABLE detection_events (
  id SERIAL PRIMARY KEY,
  test_session_id INTEGER REFERENCES test_sessions(id),
  video_id INTEGER REFERENCES videos(id),
  ground_truth_object_id INTEGER REFERENCES ground_truth_objects(id),
  expected_event_time TIMESTAMP(6),  -- PRD: Expected_Event_Time
  signal_received_time TIMESTAMP(6), -- PRD: Signal_Received_Time
  latency_ms DECIMAL(10,3),
  outcome detection_outcome_enum,
  signal_type signal_type_enum,
  signal_value DECIMAL(10,6),
  snapshot_path TEXT,
  created_at TIMESTAMP(6) DEFAULT NOW()
);
```

### Frontend TypeScript Interfaces

#### VideoFile Interface
```typescript
// Complete interface matching database and PRD requirements
interface VideoFile {
  id: number;
  filename: string;
  filePath: string;
  fileSize: number;
  status: VideoStatus;
  processingStatus: string;
  groundTruthGenerated: boolean;
  detectionCount: number;
  annotationCount: number;
  projectId?: number;
  uploadedAt: string;
  validatedAt?: string;
  duration: number;
  frameRate: number;
  width: number;
  height: number;
}
```

#### Ground Truth Object
```typescript
interface GroundTruthObject {
  id: number;
  videoId: number;
  vruId: string;          // PRD: Persistent VRU ID
  vruType: VRUType;
  frameNumber: number;
  timestampMs: number;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  confidence: number;
  validated: boolean;
}
```

#### Test Session Interface
```typescript
interface TestSession {
  id: number;
  projectId: number;
  testStartTime: string;    // PRD: Test_Start_Time
  maxLatencyMs: number;     // PRD: User-defined threshold
  labjackConnected: boolean;
  totalEvents: number;
  passedEvents: number;
  failedEvents: number;
  missedDetections: number;
  averageLatencyMs: number;
  status: TestSessionStatus;
  completedAt?: string;
}
```

#### Hardware Detection Event
```typescript
interface DetectionEvent {
  id: number;
  testSessionId: number;
  videoId: number;
  groundTruthObjectId: number;
  expectedEventTime: string;  // PRD: Expected_Event_Time
  signalReceivedTime?: string; // PRD: Signal_Received_Time
  latencyMs?: number;
  outcome: DetectionOutcome;
  signalType: SignalType;
  signalValue?: number;
  snapshotPath?: string;
  createdAt: string;
}
```

### Backend API Naming Standards

#### Endpoint Patterns
```python
# PRD Module 1: Data Management
POST   /api/v1/videos/upload
GET    /api/v1/videos/{id}/annotations
POST   /api/v1/videos/{id}/validate
GET    /api/v1/videos/library

# PRD Module 2: Test Configuration  
POST   /api/v1/projects
GET    /api/v1/projects/{id}/videos
POST   /api/v1/projects/{id}/videos/{video_id}

# PRD Module 3: Test Execution
POST   /api/v1/test-sessions
GET    /api/v1/test-sessions/{id}/status
POST   /api/v1/labjack/connect
GET    /api/v1/labjack/status

# PRD Module 4: Analysis & Reporting
GET    /api/v1/test-sessions/{id}/report
GET    /api/v1/detection-events/{id}/snapshot
```

#### Service Class Names
```python
# PRD-aligned service naming
class VideoIngestionService
class AnnotationValidationService
class ProjectManagementService
class LabJackIntegrationService
class PrecisionTimingService
class HardwareSignalService
class TestReportingService
```

### Environment Variables

#### Database Configuration
```bash
# Database connection
DATABASE_URL=postgresql://user:password@localhost:5432/adas_hil_platform
REDIS_URL=redis://localhost:6379/0

# LabJack Hardware
LABJACK_DEVICE_TYPE=U6
LABJACK_CONNECTION_TYPE=USB
LABJACK_MOCK_MODE=false

# Timing Precision
TIMING_PRECISION_MICROSECONDS=true
MONOTONIC_CLOCK_ENABLED=true

# Video Processing
MAX_VIDEO_SIZE_MB=2048
SUPPORTED_FORMATS=mp4,mov,avi
ANNOTATION_CONFIDENCE_THRESHOLD=0.7

# Test Execution
DEFAULT_MAX_LATENCY_MS=100
FULLSCREEN_MODE_ENABLED=true
HARDWARE_SIGNAL_TIMEOUT_MS=5000
```

### Configuration Constants

#### Frontend Constants
```typescript
// src/config/constants.ts
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
export const WS_BASE_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';

export const VIDEO_CONFIG = {
  MAX_FILE_SIZE_MB: 2048,
  SUPPORTED_FORMATS: ['.mp4', '.mov', '.avi'],
  FRAME_RATE_MIN: 15,
  FRAME_RATE_MAX: 120
} as const;

export const ANNOTATION_CONFIG = {
  MIN_BBOX_SIZE: 10,
  MAX_VRU_COUNT: 50,
  CONFIDENCE_THRESHOLD: 0.7
} as const;

export const HIL_CONFIG = {
  DEFAULT_MAX_LATENCY_MS: 100,
  TIMING_PRECISION_MS: 0.001,
  SIGNAL_TIMEOUT_MS: 5000
} as const;
```

#### Backend Constants
```python
# backend/config/constants.py
DATABASE_SCHEMA_VERSION = "1.0.0"
API_VERSION = "v1"

# PRD Technical Requirements
TIMING_PRECISION_MICROSECONDS = True
MONOTONIC_CLOCK_REQUIRED = True
SUB_MILLISECOND_PRECISION = True

# Video Processing
MAX_VIDEO_SIZE_BYTES = 2048 * 1024 * 1024
SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi"}
DEFAULT_FRAME_RATE = 30.0

# LabJack Configuration
LABJACK_DEVICE_MODELS = ["U3", "U6", "UE9", "T4", "T7", "T8"]
TTL_HIGH_VOLTAGE_MIN = 3.3
TTL_LOW_VOLTAGE_MAX = 0.8

# Test Execution
DEFAULT_MAX_LATENCY_MS = 100
FULLSCREEN_SWITCH_DELAY_MS = 100
SIGNAL_DETECTION_WINDOW_MS = 5000
```

## 🔄 Update Protocol

When making changes:
1. Update this document FIRST
2. Apply changes to frontend/backend
3. Update database migrations
4. Test integration
5. Mark task complete in coordination document

## 📝 Naming Rules

### DO Use (PRD-Aligned):
- `ground_truth` instead of `annotation`
- `vru` instead of `object` or `detection`
- `test_session` instead of `test_run`
- `signal_received_time` instead of `detection_time`
- `expected_event_time` instead of `ground_truth_time`
- `labjack` instead of `hardware` or `daq`

### DON'T Use (Non-PRD):
- `model_validation` (this is camera validation)
- `ai_detection` (this is hardware signal detection)
- `mock_data` (must be real implementation)
- `dummy_values` (must be actual values)

---

**This document must be updated whenever new variables, interfaces, or naming conventions are introduced.**