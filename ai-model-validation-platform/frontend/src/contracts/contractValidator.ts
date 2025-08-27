import { z } from 'zod';
import axios, { AxiosResponse, AxiosError } from 'axios';
import { apiService } from '../services/api';

// Contract version tracking
export const API_CONTRACT_VERSION = '1.0.0';

// Validation severity levels
export enum ValidationSeverity {
  ERROR = 'error',
  WARNING = 'warning',
  INFO = 'info'
}

// Contract violation interface
export interface ContractViolation {
  endpoint: string;
  violationType: string;
  message: string;
  severity: ValidationSeverity;
  fieldPath?: string;
  actualValue?: any;
  expectedType?: string;
}

// Contract validation result
export interface ValidationResult {
  isValid: boolean;
  violations: ContractViolation[];
  processingTime: number;
}

// Zod schemas for API responses
export const ProjectSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(255),
  description: z.string().nullable().optional(),
  cameraModel: z.string(),
  cameraView: z.enum(['Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior']),
  lensType: z.string().nullable().optional(),
  resolution: z.string().nullable().optional(),
  frameRate: z.number().int().positive().nullable().optional(),
  signalType: z.enum(['GPIO', 'Network Packet', 'Serial', 'CAN Bus']),
  status: z.enum(['draft', 'active', 'testing', 'completed', 'archived']),
  ownerId: z.string(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime().nullable().optional()
});

export const BoundingBoxSchema = z.object({
  x: z.number().min(0),
  y: z.number().min(0),
  width: z.number().min(0),
  height: z.number().min(0),
  label: z.string().optional(),
  confidence: z.number().min(0).max(1).optional()
});

export const VideoFileSchema = z.object({
  id: z.string().uuid(),
  filename: z.string(),
  originalName: z.string().nullable().optional(),
  projectId: z.string().uuid(),
  fileSize: z.number().int().min(0).optional(),
  duration: z.number().min(0).optional(),
  fps: z.number().min(0).optional(),
  resolution: z.string().nullable().optional(),
  status: z.enum(['uploaded', 'processing', 'processed', 'error']),
  url: z.string().url().optional(),
  groundTruthGenerated: z.boolean(),
  processingStatus: z.string(),
  detectionCount: z.number().int().min(0),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime().nullable().optional()
});

export const AnnotationSchema = z.object({
  id: z.string().uuid(),
  videoId: z.string().uuid(),
  detectionId: z.string().nullable().optional(),
  frameNumber: z.number().int().min(0),
  timestamp: z.number().min(0),
  endTimestamp: z.number().min(0).nullable().optional(),
  vruType: z.enum(['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair_user', 'scooter_rider']),
  boundingBox: BoundingBoxSchema,
  occluded: z.boolean().default(false),
  truncated: z.boolean().default(false),
  difficult: z.boolean().default(false),
  notes: z.string().nullable().optional(),
  annotator: z.string().nullable().optional(),
  validated: z.boolean().default(false),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime().nullable().optional()
});

export const TestSessionSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  projectId: z.string().uuid(),
  videoId: z.string().uuid(),
  toleranceMs: z.number().int().min(0).default(100),
  status: z.enum(['created', 'running', 'completed', 'error']),
  startedAt: z.string().datetime().nullable().optional(),
  completedAt: z.string().datetime().nullable().optional(),
  createdAt: z.string().datetime()
});

export const ValidationMetricsSchema = z.object({
  accuracy: z.number().min(0).max(1),
  precision: z.number().min(0).max(1),
  recall: z.number().min(0).max(1),
  f1Score: z.number().min(0).max(1),
  truePositives: z.number().int().min(0),
  falsePositives: z.number().int().min(0),
  falseNegatives: z.number().int().min(0),
  totalDetections: z.number().int().min(0)
});

export const DashboardStatsSchema = z.object({
  projectCount: z.number().int().min(0),
  videoCount: z.number().int().min(0),
  testCount: z.number().int().min(0),
  totalDetections: z.number().int().min(0),
  averageAccuracy: z.number().min(0).max(1),
  activeTests: z.number().int().min(0),
  confidenceIntervals: z.record(z.array(z.number())).optional(),
  trendAnalysis: z.record(z.string()).optional(),
  signalProcessingMetrics: z.record(z.any()).optional()
});

