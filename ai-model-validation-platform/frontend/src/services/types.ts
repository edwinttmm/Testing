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
  description: string;
  cameraModel: string;
  cameraView: 'Front-facing VRU' | 'Rear-facing VRU' | 'In-Cab Driver Behavior';
  signalType: string;
  createdAt: string;
  updatedAt?: string;
  status: 'Active' | 'Completed' | 'Draft';
  testsCount: number;
  accuracy: number;
  userId?: string;
}

export interface ProjectCreate {
  name: string;
  description: string;
  cameraModel: string;
  cameraView: 'Front-facing VRU' | 'Rear-facing VRU' | 'In-Cab Driver Behavior';
  signalType: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  cameraModel?: string;
  cameraView?: 'Front-facing VRU' | 'Rear-facing VRU' | 'In-Cab Driver Behavior';
  signalType?: string;
  status?: 'Active' | 'Completed' | 'Draft';
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
  detectionType: 'pedestrian' | 'cyclist' | 'vehicle';
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


// Error Types
export interface ApiError {
  message: string;
  code?: string;
  status: number;
  details?: any;
}