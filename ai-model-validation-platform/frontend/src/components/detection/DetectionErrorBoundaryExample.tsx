import React, { useState, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Stack,
  Alert,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material';
import {
  BugReport,
  NetworkCheck,
  VideoCameraBack,
  Computer,
  Settings,
  Warning
} from '@mui/icons-material';
import {
  DetectionErrorBoundary,
  withDetectionErrorBoundary,
  createErrorReportingService,
  ErrorCategory,
  ErrorSeverity,
  type DetectionError
} from './DetectionErrorBoundary';

// Mock error reporting service for demonstration
const errorReportingService = createErrorReportingService(
  '/api/error-reports',
  'demo-api-key'
);

// Example components that might throw different types of errors
const NetworkComponent: React.FC<{ shouldFail: boolean }> = ({ shouldFail }) => {
  if (shouldFail) {
    throw new Error('Network request failed: API endpoint unreachable');
  }
  return <Typography color="success.main">Network connection successful</Typography>;
};

const CanvasComponent: React.FC<{ shouldFail: boolean }> = ({ shouldFail }) => {
  if (shouldFail) {
    const error = new Error('Canvas rendering context failed: WebGL not supported');
    error.stack = 'at CanvasRenderingContext2D.getContext() at drawFrame()';
    throw error;
  }
  return <Typography color="success.main">Canvas rendering active</Typography>;
};

const VideoProcessingComponent: React.FC<{ shouldFail: boolean }> = ({ shouldFail }) => {
  if (shouldFail) {
    const error = new Error('Detection failure at frame 80: Processing timeout exceeded');
    error.stack = 'at processFrame() at VideoProcessor.analyzeFrame()';
    throw error;
  }
  return <Typography color="success.main">Video processing complete</Typography>;
};

const HardwareComponent: React.FC<{ shouldFail: boolean }> = ({ shouldFail }) => {
  if (shouldFail) {
    const error = new Error('Hardware device not found: LabJack USB connection failed');
    error.stack = 'at USBDevice.connect() at LabJackInterface.initialize()';
    throw error;
  }
  return <Typography color="success.main">Hardware connection established</Typography>;
};

// Higher-order component wrapped version
const WrappedVideoComponent = withDetectionErrorBoundary(
  VideoProcessingComponent,
  {
    maxRetries: 2,
    enableAutoRecovery: true,
    autoRetryDelay: 3000,
    errorReportingService
  }
);

interface ErrorDemoProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  component: React.ComponentType<{ shouldFail: boolean }>;
  errorType: string;
}

