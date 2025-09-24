// PRD-compliant enums matching GLOBAL_VARIABLES_REFERENCE.md
export enum CameraType {
  FRONT_FACING_VRU = "Front-facing VRU",
  REAR_FACING_VRU = "Rear-facing VRU",
  IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior",
  MULTI_ANGLE_SCENARIOS = "Multi-angle"
}

export enum SignalType {
  GPIO = "GPIO",
  NETWORK_PACKET = "Network Packet",
  SERIAL = "Serial",
  CAN_BUS = "CAN Bus",
}

// PRD-aligned VRU types
export enum VRUType {
  PEDESTRIAN = "pedestrian",
  CYCLIST = "cyclist",
  MOTORCYCLIST = "motorcyclist",
  WHEELCHAIR = "wheelchair_user",
  SCOOTER = "scooter_rider"
}

// Unified video validation status system
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

// Legacy video status (for backward compatibility)
export enum VideoStatus {
  UPLOADED = "uploaded",
  PROCESSING = "processing",
  COMPLETED = "completed", 
  VALIDATED = "validated",
  ERROR = "error",
  PENDING_ANNOTATION = "pending_annotation",
  PENDING_VALIDATION = "pending_validation"
}

// Validation workflow status
export enum ValidationStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  PENDING_VALIDATION = "pending_validation",
  VALIDATING = "validating",
  VALIDATED = "validated",
  FAILED = "failed",
  NEEDS_REVIEW = "needs_review"
}

// Type of validation performed
export enum ValidationType {
  AUTOMATIC = "automatic",
  MANUAL = "manual", 
  HYBRID = "hybrid"
}

// Validation result
export enum ValidationResultType {
  PASSED = "passed",
  FAILED = "failed",
  NEEDS_REVIEW = "needs_review",
  PROCESSING = "processing"
}

// PRD-aligned test execution outcomes
export enum DetectionOutcome {
  PASS = "pass",
  FAIL_HIGH_LATENCY = "fail_high_latency",
  FAIL_MISSED_DETECTION = "fail_missed_detection"
}

export enum ProjectStatus {
  DRAFT = "draft",
  ACTIVE = "active",
  TESTING = "testing",
  ANALYSIS = "analysis",
  COMPLETED = "completed",
  ARCHIVED = "archived"
}

// API Response Types
export interface ApiResponse<T = unknown> {
  data?: T;
  message?: string;
  error?: string;
  status?: number;
  success?: boolean;
  timestamp?: string;
}

// Project Types - Updated to match backend camelCase serializers
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
  videoCount?: number; // New field from backend
  totalAnnotations?: number; // New field from backend
  averageAccuracy?: number; // New field from backend
  ownerId: string; // Required field from backend
}

export interface ProjectCreate {
  name: string;
  description: string;
  cameraModel: string;
  cameraView: CameraType;
  signalType: SignalType;
  [key: string]: unknown;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  cameraModel?: string;
  cameraView?: CameraType;
  signalType?: SignalType;
  status?: ProjectStatus;
  [key: string]: unknown;
}

// Extended Project with additional properties
export interface ExtendedProject extends Project {
  modelConfigurations?: ModelConfiguration[];
  models?: ModelConfiguration[];
}

// Enhanced VideoFile interface with unified validation status system
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
  // Additional compatibility fields
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
  uploaded_at?: string;
  created_at?: string;
  processedAt?: string;
  bitrate?: number;
  format?: string;
  codec?: string;
  mimeType?: string;
  thumbnailUrl?: string;
  metadata?: Record<string, unknown>;
  annotations?: unknown[];
  file_size?: number;
  project_id?: number;
  original_name?: string;
  file_path?: string;
}

// Video Validation System Types

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

export interface ValidationScores {
  groundTruthScore?: number;
  technicalScore?: number;
  contentScore?: number;
  overallScore?: number;
}

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
  message?: string; // For async processing responses
}

export interface VideoStatusResponse {
  videoId: string;
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
  groundTruthCount: number;
  groundTruthQualityScore?: number;
  
