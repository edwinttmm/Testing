import React from 'react';
import ErrorBoundary, { ErrorBoundaryProps } from './ErrorBoundary';
import { Box, Typography, Button, Alert } from '@mui/material';
import { Wifi as WifiIcon, WifiOff as WifiOffIcon } from '@mui/icons-material';

interface WebSocketErrorBoundaryProps extends Omit<ErrorBoundaryProps, 'fallback'> {
  reconnectAction?: () => void;
  connectionStatus?: 'connected' | 'disconnected' | 'connecting';
}

const WebSocketErrorBoundary: React.FC<WebSocketErrorBoundaryProps> = ({
  children,
  reconnectAction,
  connectionStatus = 'disconnected',
  ...errorBoundaryProps
}) => {
  const customFallback = (
    <Box 
      sx={{ 
        p: 3, 
        textAlign: 'center',
        backgroundColor: theme => theme.palette.background.paper,
        border: theme => `1px solid ${theme.palette.divider}`,
        borderRadius: 1,
      }}
    >
      <Alert 
        severity="warning" 
        icon={<WifiOffIcon />}
        sx={{ mb: 2 }}
      >
        <Typography variant="h6" gutterBottom>
          Real-time Connection Lost
        </Typography>
        <Typography variant="body2" color="text.secondary">
          The live data connection has been interrupted. Some features may not work properly until reconnected.
        </Typography>
      </Alert>

      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Status: {connectionStatus === 'connecting' ? 'Reconnecting...' : 'Disconnected'}
        </Typography>
        
        {reconnectAction && connectionStatus !== 'connecting' && (
          <Button
            variant="contained"
            startIcon={<WifiIcon />}
            onClick={reconnectAction}
            size="small"
          >
            Reconnect
          </Button>
        )}
        
        {connectionStatus === 'connecting' && (
          <Typography variant="body2" color="primary">
            Attempting to reconnect...
          </Typography>
        )}
      </Box>
    </Box>
  );

  return (
    <ErrorBoundary
      {...errorBoundaryProps}
      fallback={customFallback}
      level="component"
      context="websocket-connection"
      enableRetry={true}
      maxRetries={5}
    >
      {children}
    </ErrorBoundary>
  );
};

export default WebSocketErrorBoundary;