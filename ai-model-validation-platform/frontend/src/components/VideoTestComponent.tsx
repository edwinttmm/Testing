/**
 * Simple Video Test Component
 * 
 * A basic test component to verify that the SequentialVideoPlayer system works correctly
 * with dummy/test video URLs.
 */

import React, { useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Stack,
  List,
  ListItem,
  ListItemText,
  Chip,
} from '@mui/material';
import { PlayArrow as PlayIcon, VideoLibrary as VideoIcon } from '@mui/icons-material';

import SequentialVideoPlayer from './SequentialVideoPlayer';
import { VideoFile, VideoStatus } from '../services/types';

// Test videos - use publicly available test video URLs
const TEST_VIDEOS: VideoFile[] = [
  {
    id: 'test-1',
    projectId: 'test-project',
    filename: 'big-buck-bunny-sample.mp4',
    name: 'Big Buck Bunny Sample',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
    duration: 596,
    fileSize: 158008374,
    size: 158008374,
    status: VideoStatus.VALIDATED,
    processingStatus: 'completed',
    groundTruthGenerated: false,
    detectionCount: 0,
    annotationCount: 0,
    createdAt: new Date().toISOString()
  },
  {
    id: 'test-2',
    projectId: 'test-project',
    filename: 'elephants-dream-sample.mp4',
    name: 'Elephants Dream Sample',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
    duration: 653,
    fileSize: 125513024,
    size: 125513024,
    status: VideoStatus.VALIDATED,
    processingStatus: 'completed',
    groundTruthGenerated: false,
    detectionCount: 0,
    annotationCount: 0,
    createdAt: new Date().toISOString()
  },
  {
    id: 'test-3',
    projectId: 'test-project',
    filename: 'for-bigger-blazes.mp4',
    name: 'For Bigger Blazes',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    duration: 15,
    fileSize: 2097152,
    size: 2097152,
    status: VideoStatus.VALIDATED,
    processingStatus: 'completed',
    groundTruthGenerated: false,
    detectionCount: 0,
    annotationCount: 0,
    createdAt: new Date().toISOString()
  }
];

