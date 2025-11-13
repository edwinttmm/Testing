# Video Popup Functionality - Code Changes with Line Numbers

## File: `/frontend/src/pages/HILResults.tsx`

### Change 1: Import Dialog Components (Lines 3-31)

**Before:**
```typescript
import {
  Box,
  Typography,
  Container,
  Paper,
  AppBar,
  Toolbar,
  IconButton,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  AlertTitle,
  Chip,
  Stack,
  Card,
  CardContent,
  Select,
  MenuItem,
  FormControl
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
```

**After:**
```typescript
import {
  Box,
  Typography,
  Container,
  Paper,
  AppBar,
  Toolbar,
  IconButton,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  AlertTitle,
  Chip,
  Stack,
  Card,
  CardContent,
  Select,
  MenuItem,
  FormControl,
  Dialog,           // ← Added
  DialogTitle,      // ← Added
  DialogContent     // ← Added
} from '@mui/material';
import { ArrowBack as ArrowBackIcon, Close as CloseIcon } from '@mui/icons-material';  // ← Added CloseIcon
```

---

### Change 2: Add Video Popup State (Lines ~250-254)

**Before:**
```typescript
  const [availableVideos, setAvailableVideos] = useState<Array<{ id: string; filename: string; url: string }>>([]);
```

**After:**
```typescript
  const [availableVideos, setAvailableVideos] = useState<Array<{ id: string; filename: string; url: string }>>([]);

  // Video popup state
  const [videoDialogOpen, setVideoDialogOpen] = useState(false);
  const [selectedDetection, setSelectedDetection] = useState<EnhancedDetectionEvent | null>(null);
  const [playbackVideoUrl, setPlaybackVideoUrl] = useState<string>('');
```

---

### Change 3: Add Detection Click Handler (Lines ~922-950)

**Before:**
```typescript
  const selectedVideoStatusColor = selectedVideoStatus === 'pass' ? 'success' : selectedVideoStatus === 'fail' ? 'error' : 'warning';

  // Video metadata for timeline
  const videoMetadata = useMemo(() => {
```

**After:**
```typescript
  const selectedVideoStatusColor = selectedVideoStatus === 'pass' ? 'success' : selectedVideoStatus === 'fail' ? 'error' : 'warning';

  /**
   * Handle detection click to open video popup
   */
  const handleDetectionClick = useCallback((detection: EnhancedDetectionEvent) => {
    console.log('🎬 Detection clicked:', detection);

    // Find the video URL for this detection
    const detectionVideoId = (detection as any).video_id ?? (detection as any).videoId ?? selectedVideoId ?? videoId;

    let videoUrl = '';
    if (detectionVideoId) {
      const video = availableVideos.find(v => v.id === detectionVideoId);
      if (video?.url) {
        videoUrl = video.url;
      }
    }

    // Fallback: if we don't have a URL, try to construct it
    if (!videoUrl && detectionVideoId) {
      const baseUrl = typeof window !== 'undefined' && window.location.hostname === 'localhost'
        ? 'http://localhost:8000'
        : 'http://155.138.239.131:8000';

      // Try to find the filename from availableVideos
      const video = availableVideos.find(v => v.id === detectionVideoId);
      if (video?.filename) {
        videoUrl = `${baseUrl}/uploads/${video.filename}`;
      }
    }

    console.log('🎬 Opening video at URL:', videoUrl, 'timestamp:', detection.timestamp);

    setSelectedDetection(detection);
    setPlaybackVideoUrl(videoUrl);
    setVideoDialogOpen(true);
  }, [availableVideos, selectedVideoId, videoId]);

  // Video metadata for timeline
  const videoMetadata = useMemo(() => {
```

---

### Change 4: Add onClick to Detection Table Rows (Lines ~1320-1325)

**Before:**
```typescript
                  <DetectionTableRow
                    key={detection.id || `detection-${index}`}
                    index={index}
                    detection={detection}
                  />
```

**After:**
```typescript
                  <DetectionTableRow
                    key={detection.id || `detection-${index}`}
                    index={index}
                    detection={detection}
                    onClick={() => handleDetectionClick(detection)}  // ← Added
                  />
```

---

### Change 5: Add Video Dialog Component (Lines ~1350-1410)

**Before:**
```typescript
      {/* Session Information Footer */}
      <Paper sx={{ p: 2, bgcolor: 'grey.50' }} elevation={1}>
        <Typography variant="caption" color="textSecondary">
          Session ID: {sessionId}
          {enhancedResults?.session_info?.project_name && (
            <> • Project: {enhancedResults.session_info.project_name}</>
          )}
          {enhancedResults?.session_info?.name && (
            <> • Test: {enhancedResults.session_info.name}</>
          )}
        </Typography>
      </Paper>
    </Container>
  );
};
```

