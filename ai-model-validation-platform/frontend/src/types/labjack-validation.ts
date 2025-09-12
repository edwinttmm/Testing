// Example/Mock data for LabJack timing validation testing
import { LatencyValidationResult, DetectionLatencyEvent, LatencyStatistics } from './enhanced-results';

// Generate mock latency validation data for testing
export const generateMockLatencyValidationResult = (sessionId: string): LatencyValidationResult => {
  const totalDetections = Math.floor(Math.random() * 500) + 100; // 100-600 detections
  const passRate = Math.random() * 30 + 70; // 70-100% pass rate
  const passedDetections = Math.floor((passRate / 100) * totalDetections);
  const failedDetections = totalDetections - passedDetections;
  
  const baseLatency = Math.random() * 50 + 30; // 30-80ms base latency
  const avgLatency = baseLatency + Math.random() * 20;
  const maxLatency = avgLatency + Math.random() * 100 + 50;
  const minLatency = Math.max(10, baseLatency - Math.random() * 20);
  const threshold = 100; // 100ms threshold
  
  // Generate detection events
  const detectionEvents: DetectionLatencyEvent[] = [];
  for (let i = 0; i < Math.min(totalDetections, 50); i++) {
    const latency = Math.random() > 0.8 ? 
      avgLatency + Math.random() * 100 : // Some outliers
      avgLatency + (Math.random() - 0.5) * 30; // Normal distribution
    
    const passed = latency <= threshold;
    
    detectionEvents.push({
      id: `detection-${i}`,
      timestamp: Date.now() - (Math.random() * 3600 * 1000), // Last hour
      frame_number: i + 1,
      detection_time_ms: Math.max(10, latency),
      processing_latency_ms: Math.max(5, latency - 10),
      labJack_trigger_time_ms: Math.random() * 5,
      passed,
      error_message: !passed ? 'Exceeded latency threshold' : undefined
    });
  }
  
  // Generate latency distribution (histogram bins)
  const distributionBins = 20;
  const latencyDistribution: number[] = [];
  for (let i = 0; i < distributionBins; i++) {
    const binLatency = minLatency + (i / distributionBins) * (maxLatency - minLatency);
    const count = Math.exp(-Math.pow((binLatency - avgLatency) / 20, 2)) * totalDetections * 0.1;
    latencyDistribution.push(Math.max(0, Math.floor(count)));
  }
  
  const summaryStats: LatencyStatistics = {
    mean: avgLatency,
    median: avgLatency * 0.95,
    std_deviation: avgLatency * 0.2,
    p95: avgLatency * 1.5,
    p99: maxLatency * 0.8,
    outlier_count: Math.floor(totalDetections * 0.05),
    outlier_threshold_ms: avgLatency * 2
  };
  
  return {
    session_id: sessionId,
    total_detections: totalDetections,
    passed_detections: passedDetections,
    failed_detections: failedDetections,
    pass_rate: passRate,
    average_latency_ms: avgLatency,
    max_latency_ms: maxLatency,
    min_latency_ms: minLatency,
    latency_threshold_ms: threshold,
    latency_distribution: latencyDistribution,
    detection_events: detectionEvents,
    summary_statistics: summaryStats
  };
};

// Generate realistic timing validation scenarios
export const generateScenarioBasedLatencyData = (scenario: 'excellent' | 'good' | 'poor' | 'failing'): LatencyValidationResult => {
  const baseConfig = {
    session_id: `test-session-${scenario}`,
    total_detections: 250,
    latency_threshold_ms: 100
  };
  
  switch (scenario) {
    case 'excellent':
      return {
        ...baseConfig,
        passed_detections: 248,
        failed_detections: 2,
        pass_rate: 99.2,
        average_latency_ms: 35.5,
        max_latency_ms: 85.2,
        min_latency_ms: 18.3,
        latency_distribution: [2, 5, 12, 25, 45, 38, 28, 20, 15, 10, 8, 5, 3, 2, 1, 0, 0, 0, 0, 0],
        detection_events: [],
        summary_statistics: {
          mean: 35.5,
          median: 34.2,
          std_deviation: 12.8,
          p95: 55.8,
          p99: 75.2,
          outlier_count: 3,
          outlier_threshold_ms: 70
        }
      };
    
    case 'good':
      return {
        ...baseConfig,
        passed_detections: 235,
        failed_detections: 15,
        pass_rate: 94.0,
        average_latency_ms: 58.3,
        max_latency_ms: 145.8,
        min_latency_ms: 25.1,
        latency_distribution: [1, 3, 8, 18, 32, 45, 38, 28, 22, 18, 12, 8, 5, 3, 2, 1, 1, 0, 0, 0],
        detection_events: [],
        summary_statistics: {
          mean: 58.3,
          median: 56.7,
          std_deviation: 22.4,
          p95: 89.2,
          p99: 125.6,
          outlier_count: 8,
          outlier_threshold_ms: 120
        }
      };
    
    case 'poor':
      return {
        ...baseConfig,
        passed_detections: 195,
        failed_detections: 55,
        pass_rate: 78.0,
        average_latency_ms: 85.7,
        max_latency_ms: 285.4,
        min_latency_ms: 32.8,
        latency_distribution: [0, 2, 5, 12, 20, 28, 35, 38, 32, 25, 18, 12, 8, 5, 3, 2, 1, 1, 1, 0],
        detection_events: [],
        summary_statistics: {
          mean: 85.7,
          median: 82.3,
          std_deviation: 35.6,
          p95: 145.8,
          p99: 220.3,
          outlier_count: 15,
          outlier_threshold_ms: 180
        }
      };
    
    case 'failing':
      return {
        ...baseConfig,
        passed_detections: 125,
        failed_detections: 125,
        pass_rate: 50.0,
        average_latency_ms: 125.8,
        max_latency_ms: 450.2,
        min_latency_ms: 45.6,
        latency_distribution: [0, 1, 2, 5, 8, 12, 18, 22, 25, 28, 25, 22, 18, 15, 12, 8, 5, 3, 2, 1],
        detection_events: [],
        summary_statistics: {
          mean: 125.8,
          median: 118.5,
          std_deviation: 58.9,
          p95: 225.8,
          p99: 350.4,
          outlier_count: 35,
          outlier_threshold_ms: 280
        }
      };
    
    default:
      return generateMockLatencyValidationResult(baseConfig.session_id);
  }
};

// API endpoint configurations for LabJack validation
export const LABJACK_API_ENDPOINTS = {
  latencyValidation: '/api/enhanced-test-sessions/{sessionId}/latency-validation',
  alternativeResults: '/api/test-sessions/{sessionId}/results',
  realtimeLatency: '/ws/latency-validation/{sessionId}',
  exportLatencyReport: '/api/enhanced-test-sessions/{sessionId}/export/latency'
} as const;

// LabJack validation configuration
export interface LabJackValidationConfig {
  latencyThresholdMs: number;
  samplingRateHz: number;
  triggerChannels: string[];
  responseChannels: string[];
  realTimeUpdates: boolean;
  outlierDetection: boolean;
  statisticalAnalysis: boolean;
}

export const DEFAULT_LABJACK_CONFIG: LabJackValidationConfig = {
  latencyThresholdMs: 100,
  samplingRateHz: 1000,
  triggerChannels: ['AIN0', 'AIN1'],
  responseChannels: ['DAC0', 'DAC1'],
  realTimeUpdates: true,
  outlierDetection: true,
  statisticalAnalysis: true
};