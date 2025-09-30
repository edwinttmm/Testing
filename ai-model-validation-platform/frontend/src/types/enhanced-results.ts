// Enhanced Results Types for comprehensive test execution analysis
// LabJack Timing Validation Types
export interface LatencyValidationResult {
  session_id: string;
  total_detections: number;
  passed_detections: number;
  failed_detections: number;
  pass_rate: number; // percentage 0-100
  average_latency_ms: number;
  max_latency_ms: number;
  min_latency_ms: number;
  latency_threshold_ms: number;
  latency_distribution: number[];
  detection_events: DetectionLatencyEvent[];
  summary_statistics: LatencyStatistics;
}

export interface DetectionLatencyEvent {
  id: string;
  timestamp: number;
  frame_number: number;
  detection_time_ms: number;
  processing_latency_ms?: number;
  labJack_trigger_time_ms: number;
  passed: boolean;
  error_message?: string;
  // Failure snapshot fields for timing validation
  screenshot_path?: string;
  screenshot_zoom_path?: string;
  failure_reason?: string;
  failure_type?: 'timing' | 'accuracy' | 'detection' | 'system' | 'voltage' | 'none';
  // Enhanced fields for ground truth integration
  voltage?: number;
  channel?: string;
  actual_latency_ms?: string;
}

export interface LatencyStatistics {
  mean: number;
  median: number;
  std_deviation: number;
  p95: number;
  p99: number;
  outlier_count: number;
  outlier_threshold_ms: number;
}

// Legacy AI validation types (maintained for compatibility)
export interface FrameAnalysisResult {
  frameNumber: number;
  timestamp: number;
  detectionCount: number;
  processingLatencyMs: number;
  confidenceDistribution: number[];
  detections: FrameDetection[];
  groundTruthMatch: {
    truePositives: number;
    falsePositives: number;
    falseNegatives: number;
    iouScores: number[];
  };
}

export interface FrameDetection {
  id: string;
  frameNumber: number;
  timestamp: number;
  className: string;
  vruType: 'pedestrian' | 'cyclist' | 'motorcyclist' | 'wheelchair_user' | 'scooter_rider';
  confidence: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  trackingId?: string;
  groundTruthId?: string;
  iouScore?: number;
  isGroundTruth: boolean;
  matchType?: 'true_positive' | 'false_positive' | 'false_negative' | 'unmatched' | 'video_ended';
  // Failure snapshot fields
  failed?: boolean;
  screenshot_path?: string;
  screenshot_zoom_path?: string;
  failure_reason?: string;
  failure_type?: 'timing' | 'accuracy' | 'detection' | 'system';
}

export interface EnhancedTestExecution {
  sessionId: string;
  sessionName: string;
  projectId: string;
  videoId: string;
  status: 'preparing' | 'running' | 'analyzing' | 'completed' | 'failed' | 'cancelled';
  progress: {
    currentFrame: number;
    totalFrames: number;
    currentPhase: 'initialization' | 'detection' | 'comparison' | 'analysis' | 'finalization';
    phaseProgress: number;
    estimatedTimeRemaining?: number;
  };
  realtimeResults: {
    currentFrame: FrameAnalysisResult;
    runningMetrics: RunningMetrics;
    detectionEvents: DetectionEvent[];
    anomalies: AnomalyDetection[];
  };
  startTime: string;
  endTime?: string;
  duration?: number;
  config: TestExecutionConfig;
}

export interface RunningMetrics {
  totalFramesProcessed: number;
  totalDetections: number;
  averageConfidence: number;
  averageProcessingLatency: number;
  detectionRate: number;
  // Legacy AI metrics
  accuracyEstimate: number;
  precisionEstimate: number;
  recallEstimate: number;
  f1ScoreEstimate: number;
  confidenceDistribution: {
    high: number; // >0.8
    medium: number; // 0.5-0.8
    low: number; // <0.5
  };
  // LabJack timing metrics
  passRateEstimate?: number;
  currentPassRate?: number;
  currentFailureRate?: number;
  latencyDistribution?: {
    fast: number; // <50ms
    normal: number; // 50-100ms
    slow: number; // >100ms
  };
}

