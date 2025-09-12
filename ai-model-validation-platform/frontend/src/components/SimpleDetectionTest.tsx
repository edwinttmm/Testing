/**
 * Simple Detection Test Component
 * 
 * Test component for validating the new simple-detection endpoints
 * Provides UI to test all endpoint functionality
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Alert,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Grid,
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Analytics as AnalyticsIcon,
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';

import {
  simpleDetectionService,
  StartDetectionResponse,
  StopDetectionResponse,
  DetectionStatusResponse,
  AnalyzeDetectionResponse,
  DetectionSessionsResponse,
} from '../services/simpleDetectionService';

interface TestResult {
  endpoint: string;
  success: boolean;
  data?: any;
  error?: string;
  duration?: number;
}

const SimpleDetectionTest: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>('');
  const [tolerance, setTolerance] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<DetectionStatusResponse | null>(null);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [sessions, setSessions] = useState<DetectionSessionsResponse | null>(null);
  const [serviceAvailable, setServiceAvailable] = useState<boolean | null>(null);

  // Generate initial session ID
  useEffect(() => {
    setSessionId(simpleDetectionService.generateSessionId('test'));
  }, []);

  // Check service availability on mount
  useEffect(() => {
    checkServiceAvailability();
  }, []);

  const checkServiceAvailability = async () => {
    try {
      const result = await simpleDetectionService.checkServiceAvailability();
      setServiceAvailable(result.available);
      if (!result.available) {
        setError(result.message);
      } else {
        setSuccess(result.message);
      }
    } catch (err) {
      setServiceAvailable(false);
      setError('Failed to check service availability');
    }
  };

  const addTestResult = (endpoint: string, success: boolean, data?: any, error?: string, duration?: number) => {
    const result: TestResult = {
      endpoint,
      success,
      data,
      error,
      duration,
    };
    setTestResults(prev => [result, ...prev.slice(0, 9)]); // Keep last 10 results
  };

  const handleStartDetection = async () => {
    if (!sessionId.trim()) {
      setError('Please enter a session ID');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);
    const startTime = Date.now();

    try {
      const response = await simpleDetectionService.startDetection({
        session_id: sessionId,
        tolerance_ms: tolerance,
        project_id: 'test_project',
        video_id: 'test_video',
      });

      const duration = Date.now() - startTime;
      addTestResult('POST /start', true, response, undefined, duration);
      setSuccess(`Detection started: ${response.message}`);
      
      // Refresh status after starting
      setTimeout(getDetectionStatus, 500);
      
    } catch (err: any) {
      const duration = Date.now() - startTime;
      addTestResult('POST /start', false, undefined, err.message, duration);
      setError(`Failed to start detection: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStopDetection = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    const startTime = Date.now();

    try {
      const response = await simpleDetectionService.stopDetection();
      const duration = Date.now() - startTime;
      addTestResult('POST /stop', true, response, undefined, duration);
      setSuccess(`Detection stopped: ${response.total_detections} events collected`);
      
      // Refresh status after stopping
      setTimeout(getDetectionStatus, 500);
      
    } catch (err: any) {
      const duration = Date.now() - startTime;
      addTestResult('POST /stop', false, undefined, err.message, duration);
      setError(`Failed to stop detection: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getDetectionStatus = async () => {
    const startTime = Date.now();
    
    try {
      const response = await simpleDetectionService.getDetectionStatus();
      const duration = Date.now() - startTime;
      setStatus(response);
      addTestResult('GET /status', true, response, undefined, duration);
    } catch (err: any) {
      const duration = Date.now() - startTime;
      addTestResult('GET /status', false, undefined, err.message, duration);
      setError(`Failed to get status: ${err.message}`);
    }
  };

  const handleAnalyzeDetection = async () => {
    if (!sessionId.trim()) {
      setError('Please enter a session ID to analyze');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);
    const startTime = Date.now();

    try {
      const videoEvents = simpleDetectionService.createSampleVideoEvents();
      const response = await simpleDetectionService.analyzeDetection(sessionId, {
        video_events: videoEvents,
        save_to_database: true,
      });

      const duration = Date.now() - startTime;
      addTestResult('POST /analyze', true, response, undefined, duration);
      setSuccess(`Analysis completed: ${response.accuracy_percentage.toFixed(1)}% accuracy`);
      
    } catch (err: any) {
      const duration = Date.now() - startTime;
      addTestResult('POST /analyze', false, undefined, err.message, duration);
      setError(`Failed to analyze detection: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleListSessions = async () => {
    setLoading(true);
    const startTime = Date.now();

    try {
      const response = await simpleDetectionService.listDetectionSessions({
        limit: 10,
        offset: 0,
      });

      const duration = Date.now() - startTime;
      setSessions(response);
      addTestResult('GET /sessions', true, response, undefined, duration);
      setSuccess(`Found ${response.total} detection sessions`);
      
    } catch (err: any) {
      const duration = Date.now() - startTime;
      addTestResult('GET /sessions', false, undefined, err.message, duration);
      setError(`Failed to list sessions: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const runFullTest = async () => {
    setTestResults([]);
    setError(null);
    setSuccess(null);
    
    // Generate new session ID for test
    const testSessionId = simpleDetectionService.generateSessionId('full_test');
    setSessionId(testSessionId);
    
    try {
      setSuccess('Running full endpoint test...');
      
      // Step 1: Check service availability
      await checkServiceAvailability();
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Step 2: Get initial status
      await getDetectionStatus();
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Step 3: Start detection
      await simpleDetectionService.startDetection({
        session_id: testSessionId,
        tolerance_ms: 100,
      });
      addTestResult('Full Test - Start', true);
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Step 4: Check status while running
      await getDetectionStatus();
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Step 5: Stop detection
      const stopResponse = await simpleDetectionService.stopDetection();
      addTestResult('Full Test - Stop', true, stopResponse);
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Step 6: Analyze results
      const videoEvents = simpleDetectionService.createSampleVideoEvents();
      await simpleDetectionService.analyzeDetection(testSessionId, {
        video_events: videoEvents,
        save_to_database: true,
      });
      addTestResult('Full Test - Analyze', true);
      
      // Step 7: List sessions
      await handleListSessions();
      
      setSuccess('Full test completed successfully! All endpoints are working.');
      
    } catch (err: any) {
      addTestResult('Full Test - Error', false, undefined, err.message);
      setError(`Full test failed: ${err.message}`);
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Simple Detection API Test Panel
        </Typography>

        {/* Service Status */}
        <Box mb={2}>
          <Alert 
            severity={serviceAvailable === null ? 'info' : serviceAvailable ? 'success' : 'error'}
            icon={serviceAvailable === null ? <CircularProgress size={20} /> : serviceAvailable ? <CheckCircleIcon /> : <ErrorIcon />}
          >
            {serviceAvailable === null ? 'Checking service availability...' :
             serviceAvailable ? 'Simple detection service is available' :
             'Simple detection service is not available'}
          </Alert>
        </Box>

        {/* Error/Success Messages */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        {/* Controls */}
        <Grid container spacing={2} mb={3}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="Session ID"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              size="small"
              disabled={loading}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <TextField
              fullWidth
              label="Tolerance (ms)"
              type="number"
              value={tolerance}
              onChange={(e) => setTolerance(Number(e.target.value))}
              size="small"
              disabled={loading}
            />
          </Grid>
          <Grid item xs={12} md={3}>
            <Button
              fullWidth
              variant="outlined"
              onClick={() => setSessionId(simpleDetectionService.generateSessionId('test'))}
              disabled={loading}
              size="small"
            >
              New Session ID
            </Button>
          </Grid>
        </Grid>

        {/* Action Buttons */}
        <Box display="flex" gap={1} flexWrap="wrap" mb={3}>
          <Button
            variant="contained"
            color="success"
            startIcon={loading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
            onClick={handleStartDetection}
            disabled={loading || !serviceAvailable}
          >
            Start Detection
          </Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<StopIcon />}
            onClick={handleStopDetection}
            disabled={loading || !serviceAvailable}
          >
            Stop Detection
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={getDetectionStatus}
            disabled={loading || !serviceAvailable}
          >
            Get Status
          </Button>
          <Button
            variant="outlined"
            startIcon={<AnalyticsIcon />}
            onClick={handleAnalyzeDetection}
            disabled={loading || !serviceAvailable}
          >
            Analyze Session
          </Button>
          <Button
            variant="outlined"
            onClick={handleListSessions}
            disabled={loading || !serviceAvailable}
          >
            List Sessions
          </Button>
          <Button
            variant="contained"
            color="primary"
            onClick={runFullTest}
            disabled={loading || !serviceAvailable}
          >
            Run Full Test
          </Button>
        </Box>

        {/* Current Status */}
        {status && (
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">
                Current Detection Status
                <Chip 
                  label={status.running ? 'RUNNING' : 'STOPPED'} 
                  color={status.running ? 'success' : 'default'} 
                  size="small" 
                  sx={{ ml: 1 }}
                />
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Running"
                    secondary={status.running ? 'Yes' : 'No'}
                  />
                </ListItem>
                {status.session_id && (
                  <ListItem>
                    <ListItemText
                      primary="Session ID"
                      secondary={status.session_id}
                    />
                  </ListItem>
                )}
                {status.duration_seconds && (
                  <ListItem>
                    <ListItemText
                      primary="Duration"
                      secondary={`${status.duration_seconds.toFixed(1)}s`}
                    />
                  </ListItem>
                )}
                {status.events_collected !== undefined && (
                  <ListItem>
                    <ListItemText
                      primary="Events Collected"
                      secondary={status.events_collected}
                    />
                  </ListItem>
                )}
                {status.tolerance_ms && (
                  <ListItem>
                    <ListItemText
                      primary="Tolerance"
                      secondary={`${status.tolerance_ms}ms`}
                    />
                  </ListItem>
                )}
                <ListItem>
                  <ListItemText
                    primary="Message"
                    secondary={status.message}
                  />
                </ListItem>
              </List>
            </AccordionDetails>
          </Accordion>
        )}

        {/* Sessions List */}
        {sessions && sessions.sessions.length > 0 && (
          <Accordion sx={{ mt: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">
                Detection Sessions ({sessions.total} total)
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Session ID</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell>Detections</TableCell>
                      <TableCell>Accuracy</TableCell>
                      <TableCell>Created</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sessions.sessions.map((session) => (
                      <TableRow key={session.id}>
                        <TableCell>{session.session_id}</TableCell>
                        <TableCell>
                          <Chip 
                            label={session.status.toUpperCase()} 
                            color={session.status === 'completed' ? 'success' : session.status === 'active' ? 'info' : 'default'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          {session.duration_seconds ? `${session.duration_seconds.toFixed(1)}s` : '-'}
                        </TableCell>
                        <TableCell>{session.total_detections || 0}</TableCell>
                        <TableCell>
                          {session.accuracy_percentage ? `${session.accuracy_percentage.toFixed(1)}%` : '-'}
                        </TableCell>
                        <TableCell>
                          {session.created_at ? new Date(session.created_at).toLocaleString() : '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </AccordionDetails>
          </Accordion>
        )}

        {/* Test Results */}
        {testResults.length > 0 && (
          <Accordion sx={{ mt: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">
                Recent Test Results ({testResults.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List>
                {testResults.map((result, index) => (
                  <React.Fragment key={index}>
                    <ListItem>
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Chip
                              icon={result.success ? <CheckCircleIcon /> : <ErrorIcon />}
                              label={result.success ? 'SUCCESS' : 'ERROR'}
                              color={result.success ? 'success' : 'error'}
                              size="small"
                            />
                            <Typography variant="body2">
                              {result.endpoint}
                            </Typography>
                            {result.duration && (
                              <Chip
                                label={`${result.duration}ms`}
                                size="small"
                                variant="outlined"
                              />
                            )}
                          </Box>
                        }
                        secondary={result.error || (result.success ? 'Request completed successfully' : undefined)}
                      />
                    </ListItem>
                    {index < testResults.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        )}
      </CardContent>
    </Card>
  );
};

export default SimpleDetectionTest;