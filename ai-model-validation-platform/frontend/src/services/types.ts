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
export interface ApiResponse<T = any> {
  data?: T;
  message?: string;
  error?: string;
  status?: number;
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
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  cameraModel?: string;
  cameraView?: CameraType;
  signalType?: SignalType;
  status?: ProjectStatus;
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
  url?: string;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  groundTruthStatus?: 'pending' | 'processing' | 'completed' | 'failed';
  groundTruthGenerated?: boolean;
  ground_truth_generated?: boolean; // API response field
  detectionCount?: number;
  annotations?: Annotation[];
}

export interface VideoUpload {
  projectId: string;
  file: File;
}

// Annotation Types
export interface Annotation {
  id: string;
  videoId: string;
  timestamp: number;
  boundingBoxes: BoundingBox[];
  detectionType: 'pedestrian' | 'cyclist' | 'vehicle' | 'other';
  confidence: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
}

// Test Session Types
export interface TestSession {
  id: string;
  projectId: string;
  videoId: string;
  name: string;
  description?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  detectionEvents: DetectionEvent[];
  metrics?: TestMetrics;
}

export interface TestSessionCreate {
  projectId: string;
  videoId: string;
  name: string;
  description?: string;
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

// Dashboard Types
export interface DashboardStats {
  projectCount: number;
  videoCount: number;
  testCount: number;
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
  trendAnalysis: Record<string, any>;
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
  metadata: Record<string, any>;
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
  brightnessAnalysis: Record<string, any>;
  noiseAnalysis: Record<string, any>;
}

export interface DetectionPipelineConfig {
  confidenceThreshold: number;
  nmsThreshold: number;
  modelName: string;
  targetClasses: string[];
}

export interface DetectionPipelineResult {
  videoId: string;
  detections: Array<Record<string, any>>;
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

// Error Types
export interface ApiError {
  message: string;
  code?: string;
  status: number;
  details?: any;
}