export interface DetectionEvent {
  id: string;
  timestamp: number;
  frameNumber: number;
  eventType: 'detection' | 'ground_truth_match' | 'ground_truth_miss' | 'false_positive';
  vruType: string;
  confidence?: number;
  details: Record<string, unknown>;
  // Failure snapshot fields
  failed?: boolean;
  screenshot_path?: string;
  screenshot_zoom_path?: string;
  failure_reason?: string;
  failure_type?: 'timing' | 'accuracy' | 'detection' | 'system';
}

export interface AnomalyDetection {
  id: string;
  timestamp: number;
  frameNumber: number;
  anomalyType: 'confidence_drop' | 'processing_delay' | 'detection_gap' | 'unusual_pattern';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  metadata: Record<string, unknown>;
}

export interface TestExecutionConfig {
  detectionModel: string;
  confidenceThreshold: number;
  nmsThreshold: number;
  targetClasses: string[];
  processingOptions: {
    batchSize: number;
    skipFrames: number;
    maxFrames?: number;
  };
  comparisonOptions: {
    iouThreshold: number;
    enableTrackingAnalysis: boolean;
    temporalWindowMs: number;
  };
  realtimeUpdates: boolean;
  saveIntermediateResults: boolean;
}

// Ground Truth Comparison Types
export interface GroundTruthComparison {
  sessionId: string;
  videoId: string;
  totalFrames: number;
  comparisonResults: FrameComparisonResult[];
  overallMetrics: ComparisonMetrics;
  perClassMetrics: Record<string, ComparisonMetrics>;
  temporalAnalysis: TemporalAnalysis;
  spatialAnalysis: SpatialAnalysis;
}

export interface FrameComparisonResult {
  frameNumber: number;
  timestamp: number;
  groundTruthDetections: FrameDetection[];
  testDetections: FrameDetection[];
  matches: DetectionMatch[];
  unmatched: {
    groundTruth: FrameDetection[];
    test: FrameDetection[];
  };
  frameMetrics: ComparisonMetrics;
}

export interface DetectionMatch {
  groundTruthDetection: FrameDetection;
  testDetection: FrameDetection;
  iouScore: number;
  confidenceScore: number;
  spatialError: {
    centerDistancePixels: number;
    areaRatio: number;
    aspectRatioError: number;
  };
  classMatch: boolean;
  temporalConsistency?: number;
}

// Updated ComparisonMetrics for LabJack timing validation
export interface ComparisonMetrics {
  // Legacy AI metrics (maintained for compatibility)
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  trueNegatives?: number;
  totalDetections?: number;
  matchedDetections?: number;
  unmatchedGroundTruth?: number;
  meanIoU?: number;
  meanConfidence?: number;
  averageIou: number;
  averageConfidence: number;
  averageLatency: number;
  
  // LabJack timing validation metrics
  passRate?: number; // percentage 0-100
  averageLatencyMs?: number;
  maxLatencyMs?: number;
  minLatencyMs?: number;
  latencyThresholdMs?: number;
  failedDetections?: number;
  passedDetections?: number;
}

export interface TemporalAnalysis {
  trackingConsistency?: number;
  temporalStability?: number;
  performanceOverTime: Array<{
    timestamp: number;
    frameNumber: number;
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
    detectionCount: number;
    processingLatency: number;
    truePositives: number;
    falsePositives: number;
    falseNegatives: number;
    averageIou: number;
  }>;
  detectionGaps: Array<{
    startFrame: number;
    endFrame: number;
    duration: number;
    severity?: 'low' | 'medium' | 'high';
    affectedObjects?: string[];
  }>;
  consistencyScore?: number;
  temporalPatterns?: Array<{
    pattern: string;
    frequency: number;
    confidence: number;
  }>;
}

