import React, { Component, ErrorInfo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  AlertTitle,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

class LabJackErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error details for debugging
    console.error('LabJack Component Error:', error);
    console.error('Error Info:', errorInfo);
    
    this.setState({
      hasError: true,
      error,
      errorInfo,
    });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Card sx={{ maxWidth: 800, mx: 'auto', mt: 2 }}>
          <CardContent>
            <Box display="flex" alignItems="center" gap={2} mb={2}>
              <ErrorIcon color="error" fontSize="large" />
              <Typography variant="h6" color="error">
                LabJack Component Error
              </Typography>
            </Box>

            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>Something went wrong with the LabJack status panel</AlertTitle>
              {this.state.error?.message || 'An unexpected error occurred in the LabJack component.'}
            </Alert>

            <Typography variant="body2" color="text.secondary" paragraph>
              This error is likely caused by one of the following issues:
            </Typography>

            <List dense>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="info" />
                </ListItemIcon>
                <ListItemText
                  primary="Backend Service Not Running"
                  secondary="The LabJack backend service may not be started. Try running the backend server."
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="info" />
                </ListItemIcon>
                <ListItemText
                  primary="Network Connection Issues"
                  secondary="Check your network connection and ensure the API endpoints are accessible."
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="info" />
                </ListItemIcon>
                <ListItemText
                  primary="LabJack Hardware Issues"
                  secondary="Ensure LabJack devices are connected and drivers are properly installed."
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <InfoIcon color="info" />
                </ListItemIcon>
                <ListItemText
                  primary="Component Configuration"
                  secondary="The component may have received invalid props or configuration."
                />
              </ListItem>
            </List>

            <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 2 }}>
              <strong>Suggested Actions:</strong>
            </Typography>

            <List dense>
              <ListItem>
                <Typography variant="body2">
                  1. Start the backend service: <code>cd backend && python main.py</code>
                </Typography>
              </ListItem>
              <ListItem>
                <Typography variant="body2">
                  2. Check LabJack hardware connections and drivers
                </Typography>
              </ListItem>
              <ListItem>
                <Typography variant="body2">
                  3. Refresh the page or reset the component
                </Typography>
              </ListItem>
              <ListItem>
                <Typography variant="body2">
                  4. Check browser console for additional error details
                </Typography>
              </ListItem>
            </List>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <Alert severity="info" sx={{ mt: 2 }}>
                <AlertTitle>Development Error Details</AlertTitle>
                <Typography variant="body2" component="pre" sx={{ fontSize: '0.75rem', mt: 1 }}>
                  {this.state.error.stack}
                </Typography>
              </Alert>
            )}

            <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={this.handleReset}
                color="primary"
              >
                Reset Component
              </Button>
              <Button
                variant="outlined"
                onClick={() => window.location.reload()}
                color="secondary"
              >
                Refresh Page
              </Button>
            </Box>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

export default LabJackErrorBoundary;