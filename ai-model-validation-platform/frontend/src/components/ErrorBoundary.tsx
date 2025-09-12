import React, { Component, ReactNode } from 'react';
import { Alert, AlertTitle, Box, Button, Typography } from '@mui/material';
import { Refresh, BugReport } from '@mui/icons-material';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo | null) => void;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo | null) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error,
      errorInfo
    });

    // Call optional error handler
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleRefresh = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Box sx={{ p: 3, maxWidth: 600, mx: 'auto', my: 4 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <AlertTitle>Something went wrong</AlertTitle>
            <Typography variant="body2" sx={{ mb: 2 }}>
              An error occurred while rendering this component. Please try refreshing or report this issue if it persists.
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                size="small"
                startIcon={<Refresh />}
                onClick={this.handleRefresh}
              >
                Try Again
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<BugReport />}
                onClick={() => {
                  // Copy error details to clipboard
                  const errorDetails = `
Error: ${this.state.error?.message || 'Unknown error'}
Stack: ${this.state.error?.stack || 'No stack trace'}
Component Stack: ${this.state.errorInfo?.componentStack || 'No component stack'}
                  `.trim();
                  
                  if (navigator.clipboard) {
                    navigator.clipboard.writeText(errorDetails);
                  }
                }}
              >
                Copy Error Details
              </Button>
            </Box>
          </Alert>

          {process.env.NODE_ENV === 'development' && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              <AlertTitle>Development Error Details</AlertTitle>
              <Typography variant="body2" component="pre" sx={{ 
                fontSize: '0.75rem',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: 300,
                overflow: 'auto',
                bgcolor: 'rgba(0, 0, 0, 0.05)',
                p: 1,
                borderRadius: 1,
                mt: 1
              }}>
                <strong>Error:</strong> {this.state.error?.message || 'Unknown error'}
                {'\n\n'}
                <strong>Stack:</strong> {this.state.error?.stack || 'No stack trace'}
                {'\n\n'}
                <strong>Component Stack:</strong> {this.state.errorInfo?.componentStack || 'No component stack'}
              </Typography>
            </Alert>
          )}
        </Box>
      );
    }

    return this.props.children;
  }
}

// HOC wrapper for functional components
export const withErrorBoundary = <P extends object>(
  WrappedComponent: React.ComponentType<P>,
  fallback?: ReactNode,
  onError?: (error: Error, errorInfo: React.ErrorInfo | null) => void
) => {
  return (props: P) => (
    <ErrorBoundary fallback={fallback} onError={onError}>
      <WrappedComponent {...props} />
    </ErrorBoundary>
  );
};

export default ErrorBoundary;