export interface SpatialAnalysis {
  detectionHeatmap?: Array<{
    x: number;
    y: number;
    intensity: number;
    detectionCount: number;
  }>;
  spatialDistribution: {
    quadrants?: Record<string, number>;
    hotspots?: Array<{
      x: number;
      y: number;
      radius: number;
      density: number;
    }>;
  };
  coverageAnalysis?: {
    coveredRegions: number;
    hotspots: Array<{
      x: number;
      y: number;
      radius: number;
      density: number;
    }>;
    blindSpots: Array<{
      x: number;
      y: number;
      radius: number;
      severity: string;
    }>;
  };
  boundingBoxQuality: {
    averageIou: number;
    tightnessFactor: number;
    consistencyScore: number;
  };
  occlusionAnalysis: {
    totalOccluded: number;
    partialOcclusion: number;
    fullOcclusion: number;
    occlusionImpact: number;
  };
}

// Statistical Validation Types
export interface StatisticalValidationResult {
  sessionId: string;
  validationId: string;
  timestamp: string;
  sampleSize: number;
  confidenceLevel: number;
  statisticalTests: {
    tTest: TTestResult;
    mannWhitneyU: MannWhitneyUResult;
    kolmogorovSmirnov: KolmogorovSmirnovResult;
    chisquare: ChiSquareResult;
  };
  confidenceIntervals: ConfidenceIntervals;
  effectSize: EffectSizeAnalysis;
  powerAnalysis: PowerAnalysis;
  validationSummary: ValidationSummary;
}

export interface TTestResult {
  statistic: number;
  pValue: number;
  degreesOfFreedom: number;
  criticalValue: number;
  isSignificant: boolean;
  effectSize: number;
  confidenceInterval: [number, number];
}

export interface MannWhitneyUResult {
  uStatistic: number;
  pValue: number;
  zScore: number;
  isSignificant: boolean;
  rankSums: {
    group1: number;
    group2: number;
  };
}

export interface KolmogorovSmirnovResult {
  kStatistic: number;
  pValue: number;
  criticalValue: number;
  isSignificant: boolean;
  maxDivergence: number;
}

export interface ChiSquareResult {
  chiSquareStatistic: number;
  pValue: number;
  degreesOfFreedom: number;
  expectedFrequencies: number[];
  observedFrequencies: number[];
  isSignificant: boolean;
}

export interface ConfidenceIntervals {
  accuracy: ConfidenceInterval;
  precision: ConfidenceInterval;
  recall: ConfidenceInterval;
  f1Score: ConfidenceInterval;
  latency: ConfidenceInterval;
  iou: ConfidenceInterval;
}

export interface ConfidenceInterval {
  estimate: number;
  lowerBound: number;
  upperBound: number;
  confidenceLevel: number;
  marginOfError: number;
  standardError: number;
  method: 'bootstrap' | 'normal' | 'student_t' | 'wilson';
}

export interface EffectSizeAnalysis {
  cohensD: number;
  hedgesG: number;
  glasssDelta: number;
  cliffsDelta: number;
  interpretation: 'negligible' | 'small' | 'medium' | 'large' | 'very_large';
  practicalSignificance: boolean;
}

export interface PowerAnalysis {
  observedPower: number;
  requiredSampleSize: number;
  minimumDetectableEffect: number;
  powerCurve: Array<{
    sampleSize: number;
    power: number;
  }>;
  recommendations: string[];
}

export interface ValidationSummary {
  overallSignificance: boolean;
  significantTests: string[];
  nonSignificantTests: string[];
  recommendations: string[];
  dataQuality: {
    completeness: number;
    consistency: number;
    outliers: number;
    normalityScore: number;
  };
  limitations: string[];
}

