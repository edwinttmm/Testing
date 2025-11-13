#!/bin/bash

# Video Popup Implementation Script
# This script adds video popup functionality to HILResults.tsx

set -e

cd /home/rigade/Testing/ai-model-validation-platform/frontend/src/pages

# Backup file
cp HILResults.tsx HILResults.tsx.pre-popup-backup

# 1. Add Dialog imports
sed -i '/FormControl$/a\  Dialog,\n  DialogTitle,\n  DialogContent' HILResults.tsx

# 2. Add CloseIcon import
sed -i "s/ArrowBack as ArrowBackIcon/ArrowBack as ArrowBackIcon, Close as CloseIcon/" HILResults.tsx

# 3. Add video popup state variables after availableVideos state
sed -i '/const \[availableVideos/a\  \n  \/\/ Video popup state\n  const [videoDialogOpen, setVideoDialogOpen] = useState(false);\n  const [selectedDetection, setSelectedDetection] = useState<EnhancedDetectionEvent | null>(null);\n  const [playbackVideoUrl, setPlaybackVideoUrl] = useState<string>('\'');' HILResults.tsx

# 4. Create handleDetectionClick function file
cat > /tmp/handleDetectionClick.txt << 'EOF'

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
EOF

# Insert handleDetectionClick before videoMetadata useMemo
sed -i '/\/\/ Video metadata for timeline/r /tmp/handleDetectionClick.txt' HILResults.tsx

# 5. Add onClick prop to DetectionTableRow
sed -i 's/<DetectionTableRow$/<DetectionTableRow\n                    onClick={() => handleDetectionClick(detection)}/' HILResults.tsx

# 6. Create video dialog component file
cat > /tmp/videoDialog.txt << 'EOF'

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
EOF

# Insert video dialog before closing </Container>
sed -i '/^    <\/Container>$/i\' HILResults.tsx
sed -i '/^    <\/Container>$/r /tmp/videoDialog.txt' HILResults.tsx

# Clean up temp files
rm /tmp/handleDetectionClick.txt /tmp/videoDialog.txt

echo "✅ Video popup functionality added successfully!"
echo "Changes made to: HILResults.tsx"
echo "Backup created at: HILResults.tsx.pre-popup-backup"
