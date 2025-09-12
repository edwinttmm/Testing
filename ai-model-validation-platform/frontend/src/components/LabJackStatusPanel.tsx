import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Alert,
  LinearProgress,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tooltip,
  Grid,
  Switch,
  FormControlLabel,
  Divider,
  CircularProgress,
  Snackbar,
  AlertTitle,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  Usb as UsbIcon,
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon,
  Computer as ComputerIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Timeline as TimelineIcon,
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  Router as RouterIcon,
  Cloud as CloudIcon,
  BugReport as BugReportIcon,
  Warning as WarningIcon,
  Search as SearchIcon,
  Autorenew as AutorenewIcon,
  ExpandMore as ExpandMoreIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  PowerSettingsNew as PowerIcon,
  NetworkCheck as NetworkCheckIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';
import { apiService } from '../services/api';
import { labjackLogger, withPerformanceTracking } from '../utils/labjackLogger';
import { LabJackStatus, ConnectionMode, ConnectionStatus, WindowsDriverInfo } from '../services/types';

// LabJack connection modes and status types imported from shared types

// Windows compatibility and retry configuration
interface RetryConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  exponentialFactor: number;
}

interface ConnectionAttempt {
  timestamp: number;
  mode: ConnectionMode;
  success: boolean;
  error?: string;
  latency?: number;
}

interface DiagnosticTest {
  name: string;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped';
  result?: string;
  error?: string;
  duration?: number;
}



interface StreamingData {
  data: number[];
  timestamp: number;
  sample_rate: number;
  channels: string[];
}

interface LabJackStatusPanelProps {
  onDataReceived?: (data: StreamingData) => void;
  onStatusChanged?: (status: LabJackStatus) => void;
}

