# HIL Test Execution Multi-Video Sequential Testing Implementation Guide

## Overview
This document outlines the comprehensive updates needed for `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx` to support one-click multi-video sequential testing.

## Implementation Summary

### 1. State Management Updates

#### New State Variables (Already Added)
```typescript
const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
const [orderedVideos, setOrderedVideos] = useState<VideoFile[]>([]);
const [multiVideoMode, setMultiVideoMode] = useState<boolean>(true);
const [sequenceId, setSequenceId] = useState<string | null>(null);
```

### 2. Video Selection Handlers (Already Added)

All handler functions have been implemented:
- `handleVideoSelect(videoId, checked)` - Toggle video selection
- `handleSelectAllVideos(checked)` - Select/deselect all videos
- `handleMoveVideoUp(index)` - Reorder videos up
- `handleMoveVideoDown(index)` - Reorder videos down
- `handleRemoveVideoFromOrder(index)` - Remove from ordered list
- `handleAddSelectedToOrder()` - Add selected videos to order
- `calculateTotalDuration()` - Calculate total test duration

### 3. Start Test Logic Updates

The `startHILTest` function needs to be updated to handle both single-video and multi-video modes:

```typescript
const startHILTest = async () => {
  setError(null);

  if (!selectedProject) {
    showSnackbar('Please select a project first', 'error');
    return;
  }

  if (multiVideoMode) {
    // Multi-video sequence validation
    if (orderedVideos.length === 0) {
      showSnackbar('Please select and order at least one video', 'error');
      return;
    }
    if (!labjackStatus.connected) {
      showSnackbar('LabJack is not connected. Please check connection.', 'error');
      return;
    }

    try {
      console.log('🚀 [HIL] Starting multi-video sequence test...');
      setTestRunning(true);

      // Call backend to start video sequence
      const response = await apiService.post<{ sequence_id: string, message: string }>(
        '/api/video-sequences/start',
        {
          project_id: selectedProject.id,
          video_ids: orderedVideos.map(v => v.id),
          max_latency_ms: maxLatencyMs,
          config: {
            detection_window_ms: 5000,
            voltage_threshold: 3.0,
            sample_rate: 1000,
            channels: ['FIO0', 'FIO1'],
          }
        }
      );

      setSequenceId(response.sequence_id);
      showSnackbar('Multi-video sequence test started', 'success');

    } catch (err: any) {
      console.error('🚨 [HIL] Error starting sequence test:', err);
      setError(`Failed to start sequence test: ${err.message}`);
      showSnackbar('Failed to start sequence test', 'error');
      setTestRunning(false);
    }
  } else {
    // Single-video mode (existing logic - keep as is)
    // ... existing single-video test logic
  }
};
```

### 4. UI Components to Add

#### A. Multi-Video Mode Toggle (Add after project selection)

```typescript
<Box sx={{ mb: 3 }}>
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
  {multiVideoMode && (
    <Typography variant="body2" color="text.secondary">
      Select and order multiple videos for sequential testing
    </Typography>
  )}
</Box>
```

#### B. Video Selection Table (Conditional render when multiVideoMode is true)

```typescript
{multiVideoMode && selectedProject && (
  <Card sx={{ mb: 3 }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        Video Selection
      </Typography>

      <FormControlLabel
        control={
          <Checkbox
            checked={selectedVideoIds.length === videoPlaylist.length && videoPlaylist.length > 0}
            indeterminate={selectedVideoIds.length > 0 && selectedVideoIds.length < videoPlaylist.length}
            onChange={(e) => handleSelectAllVideos(e.target.checked)}
          />
        }
        label="Select All"
      />

      <TableContainer component={Paper} sx={{ mt: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">Select</TableCell>
              <TableCell>Video Name</TableCell>
              <TableCell>Duration</TableCell>
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {videoPlaylist.map((video) => (
              <TableRow key={video.id}>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={selectedVideoIds.includes(video.id)}
                    onChange={(e) => handleVideoSelect(video.id, e.target.checked)}
                  />
                </TableCell>
                <TableCell>{video.filename || video.name}</TableCell>
                <TableCell>{formatTime(video.duration || 0)}</TableCell>
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
          variant="outlined"
          onClick={handleAddSelectedToOrder}
          disabled={selectedVideoIds.length === 0}
        >
          Add Selected to Test Queue ({selectedVideoIds.length})
        </Button>
      </Box>
    </CardContent>
  </Card>
)}
```

#### C. Video Order/Queue Display

```typescript
{multiVideoMode && orderedVideos.length > 0 && (
  <Card sx={{ mb: 3 }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        Test Queue ({orderedVideos.length} videos)
      </Typography>

      <Typography variant="body2" color="text.secondary" gutterBottom>
        Estimated total duration: {formatTime(calculateTotalDuration())}
      </Typography>

      <TableContainer component={Paper} sx={{ mt: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Order</TableCell>
              <TableCell>Video Name</TableCell>
              <TableCell>Duration</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {orderedVideos.map((video, index) => (
              <TableRow key={video.id}>
                <TableCell>{index + 1}</TableCell>
                <TableCell>{video.filename || video.name}</TableCell>
                <TableCell>{formatTime(video.duration || 0)}</TableCell>
                <TableCell>
                  <IconButton
                    size="small"
                    onClick={() => handleMoveVideoUp(index)}
                    disabled={index === 0}
                  >
                    <ArrowUpIcon />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => handleMoveVideoDown(index)}
                    disabled={index === orderedVideos.length - 1}
                  >
                    <ArrowDownIcon />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => handleRemoveVideoFromOrder(index)}
                    color="error"
                  >
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </CardContent>
  </Card>
)}
```

