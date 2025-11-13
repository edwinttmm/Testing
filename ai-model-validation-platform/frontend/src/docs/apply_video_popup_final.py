#!/usr/bin/env python3
"""
Carefully applies video popup functionality to HILResults.tsx
This script makes surgical, precise changes to avoid syntax errors.
"""

import os

file_path = '/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx'

# Read original content
with open(file_path, 'r') as f:
    lines = f.readlines()

# Track changes
changes_made = []

# 1. Add Dialog imports (after FormControl, before closing brace)
for i, line in enumerate(lines):
    if line.strip() == 'FormControl':
        # Insert Dialog imports after FormControl
        lines[i] = line.rstrip() + ',\n  Dialog,\n  DialogTitle,\n  DialogContent\n'
        changes_made.append(f"Line {i+1}: Added Dialog imports")
        break

# 2. Add CloseIcon import
for i, line in enumerate(lines):
    if "import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';" in line:
        lines[i] = "import { ArrowBack as ArrowBackIcon, Close as CloseIcon } from '@mui/icons-material';\n"
        changes_made.append(f"Line {i+1}: Added CloseIcon import")
        break

# 3. Add video popup state after availableVideos
for i, line in enumerate(lines):
    if 'const [availableVideos, setAvailableVideos] = useState' in line:
        # Find the end of this line
        lines[i+1] = lines[i+1].rstrip() + '\n\n  // Video popup state\n  const [videoDialogOpen, setVideoDialogOpen] = useState(false);\n  const [selectedDetection, setSelectedDetection] = useState<EnhancedDetectionEvent | null>(null);\n  const [playbackVideoUrl, setPlaybackVideoUrl] = useState<string>(\'\');\n'
        changes_made.append(f"Line {i+2}: Added video popup state")
        break

# 4. Add handleDetectionClick function before "// Video metadata for timeline"
for i, line in enumerate(lines):
    if '// Video metadata for timeline' in line:
        # Insert function before this comment
        handler_code = '''
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

'''
        lines[i] = handler_code + line
        changes_made.append(f"Line {i+1}: Added handleDetectionClick function")
        break

# 5. Add onClick to DetectionTableRow
for i, line in enumerate(lines):
    if '<DetectionTableRow' in line:
        # Find the closing /> or >
        j = i
        while j < len(lines) and '/>' not in lines[j] and (not lines[j].strip().startswith('>')):
            j += 1

        if j < len(lines):
            # Insert onClick before closing
            if '/>' in lines[j]:
                indent = '                    '
                lines[j] = indent + 'onClick={() => handleDetectionClick(detection)}\n' + lines[j]
                changes_made.append(f"Line {j+1}: Added onClick prop to DetectionTableRow")
            break

# 6. Add Video Dialog before closing </Container>
for i in range(len(lines)-1, -1, -1):
    if '</Container>' in lines[i] and '  );' in lines[i+1] and '};' in lines[i+2]:
        # Insert dialog before </Container>
        dialog_code = '''
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

'''
        lines[i] = dialog_code + lines[i]
        changes_made.append(f"Line {i+1}: Added Video Dialog component")
        break

# Write modified content
with open(file_path, 'w') as f:
    f.writelines(lines)

# Print summary
print("✅ Video popup functionality applied successfully!")
print("\nChanges made:")
for change in changes_made:
    print(f"  - {change}")
print(f"\nTotal modifications: {len(changes_made)}")