  // Latest validation result
  validationResult?: VideoValidationResult;
}

export interface VideoStatusTransition {
  id: string;
  videoId: string;
  fromStatus: string;
  toStatus: string;
  transitionReason: string;
  triggeredBy?: string;
  metadata?: Record<string, any>;
  createdAt: string;
}

export interface ValidationQueueStatus {
  pendingValidation: number;
  currentlyValidating: number;
  validationFailed: number;
  totalInQueue: number;
}

export interface VideoValidationRequest {
  validationType: ValidationType;
  criteriaId?: string;
  notes?: string;
  
  // For manual validation
  manualResult?: ValidationResultType;
  scores?: ValidationScores;
}

export interface BatchValidationRequest {
  videoIds: string[];
  validationType: ValidationType;
  criteriaId?: string;
}

export interface BatchStatusUpdate {
  videoIds: string[];
  newStatus: VideoValidationStatus;
  reason: string;
  metadata?: Record<string, any>;
}

// Status transition helpers
export interface StatusTransitionRule {
  fromStatus: VideoValidationStatus;
  toStatus: VideoValidationStatus;
  requiredConditions?: string[];
  automatic?: boolean;
  manualOverride?: boolean;
}

// Legacy compatibility wrapper
export interface LegacyVideoFile extends VideoFile {
  // Map new fields to legacy names for backward compatibility
  processingStatus: string; // Computed from status
  processing_status?: string; // Snake case alias
  ground_truth_generated?: boolean; // Snake case alias
  groundTruthStatus?: string; // Computed status
}

// Status mapping utilities
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

export const mapToLegacyProcessingStatus = (status: VideoValidationStatus): string => {
  const statusMap: Record<VideoValidationStatus, string> = {
    [VideoValidationStatus.UPLOADED]: "pending",
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
    [VideoValidationStatus.ERROR]: "failed"
  };
  return statusMap[status] || "pending";
};

export interface VideoUpload {
  projectId: string;
  file: File;
}

// Export VRUType for annotation components
export type { VRUType as AnnotationVRUType };

// GroundTruthObject interface matching GLOBAL_VARIABLES_REFERENCE.md
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

// WebSocket Message Types - PRD-compliant with string ISO timestamps
export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string; // ISO timestamp string for consistency
  id?: string;
}

// Enhanced WebSocket message types for different operations
export interface DetectionWebSocketMessage extends WebSocketMessage<DetectionEventData> {
  type: 'detection_update' | 'detection_completed' | 'detection_failed';
}

export interface AnnotationWebSocketMessage extends WebSocketMessage<AnnotationEventData> {
  type: 'annotation_created' | 'annotation_updated' | 'annotation_validated';
}

export interface SignalWebSocketMessage extends WebSocketMessage<SignalProcessingEventData> {
  type: 'signal_received' | 'signal_processed' | 'signal_failed';
}

// Detection Service Types
export interface DetectionUpdate {
  videoId: string;
  detections: Detection[];
  processingProgress: number;
  status: 'processing' | 'completed' | 'failed';
}

// Signal Processing Types
export interface SignalData {
  type: SignalType;
  data: Record<string, unknown>;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

// Detection Types - Updated to match backend camelCase serializers
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
  isGroundTruth?: boolean; // Add isGroundTruth property
  validated?: boolean; // Add validated property
  createdAt: string;
}

export interface Annotation {
  id: string;
  videoId: string;
  timestamp: number;
  endTimestamp?: number; // For temporal annotations
  boundingBoxes: BoundingBox[];
  detectionType: 'pedestrian' | 'cyclist' | 'vehicle' | 'other';
  confidence: number;
  detections: Detection[];
}

// BoundingBox - Updated to match backend camelCase serializers
export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  confidence?: number;
  // Optional label for backward compatibility
  label?: string;
  // Computed fields (from serializers)
  area?: number;
  centerX?: number;
  centerY?: number;
}

