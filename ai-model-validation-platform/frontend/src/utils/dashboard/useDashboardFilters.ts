/**
 * Custom hook for managing dashboard filters and date ranges
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import { parseISO, format, startOfDay, endOfDay, subDays, subMonths, subYears } from 'date-fns';

export interface DateRange {
  start: Date;
  end: Date;
}

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
  disabled?: boolean;
}

export interface DashboardFilters {
  dateRange: DateRange;
  dateRangePreset: string;
  metrics: string[];
  categories: string[];
  statuses: string[];
  searchQuery: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  pageSize: number;
  currentPage: number;
}

export interface FilterState extends DashboardFilters {
  totalItems: number;
  filteredItems: number;
  hasActiveFilters: boolean;
}

export interface FilterControls {
  setDateRange: (range: DateRange) => void;
  setDateRangePreset: (preset: string) => void;
  setMetrics: (metrics: string[]) => void;
  setCategories: (categories: string[]) => void;
  setStatuses: (statuses: string[]) => void;
  setSearchQuery: (query: string) => void;
  setSortBy: (sortBy: string) => void;
  setSortOrder: (order: 'asc' | 'desc') => void;
  setPageSize: (size: number) => void;
  setCurrentPage: (page: number) => void;
  addMetric: (metric: string) => void;
  removeMetric: (metric: string) => void;
  addCategory: (category: string) => void;
  removeCategory: (category: string) => void;
  addStatus: (status: string) => void;
  removeStatus: (status: string) => void;
  toggleSort: () => void;
  resetFilters: () => void;
  resetDateRange: () => void;
  resetPagination: () => void;
  applyPresetFilter: (preset: Partial<DashboardFilters>) => void;
}

export type DashboardFiltersHook = [FilterState, FilterControls];

const DEFAULT_FILTERS: DashboardFilters = {
  dateRange: {
    start: subDays(new Date(), 7),
    end: new Date(),
  },
  dateRangePreset: '7d',
  metrics: [],
  categories: [],
  statuses: [],
  searchQuery: '',
  sortBy: 'timestamp',
  sortOrder: 'desc',
  pageSize: 20,
  currentPage: 1,
};

/**
 * Predefined date range presets
 */
export const DATE_RANGE_PRESETS = {
  '1h': { label: 'Last Hour', days: 0, hours: 1 },
  '24h': { label: 'Last 24 Hours', days: 1 },
  '7d': { label: 'Last 7 Days', days: 7 },
  '30d': { label: 'Last 30 Days', days: 30 },
  '90d': { label: 'Last 90 Days', days: 90 },
  '1y': { label: 'Last Year', days: 365 },
  'mtd': { label: 'Month to Date', type: 'mtd' },
  'qtd': { label: 'Quarter to Date', type: 'qtd' },
  'ytd': { label: 'Year to Date', type: 'ytd' },
  'custom': { label: 'Custom Range', type: 'custom' },
};

/**
 * Calculates date range from preset
 */
export const getDateRangeFromPreset = (preset: string): DateRange => {
  const now = new Date();
  const config = DATE_RANGE_PRESETS[preset as keyof typeof DATE_RANGE_PRESETS];
  
  if (!config) {
    return DEFAULT_FILTERS.dateRange;
  }

  switch (config.type) {
    case 'mtd':
      return {
        start: startOfDay(new Date(now.getFullYear(), now.getMonth(), 1)),
        end: endOfDay(now),
      };
    case 'qtd':
      const quarter = Math.floor(now.getMonth() / 3);
      return {
        start: startOfDay(new Date(now.getFullYear(), quarter * 3, 1)),
        end: endOfDay(now),
      };
    case 'ytd':
      return {
        start: startOfDay(new Date(now.getFullYear(), 0, 1)),
        end: endOfDay(now),
      };
    case 'custom':
      return DEFAULT_FILTERS.dateRange;
    default:
      if (config.hours) {
        return {
          start: new Date(now.getTime() - config.hours * 60 * 60 * 1000),
          end: now,
        };
      } else if (config.days) {
        return {
          start: startOfDay(subDays(now, config.days)),
          end: endOfDay(now),
        };
      }
      return DEFAULT_FILTERS.dateRange;
  }
};

/**
 * Main dashboard filters hook
 */
