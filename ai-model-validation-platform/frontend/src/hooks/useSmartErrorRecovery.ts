import { useCallback, useRef, useState, useEffect } from 'react';
import SmartErrorRecoveryEngine, { 
  SmartErrorType, 
  RecoveryPlan, 
  ErrorContext,
  RecoveryMetrics 
} from '../utils/smartErrorRecovery';

export interface SmartErrorRecoveryOptions {
  component: string;
  operation?: string;
  enableAutoRecovery?: boolean;
  maxRetries?: number;
  showNotifications?: boolean;
  trackMetrics?: boolean;
}

export interface SmartErrorRecoveryReturn {
  /**
   * Handle an error with smart recovery
   */
  handleError: (error: any, operation?: string) => Promise<boolean>;
  
  /**
   * Execute a function with smart error recovery
   */
  withRecovery: <T>(
    fn: () => Promise<T>,
    operation?: string
  ) => Promise<T | null>;
  
  /**
   * Get current recovery metrics
   */
  getRecoveryStats: () => {
    totalErrors: number;
    recoveryRate: number;
    avgRecoveryTime: number;
  };
  
  /**
   * Force retry of last failed operation
   */
  retryLastOperation: () => Promise<boolean>;
  
  /**
   * Check if recovery is currently in progress
   */
  isRecovering: boolean;
  
  /**
   * Get the current error context
   */
  currentError: Error | null;
  
  /**
   * Get the current recovery plan
   */
  currentPlan: RecoveryPlan | null;
}

export const useSmartErrorRecovery = (
  options: SmartErrorRecoveryOptions
): SmartErrorRecoveryReturn => {
  const recoveryEngine = useRef<SmartErrorRecoveryEngine>(new SmartErrorRecoveryEngine());
  const [isRecovering, setIsRecovering] = useState(false);
  const [currentError, setCurrentError] = useState<Error | null>(null);
  const [currentPlan, setCurrentPlan] = useState<RecoveryPlan | null>(null);
  const [metrics, setMetrics] = useState<RecoveryMetrics[]>([]);
  const lastOperationRef = useRef<(() => Promise<any>) | null>(null);

  const createErrorContext = useCallback((operation?: string): ErrorContext => {
    return {
      component: options.component,
      operation: operation || options.operation || 'unknown',
      timestamp: Date.now(),
      url: window.location.href,
      userAgent: navigator.userAgent,
      retryCount: 0,
      networkStatus: navigator.onLine ? 'online' : 'offline',
    };
  }, [options.component, options.operation]);

  const handleError = useCallback(async (error: any, operation?: string): Promise<boolean> => {
    const context = createErrorContext(operation);
    const plan = recoveryEngine.current.generateRecoveryPlan(error, context);
    
    setCurrentError(error);
    setCurrentPlan(plan);
    setIsRecovering(true);

    try {
      // Log error for metrics if enabled
      if (options.trackMetrics !== false) {
        const metric: RecoveryMetrics = {
          errorType: plan.errorType,
          context,
          recoveryAttempts: 0,
          successfulRecovery: false,
          recoveryTime: Date.now(),
          userInteractionRequired: !plan.actions.some(a => a.automatic),
          strategyUsed: plan.strategy,
          timestamp: Date.now()
        };
        setMetrics(prev => [...prev, metric]);
      }

      // Attempt automatic recovery if enabled
      if (options.enableAutoRecovery !== false) {
        const automaticActions = plan.actions.filter(action => action.automatic);
        
        for (const action of automaticActions) {
          try {
            const result = await action.action();
            if (result === true) {
              // Recovery successful
              setIsRecovering(false);
              setCurrentError(null);
              setCurrentPlan(null);
              
              // Update metrics
              if (options.trackMetrics !== false) {
                setMetrics(prev => prev.map(m => 
                  m === prev[prev.length - 1] 
                    ? { ...m, successfulRecovery: true, recoveryTime: Date.now() - m.recoveryTime }
                    : m
                ));
              }
              
              return true;
            }
          } catch (recoveryError) {
            console.warn('Automatic recovery action failed:', recoveryError);
            continue;
          }
        }
      }

      // Auto recovery failed or not enabled
      setIsRecovering(false);
      return false;

    } catch (recoveryError) {
      console.error('Error during recovery process:', recoveryError);
      setIsRecovering(false);
      return false;
    }
  }, [options.enableAutoRecovery, options.trackMetrics, createErrorContext]);

  const withRecovery = useCallback(async <T>(
    fn: () => Promise<T>,
    operation?: string
  ): Promise<T | null> => {
    // Store reference for potential retry
    lastOperationRef.current = fn;

    try {
      return await fn();
    } catch (error) {
      const recovered = await handleError(error, operation);
      
      if (recovered) {
        // If recovery was successful, try the operation again
        try {
          return await fn();
        } catch (retryError) {
          // If retry also fails, return null
          console.error('Operation failed even after recovery:', retryError);
          return null;
        }
      }
      
      return null;
    }
  }, [handleError]);

  const retryLastOperation = useCallback(async (): Promise<boolean> => {
    if (!lastOperationRef.current) {
      console.warn('No previous operation to retry');
      return false;
    }

    try {
      await lastOperationRef.current();
      setCurrentError(null);
      setCurrentPlan(null);
      return true;
    } catch (error) {
      return await handleError(error);
    }
  }, [handleError]);

  const getRecoveryStats = useCallback(() => {
    const totalErrors = metrics.length;
    const successfulRecoveries = metrics.filter(m => m.successfulRecovery).length;
    const recoveryRate = totalErrors > 0 ? (successfulRecoveries / totalErrors) * 100 : 0;
    
    const recoveryTimes = metrics
      .filter(m => m.successfulRecovery && m.recoveryTime > 0)
      .map(m => m.recoveryTime);
    
    const avgRecoveryTime = recoveryTimes.length > 0 
      ? recoveryTimes.reduce((sum, time) => sum + time, 0) / recoveryTimes.length
      : 0;

    return {
      totalErrors,
      recoveryRate,
      avgRecoveryTime
    };
  }, [metrics]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      setIsRecovering(false);
      setCurrentError(null);
      setCurrentPlan(null);
    };
  }, []);

  return {
    handleError,
    withRecovery,
    getRecoveryStats,
    retryLastOperation,
    isRecovering,
    currentError,
    currentPlan,
  };
};

