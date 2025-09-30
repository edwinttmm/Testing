/**
 * Performance metric calculators for KPIs, trends, and analytics
 */

import { differenceInDays, parseISO, startOfDay, endOfDay } from 'date-fns';

export interface PerformanceMetric {
  value: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface KPIResult {
  current: number;
  previous: number;
  change: number;
  changePercent: number;
  trend: 'up' | 'down' | 'stable';
  status: 'good' | 'warning' | 'critical';
}

export interface TrendAnalysis {
  direction: 'increasing' | 'decreasing' | 'stable';
  strength: 'weak' | 'moderate' | 'strong';
  correlation: number;
  forecast?: number[];
}

export interface AccuracyMetrics {
  overall: number;
  precision: number;
  recall: number;
  f1Score: number;
  confusionMatrix: number[][];
}

export interface PerformanceStats {
  responseTime: {
    mean: number;
    median: number;
    p95: number;
    p99: number;
    min: number;
    max: number;
  };
  throughput: {
    requestsPerSecond: number;
    requestsPerMinute: number;
    requestsPerHour: number;
  };
  errorRate: {
    percentage: number;
    total: number;
    byType: Record<string, number>;
  };
  uptime: {
    percentage: number;
    totalTime: number;
    downtime: number;
  };
}

/**
 * Calculates accuracy metrics from predictions and ground truth
 */
export const calculateAccuracyMetrics = (
  predictions: number[],
  groundTruth: number[],
  threshold: number = 0.5
): AccuracyMetrics => {
  if (predictions.length !== groundTruth.length) {
    throw new Error('Predictions and ground truth arrays must have the same length');
  }

  // Convert to binary classifications
  const binaryPreds = predictions.map(p => p >= threshold ? 1 : 0);
  const binaryTruth = groundTruth.map(t => t >= threshold ? 1 : 0);

  // Calculate confusion matrix
  let tp = 0, fp = 0, tn = 0, fn = 0;
  
  for (let i = 0; i < binaryPreds.length; i++) {
    if (binaryTruth[i] === 1 && binaryPreds[i] === 1) tp++;
    else if (binaryTruth[i] === 0 && binaryPreds[i] === 1) fp++;
    else if (binaryTruth[i] === 0 && binaryPreds[i] === 0) tn++;
    else if (binaryTruth[i] === 1 && binaryPreds[i] === 0) fn++;
  }

  const confusionMatrix = [
    [tp, fp],
    [fn, tn]
  ];

  // Calculate metrics
  const precision = tp + fp > 0 ? tp / (tp + fp) : 0;
  const recall = tp + fn > 0 ? tp / (tp + fn) : 0;
  const overall = (tp + tn) / (tp + tn + fp + fn);
  const f1Score = precision + recall > 0 ? 2 * (precision * recall) / (precision + recall) : 0;

  return {
    overall,
    precision,
    recall,
    f1Score,
    confusionMatrix,
  };
};

/**
 * Calculates response time percentiles
 */
export const calculateResponseTimePercentiles = (responseTimes: number[]): {
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
} => {
  if (responseTimes.length === 0) {
    return { p50: 0, p75: 0, p90: 0, p95: 0, p99: 0 };
  }

  const sorted = [...responseTimes].sort((a, b) => a - b);
  
  const getPercentile = (p: number): number => {
    const index = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, index)];
  };

  return {
    p50: getPercentile(50),
    p75: getPercentile(75),
    p90: getPercentile(90),
    p95: getPercentile(95),
    p99: getPercentile(99),
  };
};

/**
 * Calculates throughput metrics
 */
export const calculateThroughput = (
  requests: Array<{ timestamp: string }>,
  timeWindow: 'second' | 'minute' | 'hour' = 'minute'
): number => {
  if (requests.length === 0) return 0;

  const now = new Date();
  const windowMs = timeWindow === 'second' ? 1000 : timeWindow === 'minute' ? 60000 : 3600000;
  const cutoff = new Date(now.getTime() - windowMs);

  const recentRequests = requests.filter(req => 
    parseISO(req.timestamp) >= cutoff
  );

  return recentRequests.length;
};

/**
 * Calculates error rate metrics
 */