const LabJackStatusPanel: React.FC<LabJackStatusPanelProps> = ({
  onDataReceived,
  onStatusChanged,
}) => {
  const [status, setStatus] = useState<LabJackStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [autoReconnect, setAutoReconnect] = useState(true);
  const [streamingData, setStreamingData] = useState<number[]>([]);
  const [dataRate, setDataRate] = useState(0);
  const [connectionLatency, setConnectionLatency] = useState<number | null>(null);
  const [connectionHistory, setConnectionHistory] = useState<ConnectionAttempt[]>([]);
  const [diagnosticTests, setDiagnosticTests] = useState<DiagnosticTest[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'warning' | 'error'>('warning');
  const [windowsDriverInfo, setWindowsDriverInfo] = useState<WindowsDriverInfo | null>(null);
  const [recoveryMode, setRecoveryMode] = useState(false);

  // WebSocket for real-time updates
  const [wsConnection, setWsConnection] = useState<WebSocket | null>(null);
  
  // Refs for cleanup and state management
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const statusPollingRef = useRef<NodeJS.Timeout | null>(null);
  const discoveryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const componentMountedRef = useRef(true);

  // Retry configuration for robust connection handling
  const retryConfig: RetryConfig = {
    maxRetries: 5,
    baseDelay: 1000,
    maxDelay: 30000,
    exponentialFactor: 2,
  };

  // Enhanced status loading with retry mechanism, logging, and fallback support
  const loadStatus = useCallback(async (silent: boolean = false) => {
    if (!componentMountedRef.current) return;
    
    return withPerformanceTracking(
      'labjack-status-load',
      async () => {
        try {
          if (!silent) {
            setLoading(true);
            setError(null);
            labjackLogger.debug('Status', 'Loading LabJack status', { silent });
          }

          // Check service availability first
          const serviceCheck = await checkServiceAvailability();
          if (!serviceCheck.available && !silent) {
            // Show service unavailable message with helpful suggestions
            const mockStatus: LabJackStatus = {
              mode: 'mock',
              status: 'disconnected',
              connected: false,
              device_info: {
                device_type: 'Mock LabJack',
                is_mock: true,
              },
              streaming: false,
              sample_rate: 1000,
              channels: ['AIN0', 'AIN1'],
              voltage_threshold: 2.5,
              statistics: {
                samples_received: 0,
                errors_count: 0,
                connection_attempts: 0,
                successful_connections: 0,
                failed_connections: 0,
                uptime_start: new Date().toISOString(),
                total_uptime: 0,
                recovery_attempts: 0,
              },
            };
            setStatus(mockStatus);
            setError(`${serviceCheck.error}\n\nShowing mock data. ${serviceCheck.suggestions?.join(' ')}`);
            return;
          }
          
          const response = await apiService.get<LabJackStatus>('/api/labjack/status');
          
          if (!componentMountedRef.current) return;
          
          setStatus(response);
          setConnectionLatency(response.bridge_latency || 0);
          
          // Update Windows driver info if available
          if (response.windows_driver) {
            setWindowsDriverInfo(response.windows_driver);
            if (!response.windows_driver.supported) {
              labjackLogger.logWindowsDriverIssue(
                'Unsupported or missing drivers detected',
                response.windows_driver.recommendations
              );
            }
          }
          
          if (onStatusChanged) {
            onStatusChanged(response);
          }
          
          // Clear retry count on successful load
          if (retryCount > 0) {
            setRetryCount(0);
            showSnackbar('Connection restored successfully', 'success');
            labjackLogger.info('Status', `Status loading recovered after ${retryCount} retries`);
          }
          
          labjackLogger.info('Status', 'LabJack status loaded successfully', {
            mode: response.mode,
            connected: response.connected,
            streaming: response.streaming,
          });
          
        } catch (err: unknown) {
          if (!componentMountedRef.current) return;
          
          const error = err as { response?: { data?: { detail?: string } }; message?: string };
          const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to load LabJack status';
          
          labjackLogger.error('Status', 'Failed to load LabJack status', error as Error, {
            silent,
            retryCount,
            autoReconnect,
          });
          
          // Check if this is a service availability issue
          const isServiceUnavailable = errorMessage.includes('Network Error') || 
            errorMessage.includes('ERR_NETWORK') ||
            errorMessage.includes('fetch');
          
          if (isServiceUnavailable && !silent) {
            // Provide fallback mock data and helpful guidance
            const mockStatus: LabJackStatus = {
              mode: 'mock',
              status: 'error',
              connected: false,
              device_info: {
                device_type: 'Service Unavailable',
                is_mock: true,
              },
              streaming: false,
              sample_rate: 1000,
              channels: ['AIN0', 'AIN1'],
              voltage_threshold: 2.5,
              error_message: errorMessage,
              statistics: {
                samples_received: 0,
                errors_count: 1,
                connection_attempts: 1,
                successful_connections: 0,
                failed_connections: 1,
                uptime_start: new Date().toISOString(),
                total_uptime: 0,
                recovery_attempts: retryCount,
              },
            };
            setStatus(mockStatus);
            setError('Backend services not running. Please start the backend to connect to actual LabJack devices.');
            return;
          }
          
          // Only show error if not in silent mode and not already in error state
          if (!silent) {
            setError(errorMessage);
          }
          
          // Implement exponential backoff retry for critical failures
          if (retryCount < retryConfig.maxRetries && autoReconnect && !isServiceUnavailable) {
            const delay = Math.min(
              retryConfig.baseDelay * Math.pow(retryConfig.exponentialFactor, retryCount),
              retryConfig.maxDelay
            );
            
            setRetryCount(prev => prev + 1);
            labjackLogger.warn('Status', `Retrying status load in ${delay}ms (attempt ${retryCount + 1}/${retryConfig.maxRetries})`);
            
            retryTimeoutRef.current = setTimeout(() => {
              loadStatus(true).catch(error => {
                console.error('Error in retry loadStatus:', error);
              });
            }, delay);
          }
          
          // Don't re-throw to prevent unhandled promise rejection
          // Error is already logged and handled
        } finally {
          if (!silent && componentMountedRef.current) {
            setLoading(false);
          }
        }
      },
      { silent, retryCount }
    );
  }, [onStatusChanged, retryCount, autoReconnect]);

  // Enhanced connection with retry logic, mode fallback, service availability checks, and comprehensive logging
  const handleConnect = async (forceMode?: ConnectionMode, attempt: number = 1) => {
    if (!componentMountedRef.current) return;
    
    const mode = forceMode || 'auto';
    const operationId = `labjack-connect-${mode}-${attempt}`;
    
    return withPerformanceTracking(
      operationId,
      async () => {
        try {
          setLoading(true);
          setError(null);
          setRecoveryMode(attempt > 1);
          
          // Check service availability first
          const serviceCheck = await checkServiceAvailability();
          if (!serviceCheck.available) {
            setError(`Cannot connect: ${serviceCheck.error} Please start the backend services first.`);
            showSnackbar('Backend service required for LabJack connection', 'error');
            return;
          }
          
          labjackLogger.logConnectionAttempt(mode, attempt, {
            recoveryMode: attempt > 1,
            isWindows: navigator.platform.toLowerCase().includes('win'),
          });
          
          // Enhanced payload with Windows-specific options
          const payload: any = {
            force_mode: mode,
            retry_attempt: attempt,
            windows_compatibility: navigator.platform.toLowerCase().includes('win'),
            driver_detection: true,
            timeout: 15000, // 15 second timeout
          };
          
          const response = await apiService.post('/api/labjack/connect', payload);
          
          // Record successful connection attempt
          const connectionAttempt: ConnectionAttempt = {
            timestamp: Date.now(),
            mode,
            success: true,
            latency: (response as any)?.latency || 0,
          };
          
          setConnectionHistory(prev => [connectionAttempt, ...prev.slice(0, 9)]);
          showSnackbar(`Connected successfully via ${mode} mode`, 'success');
          
          labjackLogger.logConnectionSuccess(mode, (response as any)?.device_info, (response as any)?.latency);
          
          // Reload status after successful connection
          setTimeout(() => {
            loadStatus().catch(error => {
              console.error('Error reloading status after connection:', error);
            });
          }, 1000);
          
        } catch (err: unknown) {
          if (!componentMountedRef.current) return;
          
          const error = err as { response?: { data?: { detail?: string } }; message?: string };
          const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to connect';
          
          // Check if this is a service availability issue
          const isServiceError = errorMessage.includes('Network Error') || 
            errorMessage.includes('ERR_NETWORK') ||
            errorMessage.includes('fetch') ||
            errorMessage.includes('503') ||
            errorMessage.includes('unable to reach');
          
          if (isServiceError) {
            setError('Backend service unavailable. Please start the LabJack service to enable connections.');
            showSnackbar('LabJack service is not running', 'error');
            return;
          }
          
          labjackLogger.logConnectionFailure(mode, error as Error, {
            attempt,
            isWindows: navigator.platform.toLowerCase().includes('win'),
          });
          
          // Record failed connection attempt
          const connectionAttempt: ConnectionAttempt = {
            timestamp: Date.now(),
            mode,
            success: false,
            error: errorMessage,
          };
          
          setConnectionHistory(prev => [connectionAttempt, ...prev.slice(0, 9)]);
          
          // Implement intelligent connection mode fallback for Windows
          const isWindows = navigator.platform.toLowerCase().includes('win');
          
          if (attempt === 1 && !forceMode) {
            // First attempt failed, try platform-specific fallback
            const nextMode = isWindows ? 'direct' : 'bridge';
            labjackLogger.info('Connection', `Auto connection failed, trying ${nextMode} mode...`);
            showSnackbar(`Retrying with ${nextMode} mode...`, 'warning');
            setTimeout(() => {
              handleConnect(nextMode, 2).catch(error => {
                console.error('Error in connection retry:', error);
              });
            }, 2000);
            return;
          }
          
          if (attempt === 2 && forceMode === 'direct' && isWindows) {
            labjackLogger.info('Connection', 'Direct connection failed, trying bridge mode...');
            showSnackbar('Direct connection failed, trying bridge mode...', 'warning');
            setTimeout(() => {
              handleConnect('bridge', 3).catch(error => {
                console.error('Error in bridge connection retry:', error);
              });
            }, 2000);
            return;
          }
          
          if (attempt === 3 && forceMode === 'bridge') {
            labjackLogger.warn('Connection', 'Bridge connection failed, falling back to mock mode...');
            showSnackbar('Trying mock mode for testing...', 'warning');
            setTimeout(() => {
              handleConnect('mock', 4).catch(error => {
                console.error('Error in mock connection retry:', error);
              });
            }, 2000);
            return;
          }
          
          // All attempts failed
          const finalError = `Connection failed after ${attempt} attempts: ${errorMessage}`;
          setError(finalError);
          setRecoveryMode(false);
          showSnackbar('All connection attempts failed - check hardware and drivers', 'error');
          
          labjackLogger.critical('Connection', finalError, error as Error, {
            totalAttempts: attempt,
            isWindows,
            lastMode: mode,
          });
          
          // Don't throw final error to prevent unhandled promise rejection
          // Error is already logged and set in state
          
        } finally {
          if (componentMountedRef.current) {
            setLoading(false);
            setRecoveryMode(false);
          }
        }
      },
      { mode, attempt, isWindows: navigator.platform.toLowerCase().includes('win') }
    );
  };

  // Enhanced disconnect with cleanup
  const handleDisconnect = async () => {
    if (!componentMountedRef.current) return;
    
    try {
      setLoading(true);
      setError(null);
      
      // Close WebSocket connection first
      if (wsConnection) {
        wsConnection.close(1000, 'User disconnect');
        setWsConnection(null);
      }
      
      await apiService.post('/api/labjack/disconnect');
      
      // Clear streaming data
      setStreamingData([]);
      setDataRate(0);
      
      showSnackbar('Disconnected successfully', 'success');
      
      // Reload status after disconnect
      setTimeout(() => {
        loadStatus().catch(error => {
          console.error('Error reloading status after disconnect:', error);
        });
      }, 500);
      
    } catch (err: unknown) {
      if (!componentMountedRef.current) return;
      
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to disconnect';
      setError(errorMessage);
      showSnackbar('Disconnect failed', 'error');
      
    } finally {
      if (componentMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  // Enhanced automatic device discovery function with service availability checking
  const handleDeviceDiscovery = async () => {
    if (!componentMountedRef.current) return;
    
    try {
      setIsDiscovering(true);
      setError(null);
      
      // Check service availability first
      const serviceCheck = await checkServiceAvailability();
      if (!serviceCheck.available) {
        showSnackbar('Backend service required for device discovery', 'error');
        setError(`Discovery unavailable: ${serviceCheck.error}`);
        return;
      }
      
      showSnackbar('Discovering LabJack devices...', 'warning');
      
      const response = await apiService.post('/api/labjack/discover', {
        timeout: 10000,
        scan_network: true,
        scan_usb: true,
        windows_compatibility: navigator.platform.toLowerCase().includes('win'),
      });
      
      const typedResponse = response as { devices_found?: number; message?: string; devices?: Array<{ name: string; connection: string }> };
      if (typedResponse.devices_found && typedResponse.devices_found > 0) {
        showSnackbar(`Found ${typedResponse.devices_found} LabJack device(s)`, 'success');
        
        // Show device details if available
        if (typedResponse.devices && typedResponse.devices.length > 0) {
          const deviceList = typedResponse.devices.map(d => `${d.name} (${d.connection})`).join(', ');
          labjackLogger.info('Discovery', `Discovered devices: ${deviceList}`);
        }
        
        // Auto-connect to first discovered device
        setTimeout(() => {
          handleConnect().catch(error => {
            console.error('Error in auto-connect after discovery:', error);
          });
        }, 1000);
      } else {
        showSnackbar('No LabJack devices found - check connections or try mock mode', 'warning');
        labjackLogger.warn('Discovery', 'No devices found during scan');
      }
      
    } catch (err: unknown) {
      if (!componentMountedRef.current) return;
      
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = error?.response?.data?.detail || error?.message || 'Discovery failed';
      
      // Check if this is a service availability issue
      const isServiceError = errorMessage.includes('Network Error') || 
        errorMessage.includes('ERR_NETWORK') ||
        errorMessage.includes('fetch') ||
        errorMessage.includes('503');
      
      if (isServiceError) {
        showSnackbar('Discovery service unavailable - backend not running', 'error');
        setError('Cannot discover devices: Backend service is not running. Please start the LabJack service.');
      } else {
        showSnackbar(`Discovery failed: ${errorMessage}`, 'error');
        setError(`Device discovery failed: ${errorMessage}`);
      }
      
      labjackLogger.error('Discovery', 'Device discovery failed', error as Error);
      
    } finally {
      if (componentMountedRef.current) {
        setIsDiscovering(false);
      }
    }
  };

  // Enhanced streaming control with validation
  const handleToggleStreaming = async () => {
    if (!componentMountedRef.current) return;
    
    try {
      setLoading(true);
      setError(null);
      
      if (status?.streaming) {
        await apiService.post('/api/labjack/stop-stream');
        setStreamingData([]);
        setDataRate(0);
        showSnackbar('Streaming stopped', 'warning');
      } else {
        // Validate streaming configuration
        const channels = status?.channels || ['AIN0', 'AIN1'];
        const sampleRate = status?.sample_rate || 1000;
        
        if (sampleRate > 50000) {
          throw new Error('Sample rate too high for stable operation');
        }
        
        const payload = {
          channels,
          sample_rate: sampleRate,
          voltage_threshold: status?.voltage_threshold || 2.5,
          buffer_size: Math.min(sampleRate * 2, 10000), // 2 second buffer max
        };
        
        await apiService.post('/api/labjack/start-stream', payload);
        showSnackbar(`Streaming started: ${channels.join(', ')} at ${sampleRate} Hz`, 'success');
      }
      
      setTimeout(() => {
        loadStatus().catch(error => {
          console.error('Error reloading status after streaming toggle:', error);
        });
      }, 500);
      
    } catch (err: unknown) {
      if (!componentMountedRef.current) return;
      
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to toggle streaming';
      setError(errorMessage);
      showSnackbar(`Streaming error: ${errorMessage}`, 'error');
      
    } finally {
      if (componentMountedRef.current) {
        setLoading(false);
      }
    }
  };
  
  // Snackbar utility function
  const showSnackbar = (message: string, severity: 'success' | 'warning' | 'error') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  };

  // Service availability check with fallback mechanisms
  const checkServiceAvailability = useCallback(async () => {
    try {
      // Try to reach the main API service
      await apiService.get('/health', { timeout: 3000 });
      return { available: true, service: 'main_api' };
    } catch (error) {
      try {
        // Fallback to simple detection service  
        const response = await fetch('http://localhost:8000/health', {
          method: 'GET',
          signal: AbortSignal.timeout(3000)
        });
        if (response.ok) {
          return { available: true, service: 'simple_detection' };
        }
      } catch {
        // Both services unavailable
      }
      return { 
        available: false, 
        error: 'Backend services are not running. Please start the backend server.',
        suggestions: [
          'Run "cd backend && python main.py" to start the main API service',
          'Or run "cd backend && python simple_detection_service.py" for basic functionality',
          'Check if the backend is running on the correct port (8000 or 8001)',
          'The LabJack panel will show mock data when services are unavailable'
        ]
      };
    }
  }, []);

  // Enhanced WebSocket setup with robust error handling
  useEffect(() => {
    if (!status?.connected || !componentMountedRef.current) {
      return;
    }
    
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    let pingInterval: NodeJS.Timeout;
    let reconnectTimeout: NodeJS.Timeout;
    
    const connectWebSocket = () => {
      if (!componentMountedRef.current) return;
      
      const wsUrl = process.env.REACT_APP_WS_URL?.replace('http', 'ws') || 'ws://localhost:8000';
      const ws = new WebSocket(`${wsUrl}/ws/labjack/stream`);
      
      ws.onopen = () => {
        if (!componentMountedRef.current) return;
        
        console.log('LabJack WebSocket connected');
        setWsConnection(ws);
        reconnectAttempts = 0;
        
        // Send initial configuration
        ws.send(JSON.stringify({
          type: 'subscribe',
          channels: status?.channels || ['AIN0', 'AIN1'],
          sample_rate: status?.sample_rate || 1000,
        }));
        
        // Setup ping interval
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
              type: 'ping',
              timestamp: Date.now()
            }));
          }
        }, 10000);
      };
      
      ws.onmessage = (event) => {
        if (!componentMountedRef.current) return;
        
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'streaming_data' && data.payload) {
            const streamData: StreamingData = {
              data: data.payload.data || data.payload.voltage_data || [],
              timestamp: data.payload.timestamp || Date.now(),
              sample_rate: data.payload.sample_rate || 33,
              channels: data.payload.channels || ['AIN0', 'AIN1'],
            };
            
            setStreamingData(prev => {
              const newData = [...prev.slice(-100), ...(streamData.data || [])];
              return newData;
            });
            
            setDataRate(streamData.data?.length || 0);
            
            if (onDataReceived) {
              onDataReceived(streamData);
            }
            
          } else if (data.type === 'status_update') {
            setStatus(prev => prev ? { ...prev, ...data.payload } : null);
            
          } else if (data.type === 'latency_update') {
            setConnectionLatency(data.payload.latency);
            
          } else if (data.type === 'error') {
            console.error('WebSocket error message:', data.payload);
            setError(data.payload.message || 'WebSocket error occurred');
            
          } else if (data.type === 'pong') {
            // Update connection health based on pong response
            const latency = Date.now() - data.payload.timestamp;
            setConnectionLatency(latency);
          }
          
        } catch (err) {
          console.error('Error parsing WebSocket data:', err);
        }
      };
      
      ws.onerror = (error) => {
        console.error('LabJack WebSocket error:', error);
        if (componentMountedRef.current) {
          setError('WebSocket connection error - check network connectivity');
        }
      };
      
      ws.onclose = (event) => {
        if (!componentMountedRef.current) return;
        
        console.log(`LabJack WebSocket closed: ${event.code} - ${event.reason}`);
        setWsConnection(null);
        
        if (pingInterval) {
          clearInterval(pingInterval);
        }
        
        // Implement exponential backoff for reconnection
        if (autoReconnect && status?.connected && event.code > 1001 && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 30000);
          
          console.log(`WebSocket reconnection attempt ${reconnectAttempts}/${maxReconnectAttempts} in ${delay}ms`);
          
          reconnectTimeout = setTimeout(() => {
            connectWebSocket();
          }, delay);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          setError('WebSocket connection lost - maximum reconnection attempts exceeded');
        }
      };
      
      return ws;
    };
    
    const ws = connectWebSocket();
    
    // Cleanup function
    return () => {
      if (pingInterval) clearInterval(pingInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        ws.close(1000, 'Component unmounting');
      }
      setWsConnection(null);
    };
  }, [status?.connected, status?.channels, status?.sample_rate, autoReconnect, onDataReceived]);

  // Comprehensive diagnostic tests
  const runDiagnosticTests = useCallback(async () => {
    if (!componentMountedRef.current) return;
    
    const tests: DiagnosticTest[] = [
      { name: 'API Connectivity', status: 'pending' },
      { name: 'Hardware Detection', status: 'pending' },
      { name: 'Driver Compatibility', status: 'pending' },
      { name: 'Network Connectivity', status: 'pending' },
      { name: 'WebSocket Connection', status: 'pending' },
      { name: 'Sample Rate Test', status: 'pending' },
      { name: 'Channel Configuration', status: 'pending' },
    ];
    
    setDiagnosticTests(tests);
    
    for (let i = 0; i < tests.length; i++) {
      if (!componentMountedRef.current) return;
      
      const test = tests[i];
      const startTime = Date.now();
      
      // Update test status to running
      setDiagnosticTests(prev => prev.map((t, index) => 
        index === i ? { ...t, status: 'running' } : t
      ));
      
      try {
        let result = '';
        
        switch (test.name) {
          case 'API Connectivity':
            try {
              await apiService.get('/health', { timeout: 5000 });
              result = 'API server is responding';
            } catch {
              // Try alternative endpoints
              try {
                const response = await fetch('http://localhost:8000/health', { signal: AbortSignal.timeout(5000) });
                if (response.ok) {
                  result = 'Simple detection service is responding';
                } else {
                  throw new Error('API servers not responding');
                }
              } catch {
                throw new Error('No API services are responding - check if backend is running');
              }
            }
            break;
            
          case 'Hardware Detection':
            try {
              const discoveryResult = await apiService.post('/api/labjack/discover', { timeout: 5000 });
              const typedResult = discoveryResult as { devices_found?: number };
              result = `Found ${typedResult.devices_found || 0} device(s)`;
            } catch {
              throw new Error('Hardware detection unavailable - LabJack service not running');
            }
            break;
            
          case 'Driver Compatibility':
            if (navigator.platform.toLowerCase().includes('win')) {
              // Windows-specific driver check
              try {
                const driverCheck = await apiService.get('/api/labjack/windows-driver-info') as { supported: boolean };
                result = driverCheck.supported ? 'Compatible drivers found' : 'Driver issues detected';
                if (!driverCheck.supported) {
                  throw new Error('Incompatible or missing drivers');
                }
              } catch {
                result = 'Driver check unavailable - backend service not running';
              }
            } else {
              result = 'Non-Windows platform - drivers not required';
            }
            break;
            
          case 'Network Connectivity':
            if (status?.mode === 'bridge') {
              try {
                const bridgeTest = await apiService.get(`/api/labjack/bridge-test`) as { latency: number };
                result = `Bridge latency: ${bridgeTest.latency}ms`;
              } catch {
                result = 'Bridge test unavailable - backend service not running';
              }
            } else {
              result = 'Network test skipped - not in bridge mode';
            }
            break;
            
          case 'WebSocket Connection':
            // Test WebSocket connectivity
            const wsTestPromise = new Promise((resolve, reject) => {
              const testWs = new WebSocket(
                (process.env.REACT_APP_WS_URL?.replace('http', 'ws') || 'ws://localhost:8000') + '/ws/test'
              );
              
              const timeout = setTimeout(() => {
                testWs.close();
                reject(new Error('WebSocket connection timeout'));
              }, 5000);
              
              testWs.onopen = () => {
                clearTimeout(timeout);
                testWs.close();
                resolve('WebSocket connection successful');
              };
              
              testWs.onerror = () => {
                clearTimeout(timeout);
                reject(new Error('WebSocket connection failed'));
              };
            });
            
            result = await wsTestPromise as string;
            break;
            
          case 'Sample Rate Test':
            const currentRate = status?.sample_rate || 1000;
            if (currentRate > 50000) {
              throw new Error('Sample rate too high for stable operation');
            }
            result = `Sample rate ${currentRate} Hz is within safe limits`;
            break;
            
          case 'Channel Configuration':
            const channels = status?.channels || [];
            if (channels.length === 0) {
              throw new Error('No channels configured');
            }
            result = `${channels.length} channel(s) configured: ${channels.join(', ')}`;
            break;
            
          default:
            throw new Error('Unknown test');
        }
        
        // Test passed
        setDiagnosticTests(prev => prev.map((t, index) => 
          index === i ? { 
            ...t, 
            status: 'passed', 
            result,
            duration: Date.now() - startTime 
          } : t
        ));
        
        labjackLogger.logDiagnosticTest(test.name, 'passed', { result }, Date.now() - startTime);
        
      } catch (error: unknown) {
        // Test failed
        const errorMessage = (error as Error).message || 'Unknown error';
        setDiagnosticTests(prev => prev.map((t, index) => 
          index === i ? { 
            ...t, 
            status: 'failed', 
            error: errorMessage,
            duration: Date.now() - startTime 
          } : t
        ));
      }
      
      // Small delay between tests
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }, [status?.sample_rate, status?.channels, status?.mode]);
  
  // Check Windows driver compatibility
  const checkWindowsDrivers = useCallback(async () => {
    if (!navigator.platform.toLowerCase().includes('win')) return;
    
    try {
      const driverInfo = await apiService.get<WindowsDriverInfo>('/api/labjack/windows-driver-info');
      setWindowsDriverInfo(driverInfo);
      
      if (!driverInfo.supported) {
        showSnackbar('Windows driver issues detected - check diagnostics', 'warning');
      }
    } catch (error) {
      console.error('Failed to check Windows drivers:', error);
    }
  }, []);
  
  // Load initial status and setup polling
  useEffect(() => {
    componentMountedRef.current = true;
    
    // Initial load
    loadStatus();
    checkWindowsDrivers();
    
    // Setup periodic status updates with adaptive polling
    const setupPolling = () => {
      if (statusPollingRef.current) {
        clearInterval(statusPollingRef.current);
      }
      
      // Adaptive polling - faster when connected and streaming
      const pollInterval = status?.streaming ? 2000 : 10000;
      
      statusPollingRef.current = setInterval(() => {
        if (componentMountedRef.current) {
          loadStatus(true); // Silent polling
        }
      }, pollInterval);
    };
    
    setupPolling();
    
    return () => {
      componentMountedRef.current = false;
      
      if (statusPollingRef.current) {
        clearInterval(statusPollingRef.current);
      }
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      if (discoveryTimeoutRef.current) {
        clearTimeout(discoveryTimeoutRef.current);
      }
    };
  }, [loadStatus, checkWindowsDrivers, status?.streaming]);

  // Helper functions
  const getStatusIcon = (connectionStatus: ConnectionStatus, mode: ConnectionMode) => {
    if (connectionStatus === 'connecting') {
      return <CircularProgress size={20} />;
    }
    
    switch (mode) {
      case 'bridge':
        return connectionStatus === 'connected' ? <CloudIcon color="success" /> : <WifiOffIcon color="error" />;
      case 'direct':
        return connectionStatus === 'connected' ? <UsbIcon color="success" /> : <UsbIcon color="error" />;
      case 'mock':
        return connectionStatus === 'connected' ? <ComputerIcon color="warning" /> : <ComputerIcon color="error" />;
      default:
        return <ErrorIcon color="error" />;
    }
  };

  const getStatusColor = (connectionStatus: ConnectionStatus): 'success' | 'error' | 'warning' | 'default' => {
    switch (connectionStatus) {
      case 'connected': return 'success';
      case 'error': return 'error';
      case 'connecting':
      case 'retrying': return 'warning';
      default: return 'default';
    }
  };

  const getModeLabel = (mode: ConnectionMode): string => {
    switch (mode) {
      case 'bridge': return 'Bridge';
      case 'direct': return 'Direct';
      case 'mock': return 'Mock';
      default: return 'Unknown';
    }
  };

  const formatUptime = (uptimeStart: string): string => {
    const start = new Date(uptimeStart);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    
    if (diffHours > 0) {
      return `${diffHours}h ${diffMins % 60}m`;
    }
    return `${diffMins}m`;
  };

  if (!status && loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" p={2}>
            <CircularProgress />
            <Typography variant="body1" sx={{ ml: 2 }}>
              Loading LabJack status...
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardContent>
          {/* Header */}
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6" component="div">
              LabJack Status
            </Typography>
            <Box>
              <Tooltip title="Refresh Status">
                <IconButton onClick={() => {
                  loadStatus().catch(error => {
                    console.error('Error refreshing status:', error);
                  });
                }} disabled={loading}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Settings">
                <IconButton onClick={() => setSettingsOpen(true)}>
                  <SettingsIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Diagnostics">
                <IconButton onClick={() => setDiagnosticsOpen(true)}>
                  <BugReportIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          {/* Error Alert */}
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {status && (
            <>
              {/* Enhanced Connection Status */}
              <Grid container spacing={2} alignItems="center" mb={2}>
                <Grid item xs={12} sm={8}>
                  <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                    {getStatusIcon(status.status, status.mode)}
                    <Typography variant="body1">
                      <strong>{getModeLabel(status.mode)} Mode</strong>
                    </Typography>
                    <Chip 
                      label={status.status.toUpperCase()}
                      color={getStatusColor(status.status)}
                      size="small"
                    />
                    {recoveryMode && (
                      <Chip 
                        icon={<AutorenewIcon />}
                        label="RECOVERY"
                        color="warning"
                        size="small"
                        variant="outlined"
                      />
                    )}
                    {retryCount > 0 && (
                      <Chip 
                        label={`RETRY ${retryCount}/${retryConfig.maxRetries}`}
                        color="info"
                        size="small"
                        variant="outlined"
                      />
                    )}
                  </Box>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <Box display="flex" gap={1} flexWrap="wrap">
                    {status.connected ? (
                      <Button
                        variant="outlined"
                        color="error"
                        onClick={() => {
                          handleDisconnect().catch(error => {
                            console.error('Error disconnecting:', error);
                          });
                        }}
                        disabled={loading || recoveryMode}
                        size="small"
                        startIcon={<WifiOffIcon />}
                      >
                        Disconnect
                      </Button>
                    ) : (
                      <>
                        <Button
                          variant="contained"
                          onClick={() => {
                          handleConnect().catch(error => {
                            console.error('Error connecting:', error);
                          });
                        }}
                          disabled={loading || isDiscovering}
                          size="small"
                          startIcon={loading ? <CircularProgress size={16} /> : <WifiIcon />}
                        >
                          {recoveryMode ? 'Recovering...' : 'Connect'}
                        </Button>
                        <Button
                          variant="outlined"
                          onClick={() => {
                            handleDeviceDiscovery().catch(error => {
                              console.error('Error discovering devices:', error);
                            });
                          }}
                          disabled={loading || isDiscovering}
                          size="small"
                          startIcon={isDiscovering ? <CircularProgress size={16} /> : <SearchIcon />}
                        >
                          Discover
                        </Button>
                      </>
                    )}
                  </Box>
                </Grid>
              </Grid>
              
              {/* Windows Driver Warning */}
              {windowsDriverInfo && !windowsDriverInfo.supported && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  <AlertTitle>Windows Driver Issue</AlertTitle>
                  {windowsDriverInfo.recommendations?.map((rec, index) => (
                    <Typography key={index} variant="body2">• {rec}</Typography>
                  )) || 'LabJack drivers may need to be installed or updated for optimal performance.'}
                </Alert>
              )}
              
              {/* Connection History Chip */}
              {connectionHistory.length > 0 && (
                <Box mb={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    Recent Connection Attempts
                  </Typography>
                  <Box display="flex" gap={0.5} flexWrap="wrap">
                    {connectionHistory.slice(0, 5).map((attempt, index) => (
                      <Tooltip key={index} title={`${new Date(attempt.timestamp).toLocaleTimeString()}: ${attempt.success ? 'Success' : attempt.error}`}>
                        <Chip
                          size="small"
                          label={`${getModeLabel(attempt.mode)}${attempt.latency ? ` (${attempt.latency}ms)` : ''}`}
                          color={attempt.success ? 'success' : 'error'}
                          variant="outlined"
                        />
                      </Tooltip>
                    ))}
                  </Box>
                </Box>
              )}

              {/* Device Information */}
              {status.connected && (
                <Box mb={2}>
                  <Typography variant="subtitle2" gutterBottom>
                    Device Information
                  </Typography>
                  <Grid container spacing={2}>
                    {status.device_info.device_type && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Device: {status.device_info.device_type}
                        </Typography>
                      </Grid>
                    )}
                    {status.device_info.serial_number && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          S/N: {status.device_info.serial_number}
                        </Typography>
                      </Grid>
                    )}
                    {status.device_info.bridge_host && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Bridge: {status.device_info.bridge_host}:{status.device_info.bridge_port}
                        </Typography>
                      </Grid>
                    )}
                    {connectionLatency !== null && (
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Latency: {connectionLatency}ms
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </Box>
              )}

              {/* Streaming Status */}
              <Box mb={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                  <Typography variant="subtitle2">
                    Data Streaming
                  </Typography>
                  {status.connected && (
                    <Button
                      variant={status.streaming ? "outlined" : "contained"}
                      color={status.streaming ? "error" : "primary"}
                      size="small"
                      onClick={() => {
                        handleToggleStreaming().catch(error => {
                          console.error('Error toggling streaming:', error);
                        });
                      }}
                      disabled={loading}
                      startIcon={status.streaming ? <ErrorIcon /> : <TimelineIcon />}
                    >
                      {status.streaming ? 'Stop' : 'Start'} Stream
                    </Button>
                  )}
                </Box>
                
                {status.streaming && (
                  <Box>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        Rate: {status.sample_rate} Hz • Channels: {status.channels.join(', ')}
                      </Typography>
                      <Chip 
                        label={`${dataRate} samples/s`}
                        size="small"
                        icon={<SpeedIcon />}
                        color="primary"
                      />
                    </Box>
                    
                    {/* Simple data visualization */}
                    <Box sx={{ height: 60, bgcolor: 'grey.50', borderRadius: 1, p: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Live Data ({streamingData.length} samples buffered)
                      </Typography>
                      <Box sx={{ mt: 1, height: 20, bgcolor: 'grey.200', borderRadius: 1, overflow: 'hidden' }}>
                        {streamingData.length > 0 && (
                          <LinearProgress 
                            variant="determinate" 
                            value={Math.min(100, streamingData.length)} 
                            sx={{ height: '100%' }}
                          />
                        )}
                      </Box>
                    </Box>
                  </Box>
                )}
              </Box>

              {/* Enhanced Statistics */}
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <AnalyticsIcon />
                    <Typography variant="subtitle2">
                      Statistics & Performance
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Grid container spacing={2}>
                    <Grid item xs={6} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Samples Received
                      </Typography>
                      <Typography variant="h6">
                        {status.statistics.samples_received.toLocaleString()}
                      </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Error Count
                      </Typography>
                      <Typography variant="h6" color={status.statistics.errors_count > 0 ? 'error.main' : 'text.primary'}>
                        {status.statistics.errors_count}
                      </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Success Rate
                      </Typography>
                      <Typography variant="h6" color="success.main">
                        {status.statistics.connection_attempts > 0 
                          ? Math.round((status.statistics.successful_connections || 0) / status.statistics.connection_attempts * 100)
                          : 100}%
                      </Typography>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Typography variant="body2" color="text.secondary">
                        Uptime
                      </Typography>
                      <Typography variant="h6">
                        {formatUptime(status.statistics.uptime_start)}
                      </Typography>
                    </Grid>
                    {connectionLatency !== null && (
                      <Grid item xs={6} md={3}>
                        <Typography variant="body2" color="text.secondary">
                          Latency
                        </Typography>
                        <Typography variant="h6" color={connectionLatency > 100 ? 'warning.main' : 'success.main'}>
                          {connectionLatency}ms
                        </Typography>
                      </Grid>
                    )}
                    {status.statistics.recovery_attempts > 0 && (
                      <Grid item xs={6} md={3}>
                        <Typography variant="body2" color="text.secondary">
                          Recovery Attempts
                        </Typography>
                        <Typography variant="h6">
                          {status.statistics.recovery_attempts}
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </AccordionDetails>
              </Accordion>
            </>
          )}
        </CardContent>
      </Card>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>LabJack Settings</DialogTitle>
        <DialogContent>
          <FormControlLabel
            control={
              <Switch
                checked={autoReconnect}
                onChange={(e) => setAutoReconnect(e.target.checked)}
              />
            }
            label="Auto-reconnect WebSocket"
          />
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="subtitle2" gutterBottom>
            Force Connection Mode
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            <Button
              variant="outlined"
              startIcon={<CloudIcon />}
              onClick={() => {
                handleConnect('bridge').catch(error => {
                  console.error('Error connecting in bridge mode:', error);
                });
                setSettingsOpen(false);
              }}
              disabled={loading}
            >
              Bridge Mode
            </Button>
            <Button
              variant="outlined"
              startIcon={<UsbIcon />}
              onClick={() => {
                handleConnect('direct').catch(error => {
                  console.error('Error connecting in direct mode:', error);
                });
                setSettingsOpen(false);
              }}
              disabled={loading}
            >
              Direct Mode
            </Button>
            <Button
              variant="outlined"
              startIcon={<ComputerIcon />}
              onClick={() => {
                handleConnect('mock').catch(error => {
                  console.error('Error connecting in mock mode:', error);
                });
                setSettingsOpen(false);
              }}
              disabled={loading}
            >
              Mock Mode
            </Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Enhanced Diagnostics Dialog */}
      <Dialog open={diagnosticsOpen} onClose={() => setDiagnosticsOpen(false)} maxWidth="lg" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <BugReportIcon />
            LabJack Comprehensive Diagnostics
          </Box>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 3 }}>
            <Button 
              variant="contained" 
              onClick={() => {
                runDiagnosticTests().catch(error => {
                  console.error('Error running diagnostic tests:', error);
                });
              }}
              startIcon={<PlayArrowIcon />}
              disabled={diagnosticTests.some(t => t.status === 'running')}
              sx={{ mr: 1 }}
            >
              Run Full Diagnostic
            </Button>
            <Button 
              variant="outlined" 
              onClick={() => {
                loadStatus().catch(error => {
                  console.error('Error refreshing status in diagnostics:', error);
                });
              }}
              startIcon={<RefreshIcon />}
            >
              Refresh Status
            </Button>
          </Box>
          
          {/* Diagnostic Tests Results */}
          {diagnosticTests.length > 0 && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Diagnostic Test Results
              </Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Test</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Result</TableCell>
                      <TableCell>Duration</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {diagnosticTests.map((test, index) => (
                      <TableRow key={index}>
                        <TableCell>{test.name}</TableCell>
                        <TableCell>
                          <Chip 
                            size="small"
                            label={test.status.toUpperCase()}
                            color={
                              test.status === 'passed' ? 'success' :
                              test.status === 'failed' ? 'error' :
                              test.status === 'running' ? 'info' : 'default'
                            }
                            icon={
                              test.status === 'running' ? <CircularProgress size={16} /> : undefined
                            }
                          />
                        </TableCell>
                        <TableCell>
                          {test.result || test.error || '-'}
                        </TableCell>
                        <TableCell>
                          {test.duration ? `${test.duration}ms` : '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}
          
          {/* System Information */}
          {status && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                System Information
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <InfoIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Connection Mode"
                        secondary={`${getModeLabel(status.mode)} (${status.status})`}
                      />
                    </ListItem>
                    
                    <ListItem>
                      <ListItemIcon>
                        <ComputerIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Device Type"
                        secondary={status.device_info.device_type || 'Unknown'}
                      />
                    </ListItem>
                    
                    {status.device_info.serial_number && (
                      <ListItem>
                        <ListItemIcon>
                          <InfoIcon />
                        </ListItemIcon>
                        <ListItemText
                          primary="Serial Number"
                          secondary={status.device_info.serial_number}
                        />
                      </ListItem>
                    )}
                    
                    <ListItem>
                      <ListItemIcon>
                        <MemoryIcon />
                      </ListItemIcon>
                      <ListItemText
                        primary="Sample Buffer"
                        secondary={`${streamingData.length} samples buffered`}
                      />
                    </ListItem>
                  </List>
                </Grid>
                
                <Grid item xs={12} md={6}>
                  <List dense>
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color={wsConnection ? "success" : "error"} />
                      </ListItemIcon>
                      <ListItemText
                        primary="WebSocket Connection"
                        secondary={wsConnection ? "Connected" : "Disconnected"}
                      />
                    </ListItem>
                    
                    {status.bridge_health && (
                      <ListItem>
                        <ListItemIcon>
                          <RouterIcon />
                        </ListItemIcon>
                        <ListItemText
                          primary="Bridge Health"
                          secondary={status.bridge_health}
                        />
                      </ListItem>
                    )}
                    
                    {status.error_message && (
                      <ListItem>
                        <ListItemIcon>
                          <ErrorIcon color="error" />
                        </ListItemIcon>
                        <ListItemText
                          primary="Last Error"
                          secondary={status.error_message}
                        />
                      </ListItem>
                    )}
                    
                    {windowsDriverInfo && (
                      <ListItem>
                        <ListItemIcon>
                          <PowerIcon color={windowsDriverInfo.supported ? "success" : "warning"} />
                        </ListItemIcon>
                        <ListItemText
                          primary="Windows Drivers"
                          secondary={windowsDriverInfo.supported ? 'Compatible' : 'Issues detected'}
                        />
                      </ListItem>
                    )}
                  </List>
                </Grid>
              </Grid>
            </Box>
          )}
          
          {/* Connection History */}
          {connectionHistory.length > 0 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Connection History
              </Typography>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Time</TableCell>
                      <TableCell>Mode</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Latency</TableCell>
                      <TableCell>Error</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {connectionHistory.map((attempt, index) => (
                      <TableRow key={index}>
                        <TableCell>{new Date(attempt.timestamp).toLocaleTimeString()}</TableCell>
                        <TableCell>{getModeLabel(attempt.mode)}</TableCell>
                        <TableCell>
                          <Chip 
                            size="small"
                            label={attempt.success ? 'SUCCESS' : 'FAILED'}
                            color={attempt.success ? 'success' : 'error'}
                          />
                        </TableCell>
                        <TableCell>{attempt.latency ? `${attempt.latency}ms` : '-'}</TableCell>
                        <TableCell>{attempt.error || '-'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDiagnosticsOpen(false)}>Close</Button>
          <Button onClick={() => {
            runDiagnosticTests().catch(error => {
              console.error('Error running diagnostic tests from dialog:', error);
            });
          }} startIcon={<BugReportIcon />}>
            Run Tests
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={() => setSnackbarOpen(false)} severity={snackbarSeverity}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </>
  );
};

export default LabJackStatusPanel;