export const useDashboardFilters = (
  initialFilters: Partial<DashboardFilters> = {},
  totalItems: number = 0
): DashboardFiltersHook => {
  const [filters, setFilters] = useState<DashboardFilters>({
    ...DEFAULT_FILTERS,
    ...initialFilters,
  });

  /**
   * Calculated state
   */
  const state = useMemo<FilterState>(() => {
    const hasActiveFilters = 
      filters.metrics.length > 0 ||
      filters.categories.length > 0 ||
      filters.statuses.length > 0 ||
      filters.searchQuery.trim() !== '' ||
      filters.dateRangePreset !== '7d';

    return {
      ...filters,
      totalItems,
      filteredItems: totalItems, // This would be calculated based on actual filtering
      hasActiveFilters,
    };
  }, [filters, totalItems]);

  /**
   * Date range controls
   */
  const setDateRange = useCallback((range: DateRange) => {
    setFilters(prev => ({
      ...prev,
      dateRange: range,
      dateRangePreset: 'custom',
      currentPage: 1,
    }));
  }, []);

  const setDateRangePreset = useCallback((preset: string) => {
    const dateRange = getDateRangeFromPreset(preset);
    setFilters(prev => ({
      ...prev,
      dateRange,
      dateRangePreset: preset,
      currentPage: 1,
    }));
  }, []);

  const resetDateRange = useCallback(() => {
    setDateRangePreset('7d');
  }, [setDateRangePreset]);

  /**
   * Filter array controls
   */
  const setMetrics = useCallback((metrics: string[]) => {
    setFilters(prev => ({
      ...prev,
      metrics,
      currentPage: 1,
    }));
  }, []);

  const setCategories = useCallback((categories: string[]) => {
    setFilters(prev => ({
      ...prev,
      categories,
      currentPage: 1,
    }));
  }, []);

  const setStatuses = useCallback((statuses: string[]) => {
    setFilters(prev => ({
      ...prev,
      statuses,
      currentPage: 1,
    }));
  }, []);

  /**
   * Individual filter controls
   */
  const addMetric = useCallback((metric: string) => {
    setFilters(prev => ({
      ...prev,
      metrics: prev.metrics.includes(metric) 
        ? prev.metrics 
        : [...prev.metrics, metric],
      currentPage: 1,
    }));
  }, []);

  const removeMetric = useCallback((metric: string) => {
    setFilters(prev => ({
      ...prev,
      metrics: prev.metrics.filter(m => m !== metric),
      currentPage: 1,
    }));
  }, []);

  const addCategory = useCallback((category: string) => {
    setFilters(prev => ({
      ...prev,
      categories: prev.categories.includes(category)
        ? prev.categories
        : [...prev.categories, category],
      currentPage: 1,
    }));
  }, []);

  const removeCategory = useCallback((category: string) => {
    setFilters(prev => ({
      ...prev,
      categories: prev.categories.filter(c => c !== category),
      currentPage: 1,
    }));
  }, []);

  const addStatus = useCallback((status: string) => {
    setFilters(prev => ({
      ...prev,
      statuses: prev.statuses.includes(status)
        ? prev.statuses
        : [...prev.statuses, status],
      currentPage: 1,
    }));
  }, []);

  const removeStatus = useCallback((status: string) => {
    setFilters(prev => ({
      ...prev,
      statuses: prev.statuses.filter(s => s !== status),
      currentPage: 1,
    }));
  }, []);

  /**
   * Search controls
   */
  const setSearchQuery = useCallback((query: string) => {
    setFilters(prev => ({
      ...prev,
      searchQuery: query,
      currentPage: 1,
    }));
  }, []);

  /**
   * Sort controls
   */
  const setSortBy = useCallback((sortBy: string) => {
    setFilters(prev => ({
      ...prev,
      sortBy,
      currentPage: 1,
    }));
  }, []);

  const setSortOrder = useCallback((order: 'asc' | 'desc') => {
    setFilters(prev => ({
      ...prev,
      sortOrder: order,
      currentPage: 1,
    }));
  }, []);

  const toggleSort = useCallback(() => {
    setFilters(prev => ({
      ...prev,
      sortOrder: prev.sortOrder === 'asc' ? 'desc' : 'asc',
      currentPage: 1,
    }));
  }, []);

  /**
   * Pagination controls
   */
  const setPageSize = useCallback((size: number) => {
    setFilters(prev => ({
      ...prev,
      pageSize: size,
      currentPage: 1,
    }));
  }, []);

  const setCurrentPage = useCallback((page: number) => {
    setFilters(prev => ({
      ...prev,
      currentPage: page,
    }));
  }, []);

  const resetPagination = useCallback(() => {
    setFilters(prev => ({
      ...prev,
      currentPage: 1,
    }));
  }, []);

  /**
   * Bulk controls
   */
  const resetFilters = useCallback(() => {
    setFilters({
      ...DEFAULT_FILTERS,
      ...initialFilters,
    });
  }, [initialFilters]);

  const applyPresetFilter = useCallback((preset: Partial<DashboardFilters>) => {
    setFilters(prev => ({
      ...prev,
      ...preset,
      currentPage: 1,
    }));
  }, []);

  const controls: FilterControls = {
    setDateRange,
    setDateRangePreset,
    setMetrics,
    setCategories,
    setStatuses,
    setSearchQuery,
    setSortBy,
    setSortOrder,
    setPageSize,
    setCurrentPage,
    addMetric,
    removeMetric,
    addCategory,
    removeCategory,
    addStatus,
    removeStatus,
    toggleSort,
    resetFilters,
    resetDateRange,
    resetPagination,
    applyPresetFilter,
  };

  return [state, controls];
};

