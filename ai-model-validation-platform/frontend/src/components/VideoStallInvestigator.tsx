/**
 * Video Stall Investigator Component
 * 
 * React component that provides a real-time interface for investigating
 * video element stalling issues and fullscreen compatibility problems.
 * Integrates with the VideoAPIInvestigator to provide detailed diagnostics.
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Grid,
  Switch,
  FormControlLabel,
  Divider,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import {
  ExpandMore,
  PlayArrow,
  Pause,
  Fullscreen,
  FullscreenExit,
  BugReport,
  Assessment,
  VideoSettings,
  NetworkCheck,
} from '@mui/icons-material';
import { 
  videoAPIInvestigator,
  startVideoInvestigation,
  analyzeVideoStall,
  testVideoFullscreenCompatibility,
  generateVideoReport,
  VideoEventLog,
  VideoStallDiagnostic,
  FullscreenCompatibilityTest
} from '../utils/videoAPIInvestigation';

interface VideoStallInvestigatorProps {
  testVideoUrl?: string;
  autoStart?: boolean;
}

interface InvestigationSession {
  id: string;
  cleanup: () => void;
  startTime: number;
}

const VideoStallInvestigator: React.FC<VideoStallInvestigatorProps> = ({
  testVideoUrl = '/api/test-video.mp4',
  autoStart = false
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [session, setSession] = useState<InvestigationSession | null>(null);
  const [eventLogs, setEventLogs] = useState<VideoEventLog[]>([]);
  const [stallDiagnostic, setStallDiagnostic] = useState<VideoStallDiagnostic | null>(null);
  const [fullscreenTest, setFullscreenTest] = useState<FullscreenCompatibilityTest | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [diagnosticReport, setDiagnosticReport] = useState<string>('');

  // Auto-refresh diagnostics every 2 seconds when enabled
  useEffect(() => {
    if (!autoRefresh || !session || !videoRef.current) return;

    const interval = setInterval(() => {
      updateDiagnostics();
    }, 2000);

    return () => clearInterval(interval);
  }, [autoRefresh, session]);

  // Start investigation on component mount if autoStart is true
  useEffect(() => {
    if (autoStart && videoRef.current && !session) {
      startInvestigation();
    }
  }, [autoStart]);

  // Update event logs periodically
  useEffect(() => {
    if (!session) return;

    const interval = setInterval(() => {
      const logs = videoAPIInvestigator.getEventLogs(session.id);
      setEventLogs(logs.slice(-50)); // Show last 50 events
    }, 1000);

    return () => clearInterval(interval);
  }, [session]);

  const startInvestigation = useCallback(() => {
    if (!videoRef.current || session) return;

    const investigation = startVideoInvestigation(videoRef.current);
    setSession({
      id: investigation.id,
      cleanup: investigation.cleanup,
      startTime: Date.now()
    });

    setVideoError(null);
    console.log('[VideoStallInvestigator] Started investigation:', investigation.id);
  }, [session]);

  const stopInvestigation = useCallback(() => {
    if (!session) return;

    session.cleanup();
    setSession(null);
    setEventLogs([]);
    setStallDiagnostic(null);
    console.log('[VideoStallInvestigator] Stopped investigation');
  }, [session]);

  const updateDiagnostics = useCallback(() => {
    if (!videoRef.current) return;

    // Update stall diagnostic
    const stallAnalysis = analyzeVideoStall(videoRef.current);
    setStallDiagnostic(stallAnalysis);

    // Generate diagnostic report
    if (session) {
      const report = generateVideoReport(session.id, videoRef.current);
      setDiagnosticReport(report);
    }
  }, [session]);

  const testFullscreenCompatibility = useCallback(async () => {
    if (!videoRef.current) return;

    try {
      const test = await testVideoFullscreenCompatibility(videoRef.current);
      setFullscreenTest(test);
      console.log('[VideoStallInvestigator] Fullscreen test completed:', test);
    } catch (error) {
      console.error('[VideoStallInvestigator] Fullscreen test failed:', error);
    }
  }, []);

  const handleVideoPlay = useCallback(() => {
    if (!videoRef.current) return;

    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play().catch(error => {
        setVideoError(`Play failed: ${error.message}`);
      });
    }
  }, [isPlaying]);

  const handleFullscreenToggle = useCallback(async () => {
    if (!videoRef.current) return;

    try {
      if (isFullscreen) {
        await document.exitFullscreen();
      } else {
        await videoRef.current.requestFullscreen();
      }
    } catch (error) {
      setVideoError(`Fullscreen failed: ${error.message}`);
    }
  }, [isFullscreen]);

  const handleVideoEvent = useCallback((eventType: string) => {
    return () => {
      if (eventType === 'play') setIsPlaying(true);
      if (eventType === 'pause') setIsPlaying(false);
      if (eventType === 'error') {
        const error = videoRef.current?.error;
        setVideoError(error ? `Video Error: ${error.message}` : 'Unknown video error');
      }
    };
  }, []);

  const handleFullscreenChange = useCallback(() => {
    setIsFullscreen(!!document.fullscreenElement);
  }, []);

  // Set up video event listeners
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const events = ['play', 'pause', 'error', 'loadstart', 'canplay', 'stalled'];
    const eventListeners: { [key: string]: EventListener } = {};

    events.forEach(eventType => {
      eventListeners[eventType] = handleVideoEvent(eventType);
      video.addEventListener(eventType, eventListeners[eventType]);
    });

    // Fullscreen change listener
    const fullscreenChangeListener = handleFullscreenChange;
    document.addEventListener('fullscreenchange', fullscreenChangeListener);

    return () => {
      events.forEach(eventType => {
        video.removeEventListener(eventType, eventListeners[eventType]);
      });
      document.removeEventListener('fullscreenchange', fullscreenChangeListener);
    };
  }, [handleVideoEvent, handleFullscreenChange]);

  const getReadyStateString = (readyState: number): string => {
    const states = ['HAVE_NOTHING', 'HAVE_METADATA', 'HAVE_CURRENT_DATA', 'HAVE_FUTURE_DATA', 'HAVE_ENOUGH_DATA'];
    return states[readyState] || `UNKNOWN(${readyState})`;
  };

  const getNetworkStateString = (networkState: number): string => {
    const states = ['NETWORK_EMPTY', 'NETWORK_IDLE', 'NETWORK_LOADING', 'NETWORK_NO_SOURCE'];
    return states[networkState] || `UNKNOWN(${networkState})`;
  };

  const formatTimeRanges = (ranges: TimeRanges): string => {
    const rangeStrings: string[] = [];
    for (let i = 0; i < ranges.length; i++) {
      rangeStrings.push(`[${ranges.start(i).toFixed(2)}-${ranges.end(i).toFixed(2)}]`);
    }
    return rangeStrings.join(', ') || 'None';
  };

  const currentVideo = videoRef.current;
  const investigationDuration = session ? (Date.now() - session.startTime) / 1000 : 0;

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        <BugReport sx={{ mr: 1, verticalAlign: 'middle' }} />
        Video Stall Investigator
      </Typography>
      
      {videoError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setVideoError(null)}>
          {videoError}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Video Player Section */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Video Player
              </Typography>
              
              <Box sx={{ position: 'relative', mb: 2 }}>
                <video
                  ref={videoRef}
                  src={testVideoUrl}
                  style={{
                    width: '100%',
                    maxHeight: '300px',
                    backgroundColor: '#000'
                  }}
                  controls
                />
                
                {stallDiagnostic?.isStalled && (
                  <Alert 
                    severity="warning" 
                    sx={{ 
                      position: 'absolute', 
                      top: 8, 
                      right: 8, 
                      opacity: 0.9 
                    }}
                  >
                    Video Stalled ({stallDiagnostic.stallType})
                  </Alert>
                )}
              </Box>

              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Button
                  variant="contained"
                  startIcon={isPlaying ? <Pause /> : <PlayArrow />}
                  onClick={handleVideoPlay}
                >
                  {isPlaying ? 'Pause' : 'Play'}
                </Button>

                <Button
                  variant="outlined"
                  startIcon={isFullscreen ? <FullscreenExit /> : <Fullscreen />}
                  onClick={handleFullscreenToggle}
                  disabled={!currentVideo}
                >
                  {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
                </Button>

                <Button
                  variant={session ? "contained" : "outlined"}
                  color={session ? "secondary" : "primary"}
                  startIcon={<Assessment />}
                  onClick={session ? stopInvestigation : startInvestigation}
                >
                  {session ? 'Stop Investigation' : 'Start Investigation'}
                </Button>

                <Button
                  variant="outlined"
                  startIcon={<VideoSettings />}
                  onClick={testFullscreenCompatibility}
                >
                  Test Fullscreen
                </Button>
              </Box>

              <FormControlLabel
                control={
                  <Switch
                    checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)}
                  />
                }
                label="Auto-refresh diagnostics"
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Investigation Status */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Investigation Status
              </Typography>

              {session ? (
                <>
                  <Chip label={`Active (${investigationDuration.toFixed(1)}s)`} color="primary" sx={{ mb: 2 }} />
                  <Typography variant="body2" color="textSecondary">
                    Session ID: {session.id}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Events Logged: {eventLogs.length}
                  </Typography>
                </>
              ) : (
                <Chip label="Not Active" sx={{ mb: 2 }} />
              )}

              {currentVideo && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Current Video State</Typography>
                  <List dense>
                    <ListItem>
                      <ListItemText 
                        primary="Ready State" 
                        secondary={getReadyStateString(currentVideo.readyState)}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText 
                        primary="Network State" 
                        secondary={getNetworkStateString(currentVideo.networkState)}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText 
                        primary="Current Time" 
                        secondary={`${currentVideo.currentTime.toFixed(2)}s`}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText 
                        primary="Duration" 
                        secondary={isFinite(currentVideo.duration) ? `${currentVideo.duration.toFixed(2)}s` : 'Unknown'}
                      />
                    </ListItem>
                  </List>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Diagnostic Results */}
      <Box sx={{ mt: 3 }}>
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography variant="h6">
              <NetworkCheck sx={{ mr: 1, verticalAlign: 'middle' }} />
              Stall Diagnostic
              {stallDiagnostic?.isStalled && (
                <Chip label="STALLED" color="error" size="small" sx={{ ml: 2 }} />
              )}
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {stallDiagnostic ? (
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>Stall Status</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Is Stalled</TableCell>
                        <TableCell>
                          <Chip 
                            label={stallDiagnostic.isStalled ? 'Yes' : 'No'} 
                            color={stallDiagnostic.isStalled ? 'error' : 'success'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Stall Type</TableCell>
                        <TableCell>{stallDiagnostic.stallType}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Duration</TableCell>
                        <TableCell>{stallDiagnostic.stallDuration}ms</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>Buffer Analysis</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Bytes Loaded</TableCell>
                        <TableCell>{stallDiagnostic.bytesLoaded.toLocaleString()}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Total Bytes</TableCell>
                        <TableCell>{stallDiagnostic.totalBytes.toLocaleString()}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Buffer Health</TableCell>
                        <TableCell>
                          {stallDiagnostic.bufferHealth.hasBufferedData ? 'Good' : 'Poor'}
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </Grid>
              </Grid>
            ) : (
              <Alert severity="info">
                Start an investigation and click "Update Diagnostics" to see stall analysis.
              </Alert>
            )}
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography variant="h6">
              <Fullscreen sx={{ mr: 1, verticalAlign: 'middle' }} />
              Fullscreen Compatibility Test
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {fullscreenTest ? (
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>Basic Support</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Supports Fullscreen</TableCell>
                        <TableCell>
                          <Chip 
                            label={fullscreenTest.supportsFullscreen ? 'Yes' : 'No'} 
                            color={fullscreenTest.supportsFullscreen ? 'success' : 'error'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Fullscreen Method</TableCell>
                        <TableCell>{fullscreenTest.fullscreenMethod || 'None'}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Exit Method</TableCell>
                        <TableCell>{fullscreenTest.exitFullscreenMethod || 'None'}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Picture-in-Picture</TableCell>
                        <TableCell>
                          <Chip 
                            label={fullscreenTest.supportsPictureInPicture ? 'Yes' : 'No'} 
                            color={fullscreenTest.supportsPictureInPicture ? 'success' : 'default'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="subtitle2" gutterBottom>Video Fullscreen Tests</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Direct Video</TableCell>
                        <TableCell>
                          <Chip 
                            label={fullscreenTest.testResults.directVideoFullscreen ? 'Pass' : 'Fail'} 
                            color={fullscreenTest.testResults.directVideoFullscreen ? 'success' : 'error'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Container Wrapper</TableCell>
                        <TableCell>
                          <Chip 
                            label={fullscreenTest.testResults.containerFullscreen ? 'Pass' : 'Fail'} 
                            color={fullscreenTest.testResults.containerFullscreen ? 'success' : 'error'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>While Playing</TableCell>
                        <TableCell>
                          <Chip 
                            label={fullscreenTest.testResults.fullscreenWhilePlaying ? 'Pass' : 'Fail'} 
                            color={fullscreenTest.testResults.fullscreenWhilePlaying ? 'success' : 'error'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>While Paused</TableCell>
                        <TableCell>
                          <Chip 
                            label={fullscreenTest.testResults.fullscreenWhilePaused ? 'Pass' : 'Fail'} 
                            color={fullscreenTest.testResults.fullscreenWhilePaused ? 'success' : 'error'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </Grid>
                {fullscreenTest.browserQuirks.length > 0 && (
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" gutterBottom>Browser Quirks</Typography>
                    {fullscreenTest.browserQuirks.map((quirk, index) => (
                      <Chip key={index} label={quirk} variant="outlined" sx={{ mr: 1, mb: 1 }} />
                    ))}
                  </Grid>
                )}
              </Grid>
            ) : (
              <Alert severity="info">
                Click "Test Fullscreen" to analyze fullscreen compatibility.
              </Alert>
            )}
          </AccordionDetails>
        </Accordion>

        <Accordion>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography variant="h6">Event Log ({eventLogs.length})</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Event</TableCell>
                    <TableCell>Ready State</TableCell>
                    <TableCell>Network State</TableCell>
                    <TableCell>Current Time</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {eventLogs.slice(-20).reverse().map((log, index) => (
                    <TableRow key={index}>
                      <TableCell>{new Date(log.timestamp).toLocaleTimeString()}</TableCell>
                      <TableCell>
                        <Chip 
                          label={log.event} 
                          size="small" 
                          color={
                            log.event === 'error' ? 'error' :
                            log.event === 'stalled' ? 'warning' :
                            ['canplay', 'playing'].includes(log.event) ? 'success' : 'default'
                          }
                        />
                      </TableCell>
                      <TableCell>{getReadyStateString(log.elementState.readyState)}</TableCell>
                      <TableCell>{getNetworkStateString(log.elementState.networkState)}</TableCell>
                      <TableCell>{log.elementState.currentTime.toFixed(2)}s</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>

        {diagnosticReport && (
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="h6">Diagnostic Report</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Paper sx={{ p: 2, backgroundColor: '#f5f5f5' }}>
                <Typography component="pre" sx={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                  {diagnosticReport}
                </Typography>
              </Paper>
            </AccordionDetails>
          </Accordion>
        )}
      </Box>

      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
        <Button
          variant="contained"
          onClick={updateDiagnostics}
          disabled={!session}
        >
          Update Diagnostics
        </Button>
      </Box>
    </Box>
  );
};

export default VideoStallInvestigator;