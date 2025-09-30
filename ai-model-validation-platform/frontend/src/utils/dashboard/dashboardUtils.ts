/**
 * Dashboard utility functions for data formatting, calculations, and transformations
 */

import { format, parseISO, differenceInDays, startOfDay, endOfDay } from 'date-fns';

export interface TimeSeriesData {
  timestamp: string;
  value: number;
  label?: string;
}

export interface DataPoint {
  x: string | number;
  y: number;
  category?: string;
}

export interface MetricSummary {
  current: number;
  previous: number;
  change: number;
  changePercent: number;
  trend: 'up' | 'down' | 'stable';
}

/**
 * Formats a number as a percentage with specified decimal places
 */
export const formatPercentage = (value: number, decimals: number = 1): string => {
  return `${(value * 100).toFixed(decimals)}%`;
};

/**
 * Formats a number with appropriate unit suffixes (K, M, B)
 */
export const formatNumber = (value: number, decimals: number = 1): string => {
  if (value === 0) return '0';
  
  const absValue = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  
  if (absValue >= 1e9) {
    return `${sign}${(absValue / 1e9).toFixed(decimals)}B`;
  } else if (absValue >= 1e6) {
    return `${sign}${(absValue / 1e6).toFixed(decimals)}M`;
  } else if (absValue >= 1e3) {
    return `${sign}${(absValue / 1e3).toFixed(decimals)}K`;
  }
  
  return `${sign}${absValue.toFixed(decimals)}`;
};

/**
 * Formats duration in milliseconds to human-readable format
 */
export const formatDuration = (milliseconds: number): string => {
  if (milliseconds < 1000) {
    return `${milliseconds}ms`;
  } else if (milliseconds < 60000) {
    return `${(milliseconds / 1000).toFixed(1)}s`;
  } else if (milliseconds < 3600000) {
    return `${Math.floor(milliseconds / 60000)}m ${Math.floor((milliseconds % 60000) / 1000)}s`;
  } else {
    const hours = Math.floor(milliseconds / 3600000);
    const minutes = Math.floor((milliseconds % 3600000) / 60000);
    return `${hours}h ${minutes}m`;
  }
};

/**
 * Formats date for display based on the time range
 */
export const formatDateForRange = (date: string | Date, range: string): string => {
  const parsedDate = typeof date === 'string' ? parseISO(date) : date;
  
  switch (range) {
    case '24h':
      return format(parsedDate, 'HH:mm');
    case '7d':
      return format(parsedDate, 'MMM dd');
    case '30d':
      return format(parsedDate, 'MMM dd');
    case '90d':
      return format(parsedDate, 'MMM yyyy');
    default:
      return format(parsedDate, 'MMM dd, yyyy');
  }
};

/**
 * Aggregates time series data by specified interval
 */
export const aggregateTimeSeriesData = (
  data: TimeSeriesData[],
  interval: 'hour' | 'day' | 'week' | 'month'
): TimeSeriesData[] => {
  if (!data.length) return [];

  const groupedData = new Map<string, number[]>();
  
  data.forEach(point => {
    const date = parseISO(point.timestamp);
    let key: string;
    
    switch (interval) {
      case 'hour':
        key = format(date, 'yyyy-MM-dd HH:00:00');
        break;
      case 'day':
        key = format(date, 'yyyy-MM-dd');
        break;
      case 'week':
        key = format(startOfDay(date), 'yyyy-MM-dd');
        break;
      case 'month':
        key = format(date, 'yyyy-MM');
        break;
    }
    
    if (!groupedData.has(key)) {
      groupedData.set(key, []);
    }
    groupedData.get(key)!.push(point.value);
  });

  return Array.from(groupedData.entries()).map(([timestamp, values]) => ({
    timestamp,
    value: values.reduce((sum, val) => sum + val, 0) / values.length,
  })).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
};

/**
 * Calculates moving average for time series data
 */
export const calculateMovingAverage = (
  data: TimeSeriesData[],
  windowSize: number
): TimeSeriesData[] => {
  if (data.length < windowSize) return data;

  return data.map((_, index) => {
    const start = Math.max(0, index - windowSize + 1);
    const end = index + 1;
    const window = data.slice(start, end);
    const average = window.reduce((sum, point) => sum + point.value, 0) / window.length;
    
    return {
      timestamp: data[index].timestamp,
      value: average,
      label: `${windowSize}-period MA`,
    };
  });
};

