// Architecture-compliant enums
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
  CAN_BUS = "CAN Bus"
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

// Project Types
export interface Project {
  id: string;
  name: string;
  description?: string;
  cameraModel: string;
  camera_model?: string; // API response alias
  cameraView: CameraType;
  camera_view?: CameraType; // API response alias
  signalType: SignalType;
  signal_type?: SignalType; // API response alias
  lensType?: string;
  lens_type?: string; // API response alias
  resolution?: string;
  frameRate?: number;
  frame_rate?: number; // API response alias
  createdAt: string;
  created_at?: string; // API response alias
  updatedAt?: string;
  updated_at?: string; // API response alias
  status: ProjectStatus;
  testsCount?: number;
  accuracy?: number;
  userId?: string;
  owner_id?: string; // API response alias
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

// Video Types
export interface VideoFile {
  id: string;
  projectId: string;
  filename: string;
  originalName: string;
  name?: string;
  size: number;
  fileSize?: number;
  file_size?: number; // API response field
  duration?: number;
  uploadedAt: string;
  createdAt?: string;
  created_at?: string; // API response field
  url: string;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  processing_status?: 'pending' | 'processing' | 'completed' | 'failed'; // API response field
  groundTruthStatus?: 'pending' | 'processing' | 'completed' | 'failed';
  groundTruthGenerated?: boolean;
  ground_truth_generated?: boolean; // API response field
  detectionCount?: number;
  annotations?: Annotation[];
  // Additional properties for enhanced video handling
  width?: number;
  height?: number;
  fps?: number;
  bitrate?: number;
  format?: string;
  codec?: string;
  thumbnailUrl?: string;
  metadata?: Record<string, unknown>;
}

export interface VideoUpload {
  projectId: string;
  file: File;
}

// VRU Detection Types
export type VRUType = 'pedestrian' | 'cyclist' | 'motorcyclist' | 'wheelchair_user' | 'scooter_rider';

// Export VRUType for annotation components
export type { VRUType as AnnotationVRUType };

// WebSocket Message Types
export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: number;
  id?: string;
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

// Annotation Types
export interface Detection {
  id: string;
  detectionId: string;
  timestamp: number;
  boundingBox: BoundingBox;
  vruType: VRUType;
  confidence: number;
  isGroundTruth: boolean;
  notes?: string;
  validated: boolean;
  createdAt: string;
  updatedAt?: string;
  // Additional properties for API compatibility
  frame?: number;
  frameNumber?: number;
  bbox?: BoundingBox;
  label?: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  time?: number;
  occluded?: boolean;
  truncated?: boolean;
  difficult?: boolean;
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

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
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
  confidence?: number;
  locked?: boolean;
  selected?: boolean;
  visible?: boolean;
}

// Ground Truth Annotation Types
export interface GroundTruthAnnotation {
  id: string;
  videoId: string;
  detectionId: string;
  frameNumber: number;
  timestamp: number;
  vruType: VRUType;
  boundingBox: BoundingBox;
  occluded: boolean;
  truncated: boolean;
  difficult: boolean;
  notes?: string;
  annotator?: string;
  validated: boolean;
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
  config?: any; // Test configuration object
  detectionEvents?: DetectionEvent[];
  metrics?: TestMetrics;
}

export interface TestSessionCreate {
  projectId: string;
  videoId?: string;
  videoIds?: string[];
  name: string;
  description?: string;
  config?: any;
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

// Dashboard Types - Aligned with backend snake_case
export interface DashboardStats {
  project_count: number;
  video_count: number;
  test_session_count: number;
  detection_event_count: number;
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
  detections: Array<Record<string, number | string | boolean>>;
  processingTime: number;
  modelUsed: string;
  totalDetections: number;
  confidenceDistribution: Record<string, number>;
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
  sortBy?: 'accuracy' | 'precision' | 'recall' | 'f1Score' | 'date' | 'name';
  sortOrder?: 'asc' | 'desc';
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