// Visual Analytics Types
export interface VisualizationData {
  sessionId: string;
  charts: {
    performanceTimeline: TimelineChartData;
    confidenceDistribution: DistributionChartData;
    confusionMatrix: ConfusionMatrixData;
    rocCurve: ROCCurveData;
    precisionRecallCurve: PRCurveData;
    latencyDistribution: DistributionChartData;
    spatialHeatmap: HeatmapData;
    temporalPatterns: TemporalPatternData;
  };
  interactiveElements: {
    frameNavigation: boolean;
    detectionFiltering: boolean;
    zoomableCharts: boolean;
    exportOptions: string[];
  };
}

export interface TimelineChartData {
  data: Array<{
    timestamp: number;
    frameNumber: number;
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
    detectionCount: number;
    processingLatency: number;
  }>;
  annotations: Array<{
    timestamp: number;
    type: 'anomaly' | 'milestone' | 'error';
    label: string;
    description: string;
  }>;
}

export interface DistributionChartData {
  bins: Array<{
    min: number;
    max: number;
    count: number;
    density: number;
  }>;
  statistics: {
    mean: number;
    median: number;
    mode: number;
    standardDeviation: number;
    skewness: number;
    kurtosis: number;
  };
  outliers: number[];
}

export interface ConfusionMatrixData {
  classes: string[];
  matrix: number[][];
  normalized: number[][];
  classMetrics: Record<string, {
    precision: number;
    recall: number;
    f1Score: number;
    support: number;
  }>;
}

export interface ROCCurveData {
  curves: Array<{
    className: string;
    fpr: number[];
    tpr: number[];
    auc: number;
    thresholds: number[];
  }>;
  microAverage: {
    fpr: number[];
    tpr: number[];
    auc: number;
  };
  macroAverage: {
    fpr: number[];
    tpr: number[];
    auc: number;
  };
}

export interface PRCurveData {
  curves: Array<{
    className: string;
    precision: number[];
    recall: number[];
    ap: number;
    thresholds: number[];
  }>;
  microAverage: {
    precision: number[];
    recall: number[];
    ap: number;
  };
  macroAverage: {
    precision: number[];
    recall: number[];
    ap: number;
  };
}

export interface HeatmapData {
  width: number;
  height: number;
  data: Array<{
    x: number;
    y: number;
    intensity: number;
    detectionCount: number;
  }>;
  colorScale: {
    min: number;
    max: number;
    colormap: string;
  };
}

export interface TemporalPatternData {
  patterns: Array<{
    id: string;
    name: string;
    description: string;
    frequency: number;
    confidence: number;
    timeRanges: Array<{
      start: number;
      end: number;
      strength: number;
    }>;
  }>;
  periodicities: Array<{
    period: number;
    amplitude: number;
    phase: number;
    significance: number;
  }>;
}

// Real-time Streaming Types
export interface RealTimeUpdate {
  sessionId: string;
  updateType: 'frame_processed' | 'metrics_updated' | 'anomaly_detected' | 'phase_changed' | 'completed' | 'error';
  timestamp: string;
  data: {
    currentFrame?: FrameAnalysisResult;
    runningMetrics?: RunningMetrics;
    anomaly?: AnomalyDetection;
    phase?: string;
    progress?: number;
    error?: string;
    finalResults?: GroundTruthComparison;
  };
}

export interface StreamingConnection {
  sessionId: string;
  isConnected: boolean;
  lastUpdate: string;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error' | 'reconnecting';
  messageCount: number;
  errorCount: number;
  latency: number;
}

// Failure Snapshot Display Types
export interface FailureSnapshotData {
  id: string;
  frameNumber: number;
  timestamp: number;
  screenshot_path: string;
  screenshot_zoom_path?: string;
  failure_reason: string;
  failure_type: 'timing' | 'accuracy' | 'detection' | 'system';
  detection_id?: string;
  event_id?: string;
  confidence?: number;
  expected_value?: number;
  actual_value?: number;
  threshold?: number;
  metadata?: Record<string, unknown>;
}

