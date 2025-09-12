import React, { useState, Component, ReactNode } from 'react';
import { Box, Container, Typography, Alert, Button } from '@mui/material';
import ApiHealthIndicator from './ApiHealthIndicator';

// Custom Error Boundary Component
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, resetError: () => void) => ReactNode;
}

class ApiHealthErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ApiHealthIndicator Error:', error, errorInfo);
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.resetError);
      }
      
      return (
        <Alert severity="error" sx={{ mt: 2 }}>
          <Typography variant="h6">Something went wrong with the API Health Monitor:</Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            {this.state.error.message}
          </Typography>
          <Button onClick={this.resetError} variant="outlined" size="small" sx={{ mt: 2 }}>
            Try again
          </Button>
        </Alert>
      );
    }

    return this.props.children;
  }
}

const ApiHealthExample: React.FC = () => {
  const [overallStatus, setOverallStatus] = useState<'healthy' | 'unhealthy' | 'warning'>('unhealthy');

  const handleHealthChange = (status: 'healthy' | 'unhealthy' | 'warning') => {
    setOverallStatus(status);
  };

  const getStatusMessage = () => {
    switch (overallStatus) {
      case 'healthy':
        return 'All systems operational';
      case 'warning':
        return 'Some issues detected';
      case 'unhealthy':
        return 'System unavailable';
      default:
        return 'Status unknown';
    }
  };

  return (
    <Container maxWidth="lg">
      <Box py={3}>
        <Typography variant="h4" gutterBottom>
          AI Model Validation Platform - System Status
        </Typography>
        
        <Alert severity={overallStatus === 'healthy' ? 'success' : overallStatus === 'warning' ? 'warning' : 'error'} sx={{ mb: 3 }}>
          <Typography variant="h6">
            System Status: {getStatusMessage()}
          </Typography>
        </Alert>

        <ApiHealthErrorBoundary>
          <ApiHealthIndicator
            baseUrl="http://localhost:8000"
            refreshInterval={10000}
            onHealthChange={handleHealthChange}
          />
        </ApiHealthErrorBoundary>

        <Box mt={3}>
          <Alert severity="info">
            <Typography variant="body2">
              <strong>Note:</strong> This component monitors the backend API health at localhost:8000/health.
              It automatically refreshes every 10 seconds and provides detailed status information for:
            </Typography>
            <ul>
              <li>Backend API connectivity and performance</li>
              <li>LabJack hardware connection status</li>
              <li>Frame 80 detection model readiness</li>
              <li>Windows driver compatibility</li>
              <li>System resource usage</li>
            </ul>
          </Alert>
        </Box>
      </Box>
    </Container>
  );
};

export default ApiHealthExample;