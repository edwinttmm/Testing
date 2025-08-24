/**
 * Example implementations of Error Boundaries in the AI Model Validation Platform
 * This file demonstrates various error boundary patterns and best practices
 */

import React, { useState, useEffect } from 'react';
import { Box, Button, Typography, Card, CardContent, Alert } from '@mui/material';
import {
  ErrorBoundary,
  WebSocketErrorBoundary,
  AsyncErrorBoundary,
  withErrorBoundary
} from '../components/ui';
import { useErrorBoundary, useApiError, useWebSocketError } from '../hooks/useErrorBoundary';
import { NetworkError, AppError as ApiError, ErrorFactory } from '../utils/errorTypes';

// Example 1: Basic Error Boundary Usage
export const BasicErrorBoundaryExample: React.FC = () => {
  const [shouldError, setShouldError] = useState(false);

  const ProblematicComponent = () => {
    if (shouldError) {
      throw new Error('This is a demonstration error');
    }
    return <Typography>Component working normally</Typography>;
  };

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Basic Error Boundary Example
        </Typography>
        
        <Button 
          onClick={() => setShouldError(!shouldError)}
          variant="outlined"
          sx={{ mb: 2 }}
        >
          {shouldError ? 'Fix Component' : 'Break Component'}
        </Button>

        <ErrorBoundary
          level="component"
          context="basic-example"
          enableRetry={true}
          onError={(error, errorInfo, errorType) => {
            console.log('Example error caught:', { error, errorInfo, errorType });
          }}
        >
          <ProblematicComponent />
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
};

// Example 2: API Call with Error Boundary
export const ApiErrorBoundaryExample: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const { handleApiError } = useApiError();

  const fetchData = async () => {
    try {
      setLoading(true);
      // Simulate API call that might fail
      const response = await fetch('/api/nonexistent-endpoint');
      if (!response.ok) {
        throw ErrorFactory.createApiError(response as any, {} as Record<string, unknown>, { context: 'example-api-call' });
      }
      const result: Record<string, any> = await response.json();
      setData(result);
    } catch (error) {
      handleApiError(error, 'api-example');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          API Error Boundary Example
        </Typography>
        
        <Button 
          onClick={fetchData}
          variant="outlined"
          disabled={loading}
          sx={{ mb: 2 }}
        >
          {loading ? 'Loading...' : 'Fetch Data (Will Fail)'}
        </Button>

        <ErrorBoundary
          level="component"
          context="api-example"
          enableRetry={true}
          maxRetries={3}
        >
          {data ? (
            <Typography>Data loaded successfully</Typography>
          ) : (
            <Typography color="text.secondary">No data loaded yet</Typography>
          )}
        </ErrorBoundary>
      </CardContent>
    </Card>
  );
};

// Example 3: WebSocket Error Boundary
export const WebSocketErrorBoundaryExample: React.FC = () => {
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');
  const { handleWebSocketError } = useWebSocketError();

  const simulateWebSocketError = () => {
    const fakeEvent = new Event('error');
    handleWebSocketError(fakeEvent, 'websocket-example');
    setConnectionStatus('disconnected');
  };

  const reconnect = () => {
    setConnectionStatus('connecting');
    setTimeout(() => {
      setConnectionStatus('connected');
    }, 2000);
  };

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          WebSocket Error Boundary Example
        </Typography>
        
        <Alert severity="info" sx={{ mb: 2 }}>
          Connection Status: {connectionStatus}
        </Alert>

        <Button 
          onClick={simulateWebSocketError}
          variant="outlined"
          sx={{ mr: 1, mb: 2 }}
        >
          Simulate Connection Error
        </Button>

        <WebSocketErrorBoundary
          connectionStatus={connectionStatus}
          reconnectAction={reconnect}
        >
          <Box sx={{ p: 2, backgroundColor: 'success.light', color: 'success.contrastText' }}>
            <Typography>
              Real-time data would be displayed here
            </Typography>
          </Box>
        </WebSocketErrorBoundary>
      </CardContent>
    </Card>
  );
};

