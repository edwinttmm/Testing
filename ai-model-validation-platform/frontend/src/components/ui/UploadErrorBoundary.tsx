import React, { Component, ReactNode } from 'react';
import { Box, Alert, Button, Typography, Collapse } from '@mui/material';
import { ErrorOutline, Refresh } from '@mui/icons-material';

interface Props {
  children: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  showDetails: boolean;
}

class UploadErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Upload component error:', error, errorInfo);
    
    this.setState({
      error,
      errorInfo,
    });

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
  };

  toggleDetails = () => {
    this.setState(prev => ({
      showDetails: !prev.showDetails,
    }));
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Box sx={{ p: 3 }}>
          <Alert 
            severity="error" 
            icon={<ErrorOutline />}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={this.handleRetry}
                startIcon={<Refresh />}
              >
                Retry
              </Button>
            }
          >
            <Typography variant="h6" gutterBottom>
              Upload Component Error
            </Typography>
            <Typography variant="body2" gutterBottom>
              Something went wrong with the file upload component. Please try again.
            </Typography>
            
            {this.state.error && (
              <>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Error: {this.state.error.message}
                </Typography>
                
                <Button 
                  size="small" 
                  onClick={this.toggleDetails}
                  sx={{ mt: 1 }}
                >
                  {this.state.showDetails ? 'Hide Details' : 'Show Details'}
                </Button>
                
                <Collapse in={this.state.showDetails}>
                  <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                    <Typography variant="caption" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
                      {this.state.error.stack}
                    </Typography>
                    {this.state.errorInfo && (
                      <Typography variant="caption" component="pre" sx={{ whiteSpace: 'pre-wrap', mt: 1 }}>
                        Component Stack: {this.state.errorInfo.componentStack}
                      </Typography>
                    )}
                  </Box>
                </Collapse>
              </>
            )}
          </Alert>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default UploadErrorBoundary;