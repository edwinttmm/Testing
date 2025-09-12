/**
 * Sequential Video Playback System - Example Implementation
 * 
 * Complete demonstration of the sequential video playback system
 * with automatic fullscreen functionality and all features
 */

import React, { useState, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Stack,
  Alert,
  Switch,
  FormControlLabel,
  TextField,
  Paper,
  Divider,
  Chip,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  VideoLibrary as VideoIcon,
  Settings as SettingsIcon,
  Fullscreen as FullscreenIcon,
} from '@mui/icons-material';

import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import { VideoFile, VideoStatus } from '../services/types';

const SequentialVideoPlaybackExample: React.FC = () => {
  const [exampleVideos] = useState<VideoFile[]>([
    {
      id: '1',
      projectId: 'example-project',
      filename: 'test-video-1.mp4',
      name: 'Sample Video 1',
      url: 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4',
      duration: 30,
      size: 1048576,
      fileSize: 1048576,
      filePath: '/videos/test-1.mp4',
      format: 'mp4',
      status: VideoStatus.VALIDATED,
      processingStatus: 'completed' as const,
      groundTruthGenerated: false,
      detectionCount: 0,
      annotationCount: 0,
      uploaded_at: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    },
    {
      id: '2',
      projectId: 'example-project',
      filename: 'test-video-2.mp4',
      name: 'Sample Video 2',
      url: 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_2mb.mp4',
      duration: 45,
      size: 2097152,
      fileSize: 2097152,
      filePath: '/videos/test-2.mp4',
      format: 'mp4',
      status: VideoStatus.VALIDATED,
      processingStatus: 'completed' as const,
      groundTruthGenerated: false,
      detectionCount: 0,
      annotationCount: 0,
      uploaded_at: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    },
    {
      id: '3',
      projectId: 'example-project',
      filename: 'test-video-3.mp4',
      name: 'Sample Video 3',
      url: 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_5mb.mp4',
      duration: 60,
      size: 5242880,
      fileSize: 5242880,
      filePath: '/videos/test-3.mp4',
      format: 'mp4',
      status: VideoStatus.VALIDATED,
      processingStatus: 'completed' as const,
      groundTruthGenerated: false,
      detectionCount: 0,
      annotationCount: 0,
      uploaded_at: new Date().toISOString(),
      createdAt: new Date().toISOString(),
    },
  ]);

  const [playbackConfig, setPlaybackConfig] = useState({
    autoAdvance: true,
    loopPlayback: false,
    randomOrder: false,
    preloadNext: true,
    fullscreenMode: true,
    autoFullscreen: false,
    transitionDelay: 1000,
    enableHardwareAcceleration: true,
    syncWithExternalSignals: false,
  });

  const [playbackLog, setPlaybackLog] = useState<string[]>([]);
  const [errorLog, setErrorLog] = useState<string[]>([]);
  const [showDemo, setShowDemo] = useState(false);

  const addToLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setPlaybackLog(prev => [...prev, `[${timestamp}] ${message}`]);
  };

  const handleVideoStart = (video: VideoFile, index: number) => {
    addToLog(`🎬 Started video ${index + 1}: ${video.filename}`);
  };

  const handleVideoEnd = (video: VideoFile, index: number) => {
    addToLog(`✅ Completed video ${index + 1}: ${video.filename}`);
  };

  const handlePlaybackComplete = () => {
    addToLog('🎉 Sequential playback completed!');
  };

  const handleError = (error: string) => {
    addToLog(`❌ Error: ${error}`);
    setErrorLog(prev => [...prev, error]);
  };

  const handleProgressUpdate = (progress: number, videoIndex: number) => {
    // Only log major progress milestones to avoid spam
    if (progress % 25 === 0 && progress > 0) {
      addToLog(`📊 Progress: ${progress}% (Video ${videoIndex + 1})`);
    }
  };

  const clearLogs = () => {
    setPlaybackLog([]);
    setErrorLog([]);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Sequential Video Playback System Demo
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        This demo showcases the complete sequential video playback system with automatic 
        fullscreen functionality, video queue management, and comprehensive controls.
      </Alert>

      {/* Configuration Panel */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <SettingsIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Playback Configuration
          </Typography>

          <Stack spacing={2}>
            <Stack direction="row" spacing={2} flexWrap="wrap">
              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.autoAdvance}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      autoAdvance: e.target.checked
                    }))}
                  />
                }
                label="Auto Advance Videos"
              />
              
              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.loopPlayback}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      loopPlayback: e.target.checked
                    }))}
                  />
                }
                label="Loop Playback"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.randomOrder}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      randomOrder: e.target.checked
                    }))}
                  />
                }
                label="Random Order"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.preloadNext}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      preloadNext: e.target.checked
                    }))}
                  />
                }
                label="Preload Next Video"
              />
            </Stack>

            <Stack direction="row" spacing={2} flexWrap="wrap">
              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.fullscreenMode}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      fullscreenMode: e.target.checked
                    }))}
                  />
                }
                label="Fullscreen Mode"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.autoFullscreen}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      autoFullscreen: e.target.checked
                    }))}
                  />
                }
                label="Auto Fullscreen on Start"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={playbackConfig.syncWithExternalSignals}
                    onChange={(e) => setPlaybackConfig(prev => ({
                      ...prev,
                      syncWithExternalSignals: e.target.checked
                    }))}
                  />
                }
                label="Sync with External Signals"
              />
            </Stack>

            <Stack direction="row" spacing={2} alignItems="center">
              <TextField
                label="Transition Delay (ms)"
                type="number"
                value={playbackConfig.transitionDelay}
                onChange={(e) => setPlaybackConfig(prev => ({
                  ...prev,
                  transitionDelay: parseInt(e.target.value) || 1000
                }))}
                sx={{ width: 200 }}
                size="small"
              />
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {/* Demo Control */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center">
            <Button
              variant="contained"
              startIcon={showDemo ? <VideoIcon /> : <PlayIcon />}
              onClick={() => {
                setShowDemo(!showDemo);
                if (!showDemo) {
                  clearLogs();
                  addToLog('Demo started with configuration: ' + 
                    JSON.stringify(playbackConfig, null, 2));
                }
              }}
              size="large"
            >
              {showDemo ? 'Hide Demo' : 'Show Demo'}
            </Button>

            <Button
              variant="outlined"
              onClick={clearLogs}
              disabled={playbackLog.length === 0}
            >
              Clear Logs
            </Button>

            <Chip 
              label={`${exampleVideos.length} Videos`}
              icon={<VideoIcon />}
              color="primary"
            />

            {playbackConfig.fullscreenMode && (
              <Chip
                label="Fullscreen Ready"
                icon={<FullscreenIcon />}
                color="success"
              />
            )}
          </Stack>
        </CardContent>
      </Card>

      {/* Sequential Video Player Demo */}
      {showDemo && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Sequential Video Player
            </Typography>
            
            <SequentialVideoPlayer
              videos={exampleVideos}
              config={{ autoAdvance: playbackConfig.autoAdvance, loopPlayback: playbackConfig.loopPlayback }}
              onVideoStart={handleVideoStart}
              onVideoEnd={handleVideoEnd}
              onPlaybackComplete={handlePlaybackComplete}
              onError={handleError}
              onProgressUpdate={handleProgressUpdate}
              autoStart={false}
              showControls={true}
              showProgress={true}
              syncWithLabJack={playbackConfig.syncWithExternalSignals}
            />
          </CardContent>
        </Card>
      )}

      {/* Event Log */}
      {(playbackLog.length > 0 || errorLog.length > 0) && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Event Log
            </Typography>

            {/* Playback Events */}
            <Paper sx={{ p: 2, mb: 2, maxHeight: 300, overflow: 'auto' }}>
              <Typography variant="subtitle2" gutterBottom>
                Playback Events ({playbackLog.length})
              </Typography>
              <Divider sx={{ mb: 1 }} />
              {playbackLog.length > 0 ? (
                <Stack spacing={0.5}>
                  {playbackLog.map((log, index) => (
                    <Typography
                      key={index}
                      variant="body2"
                      sx={{ fontFamily: 'monospace' }}
                    >
                      {log}
                    </Typography>
                  ))}
                </Stack>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No events yet. Start the demo to see playback events.
                </Typography>
              )}
            </Paper>

            {/* Error Log */}
            {errorLog.length > 0 && (
              <Paper sx={{ p: 2, maxHeight: 200, overflow: 'auto' }}>
                <Typography variant="subtitle2" gutterBottom color="error">
                  Error Log ({errorLog.length})
                </Typography>
                <Divider sx={{ mb: 1 }} />
                <Stack spacing={1}>
                  {errorLog.map((error, index) => (
                    <Alert key={index} severity="error">
                      <Typography variant="body2">
                        {error}
                      </Typography>
                    </Alert>
                  ))}
                </Stack>
              </Paper>
            )}
          </CardContent>
        </Card>
      )}

      {/* Feature Overview */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            System Features
          </Typography>

          <Stack spacing={2}>
            <Alert severity="success">
              <Typography variant="subtitle2" gutterBottom>
                ✨ Automatic Sequential Playback
              </Typography>
              Videos automatically advance with configurable delays and smooth transitions.
            </Alert>

            <Alert severity="info">
              <Typography variant="subtitle2" gutterBottom>
                🖥️ Fullscreen API Integration
              </Typography>
              Cross-browser fullscreen support with automatic video optimization.
            </Alert>

            <Alert severity="warning">
              <Typography variant="subtitle2" gutterBottom>
                📱 Comprehensive Controls
              </Typography>
              Play, pause, skip, jump to any video, and configure all playback options.
            </Alert>

            <Alert severity="error">
              <Typography variant="subtitle2" gutterBottom>
                🔧 Error Handling & Recovery
              </Typography>
              Robust error handling with automatic retry and graceful fallbacks.
            </Alert>
          </Stack>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            This system is designed for research and testing environments where precise 
            video playback control and timing are essential. It integrates with external 
            data collection systems like LabJack for synchronized measurements.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default SequentialVideoPlaybackExample;