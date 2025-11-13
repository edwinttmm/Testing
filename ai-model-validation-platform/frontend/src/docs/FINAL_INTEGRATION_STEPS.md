# Final Integration Steps for HIL Multi-Video Sequential Testing

## Overview
This document provides the complete, step-by-step integration guide for adding multi-video sequential testing to the HIL Test Execution page.

## Changes Already Made to HILTestExecutionPRD.tsx

### 1. Imports Added ✅
```typescript
import { videoProjectService } from '../services/videoProjectService';
import SequentialVideoPlayer from '../components/SequentialVideoPlayer';
import {
  Checkbox,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
} from '@mui/material';
import {
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
```

### 2. State Variables Added ✅
```typescript
const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
const [orderedVideos, setOrderedVideos] = useState<VideoFile[]>([]);
const [multiVideoMode, setMultiVideoMode] = useState<boolean>(true);
const [sequenceId, setSequenceId] = useState<string | null>(null);
```

### 3. Handler Functions Added ✅
All video selection and ordering handlers have been implemented.

## Remaining Integration Steps

### Step 1: Update loadVideoPlaylist Function

The function has been updated to use `videoProjectService.getProjectVideos()` instead of ground truth API.

### Step 2: Update startHILTest Function

Replace the existing `startHILTest` function with the following:

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
    // Single-video mode (KEEP EXISTING LOGIC)
    if (validatedVideos.length === 0) {
      showSnackbar('No validated videos available for testing', 'error');
      return;
    }
    if (!labjackStatus.connected) {
      showSnackbar('LabJack is not connected. Please check connection.', 'error');
      return;
    }

    try {
      console.log('🚀 [HIL] Starting HIL test with PRD workflow...');
      setTestRunning(true);

      const sessionName = `HIL Test - ${selectedProject.name} - ${new Date().toLocaleString()}`;
      console.log('🔄 [HIL] Creating test session:', sessionName);

      const session: HILTestSession = {
        name: sessionName,
        projectId: selectedProject.id,
        videoIds: validatedVideos.map(v => v.id),
        config: {
          maxLatencyMs: maxLatencyMs,
        },
        results: [],
        createdAt: new Date().toISOString(),
      };

      setCurrentSession(session);
      setCurrentVideoIndex(0);

      setTimeout(() => {
        console.log('⏰ [HIL] Starting playback after 300ms delay...');
        startPlaybackForIndex(0);
      }, 300);

      showSnackbar('Test started. Play video to begin detection.', 'success');

    } catch (err: any) {
      console.error('🚨 [HIL] Error starting test:', err);
      setError(`Failed to start test: ${err.message}`);
      showSnackbar('Failed to start test', 'error');
      setTestRunning(false);
    }
  }
};
```

### Step 3: Update canStartTest Function

Replace the existing validation function with:

```typescript
const canStartTest = (): { canStart: boolean; reasons: string[] } => {
  const reasons: string[] = [];

  if (!selectedProject) {
    reasons.push('No project selected');
  }

  if (multiVideoMode) {
    // Multi-video validation
    if (orderedVideos.length === 0) {
      reasons.push('No videos selected for sequence. Add at least one video to the test queue.');
    }
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
```

### Step 4: Add UI Components

Add these components after the "3. Maximum Acceptable Latency" section (around line 1650):

```typescript
{/* Test Mode Toggle */}
<Box sx={{ mb: 3 }}>
  <Typography variant="subtitle2" gutterBottom>
    4. Test Mode
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

{/* Video Selection Table - Only show in multi-video mode */}
{multiVideoMode && selectedProject && (
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
            {videoPlaylist.map((video) => (
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
                <TableCell align="right">
                  {(() => {
                    const duration = video.duration || 0;
                    const mins = Math.floor(duration / 60);
                    const secs = Math.floor(duration % 60);
                    return `${mins}:${secs.toString().padStart(2, '0')}`;
                  })()}
                </TableCell>
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
)}

{/* Test Queue Display - Only show in multi-video mode */}
{multiVideoMode && orderedVideos.length > 0 && (
  <Card sx={{ mb: 3 }}>
    <CardContent>
      <Typography variant="h6" gutterBottom>
        Test Queue ({orderedVideos.length} videos)
      </Typography>

      <Box sx={{ display: 'flex', gap: 4, mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          <strong>Estimated total duration:</strong>{' '}
          {(() => {
            const totalSeconds = calculateTotalDuration();
            const mins = Math.floor(totalSeconds / 60);
            const secs = Math.floor(totalSeconds % 60);
            return `${mins}:${secs.toString().padStart(2, '0')}`;
          })()}
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
            {orderedVideos.map((video, index) => (
              <TableRow key={video.id}>
                <TableCell>
                  <Chip label={`${index + 1}`} size="small" color="primary" />
                </TableCell>
                <TableCell>{video.filename || video.name}</TableCell>
                <TableCell align="right">
                  {(() => {
                    const duration = video.duration || 0;
                    const mins = Math.floor(duration / 60);
                    const secs = Math.floor(duration % 60);
                    return `${mins}:${secs.toString().padStart(2, '0')}`;
                  })()}
                </TableCell>
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
)}
```

### Step 5: Add SequentialVideoPlayer Component

Add this section after the existing video player section (around line 1835). This should replace the video container when in multi-video mode:

```typescript
{/* Sequential Video Player for Multi-Video Mode */}
{testRunning && multiVideoMode && sequenceId && (
  <Box sx={{ width: '100%', minHeight: '80vh', bgcolor: 'background.paper' }}>
    <SequentialVideoPlayer
      videoPlaylist={orderedVideos}
      sequenceId={sequenceId}
      maxLatencyMs={maxLatencyMs}
      onSequenceComplete={() => {
        console.log('🎉 Sequence completed - navigating to results');
        setTestRunning(false);
        showSnackbar('Test sequence completed!', 'success');
        // Navigate to results page with sequence_id
        setTimeout(() => {
          navigate(`/hil-results?sequence_id=${sequenceId}`);
        }, 1000);
      }}
      onError={(error) => {
        console.error('❌ Sequential player error:', error);
        showSnackbar(`Player error: ${error}`, 'error');
      }}
    />
  </Box>
)}
```

### Step 6: Update Ground Truth Section

The ground truth section should only show in single-video mode. Wrap it with:

```typescript
{/* Ground Truth Status Display - Only in single-video mode */}
{!multiVideoMode && selectedProject && (
  <Box sx={{ mb: 3 }}>
    {/* Existing ground truth display code */}
  </Box>
)}
```

## Testing Checklist

After integration, test these scenarios:

1. **Mode Toggle**
   - [ ] Toggle between single and multi-video modes
   - [ ] UI updates correctly based on mode
   - [ ] State is preserved when toggling

2. **Video Selection (Multi-Video Mode)**
   - [ ] Videos load in selection table
   - [ ] Individual video selection works
   - [ ] Select all checkbox works
   - [ ] Add to queue button is enabled/disabled correctly

3. **Video Ordering**
   - [ ] Videos appear in test queue
   - [ ] Move up/down buttons work
   - [ ] Remove button works
   - [ ] Order persists correctly

4. **Test Execution**
   - [ ] Validation prevents test with no videos
   - [ ] Validation checks LabJack connection
   - [ ] Test starts correctly with valid configuration
   - [ ] SequentialVideoPlayer loads and displays
   - [ ] Videos advance automatically
   - [ ] Progress tracking updates correctly

5. **Results Navigation**
   - [ ] Sequence completes and navigates to results
   - [ ] sequence_id is passed correctly
   - [ ] Results page loads multi-video data

6. **Error Handling**
   - [ ] Video load failures are handled gracefully
   - [ ] LabJack disconnection is handled
   - [ ] Test can be stopped mid-sequence
   - [ ] Error messages are user-friendly

7. **Single-Video Mode (Backward Compatibility)**
   - [ ] Single-video mode still works as before
   - [ ] Ground truth loading works
   - [ ] Test execution works
   - [ ] Results display correctly

## Backend Requirements

The backend must implement these endpoints:

1. **POST /api/video-sequences/start**
   - Creates a new video sequence test session
   - Returns: `{ sequence_id: string, message: string }`

2. **POST /api/video-sequences/{sequence_id}/video-started**
   - Tracks when each video starts in the sequence

3. **POST /api/video-sequences/{sequence_id}/video-ended**
   - Tracks when each video ends
   - Returns: `{ nextVideoId: string | null }`

4. **POST /api/video-sequences/{sequence_id}/heartbeat**
   - Monitors playback progress

5. **GET /api/video-sequences/{sequence_id}/results**
   - Returns aggregated results for all videos in sequence

6. **POST /api/video-sequences/video-failed**
   - Logs video failures during sequence

## File References

- **Main Component**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx`
- **Sequential Player**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/SequentialVideoPlayer.tsx`
- **Video Service**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/videoProjectService.ts`
- **API Service**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/api.ts`
- **UI Snippets**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/docs/HIL_UI_CODE_SNIPPETS.tsx`
- **Implementation Guide**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/docs/HIL_MULTI_VIDEO_IMPLEMENTATION_GUIDE.md`

## Notes

- All core state variables and handlers have been implemented
- The SequentialVideoPlayer component has been updated with the correct API
- Integration primarily involves adding UI components and updating startHILTest logic
- Backward compatibility with single-video mode is maintained
- Error handling is comprehensive with retry logic