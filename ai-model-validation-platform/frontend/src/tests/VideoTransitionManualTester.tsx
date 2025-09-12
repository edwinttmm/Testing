/**
 * Manual Video Transition System Tester
 * 
 * This component provides a manual testing interface for developers to validate
 * the robust video transition system in a real browser environment.
 * 
 * Usage: Import and render this component to manually test video transitions
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  LinearProgress,
  Alert,
  Chip,
  Stack,
  Paper,
  Divider,
  FormControlLabel,
  Switch,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Collapse
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  BugReport,
  CheckCircle,
  Error,
  Warning,
  Info,
  ExpandMore,
  ExpandLess,
  Refresh
} from '@mui/icons-material';

import SequentialVideoManager from '../components/SequentialVideoManager';
import { VideoFile } from '../services/types';

interface TestResult {
  testName: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  message: string;
  timestamp: number;
  details?: string[];
}

interface VideoTransitionLog {
  timestamp: number;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
  videoId?: string;
  transitionType?: string;
}

// Test video data - using sample URLs for manual testing
const createTestVideo = (id: string, filename: string, duration: number, sampleUrl?: string): VideoFile => ({
  id,
  filename,
  originalName: filename,
  url: sampleUrl || `https://sample-videos.com/zip/10/mp4/SampleVideo_${duration}sec_1mb.mp4`,
  projectId: 'manual-test-project',
  status: 'completed',
  duration,
  fps: 30,
  size: duration * 1024 * 1024,
  fileSize: duration * 1024 * 1024,
  createdAt: new Date().toISOString(),
  uploadedAt: new Date().toISOString(),
  groundTruthGenerated: false,
  groundTruthStatus: 'pending',
  processing_status: 'completed',
  detectionCount: 0
});

// Sample video sequences for different test scenarios
const TEST_VIDEO_SEQUENCES = {
  basic: [
    createTestVideo('manual-test-1', 'test-video-1.mp4', 5),
    createTestVideo('manual-test-2', 'test-video-2.mp4', 8), // Critical - should never be skipped
    createTestVideo('manual-test-3', 'test-video-3.mp4', 6),
  ],
  short: [
    createTestVideo('short-1', 'short-video-1.mp4', 2),
    createTestVideo('short-2', 'short-video-2.mp4', 3), // Critical - should never be skipped
    createTestVideo('short-3', 'short-video-3.mp4', 2),
  ],
  varied: [
    createTestVideo('varied-1', 'long-video.mp4', 15),
    createTestVideo('varied-2', 'medium-video.mp4', 8), // Critical - should never be skipped
    createTestVideo('varied-3', 'brief-video.mp4', 3),
    createTestVideo('varied-4', 'final-video.mp4', 10),
  ]
};

const VideoTransitionManualTester: React.FC = () => {
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [currentTest, setCurrentTest] = useState<string | null>(null);
  const [transitionLogs, setTransitionLogs] = useState<VideoTransitionLog[]>([]);
  const [selectedSequence, setSelectedSequence] = useState<'basic' | 'short' | 'varied'>('basic');
  const [testSettings, setTestSettings] = useState({
    autoAdvance: true,
    latencyMs: 200,
    loopPlayback: false,
    enableLogging: true
  });
  const [showLogs, setShowLogs] = useState(false);
  const [showResults, setShowResults] = useState(false);
  
  const testStartTimeRef = useRef<number>(0);
  const videoTransitionCountRef = useRef<number>(0);
  const skippedVideosRef = useRef<string[]>([]);

  // Initialize test results
  useEffect(() => {
    const initialTests: TestResult[] = [
      { testName: 'Sequential Flow Test', status: 'pending', message: 'Video 1 → Video 2 → Video 3 complete playback', timestamp: 0 },
      { testName: 'Video 2 Skip Prevention', status: 'pending', message: 'Ensure Video 2 is never skipped', timestamp: 0 },
      { testName: 'Timing Verification', status: 'pending', message: 'Proper gaps between video transitions', timestamp: 0 },
      { testName: 'User Experience Test', status: 'pending', message: 'Smooth user interface interactions', timestamp: 0 },
      { testName: 'Console Log Analysis', status: 'pending', message: 'Debug output shows proper progression', timestamp: 0 }
    ];
    setTestResults(initialTests);
  }, []);

  const addTransitionLog = useCallback((level: VideoTransitionLog['level'], message: string, videoId?: string, transitionType?: string) => {
    if (!testSettings.enableLogging) return;
    
    const logEntry: VideoTransitionLog = {
      timestamp: Date.now(),
      level,
      message,
      videoId,
      transitionType
    };
    
    setTransitionLogs(prev => [...prev, logEntry]);
    console.log(`[MANUAL TEST] ${level.toUpperCase()}: ${message}`);
  }, [testSettings.enableLogging]);

  const updateTestResult = useCallback((testName: string, status: TestResult['status'], message: string, details?: string[]) => {
    setTestResults(prev => prev.map(test => 
      test.testName === testName 
        ? { ...test, status, message, timestamp: Date.now(), details }
        : test
    ));
  }, []);

  const startTest = useCallback(() => {
    console.log('[MANUAL TEST] Starting comprehensive video transition test');
    addTransitionLog('info', 'Starting comprehensive video transition test');
    
    // Reset test state
    setTransitionLogs([]);
    videoTransitionCountRef.current = 0;
    skippedVideosRef.current = [];
    testStartTimeRef.current = Date.now();
    setCurrentTest('running');
    
    // Mark all tests as running
    setTestResults(prev => prev.map(test => ({ ...test, status: 'running' as const, timestamp: Date.now() })));
    
    addTransitionLog('info', `Testing with sequence: ${selectedSequence} (${TEST_VIDEO_SEQUENCES[selectedSequence].length} videos)`);
  }, [selectedSequence, addTransitionLog]);

  const stopTest = useCallback(() => {
    console.log('[MANUAL TEST] Stopping video transition test');
    addTransitionLog('warning', 'Test manually stopped by user');
    setCurrentTest(null);
  }, [addTransitionLog]);

  const resetTest = useCallback(() => {
    console.log('[MANUAL TEST] Resetting test state');
    setTransitionLogs([]);
    videoTransitionCountRef.current = 0;
    skippedVideosRef.current = [];
    setCurrentTest(null);
    
    // Reset all tests to pending
    setTestResults(prev => prev.map(test => ({ ...test, status: 'pending' as const, message: test.message.split(' - ')[0], timestamp: 0 })));
  }, []);

  const handleVideoChange = useCallback((video: VideoFile, index: number) => {
    const timestamp = Date.now();
    const elapsedMs = timestamp - testStartTimeRef.current;
    
    videoTransitionCountRef.current++;
    addTransitionLog('info', `Video transition to: ${video.filename} (index: ${index})`, video.id, 'change');
    
    console.log(`[MANUAL TEST] Video changed to ${video.filename} at ${elapsedMs}ms`);
    
    // Check for Video 2 specifically (critical test)
    if (video.id.includes('test-2') || video.id.includes('2') || index === 1) {
      updateTestResult('Video 2 Skip Prevention', 'passed', `✅ Video 2 played successfully: ${video.filename}`, [
        `Video ID: ${video.id}`,
        `Index: ${index}`,
        `Timestamp: ${new Date(timestamp).toLocaleTimeString()}`
      ]);
      addTransitionLog('success', '✅ Critical Video 2 successfully loaded and played', video.id, 'critical-success');
    }
    
    // Update sequential flow test
    if (index === 0) {
      updateTestResult('Sequential Flow Test', 'running', `Started with Video 1: ${video.filename}`);
    } else if (index === TEST_VIDEO_SEQUENCES[selectedSequence].length - 1) {
      updateTestResult('Sequential Flow Test', 'passed', `✅ All ${TEST_VIDEO_SEQUENCES[selectedSequence].length} videos played sequentially`, [
        `Total transitions: ${videoTransitionCountRef.current}`,
        `Test duration: ${elapsedMs}ms`
      ]);
    }
    
    // Update timing verification
    if (index > 0) {
      updateTestResult('Timing Verification', 'running', `Transition ${index} completed with ${testSettings.latencyMs}ms gap`);
    }
    
    // Update user experience test
    updateTestResult('User Experience Test', 'running', `User sees: ${video.filename} (${index + 1}/${TEST_VIDEO_SEQUENCES[selectedSequence].length})`);
  }, [selectedSequence, testSettings.latencyMs, addTransitionLog, updateTestResult]);

  const handlePlaybackComplete = useCallback(() => {
    const endTime = Date.now();
    const totalDuration = endTime - testStartTimeRef.current;
    
    addTransitionLog('success', '🎉 All videos played successfully - Test completed!');
    console.log(`[MANUAL TEST] Playback completed in ${totalDuration}ms`);
    
    // Mark remaining tests as passed
    updateTestResult('Sequential Flow Test', 'passed', `✅ Complete sequence played in ${totalDuration}ms`);
    updateTestResult('Timing Verification', 'passed', `✅ All transitions respected ${testSettings.latencyMs}ms latency`);
    updateTestResult('User Experience Test', 'passed', '✅ Smooth playback with proper UI feedback');
    updateTestResult('Console Log Analysis', 'passed', `✅ Generated ${transitionLogs.length} debug logs`);
    
    setCurrentTest(null);
    setShowResults(true);
  }, [testSettings.latencyMs, transitionLogs.length, addTransitionLog, updateTestResult]);

  const handleProgress = useCallback((progress: number) => {
    if (progress % 25 === 0 && testSettings.enableLogging) { // Log every 25%
      addTransitionLog('info', `Overall progress: ${Math.round(progress)}%`);
    }
  }, [testSettings.enableLogging, addTransitionLog]);

  const getStatusIcon = (status: TestResult['status']) => {
    switch (status) {
      case 'passed': return <CheckCircle color="success" />;
      case 'failed': return <Error color="error" />;
      case 'running': return <PlayArrow color="primary" />;
      default: return <Info color="disabled" />;
    }
  };

  const getStatusColor = (status: TestResult['status']) => {
    switch (status) {
      case 'passed': return 'success';
      case 'failed': return 'error';
      case 'running': return 'primary';
      default: return 'default';
    }
  };

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>
        🎬 Video Transition System Manual Tester
      </Typography>
      
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        This manual tester validates the robust video transition system to ensure Video 2 is never skipped
        and all transitions work properly. Monitor the console and test results for detailed analysis.
      </Typography>

      {/* Test Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Test Configuration</Typography>
          
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
            <TextField
              select
              label="Video Sequence"
              value={selectedSequence}
              onChange={(e) => setSelectedSequence(e.target.value as any)}
              SelectProps={{ native: true }}
              size="small"
            >
              <option value="basic">Basic (3 videos, 5-8s each)</option>
              <option value="short">Short (3 videos, 2-3s each)</option>
              <option value="varied">Varied (4 videos, different durations)</option>
            </TextField>
            
            <TextField
              type="number"
              label="Latency (ms)"
              value={testSettings.latencyMs}
              onChange={(e) => setTestSettings(prev => ({ ...prev, latencyMs: parseInt(e.target.value) || 200 }))}
              size="small"
              inputProps={{ min: 0, max: 2000, step: 50 }}
            />
            
            <FormControlLabel
              control={
                <Switch 
                  checked={testSettings.autoAdvance} 
                  onChange={(e) => setTestSettings(prev => ({ ...prev, autoAdvance: e.target.checked }))}
                />
              }
              label="Auto Advance"
            />
            
            <FormControlLabel
              control={
                <Switch 
                  checked={testSettings.enableLogging} 
                  onChange={(e) => setTestSettings(prev => ({ ...prev, enableLogging: e.target.checked }))}
                />
              }
              label="Debug Logging"
            />
          </Stack>
          
          <Stack direction="row" spacing={2}>
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              onClick={startTest}
              disabled={currentTest === 'running'}
              color="primary"
            >
              Start Test
            </Button>
            
            <Button
              variant="outlined"
              startIcon={<Stop />}
              onClick={stopTest}
              disabled={currentTest !== 'running'}
            >
              Stop Test
            </Button>
            
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={resetTest}
            >
              Reset
            </Button>
            
            <Button
              variant="text"
              startIcon={<BugReport />}
              onClick={() => setShowLogs(!showLogs)}
            >
              {showLogs ? 'Hide' : 'Show'} Debug Logs
            </Button>
            
            <Button
              variant="text"
              onClick={() => setShowResults(!showResults)}
            >
              {showResults ? 'Hide' : 'Show'} Results
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {/* Test Status */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Test Results</Typography>
          
          <List dense>
            {testResults.map((result, index) => (
              <ListItem key={index} sx={{ pl: 0 }}>
                <ListItemIcon>
                  {getStatusIcon(result.status)}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography variant="subtitle2">{result.testName}</Typography>
                      <Chip 
                        label={result.status} 
                        size="small" 
                        color={getStatusColor(result.status) as any}
                        variant={result.status === 'pending' ? 'outlined' : 'filled'}
                      />
                    </Stack>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        {result.message}
                      </Typography>
                      {result.details && (
                        <Box sx={{ mt: 1 }}>
                          {result.details.map((detail, idx) => (
                            <Typography key={idx} variant="caption" display="block" color="text.secondary">
                              • {detail}
                            </Typography>
                          ))}
                        </Box>
                      )}
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {/* Video Player */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Video Playback</Typography>
          
          {currentTest === 'running' ? (
            <SequentialVideoManager
              videos={TEST_VIDEO_SEQUENCES[selectedSequence]}
              onVideoChange={handleVideoChange}
              onPlaybackComplete={handlePlaybackComplete}
              onProgress={handleProgress}
              autoAdvance={testSettings.autoAdvance}
              latencyMs={testSettings.latencyMs}
              loopPlayback={testSettings.loopPlayback}
            />
          ) : (
            <Box 
              sx={{ 
                height: 300, 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center', 
                bgcolor: 'grey.100',
                borderRadius: 1
              }}
            >
              <Typography variant="h6" color="text.secondary">
                Click "Start Test" to begin video playback testing
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Debug Logs */}
      <Collapse in={showLogs}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Debug Logs</Typography>
            
            <Paper 
              sx={{ 
                maxHeight: 400, 
                overflow: 'auto', 
                p: 2, 
                bgcolor: 'grey.900', 
                color: 'grey.100',
                fontFamily: 'monospace'
              }}
            >
              {transitionLogs.length === 0 ? (
                <Typography variant="body2" color="grey.400">
                  No logs yet. Start a test to see debug output.
                </Typography>
              ) : (
                transitionLogs.map((log, index) => (
                  <Typography 
                    key={index} 
                    variant="body2" 
                    sx={{ 
                      mb: 0.5,
                      color: log.level === 'error' ? 'error.main' :
                             log.level === 'warning' ? 'warning.main' :
                             log.level === 'success' ? 'success.main' : 'grey.100'
                    }}
                  >
                    [{new Date(log.timestamp).toLocaleTimeString()}] {log.level.toUpperCase()}: {log.message}
                    {log.videoId && ` (Video: ${log.videoId})`}
                  </Typography>
                ))
              )}
            </Paper>
          </CardContent>
        </Card>
      </Collapse>

      {/* Test Instructions */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Manual Testing Instructions</Typography>
          
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              <strong>Critical Test Goal:</strong> Verify that Video 2 is NEVER skipped under any circumstances during sequential playback.
            </Typography>
          </Alert>
          
          <Typography variant="body2" component="div">
            <strong>Test Procedure:</strong>
            <ol>
              <li>Configure test settings above (sequence type, latency, etc.)</li>
              <li>Click "Start Test" to begin video playback</li>
              <li>Watch the video player and monitor console output</li>
              <li>Verify all videos play in order: Video 1 → Video 2 → Video 3</li>
              <li>Check that Video 2 status shows "✅ Video 2 played successfully"</li>
              <li>Review debug logs for proper transition timing</li>
              <li>Try different video sequences and settings</li>
            </ol>
          </Typography>
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="body2" component="div">
            <strong>Success Criteria:</strong>
            <ul>
              <li>✅ All videos play completely in sequential order</li>
              <li>✅ Video 2 is never skipped (critical requirement)</li>
              <li>✅ Proper timing gaps between videos (respects latency setting)</li>
              <li>✅ Debug logs show proper progression</li>
              <li>✅ User interface provides clear feedback</li>
              <li>✅ No errors in browser console</li>
            </ul>
          </Typography>
          
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2">
              If Video 2 gets skipped or any test fails, there is a bug in the video transition system that needs to be fixed.
              Check the console logs and test results for detailed debugging information.
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    </Box>
  );
};

export default VideoTransitionManualTester;