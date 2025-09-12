/**
 * Video Compatibility Dashboard
 * 
 * Complete integration of all video compatibility features:
 * - Real-time format testing and validation
 * - Browser compatibility matrix
 * - Debug tools and monitoring
 * - Accessibility testing
 * - Performance analysis
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  Button,
  Tabs,
  Tab,
  Alert,
  Chip,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Switch
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  Assessment as AssessmentIcon,
  Security as SecurityIcon,
  Speed as SpeedIcon,
  BugReport as BugReportIcon,
  GetApp as DownloadIcon,
  Visibility as VisibilityIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon
} from '@mui/icons-material';

import VideoCompatibilityPanel from './VideoCompatibilityPanel';
import VideoTestValidator from './VideoTestValidator';
import {
  getBrowserCapabilities,
  VideoCompatibilityResult,
  VideoTestResult
} from '../utils/videoCompatibilityChecker';
import {
  startDebugSession,
  generateCompatibilityMatrix,
  generateSessionReport,
  VideoDebugSession
} from '../utils/videoDebugTools';
import {
  testVideoAccessibility,
  VideoAccessibilityTestSuite,
  generateAccessibilityReport
} from '../utils/videoAccessibilityTester';
import { videoCompatibilityDemo } from '../scripts/video-compatibility-demo';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div hidden={value !== index}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const VideoCompatibilityDashboard: React.FC = () => {
  const [currentTab, setCurrentTab] = useState(0);
  const [browserCapabilities, setBrowserCapabilities] = useState<any>(null);
  const [compatibilityMatrix, setCompatibilityMatrix] = useState<string>('');
  const [debugSession, setDebugSession] = useState<VideoDebugSession | null>(null);
  const [isRunningDemo, setIsRunningDemo] = useState(false);
  const [testResults, setTestResults] = useState<VideoTestResult[]>([]);
  const [accessibilityResults, setAccessibilityResults] = useState<VideoAccessibilityTestSuite[]>([]);
  const [reportDialog, setReportDialog] = useState<{ open: boolean; title: string; content: string }>({
    open: false,
    title: '',
    content: ''
  });
  const [demoConfig, setDemoConfig] = useState({
    enableRealTimeMonitoring: true,
    testAllFormats: true,
    includeAccessibilityTests: true,
    generateReports: true
  });

  // Initialize dashboard
  useEffect(() => {
    initializeDashboard();
    
    // Cleanup function
    return () => {
      // Cleanup video resources when component unmounts
      try {
        const { videoCompatibilityChecker } = require('../utils/videoCompatibilityChecker');
        videoCompatibilityChecker.cleanup();
      } catch (error) {
        console.warn('Error during dashboard cleanup:', error);
      }
    };
  }, []);

  const initializeDashboard = async () => {
    try {
      // Get browser capabilities
      const capabilities = getBrowserCapabilities();
      setBrowserCapabilities(capabilities);

      // Generate compatibility matrix
      const matrix = generateCompatibilityMatrix();
      setCompatibilityMatrix(matrix);

    } catch (error) {
      console.error('Dashboard initialization failed:', error);
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const handleStartDemo = async () => {
    setIsRunningDemo(true);
    
    try {
      // Start debug session
      if (demoConfig.enableRealTimeMonitoring) {
        const sessionId = startDebugSession();
        // Note: In real implementation, would get session object
      }

      // Run demo
      await videoCompatibilityDemo.runDemo();
      
      // Generate final report
      if (demoConfig.generateReports) {
        const report = videoCompatibilityDemo.generateSummaryReport();
        setReportDialog({
          open: true,
          title: 'Demo Completion Report',
          content: report
        });
      }

    } catch (error) {
      console.error('Demo failed:', error);
    } finally {
      setIsRunningDemo(false);
    }
  };

  const handleStopDemo = () => {
    setIsRunningDemo(false);
    // Stop any running processes
  };

  const handleExportReport = (title: string, content: string) => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.toLowerCase().replace(/\s+/g, '-')}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getStatusIcon = (status: 'supported' | 'partial' | 'unsupported' | boolean) => {
    if (typeof status === 'boolean') {
      return status ? <CheckCircleIcon color="success" /> : <ErrorIcon color="error" />;
    }
    
    switch (status) {
      case 'supported':
        return <CheckCircleIcon color="success" />;
      case 'partial':
        return <WarningIcon color="warning" />;
      case 'unsupported':
        return <ErrorIcon color="error" />;
    }
  };

  const getStatusColor = (status: 'supported' | 'partial' | 'unsupported' | boolean) => {
    if (typeof status === 'boolean') {
      return status ? 'success' : 'error';
    }
    
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
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography variant="h3" gutterBottom align="center">
        Video Compatibility Dashboard
      </Typography>
      
      <Typography variant="subtitle1" align="center" color="text.secondary" sx={{ mb: 4 }}>
        Comprehensive video format testing and compatibility validation
      </Typography>

      {/* Quick Actions */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {!isRunningDemo ? (
                  <Button
                    variant="contained"
                    startIcon={<PlayArrowIcon />}
                    onClick={handleStartDemo}
                    color="primary"
                  >
                    Run Full Demo
                  </Button>
                ) : (
                  <Button
                    variant="outlined"
                    startIcon={<StopIcon />}
                    onClick={handleStopDemo}
                    color="secondary"
                  >
                    Stop Demo
                  </Button>
                )}
                
                <Button
                  variant="outlined"
                  startIcon={<AssessmentIcon />}
                  onClick={() => setReportDialog({
                    open: true,
                    title: 'Compatibility Matrix',
                    content: compatibilityMatrix
                  })}
                >
                  View Matrix
                </Button>
                
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  onClick={() => handleExportReport('Browser Capabilities', 
                    JSON.stringify(browserCapabilities, null, 2))}
                  disabled={!browserCapabilities}
                >
                  Export Data
                </Button>
              </Box>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Demo Configuration
              </Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={demoConfig.enableRealTimeMonitoring}
                    onChange={(e) => setDemoConfig(prev => ({
                      ...prev,
                      enableRealTimeMonitoring: e.target.checked
                    }))}
                  />
                }
                label="Real-time Monitoring"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={demoConfig.testAllFormats}
                    onChange={(e) => setDemoConfig(prev => ({
                      ...prev,
                      testAllFormats: e.target.checked
                    }))}
                  />
                }
                label="Test All Formats"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={demoConfig.includeAccessibilityTests}
                    onChange={(e) => setDemoConfig(prev => ({
                      ...prev,
                      includeAccessibilityTests: e.target.checked
                    }))}
                  />
                }
                label="Accessibility Tests"
              />
            </Grid>
          </Grid>
          
          {isRunningDemo && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" gutterBottom>
                Running comprehensive video compatibility demo...
              </Typography>
              <LinearProgress />
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={currentTab} onChange={handleTabChange}>
            <Tab label="Browser Capabilities" />
            <Tab label="Format Testing" />
            <Tab label="Accessibility Testing" />
            <Tab label="Debug Tools" />
            <Tab label="DOM Test Validator" />
            <Tab label="Reports" />
          </Tabs>
        </Box>

        {/* Browser Capabilities Tab */}
        <TabPanel value={currentTab} index={0}>
          {browserCapabilities ? (
            <Grid container spacing={3}>
              {/* Browser Info */}
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Browser Information
                    </Typography>
                    <List dense>
                      <ListItem>
                        <ListItemText 
                          primary="Name" 
                          secondary={`${browserCapabilities.browser.name} ${browserCapabilities.browser.version}`}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText 
                          primary="Engine" 
                          secondary={browserCapabilities.browser.engine}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText 
                          primary="Platform" 
                          secondary={browserCapabilities.browser.platform}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemIcon>
                          {getStatusIcon(browserCapabilities.browser.mobile as boolean)}
                        </ListItemIcon>
                        <ListItemText 
                          primary="Mobile Device"
                          secondary={browserCapabilities.browser.mobile ? 'Yes' : 'No'}
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>

              {/* Format Support */}
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Format Support
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {Object.entries(browserCapabilities.formats).map(([format, support]) => (
                        <Chip
                          key={format}
                          label={`${format.toUpperCase()}: ${support}`}
                          color={getStatusColor(support === 'full' ? 'supported' : 
                                               support === 'partial' ? 'partial' : 'unsupported')}
                          icon={getStatusIcon(support === 'full' ? 'supported' : 
                                            support === 'partial' ? 'partial' : 'unsupported')}
                          size="small"
                        />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* Codec Support */}
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Codec Support
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {Object.entries(browserCapabilities.codecs).map(([codec, supported]) => (
                        <Chip
                          key={codec}
                          label={codec.toUpperCase()}
                          color={getStatusColor(supported as boolean)}
                          icon={getStatusIcon(supported as boolean)}
                          size="small"
                        />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* Features */}
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Features
                    </Typography>
                    <List dense>
                      {Object.entries(browserCapabilities.features).map(([feature, support]) => (
                        <ListItem key={feature}>
                          <ListItemIcon>
                            {getStatusIcon(typeof support === 'boolean' ? (support as boolean) : ((support as string) === 'supported' ? 'supported' : 'unsupported'))}
                          </ListItemIcon>
                          <ListItemText 
                            primary={feature}
                            secondary={typeof support === 'string' ? support : (support ? 'Supported' : 'Not Supported')}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          ) : (
            <Alert severity="info">Loading browser capabilities...</Alert>
          )}
        </TabPanel>

        {/* Format Testing Tab */}
        <TabPanel value={currentTab} index={1}>
          <VideoCompatibilityPanel 
            showDebugTools={true}
            autoTest={false}
          />
        </TabPanel>

        {/* Accessibility Testing Tab */}
        <TabPanel value={currentTab} index={2}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Video Accessibility Testing
              </Typography>
              <Alert severity="info" sx={{ mb: 3 }}>
                Test video file accessibility, CORS policies, and security restrictions
              </Alert>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Quick Accessibility Tests
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    These tests verify video file accessibility using different HTTP methods
                  </Typography>
                  
                  {accessibilityResults.length > 0 && (
                    <Box sx={{ mt: 3 }}>
                      <Typography variant="subtitle1" gutterBottom>
                        Test Results
                      </Typography>
                      {accessibilityResults.map((result, index) => (
                        <Card key={index} variant="outlined" sx={{ mb: 2 }}>
                          <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                              {getStatusIcon(result.summary.overallAccessible)}
                              <Typography variant="subtitle2" sx={{ ml: 1 }}>
                                {result.url}
                              </Typography>
                            </Box>
                            <Typography variant="body2" color="text.secondary">
                              Best Method: {result.summary.bestMethod.toUpperCase()}
                            </Typography>
                            {result.summary.issues.length > 0 && (
                              <Alert severity="warning" sx={{ mt: 1 }}>
                                Issues: {result.summary.issues.join(', ')}
                              </Alert>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Debug Tools Tab */}
        <TabPanel value={currentTab} index={3}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Debug Tools & Monitoring
              </Typography>
              <Alert severity="info" sx={{ mb: 3 }}>
                Advanced debugging tools for video compatibility issues
              </Alert>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Debug Session
                  </Typography>
                  {debugSession ? (
                    <Box>
                      <Typography variant="body2">
                        <strong>Session ID:</strong> {debugSession.id}
                      </Typography>
                      <Typography variant="body2">
                        <strong>Started:</strong> {new Date(debugSession.startTime).toLocaleString()}
                      </Typography>
                      <Typography variant="body2">
                        <strong>Tests Run:</strong> {debugSession.performance.totalTests}
                      </Typography>
                      <Button 
                        variant="outlined" 
                        color="secondary" 
                        startIcon={<StopIcon />}
                        onClick={() => setDebugSession(null)}
                        sx={{ mt: 2 }}
                      >
                        Stop Session
                      </Button>
                    </Box>
                  ) : (
                    <Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        No active debug session
                      </Typography>
                      <Button 
                        variant="contained" 
                        startIcon={<BugReportIcon />}
                        onClick={() => {
                          const sessionId = startDebugSession();
                          // Mock session for demo
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
                        }}
                      >
                        Start Debug Session
                      </Button>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Performance Monitoring
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Monitor video loading and playback performance
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Chip 
                      icon={<SpeedIcon />} 
                      label="Load Time Tracking" 
                      color="primary" 
                      size="small"
                    />
                    <Chip 
                      icon={<AssessmentIcon />} 
                      label="Format Analysis" 
                      color="secondary" 
                      size="small"
                    />
                    <Chip 
                      icon={<SecurityIcon />} 
                      label="Security Checks" 
                      color="success" 
                      size="small"
                    />
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Real-time Event Monitoring
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Monitor video events in real-time for debugging purposes
                  </Typography>
                  <Alert severity="info" sx={{ mt: 2 }}>
                    Real-time monitoring will be activated when a video element is detected
                  </Alert>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>

        {/* DOM Test Validator Tab */}
        <TabPanel value={currentTab} index={4}>
          <VideoTestValidator />
        </TabPanel>

        {/* Reports Tab */}
        <TabPanel value={currentTab} index={5}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom>
                Reports & Documentation
              </Typography>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Compatibility Matrix
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Complete browser compatibility matrix for all video formats
                  </Typography>
                  <Button 
                    variant="outlined" 
                    startIcon={<VisibilityIcon />}
                    onClick={() => setReportDialog({
                      open: true,
                      title: 'Video Format Compatibility Matrix',
                      content: compatibilityMatrix
                    })}
                    fullWidth
                  >
                    View Report
                  </Button>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Browser Capabilities
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Detailed analysis of current browser's video capabilities
                  </Typography>
                  <Button 
                    variant="outlined" 
                    startIcon={<DownloadIcon />}
                    onClick={() => browserCapabilities && handleExportReport(
                      'Browser Capabilities Report',
                      JSON.stringify(browserCapabilities, null, 2)
                    )}
                    fullWidth
                    disabled={!browserCapabilities}
                  >
                    Export JSON
                  </Button>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    System Summary
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Complete system analysis and recommendations
                  </Typography>
                  <Button 
                    variant="outlined" 
                    startIcon={<AssessmentIcon />}
                    onClick={() => {
                      const report = videoCompatibilityDemo.generateSummaryReport();
                      setReportDialog({
                        open: true,
                        title: 'System Summary Report',
                        content: report
                      });
                    }}
                    fullWidth
                  >
                    Generate Report
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>
      </Card>

      {/* Report Dialog */}
      <Dialog 
        open={reportDialog.open} 
        onClose={() => setReportDialog({ open: false, title: '', content: '' })}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{reportDialog.title}</DialogTitle>
        <DialogContent>
          <TextField
            multiline
            fullWidth
            value={reportDialog.content}
            variant="outlined"
            sx={{ fontFamily: 'monospace' }}
            rows={20}
            InputProps={{
              readOnly: true,
              sx: { fontSize: '0.875rem' }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReportDialog({ open: false, title: '', content: '' })}>
            Close
          </Button>
          <Button 
            variant="contained" 
            startIcon={<DownloadIcon />}
            onClick={() => {
              handleExportReport(reportDialog.title, reportDialog.content);
              setReportDialog({ open: false, title: '', content: '' });
            }}
          >
            Export
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default VideoCompatibilityDashboard;