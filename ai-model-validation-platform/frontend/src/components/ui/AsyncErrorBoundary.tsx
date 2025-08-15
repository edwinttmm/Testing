import React, { useState, useEffect, ReactNode } from 'react';
import ErrorBoundary, { ErrorBoundaryProps } from './ErrorBoundary';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';

interface AsyncErrorBoundaryProps extends Omit<ErrorBoundaryProps, 'children'> {
  children: ReactNode;
  asyncOperation?: () => Promise<any>;
  loadingComponent?: ReactNode;
  errorComponent?: (error: Error, retry: () => void) => ReactNode;
  dependencies?: any[];
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

  const executeAsyncOperation = async () => {
    if (!asyncOperation) return;

    try {
      setLoading(true);
      setAsyncError(null);
      await asyncOperation();
    } catch (error) {
      setAsyncError(error instanceof Error ? error : new Error(
        (error as any)?.message || (typeof error === 'string' ? error : 'Unknown async error')
      ));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    executeAsyncOperation();
  }, dependencies);

  const retry = () => {
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
  const defaultErrorComponent = (error: Error, retryFn: () => void) => (
    <Alert 
      severity="error" 
      action={
        <button onClick={retryFn} style={{ marginLeft: '8px' }}>
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