export const calculateErrorRate = (
  responses: Array<{ success: boolean; errorType?: string }>
): { percentage: number; total: number; byType: Record<string, number> } => {
  if (responses.length === 0) {
    return { percentage: 0, total: 0, byType: {} };
  }

  const errors = responses.filter(r => !r.success);
  const errorsByType: Record<string, number> = {};

  errors.forEach(error => {
    const type = error.errorType || 'unknown';
    errorsByType[type] = (errorsByType[type] || 0) + 1;
  });

  return {
    percentage: (errors.length / responses.length) * 100,
    total: errors.length,
    byType: errorsByType,
  };
};

/**
 * Calculates uptime percentage
 */
export const calculateUptime = (
  healthChecks: Array<{ timestamp: string; status: 'up' | 'down' }>,
  timeWindow: number = 24 * 60 * 60 * 1000 // 24 hours in ms
): { percentage: number; totalTime: number; downtime: number } => {
  if (healthChecks.length === 0) {
    return { percentage: 100, totalTime: timeWindow, downtime: 0 };
  }

  const now = new Date();
  const cutoff = new Date(now.getTime() - timeWindow);
  
  const recentChecks = healthChecks
    .filter(check => parseISO(check.timestamp) >= cutoff)
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp));

  if (recentChecks.length === 0) {
    return { percentage: 100, totalTime: timeWindow, downtime: 0 };
  }

  let downtime = 0;
  let lastDownTime: Date | null = null;

  recentChecks.forEach((check, index) => {
    const checkTime = parseISO(check.timestamp);
    
    if (check.status === 'down' && !lastDownTime) {
      lastDownTime = checkTime;
    } else if (check.status === 'up' && lastDownTime) {
      downtime += checkTime.getTime() - lastDownTime.getTime();
      lastDownTime = null;
    }
  });

  // If still down at the end
  if (lastDownTime) {
    downtime += now.getTime() - lastDownTime.getTime();
  }

  const percentage = Math.max(0, ((timeWindow - downtime) / timeWindow) * 100);

  return {
    percentage,
    totalTime: timeWindow,
    downtime,
  };
};

/**
 * Performs trend analysis on time series data
 */
export const analyzeTrend = (
  data: PerformanceMetric[],
  windowSize: number = 10
): TrendAnalysis => {
  if (data.length < 2) {
    return {
      direction: 'stable',
      strength: 'weak',
      correlation: 0,
    };
  }

  // Sort by timestamp
  const sorted = [...data].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  
  // Use last windowSize points or all data if less
  const window = sorted.slice(-windowSize);
  const values = window.map(d => d.value);
  const indices = window.map((_, i) => i);

  // Calculate linear regression
  const n = values.length;
  const sumX = indices.reduce((sum, x) => sum + x, 0);
  const sumY = values.reduce((sum, y) => sum + y, 0);
  const sumXY = indices.reduce((sum, x, i) => sum + x * values[i], 0);
  const sumXX = indices.reduce((sum, x) => sum + x * x, 0);

  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // Calculate correlation coefficient
  const meanX = sumX / n;
  const meanY = sumY / n;
  
  let numerator = 0;
  let denomX = 0;
  let denomY = 0;
  
  for (let i = 0; i < n; i++) {
    const dx = indices[i] - meanX;
    const dy = values[i] - meanY;
    numerator += dx * dy;
    denomX += dx * dx;
    denomY += dy * dy;
  }
  
  const correlation = numerator / Math.sqrt(denomX * denomY);

  // Determine direction and strength
  const direction = Math.abs(slope) < 0.001 ? 'stable' : slope > 0 ? 'increasing' : 'decreasing';
  const absCorrelation = Math.abs(correlation);
  const strength = absCorrelation > 0.7 ? 'strong' : absCorrelation > 0.3 ? 'moderate' : 'weak';

  // Generate simple forecast (next 5 points)
  const forecast = [];
  for (let i = 1; i <= 5; i++) {
    forecast.push(slope * (n + i) + intercept);
  }

  return {
    direction,
    strength,
    correlation,
    forecast,
  };
};

/**
 * Calculates KPI with trend comparison
 */
export const calculateKPI = (
  current: number,
  previous: number,
  thresholds: { good: number; warning: number }
): KPIResult => {
  const change = current - previous;
  const changePercent = previous !== 0 ? (change / previous) * 100 : 0;
  
  let trend: 'up' | 'down' | 'stable' = 'stable';
  if (Math.abs(changePercent) > 1) { // 1% threshold
    trend = changePercent > 0 ? 'up' : 'down';
  }

  let status: 'good' | 'warning' | 'critical' = 'good';
  if (current < thresholds.warning) {
    status = 'critical';
  } else if (current < thresholds.good) {
    status = 'warning';
  }

  return {
    current,
    previous,
    change,
    changePercent,
    trend,
    status,
  };
};

