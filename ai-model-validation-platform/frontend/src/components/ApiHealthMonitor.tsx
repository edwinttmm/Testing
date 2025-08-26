import React, { useState, useEffect, useCallback } from 'react';
import {
  Alert,
  AlertTitle,
  Card,
  CardContent,
  CardHeader,
  Typography,
  CircularProgress,
  Box,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  LinearProgress
} from '@mui/material';
import {
  CheckCircle,
  Error,
  Warning,
  Refresh,
  NetworkCheck,
  Speed,
  Timer,
  CloudOff
} from '@mui/icons-material';
import { smartApiService } from '../utils/smartApiService';
import { envConfig } from '../utils/envConfig';

interface ApiHealthStatus {
  overall: 'healthy' | 'degraded' | 'offline';
  primary: {
    available: boolean;
    latency?: number;
    error?: string;
  };
  fallbacks: Array<{
    url: string;
    available: boolean;
    latency?: number;
    error?: string;
  }>;
  lastChecked: Date;
  isOnline: boolean;
}

interface ApiHealthMonitorProps {
  showDetails?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export const ApiHealthMonitor: React.FC<ApiHealthMonitorProps> = ({
  showDetails = false,
  autoRefresh = true,
  refreshInterval = 30000 // 30 seconds
}) => {
  const [healthStatus, setHealthStatus] = useState<ApiHealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      setLoading(true);
      
      const connectivity = smartApiService.getConnectivityStatus();
      const config = envConfig.getConfig();
      
      // Test primary API
      let primaryLatency: number | undefined;
      let primaryError: string | undefined;
      let primaryAvailable = false;
      
      try {
        const startTime = Date.now();
        await smartApiService.get('/health', { skipFallback: true, skipCache: true });
        primaryLatency = Date.now() - startTime;
        primaryAvailable = true;
      } catch (error: any) {
        primaryError = error.message || 'Connection failed';
        primaryAvailable = false;
      }
      
      // Test fallback APIs
      const fallbacks = [];
      const fallbackUrls = ['http://localhost:8000', 'http://127.0.0.1:8000'];
      
      for (const url of fallbackUrls) {
        let fallbackLatency: number | undefined;
        let fallbackError: string | undefined;
        let fallbackAvailable = false;
        
        try {
          const startTime = Date.now();
          const response = await fetch(`${url}/health`, { 
            method: 'GET',
            signal: AbortSignal.timeout(5000)
          });
          
          if (response.ok) {
            fallbackLatency = Date.now() - startTime;
            fallbackAvailable = true;
          } else {
            fallbackError = `HTTP ${response.status}`;
          }
        } catch (error: any) {
          fallbackError = error.message || 'Connection failed';
        }
        
        fallbacks.push({
          url,
          available: fallbackAvailable,
          latency: fallbackLatency,
          error: fallbackError
        });
      }
      
      // Determine overall status
      let overall: 'healthy' | 'degraded' | 'offline';
      if (primaryAvailable) {
        overall = 'healthy';
      } else if (fallbacks.some(f => f.available)) {
        overall = 'degraded';
      } else {
        overall = 'offline';
      }
      
      const newStatus: ApiHealthStatus = {
        overall,
        primary: {
          available: primaryAvailable,
          latency: primaryLatency,
          error: primaryError
        },
        fallbacks,
        lastChecked: new Date(),
        isOnline: connectivity.isOnline
      };
      
      setHealthStatus(newStatus);
      setLastUpdate(new Date());
      
    } catch (error) {
      console.error('Health check failed:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(checkHealth, refreshInterval);
    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, checkHealth]);

