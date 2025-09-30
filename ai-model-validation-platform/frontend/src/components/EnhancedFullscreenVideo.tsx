/**
 * Enhanced Fullscreen Video Component
 * Integrates comprehensive DOM analysis and robust fullscreen handling
 * for HIL test execution
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  Alert,
  AlertTitle,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  List,
  ListItem,
  ListItemText,
  Paper,
} from '@mui/material';
import {
  Fullscreen,
  FullscreenExit,
  BugReport,
  Warning,
  CheckCircle,
  Error,
  ExpandMore,
} from '@mui/icons-material';
import { useEnhancedFullscreen } from '../hooks/useEnhancedFullscreen';
import { debugFullscreenDOM, generateFullscreenDebugReport } from '../utils/debugFullscreenDOM';
import { analyzeFullscreenDOM } from '../utils/fullscreenDomAnalyzer';

interface EnhancedFullscreenVideoProps {
  src: string;
  onVideoReady?: (video: HTMLVideoElement) => void;
  onFullscreenChange?: (isFullscreen: boolean) => void;
  onError?: (error: string) => void;
  debug?: boolean;
  fallbackMode?: 'css' | 'none';
  autoEnterFullscreen?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

interface DiagnosticState {
  isVisible: boolean;
  isRunning: boolean;
  results: any[];
  report: string;
}

export const EnhancedFullscreenVideo: React.FC<EnhancedFullscreenVideoProps> = ({
  src,
  onVideoReady,
  onFullscreenChange,
  onError,
  debug = false,
  fallbackMode = 'css',
  autoEnterFullscreen = false,
  className,
  style,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [videoReady, setVideoReady] = useState(false);
  const [diagnostics, setDiagnostics] = useState<DiagnosticState>({
    isVisible: false,
    isRunning: false,
    results: [],
    report: '',
  });

  // Enhanced fullscreen hook
  const {
    isFullscreen,
    isSupported,
    isPending,
    error: fullscreenError,
    fallbackActive,
    enterFullscreen,
    exitFullscreen,
    toggleFullscreen,
    analyzeDOMState,
  } = useEnhancedFullscreen({
    onEnter: () => {
      console.log('🎬 Entered fullscreen mode');
      onFullscreenChange?.(true);
    },
    onExit: () => {
      console.log('🚪 Exited fullscreen mode');
      onFullscreenChange?.(false);
    },
    onError: (error) => {
      console.error('❌ Fullscreen error:', error);
      onError?.(error.message);
    },
    fallbackMode,
    debugMode: debug,
    retryAttempts: 3,
    retryDelay: 1000,
  });

  // Handle video ready state
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleCanPlay = () => {
      console.log('📹 Video can play - ready for fullscreen');
      setVideoReady(true);
      onVideoReady?.(video);

      // Auto-enter fullscreen if requested
      if (autoEnterFullscreen && !isFullscreen) {
        handleFullscreenRequest();
      }
    };

    const handleLoadedData = () => {
      console.log('📹 Video data loaded');
    };

    const handleError = (e: Event) => {
      const error = `Video load error: ${video.error?.message || 'Unknown error'}`;
      console.error('📹 Video error:', error);
      onError?.(error);
    };

    video.addEventListener('canplay', handleCanPlay);
    video.addEventListener('loadeddata', handleLoadedData);
    video.addEventListener('error', handleError);

    return () => {
      video.removeEventListener('canplay', handleCanPlay);
      video.removeEventListener('loadeddata', handleLoadedData);
      video.removeEventListener('error', handleError);
    };
  }, [src, autoEnterFullscreen, isFullscreen, onVideoReady, onError]);

  // Handle fullscreen request with enhanced diagnostics
  const handleFullscreenRequest = useCallback(async () => {
    if (!videoReady) {
      onError?.('Video not ready for fullscreen. Please wait for video to load.');
      return;
    }

    if (debug) {
      console.log('🔍 Running pre-fullscreen diagnostics...');
      
      // Run comprehensive DOM analysis
      const domAnalysis = analyzeDOMState(videoRef, containerRef);
      
      // Check for critical issues
      const criticalIssues = domAnalysis.recommendations.filter(r => r.category === 'critical');
      if (criticalIssues.length > 0) {
        console.warn('⚠️ Critical fullscreen issues detected:', criticalIssues);
        onError?.(`Critical issues detected: ${criticalIssues.map(i => i.issue).join(', ')}`);
      }
    }

    // Attempt fullscreen on container (which contains video)
    const success = await enterFullscreen(containerRef.current || undefined);
    
    if (!success) {
      console.error('❌ Fullscreen attempt failed');
      
      if (debug) {
        // Run post-failure diagnostics
        await runFullDiagnostics();
      }
    }
  }, [videoReady, enterFullscreen, analyzeDOMState, debug, onError]);

  // Run full diagnostics
  const runFullDiagnostics = useCallback(async () => {
    setDiagnostics(prev => ({ ...prev, isRunning: true }));

    try {
      const results = await debugFullscreenDOM(videoRef, containerRef);
      const report = await generateFullscreenDebugReport(videoRef, containerRef);
      
      setDiagnostics({
        isVisible: true,
        isRunning: false,
        results,
        report,
      });

      console.log('🔍 Fullscreen diagnostics complete:', { results, report });
    } catch (error) {
      console.error('❌ Diagnostics failed:', error);
      setDiagnostics(prev => ({ 
        ...prev, 
        isRunning: false,
        results: [],
        report: `Diagnostics failed: ${error}`,
      }));
    }
  }, []);

  // Get status color for diagnostics
  const getStatusColor = (success: boolean) => success ? 'success' : 'error';
  const getStatusIcon = (success: boolean) => success ? <CheckCircle /> : <Error />;

  return (
    <Box className={className} style={style}>
      {/* Main Container - This will be the fullscreen target */}
      <Box
        ref={containerRef}
        sx={{
          position: 'relative',
          width: '100%',
          height: isFullscreen ? '100vh' : 'auto',
          backgroundColor: 'black',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Video Element */}
        <video
          ref={videoRef}
          src={src}
          style={{
            width: '100%',
            height: 'auto',
            maxWidth: '100%',
            maxHeight: isFullscreen ? '100vh' : '600px',
            objectFit: 'contain',
          }}
          preload="metadata"
          playsInline
          muted // Muted to allow autoplay in some browsers
        />

        {/* Loading Indicator */}
        {!videoReady && (
          <Box
            sx={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              color: 'white',
            }}
          >
            <CircularProgress sx={{ color: 'white' }} />
            <Typography variant="body1">Loading video...</Typography>
          </Box>
        )}

        {/* Fullscreen Controls - Only show when video is ready */}
        {videoReady && (
          <Box
            sx={{
              position: 'absolute',
              top: 16,
              right: 16,
              display: 'flex',
              gap: 1,
              backgroundColor: 'rgba(0, 0, 0, 0.7)',
              borderRadius: 2,
              p: 1,
            }}
          >
            {/* Debug Button */}
            {debug && (
              <Tooltip title="Run Fullscreen Diagnostics">
                <IconButton
                  onClick={runFullDiagnostics}
                  disabled={diagnostics.isRunning}
                  sx={{ color: 'white' }}
                >
                  {diagnostics.isRunning ? (
                    <CircularProgress size={24} sx={{ color: 'white' }} />
                  ) : (
                    <BugReport />
                  )}
                </IconButton>
              </Tooltip>
            )}

            {/* Fullscreen Toggle Button */}
            <Tooltip title={isFullscreen ? "Exit Fullscreen" : "Enter Fullscreen"}>
              <IconButton
                onClick={isFullscreen ? exitFullscreen : handleFullscreenRequest}
                disabled={isPending}
                sx={{ color: 'white' }}
              >
                {isPending ? (
                  <CircularProgress size={24} sx={{ color: 'white' }} />
                ) : isFullscreen ? (
                  <FullscreenExit />
                ) : (
                  <Fullscreen />
                )}
              </IconButton>
            </Tooltip>
          </Box>
        )}

        {/* Fullscreen Status Indicators */}
        {(isFullscreen || fallbackActive) && (
          <Box
            sx={{
              position: 'absolute',
              bottom: 16,
              left: 16,
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              borderRadius: 1,
              p: 1,
            }}
          >
            <Chip
              icon={<CheckCircle />}
              label={fallbackActive ? 'CSS Fullscreen Active' : 'Native Fullscreen Active'}
              color="success"
              size="small"
              sx={{ color: 'white', backgroundColor: 'rgba(76, 175, 80, 0.8)' }}
            />
          </Box>
        )}
      </Box>

      {/* Error Display */}
      {fullscreenError && (
        <Alert severity="error" sx={{ mt: 2 }} onClose={() => {}}>
          <AlertTitle>Fullscreen Error</AlertTitle>
          {fullscreenError.message}
          {!isSupported && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Your browser may not support fullscreen API. {fallbackMode === 'css' ? 'CSS fallback is available.' : 'No fallback configured.'}
            </Typography>
          )}
        </Alert>
      )}

      {/* Browser Support Warning */}
      {!isSupported && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          <AlertTitle>Limited Fullscreen Support</AlertTitle>
          Your browser has limited fullscreen support. Some features may not work as expected.
          {fallbackMode === 'css' && ' CSS-based fullscreen fallback is enabled.'}
        </Alert>
      )}

      {/* Diagnostics Dialog */}
      <Dialog
        open={diagnostics.isVisible}
        onClose={() => setDiagnostics(prev => ({ ...prev, isVisible: false }))}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: { maxHeight: '80vh' }
        }}
      >
        <DialogTitle>
          Fullscreen Diagnostics Report
          <Chip
            label={`${diagnostics.results.filter(r => r.success).length}/${diagnostics.results.length} tests passed`}
            color={diagnostics.results.every(r => r.success) ? 'success' : 'error'}
            size="small"
            sx={{ ml: 2 }}
          />
        </DialogTitle>
        
        <DialogContent dividers>
          {/* Quick Summary */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>Quick Summary</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              <Chip
                icon={<CheckCircle />}
                label={`Browser Support: ${isSupported ? 'Yes' : 'No'}`}
                color={getStatusColor(isSupported)}
                size="small"
              />
              <Chip
                icon={<CheckCircle />}
                label={`Video Ready: ${videoReady ? 'Yes' : 'No'}`}
                color={getStatusColor(videoReady)}
                size="small"
              />
              <Chip
                icon={<CheckCircle />}
                label={`Fallback: ${fallbackMode === 'css' ? 'Available' : 'Disabled'}`}
                color={getStatusColor(fallbackMode === 'css')}
                size="small"
              />
            </Box>
          </Box>

          {/* Test Results */}
          {diagnostics.results.length > 0 && (
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">Detailed Test Results</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <List>
                  {diagnostics.results.map((result, index) => (
                    <ListItem key={index}>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {getStatusIcon(result.success)}
                            <Typography variant="body1">
                              {result.testName}
                            </Typography>
                            <Chip
                              label={result.success ? 'PASS' : 'FAIL'}
                              color={getStatusColor(result.success)}
                              size="small"
                            />
                          </Box>
                        }
                        secondary={
                          <>
                            {result.error && (
                              <Typography color="error" variant="body2">
                                Error: {result.error}
                              </Typography>
                            )}
                            {result.recommendations.length > 0 && (
                              <Box sx={{ mt: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                  Recommendations:
                                </Typography>
                                <ul style={{ margin: 0, paddingLeft: 16 }}>
                                  {result.recommendations.map((rec, i) => (
                                    <li key={i}>
                                      <Typography variant="caption" color="text.secondary">
                                        {rec}
                                      </Typography>
                                    </li>
                                  ))}
                                </ul>
                              </Box>
                            )}
                          </>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          )}

          {/* Raw Report */}
          {diagnostics.report && (
            <Accordion sx={{ mt: 2 }}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="h6">Raw Diagnostic Report</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Paper sx={{ p: 2, backgroundColor: 'grey.50' }}>
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    fontFamily: 'monospace', 
                    fontSize: '0.875rem',
                    margin: 0,
                  }}>
                    {diagnostics.report}
                  </pre>
                </Paper>
              </AccordionDetails>
            </Accordion>
          )}
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => runFullDiagnostics()}>
            Refresh Diagnostics
          </Button>
          <Button 
            onClick={() => setDiagnostics(prev => ({ ...prev, isVisible: false }))}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EnhancedFullscreenVideo;