// Enhanced Point and Shape Types for Annotation Canvas
export interface Point {
  x: number;
  y: number;
  pressure?: number;
  size?: number;
  timestamp?: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface Rectangle extends Point, Size {}

export interface AnnotationStyle {
  strokeColor: string;
  fillColor: string;
  strokeWidth: number;
  fillOpacity: number;
  fontSize?: number;
  dashArray?: number[];
}

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

// Ground Truth Annotation Types - Updated to match backend camelCase serializers
export interface GroundTruthAnnotation {
  id: string;
  videoId: string;
  detectionId?: string;
  frameNumber: number;
  timestamp: number;
  endTimestamp?: number;
  vruType: VRUType;
  classLabel?: string;
  boundingBox: BoundingBox;
  occluded: boolean;
  truncated: boolean;
  difficult: boolean;
  validationStatus: 'pending' | 'validated' | 'rejected' | 'needs_review';
  validated: boolean;
  confidence?: number;
  notes?: string;
  annotator?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface AnnotationSession {
  id: string;
  videoId: string;
  projectId: string;
  annotatorId?: string;
  status: 'active' | 'paused' | 'completed' | 'cancelled';
  totalDetections: number;
  validatedDetections: number;
  currentFrame: number;
  totalFrames: number;
  createdAt: string;
  updatedAt?: string;
}

export interface AnnotationTool {
  id: string;
  name: string;
  type: 'rectangle' | 'polygon' | 'circle' | 'point';
  color: string;
  strokeWidth: number;
  fillOpacity: number;
}

// Test Session Types
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
  config?: TestConfiguration; // Test configuration object
  detectionEvents?: DetectionEvent[];
  metrics?: TestMetrics;
  // Additional properties for TestExecution
  modelConfigurations?: ModelConfiguration[];
  models?: ModelConfiguration[];
  modelConfigIds?: string[];
}

export interface TestSessionCreate {
  projectId: string;
  videoId?: string;
  videoIds?: string[];
  name: string;
  description?: string;
  config?: TestConfiguration;
  [key: string]: unknown;
}

export interface TestConfiguration {
  [key: string]: unknown;
}

export interface TestResult {
  id: string;
  sessionId: string;
  videoId: string;
  videoName?: string;
  status: 'success' | 'failed' | 'pending' | 'processing';
  timestamp: string | Date;
  processingTime?: number;
  confidence?: number;
  details?: string;
  detections?: Detection[];
  metadata?: Record<string, unknown>;
}

export interface DetectionEvent {
  id: string;
  testSessionId: string;
  timestamp: number;
  detectionType: 'pedestrian' | 'cyclist' | 'motorcyclist' | 'vehicle';
  confidence: number;
  boundingBox: BoundingBox;
  isGroundTruth: boolean;
  isCorrectDetection: boolean;
}

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

// New types for Results component
export interface DetectionComparison {
  id: string;
  frameNumber: number;
  timestamp: number;
  groundTruthDetection?: Detection;
  testDetection?: Detection;
  matchType: 'true_positive' | 'false_positive' | 'false_negative' | 'true_negative';
  confidence?: number;
  iouScore?: number;
  distanceError?: number;
  notes?: string;
}

export interface LatencyStats {
  averageLatency: number;
  minLatency: number;
  maxLatency: number;
  medianLatency: number;
  latencyDistribution: { range: string; count: number }[];
  frameProcessingTimes: { frame: number; processingTime: number }[];
}

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

export interface StatisticalAnalysis {
  confidenceIntervals: {
    precision: [number, number];
    recall: [number, number];
    f1Score: [number, number];
    accuracy: [number, number];
  };
  pValue: number;
  statisticalSignificance: boolean;
  sampleSize: number;
  standardDeviations: {
    precision: number;
    recall: number;
    f1Score: number;
    accuracy: number;
  };
}

export interface DetectionTypeBreakdown {
  pedestrian: DetectionTypeMetrics;
  cyclist: DetectionTypeMetrics;
  motorcyclist: DetectionTypeMetrics;
  wheelchair_user: DetectionTypeMetrics;
  scooter_rider: DetectionTypeMetrics;
  overall: DetectionTypeMetrics;
}

export interface DetectionTypeMetrics {
  totalGroundTruth: number;
  totalDetected: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  precision: number;
  recall: number;
  f1Score: number;
  averageConfidence: number;
}

export interface PassFailResult {
  overall: 'PASS' | 'FAIL' | 'WARNING';
  criteria: {
    minPrecision: { required: number; actual: number; status: 'PASS' | 'FAIL' };
    minRecall: { required: number; actual: number; status: 'PASS' | 'FAIL' };
    minF1Score: { required: number; actual: number; status: 'PASS' | 'FAIL' };
    maxLatency: { required: number; actual: number; status: 'PASS' | 'FAIL' };
  };
  recommendations: string[];
  score: number; // 0-100
}

export interface ExportOptions {
  formats: ('csv' | 'json' | 'pdf' | 'excel')[];
  includeVisualizations: boolean;
  includeDetectionComparisons: boolean;
  includeStatisticalAnalysis: boolean;
}

// Test Configuration Interface for replacing any types
export interface TestConfiguration {
  modelName?: string;
  confidenceThreshold?: number;
  detectionClasses?: VRUType[];
  processingOptions?: {
    batchSize?: number;
    maxFrames?: number;
    skipFrames?: number;
  };
  validationCriteria?: {
    minAccuracy?: number;
    minPrecision?: number;
    minRecall?: number;
    maxLatency?: number;
  };
  outputFormat?: 'json' | 'xml' | 'csv';
  metadata?: Record<string, string | number | boolean>;
}

// Dashboard Types - Aligned with backend snake_case
export interface DashboardStats {
  projectCount: number;
  videoCount: number;
  testSessionCount: number;
  detectionEventCount: number;
  averageAccuracy: number;
  activeTests: number;
  totalDetections: number;
}

export interface ChartData {
  accuracyTrend: {
    date: string;
    accuracy: number;
  }[];
  detectionsByType: {
    type: string;
    count: number;
  }[];
  recentActivity: {
    date: string;
    activity: string;
    count: number;
  }[];
}

// User Types
export interface User {
  id: string;
  email: string;
  fullName: string;
  isActive: boolean;
  createdAt?: string;
  updatedAt?: string;
}


// New interfaces for architectural features
export interface PassFailCriteria {
  id?: string;
  projectId?: string;
  minPrecision: number;
  minRecall: number;
  minF1Score: number;
  maxLatencyMs: number;
  createdAt?: string;
}

export interface StatisticalValidation {
  id: string;
  testSessionId: string;
  confidenceInterval: number;
  pValue: number;
  statisticalSignificance: boolean;
  trendAnalysis: Record<string, number | string | boolean>;
  createdAt: string;
}

export interface VideoAssignment {
  id: string;
  projectId: string;
  videoId: string;
  assignmentReason: string;
  intelligentMatch: boolean;
  createdAt: string;
}

export interface SignalProcessingResult {
  id: string;
  signalType: SignalType;
  processingTime: number;
  success: boolean;
  metadata: Record<string, number | string | boolean>;
  createdAt: string;
}

export interface VideoLibraryOrganization {
  organizedFolders: string[];
  totalVideos: number;
  organizationStrategy: string;
  metadataExtracted: boolean;
}

export interface VideoQualityAssessment {
  videoId: string;
  qualityScore: number;
  resolutionQuality: string;
  frameRateQuality: string;
  brightnessAnalysis: Record<string, number | string>;
  noiseAnalysis: Record<string, number | string>;
}

export interface DetectionPipelineConfig {
  confidenceThreshold: number;
  nmsThreshold: number;
  modelName: string;
  targetClasses: string[];
}

export interface DetectionPipelineResult {
  videoId: string;
  detections: Array<Record<string, number | string | boolean | object | null>>;
  processingTime: number;
  modelUsed: string;
  totalDetections: number;
  confidenceDistribution: Record<string, number>;
  success?: boolean; // Optional success flag for compatibility
  error?: string; // Optional error message for failed operations
}

// Backend response type alias for compatibility
export interface DetectionPipelineResponse extends DetectionPipelineResult {
  video_id?: string; // Backend snake_case field
  processing_time?: number; // Backend snake_case field  
  model_used?: string; // Backend snake_case field
  total_detections?: number; // Backend snake_case field
  confidence_distribution?: Record<string, number>; // Backend snake_case field
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

// Result Visualization Types
export interface ComparisonViewMode {
  type: 'side_by_side' | 'overlay' | 'difference' | 'timeline';
  showGroundTruth: boolean;
  showTestResults: boolean;
  highlightDifferences: boolean;
  filterBy?: {
    detectionType?: VRUType[];
    matchType?: ('true_positive' | 'false_positive' | 'false_negative')[];
    confidenceRange?: [number, number];
    timeRange?: [number, number];
  };
}

export interface ResultsFilter {
  projectId?: string;
  sessionIds?: string[];
  dateRange?: {
    start: string;
    end: string;
  };
  performanceRange?: {
    minAccuracy?: number;
    minPrecision?: number;
    minRecall?: number;
  };
  status?: ('completed' | 'failed' | 'running')[];
  sortBy?: ResultsSortBy;
  sortOrder?: 'asc' | 'desc';
}

// Event Data Types for WebSocket handlers
export interface DetectionEventData {
  id?: string;
  videoId?: string;
  detectionId?: string;
  timestamp?: number;
  vruType?: VRUType;
  confidence?: number;
  boundingBox?: BoundingBox;
  success?: boolean;
  processingTime?: number;
}

export interface AnnotationEventData {
  id?: string;
  videoId?: string;
  annotationId?: string;
  detectionId?: string;
  timestamp?: number;
  vruType?: VRUType;
  boundingBox?: BoundingBox;
  validated?: boolean;
  annotator?: string;
}

export interface SignalProcessingEventData {
  id?: string;
  signalType?: SignalType;
  success?: boolean;
  processingTime?: number;
  timestamp?: number;
  metadata?: Record<string, unknown>;
}

// Chart and Data Visualization Types
export interface ChartSortValue {
  [key: string]: string | number | boolean | null | undefined;
}

// MUI Component Type Helpers
export type ChipColor = 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';
export type LinearProgressColor = 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';
export type ResultsSortBy = 'date' | 'accuracy' | 'precision' | 'recall' | 'f1Score' | 'sessionName';

// API Response Types for Raw Data
export interface RawDetectionData {
  id?: string;
  detection_id?: string;
  detectionId?: string;
  frame_number?: number;
  frameNumber?: number;
  timestamp?: number;
  vru_type?: VRUType;
  vruType?: VRUType;
  bounding_box?: Partial<BoundingBox>;
  boundingBox?: Partial<BoundingBox>;
  confidence?: number;
  occluded?: boolean;
  truncated?: boolean;
  difficult?: boolean;
  validated?: boolean;
  created_at?: string;
  createdAt?: string;
  updated_at?: string;
  updatedAt?: string;
  [key: string]: unknown;
}

export interface ImportAnnotationItem {
  id?: string;
  type?: string;
  x?: number | string;
  y?: number | string;
  width?: number | string;
  height?: number | string;
  label?: string;
  points?: Point[];
  [key: string]: unknown;
}

export interface ModelConfiguration {
  id: string;
  name: string;
  type: string;
  parameters?: Record<string, unknown>;
  active?: boolean;
}

// Error Types
export interface ApiError {
  message: string;
  code?: string;
  status: number;
  details?: Record<string, unknown>;
}

// ApiError class for proper error handling
export class ApiError extends Error {
  public status: number;
  public code?: string;
  public details?: Record<string, unknown>;

  constructor(message: string, status: number = 500, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'UNKNOWN_ERROR';
    if (details !== undefined) {
      this.details = details;
    }
    
    // Maintain proper prototype chain for instanceof checks
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

// LabJack Types - Shared across components
export type ConnectionMode = 'bridge' | 'direct' | 'mock' | 'auto';
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'retrying' | 'discovering' | 'testing' | 'recovery';

export interface WindowsDriverInfo {
  detected: boolean;
  version?: string;
  path?: string;
  supported: boolean;
  recommendations?: string[];
}

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