  const getStatusColor = (status: 'healthy' | 'degraded' | 'offline') => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'degraded':
        return 'warning';
      case 'offline':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: 'healthy' | 'degraded' | 'offline') => {
    switch (status) {
      case 'healthy':
        return <CheckCircle color="success" />;
      case 'degraded':
        return <Warning color="warning" />;
      case 'offline':
        return <Error color="error" />;
      default:
        return <CloudOff />;
    }
  };

  const getLatencyColor = (latency: number) => {
    if (latency < 200) return 'success';
    if (latency < 1000) return 'warning';
    return 'error';
  };

  const formatLatency = (latency?: number) => {
    if (!latency) return 'N/A';
    return `${latency}ms`;
  };

  const renderCompactView = () => {
    if (loading && !healthStatus) {
      return (
        <Box display="flex" alignItems="center" gap={1}>
          <CircularProgress size={16} />
          <Typography variant="body2" color="text.secondary">
            Checking API status...
          </Typography>
        </Box>
      );
    }

    if (!healthStatus) {
      return (
        <Box display="flex" alignItems="center" gap={1}>
          <CloudOff color="disabled" />
          <Typography variant="body2" color="text.secondary">
            Status unknown
          </Typography>
        </Box>
      );
    }

    return (
      <Box display="flex" alignItems="center" gap={1}>
        {getStatusIcon(healthStatus.overall)}
        <Chip
          label={healthStatus.overall.toUpperCase()}
          color={getStatusColor(healthStatus.overall) as any}
          size="small"
        />
        {healthStatus.primary.available && healthStatus.primary.latency && (
          <Chip
            label={formatLatency(healthStatus.primary.latency)}
            color={getLatencyColor(healthStatus.primary.latency) as any}
            size="small"
            variant="outlined"
          />
        )}
        <Button
          size="small"
          onClick={() => setDetailsOpen(true)}
        >
          Details
        </Button>
      </Box>
    );
  };

  const renderDetailedView = () => {
    if (loading && !healthStatus) {
      return (
        <Card>
          <CardContent>
            <Box display="flex" justifyContent="center" alignItems="center" py={4}>
              <CircularProgress />
            </Box>
          </CardContent>
        </Card>
      );
    }

    if (!healthStatus) {
      return (
        <Alert severity="warning">
          <AlertTitle>API Status Unknown</AlertTitle>
          Unable to determine API connectivity status.
        </Alert>
      );
    }

    return (
      <Card>
        <CardHeader
          title={
            <Box display="flex" alignItems="center" gap={2}>
              {getStatusIcon(healthStatus.overall)}
              <Typography variant="h6">
                API Health Status
              </Typography>
              <Chip
                label={healthStatus.overall.toUpperCase()}
                color={getStatusColor(healthStatus.overall) as any}
              />
            </Box>
          }
          action={
            <Button
              variant="outlined"
              startIcon={loading ? <CircularProgress size={16} /> : <Refresh />}
              onClick={checkHealth}
              disabled={loading}
            >
              Refresh
            </Button>
          }
        />
        <CardContent>
          {healthStatus.overall === 'offline' && (
            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>All API Endpoints Unavailable</AlertTitle>
              The application cannot connect to any API servers. Please check your network connection and server status.
            </Alert>
          )}

          {healthStatus.overall === 'degraded' && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <AlertTitle>Primary API Unavailable</AlertTitle>
              The primary API server is not responding. The application is using fallback servers, which may result in reduced functionality.
            </Alert>
          )}

          <Grid container spacing={2}>
            {/* Primary API Status */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardHeader 
                  title="Primary API"
                  titleTypographyProps={{ variant: 'subtitle1' }}
                />
                <CardContent>
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        {healthStatus.primary.available ? (
                          <CheckCircle color="success" />
                        ) : (
                          <Error color="error" />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary="Status"
                        secondary={healthStatus.primary.available ? 'Available' : 'Unavailable'}
                      />
                    </ListItem>
                    
                    {healthStatus.primary.latency && (
                      <ListItem>
                        <ListItemIcon>
                          <Speed color={getLatencyColor(healthStatus.primary.latency) as any} />
                        </ListItemIcon>
                        <ListItemText
                          primary="Latency"
                          secondary={formatLatency(healthStatus.primary.latency)}
                        />
                      </ListItem>
                    )}
                    
                    {healthStatus.primary.error && (
                      <ListItem>
                        <ListItemIcon>
                          <Error color="error" />
                        </ListItemIcon>
                        <ListItemText
                          primary="Error"
                          secondary={healthStatus.primary.error}
                        />
                      </ListItem>
                    )}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {/* Fallback APIs Status */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardHeader 
                  title="Fallback APIs"
                  titleTypographyProps={{ variant: 'subtitle1' }}
                />
                <CardContent>
                  {healthStatus.fallbacks.map((fallback, index) => (
                    <Box key={fallback.url} mb={index < healthStatus.fallbacks.length - 1 ? 2 : 0}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        {fallback.url}
                      </Typography>
                      <Box display="flex" alignItems="center" gap={1}>
                        {fallback.available ? (
                          <CheckCircle color="success" fontSize="small" />
                        ) : (
                          <Error color="error" fontSize="small" />
                        )}
                        <Typography variant="body2">
                          {fallback.available ? 'Available' : 'Unavailable'}
                        </Typography>
                        {fallback.latency && (
                          <Chip
                            label={formatLatency(fallback.latency)}
                            size="small"
                            color={getLatencyColor(fallback.latency) as any}
                            variant="outlined"
                          />
                        )}
                      </Box>
                      {fallback.error && (
                        <Typography variant="caption" color="error">
                          {fallback.error}
                        </Typography>
                      )}
                    </Box>
                  ))}
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Additional Information */}
          <Box mt={2}>
            <Typography variant="body2" color="text.secondary">
              <Timer fontSize="small" sx={{ mr: 1, verticalAlign: 'middle' }} />
              Last checked: {healthStatus.lastChecked.toLocaleTimeString()}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              <NetworkCheck fontSize="small" sx={{ mr: 1, verticalAlign: 'middle' }} />
              Network status: {healthStatus.isOnline ? 'Online' : 'Offline'}
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  };

  const renderDetailsDialog = () => {
    return (
      <Dialog
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={2}>
            {healthStatus && getStatusIcon(healthStatus.overall)}
            API Connectivity Details
          </Box>
        </DialogTitle>
        <DialogContent>
          {renderDetailedView()}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailsOpen(false)}>
            Close
          </Button>
          <Button 
            onClick={checkHealth} 
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <Refresh />}
          >
            Refresh
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <>
      {showDetails ? renderDetailedView() : renderCompactView()}
      {!showDetails && renderDetailsDialog()}
    </>
  );
};

export default ApiHealthMonitor;