const VideoTestComponent: React.FC = () => {
  const [testStarted, setTestStarted] = useState(false);
  const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(null);
  const [testLogs, setTestLogs] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const addLog = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    const logMessage = `[${timestamp}] ${message}`;
    setTestLogs(prev => [...prev, logMessage]);
    console.log('📹 VideoTest:', logMessage);
  }, []);

  const addError = useCallback((error: string) => {
    const timestamp = new Date().toLocaleTimeString(); 
    const errorMessage = `[${timestamp}] ERROR: ${error}`;
    setErrors(prev => [...prev, errorMessage]);
    console.error('🚨 VideoTest Error:', errorMessage);
  }, []);

  const handleStartTest = useCallback(() => {
    // IMMEDIATE debug logging to verify button click
    console.log('🔵 BUTTON CLICKED: handleStartTest called immediately');
    console.log('🔵 BUTTON CLICKED: Event fired at', new Date().toISOString());
    
    console.log('🔍 DEBUG: handleStartTest called - button was clicked');
    setTestStarted(true);
    setTestLogs([]);
    setErrors([]);
    addLog('Starting sequential video test with 3 sample videos');
    console.log('🔍 DEBUG: Test state updated, VideoTestComponent should now render SequentialVideoPlayer');
    
    // Additional verification logging
    console.log('🔍 DEBUG: testStarted state will be set to true');
  }, [addLog]);

  const handleVideoStart = useCallback((video: VideoFile, index: number) => {
    setCurrentVideo(video);
    addLog(`Video ${index + 1} started: ${video.name} (${video.filename})`);
  }, [addLog]);

  const handleVideoEnd = useCallback((video: VideoFile, index: number) => {
    addLog(`Video ${index + 1} ended: ${video.name}`);
  }, [addLog]);

  const handlePlaybackComplete = useCallback(() => {
    addLog('All videos completed successfully! 🎉');
    setCurrentVideo(null);
  }, [addLog]);

  const handleError = useCallback((error: string, video: VideoFile) => {
    addError(`Video ${video.name}: ${error}`);
  }, [addError]);

  const handleProgressUpdate = useCallback((progress: number, videoIndex: number) => {
    // Only log progress every 25% to avoid spam
    if (progress % 25 < 1) {
      addLog(`Video ${videoIndex + 1} progress: ${Math.round(progress)}%`);
    }
  }, [addLog]);

  const resetTest = useCallback(() => {
    setTestStarted(false);
    setCurrentVideo(null);
    setTestLogs([]);
    setErrors([]);
  }, []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        🎬 Video Playback System Test
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        This test uses publicly available sample videos to verify the sequential video playback system works correctly.
        Check the browser console and the logs below for detailed debugging information.
      </Alert>

      {/* Test Videos List */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Test Videos ({TEST_VIDEOS.length})
          </Typography>
          <List dense>
            {TEST_VIDEOS.map((video, index) => (
              <ListItem key={video.id}>
                <VideoIcon sx={{ mr: 2, color: 'primary.main' }} />
                <ListItemText
                  primary={`${index + 1}. ${video.name}`}
                  secondary={`Duration: ${Math.floor((video.duration || 0) / 60)}:${String((video.duration || 0) % 60).padStart(2, '0')} | Size: ${Math.round((video.size || 0) / 1024 / 1024)}MB`}
                />
                <Chip
                  label={video === currentVideo ? 'Playing' : 'Pending'}
                  color={video === currentVideo ? 'success' : 'default'}
                  size="small"
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      {/* Control Panel */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center">
            {!testStarted ? (
              <Button
                variant="contained"
                startIcon={<PlayIcon />}
                onClick={handleStartTest}
                size="large"
                // Never disable this button - it should work even without backend
                disabled={false}
                style={{ minWidth: '200px' }}
              >
                Start Video Test
              </Button>
            ) : (
              <Button
                variant="outlined"
                onClick={resetTest}
                size="large"
              >
                Reset Test
              </Button>
            )}
            
            <Typography variant="body2" color="text.secondary">
              {testStarted 
                ? currentVideo 
                  ? `Currently playing: ${currentVideo.name}`
                  : 'Test completed or waiting...'
                : 'Click "Start Video Test" to begin'
              }
            </Typography>
          </Stack>
        </CardContent>
      </Card>

      {/* Video Player */}
      {testStarted && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Sequential Video Player
            </Typography>
            <Box sx={{ border: '1px solid #ddd', borderRadius: 1 }}>
              <SequentialVideoPlayer
                key="stable-video-player" // Stable key prevents unnecessary re-mounts
                videos={TEST_VIDEOS}
                onVideoStart={handleVideoStart}
                onVideoEnd={handleVideoEnd}
                onPlaybackComplete={handlePlaybackComplete}
                onError={handleError}
                onProgressUpdate={handleProgressUpdate}
                autoStart={true}
                showControls={true}
                showProgress={true}
              />
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Test Logs */}
      {(testLogs.length > 0 || errors.length > 0) && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Test Logs & Debug Information
            </Typography>
            
            {errors.length > 0 && (
              <Alert severity="error" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Errors Detected ({errors.length}):
                </Typography>
                {errors.map((error, index) => (
                  <Typography key={index} variant="body2" component="div">
                    {error}
                  </Typography>
                ))}
              </Alert>
            )}

            <Box
              sx={{
                maxHeight: 400,
                overflow: 'auto',
                bgcolor: '#f5f5f5',
                p: 2,
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: '0.875rem',
              }}
            >
              {testLogs.map((log, index) => (
                <div key={index} style={{ marginBottom: '4px' }}>
                  {log}
                </div>
              ))}
              {testLogs.length === 0 && (
                <Typography variant="body2" color="text.secondary" style={{ fontStyle: 'italic' }}>
                  No logs yet. Start the test to see debug information.
                </Typography>
              )}
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default VideoTestComponent;