export const ErrorResponseSchema = z.object({
  message: z.string(),
  code: z.string().optional(),
  details: z.any().optional(),
  timestamp: z.string().datetime().optional()
});

export const HealthCheckSchema = z.object({
  status: z.enum(['healthy', 'unhealthy']),
  timestamp: z.string().datetime().optional(),
  environment: z.string().optional(),
  database_status: z.string().optional(),
  version: z.string().optional()
});

// Type definitions from schemas
export type Project = z.infer<typeof ProjectSchema>;
export type VideoFile = z.infer<typeof VideoFileSchema>;
export type Annotation = z.infer<typeof AnnotationSchema>;
export type BoundingBox = z.infer<typeof BoundingBoxSchema>;
export type TestSession = z.infer<typeof TestSessionSchema>;
export type ValidationMetrics = z.infer<typeof ValidationMetricsSchema>;
export type DashboardStats = z.infer<typeof DashboardStatsSchema>;
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
export type HealthCheck = z.infer<typeof HealthCheckSchema>;

// Contract validator class
class ContractValidator {
  private contracts: Map<string, z.ZodSchema> = new Map();
  private validationHistory: ContractViolation[] = [];
  private metrics = {
    totalValidations: 0,
    failures: 0,
    successRate: 0,
    responseTimeMs: [] as number[],
    endpointStats: {} as Record<string, { validations: number; failures: number; avgTime: number }>
  };

  constructor() {
    this.initializeContracts();
  }

  private initializeContracts() {
    // Register all endpoint contracts
    this.contracts.set('GET /api/projects', z.array(ProjectSchema));
    this.contracts.set('POST /api/projects', ProjectSchema);
    this.contracts.set('GET /api/projects/:id', ProjectSchema);
    this.contracts.set('PUT /api/projects/:id', ProjectSchema);
    
    this.contracts.set('GET /api/projects/:id/videos', z.object({
      videos: z.array(VideoFileSchema),
      total: z.number().int().min(0)
    }));
    this.contracts.set('POST /api/projects/:id/videos', VideoFileSchema);
    this.contracts.set('GET /api/videos', z.object({
      videos: z.array(VideoFileSchema),
      total: z.number().int().min(0)
    }));
    
    this.contracts.set('GET /api/videos/:id/annotations', z.array(AnnotationSchema));
    this.contracts.set('POST /api/videos/:id/annotations', AnnotationSchema);
    this.contracts.set('GET /api/videos/:id/ground-truth', z.object({
      video_id: z.string().uuid(),
      objects: z.array(z.object({
        id: z.string().uuid(),
        timestamp: z.number().min(0),
        frame_number: z.number().int().min(0).optional(),
        class_label: z.string(),
        x: z.number().min(0),
        y: z.number().min(0),
        width: z.number().min(0),
        height: z.number().min(0),
        confidence: z.number().min(0).max(1),
        validated: z.boolean()
      })),
      total_detections: z.number().int().min(0),
      status: z.enum(['pending', 'processing', 'completed', 'error'])
    }));
    
    this.contracts.set('POST /api/test-sessions', TestSessionSchema);
    this.contracts.set('GET /api/test-sessions', z.array(TestSessionSchema));
    this.contracts.set('GET /api/test-sessions/:id/results', ValidationMetricsSchema);
    
    this.contracts.set('GET /api/dashboard/stats', DashboardStatsSchema);
    this.contracts.set('GET /health', HealthCheckSchema);
    
    console.log(`✅ Initialized ${this.contracts.size} API contract validations`);
  }

