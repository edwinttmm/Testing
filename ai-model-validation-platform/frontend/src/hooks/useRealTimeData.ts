import { useState, useEffect, useCallback, useRef } from 'react';
import { apiCache } from '../utils/apiCache';

interface UseRealTimeDataOptions {
  pollingInterval?: number;
  enabled?: boolean;
  onDataUpdate?: (data: any) => void;
  onError?: (error: Error) => void;
}

/**
 * Hook for managing real-time data updates with automatic cache invalidation
 * Useful for components that need fresh data when backend processing completes
 */
export const useRealTimeData = <T>(
  fetchFn: () => Promise<T>,
  options: UseRealTimeDataOptions = {}
) => {
  const {
    pollingInterval = 10000, // 10 seconds default
    enabled = true,
    onDataUpdate,
    onError,
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number>(Date.now());

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef<boolean>(true);

  // Manual refresh function that clears cache
  const refresh = useCallback(async (clearCache = true) => {
    if (!isMountedRef.current) return;

    try {
      setLoading(true);
      setError(null);

      if (clearCache) {
        // Clear relevant caches to force fresh data
        apiCache.invalidateResults();
        console.log('🔄 Cache cleared for fresh data fetch');
      }

      const result = await fetchFn();
      
      if (isMountedRef.current) {
        setData(result);
        setLastUpdated(Date.now());
        onDataUpdate?.(result);
        console.log('📈 Real-time data updated');
      }
    } catch (err) {
      if (isMountedRef.current) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);
        onError?.(err instanceof Error ? err : new Error(errorMessage));
        console.error('❌ Real-time data update failed:', err);
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [fetchFn, onDataUpdate, onError]);

  // Start polling
  const startPolling = useCallback(() => {
    if (pollingRef.current) return;
    
    pollingRef.current = setInterval(() => {
      refresh(false); // Don't clear cache on polling updates
    }, pollingInterval);
    
    console.log(`🔄 Started polling every ${pollingInterval}ms`);
  }, [refresh, pollingInterval]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
      console.log('⏹️ Stopped polling');
    }
  }, []);

  // Initial data fetch and polling setup
  useEffect(() => {
    if (!enabled) return;

    // Initial fetch
    refresh(false);

    // Start polling if enabled
    if (pollingInterval > 0) {
      startPolling();
    }

    return () => {
      stopPolling();
    };
  }, [enabled, refresh, startPolling, stopPolling, pollingInterval]);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    
    return () => {
      isMountedRef.current = false;
      stopPolling();
    };
  }, [stopPolling]);

  // Handle page visibility changes (pause polling when hidden)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
        console.log('📴 Page hidden, stopped polling');
      } else if (enabled && pollingInterval > 0) {
        refresh(true); // Refresh with cache clear when page becomes visible
        startPolling();
        console.log('📱 Page visible, resumed polling');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, pollingInterval, refresh, startPolling, stopPolling]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    refresh: () => refresh(true), // Always clear cache on manual refresh
    startPolling,
    stopPolling,
    isPolling: pollingRef.current !== null,
  };
};

export default useRealTimeData;