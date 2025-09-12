import React, { useState, useEffect, ReactNode, DependencyList } from 'react';
import ErrorBoundary, { ErrorBoundaryProps } from './ErrorBoundary';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';

// Type for async operation result
type AsyncOperationResult = void | unknown;

// Type guard to check if error is an Error instance
const isError = (error: unknown): error is Error => {
  return error instanceof Error;
};

// Type guard to check if error has a message property
const hasMessage = (error: unknown): error is { message: string } => {
  return typeof error === 'object' && error !== null && 'message' in error && typeof (error as { message: unknown }).message === 'string';
};

interface AsyncErrorBoundaryProps extends Omit<ErrorBoundaryProps, 'children'> {
  children: ReactNode;
  asyncOperation?: () => Promise<AsyncOperationResult>;
  loadingComponent?: ReactNode;
  errorComponent?: (error: Error, retry: () => void) => ReactNode;
  dependencies?: DependencyList;
}

const AsyncErrorBoundary = ({
  children,
  asyncOperation,
  loadingComponent,
  errorComponent,
  dependencies = [],
  ...errorBoundaryProps
}: AsyncErrorBoundaryProps): React.ReactElement => {
  const [loading, setLoading] = useState(false);
  const [asyncError, setAsyncError] = useState<Error | null>(null);

  const executeAsyncOperation = async (): Promise<void> => {
    if (!asyncOperation) return;

    try {
      setLoading(true);
      setAsyncError(null);
      await asyncOperation();
    } catch (error: unknown) {
      let errorToSet: Error;
      
      if (isError(error)) {
        errorToSet = error;
      } else if (hasMessage(error)) {
        errorToSet = new Error(error.message);
      } else if (typeof error === 'string') {
        errorToSet = new Error(error);
      } else {
        errorToSet = new Error('Unknown async error occurred');
      }
      
      setAsyncError(errorToSet);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    executeAsyncOperation();
  }, dependencies);

  const retry = (): void => {
    executeAsyncOperation();
  };

  // Default loading component
  const defaultLoadingComponent = (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', p: 4 }}>
      <CircularProgress size={40} />
      <Typography variant="body2" sx={{ ml: 2 }}>
        Loading...
      </Typography>
    </Box>
  );

  // Default error component
  const defaultErrorComponent = (error: Error, retryFn: () => void): ReactNode => (
    <Alert 
      severity="error" 
      action={
        <button 
          type="button"
          onClick={retryFn} 
          style={{ marginLeft: '8px' }}
        >
          Retry
        </button>
      }
    >
      <Typography variant="body2">
        {error.message || 'An error occurred while loading data'}
      </Typography>
    </Alert>
  );

  if (loading) {
    return <>{loadingComponent || defaultLoadingComponent}</>;
  }

  if (asyncError) {
    return <>{errorComponent 
      ? errorComponent(asyncError, retry)
      : defaultErrorComponent(asyncError, retry)}</>;
  }

  return (
    <ErrorBoundary {...errorBoundaryProps}>
      {children}
    </ErrorBoundary>
  );
};

export default AsyncErrorBoundary;