// Example 4: Async Error Boundary
export const AsyncErrorBoundaryExample: React.FC = () => {
  const [shouldFail, setShouldFail] = useState(false);

  const asyncOperation = async () => {
    await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate delay
    
    if (shouldFail) {
      throw new Error('Async operation failed');
    }
    
    return 'Success!';
  };

  const CustomLoader = (
    <Box sx={{ textAlign: 'center', p: 2 }}>
      <Typography>Custom loading component...</Typography>
    </Box>
  );

  const CustomError = (error: Error, retry: () => void) => (
    <Alert 
      severity="error"
      action={
        <Button color="inherit" size="small" onClick={retry}>
          Retry
        </Button>
      }
    >
      Custom error handling: {error.message}
    </Alert>
  );

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Async Error Boundary Example
        </Typography>
        
        <Button 
          onClick={() => setShouldFail(!shouldFail)}
          variant="outlined"
          sx={{ mb: 2 }}
        >
          {shouldFail ? 'Make Operation Succeed' : 'Make Operation Fail'}
        </Button>

        <AsyncErrorBoundary
          asyncOperation={asyncOperation}
          dependencies={[shouldFail]}
          loadingComponent={CustomLoader}
          errorComponent={CustomError}
          level="component"
          context="async-example"
        >
          <Box sx={{ p: 2, backgroundColor: 'success.light' }}>
            <Typography>Async operation completed successfully!</Typography>
          </Box>
        </AsyncErrorBoundary>
      </CardContent>
    </Card>
  );
};

// Example 5: Higher-Order Component with Error Boundary
const ProblematicHOCComponent: React.FC<{ shouldError: boolean }> = ({ shouldError }) => {
  if (shouldError) {
    throw new Error('HOC component error');
  }
  return <Typography>HOC component working fine</Typography>;
};

const SafeHOCComponent = withErrorBoundary(ProblematicHOCComponent, {
  level: 'component',
  context: 'hoc-example',
  enableRetry: true,
});

export const HOCErrorBoundaryExample: React.FC = () => {
  const [shouldError, setShouldError] = useState(false);

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Higher-Order Component Error Boundary Example
        </Typography>
        
        <Button 
          onClick={() => setShouldError(!shouldError)}
          variant="outlined"
          sx={{ mb: 2 }}
        >
          {shouldError ? 'Fix HOC Component' : 'Break HOC Component'}
        </Button>

        <SafeHOCComponent shouldError={shouldError} />
      </CardContent>
    </Card>
  );
};

// Example 6: Manual Error Reporting
export const ManualErrorReportingExample: React.FC = () => {
  const { captureError, clearError, error, hasError } = useErrorBoundary();

  const reportError = () => {
    const customError = new NetworkError(
      'Manually reported network error',
      0,
      { context: 'manual-reporting-example', userAction: 'button-click' }
    );
    captureError(customError, 'manual-error-example');
  };

  return (
    <Card sx={{ m: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Manual Error Reporting Example
        </Typography>
        
        <Box sx={{ mb: 2 }}>
          <Button onClick={reportError} variant="outlined" sx={{ mr: 1 }}>
            Report Error Manually
          </Button>
          
          <Button onClick={clearError} variant="outlined" disabled={!hasError}>
            Clear Error
          </Button>
        </Box>

        {hasError && (
          <Alert severity="error">
            <Typography variant="subtitle2">Captured Error:</Typography>
            <Typography variant="body2">{error?.message}</Typography>
          </Alert>
        )}

        {!hasError && (
          <Alert severity="success">
            No errors reported
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

// Main examples component that combines all examples
export const ErrorBoundaryExamples: React.FC = () => {
  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Error Boundary Examples
      </Typography>
      
      <Typography variant="body1" sx={{ mb: 3 }}>
        This page demonstrates various error boundary patterns and implementations
        used throughout the AI Model Validation Platform.
      </Typography>

      <BasicErrorBoundaryExample />
      <ApiErrorBoundaryExample />
      <WebSocketErrorBoundaryExample />
      <AsyncErrorBoundaryExample />
      <HOCErrorBoundaryExample />
      <ManualErrorReportingExample />
    </Box>
  );
};

export default ErrorBoundaryExamples;