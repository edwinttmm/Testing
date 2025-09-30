/**
 * Dashboard utilities and hooks index
 * Exports all dashboard-related utilities for easy importing
 */

// Utility functions
export * from './dashboardUtils';
export * from './chartHelpers';
export * from './performanceCalculators';

// Custom hooks
export * from './useAutoRefresh';
export * from './useDashboardFilters';

// Re-export commonly used types for convenience
export type {
  TimeSeriesData,
  DataPoint,
  MetricSummary,
} from './dashboardUtils';

export type {
  ChartColorScheme,
  GradientColors,
} from './chartHelpers';

export type {
  PerformanceMetric,
  KPIResult,
  TrendAnalysis,
  AccuracyMetrics,
  PerformanceStats,
} from './performanceCalculators';

export type {
  AutoRefreshConfig,
  AutoRefreshState,
  AutoRefreshControls,
  AutoRefreshHook,
} from './useAutoRefresh';

export type {
  DateRange,
  FilterOption,
  DashboardFilters,
  FilterState,
  FilterControls,
  DashboardFiltersHook,
} from './useDashboardFilters';