/**
 * Hook for component-specific error recovery with enhanced features
 */
export const useComponentErrorRecovery = (componentName: string) => {
  return useSmartErrorRecovery({
    component: componentName,
    enableAutoRecovery: true,
    showNotifications: true,
    trackMetrics: true,
  });
};

/**
 * Hook for API operation error recovery
 */
export const useApiErrorRecovery = (apiEndpoint: string) => {
  return useSmartErrorRecovery({
    component: 'api-client',
    operation: apiEndpoint,
    enableAutoRecovery: true,
    maxRetries: 3,
    trackMetrics: true,
  });
};

/**
 * Hook for form submission error recovery
 */
export const useFormErrorRecovery = (formName: string) => {
  const recovery = useSmartErrorRecovery({
    component: 'form',
    operation: formName,
    enableAutoRecovery: false, // Forms usually need user interaction
    showNotifications: true,
    trackMetrics: true,
  });

  const handleSubmitError = useCallback(async (error: any, formData?: any) => {
    // Enhanced error handling for forms
    if (error?.response?.status === 422 && error?.response?.data?.errors) {
      // Validation errors - show field-specific errors
      const validationError = new Error('Validation failed');
      (validationError as any).type = 'validation';
      (validationError as any).fieldErrors = error.response.data.errors;
      return await recovery.handleError(validationError, 'form_submission');
    }

    return await recovery.handleError(error, 'form_submission');
  }, [recovery]);

  return {
    ...recovery,
    handleSubmitError,
  };
};

export default useSmartErrorRecovery;