const ErrorDemo: React.FC<ErrorDemoProps> = ({ 
  title, 
  description, 
  icon, 
  component: Component, 
  errorType 
}) => {
  const [shouldFail, setShouldFail] = useState(false);
  const [key, setKey] = useState(0);

  const handleToggle = useCallback(() => {
    setShouldFail(!shouldFail);
    // Force re-render to reset error boundary
    setKey(prev => prev + 1);
  }, [shouldFail]);

  const handleErrorCallback = useCallback((error: DetectionError) => {
    console.log(`Error reported for ${errorType}:`, error);
  }, [errorType]);

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} alignItems="center">
            {icon}
            <Typography variant="h6">{title}</Typography>
          </Stack>
          
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
          
          <FormControlLabel
            control={
              <Switch
                checked={shouldFail}
                onChange={handleToggle}
                color="error"
              />
            }
            label={shouldFail ? 'Trigger Error' : 'Normal Operation'}
          />
          
          <Box sx={{ 
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            p: 2,
            minHeight: 80,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <DetectionErrorBoundary
              key={key}
              onError={handleErrorCallback}
              errorReportingService={errorReportingService}
              maxRetries={3}
              enableAutoRecovery={errorType === 'network' || errorType === 'processing'}
              userId="demo-user"
              sessionId="demo-session"
              environment="development"
            >
              <Component shouldFail={shouldFail} />
            </DetectionErrorBoundary>
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
};

export const DetectionErrorBoundaryExample: React.FC = () => {
  const [globalRetryCount, setGlobalRetryCount] = useState(0);

  const demos: ErrorDemoProps[] = [
    {
      title: 'Network Errors',
      description: 'Simulates API failures, connection timeouts, and network issues',
      icon: <NetworkCheck color="primary" />,
      component: NetworkComponent,
      errorType: 'network'
    },
    {
      title: 'Canvas Rendering',
      description: 'Tests WebGL context failures and rendering errors',
      icon: <Computer color="primary" />,
      component: CanvasComponent,
      errorType: 'canvas'
    },
    {
      title: 'Video Processing',
      description: 'Frame 80 detection failures and video processing errors',
      icon: <VideoCameraBack color="primary" />,
      component: VideoProcessingComponent,
      errorType: 'processing'
    },
    {
      title: 'Hardware Devices',
      description: 'LabJack and USB device connection failures',
      icon: <Settings color="primary" />,
      component: HardwareComponent,
      errorType: 'hardware'
    }
  ];

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <BugReport color="primary" />
        Detection Error Boundary Demo
      </Typography>
      
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        This demo showcases the comprehensive error handling capabilities of the DetectionErrorBoundary 
        component. Toggle the switches to simulate different types of errors and observe the recovery mechanisms.
      </Typography>

      <Alert severity="info" sx={{ mb: 4 }}>
        <Typography variant="body2">
          <strong>Features demonstrated:</strong>
        </Typography>
        <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
          <li>Automatic error categorization (Network, Rendering, Processing, Hardware)</li>
          <li>Severity-based error handling with appropriate UI responses</li>
          <li>Specific Frame 80 detection failure handling</li>
          <li>Automatic retry mechanisms with configurable delays</li>
          <li>User-friendly recovery instructions</li>
          <li>Error reporting to external services</li>
          <li>Development mode debugging information</li>
          <li>Error throttling to prevent spam</li>
        </ul>
      </Alert>

      <Box sx={{ 
        display: 'grid', 
        gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
        gap: 3,
        mb: 4
      }}>
        {demos.map((demo, index) => (
          <ErrorDemo key={index} {...demo} />
        ))}
      </Box>

      <Divider sx={{ my: 4 }} />

      <Typography variant="h5" gutterBottom>
        Higher-Order Component Example
      </Typography>
      
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        This video component is wrapped with the DetectionErrorBoundary HOC for automatic error handling:
      </Typography>

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h6">Auto-Recovery Video Processor</Typography>
            
            <Alert severity="info">
              This component has auto-recovery enabled with 2 max retries and 3-second delays.
              It will automatically attempt to recover from processing errors.
            </Alert>
            
            <Box sx={{ 
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1,
              p: 2,
              minHeight: 80,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <WrappedVideoComponent shouldFail={false} />
            </Box>
            
            <Button
              variant="outlined"
              color="error"
              onClick={() => setGlobalRetryCount(prev => prev + 1)}
              startIcon={<Warning />}
            >
              Trigger HOC Error (Key: {globalRetryCount})
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          Integration Code Example
        </Typography>
        
        <Box sx={{ 
          bgcolor: 'grey.100',
          p: 2,
          borderRadius: 1,
          fontFamily: 'monospace',
          fontSize: '0.875rem',
          overflow: 'auto'
        }}>
          <pre>{`
// Basic usage
<DetectionErrorBoundary
  onError={(error, errorInfo) => console.log('Error:', error)}
  errorReportingService={errorReportingService}
  maxRetries={3}
  enableAutoRecovery={true}
  userId="user-123"
  sessionId="session-456"
>
  <YourDetectionComponent />
</DetectionErrorBoundary>

// HOC usage
const SafeComponent = withDetectionErrorBoundary(YourComponent, {
  maxRetries: 2,
  enableAutoRecovery: true,
  errorReportingService
});

// Error reporting service
const errorService = createErrorReportingService(
  '/api/error-reports',
  'your-api-key'
);
          `}</pre>
        </Box>
      </Box>
    </Box>
  );
};

export default DetectionErrorBoundaryExample;