/**
 * Calculates comprehensive performance statistics
 */
export const calculatePerformanceStats = (
  requests: Array<{
    timestamp: string;
    responseTime: number;
    success: boolean;
    errorType?: string;
  }>,
  healthChecks: Array<{ timestamp: string; status: 'up' | 'down' }>
): PerformanceStats => {
  const responseTimes = requests.map(r => r.responseTime);
  const percentiles = calculateResponseTimePercentiles(responseTimes);
  
  const stats: PerformanceStats = {
    responseTime: {
      mean: responseTimes.length > 0 ? responseTimes.reduce((sum, rt) => sum + rt, 0) / responseTimes.length : 0,
      median: percentiles.p50,
      p95: percentiles.p95,
      p99: percentiles.p99,
      min: responseTimes.length > 0 ? Math.min(...responseTimes) : 0,
      max: responseTimes.length > 0 ? Math.max(...responseTimes) : 0,
    },
    throughput: {
      requestsPerSecond: calculateThroughput(requests, 'second'),
      requestsPerMinute: calculateThroughput(requests, 'minute'),
      requestsPerHour: calculateThroughput(requests, 'hour'),
    },
    errorRate: calculateErrorRate(requests),
    uptime: calculateUptime(healthChecks),
  };

  return stats;
};

/**
 * Calculates model performance scores
 */
export const calculateModelPerformance = (
  predictions: number[],
  groundTruth: number[],
  responseTimes: number[]
): {
  accuracy: AccuracyMetrics;
  avgResponseTime: number;
  throughput: number;
  performanceScore: number;
} => {
  const accuracy = calculateAccuracyMetrics(predictions, groundTruth);
  const avgResponseTime = responseTimes.reduce((sum, rt) => sum + rt, 0) / responseTimes.length;
  const throughput = responseTimes.length; // Simple throughput measure
  
  // Composite performance score (0-100)
  const accuracyWeight = 0.5;
  const speedWeight = 0.3;
  const throughputWeight = 0.2;
  
  const accuracyScore = accuracy.overall * 100;
  const speedScore = Math.max(0, 100 - (avgResponseTime / 10)); // Penalty for slower responses
  const throughputScore = Math.min(100, throughput * 2); // Reward for higher throughput
  
  const performanceScore = 
    accuracyScore * accuracyWeight +
    speedScore * speedWeight +
    throughputScore * throughputWeight;

  return {
    accuracy,
    avgResponseTime,
    throughput,
    performanceScore: Math.round(performanceScore * 100) / 100,
  };
};

/**
 * Calculates performance degradation alerts
 */
export const calculatePerformanceDegradation = (
  metrics: PerformanceMetric[],
  baselineWindow: number = 7, // days
  alertThreshold: number = 0.2 // 20% degradation
): {
  isAlert: boolean;
  degradationPercent: number;
  baselineAverage: number;
  currentAverage: number;
} => {
  if (metrics.length === 0) {
    return {
      isAlert: false,
      degradationPercent: 0,
      baselineAverage: 0,
      currentAverage: 0,
    };
  }

  const now = new Date();
  const baselineCutoff = new Date(now.getTime() - baselineWindow * 24 * 60 * 60 * 1000);
  const recentCutoff = new Date(now.getTime() - 24 * 60 * 60 * 1000); // Last 24 hours

  const baselineMetrics = metrics.filter(m => {
    const date = parseISO(m.timestamp);
    return date >= baselineCutoff && date < recentCutoff;
  });

  const recentMetrics = metrics.filter(m => {
    const date = parseISO(m.timestamp);
    return date >= recentCutoff;
  });

  if (baselineMetrics.length === 0 || recentMetrics.length === 0) {
    return {
      isAlert: false,
      degradationPercent: 0,
      baselineAverage: 0,
      currentAverage: 0,
    };
  }

  const baselineAverage = baselineMetrics.reduce((sum, m) => sum + m.value, 0) / baselineMetrics.length;
  const currentAverage = recentMetrics.reduce((sum, m) => sum + m.value, 0) / recentMetrics.length;
  
  const degradationPercent = (baselineAverage - currentAverage) / baselineAverage;
  const isAlert = degradationPercent > alertThreshold;

  return {
    isAlert,
    degradationPercent,
    baselineAverage,
    currentAverage,
  };
};