  /**
   * Validate API response against contract
   */
  validateResponse(
    method: string,
    path: string,
    data: any,
    statusCode: number = 200
  ): ValidationResult {
    const startTime = performance.now();
    const endpointKey = `${method} ${this.normalizeEndpointPath(path)}`;
    
    // Update metrics
    this.metrics.totalValidations++;
    if (!this.metrics.endpointStats[endpointKey]) {
      this.metrics.endpointStats[endpointKey] = {
        validations: 0,
        failures: 0,
        avgTime: 0
      };
    }
    this.metrics.endpointStats[endpointKey].validations++;

    const violations: ContractViolation[] = [];

    try {
      // Handle error responses
      if (statusCode >= 400) {
        const errorValidation = ErrorResponseSchema.safeParse(data);
        if (!errorValidation.success) {
          violations.push({
            endpoint: endpointKey,
            violationType: 'invalid_error_format',
            message: 'Error response does not match expected format',
            severity: ValidationSeverity.ERROR,
            actualValue: data
          });
        }
      } else {
        // Validate successful responses
        const schema = this.contracts.get(endpointKey);
        if (schema) {
          const validation = schema.safeParse(data);
          if (!validation.success) {
            // Parse Zod errors into contract violations
            validation.error.issues.forEach(issue => {
              violations.push({
                endpoint: endpointKey,
                violationType: 'schema_validation_error',
                message: issue.message,
                severity: this.getViolationSeverity(issue.code),
                fieldPath: issue.path.join('.'),
                actualValue: issue.received,
                expectedType: issue.expected
              });
            });
          }
        } else {
          violations.push({
            endpoint: endpointKey,
            violationType: 'unknown_endpoint',
            message: `No contract defined for endpoint: ${endpointKey}`,
            severity: ValidationSeverity.WARNING
          });
        }
      }

      // Additional validation for critical endpoints
      if (this.isCriticalEndpoint(endpointKey)) {
        violations.push(...this.validateCriticalEndpoint(endpointKey, data, statusCode));
      }

    } catch (error) {
      violations.push({
        endpoint: endpointKey,
        violationType: 'validation_exception',
        message: `Validation error: ${error instanceof Error ? error.message : String(error)}`,
        severity: ValidationSeverity.ERROR
      });
    }

    const endTime = performance.now();
    const processingTime = endTime - startTime;
    
    // Update metrics
    this.metrics.responseTimeMs.push(processingTime);
    if (this.metrics.responseTimeMs.length > 1000) {
      this.metrics.responseTimeMs = this.metrics.responseTimeMs.slice(-1000);
    }
    
    const stats = this.metrics.endpointStats[endpointKey];
    if (violations.length > 0) {
      this.metrics.failures++;
      stats.failures++;
    }
    
    stats.avgTime = (stats.avgTime * (stats.validations - 1) + processingTime) / stats.validations;
    this.metrics.successRate = ((this.metrics.totalValidations - this.metrics.failures) / this.metrics.totalValidations) * 100;

    // Store validation history
    if (violations.length > 0) {
      this.validationHistory.push(...violations);
      if (this.validationHistory.length > 500) {
        this.validationHistory = this.validationHistory.slice(-500);
      }
    }

    return {
      isValid: violations.length === 0,
      violations,
      processingTime
    };
  }

  /**
   * Validate request data before sending
   */
  validateRequest(
    method: string,
    path: string,
    data: any
  ): ValidationResult {
    const startTime = performance.now();
    const endpointKey = `${method} ${this.normalizeEndpointPath(path)}`;
    const violations: ContractViolation[] = [];

    try {
      // Basic request validation
      if (method === 'POST' || method === 'PUT' || method === 'PATCH') {
        if (data !== undefined) {
          // Validate request body structure
          if (typeof data === 'object' && data !== null) {
            // Check for required fields based on endpoint
            violations.push(...this.validateRequestFields(endpointKey, data));
          } else if (typeof data !== 'string') { // Allow FormData as string
            violations.push({
              endpoint: endpointKey,
              violationType: 'invalid_request_type',
              message: 'Request body must be an object or FormData',
              severity: ValidationSeverity.ERROR,
              actualValue: typeof data
            });
          }
        }
      }
    } catch (error) {
      violations.push({
        endpoint: endpointKey,
        violationType: 'request_validation_error',
        message: `Request validation error: ${error instanceof Error ? error.message : String(error)}`,
        severity: ValidationSeverity.ERROR
      });
    }

    return {
      isValid: violations.length === 0,
      violations,
      processingTime: performance.now() - startTime
    };
  }

  private normalizeEndpointPath(path: string): string {
    // Convert dynamic paths to template format
    return path
      .replace(/\/\d+/g, '/:id') // Replace numeric IDs
      .replace(/\/[a-f0-9-]{36}/g, '/:id') // Replace UUIDs
      .replace(/\/[a-f0-9-]{8,}/g, '/:id'); // Replace other long IDs
  }

  private getViolationSeverity(zodErrorCode: string): ValidationSeverity {
    switch (zodErrorCode) {
      case 'invalid_type':
      case 'invalid_string':
      case 'invalid_number':
        return ValidationSeverity.ERROR;
      case 'too_small':
      case 'too_big':
        return ValidationSeverity.WARNING;
      default:
        return ValidationSeverity.INFO;
    }
  }

