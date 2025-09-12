import React, { useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Slider,
  Switch,
  FormControlLabel,
  Grid,
  Chip,
  LinearProgress,
  Alert,
  CircularProgress,
  Input,
  Divider,
  Snackbar,
  Badge,
  Tooltip,
  ButtonGroup
} from '@mui/material';
import { 
  PlayArrow, 
  Pause, 
  ZoomIn, 
  ZoomOut, 
  CenterFocusStrong, 
  Upload,
  Refresh,
  Download,
  Clear,
  Warning,
  CheckCircle,
  Error,
  FastForward,
  FastRewind,
  SkipNext,
  SkipPrevious,
  Fullscreen,
  GridOn,
  GridOff,
  Timeline,
  Speed,
  Memory,
  Analytics
} from '@mui/icons-material';
import { useDetection } from '../hooks/useDetection';
import { BoundaryBox } from '../services/detectionApi';
import ApiHealthIndicator from '../components/detection/ApiHealthIndicator';
import { DetectionErrorBoundary } from '../components/detection/DetectionErrorBoundary';

/**
 * Real Frame 80 Pedestrian Detection Interface
 * Connects to backend API at localhost:8000 for actual detection processing
 */
const BoundaryBoxDemoContent: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showApiHealth, setShowApiHealth] = React.useState<boolean>(true);
  const [demoMode, setDemoMode] = React.useState<boolean>(false);
  const [showSnackbar, setShowSnackbar] = React.useState<boolean>(false);
  const [snackbarMessage, setSnackbarMessage] = React.useState<string>('');
  const [realTimeMode, setRealTimeMode] = React.useState<boolean>(false);
  const [fullscreen, setFullscreen] = React.useState<boolean>(false);
  
  const {
    // State
    videoFile,
    videoMetadata,
    currentFrame,
    isPlaying,
    detections,
    isDetecting,
    detectionError,
    frame80Data,
    frame80Detections,
    frame80Processed,
    apiStatus,
    apiMessage,
    selectedBox,
    snapToGrid,
    gridSize,
    zoom,
    processingTime,
    frameRate,
    // Actions
    loadVideo,
    setCurrentFrame,
    setIsPlaying,
    detectCurrentFrame,
    detectFrame80,
    clearDetections,
    setSelectedBox,
    setSnapToGrid,
    setGridSize,
    setZoom,
    exportDetections,
    resetState,
    startRealTimeDetection,
    stopRealTimeDetection
  } = useDetection();

  // Demo pedestrian detection data for Frame 80 with 99% confidence at 0,0 100x100
  const demoFrame80Detection: BoundaryBox = {
    id: 'demo_pedestrian_80_99',
    type: 'pedestrian',
    x: 0,
    y: 0,
    width: 100,
    height: 100,
    confidence: 0.99,
    color: '#ff4444',
    timestamp: Date.now(),
    frameNumber: 80
  };

  // Handle video file upload with Frame 80 auto-detection
  const handleVideoUpload = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      try {
        await loadVideo(file);
        setSnackbarMessage('Video loaded successfully! Automatically navigating to Frame 80...');
        setShowSnackbar(true);
        
        // Auto-navigate to Frame 80 and process
        setTimeout(() => {
          setCurrentFrame(80);
          if (demoMode) {
            // In demo mode, add the demo detection
            clearDetections();
            // This would be added via the detection system in a real implementation
          }
        }, 1000);
      } catch (error) {
        setSnackbarMessage(`Failed to load video: ${error instanceof Error ? error.message : 'Unknown error'}`);
        setShowSnackbar(true);
      }
    }
  }, [loadVideo, setCurrentFrame, clearDetections, demoMode]);

  // Handle demo mode toggle
  const handleDemoMode = useCallback(() => {
    const newDemoMode = !demoMode;
    setDemoMode(newDemoMode);
    
    if (newDemoMode && currentFrame === 80) {
      // Add demo detection for Frame 80
      setSnackbarMessage('Demo mode enabled: Showing 99% confidence pedestrian detection at (0,0) 100×100');
      setShowSnackbar(true);
    } else if (!newDemoMode) {
      setSnackbarMessage('Demo mode disabled: Using real API detection');
      setShowSnackbar(true);
    }
  }, [demoMode, currentFrame]);

  // Handle real-time mode toggle
  const handleRealTimeMode = useCallback(() => {
    const newRealTimeMode = !realTimeMode;
    setRealTimeMode(newRealTimeMode);
    
    if (newRealTimeMode) {
      startRealTimeDetection();
      setSnackbarMessage('Real-time detection started');
    } else {
      stopRealTimeDetection();
      setSnackbarMessage('Real-time detection stopped');
    }
    setShowSnackbar(true);
  }, [realTimeMode, startRealTimeDetection, stopRealTimeDetection]);

  // Frame navigation helpers
  const goToNextFrame = useCallback(() => {
    const nextFrame = Math.min((videoMetadata?.totalFrames || 100) - 1, currentFrame + 1);
    setCurrentFrame(nextFrame);
  }, [currentFrame, videoMetadata, setCurrentFrame]);

  const goToPrevFrame = useCallback(() => {
    const prevFrame = Math.max(0, currentFrame - 1);
    setCurrentFrame(prevFrame);
  }, [currentFrame, setCurrentFrame]);

  const skipFrames = useCallback((amount: number) => {
    const newFrame = Math.max(0, Math.min((videoMetadata?.totalFrames || 100) - 1, currentFrame + amount));
    setCurrentFrame(newFrame);
  }, [currentFrame, videoMetadata, setCurrentFrame]);

  // Canvas drawing effect with real detection data
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size based on video metadata or default
    const canvasWidth = videoMetadata?.width || 800;
    const canvasHeight = videoMetadata?.height || 450;
    canvas.width = canvasWidth;
    canvas.height = canvasHeight;

    // Clear canvas
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw video frame if available
    if (frame80Data && currentFrame === 80) {
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        drawDetections();
      };
      img.src = frame80Data.imageData;
    } else {
      drawDetections();
    }

    function drawDetections() {
      // Draw grid if enabled
      if (snapToGrid) {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = 1;
        for (let x = 0; x < canvas.width; x += gridSize) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, canvas.height);
          ctx.stroke();
        }
        for (let y = 0; y < canvas.height; y += gridSize) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(canvas.width, y);
          ctx.stroke();
        }
      }

      // Use current detections, Frame 80 specific detections, or demo data
      let currentDetections = currentFrame === 80 && frame80Detections.length > 0 
        ? frame80Detections 
        : detections;

      // Add demo detection for Frame 80 if in demo mode
      if (demoMode && currentFrame === 80) {
        currentDetections = [...currentDetections, demoFrame80Detection];
      }

      // Draw boundary boxes with enhanced visualization
      currentDetections.forEach((box: BoundaryBox) => {
        ctx.strokeStyle = box.color;
        ctx.lineWidth = selectedBox === box.id ? 4 : 2;
        ctx.strokeRect(box.x * zoom, box.y * zoom, box.width * zoom, box.height * zoom);
        
        // Draw confidence label with background
        const confidence = `${(box.confidence * 100).toFixed(0)}%`;
        const labelX = box.x * zoom;
        const labelY = box.y * zoom - 5;
        
        ctx.font = '12px Arial';
        const textWidth = ctx.measureText(confidence).width;
        
        // Background for label
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(labelX, labelY - 15, textWidth + 8, 18);
        
        // Label text
        ctx.fillStyle = box.color;
        ctx.fillText(confidence, labelX + 4, labelY - 2);
        
        // Type label
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(labelX, labelY + 5, ctx.measureText(box.type).width + 8, 18);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(box.type, labelX + 4, labelY + 18);
      });

      // Draw Frame 80 indicator
      if (currentFrame === 80) {
        ctx.fillStyle = 'rgba(255, 215, 0, 0.2)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#ffd700';
        ctx.font = 'bold 16px Arial';
        ctx.fillText('FRAME 80 - PEDESTRIAN DETECTION', 10, 30);
        
        if (frame80Processed) {
          ctx.fillStyle = '#00ff00';
          ctx.fillText('✓ PROCESSED', 10, 55);
        }
      }

      // Draw loading indicator
      if (isDetecting) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('PROCESSING...', canvas.width / 2, canvas.height / 2);
        ctx.textAlign = 'left';
      }
    }
  }, [currentFrame, snapToGrid, gridSize, selectedBox, zoom, detections, frame80Data, frame80Detections, frame80Processed, isDetecting, videoMetadata]);

  // Handle canvas click for box selection
  const handleCanvasClick = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (event.clientX - rect.left) * scaleX / zoom;
    const y = (event.clientY - rect.top) * scaleY / zoom;

    // Use current detections, Frame 80 specific detections, or demo data
    let currentDetections = currentFrame === 80 && frame80Detections.length > 0 
      ? frame80Detections 
      : detections;

    // Add demo detection for Frame 80 if in demo mode
    if (demoMode && currentFrame === 80) {
      currentDetections = [...currentDetections, demoFrame80Detection];
    }

    // Check if click is inside any boundary box
    const clickedBox = currentDetections.find((box: BoundaryBox) => 
      x >= box.x && x <= box.x + box.width &&
      y >= box.y && y <= box.y + box.height
    );

    setSelectedBox(clickedBox ? clickedBox.id : null);
  }, [currentFrame, frame80Detections, detections, zoom, setSelectedBox]);

  // Handle export
  const handleExport = useCallback(() => {
    const data = exportDetections();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `frame80_detections_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [exportDetections]);

  // Get API status icon
  const getApiStatusIcon = () => {
    switch (apiStatus) {
      case 'healthy': return <CheckCircle color="success" />;
      case 'unhealthy': return <Error color="error" />;
      default: return <CircularProgress size={20} />;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        🎯 Real Frame 80 Pedestrian Detection
      </Typography>

      {/* API Health Status */}
      {showApiHealth && (
        <Box sx={{ mb: 3 }}>
          <ApiHealthIndicator 
            baseUrl="http://localhost:8000"
            refreshInterval={10000}
            onHealthChange={(status) => {
              console.log('API Health Status:', status);
            }}
          />
        </Box>
      )}

      {/* Mode Controls */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>Detection Modes</Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <FormControlLabel
              control={
                <Switch
                  checked={demoMode}
                  onChange={handleDemoMode}
                  color="warning"
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  Demo Mode
                  {demoMode && <Chip label="99% Pedestrian" size="small" color="warning" />}
                </Box>
              }
            />
            
            <FormControlLabel
              control={
                <Switch
                  checked={realTimeMode}
                  onChange={handleRealTimeMode}
                  color="primary"
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  Real-time Detection
                  {realTimeMode && <Badge color="success" variant="dot">Live</Badge>}
                </Box>
              }
            />

            <FormControlLabel
              control={
                <Switch
                  checked={showApiHealth}
                  onChange={(e) => setShowApiHealth(e.target.checked)}
                />
              }
              label="Show API Health"
            />

            <Button
              variant="outlined"
              size="small"
              onClick={() => setFullscreen(!fullscreen)}
              startIcon={<Fullscreen />}
            >
              {fullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Video Upload */}
      {!videoFile && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Upload Video for Analysis</Typography>
            <Button
              variant="contained"
              startIcon={<Upload />}
              onClick={() => fileInputRef.current?.click()}
              sx={{ mb: 2 }}
            >
              Select Video File
            </Button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleVideoUpload}
              accept="video/*"
              style={{ display: 'none' }}
            />
            <Typography variant="body2" color="text.secondary">
              Supported formats: MP4, WebM, AVI, MOV (max 100MB)
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Detection Error */}
      {detectionError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSelectedBox(null)}>
          {detectionError}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Main Canvas */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              {/* Video Info */}
              {videoMetadata && (
                <Box sx={{ mb: 2, p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
                  <Typography variant="body2">
                    Video: {videoMetadata.width}×{videoMetadata.height} | 
                    {videoMetadata.duration.toFixed(1)}s | 
                    {videoMetadata.totalFrames} frames
                  </Typography>
                </Box>
              )}
              
              <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                style={{
                  border: currentFrame === 80 ? '3px solid #ffd700' : '2px solid #333',
                  cursor: 'crosshair',
                  width: '100%',
                  maxWidth: '800px',
                  height: 'auto',
                  opacity: isDetecting ? 0.7 : 1
                }}
              />
              
              {/* Video Controls */}
              <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                {/* Playback Controls */}
                <ButtonGroup variant="outlined">
                  <Button
                    onClick={() => skipFrames(-10)}
                    disabled={!videoFile || isDetecting}
                    startIcon={<FastRewind />}
                    size="small"
                  >
                    -10
                  </Button>
                  <Button
                    onClick={goToPrevFrame}
                    disabled={!videoFile || isDetecting}
                    startIcon={<SkipPrevious />}
                    size="small"
                  >
                    Prev
                  </Button>
                  <Button
                    variant="contained"
                    onClick={() => setIsPlaying(!isPlaying)}
                    startIcon={isPlaying ? <Pause /> : <PlayArrow />}
                    disabled={!videoFile || isDetecting}
                  >
                    {isPlaying ? 'Pause' : 'Play'}
                  </Button>
                  <Button
                    onClick={goToNextFrame}
                    disabled={!videoFile || isDetecting}
                    startIcon={<SkipNext />}
                    size="small"
                  >
                    Next
                  </Button>
                  <Button
                    onClick={() => skipFrames(10)}
                    disabled={!videoFile || isDetecting}
                    startIcon={<FastForward />}
                    size="small"
                  >
                    +10
                  </Button>
                </ButtonGroup>
                
                {/* Detection Controls */}
                <Button
                  variant="outlined"
                  onClick={detectCurrentFrame}
                  disabled={!videoFile || isDetecting}
                  startIcon={isDetecting ? <CircularProgress size={16} /> : <Refresh />}
                  color="primary"
                >
                  Detect Current
                </Button>
                
                <Button
                  variant={currentFrame === 80 ? 'contained' : 'outlined'}
                  color={currentFrame === 80 ? 'warning' : 'primary'}
                  onClick={() => setCurrentFrame(80)}
                  disabled={!videoFile}
                  startIcon={currentFrame === 80 ? <Analytics /> : <Timeline />}
                >
                  Frame 80
                  {currentFrame === 80 && <Chip label="ACTIVE" size="small" sx={{ ml: 1 }} />}
                </Button>
              </Box>

              {/* Frame Slider */}
              <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="body2" sx={{ minWidth: 80 }}>
                  Frame: {currentFrame}
                </Typography>
                <Slider
                  value={currentFrame}
                  onChange={(_, value) => setCurrentFrame(value as number)}
                  min={0}
                  max={videoMetadata?.totalFrames || 99}
                  sx={{ flexGrow: 1 }}
                  disabled={!videoFile || isDetecting}
                  marks={[
                    { value: 0, label: '0' },
                    { value: 80, label: 'F80' },
                    { value: videoMetadata?.totalFrames || 99, label: `${videoMetadata?.totalFrames || 99}` }
                  ]}
                  valueLabelDisplay="auto"
                />
                <Typography variant="body2" sx={{ minWidth: 60 }}>
                  / {videoMetadata?.totalFrames || 99}
                </Typography>
              </Box>
              
              {/* Zoom Controls */}
              <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body2" sx={{ minWidth: 80 }}>
                  Zoom: {(zoom * 100).toFixed(0)}%
                </Typography>
                <ButtonGroup variant="outlined" size="small">
                  <Button onClick={() => setZoom(zoom / 1.2)} startIcon={<ZoomOut />}>
                    Zoom Out
                  </Button>
                  <Button onClick={() => setZoom(1)} startIcon={<CenterFocusStrong />}>
                    Reset (100%)
                  </Button>
                  <Button onClick={() => setZoom(zoom * 1.2)} startIcon={<ZoomIn />}>
                    Zoom In
                  </Button>
                </ButtonGroup>
                <Slider
                  value={zoom}
                  onChange={(_, value) => setZoom(value as number)}
                  min={0.1}
                  max={5}
                  step={0.1}
                  sx={{ width: 100, ml: 2 }}
                  valueLabelDisplay="auto"
                  valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                />
              </Box>
              
              {/* Action Buttons */}
              <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Button
                  variant="outlined"
                  startIcon={<Download />}
                  onClick={handleExport}
                  disabled={detections.length === 0}
                  size="small"
                >
                  Export
                </Button>
                
                <Button
                  variant="outlined"
                  startIcon={<Clear />}
                  onClick={clearDetections}
                  disabled={detections.length === 0}
                  size="small"
                >
                  Clear
                </Button>
                
                <Button
                  variant="outlined"
                  onClick={resetState}
                  size="small"
                >
                  Reset All
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Controls Panel */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Detection Controls</Typography>
              
              {/* Grid Controls */}
              <Box sx={{ mb: 3 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={snapToGrid}
                      onChange={(e) => setSnapToGrid(e.target.checked)}
                      icon={<GridOff />}
                      checkedIcon={<GridOn />}
                    />
                  }
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      Snap to Grid
                      {snapToGrid && <Chip label={`${gridSize}px`} size="small" color="primary" />}
                    </Box>
                  }
                />
                
                <Typography gutterBottom sx={{ mt: 2 }}>Grid Size: {gridSize}px</Typography>
                <Slider
                  value={gridSize}
                  onChange={(_, value) => setGridSize(value as number)}
                  min={5}
                  max={50}
                  step={5}
                  marks={[
                    { value: 5, label: '5px' },
                    { value: 20, label: '20px' },
                    { value: 50, label: '50px' }
                  ]}
                  valueLabelDisplay="auto"
                  disabled={!snapToGrid}
                />
              </Box>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="h6" gutterBottom>
                Detections ({(demoMode && currentFrame === 80 ? [...detections, demoFrame80Detection] : detections).length})
              </Typography>
              
              {/* Demo Mode Indicator */}
              {demoMode && currentFrame === 80 && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  <Typography variant="body2">
                    Demo Mode: Showing simulated 99% confidence pedestrian detection
                  </Typography>
                </Alert>
              )}
              
              {(demoMode && currentFrame === 80 ? [...detections, demoFrame80Detection] : detections).length === 0 && !demoMode && (
                <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                  No detections. {videoFile ? 'Click "Detect" to analyze current frame or enable Demo Mode.' : 'Upload a video to start.'}
                </Typography>
              )}
              
              {(demoMode && currentFrame === 80 ? [...detections, demoFrame80Detection] : detections).map((box: BoundaryBox) => (
                <Card 
                  key={box.id} 
                  variant="outlined" 
                  sx={{ 
                    mb: 1, 
                    border: selectedBox === box.id ? `2px solid ${box.color}` : undefined,
                    cursor: 'pointer',
                    '&:hover': { boxShadow: 2 }
                  }}
                  onClick={() => setSelectedBox(box.id)}
                >
                  <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {box.type}
                      </Typography>
                      <Chip 
                        label={`${(box.confidence * 100).toFixed(0)}%`}
                        size="small"
                        color={box.confidence >= 0.95 ? 'success' : box.confidence >= 0.8 ? 'warning' : 'error'}
                      />
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      Frame {box.frameNumber}: ({box.x},{box.y}) {box.width}×{box.height}
                      {snapToGrid && <Chip label="Grid Aligned" size="small" sx={{ ml: 1 }} />}
                    </Typography>
                    {box.confidence >= 0.99 && box.type === 'pedestrian' && (
                      <Box sx={{ mt: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        <Chip label="99% Confidence" size="small" color="success" />
                        {box.frameNumber === 80 && <Chip label="Frame 80 Target" size="small" color="warning" />}
                        {box.id === demoFrame80Detection.id && <Chip label="Demo Data" size="small" color="info" />}
                      </Box>
                    )}
                  </CardContent>
                </Card>
              ))}
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Speed />
                Performance Metrics
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Frame Rate</Typography>
                  <Typography variant="body2" color={frameRate >= 25 ? 'success.main' : frameRate >= 15 ? 'warning.main' : 'error.main'}>
                    {frameRate} FPS
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(100, (frameRate / 30) * 100)} 
                  color={frameRate >= 25 ? 'success' : frameRate >= 15 ? 'warning' : 'error'}
                  sx={{ mb: 1 }}
                />
              </Box>
              
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Processing Time</Typography>
                  <Typography variant="body2" color={processingTime <= 100 ? 'success.main' : processingTime <= 500 ? 'warning.main' : 'error.main'}>
                    {processingTime.toFixed(0)}ms
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(100, Math.max(0, 100 - (processingTime / 1000) * 100))} 
                  color={processingTime <= 100 ? 'success' : processingTime <= 500 ? 'warning' : 'error'}
                  sx={{ mb: 1 }}
                />
              </Box>
              
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2">Zoom Level</Typography>
                  <Typography variant="body2">{(zoom * 100).toFixed(0)}%</Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(100, (zoom / 2) * 100)} 
                  color="primary"
                  sx={{ mb: 1 }}
                />
              </Box>
              
              {/* Additional Metrics */}
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 2 }}>
                <Chip 
                  icon={<Memory />} 
                  label={`API: ${apiStatus}`} 
                  size="small" 
                  color={apiStatus === 'healthy' ? 'success' : 'error'} 
                />
                <Chip 
                  icon={<Analytics />} 
                  label={`Grid: ${gridSize}px`} 
                  size="small" 
                  color={snapToGrid ? 'primary' : 'default'} 
                />
                {realTimeMode && (
                  <Chip 
                    label="Real-time" 
                    size="small" 
                    color="success" 
                    sx={{ animation: 'pulse 2s infinite' }}
                  />
                )}
              </Box>
              
              {isDetecting && (
                <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
                  <CircularProgress size={16} sx={{ mr: 1 }} />
                  <Typography variant="body2">Processing...</Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Notification Snackbar */}
      <Snackbar
        open={showSnackbar}
        autoHideDuration={4000}
        onClose={() => setShowSnackbar(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={() => setShowSnackbar(false)} 
          severity="info" 
          sx={{ width: '100%' }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>

      {/* Frame 80 Specific Status */}
      {currentFrame === 80 && (
        <Card sx={{ mt: 2, bgcolor: frame80Processed ? 'success.light' : 'warning.light' }}>
          <CardContent>
            <Typography variant="h6" color={frame80Processed ? 'success.dark' : 'warning.dark'} gutterBottom>
              🎯 Frame 80 Pedestrian Detection Analysis
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Typography variant="body2">
                  Status: {frame80Processed ? '✅ PROCESSED' : '⏳ PENDING'}
                </Typography>
                <Typography variant="body2">
                  Detections: {frame80Detections.length}
                </Typography>
                <Typography variant="body2">
                  Grid Snapping: {snapToGrid ? '✅ ENABLED' : '❌ DISABLED'}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={4}>
                <Typography variant="body2">
                  High Confidence Pedestrians: {frame80Detections.filter(d => d.type === 'pedestrian' && d.confidence >= 0.99).length}
                </Typography>
                <Typography variant="body2">
                  Selected Box: {selectedBox || 'None'}
                </Typography>
              </Grid>
              
              <Grid item xs={12} md={4}>
                {!frame80Processed && videoFile && (
                  <Button
                    variant="contained"
                    color="warning"
                    onClick={detectFrame80}
                    disabled={isDetecting}
                    startIcon={isDetecting ? <CircularProgress size={16} /> : <Warning />}
                  >
                    Process Frame 80
                  </Button>
                )}
              </Grid>
            </Grid>
            
            {frame80Detections.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>Frame 80 Detections:</Typography>
                {frame80Detections.map((detection: BoundaryBox) => (
                  <Chip
                    key={detection.id}
                    label={`${detection.type}: ${(detection.confidence * 100).toFixed(0)}%`}
                    color={detection.confidence >= 0.99 ? 'success' : 'warning'}
                    size="small"
                    sx={{ mr: 1, mb: 1 }}
                  />
                ))}
              </Box>
            )}
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

/**
 * Main BoundaryBoxDemo component wrapped with DetectionErrorBoundary
 */
const BoundaryBoxDemo: React.FC = () => {
  return (
    <DetectionErrorBoundary
      maxRetries={3}
      enableAutoRecovery={true}
      environment="development"
      onError={(error, errorInfo) => {
        console.error('BoundaryBoxDemo Error:', error);
        console.error('Error Info:', errorInfo);
      }}
    >
      <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
        <BoundaryBoxDemoContent />
      </Box>
    </DetectionErrorBoundary>
  );
};

export default BoundaryBoxDemo;