export interface SnapshotDisplaySettings {
  showThumbnails: boolean;
  enableZoom: boolean;
  lazyLoading: boolean;
  imageQuality: 'low' | 'medium' | 'high';
  maxWidth: number;
  maxHeight: number;
  groupByType: boolean;
  sortBy: 'timestamp' | 'frame' | 'severity';
  filterByType?: ('timing' | 'accuracy' | 'detection' | 'system')[];
}

export interface ImageLoadingState {
  loading: boolean;
  error?: string;
  retryCount: number;
  loaded: boolean;
}

export interface ZoomModalState {
  isOpen: boolean;
  imageUrl?: string;
  title?: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

// Export and Analysis Types
export interface ResultsExportConfig {
  sessionId: string;
  format: 'pdf' | 'excel' | 'csv' | 'json' | 'html';
  sections: {
    executiveSummary: boolean;
    detailedMetrics: boolean;
    frameByFrameAnalysis: boolean;
    statisticalValidation: boolean;
    visualizations: boolean;
    rawData: boolean;
    recommendations: boolean;
  };
  visualizationOptions: {
    includeCharts: boolean;
    chartFormat: 'png' | 'svg' | 'pdf';
    resolution: 'low' | 'medium' | 'high';
    colorScheme: 'default' | 'dark' | 'grayscale' | 'colorblind_friendly';
  };
  filtering: {
    frameRange?: [number, number];
    confidenceThreshold?: number;
    classFilter?: string[];
    timeRange?: [string, string];
    includeFailureSnapshots?: boolean;
    onlyFailures?: boolean;
  };
}

export interface ResultsExportStatus {
  exportId: string;
  status: 'preparing' | 'generating' | 'completed' | 'failed';
  progress: number;
  estimatedTimeRemaining?: number;
  downloadUrl?: string;
  error?: string;
  fileSize?: number;
  generatedAt?: string;
}

// Performance Benchmark Types
export interface PerformanceBenchmark {
  sessionId: string;
  benchmarkId: string;
  baseline: ComparisonMetrics;
  current: ComparisonMetrics;
  improvement: {
    accuracy: number;
    precision: number;
    recall: number;
    f1Score: number;
    latency: number;
  };
  significantChanges: Array<{
    metric: string;
    change: number;
    isImprovement: boolean;
    isSignificant: boolean;
    pValue: number;
  }>;
  recommendations: Array<{
    category: 'performance' | 'accuracy' | 'efficiency';
    priority: 'high' | 'medium' | 'low';
    description: string;
    expectedImpact: number;
  }>;
}

// Integration Types for Results Page
export interface EnhancedResultsPageState {
  selectedSession: string | null;
  activeTab: 'overview' | 'comparison' | 'statistics' | 'timeline' | 'export';
  streamingConnection: StreamingConnection | null;
  realtimeUpdates: boolean;
  filters: ResultsFilter;
  comparisonMode: ComparisonViewMode;
  exportConfig: ResultsExportConfig | null;
  visualizationSettings: VisualizationSettings;
}

export interface ResultsFilter {
  dateRange?: [string, string];
  sessionIds?: string[];
  projectIds?: string[];
  performanceThreshold?: {
    minAccuracy?: number;
    minPrecision?: number;
    minRecall?: number;
    maxLatency?: number;
  };
  statusFilter?: Array<'preparing' | 'running' | 'completed' | 'failed'>;
  sortBy: 'date' | 'accuracy' | 'precision' | 'recall' | 'f1Score' | 'latency';
  sortOrder: 'asc' | 'desc';
  searchTerm?: string;
}

export interface ComparisonViewMode {
  layout: 'side_by_side' | 'overlay' | 'difference_map' | 'timeline_sync';
  showGroundTruth: boolean;
  showPredictions: boolean;
  highlightMismatches: boolean;
  overlayOpacity: number;
  frameSync: boolean;
  playbackSpeed: number;
}

export interface VisualizationSettings {
  colorScheme: 'default' | 'dark' | 'colorblind_friendly' | 'high_contrast';
  animation: boolean;
  interactivity: boolean;
  autoRefresh: boolean;
  refreshInterval: number;
  maxDataPoints: number;
  smoothing: boolean;
}

// Enhanced HIL Results with Ground Truth Comparison
export interface EnhancedHILResults {
  session_id: string;
  hardware_status: {
    labjack_connected: boolean;
    model: string;
    firmware_version?: string;
    channels_active?: number;
    sample_rate?: number;
  };
  video_timing: {
    startup_delay_ms: number;
    timing_sync_status: string;
    timing_accuracy_ns: number | null;
    fps?: number;
    duration?: number;
    filename?: string;
  };
  detection_statistics: {
    total_detections: number;
    original_results: {
      average_apparent_latency_ms: number;
      passed_detections: number;
      failed_detections: number;
      pass_rate: number;
    };
    corrected_results: {
      average_real_latency_ms: number;
      median_real_latency_ms: number;
      passed_detections: number;
      failed_detections: number;
      pass_rate: number;
    };
  };
  ground_truth_comparison?: {
    ground_truth_events_available: number;
    total_detections: number;
    events_with_matches: number;
    average_confidence_score: number;
    timing_quality_distribution: {
      excellent?: number;
      good?: number;
      fair?: number;
      poor?: number;
    };
    precision?: number;
    recall?: number;
    f1_score?: number;
    true_positives?: number;
    false_positives?: number;
    false_negatives?: number;
  };
  detection_events: Array<{
    event_id: string;
    detection_time: string;
    labjack_trigger_time: string;
    frame_number: number;
    threshold_ms: number;
    result: 'pass' | 'fail';
    voltage_level: number;
    original_latency?: {
      apparent_latency_ms: number;
    };
    corrected_latency?: {
      real_latency_ms: number;
    };
    timing_synchronization?: {
      timing_quality: 'excellent' | 'good' | 'fair' | 'poor';
      confidence_score: number;
      ground_truth_available: boolean;
    };
    measured_breakdown?: {
      system_processing_ms: number;
      frame_timing_variance_ms: number;
      initial_startup_effect_ms: number;
      camera_processing_note: string;
      total_measured_latency_ms: number;
      measurement_source: string;
      measurement_method: string;
      note?: string;
    };
  }>;
  session_info?: {
    project_name?: string;
    name?: string;
    duration_seconds?: number;
    status?: string;
    start_time?: string;
    end_time?: string;
    operator?: string;
  };
}

// Ground Truth Event Structure
export interface GroundTruthEvent {
  id: string;
  timestamp: number;
  video_frame: number;
  frame_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
  class_label: string;
  confidence: number;
  validated: boolean;
  difficult?: boolean;
}

// Ground Truth Comparison Metrics
export interface GroundTruthComparisonMetrics {
  ground_truth_events_available: number;
  total_detections: number;
  events_with_matches: number;
  average_confidence_score: number;
  timing_quality_distribution: {
    excellent: number;
    good: number;
    fair: number;
    poor: number;
  };
  precision: number;
  recall: number;
  f1_score: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
}

// Enhanced Detection Event with Ground Truth Integration
export interface EnhancedDetectionEvent extends DetectionLatencyEvent {
  // Enhanced timing fields
  real_latency_ms?: number;
  apparent_latency_ms?: number;
  timing_quality?: 'excellent' | 'good' | 'fair' | 'poor';
  confidence_score?: number;
  processing_time_ms?: number;
  