/**
 * Hook for managing filter options with dynamic counts
 */
export const useFilterOptions = <T>(
  items: T[],
  getOptions: (items: T[]) => FilterOption[]
) => {
  const [options, setOptions] = useState<FilterOption[]>([]);

  useEffect(() => {
    const newOptions = getOptions(items);
    setOptions(newOptions);
  }, [items, getOptions]);

  const getOptionByValue = useCallback((value: string) => {
    return options.find(option => option.value === value);
  }, [options]);

  const getActiveOptions = useCallback(() => {
    return options.filter(option => !option.disabled);
  }, [options]);

  return {
    options,
    getOptionByValue,
    getActiveOptions,
  };
};

/**
 * Hook for persisting filters to localStorage
 */
export const usePersistentFilters = (
  key: string,
  initialFilters: Partial<DashboardFilters> = {}
) => {
  // Load filters from localStorage on mount
  const loadedFilters = useMemo(() => {
    try {
      const stored = localStorage.getItem(key);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert date strings back to Date objects
        if (parsed.dateRange) {
          parsed.dateRange.start = new Date(parsed.dateRange.start);
          parsed.dateRange.end = new Date(parsed.dateRange.end);
        }
        return { ...initialFilters, ...parsed };
      }
    } catch (error) {
      console.warn('Failed to load filters from localStorage:', error);
    }
    return initialFilters;
  }, [key, initialFilters]);

  const [state, controls] = useDashboardFilters(loadedFilters);

  // Save filters to localStorage when they change
  useEffect(() => {
    try {
      const filtersToSave = {
        dateRange: state.dateRange,
        dateRangePreset: state.dateRangePreset,
        metrics: state.metrics,
        categories: state.categories,
        statuses: state.statuses,
        searchQuery: state.searchQuery,
        sortBy: state.sortBy,
        sortOrder: state.sortOrder,
        pageSize: state.pageSize,
      };
      localStorage.setItem(key, JSON.stringify(filtersToSave));
    } catch (error) {
      console.warn('Failed to save filters to localStorage:', error);
    }
  }, [key, state]);

  return [state, controls];
};

/**
 * Hook for URL-synced filters
 */
export const useUrlSyncedFilters = (
  initialFilters: Partial<DashboardFilters> = {}
) => {
  const [state, controls] = useDashboardFilters(initialFilters);

  // Sync filters with URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const updates: Partial<DashboardFilters> = {};

    if (params.has('dateRange')) {
      updates.dateRangePreset = params.get('dateRange') || '7d';
    }
    if (params.has('search')) {
      updates.searchQuery = params.get('search') || '';
    }
    if (params.has('sort')) {
      updates.sortBy = params.get('sort') || 'timestamp';
    }
    if (params.has('order')) {
      updates.sortOrder = (params.get('order') as 'asc' | 'desc') || 'desc';
    }
    if (params.has('page')) {
      updates.currentPage = parseInt(params.get('page') || '1');
    }

    if (Object.keys(updates).length > 0) {
      controls.applyPresetFilter(updates);
    }
  }, [controls]);

  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    
    if (state.dateRangePreset !== '7d') {
      params.set('dateRange', state.dateRangePreset);
    }
    if (state.searchQuery) {
      params.set('search', state.searchQuery);
    }
    if (state.sortBy !== 'timestamp') {
      params.set('sort', state.sortBy);
    }
    if (state.sortOrder !== 'desc') {
      params.set('order', state.sortOrder);
    }
    if (state.currentPage > 1) {
      params.set('page', state.currentPage.toString());
    }

    const newUrl = params.toString() 
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;
    
    window.history.replaceState({}, '', newUrl);
  }, [state]);

  return [state, controls];
};