  private isCriticalEndpoint(endpoint: string): boolean {
    const criticalEndpoints = [
      'GET /api/videos/:id/annotations',
      'POST /api/videos/:id/annotations', 
      'GET /api/videos/:id/ground-truth',
      'POST /api/projects/:id/videos',
      'GET /api/projects/:id/videos',
      'POST /api/detection/pipeline/run',
      'GET /api/dashboard/stats',
      'POST /api/test-sessions',
      'GET /api/test-sessions/:id/results'
    ];
    return criticalEndpoints.includes(endpoint);
  }

  private validateCriticalEndpoint(
    endpoint: string,
    data: any,
    statusCode: number
  ): ContractViolation[] {
    const violations: ContractViolation[] = [];

    // Critical endpoints should never return server errors
    if (statusCode >= 500) {
      violations.push({
        endpoint,
        violationType: 'critical_endpoint_server_error',
        message: `Critical endpoint returned server error: ${statusCode}`,
        severity: ValidationSeverity.ERROR
      });
    }

    // Specific validations for annotation endpoints (GroundTruth issue source)
    if (endpoint.includes('/annotations')) {
      if (statusCode === 200 && Array.isArray(data)) {
        // Validate each annotation has required fields
        data.forEach((annotation, index) => {
          if (!annotation.id || !annotation.videoId || !annotation.boundingBox) {
            violations.push({
              endpoint,
              violationType: 'incomplete_annotation',
              message: `Annotation at index ${index} missing critical fields`,
              severity: ValidationSeverity.ERROR,
              fieldPath: `[${index}]`
            });
          }
        });
      }
    }

    // Ground truth endpoint validation
    if (endpoint.includes('/ground-truth')) {
      if (statusCode === 200 && data) {
        if (!data.video_id || !Array.isArray(data.objects)) {
          violations.push({
            endpoint,
            violationType: 'invalid_ground_truth_structure',
            message: 'Ground truth response missing required structure',
            severity: ValidationSeverity.ERROR
          });
        }
      }
    }

    return violations;
  }

  private validateRequestFields(endpoint: string, data: any): ContractViolation[] {
    const violations: ContractViolation[] = [];

    // Define required fields for different endpoints
    const requiredFields: Record<string, string[]> = {
      'POST /api/projects': ['name', 'cameraModel', 'cameraView', 'signalType'],
      'POST /api/videos/:id/annotations': ['frameNumber', 'timestamp', 'vruType', 'boundingBox'],
      'POST /api/test-sessions': ['name', 'project_id', 'video_id']
    };

    const required = requiredFields[endpoint];
    if (required) {
      required.forEach(field => {
        if (!(field in data) || data[field] === null || data[field] === undefined) {
          violations.push({
            endpoint,
            violationType: 'missing_required_field',
            message: `Missing required field: ${field}`,
            severity: ValidationSeverity.ERROR,
            fieldPath: field
          });
        }
      });
    }

    return violations;
  }

  /**
   * Get validation metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      averageResponseTime: this.metrics.responseTimeMs.length > 0 
        ? this.metrics.responseTimeMs.reduce((a, b) => a + b, 0) / this.metrics.responseTimeMs.length 
        : 0,
      contractsCovered: this.contracts.size,
      recentViolations: this.validationHistory.slice(-10)
    };
  }

  /**
   * Get contract health status
   */
  getHealthStatus() {
    const errorRate = this.metrics.failures / Math.max(this.metrics.totalValidations, 1);
    
    let status: 'healthy' | 'degraded' | 'unhealthy';
    if (errorRate > 0.1) {
      status = 'unhealthy';
    } else if (errorRate > 0.05) {
      status = 'degraded';
    } else {
      status = 'healthy';
    }

    return {
      status,
      contractVersion: API_CONTRACT_VERSION,
      totalValidations: this.metrics.totalValidations,
      successRate: this.metrics.successRate,
      errorRate: errorRate * 100,
      recentViolationCount: this.validationHistory.filter(v => 
        v.severity === ValidationSeverity.ERROR
      ).length,
      lastCheck: new Date().toISOString()
    };
  }

