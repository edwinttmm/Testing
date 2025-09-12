/**
 * Video Compatibility Panel Component
 * 
 * Interactive component for testing and displaying video compatibility:
 * - Real-time format testing
 * - Compatibility matrix display
 * - Browser capability detection
 * - Debug tools integration
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Chip,
  Alert,
  LinearProgress,
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
  TextField,
  FormGroup,
  FormControlLabel,
  Switch,
  Divider
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Assessment as AssessmentIcon
} from '@mui/icons-material';

import {
  videoCompatibilityChecker,
  VideoCompatibilityResult,
  VideoCompatibilityMatrix,
  VideoTestResult,
  performCompatibilityCheck,
  testVideoPlayback,
  getBrowserCapabilities
} from '../utils/videoCompatibilityChecker';

import {
  videoDebugTools,
  startDebugSession,
  generateCompatibilityMatrix,
  generateSessionReport,
  VideoDebugSession
} from '../utils/videoDebugTools';

interface VideoCompatibilityPanelProps {
  videoUrl?: string;
  filename?: string;
  onCompatibilityResult?: (result: VideoCompatibilityResult) => void;
  showDebugTools?: boolean;
  autoTest?: boolean;
}

const VideoCompatibilityPanel: React.FC<VideoCompatibilityPanelProps> = ({
  videoUrl,
  filename,
  onCompatibilityResult,
  showDebugTools = true,
  autoTest = false
}) => {
  const [compatibilityResult, setCompatibilityResult] = useState<VideoCompatibilityResult | null>(null);
  const [testResults, setTestResults] = useState<VideoTestResult[]>([]);
  const [debugSession, setDebugSession] = useState<VideoDebugSession | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [browserCapabilities, setBrowserCapabilities] = useState<any>(null);
  const [compatibilityMatrix, setCompatibilityMatrix] = useState<VideoCompatibilityMatrix[]>([]);
  const [testUrl, setTestUrl] = useState(videoUrl || '');
  const [testFilename, setTestFilename] = useState(filename || '');
  const [enableRealtimeMonitoring, setEnableRealtimeMonitoring] = useState(false);
  const [monitoringCleanup, setMonitoringCleanup] = useState<(() => void) | null>(null);

  // Initialize on mount
  useEffect(() => {
    const capabilities = getBrowserCapabilities();
    setBrowserCapabilities(capabilities);
    setCompatibilityMatrix(videoCompatibilityChecker.getCompatibilityMatrix());

    if (autoTest && videoUrl && filename) {
      handleCompatibilityCheck();
    }
  }, [videoUrl, filename, autoTest]);

  // Cleanup monitoring and video resources on unmount
  useEffect(() => {
    return () => {
      if (monitoringCleanup) {
        monitoringCleanup();
      }
      // Cleanup video resources when component unmounts
      videoCompatibilityChecker.cleanup();
    };
  }, [monitoringCleanup]);

  /**
   * Perform compatibility check
   */
  const handleCompatibilityCheck = async () => {
    if (!testUrl || !testFilename) {
      setError('Please provide both URL and filename');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await performCompatibilityCheck(testUrl, testFilename);
      setCompatibilityResult(result);
      onCompatibilityResult?.(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Test video playback
   */
  const handleVideoTest = async () => {
    if (!testUrl) {
      setError('Please provide a video URL');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await testVideoPlayback(testUrl);
      setTestResults([result]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Test multiple formats
   */
  const handleMultiFormatTest = async () => {
    if (!testUrl) {
      setError('Please provide a base video URL');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const formats = ['mp4', 'webm', 'ogg', 'm4v'];
      const results = await videoCompatibilityChecker.testMultipleFormats(testUrl, formats);
      setTestResults(results);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Start debug session
   */
  const handleStartDebugSession = () => {
    const sessionId = startDebugSession();
    // Note: In a real implementation, you'd get the session data
    // For now, we'll create a mock session
    setDebugSession({
      id: sessionId,
      startTime: Date.now(),
      browser: browserCapabilities?.browser || {
        name: 'unknown',
        version: 'unknown',
        engine: 'unknown',
        platform: 'unknown',
        mobile: false
      },
      tests: [],
      errors: [],
      performance: {
        totalTests: 0,
        successfulTests: 0,
        failedTests: 0,
        averageLoadTime: 0,
        slowestLoadTime: 0,
        fastestLoadTime: Infinity,
        formatPerformance: {}
      }
    });
  };

  /**
   * Stop debug session
   */
  const handleStopDebugSession = () => {
    if (debugSession) {
      videoDebugTools.clearSession(debugSession.id);
      setDebugSession(null);
    }
  };

  /**
   * Get status icon for compatibility
   */
  const getStatusIcon = (status: 'supported' | 'partial' | 'unsupported') => {
    switch (status) {
      case 'supported':
        return <CheckCircleIcon color="success" />;
      case 'partial':
        return <WarningIcon color="warning" />;
      case 'unsupported':
        return <ErrorIcon color="error" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  /**
   * Get status color
   */
  const getStatusColor = (status: 'supported' | 'partial' | 'unsupported') => {
    switch (status) {
      case 'supported':
        return 'success';
      case 'partial':
        return 'warning';
      case 'unsupported':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <Box sx={{ width: '100%', maxWidth: 1200, mx: 'auto', p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Video Compatibility Checker
      </Typography>

      {/* Test Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Configuration
          </Typography>
          
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Video URL"
                value={testUrl}
                onChange={(e) => setTestUrl(e.target.value)}
                placeholder="https://example.com/video.mp4"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label="Filename"
                value={testFilename}
                onChange={(e) => setTestFilename(e.target.value)}
                placeholder="video.mp4"
              />
            </Grid>
          </Grid>

          <Grid container spacing={2} alignItems="center">
            <Grid item>
              <Button
                variant="contained"
                onClick={handleCompatibilityCheck}
                disabled={isLoading || !testUrl || !testFilename}
                startIcon={<AssessmentIcon />}
              >
                Check Compatibility
              </Button>
            </Grid>
            <Grid item>
              <Button
                variant="outlined"
                onClick={handleVideoTest}
                disabled={isLoading || !testUrl}
                startIcon={<PlayArrowIcon />}
              >
                Test Playback
              </Button>
            </Grid>
            <Grid item>
              <Button
                variant="outlined"
                onClick={handleMultiFormatTest}
                disabled={isLoading || !testUrl}
              >
                Test Multiple Formats
              </Button>
            </Grid>
          </Grid>

          {showDebugTools && (
            <>
              <Divider sx={{ my: 2 }} />
              <FormGroup>
                <FormControlLabel
                  control={
                    <Switch
                      checked={enableRealtimeMonitoring}
                      onChange={(e) => setEnableRealtimeMonitoring(e.target.checked)}
                    />
                  }
                  label="Enable Real-time Monitoring"
                />
              </FormGroup>
              
              <Box sx={{ mt: 2 }}>
                {!debugSession ? (
                  <Button variant="outlined" onClick={handleStartDebugSession}>
                    Start Debug Session
                  </Button>
                ) : (
                  <Button 
                    variant="outlined" 
                    onClick={handleStopDebugSession}
                    startIcon={<StopIcon />}
                    color="secondary"
                  >
                    Stop Debug Session ({debugSession.id})
                  </Button>
                )}
              </Box>
            </>
          )}
        </CardContent>
      </Card>

      {/* Loading indicator */}
      {isLoading && (
        <Box sx={{ width: '100%', mb: 2 }}>
          <LinearProgress />
        </Box>
      )}

      {/* Error display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Browser Capabilities */}
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Browser Capabilities</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {browserCapabilities ? (
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  Browser Information
                </Typography>
                <Typography variant="body2">
                  <strong>Name:</strong> {browserCapabilities.browser.name} {browserCapabilities.browser.version}
                </Typography>
                <Typography variant="body2">
                  <strong>Engine:</strong> {browserCapabilities.browser.engine}
                </Typography>
                <Typography variant="body2">
                  <strong>Platform:</strong> {browserCapabilities.browser.platform}
                </Typography>
                <Typography variant="body2">
                  <strong>Mobile:</strong> {browserCapabilities.browser.mobile ? 'Yes' : 'No'}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1" gutterBottom>
                  Format Support
                </Typography>
                {Object.entries(browserCapabilities.formats).map(([format, support]) => (
                  <Chip
                    key={format}
                    label={`${format.toUpperCase()}: ${support}`}
                    color={support === 'full' ? 'success' : support === 'partial' ? 'warning' : 'error'}
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                  />
                ))}
              </Grid>

              <Grid item xs={12}>
                <Typography variant="subtitle1" gutterBottom>
                  Codec Support
                </Typography>
                {Object.entries(browserCapabilities.codecs).map(([codec, supported]) => (
                  <Chip
                    key={codec}
                    label={`${codec.toUpperCase()}: ${supported ? 'Supported' : 'Not Supported'}`}
                    color={supported ? 'success' : 'error'}
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                  />
                ))}
              </Grid>
            </Grid>
          ) : (
            <Typography>Loading browser capabilities...</Typography>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Compatibility Results */}
      {compatibilityResult && (
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">Compatibility Results</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Alert 
              severity={compatibilityResult.isCompatible ? 'success' : 'warning'} 
              sx={{ mb: 2 }}
            >
              {compatibilityResult.isCompatible 
                ? 'Video format is compatible with your browser!' 
                : 'Video format may have compatibility issues.'}
            </Alert>

            {compatibilityResult.primaryFormat && (
              <Typography variant="body1" sx={{ mb: 2 }}>
                <strong>Primary Format:</strong> {compatibilityResult.primaryFormat.toUpperCase()}
              </Typography>
            )}

            {compatibilityResult.fallbackFormats.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Recommended Fallback Formats:
                </Typography>
                {compatibilityResult.fallbackFormats.map(format => (
                  <Chip key={format} label={format.toUpperCase()} sx={{ mr: 1 }} />
                ))}
              </Box>
            )}

            {compatibilityResult.recommendations.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  Recommendations:
                </Typography>
                {compatibilityResult.recommendations.map((rec, index) => (
                  <Typography key={index} variant="body2" sx={{ mb: 1 }}>
                    • {rec}
                  </Typography>
                ))}
              </Box>
            )}

            {compatibilityResult.unsupportedReasons.length > 0 && (
              <Box>
                <Typography variant="subtitle1" gutterBottom>
                  Issues Found:
                </Typography>
                {compatibilityResult.unsupportedReasons.map((reason, index) => (
                  <Alert key={index} severity="error" sx={{ mb: 1 }}>
                    {reason}
                  </Alert>
                ))}
              </Box>
            )}
          </AccordionDetails>
        </Accordion>
      )}

      {/* Test Results */}
      {testResults.length > 0 && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">Test Results</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Format</TableCell>
                    <TableCell>Can Load</TableCell>
                    <TableCell>Can Play</TableCell>
                    <TableCell>Load Time</TableCell>
                    <TableCell>Error</TableCell>
                    <TableCell>Metadata</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {testResults.map((result, index) => (
                    <TableRow key={index}>
                      <TableCell>{result.format.toUpperCase()}</TableCell>
                      <TableCell>
                        {result.canLoad ? (
                          <CheckCircleIcon color="success" />
                        ) : (
                          <ErrorIcon color="error" />
                        )}
                      </TableCell>
                      <TableCell>
                        {result.canPlay ? (
                          <CheckCircleIcon color="success" />
                        ) : (
                          <ErrorIcon color="error" />
                        )}
                      </TableCell>
                      <TableCell>
                        {result.loadTime ? `${Math.round(result.loadTime)}ms` : '-'}
                      </TableCell>
                      <TableCell>
                        {result.error || '-'}
                      </TableCell>
                      <TableCell>
                        {result.metadata ? (
                          <Box>
                            {result.metadata.dimensions && (
                              <Typography variant="caption" display="block">
                                {result.metadata.dimensions.width}x{result.metadata.dimensions.height}
                              </Typography>
                            )}
                            {result.metadata.duration && (
                              <Typography variant="caption" display="block">
                                {Math.round(result.metadata.duration)}s
                              </Typography>
                            )}
                          </Box>
                        ) : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      )}

      {/* Compatibility Matrix */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="h6">Format Compatibility Matrix</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Format</TableCell>
                  <TableCell align="center">Chrome</TableCell>
                  <TableCell align="center">Firefox</TableCell>
                  <TableCell align="center">Safari</TableCell>
                  <TableCell align="center">Edge</TableCell>
                  <TableCell>Codecs</TableCell>
                  <TableCell>Recommendation</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {compatibilityMatrix.map((entry) => (
                  <TableRow key={entry.format}>
                    <TableCell>
                      <strong>{entry.format.toUpperCase()}</strong>
                    </TableCell>
                    <TableCell align="center">
                      {getStatusIcon(entry.browsers.chrome)}
                    </TableCell>
                    <TableCell align="center">
                      {getStatusIcon(entry.browsers.firefox)}
                    </TableCell>
                    <TableCell align="center">
                      {getStatusIcon(entry.browsers.safari)}
                    </TableCell>
                    <TableCell align="center">
                      {getStatusIcon(entry.browsers.edge)}
                    </TableCell>
                    <TableCell>
                      {entry.codecs.join(', ')}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={entry.recommendation}
                        color={getStatusColor(
                          entry.recommendation === 'primary' ? 'supported' :
                          entry.recommendation === 'fallback' ? 'partial' : 'unsupported'
                        )}
                        size="small"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          
          {compatibilityMatrix.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" display="block">
                <CheckCircleIcon fontSize="small" color="success" sx={{ mr: 1 }} />
                Fully Supported
              </Typography>
              <Typography variant="caption" display="block">
                <WarningIcon fontSize="small" color="warning" sx={{ mr: 1 }} />
                Partial Support
              </Typography>
              <Typography variant="caption" display="block">
                <ErrorIcon fontSize="small" color="error" sx={{ mr: 1 }} />
                Not Supported
              </Typography>
            </Box>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Debug Session Info */}
      {debugSession && showDebugTools && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">Debug Session</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" gutterBottom>
              <strong>Session ID:</strong> {debugSession.id}
            </Typography>
            <Typography variant="body2" gutterBottom>
              <strong>Started:</strong> {new Date(debugSession.startTime).toLocaleString()}
            </Typography>
            <Typography variant="body2" gutterBottom>
              <strong>Duration:</strong> {Math.round((Date.now() - debugSession.startTime) / 1000)}s
            </Typography>
            
            {debugSession.performance && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Performance Metrics
                </Typography>
                <Typography variant="body2">
                  Tests: {debugSession.performance.totalTests} | 
                  Success: {debugSession.performance.successfulTests} | 
                  Failed: {debugSession.performance.failedTests}
                </Typography>
                {debugSession.performance.averageLoadTime > 0 && (
                  <Typography variant="body2">
                    Average Load Time: {Math.round(debugSession.performance.averageLoadTime)}ms
                  </Typography>
                )}
              </Box>
            )}
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
};

export default VideoCompatibilityPanel;