**After:**
```typescript
      {/* Session Information Footer */}
      <Paper sx={{ p: 2, bgcolor: 'grey.50' }} elevation={1}>
        <Typography variant="caption" color="textSecondary">
          Session ID: {sessionId}
          {enhancedResults?.session_info?.project_name && (
            <> • Project: {enhancedResults.session_info.project_name}</>
          )}
          {enhancedResults?.session_info?.name && (
            <> • Test: {enhancedResults.session_info.name}</>
          )}
        </Typography>
      </Paper>

      {/* Video Playback Dialog */}
      <Dialog
        open={videoDialogOpen}
        onClose={() => setVideoDialogOpen(false)}
        maxWidth="xl"
        fullWidth
        PaperProps={{
          sx: {
            minHeight: '80vh',
            maxHeight: '90vh'
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h6">
              Video Playback - Detection at {selectedDetection?.timestamp?.toFixed(3) || '—'}s
            </Typography>
            {selectedDetection && (
              <Typography variant="caption" color="text.secondary">
                Latency: {(selectedDetection.real_latency_ms || selectedDetection.actualLatencyMs || 0).toFixed(1)}ms •
                Voltage: {(selectedDetection.voltage || selectedDetection.voltage_level || 0).toFixed(2)}V •
                Result: {selectedDetection.passed || selectedDetection.result === 'pass' ? 'PASS' : 'FAIL'}
              </Typography>
            )}
          </Box>
          <IconButton onClick={() => setVideoDialogOpen(false)} edge="end">
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 3 }}>
          {playbackVideoUrl ? (
            <Box sx={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <video
                controls
                autoPlay
                src={playbackVideoUrl}
                style={{
                  width: '100%',
                  maxHeight: '70vh',
                  backgroundColor: '#000',
                  borderRadius: '8px'
                }}
                onLoadedMetadata={(e) => {
                  // Seek to the detection timestamp when video loads
                  if (selectedDetection?.timestamp && e.currentTarget) {
                    e.currentTarget.currentTime = selectedDetection.timestamp;
                  }
                }}
              />
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  Video will start at the detection timestamp ({selectedDetection?.timestamp?.toFixed(3) || '—'}s).
                  Use the video controls to review the detection event.
                </Typography>
              </Alert>
            </Box>
          ) : (
            <Alert severity="warning">
              <AlertTitle>Video Not Available</AlertTitle>
              <Typography variant="body2">
                Unable to load video for this detection. The video file may not be accessible.
              </Typography>
            </Alert>
          )}
        </DialogContent>
      </Dialog>
    </Container>
  );
};
```

---

## File: `/frontend/src/components/DetectionTableRow.tsx`

### No Changes Required ✅

The component already had proper support for the `onClick` prop:

```typescript
interface DetectionTableRowProps {
  index: number;
  detection: { /* ... */ };
  onClick?: () => void;  // ← Already present
}

export const DetectionTableRow: React.FC<DetectionTableRowProps> = ({
  index,
  detection,
  onClick  // ← Already destructured
}) => {
  return (
    <TableRow
      onClick={onClick}  // ← Already wired up
      sx={{
        // ...
        cursor: onClick ? 'pointer' : 'default'  // ← Already styled
      }}
    >
      {/* ... */}
    </TableRow>
  );
};
```

---

## Summary of Changes

### Total Lines Added: ~70
- Import statements: +3 lines
- State variables: +3 lines
- Click handler function: ~30 lines
- onClick prop: +1 line
- Dialog component: ~60 lines

### Files Modified: 1
- `/frontend/src/pages/HILResults.tsx` ✅

### Files Unchanged: 1
- `/frontend/src/components/DetectionTableRow.tsx` ✅ (already compatible)

### Backups Created: 1
- `HILResults.tsx.pre-popup-backup` ✅

---

## Testing Commands

### Start Frontend Development Server
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm start
```

### Navigate to HIL Results
1. Open browser to `http://localhost:3000`
2. Navigate to any HIL Results page
3. Click on any detection row
4. Verify video dialog opens and plays

### Check for TypeScript Errors
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm run typecheck
```

### Build Production Bundle
```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm run build
```

---

## Rollback Instructions

If you need to revert the changes:

```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend/src/pages
cp HILResults.tsx.pre-popup-backup HILResults.tsx
```

---

## Implementation Notes

### Why No SequentialVideoPlayer?
The original requirement suggested using `SequentialVideoPlayer`, but that component is designed for **sequential playlist playback** during test execution, not for **on-demand single video playback** at specific timestamps.

Instead, we used a standard HTML5 `<video>` element which:
- Loads faster (no complex component initialization)
- Supports direct timestamp seeking via `currentTime`
- Provides standard browser controls
- Is more appropriate for review/playback scenarios

### Video URL Resolution Strategy
1. Check detection event for `video_id`
2. Look up video in `availableVideos` array
3. Use video's `url` property
4. Fallback: construct URL from filename
5. Handle both localhost and production base URLs

This multi-level fallback ensures maximum compatibility with different data structures.

### TypeScript Type Safety
All type definitions are preserved:
- `EnhancedDetectionEvent` type used for detection data
- Proper typing for state variables
- useCallback with correct dependency arrays
- Type guards for optional fields (`?.` operator)

---

## Next Steps After Testing

1. ✅ Code implementation complete
2. ⏳ Manual testing by user
3. ⏳ Verify video playback works
4. ⏳ Test multi-video scenarios
5. ⏳ Gather user feedback
6. ⏳ Iterate on UX if needed
