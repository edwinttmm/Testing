/**
 * Video Test Validator Component
 * 
 * Comprehensive testing component to validate video DOM manipulation fixes:
 * - Tests video element creation and cleanup
 * - Validates memory management
 * - Checks sequential playback handling
 * - Tests error handling for failed video loads
 * - Monitors DOM pollution and resource leaks
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Alert,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Divider
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Delete as CleanupIcon,
  Assessment as StatsIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

import { 
  videoCompatibilityChecker, 
  testVideoPlayback,
  VideoTestResult
} from '../utils/videoCompatibilityChecker';
import { videoFullscreenManager } from '../utils/videoFullscreenManager';

interface TestResult {
  testName: string;
  status: 'success' | 'error' | 'warning';
  message: string;
  timestamp: Date;
  details?: any;
}

const VideoTestValidator: React.FC = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [videoManagerStats, setVideoManagerStats] = useState<{ activeElements: number; pendingCleanups: number } | null>(null);
  const [fullscreenCapabilities, setFullscreenCapabilities] = useState<any>(null);

  // Test URLs for validation
  const TEST_VIDEOS = {
    validMP4: 'https://sample-videos.com/zip/10/mp4/SampleVideo_640x360_1mb.mp4',
    validWebM: 'https://sample-videos.com/zip/10/webm/SampleVideo_640x360_1mb.webm',
    invalidURL: 'https://example.com/nonexistent-video.mp4',
    invalidFormat: 'https://example.com/test.xyz'
  };

  useEffect(() => {
    updateStats();
    updateFullscreenCapabilities();

    // Cleanup on unmount
    return () => {
      videoCompatibilityChecker.cleanup();
      videoFullscreenManager.cleanup();
    };
  }, []);

  const updateStats = () => {
    const stats = videoCompatibilityChecker.getVideoManagerStats();
    setVideoManagerStats(stats);
  };

  const updateFullscreenCapabilities = () => {
    const capabilities = videoFullscreenManager.getCapabilities();
    setFullscreenCapabilities(capabilities);
  };

  const addTestResult = (testName: string, status: 'success' | 'error' | 'warning', message: string, details?: any) => {
    const result: TestResult = {
      testName,
      status,
      message,
      timestamp: new Date(),
      details
    };
    setTestResults(prev => [...prev, result]);
  };

  /**
   * Test 1: Basic video element creation and cleanup
   */
  const testVideoElementLifecycle = async () => {
    addTestResult('Video Element Lifecycle', 'warning', 'Starting test...');
    
    try {
      const initialStats = videoCompatibilityChecker.getVideoManagerStats();
      
      // Create multiple video elements
      const results = await Promise.all([
        testVideoPlayback(TEST_VIDEOS.validMP4, 'mp4'),
        testVideoPlayback(TEST_VIDEOS.validWebM, 'webm'),
        testVideoPlayback(TEST_VIDEOS.invalidURL, 'mp4')
      ]);

      // Check stats during test
      const duringStats = videoCompatibilityChecker.getVideoManagerStats();
      
      // Wait for cleanup
      await new Promise(resolve => setTimeout(resolve, 200));
      
      const finalStats = videoCompatibilityChecker.getVideoManagerStats();
      
      const success = finalStats.activeElements <= initialStats.activeElements;
      
      addTestResult(
        'Video Element Lifecycle',
        success ? 'success' : 'error',
        success 
          ? 'Video elements created and cleaned up successfully'
          : `Memory leak detected: ${finalStats.activeElements} active elements remaining`,
        { initialStats, duringStats, finalStats, results }
      );
      
    } catch (error) {
      addTestResult('Video Element Lifecycle', 'error', `Test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  /**
   * Test 2: Sequential video loading
   */
  const testSequentialLoading = async () => {
    addTestResult('Sequential Loading', 'warning', 'Starting sequential test...');
    
    try {
      const testUrls = Object.values(TEST_VIDEOS);
      const results: VideoTestResult[] = [];
      
      for (const url of testUrls) {
        const result = await testVideoPlayback(url);
        results.push(result);
        
        // Small delay between tests
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Check for memory leaks between tests
        const stats = videoCompatibilityChecker.getVideoManagerStats();
        if (stats.activeElements > 2) { // Allow some buffer
          addTestResult('Sequential Loading', 'warning', `High element count during test: ${stats.activeElements}`);
        }
      }
      
      const finalStats = videoCompatibilityChecker.getVideoManagerStats();
      const success = finalStats.activeElements === 0;
      
      addTestResult(
        'Sequential Loading',
        success ? 'success' : 'warning',
        `Sequential loading completed. Final active elements: ${finalStats.activeElements}`,
        { results, finalStats }
      );
      
    } catch (error) {
      addTestResult('Sequential Loading', 'error', `Sequential test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  /**
   * Test 3: Error handling
   */
  const testErrorHandling = async () => {
    addTestResult('Error Handling', 'warning', 'Testing error scenarios...');
    
    try {
      const errorTests = [
        { url: TEST_VIDEOS.invalidURL, expected: 'Network error' },
        { url: TEST_VIDEOS.invalidFormat, expected: 'Format error' },
        { url: 'invalid-url', expected: 'URL error' }
      ];
      
      const results = [];
      
      for (const test of errorTests) {
        try {
          const result = await testVideoPlayback(test.url);
          results.push({ url: test.url, result, handled: !!result.error });
        } catch (error) {
          results.push({ url: test.url, error: error instanceof Error ? error.message : 'Unknown error', handled: true });
        }
      }
      
      const allHandled = results.every(r => r.handled);
      
      addTestResult(
        'Error Handling',
        allHandled ? 'success' : 'error',
        allHandled ? 'All errors handled properly' : 'Some errors not handled correctly',
        { results }
      );
      
    } catch (error) {
      addTestResult('Error Handling', 'error', `Error handling test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  /**
   * Test 4: Memory cleanup validation
   */
  const testMemoryCleanup = async () => {
    addTestResult('Memory Cleanup', 'warning', 'Testing memory cleanup...');
    
    try {
      const initialStats = videoCompatibilityChecker.getVideoManagerStats();
      
      // Create multiple videos simultaneously
      const promises = Array.from({ length: 5 }, (_, i) => 
        testVideoPlayback(TEST_VIDEOS.validMP4, 'mp4').catch(() => null)
      );
      
      await Promise.all(promises);
      
      // Force cleanup
      videoCompatibilityChecker.cleanup();
      
      // Wait for cleanup to complete
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const finalStats = videoCompatibilityChecker.getVideoManagerStats();
      
      const cleaned = finalStats.activeElements === 0 && finalStats.pendingCleanups === 0;
      
      addTestResult(
        'Memory Cleanup',
        cleaned ? 'success' : 'error',
        cleaned 
          ? 'Memory cleaned up successfully'
          : `Memory not cleaned: ${finalStats.activeElements} active, ${finalStats.pendingCleanups} pending`,
        { initialStats, finalStats }
      );
      
    } catch (error) {
      addTestResult('Memory Cleanup', 'error', `Memory cleanup test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  /**
   * Test 5: Fullscreen API integration
   */
  const testFullscreenIntegration = async () => {
    addTestResult('Fullscreen Integration', 'warning', 'Testing fullscreen capabilities...');
    
    try {
      const capabilities = videoFullscreenManager.getCapabilities();
      
      if (!capabilities.supported) {
        addTestResult('Fullscreen Integration', 'warning', 'Fullscreen not supported in this browser');
        return;
      }
      
      // Create a test video element
      const video = document.createElement('video');
      video.style.display = 'none';
      document.body.appendChild(video);
      
      try {
        // Test fullscreen request (will likely fail due to user gesture requirement)
        await videoFullscreenManager.requestFullscreen(video);
        addTestResult('Fullscreen Integration', 'success', 'Fullscreen API working correctly');
      } catch (error) {
        // Expected to fail without user gesture
        const isUserGestureError = error instanceof Error && 
          (error.message.includes('user gesture') || error.message.includes('user activation'));
        
        addTestResult(
          'Fullscreen Integration',
          isUserGestureError ? 'success' : 'error',
          isUserGestureError 
            ? 'Fullscreen API correctly requires user gesture'
            : `Fullscreen error: ${error instanceof Error ? error.message : 'Unknown error'}`
        );
      } finally {
        document.body.removeChild(video);
      }
      
    } catch (error) {
      addTestResult('Fullscreen Integration', 'error', `Fullscreen test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  /**
   * Run all tests
   */
  const runAllTests = async () => {
    setIsRunning(true);
    setTestResults([]);
    
    try {
      addTestResult('Test Suite', 'warning', 'Starting comprehensive video DOM tests...');
      
      await testVideoElementLifecycle();
      updateStats();
      
      await testSequentialLoading();
      updateStats();
      
      await testErrorHandling();
      updateStats();
      
      await testMemoryCleanup();
      updateStats();
      
      await testFullscreenIntegration();
      updateStats();
      updateFullscreenCapabilities();
      
      addTestResult('Test Suite', 'success', 'All tests completed successfully');
      
    } catch (error) {
      addTestResult('Test Suite', 'error', `Test suite failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsRunning(false);
    }
  };

  const clearResults = () => {
    setTestResults([]);
  };

  const forceCleanup = () => {
    videoCompatibilityChecker.cleanup();
    videoFullscreenManager.cleanup();
    updateStats();
    updateFullscreenCapabilities();
    addTestResult('Manual Cleanup', 'success', 'Manual cleanup executed');
  };

  const getStatusIcon = (status: 'success' | 'error' | 'warning') => {
    switch (status) {
      case 'success': return <SuccessIcon color="success" />;
      case 'error': return <ErrorIcon color="error" />;
      case 'warning': return <WarningIcon color="warning" />;
    }
  };

  const getStatusColor = (status: 'success' | 'error' | 'warning') => {
    switch (status) {
      case 'success': return 'success';
      case 'error': return 'error';
      case 'warning': return 'warning';
      default: return 'default';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Video DOM Manipulation Test Validator
      </Typography>
      
      <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 3 }}>
        Comprehensive testing of video element lifecycle, memory management, and DOM manipulation fixes
      </Typography>

      {/* Control Panel */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item>
              <Button
                variant="contained"
                startIcon={<PlayIcon />}
                onClick={runAllTests}
                disabled={isRunning}
                size="large"
              >
                Run All Tests
              </Button>
            </Grid>
            
            <Grid item>
              <Button
                variant="outlined"
                startIcon={<CleanupIcon />}
                onClick={forceCleanup}
                disabled={isRunning}
              >
                Force Cleanup
              </Button>
            </Grid>
            
            <Grid item>
              <Button
                variant="outlined"
                startIcon={<StopIcon />}
                onClick={clearResults}
                disabled={isRunning}
              >
                Clear Results
              </Button>
            </Grid>

            {isRunning && (
              <Grid item xs={12}>
                <LinearProgress sx={{ mt: 2 }} />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Running comprehensive DOM manipulation tests...
                </Typography>
              </Grid>
            )}
          </Grid>
        </CardContent>
      </Card>

      {/* Stats Panel */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <StatsIcon sx={{ mr: 1 }} />
                <Typography variant="h6">
                  Video Manager Stats
                </Typography>
              </Box>
              {videoManagerStats ? (
                <Box>
                  <Chip
                    label={`Active Elements: ${videoManagerStats.activeElements}`}
                    color={videoManagerStats.activeElements === 0 ? 'success' : 'warning'}
                    sx={{ mr: 1, mb: 1 }}
                  />
                  <Chip
                    label={`Pending Cleanups: ${videoManagerStats.pendingCleanups}`}
                    color={videoManagerStats.pendingCleanups === 0 ? 'success' : 'warning'}
                    sx={{ mr: 1, mb: 1 }}
                  />
                </Box>
              ) : (
                <Typography color="text.secondary">Loading stats...</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Fullscreen Capabilities
              </Typography>
              {fullscreenCapabilities ? (
                <Box>
                  <Chip
                    label={`Supported: ${fullscreenCapabilities.supported ? 'Yes' : 'No'}`}
                    color={fullscreenCapabilities.supported ? 'success' : 'error'}
                    sx={{ mr: 1, mb: 1 }}
                  />
                  <Chip
                    label={`Active: ${fullscreenCapabilities.isFullscreen ? 'Yes' : 'No'}`}
                    color="default"
                    sx={{ mr: 1, mb: 1 }}
                  />
                  <Chip
                    label={`API: ${fullscreenCapabilities.api || 'Unknown'}`}
                    color="default"
                    sx={{ mr: 1, mb: 1 }}
                  />
                </Box>
              ) : (
                <Typography color="text.secondary">Loading capabilities...</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Test Results */}
      {testResults.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Test Results
            </Typography>
            
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Status</TableCell>
                    <TableCell>Test Name</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell>Timestamp</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {testResults.map((result, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          {getStatusIcon(result.status)}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {result.testName}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {result.message}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {result.timestamp.toLocaleTimeString()}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            
            {/* Summary */}
            <Divider sx={{ my: 2 }} />
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip
                label={`Success: ${testResults.filter(r => r.status === 'success').length}`}
                color="success"
                size="small"
              />
              <Chip
                label={`Warnings: ${testResults.filter(r => r.status === 'warning').length}`}
                color="warning"
                size="small"
              />
              <Chip
                label={`Errors: ${testResults.filter(r => r.status === 'error').length}`}
                color="error"
                size="small"
              />
            </Box>
          </CardContent>
        </Card>
      )}

      {testResults.length === 0 && !isRunning && (
        <Alert severity="info">
          Click "Run All Tests" to validate video DOM manipulation fixes. 
          This will test element creation, cleanup, memory management, error handling, and fullscreen integration.
        </Alert>
      )}
    </Box>
  );
};

export default VideoTestValidator;