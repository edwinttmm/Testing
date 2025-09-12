import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Alert,
  Grid,
  IconButton,
  Tooltip,
  Paper,
  Stack
} from '@mui/material';
import {
  Cable as CableIcon,
  SignalWifi4Bar as SignalIcon,
  SignalWifiOff as NoSignalIcon,
  Speed as SpeedIcon,
  Timeline as TimelineIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';

interface SignalData {
  timestamp: number;
  voltage: number;
  channel: string;
  latency?: number;
}

interface ConnectionStatus {
  connected: boolean;
  latency: number;
  lastCheck?: Date;
  errorMessage?: string;
}

interface HardwareSignalPanelProps {
  signalData: SignalData[];
  connectionStatus: ConnectionStatus;
  isRunning: boolean;
  onSignalDetected?: (signal: SignalData) => void;
  onConnectionStatusChange?: (status: ConnectionStatus) => void;
}

const HardwareSignalPanel: React.FC<HardwareSignalPanelProps> = ({
  signalData,
  connectionStatus,
  isRunning,
  onSignalDetected,
  onConnectionStatusChange
}) => {
  const [realtimeVoltage, setRealtimeVoltage] = useState<{ [channel: string]: number }>({});
  const [signalStrength, setSignalStrength] = useState(0);
  const [averageLatency, setAverageLatency] = useState(0);

  // Simulate real-time signal monitoring
  useEffect(() => {
    if (!isRunning || !connectionStatus.connected) return;

    const interval = setInterval(() => {
      // Simulate voltage readings
      const channels = ['AIN0', 'AIN1'];
      const newVoltages: { [channel: string]: number } = {};
      
      channels.forEach(channel => {
        const baseVoltage = 2.5;
        const noise = (Math.random() - 0.5) * 0.2; // ±0.1V noise
        const signal = Math.sin(Date.now() / 1000) * 0.5; // Sine wave signal
        newVoltages[channel] = baseVoltage + noise + signal;
      });

      setRealtimeVoltage(newVoltages);

      // Calculate signal strength based on voltage stability
      const voltage = newVoltages['AIN0'] || 0;
      const strength = Math.max(0, Math.min(100, (voltage / 5.0) * 100));
      setSignalStrength(strength);

      // Simulate signal detection events
      if (Math.random() < 0.1 && voltage > 3.0) { // 10% chance when voltage is high
        const latency = Math.random() * 200 + 50; // 50-250ms latency
        const signal: SignalData = {
          timestamp: Date.now(),
          voltage,
          channel: 'AIN0',
          latency
        };
        
        onSignalDetected?.(signal);
      }
    }, 100); // 10Hz update rate

    return () => clearInterval(interval);
  }, [isRunning, connectionStatus.connected, onSignalDetected]);

  // Calculate average latency from recent signal data
  useEffect(() => {
    if (signalData.length > 0) {
      const recentSignals = signalData.slice(-10); // Last 10 signals
      const validLatencies = recentSignals.filter(s => s.latency !== undefined);
      if (validLatencies.length > 0) {
        const avg = validLatencies.reduce((sum, s) => sum + (s.latency || 0), 0) / validLatencies.length;
        setAverageLatency(avg);
      }
    }
  }, [signalData]);

  const getConnectionColor = () => {
    if (!connectionStatus.connected) return 'error';
    if (connectionStatus.latency > 100) return 'warning';
    return 'success';
  };

  const getSignalQuality = () => {
    if (signalStrength > 80) return 'Excellent';
    if (signalStrength > 60) return 'Good';
    if (signalStrength > 40) return 'Fair';
    if (signalStrength > 20) return 'Poor';
    return 'No Signal';
  };

  const formatVoltage = (voltage: number) => {
    return `${voltage.toFixed(3)}V`;
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CableIcon />
            Hardware Signal Monitor
          </Typography>
          
          <Stack direction="row" spacing={1}>
            <Tooltip title="Refresh Connection">
              <IconButton 
                size="small" 
                onClick={() => {
                  onConnectionStatusChange?.({
                    ...connectionStatus,
                    lastCheck: new Date()
                  });
                }}
              >
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Settings">
              <IconButton size="small">
                <SettingsIcon />
              </IconButton>
            </Tooltip>
          </Stack>
        </Box>

        {/* Connection Status */}
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={3}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {connectionStatus.connected ? (
                  <SignalIcon color="success" />
                ) : (
                  <NoSignalIcon color="error" />
                )}
                
                <Box>
                  <Typography variant="subtitle2">
                    {connectionStatus.connected ? 'Connected' : 'Disconnected'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    LabJack Hardware
                  </Typography>
                </Box>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SpeedIcon fontSize="small" />
                  Latency
                </Typography>
                <Chip 
                  label={`${connectionStatus.latency}ms`}
                  color={getConnectionColor()}
                  size="small"
                />
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="subtitle2">Signal Quality</Typography>
                <Typography variant="body2" color={signalStrength > 60 ? 'success.main' : 'warning.main'}>
                  {getSignalQuality()} ({signalStrength.toFixed(1)}%)
                </Typography>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="subtitle2">Avg Response</Typography>
                <Typography variant="body2">
                  {averageLatency.toFixed(1)}ms
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>

        {/* Real-time Voltage Display */}
        {connectionStatus.connected && (
          <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Real-time Voltage Readings
            </Typography>
            
            <Grid container spacing={2}>
              {Object.entries(realtimeVoltage).map(([channel, voltage]) => (
                <Grid item xs={12} sm={6} md={4} key={channel}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="primary.main" sx={{ fontFamily: 'monospace' }}>
                      {formatVoltage(voltage)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {channel}
                    </Typography>
                    
                    {/* Voltage Bar */}
                    <LinearProgress
                      variant="determinate"
                      value={(voltage / 5.0) * 100}
                      sx={{ 
                        mt: 1, 
                        height: 8, 
                        borderRadius: 4,
                        backgroundColor: 'grey.200',
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 4,
                          backgroundColor: voltage > 3.5 ? 'error.main' : 
                                          voltage > 2.5 ? 'warning.main' : 'success.main'
                        }
                      }}
                    />
                    
                    <Typography variant="caption" color="text.secondary">
                      0V - 5V Range
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </Paper>
        )}

        {/* Recent Signal Activity */}
        {signalData.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TimelineIcon fontSize="small" />
              Recent Signal Activity ({signalData.slice(-5).length} recent)
            </Typography>
            
            <Stack spacing={1}>
              {signalData.slice(-5).reverse().map((signal, index) => (
                <Paper variant="outlined" key={signal.timestamp} sx={{ p: 1 }}>
                  <Grid container alignItems="center" spacing={2}>
                    <Grid item xs={3}>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {new Date(signal.timestamp).toLocaleTimeString()}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={2}>
                      <Typography variant="body2" color="primary.main" sx={{ fontFamily: 'monospace' }}>
                        {formatVoltage(signal.voltage)}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={2}>
                      <Typography variant="body2" color="text.secondary">
                        {signal.channel}
                      </Typography>
                    </Grid>
                    
                    <Grid item xs={3}>
                      {signal.latency && (
                        <Chip 
                          label={`${signal.latency.toFixed(1)}ms`}
                          color={signal.latency < 100 ? 'success' : signal.latency < 200 ? 'warning' : 'error'}
                          size="small"
                        />
                      )}
                    </Grid>
                    
                    <Grid item xs={2}>
                      <Chip 
                        label={signal.latency && signal.latency < 500 ? 'PASS' : 'FAIL'}
                        color={signal.latency && signal.latency < 500 ? 'success' : 'error'}
                        size="small"
                        variant="outlined"
                      />
                    </Grid>
                  </Grid>
                </Paper>
              ))}
            </Stack>
          </Box>
        )}

        {/* Error State */}
        {!connectionStatus.connected && connectionStatus.errorMessage && (
          <Alert severity="error" sx={{ mt: 2 }}>
            Hardware Connection Error: {connectionStatus.errorMessage}
          </Alert>
        )}

        {/* No Data State */}
        {connectionStatus.connected && signalData.length === 0 && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Hardware connected. Waiting for signal data during test execution...
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

export default HardwareSignalPanel;