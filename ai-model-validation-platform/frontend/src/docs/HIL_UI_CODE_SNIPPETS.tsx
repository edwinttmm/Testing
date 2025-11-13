/**
 * HIL Multi-Video Sequential Testing - UI Code Snippets
 *
 * These code snippets should be integrated into HILTestExecutionPRD.tsx
 * Copy and paste these sections into the appropriate locations.
 */

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Checkbox,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
} from '@mui/material';
import {
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';

// ============================================================================
// SNIPPET 1: Multi-Video Mode Toggle
// Location: Add after "3. Maximum Acceptable Latency" section (around line 1650)
// ============================================================================

export const MultiVideoModeToggle = () => (
  <Box sx={{ mb: 3 }}>
    <Typography variant="subtitle2" gutterBottom>
      Test Mode
    </Typography>
    <FormControlLabel
      control={
        <Checkbox
          checked={multiVideoMode}
          onChange={(e) => setMultiVideoMode(e.target.checked)}
          disabled={testRunning}
        />
      }
      label="Multi-video sequence mode"
    />
    {multiVideoMode ? (
      <Typography variant="body2" color="text.secondary">
        Select and order multiple videos for sequential automated testing
      </Typography>
    ) : (
      <Typography variant="body2" color="text.secondary">
        Single video mode with manual control
      </Typography>
    )}
  </Box>
);

// ============================================================================
// SNIPPET 2: Video Selection Table
// Location: Add after MultiVideoModeToggle, conditional on multiVideoMode
// ============================================================================

export const VideoSelectionTable = ({ videoPlaylist, selectedVideoIds, handleVideoSelect, handleSelectAllVideos, handleAddSelectedToOrder, testRunning }: any) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Video Selection
        </Typography>

        <Typography variant="body2" color="text.secondary" gutterBottom>
          Select videos to include in the sequential test
        </Typography>

        <FormControlLabel
          control={
            <Checkbox
              checked={selectedVideoIds.length === videoPlaylist.length && videoPlaylist.length > 0}
              indeterminate={selectedVideoIds.length > 0 && selectedVideoIds.length < videoPlaylist.length}
              onChange={(e) => handleSelectAllVideos(e.target.checked)}
              disabled={testRunning}
            />
          }
          label={`Select All (${selectedVideoIds.length}/${videoPlaylist.length})`}
        />

        <TableContainer component={Paper} sx={{ mt: 2, maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">Select</TableCell>
                <TableCell>Video Name</TableCell>
                <TableCell align="right">Duration</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {videoPlaylist.map((video: any) => (
                <TableRow
                  key={video.id}
                  hover
                  sx={{
                    '&:hover': { bgcolor: 'action.hover' },
                    opacity: selectedVideoIds.includes(video.id) ? 1 : 0.7
                  }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectedVideoIds.includes(video.id)}
                      onChange={(e) => handleVideoSelect(video.id, e.target.checked)}
                      disabled={testRunning}
                    />
                  </TableCell>
                  <TableCell>{video.filename || video.name}</TableCell>
                  <TableCell align="right">{formatTime(video.duration || 0)}</TableCell>
                  <TableCell>
                    <Chip
                      label={video.status}
                      size="small"
                      color={video.status === 'validated' ? 'success' : 'default'}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
          <Button
            variant="contained"
            onClick={handleAddSelectedToOrder}
            disabled={selectedVideoIds.length === 0 || testRunning}
          >
            Add Selected to Test Queue ({selectedVideoIds.length})
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// SNIPPET 3: Test Queue Display with Drag-and-Drop Ordering
// Location: Add after VideoSelectionTable
// ============================================================================

export const TestQueueDisplay = ({ orderedVideos, handleMoveVideoUp, handleMoveVideoDown, handleRemoveVideoFromOrder, calculateTotalDuration, testRunning }: any) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (orderedVideos.length === 0) return null;

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Test Queue ({orderedVideos.length} videos)
        </Typography>

        <Box sx={{ display: 'flex', gap: 4, mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Estimated total duration:</strong> {formatTime(calculateTotalDuration())}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Videos:</strong> {orderedVideos.length}
          </Typography>
        </Box>

        <TableContainer component={Paper} sx={{ maxHeight: 400 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell width={80}>Order</TableCell>
                <TableCell>Video Name</TableCell>
                <TableCell align="right">Duration</TableCell>
                <TableCell align="center" width={150}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orderedVideos.map((video: any, index: number) => (
                <TableRow key={video.id}>
                  <TableCell>
                    <Chip label={`${index + 1}`} size="small" color="primary" />
                  </TableCell>
                  <TableCell>{video.filename || video.name}</TableCell>
                  <TableCell align="right">{formatTime(video.duration || 0)}</TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={() => handleMoveVideoUp(index)}
                      disabled={index === 0 || testRunning}
                      title="Move up"
                    >
                      <ArrowUpIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleMoveVideoDown(index)}
                      disabled={index === orderedVideos.length - 1 || testRunning}
                      title="Move down"
                    >
                      <ArrowDownIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleRemoveVideoFromOrder(index)}
                      disabled={testRunning}
                      color="error"
                      title="Remove from queue"
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Use the arrow buttons to reorder videos. Videos will play in this order during the test.
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

// ============================================================================
// SNIPPET 4: Sequential Video Player Integration
// Location: Replace existing video player section when in multi-video mode
// ============================================================================

export const MultiVideoPlayerSection = ({ testRunning, multiVideoMode, sequenceId, orderedVideos, showSnackbar, navigate }: any) => {
  if (!testRunning || !multiVideoMode || !sequenceId) return null;

  return (
    <Box sx={{ width: '100%', height: '100vh' }}>
      <SequentialVideoPlayer
        videos={orderedVideos}
        config={{
          autoAdvance: true,
          loopPlayback: false,
        }}
        onVideoStart={(video, index) => {
          console.log(`🎬 Starting video ${index + 1}/${orderedVideos.length}: ${video.filename}`);
          showSnackbar(`Playing video ${index + 1}/${orderedVideos.length}`, 'info');
        }}
        onVideoEnd={(video, index) => {
          console.log(`✅ Completed video ${index + 1}/${orderedVideos.length}: ${video.filename}`);
        }}
        onPlaybackComplete={() => {
          console.log('🎉 All videos completed - navigating to results');
          showSnackbar('Test sequence completed!', 'success');
          // Navigate to results page with sequence_id
          setTimeout(() => {
            navigate(`/hil-results?sequence_id=${sequenceId}`);
          }, 1000);
        }}
        onError={(error, video) => {
          console.error('❌ Video error:', error, video);
          showSnackbar(`Video error: ${error}`, 'error');
          // Log error to backend
          apiService.post('/api/video-sequences/video-failed', {
            sequence_id: sequenceId,
            video_id: video.id,
            error: error
          });
        }}
        onProgressUpdate={(progress, videoIndex) => {
          // Optional: Update progress state for UI
          console.log(`Progress: ${progress}% (video ${videoIndex + 1}/${orderedVideos.length})`);
        }}
        autoStart={true}
        showControls={true}
        showProgress={true}
        syncWithLabJack={true}
      />
    </Box>
  );
};

// ============================================================================
// SNIPPET 5: Updated Validation Function
// Location: Replace existing canStartTest function
// ============================================================================

export const canStartTestMultiVideo = (
  selectedProject: any,
  multiVideoMode: boolean,
  orderedVideos: any[],
  validatedVideos: any[],
  expectedDetections: any[],
  labjackStatus: any
) => {
  const reasons: string[] = [];

  if (!selectedProject) {
    reasons.push('No project selected');
  }

  if (multiVideoMode) {
    // Multi-video validation
    if (orderedVideos.length === 0) {
      reasons.push('No videos selected for sequence. Add at least one video to the test queue.');
    }
    // Note: Ground truth not required for multi-video mode as it's handled per-video by backend
  } else {
    // Single-video validation
    if (validatedVideos.length === 0) {
      reasons.push('No validated videos available');
    }
    if (expectedDetections.length === 0) {
      reasons.push('No ground truth data loaded for selected video');
    }
  }

  if (!labjackStatus.connected) {
    reasons.push('LabJack hardware not connected. Please check connection.');
  }

  return {
    canStart: reasons.length === 0,
    reasons
  };
};

// ============================================================================
// SNIPPET 6: Pre-Test Configuration Display
// Location: Add before Start Test button
// ============================================================================

export const PreTestConfiguration = ({ multiVideoMode, orderedVideos, maxLatencyMs, labjackStatus }: any) => {
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Card sx={{ mb: 3, bgcolor: 'info.light', borderLeft: 4, borderColor: 'info.main' }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Pre-Test Configuration Summary
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Typography variant="body2">
            <strong>Mode:</strong> {multiVideoMode ? 'Multi-video Sequential' : 'Single Video'}
          </Typography>

          {multiVideoMode && (
            <>
              <Typography variant="body2">
                <strong>Videos in Queue:</strong> {orderedVideos.length}
              </Typography>
              <Typography variant="body2">
                <strong>Estimated Duration:</strong> {formatTime(orderedVideos.reduce((sum: number, v: any) => sum + (v.duration || 0), 0))}
              </Typography>
            </>
          )}

          <Typography variant="body2">
            <strong>Max Latency Threshold:</strong> {maxLatencyMs}ms
          </Typography>

          <Typography variant="body2">
            <strong>LabJack Status:</strong>{' '}
            <Chip
              label={labjackStatus.connected ? 'Connected' : 'Disconnected'}
              size="small"
              color={labjackStatus.connected ? 'success' : 'error'}
            />
          </Typography>

          {multiVideoMode && orderedVideos.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Videos will play automatically in sequence. No user interaction required between videos.
              </Typography>
            </Box>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

export default {
  MultiVideoModeToggle,
  VideoSelectionTable,
  TestQueueDisplay,
  MultiVideoPlayerSection,
  canStartTestMultiVideo,
  PreTestConfiguration,
};