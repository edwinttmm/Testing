# Frontend TypeScript Interfaces Documentation

## Overview
This document provides comprehensive documentation of all TypeScript interfaces, types, enums, and type definitions in the frontend codebase. The frontend uses a sophisticated type system with strict typing enforcement and comprehensive data validation.

## Table of Contents
- [Core Enums](#core-enums)
- [Project Management Types](#project-management-types)
- [Video Management Types](#video-management-types)
- [Detection and Annotation Types](#detection-and-annotation-types)
- [Test Execution Types](#test-execution-types)
- [Error Handling Types](#error-handling-types)
- [API Response Types](#api-response-types)
- [WebSocket Types](#websocket-types)
- [LabJack Hardware Types](#labjack-hardware-types)
- [Utility and Helper Types](#utility-and-helper-types)

## Core Enums

### CameraType
```typescript
export enum CameraType {
  FRONT_FACING = "front_facing",
  FRONT_FACING_VRU = "front_facing_vru", 
  SIDE_VIEW = "side_view",
  REAR_VIEW = "rear_view"
}
```
**Purpose**: Defines camera positioning types for VRU detection scenarios
**Usage**: Project configuration, camera setup validation
**Alignment**: Matches backend CameraTypeEnum with snake_case conversion

### SignalType
```typescript
export enum SignalType {
  TTL = "ttl",
  GPIO = "gpio", 
  ANALOG = "analog",
  DIGITAL = "digital"
}
```
**Purpose**: Hardware signal types for LabJack integration
**Usage**: Project signal configuration, hardware validation
**Alignment**: Maps to backend SignalTypeEnum

### VRUType
```typescript
export enum VRUType {
  PEDESTRIAN = "pedestrian",
  CYCLIST = "cyclist",
  MOTORCYCLIST = "motorcyclist", 
  WHEELCHAIR = "wheelchair",
  SCOOTER = "scooter"
}
```
**Purpose**: Vulnerable Road User classifications for detection
**Usage**: Ground truth annotation, detection classification
**Alignment**: Matches backend VRUType exactly

### VideoValidationStatus (Unified System)
```typescript
export enum VideoValidationStatus {
  // Initial states
  UPLOADED = "uploaded",
  PROCESSING = "processing",
  PROCESSING_FAILED = "processing_failed",
  
  // Annotation states
  ANNOTATED = "annotated",
  
  // Validation states
  VALIDATING = "validating", 
  VALIDATION_FAILED = "validation_failed",
  VALIDATED = "validated",
  
  // Testing readiness
  READY_FOR_TESTING = "ready_for_testing",
  IN_TESTING = "in_testing", 
  TESTED = "tested",
  
  // Final states
  ARCHIVED = "archived",
  ERROR = "error"
}
```
**Purpose**: Comprehensive video lifecycle status management
**Usage**: Video state tracking, workflow validation
**Alignment**: Mirrors backend VideoValidationStatus enum

### ValidationStatus
```typescript
export enum ValidationStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  PENDING_VALIDATION = "pending_validation",
  VALIDATING = "validating", 
  VALIDATED = "validated",
  FAILED = "failed",
  NEEDS_REVIEW = "needs_review"
}
```
**Purpose**: Detailed validation workflow status
**Usage**: Validation process tracking
**Alignment**: Matches backend ValidationStatus

## Project Management Types

### Project Interface
```typescript
export interface Project {
  id: string;
  name: string;
  description?: string;
  cameraModel: string;
  cameraView: CameraType;
  signalType: SignalType;
  lensType?: string;
  resolution?: string;
  frameRate?: number;
  createdAt: string;
  updatedAt?: string; 
  status: ProjectStatus;
  testsCount?: number;
  videoCount?: number;
  totalAnnotations?: number;
  averageAccuracy?: number;
  ownerId: string; // Required field from backend
}
```
**Purpose**: Core project data structure
**Key Features**:
- **Required Fields**: id, name, cameraModel, cameraView, signalType, createdAt, status, ownerId
- **Optional Metadata**: description, technical specs, analytics
- **Computed Fields**: testsCount, videoCount, totalAnnotations, averageAccuracy
- **Backend Alignment**: Uses camelCase with serializer compatibility

### ProjectCreate
```typescript
export interface ProjectCreate {
  name: string;
  description: string;
  cameraModel: string;
  cameraView: CameraType;
  signalType: SignalType;
  [key: string]: unknown;
}
```
**Purpose**: Project creation request payload
**Validation**: All fields required except extensible properties

### ProjectUpdate
```typescript
export interface ProjectUpdate {
  name?: string;
  description?: string;
  cameraModel?: string;
  cameraView?: CameraType;
  signalType?: SignalType;
  status?: ProjectStatus;
  [key: string]: unknown;
}
```
**Purpose**: Project update request payload
**Features**: All fields optional, extensible structure

## Video Management Types

### VideoFile Interface (Core)
```typescript
export interface VideoFile {
  id: string;
  filename: string;
  filePath?: string;
  fileSize: number;
  
  // Unified status system
  status: VideoValidationStatus;
  validationStatus: ValidationStatus;
  validationType?: ValidationType;
  validatedAt?: string;
  validatedBy?: string;
  
  // HIL testing readiness
  hilTestingReady: boolean;
  hilTestingApprovedBy?: string;
  hilTestingApprovedAt?: string;
  
  // Ground truth information
  groundTruthGenerated: boolean;
  groundTruthCount: number;
  groundTruthQualityScore?: number;
  groundTruthCompletedAt?: string;
  
  // Basic metadata
  detectionCount: number;
  annotationCount: number;
  projectId?: string;
  duration?: number;
  frameRate?: number;
  width?: number;
  height?: number;
  createdAt: string;
  updatedAt?: string;
  
  // Extensive compatibility fields for legacy support
  originalName?: string;
  name?: string;
  size?: number;
  url?: string;
  fps?: number;
  frame_rate?: number;
  resolution?: string;
  frameCount?: number;
  processing_status?: string;
  ground_truth_generated?: boolean;
  groundTruthStatus?: string;
  ground_truth_status?: string;
  detection_count?: number;
  validationScore?: number;
  // ... additional compatibility fields
}
```
**Purpose**: Comprehensive video data structure
**Key Features**:
- **Unified Status System**: Primary status with validation workflow
- **HIL Testing Integration**: Ready flags and approval tracking  
- **Ground Truth Management**: Generation tracking and quality metrics
- **Legacy Compatibility**: Extensive snake_case and alternate field support
- **Rich Metadata**: Technical specifications, processing history

### Video Validation System Types

#### VideoValidationCriteria
```typescript
export interface VideoValidationCriteria {
  id: string;
  projectId?: string; // null = global criteria
  
  // Ground truth quality requirements
  minDetectionCount: number;
  minConfidenceThreshold: number;
  minFrameCoveragePercent: number;
  
  // Technical requirements
  minDurationSeconds: number;
  maxDurationSeconds: number;
  requiredResolutionMin: string;
  minFps: number;
  
  // Content requirements
  requiredVruTypes?: string[];
  minSceneComplexityScore: number;
  
  createdAt: string;
  updatedAt?: string;
}
```
**Purpose**: Configurable validation requirements
**Features**: Project-specific or global criteria

#### VideoValidationResult
```typescript
export interface VideoValidationResult {
  id: string;
  videoId: string;
  validationCriteriaId?: string;
  validationType: ValidationType;
  overallResult: ValidationResultType;
  scores?: ValidationScores;
  criteriaMet?: Record<string, boolean>;
  validationNotes?: string;
  validatedBy?: string;
  createdAt: string;
  message?: string;
}
```
**Purpose**: Validation process results
**Features**: Detailed scoring, criteria breakdown, audit trail

## Detection and Annotation Types

### Detection Interface
```typescript
export interface Detection {
  id: string;
  videoId: string;
  detectionId?: string;
  inferenceSessionId?: string;
  frameNumber: number;
  timestamp: number;
  classId: number;
  className: string;
  vruType: VRUType;
  confidence: number;
  boundingBox: BoundingBox;
  detectionScore?: number;
  nmsScore?: number;
  trackingId?: string;
  validationStatus: 'pending' | 'validated' | 'rejected' | 'needs_review';
  groundTruthMatchId?: string;
  iouWithGroundTruth?: number;
  isGroundTruth?: boolean;
  validated?: boolean;
  createdAt: string;
}
```
**Purpose**: Core detection data structure
**Key Features**:
- **Comprehensive Detection Data**: Frame, timestamp, classification
- **Validation Integration**: Status tracking, ground truth matching
- **Quality Metrics**: Confidence, IOU scores, NMS processing
- **Tracking Support**: Cross-frame VRU tracking

### BoundingBox Interface
```typescript
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
  label?: string;
  // Computed fields (from serializers)
  area?: number;
  centerX?: number;
  centerY?: number;
}
```
**Purpose**: Spatial detection coordinates
**Features**: Basic coordinates, optional metadata, computed properties

### GroundTruthObject Interface
```typescript
export interface GroundTruthObject {
  id: string;
  videoId: string;
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
**Purpose**: Ground truth annotation data
**Features**: VRU tracking, validation status, spatial data

### Enhanced Annotation Types

#### AnnotationShape (Advanced Canvas System)
```typescript
export interface AnnotationShape {
  id: string;
  type: 'rectangle' | 'polygon' | 'brush' | 'point';
  points: Point[];
  boundingBox: Rectangle;
  style: AnnotationStyle;
  label?: string;
  confidence?: number | undefined;
  locked?: boolean;
  selected?: boolean;
  visible?: boolean;
}
```
**Purpose**: Advanced annotation canvas shape system
**Features**: Multi-shape support, styling, interaction state

#### AnnotationStyle
```typescript
export interface AnnotationStyle {
  strokeColor: string;
  fillColor: string;
  strokeWidth: number;
  fillOpacity: number;
  fontSize?: number;
  dashArray?: number[];
}
```
**Purpose**: Visual styling for annotations
**Features**: Complete styling control, optional properties

## Test Execution Types

### TestSession Interface
```typescript
export interface TestSession {
  id: string;
  projectId: string;
  videoId?: string;
  videoIds?: string[];
  name: string;
  description?: string;
  status: 'created' | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  createdAt?: string | Date;
  startedAt?: string;
  completedAt?: string;
  config?: TestConfiguration;
  detectionEvents?: DetectionEvent[];
  metrics?: TestMetrics;
  modelConfigurations?: ModelConfiguration[];
  models?: ModelConfiguration[];
  modelConfigIds?: string[];
}
```
**Purpose**: Test execution session management
**Features**: Multi-video support, configuration tracking, results integration

### TestMetrics Interface
```typescript
export interface TestMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  totalDetections: number;
}
```
**Purpose**: Statistical test performance metrics
**Features**: Standard ML performance metrics

### DetailedTestResults Interface
```typescript
export interface DetailedTestResults {
  sessionId: string;
  sessionName: string;
  projectName: string;
  videoName: string;
  status: 'completed' | 'failed' | 'running';
  metrics: TestMetrics;
  statisticalAnalysis: StatisticalAnalysis;
  detectionBreakdown: DetectionTypeBreakdown;
  latencyAnalysis: LatencyStats;
  passFailResult: PassFailResult;
  detectionComparisons: DetectionComparison[];
  groundTruthDetections: Detection[];
  testDetections: Detection[];
  exportOptions: ExportOptions;
}
```
**Purpose**: Comprehensive test analysis results
**Features**: Multi-dimensional analysis, statistical validation, export support

## Error Handling Types

### Error Boundary Types
```typescript
export interface ErrorInfo {
  componentStack: string;
  errorBoundary?: string;
  errorBoundaryStack?: string;
}

export interface ErrorBoundaryError extends Error {
  digest?: string;
}

export interface ErrorBoundaryContext {
  level: 'app' | 'page' | 'component';
  context: string;
  metadata?: Record<string, unknown>;
}
```
**Purpose**: React Error Boundary integration
**Features**: Component-level error tracking, context preservation

### API Error Types
```typescript
export interface ApiErrorResponse {
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, unknown>;
  timestamp?: string;
}

export interface NetworkError extends Error {
  code?: string;
  response?: {
    status: number;
    statusText: string;
    data?: unknown;
  };
  request?: unknown;
  config?: Record<string, unknown>;
}
```
**Purpose**: API and network error handling
**Features**: Structured error data, HTTP context

### Error Factory
```typescript
export class TypedErrorFactory {
  static createApiError(
    message: string, 
    status?: number, 
    details?: Record<string, unknown>
  ): NetworkError

  static createNetworkError(message?: string): NetworkError

  static createValidationError(
    message: string, 
    field?: string, 
    value?: unknown
  ): Error & { field?: string; value?: unknown }

  static fromUnknown(error: unknown, fallbackMessage?: string): SafeError
}
```
**Purpose**: Consistent error object creation
**Features**: Type-safe error construction, unknown error handling

## API Response Types

### Generic API Response
```typescript
export interface ApiResponse<T = unknown> {
  data?: T;
  message?: string;
  error?: string;
  status?: number;
  success?: boolean;
  timestamp?: string;
}
```
**Purpose**: Standardized API response wrapper
**Features**: Generic type support, optional fields

### Specialized Response Types
```typescript
export interface DashboardStats {
  project_count: number;
  video_count: number;
  test_session_count: number;
  detection_event_count: number;
}

export interface EnhancedDashboardStats extends DashboardStats {
  confidence_intervals: {
    precision: [number, number];
    recall: [number, number];
    f1_score: [number, number];
  };
  trend_analysis: {
    accuracy: 'improving' | 'declining' | 'stable';
    detectionRate: 'improving' | 'declining' | 'stable';
    performance: 'improving' | 'declining' | 'stable';
  };
  signal_processing_metrics: {
    totalSignals: number;
    successRate: number;
    avgProcessingTime: number;
  };
  average_accuracy: number;
  active_tests: number;
  total_detections: number;
}
```
**Purpose**: Dashboard analytics and statistics
**Features**: Basic and enhanced metrics, trend analysis

## WebSocket Types

### Base WebSocket Message
```typescript
export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string; // ISO timestamp string
  id?: string;
}
```
**Purpose**: Base WebSocket communication structure
**Features**: Generic payload, timestamp consistency

### Specialized WebSocket Messages
```typescript
export interface DetectionWebSocketMessage extends WebSocketMessage<DetectionEventData> {
  type: 'detection_update' | 'detection_completed' | 'detection_failed';
}

export interface AnnotationWebSocketMessage extends WebSocketMessage<AnnotationEventData> {
  type: 'annotation_created' | 'annotation_updated' | 'annotation_validated';
}

export interface SignalWebSocketMessage extends WebSocketMessage<SignalProcessingEventData> {
  type: 'signal_received' | 'signal_processed' | 'signal_failed';
}
```
**Purpose**: Typed real-time communication
**Features**: Event-specific payloads, type safety

## LabJack Hardware Types

### Connection Types
```typescript
export type ConnectionMode = 'bridge' | 'direct' | 'mock' | 'auto';
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'retrying' | 'discovering' | 'testing' | 'recovery';
```
**Purpose**: LabJack connection management
**Features**: Multiple connection modes, detailed status tracking

### LabJack Status Interface
```typescript
export interface LabJackStatus {
  mode: ConnectionMode;
  status: ConnectionStatus;
  connected: boolean;
  device_info: {
    device_type?: string;
    serial_number?: string;
    ip_address?: string;
    is_mock?: boolean;
    bridge_host?: string;
    bridge_port?: number;
    firmware_version?: string;
    hardware_version?: string;
    calibration_date?: string;
  };
  streaming: boolean;
  sample_rate: number;
  channels: string[];
  voltage_threshold: number;
  last_data_time?: string;
  error_message?: string;
  statistics: {
    samples_received: number;
    errors_count: number;
    connection_attempts: number;
    successful_connections: number;
    failed_connections: number;
    last_error_time?: string;
    uptime_start: string;
    total_uptime: number;
    recovery_attempts: number;
  };
  bridge_latency?: number;
  bridge_health?: 'healthy' | 'degraded' | 'unhealthy';
  windows_driver?: WindowsDriverInfo;
  auto_discovery?: {
    enabled: boolean;
    last_scan?: string;
    devices_found?: number;
    scan_duration?: number;
  };
}
```
**Purpose**: Comprehensive LabJack hardware monitoring
**Features**: Device info, statistics, health monitoring, auto-discovery

## Utility and Helper Types

### Generic Utility Types
```typescript
export interface GenericCallback<T = void> {
  (data: T): void;
}

export interface GenericAsyncCallback<T = unknown, R = void> {
  (data: T): Promise<R>;
}

export type FunctionArgument = string | number | boolean | object | null | undefined;
```
**Purpose**: Generic function type definitions
**Features**: Callback patterns, type safety

### Component Props Types
```typescript
export interface BaseComponentProps {
  children?: React.ReactNode | undefined;
  className?: string | undefined;
  style?: React.CSSProperties | undefined;
}

export interface ComponentProps extends BaseComponentProps {
  id?: string | undefined;
  'data-testid'?: string | undefined;
}
```
**Purpose**: React component prop standardization
**Features**: Base props, testing attributes

### Type Guards and Validation
```typescript
export const isNetworkError = (error: unknown): error is NetworkError => {
  return error instanceof Error && (
    error.name === 'NetworkError' ||
    (error.name === 'TypeError' && error.message.includes('fetch')) ||
    'response' in error ||
    'request' in error
  );
};

export const isApiErrorResponse = (error: unknown): error is ApiErrorResponse => {
  return typeof error === 'object' && 
         error !== null && 
         'message' in error &&
         typeof (error as ApiErrorResponse).message === 'string';
};
```
**Purpose**: Runtime type validation
**Features**: Type guards, safe type checking

## Status Mapping Utilities

### Legacy Compatibility
```typescript
export const mapToLegacyStatus = (status: VideoValidationStatus): string => {
  const statusMap: Record<VideoValidationStatus, string> = {
    [VideoValidationStatus.UPLOADED]: "uploaded",
    [VideoValidationStatus.PROCESSING]: "processing",
    [VideoValidationStatus.PROCESSING_FAILED]: "failed",
    [VideoValidationStatus.ANNOTATED]: "completed",
    [VideoValidationStatus.VALIDATING]: "processing", 
    [VideoValidationStatus.VALIDATION_FAILED]: "failed",
    [VideoValidationStatus.VALIDATED]: "completed",
    [VideoValidationStatus.READY_FOR_TESTING]: "completed",
    [VideoValidationStatus.IN_TESTING]: "completed",
    [VideoValidationStatus.TESTED]: "completed",
    [VideoValidationStatus.ARCHIVED]: "completed",
    [VideoValidationStatus.ERROR]: "error"
  };
  return statusMap[status] || "uploaded";
};
```
**Purpose**: Backward compatibility with legacy status systems
**Features**: Status mapping, fallback handling

## Type Safety Features

### Strict Typing Enforcement
- **exactOptionalPropertyTypes**: Enabled in tsconfig.json
- **strict**: All strict TypeScript checks enabled
- **noImplicitAny**: No implicit any types allowed
- **strictNullChecks**: Explicit null/undefined handling

### Runtime Validation
- **Type Guards**: Comprehensive runtime type checking
- **Error Factories**: Typed error construction
- **Validation Utilities**: Input validation helpers

### API Contract Enforcement
- **Interface Alignment**: Frontend-backend type matching
- **Serialization Support**: camelCase/snake_case conversion
- **Version Compatibility**: Legacy field support

## Usage Examples

### Project Creation
```typescript
const createProject = async (data: ProjectCreate): Promise<ApiResponse<Project>> => {
  const response = await api.post<Project>('/projects', data);
  return response.data;
};
```

### Error Handling
```typescript
try {
  const result = await api.get('/videos');
} catch (error) {
  if (isNetworkError(error)) {
    // Handle network-specific error
    console.error('Network error:', error.response?.status);
  } else {
    // Handle generic error
    const safeError = TypedErrorFactory.fromUnknown(error);
    console.error('Error:', safeError.message);
  }
}
```

### WebSocket Integration
```typescript
const handleWebSocketMessage = (message: WebSocketMessage) => {
  switch (message.type) {
    case 'detection_update':
      const detectionMsg = message as DetectionWebSocketMessage;
      updateDetectionStatus(detectionMsg.payload);
      break;
    // Handle other message types...
  }
};
```

This comprehensive type system ensures type safety, backward compatibility, and clear API contracts across the entire frontend application.