  // Ground truth matching
  ground_truth_match_id?: string;
  ground_truth_available?: boolean;
  match_distance_pixels?: number;
  match_iou_score?: number;
  
  // Video timing context
  video_frame?: number;
  voltage?: number;
  labjack_voltage?: number;
  channel?: string;
  
  // Measured breakdown
  measured_breakdown?: {
    system_processing_ms: number | string;
    frame_timing_variance_ms: number;
    initial_startup_effect_ms: number;
    camera_processing_note: string;
    total_measured_latency_ms: number;
    measurement_source: string;
    measurement_method: string;
    note?: string;
  };
}

// Raw Timing Data Types for Hybrid Logging System
export interface RawTimingData {
  session_id: string;
  data_source: 'hybrid_raw_compression' | 'legacy_detection_events';
  timing_precision: 'microsecond' | 'second';
  sample_rate_actual_hz: number;
  session_info: RawSessionInfo;
  voltage_transitions?: VoltageTransition[];
  voltage_run_periods?: VoltageRunPeriod[];
  compression_statistics?: CompressionStatistics;
  timing_correlation?: TimingCorrelation;
}

export interface RawSessionInfo {
  start_timestamp_us?: number;
  end_timestamp_us?: number;
  duration_us?: number;
  total_samples?: number;
  compression_ratio?: number;
  data_quality_score?: number;
}

export interface VoltageTransition {
  id: string;
  timestamp_us: number;
  timestamp_ms: number;
  channel: string;
  voltage_before_v: number;
  voltage_after_v: number;
  voltage_delta_v: number;
  transition_type: 'rising_edge' | 'falling_edge' | 'spike' | 'drift' | 'noise';
  is_detection_event: boolean;
  detection_confidence: number;
  signal_quality_score: number;
  transition_duration_us?: number;
  slope_v_per_s?: number;
  sequence_number: number;
  time_since_last_us?: number;
  data_source?: string;
}

export interface VoltageRunPeriod {
  id: string;
  start_timestamp_us: number;
  end_timestamp_us: number;
  duration_us: number;
  channel: string;
  steady_voltage_v: number;
  voltage_min_v?: number;
  voltage_max_v?: number;
  sample_count: number;
  sequence_number: number;
  confidence_score: number;
}

export interface CompressionStatistics {
  achieved_compression_ratio?: number;
  signal_fidelity_score?: number;
  data_loss_estimate?: number;
  throughput_samples_per_second?: number;
  raw_data_size_bytes?: number;
  compressed_data_size_bytes?: number;
  storage_efficiency_percent?: number;
  note?: string;
}

export interface TimingCorrelation {
  legacy_events_count?: number;
  raw_detection_transitions_count?: number;
  timing_comparison?: TimingComparisonPoint[];
  frequency_analysis?: FrequencyAnalysis;
  note?: string;
  error?: string;
}

export interface TimingComparisonPoint {
  legacy_timestamp_us: number;
  raw_timestamp_us: number;
  difference_us: number;
  difference_ms: number;
  detection_confidence: number;
}

export interface FrequencyAnalysis {
  raw_average_interval_ms: number;
  legacy_average_interval_ms: number;
  raw_frequency_hz: number;
  legacy_frequency_hz: number;
}

export interface TimelineData {
  session_id: string;
  resolution_us: number;
  timeline_start_us: number;
  timeline_end_us: number;
  duration_us: number;
  timeline_points: TimelinePoint[];
  video_sync_events: VideoSyncEvent[];
  summary: TimelineSummary;
}

export interface TimelinePoint {
  timestamp_us: number;
  timestamp_ms: number;
  window_duration_us: number;
  total_transitions: number;
  detection_transitions: number;
  transition_rate_hz: number;
}

export interface VideoSyncEvent {
  timestamp_us: number;
  timestamp_ms: number;
  frame_number?: number;
  latency_ms?: number;
  voltage_level?: number;
}

export interface TimelineSummary {
  total_timeline_points: number;
  total_video_sync_events: number;
  peak_transition_rate_hz: number;
}

export interface RawDataExport {
  session_id: string;
  export_timestamp: string;
  format: string;
  compressed: boolean;
  data: RawTimingData;
  export_metadata?: {
    total_transitions: number;
    total_run_periods: number;
    timing_precision: string;
    data_source: string;
    sample_rate_hz: number;
    export_tool: string;
    export_version: string;
  };
}