  /**
   * Clear validation history and reset metrics
   */
  reset() {
    this.validationHistory = [];
    this.metrics = {
      totalValidations: 0,
      failures: 0,
      successRate: 0,
      responseTimeMs: [],
      endpointStats: {}
    };
  }
}

// Global contract validator instance
export const contractValidator = new ContractValidator();

// Axios interceptor setup for automatic validation
export const setupContractInterceptors = (enableValidation: boolean = true) => {
  if (!enableValidation) return;

  // Request interceptor
  axios.interceptors.request.use(
    (config) => {
      if (config.method && config.url) {
        const validation = contractValidator.validateRequest(
          config.method.toUpperCase(),
          config.url,
          config.data
        );
        
        if (!validation.isValid && validation.violations.some(v => v.severity === ValidationSeverity.ERROR)) {
          console.error('Contract validation failed for request:', validation.violations);
          // In strict mode, you could reject the request here
          // return Promise.reject(new Error('Contract validation failed'));
        }
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor
  axios.interceptors.response.use(
    (response: AxiosResponse) => {
      if (response.config.method && response.config.url) {
        const validation = contractValidator.validateResponse(
          response.config.method.toUpperCase(),
          response.config.url,
          response.data,
          response.status
        );
        
        if (!validation.isValid) {
          console.warn('Contract validation warnings for response:', validation.violations);
          
          // Add validation metadata to response
          (response as any).contractValidation = validation;
        }
      }
      return response;
    },
    (error: AxiosError) => {
      if (error.response && error.config?.method && error.config?.url) {
        const validation = contractValidator.validateResponse(
          error.config.method.toUpperCase(),
          error.config.url,
          error.response.data,
          error.response.status
        );
        
        if (!validation.isValid) {
          console.error('Contract validation failed for error response:', validation.violations);
        }
      }
      return Promise.reject(error);
    }
  );

  console.log('✅ Contract validation interceptors setup complete');
};

// Validation utility functions
export const validateApiResponse = <T>(
  schema: z.ZodSchema<T>,
  data: unknown,
  endpoint: string
): T => {
  const result = schema.safeParse(data);
  if (!result.success) {
    const violations = result.error.issues.map(issue => ({
      endpoint,
      violationType: 'schema_validation_error',
      message: issue.message,
      severity: ValidationSeverity.ERROR as ValidationSeverity,
      fieldPath: issue.path.join('.'),
      actualValue: (issue as any).received,
      expectedType: (issue as any).expected
    }));
    
    console.error(`API response validation failed for ${endpoint}:`, violations);
    throw new Error(`API response validation failed: ${violations.map(v => v.message).join(', ')}`);
  }
  return result.data;
};

export const isValidApiResponse = <T>(
  schema: z.ZodSchema<T>,
  data: unknown
): data is T => {
  return schema.safeParse(data).success;
};

// Contract-aware API service wrapper
export class ContractAwareApiService {
  private apiService: any;
  
  constructor(apiService: any) {
    this.apiService = apiService;
  }
  
  async getProjects(): Promise<Project[]> {
    const response = await this.apiService.getProjects();
    return validateApiResponse(z.array(ProjectSchema), response, 'GET /api/projects');
  }
  
  async createProject(project: Partial<Project>): Promise<Project> {
    const response = await this.apiService.createProject(project);
    return validateApiResponse(ProjectSchema, response, 'POST /api/projects');
  }
  
  async getVideos(projectId: string): Promise<VideoFile[]> {
    const response = await this.apiService.getVideos(projectId);
    return validateApiResponse(z.array(VideoFileSchema), response, 'GET /api/projects/:id/videos');
  }
  
  async getAnnotations(videoId: string): Promise<Annotation[]> {
    const response = await this.apiService.getAnnotations(videoId);
    return validateApiResponse(z.array(AnnotationSchema), response, 'GET /api/videos/:id/annotations');
  }
  
  async getDashboardStats(): Promise<DashboardStats> {
    const response = await this.apiService.getDashboardStats();
    return validateApiResponse(DashboardStatsSchema, response, 'GET /api/dashboard/stats');
  }
  
  async healthCheck(): Promise<HealthCheck> {
    const response = await this.apiService.healthCheck();
    return validateApiResponse(HealthCheckSchema, response, 'GET /health');
  }
}

// Create contract-aware API service instance
export const contractAwareApi = new ContractAwareApiService(apiService);