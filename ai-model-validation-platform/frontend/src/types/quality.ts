/**
 * Quality Metrics Type Definitions
 *
 * Complete type definitions for quality monitoring and validation features.
 * NO partial types, NO any types - fully typed for production use.
 */

/**
 * Quality warning severity levels
 */
export enum QualityWarningSeverity {
  INFO = 'INFO',
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL'
}

/**
 * Quality warning category types
 */
export enum QualityWarningCategory {
  TIMING = 'timing',
  ACCURACY = 'accuracy',
  COVERAGE = 'coverage',
  SYSTEM = 'system',
  DATA_QUALITY = 'data_quality'
}

/**
 * Quality level classifications
 */
export enum QualityLevel {
  EXCELLENT = 'EXCELLENT',
  GOOD = 'GOOD',
  FAIR = 'FAIR',
  POOR = 'POOR',
  UNKNOWN = 'UNKNOWN'
}

/**
 * Quality warning with actionable information
 */
export interface QualityWarning {
  id: string;
  session_id: string;
  video_id?: string;
  severity: QualityWarningSeverity;
  category: QualityWarningCategory;
  message: string;
  impact: string;
  recommendation: string;
  detection_count?: number;
  affected_videos?: string[];
  created_at: string;
  acknowledged?: boolean;
}

/**
 * Session-level timing health status
 */
export interface TimingHealthStatus {
  session_id: string;
  timing_degraded: boolean;
  timing_verified: boolean;
  total_detections: number;
  degraded_count: number;
  verified_count: number;
  quality_level: QualityLevel;
  degradation_percentage: number;
  validation_rate: number;
  usable_detections_count: number;
  timestamp: string;
}

/**
 * Video-specific quality metrics
 */
export interface VideoQualityMetrics {
  video_id: string;
  video_name?: string;
  total_detections: number;
  usable_count: number;
  degraded_count: number;
  validation_rate: number;
  quality_level: QualityLevel;
  timing_stats: {
    mean_latency_ms: number;
    median_latency_ms: number;
    max_latency_ms: number;
    min_latency_ms: number;
    std_deviation_ms: number;
  };
  accuracy_stats?: {
    precision: number;
    recall: number;
    f1_score: number;
    true_positives: number;
    false_positives: number;
    false_negatives: number;
  };
}

/**
 * Global quality metrics across all sessions
 */
export interface GlobalQualityMetrics {
  total_sessions: number;
  total_detections: number;
  overall_validation_rate: number;
  overall_quality_level: QualityLevel;
  sessions_with_issues: number;
  sessions_excellent: number;
  sessions_good: number;
  sessions_fair: number;
  sessions_poor: number;
  recent_warnings: QualityWarning[];
  trend_data: QualityTrendData[];
  last_updated: string;
}

/**
 * Quality trend data for visualization
 */
export interface QualityTrendData {
  timestamp: string;
  date: string;
  validation_rate: number;
  quality_level: QualityLevel;
  session_count: number;
  degraded_count: number;
  total_detections: number;
}

/**
 * Quality information for a single session
 */
export interface QualityInfo {
  session_id: string;
  quality_level: QualityLevel;
  validation_rate: number;
  timing_health: TimingHealthStatus;
  warnings: QualityWarning[];
  video_metrics?: VideoQualityMetrics[];
  summary: {
    total_detections: number;
    usable_detections: number;
    degraded_detections: number;
    critical_issues: number;
    has_warnings: boolean;
  };
}

/**
 * Detection quality flags
 */
export interface DetectionQualityFlags {
  usable_for_validation: boolean;
  timing_degraded: boolean;
  timing_verified: boolean;
  quality_score?: number;
  degradation_reason?: string;
  confidence_level?: number;
}

/**
 * Quality filter options
 */
export type QualityFilterType = 'all' | 'validated' | 'degraded' | 'verified';

/**
 * Quality statistics for filtering
 */
export interface QualityFilterStats {
  all_count: number;
  validated_count: number;
  degraded_count: number;
  verified_count: number;
}

/**
 * API request parameters for quality endpoints
 */
export interface QualityApiParams {
  session_id?: string;
  video_id?: string;
  start_date?: string;
  end_date?: string;
  severity?: QualityWarningSeverity[];
  category?: QualityWarningCategory[];
  limit?: number;
  offset?: number;
}

/**
 * API response wrapper for quality data
 */
export interface QualityApiResponse<T> {
  success: boolean;
  data: T;
  timestamp: string;
  cache_hit?: boolean;
  error?: string;
}

/**
 * Quality alert configuration
 */
export interface QualityAlertConfig {
  enabled: boolean;
  min_severity: QualityWarningSeverity;
  categories: QualityWarningCategory[];
  notification_channels: ('ui' | 'email' | 'webhook')[];
  auto_dismiss_info: boolean;
  show_recommendations: boolean;
}

/**
 * Quality report export options
 */
export interface QualityReportOptions {
  session_ids: string[];
  include_warnings: boolean;
  include_trends: boolean;
  include_video_breakdown: boolean;
  date_range?: {
    start: string;
    end: string;
  };
  format: 'pdf' | 'excel' | 'json' | 'csv';
}

/**
 * Quality monitoring preferences
 */
export interface QualityPreferences {
  auto_refresh: boolean;
  refresh_interval_ms: number;
  show_dismissed_warnings: boolean;
  default_filter: QualityFilterType;
  alert_config: QualityAlertConfig;
  chart_animation: boolean;
  compact_view: boolean;
}