/**
 * Calculates metric summary with trend analysis
 */
export const calculateMetricSummary = (
  current: number,
  previous: number
): MetricSummary => {
  const change = current - previous;
  const changePercent = previous !== 0 ? (change / previous) : 0;
  
  let trend: 'up' | 'down' | 'stable' = 'stable';
  if (Math.abs(changePercent) > 0.01) { // 1% threshold
    trend = changePercent > 0 ? 'up' : 'down';
  }
  
  return {
    current,
    previous,
    change,
    changePercent,
    trend,
  };
};

/**
 * Filters data by date range
 */
export const filterDataByDateRange = <T extends { timestamp: string }>(
  data: T[],
  startDate: string,
  endDate: string
): T[] => {
  const start = startOfDay(parseISO(startDate));
  const end = endOfDay(parseISO(endDate));
  
  return data.filter(item => {
    const itemDate = parseISO(item.timestamp);
    return itemDate >= start && itemDate <= end;
  });
};

/**
 * Sorts data by timestamp
 */
export const sortByTimestamp = <T extends { timestamp: string }>(
  data: T[],
  ascending: boolean = true
): T[] => {
  return [...data].sort((a, b) => {
    const comparison = a.timestamp.localeCompare(b.timestamp);
    return ascending ? comparison : -comparison;
  });
};

/**
 * Groups data by a specified key
 */
export const groupDataBy = <T, K extends keyof T>(
  data: T[],
  key: K
): Map<T[K], T[]> => {
  const grouped = new Map<T[K], T[]>();
  
  data.forEach(item => {
    const groupKey = item[key];
    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, []);
    }
    grouped.get(groupKey)!.push(item);
  });
  
  return grouped;
};

/**
 * Calculates percentile for an array of numbers
 */
export const calculatePercentile = (values: number[], percentile: number): number => {
  if (values.length === 0) return 0;
  
  const sorted = [...values].sort((a, b) => a - b);
  const index = (percentile / 100) * (sorted.length - 1);
  
  if (Number.isInteger(index)) {
    return sorted[index];
  } else {
    const lower = Math.floor(index);
    const upper = Math.ceil(index);
    const weight = index - lower;
    return sorted[lower] * (1 - weight) + sorted[upper] * weight;
  }
};

/**
 * Calculates statistics for an array of numbers
 */
export const calculateStatistics = (values: number[]) => {
  if (values.length === 0) {
    return { min: 0, max: 0, mean: 0, median: 0, std: 0 };
  }
  
  const sorted = [...values].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
  
  const median = sorted.length % 2 === 0
    ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
    : sorted[Math.floor(sorted.length / 2)];
  
  const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
  const std = Math.sqrt(variance);
  
  return { min, max, mean, median, std };
};

/**
 * Debounces a function call
 */
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: NodeJS.Timeout;
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
};

/**
 * Throttles a function call
 */
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let lastCall = 0;
  
  return (...args: Parameters<T>) => {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      func(...args);
    }
  };
};

/**
 * Exports data to CSV format
 */
export const exportToCSV = (data: any[], filename: string): void => {
  if (!data.length) return;
  
  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(','),
    ...data.map(row => 
      headers.map(header => {
        const value = row[header];
        // Escape quotes and wrap in quotes if necessary
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(',')
    ),
  ].join('\n');
  
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  
  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${filename}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
};

/**
 * Validates if a date string is valid
 */
export const isValidDate = (dateString: string): boolean => {
  try {
    const date = parseISO(dateString);
    return !isNaN(date.getTime());
  } catch {
    return false;
  }
};

/**
 * Generates date range options for filters
 */
export const getDateRangeOptions = () => [
  { value: '24h', label: 'Last 24 hours', days: 1 },
  { value: '7d', label: 'Last 7 days', days: 7 },
  { value: '30d', label: 'Last 30 days', days: 30 },
  { value: '90d', label: 'Last 90 days', days: 90 },
  { value: '1y', label: 'Last year', days: 365 },
  { value: 'custom', label: 'Custom range', days: 0 },
];