#### D. Replace Video Player When Sequence is Active

```typescript
{testRunning && multiVideoMode && sequenceId && (
  <Box>
    <SequentialVideoPlayer
      videos={orderedVideos}
      config={{
        autoAdvance: true,
        loopPlayback: false,
      }}
      onVideoStart={(video, index) => {
        console.log(`Starting video ${index + 1}/${orderedVideos.length}: ${video.filename}`);
      }}
      onVideoEnd={(video, index) => {
        console.log(`Completed video ${index + 1}/${orderedVideos.length}: ${video.filename}`);
      }}
      onPlaybackComplete={() => {
        console.log('All videos completed');
        // Navigate to results
        navigate(`/hil-results?sequence_id=${sequenceId}`);
      }}
      onError={(error, video) => {
        console.error('Video error:', error, video);
        showSnackbar(`Video error: ${error}`, 'error');
      }}
      autoStart={true}
      showControls={true}
      showProgress={true}
      syncWithLabJack={true}
    />
  </Box>
)}
```

### 5. Navigation After Test

Update the stop test logic to navigate to results with sequence_id:

```typescript
const onSequenceComplete = () => {
  setTestRunning(false);
  if (sequenceId) {
    navigate(`/hil-results?sequence_id=${sequenceId}`);
  }
};
```

### 6. Error Handling

Add comprehensive error handling for multi-video mode:

```typescript
// Video load failure - mark as failed, continue to next
const handleVideoLoadError = (video: VideoFile, error: string) => {
  console.error(`Video load failed: ${video.filename}`, error);
  showSnackbar(`Video ${video.filename} failed to load, continuing...`, 'warning');

  // Log to backend
  apiService.post('/api/video-sequences/video-failed', {
    sequence_id: sequenceId,
    video_id: video.id,
    error: error
  });
};

// LabJack disconnection during test
const handleLabJackDisconnect = () => {
  showSnackbar('LabJack disconnected! Attempting reconnection...', 'error');

  // Attempt reconnection
  setTimeout(async () => {
    try {
      const status = await apiService.checkLabJackStatus();
      if (status.connected) {
        showSnackbar('LabJack reconnected successfully', 'success');
      }
    } catch (err) {
      showSnackbar('Failed to reconnect LabJack', 'error');
    }
  }, 2000);
};
```

### 7. Validation Updates

Update `canStartTest()` function:

```typescript
const canStartTest = (): { canStart: boolean; reasons: string[] } => {
  const reasons: string[] = [];

  if (!selectedProject) {
    reasons.push('No project selected');
  }

  if (multiVideoMode) {
    if (orderedVideos.length === 0) {
      reasons.push('No videos selected for sequence');
    }
  } else {
    if (validatedVideos.length === 0) {
      reasons.push('No validated videos available');
    }
    if (expectedDetections.length === 0) {
      reasons.push('No ground truth data loaded');
    }
  }

  if (!labjackStatus.connected) {
    reasons.push('LabJack not connected');
  }

  return {
    canStart: reasons.length === 0,
    reasons
  };
};
```

## Backend API Requirements

The following backend endpoints need to be implemented or exist:

1. **POST /api/video-sequences/start**
   - Input: `{ project_id, video_ids[], max_latency_ms, config }`
   - Output: `{ sequence_id, message }`

2. **GET /api/video-sequences/{sequence_id}/status**
   - Output: `{ current_video_index, total_videos, is_complete }`

3. **GET /api/video-sequences/{sequence_id}/results**
   - Output: Multi-video test results

4. **POST /api/video-sequences/stop**
   - Input: `{ sequence_id }`

5. **POST /api/video-sequences/video-failed**
   - Input: `{ sequence_id, video_id, error }`

## Testing Checklist

- [ ] Single video selection displays table with checkboxes
- [ ] Select all checkbox works correctly
- [ ] Videos can be added to test queue
- [ ] Video ordering (up/down) works
- [ ] Videos can be removed from queue
- [ ] Total duration calculation is accurate
- [ ] Start test validates: project, videos, LabJack
- [ ] SequentialVideoPlayer loads and plays videos
- [ ] Auto-advance between videos works
- [ ] LabJack sync works during sequence
- [ ] Video load errors are handled gracefully
- [ ] Test stops on user request
- [ ] Results page loads with sequence_id
- [ ] Mode toggle preserves state appropriately

## File Locations

- Main component: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx`
- Sequential player: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/SequentialVideoPlayer.tsx`
- Video service: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/videoProjectService.ts`
- API service: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/api.ts`

## Notes

- The implementation maintains backward compatibility with single-video mode
- Multi-video mode uses the SequentialVideoPlayer component
- All validations are performed before test start
- Error handling allows test to continue on individual video failures
- Results are tracked per-video and aggregated for the full sequence