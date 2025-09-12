/**
 * Enhanced Video Test Component with Boundary Box Visualization
 * 
 * Integrates the boundary box visualizer with the existing video test component
 * to provide interactive detection visualization and validation capabilities.
 */

import React, { useState, useCallback, useRef, useMemo } from 'react';
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
  Grid,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Paper
} from '@mui/material';
import { 
  PlayArrow as PlayIcon, 
  VideoLibrary as VideoIcon,
  BoundingBox as BoxIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';

import SequentialVideoPlayer from './SequentialVideoPlayer';
import { BoundaryBoxVisualizer } from './BoundaryBox/BoundaryBoxVisualizer';
import { BoundaryBoxControls } from './BoundaryBox/BoundaryBoxControls';
import { VideoFile, VideoStatus } from '../services/types';
import { FrameDetection } from '../types/enhanced-results';

// Test videos with mock detection data
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
    groundTruthGenerated: true,
    detectionCount: 15,
    annotationCount: 12,
    createdAt: new Date().toISOString()
  },
  {
    id: 'test-2',
    projectId: 'test-project',
    filename: 'pedestrian-detection-test.mp4',
    name: 'Pedestrian Detection Test Video',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
    duration: 653,
    fileSize: 125513024,
    size: 125513024,
    status: VideoStatus.VALIDATED,
    processingStatus: 'completed',
    groundTruthGenerated: true,
    detectionCount: 8,
    annotationCount: 8,
    createdAt: new Date().toISOString()
  }
];

// Mock detection data - Frame 80 specific data for pedestrian validation
const generateMockDetections = (videoId: string, frameNumber: number): FrameDetection[] => {
  // Special Frame 80 data for pedestrian detection validation
  if (frameNumber === 80) {
    return [
      {
        id: `det-${videoId}-80-1`,
        frameNumber: 80,
        timestamp: 2.66,
        className: 'Pedestrian',
        vruType: 'pedestrian',
        confidence: 0.94,
        boundingBox: { x: 180, y: 220, width: 75, height: 160 },
        isGroundTruth: false,
        matchType: 'true_positive'
      },
      {
        id: `det-${videoId}-80-2`,
        frameNumber: 80,
        timestamp: 2.66,
        className: 'Pedestrian',
        vruType: 'pedestrian',
        confidence: 0.88,
        boundingBox: { x: 320, y: 200, width: 80, height: 170 },
        isGroundTruth: false,
        matchType: 'true_positive'
      },
      {
        id: `det-${videoId}-80-3`,
        frameNumber: 80,
        timestamp: 2.66,
        className: 'Cyclist',
        vruType: 'cyclist',
        confidence: 0.72,
        boundingBox: { x: 480, y: 160, width: 110, height: 180 },
        isGroundTruth: false,
        matchType: 'false_positive'
      }
    ];
  }

  // Generate random detections for other frames
  const detectionCount = Math.floor(Math.random() * 3) + 1;
  const detections: FrameDetection[] = [];

  for (let i = 0; i < detectionCount; i++) {
    detections.push({
      id: `det-${videoId}-${frameNumber}-${i}`,
      frameNumber,
      timestamp: frameNumber / 30,
      className: Math.random() > 0.6 ? 'Pedestrian' : 'Cyclist',
      vruType: Math.random() > 0.6 ? 'pedestrian' : 'cyclist',
      confidence: 0.5 + Math.random() * 0.4,
      boundingBox: {
        x: Math.random() * 500,
        y: Math.random() * 300 + 100,
        width: 60 + Math.random() * 80,
        height: 120 + Math.random() * 100
      },
      isGroundTruth: false,
      matchType: Math.random() > 0.3 ? 'true_positive' : 'false_positive'
    });
  }

  return detections;
};

// Ground truth data for Frame 80
const FRAME_80_GROUND_TRUTH: FrameDetection[] = [
  {
    id: 'gt-80-1',
    frameNumber: 80,
    timestamp: 2.66,
    className: 'Pedestrian',
    vruType: 'pedestrian',
    confidence: 1.0,
    boundingBox: { x: 178, y: 218, width: 77, height: 162 },
    isGroundTruth: true,
    groundTruthId: 'gt-80-1'
  },
  {
    id: 'gt-80-2',
    frameNumber: 80,
    timestamp: 2.66,
    className: 'Pedestrian',
    vruType: 'pedestrian',
    confidence: 1.0,
    boundingBox: { x: 322, y: 198, width: 78, height: 172 },
    isGroundTruth: true,
    groundTruthId: 'gt-80-2'
  }
];

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index, ...other }: TabPanelProps) => (
  <div
    role="tabpanel"
    hidden={value !== index}
    id={`tabpanel-${index}`}
    aria-labelledby={`tab-${index}`}
    {...other}
  >
    {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
  </div>
);

const VideoTestComponentWithBoundaryBoxes: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  
  // Video test states
  const [testStarted, setTestStarted] = useState(false);
  const [currentVideo, setCurrentVideo] = useState<VideoFile | null>(null);
  const [testLogs, setTestLogs] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [currentFrame, setCurrentFrame] = useState(80); // Start at Frame 80 for demo
  const [isPlaying, setIsPlaying] = useState(false);
  
  // Boundary box states
  const [showBoundaryBoxes, setShowBoundaryBoxes] = useState(true);
  const [detections, setDetections] = useState<FrameDetection[]>([]);
  const [groundTruthDetections, setGroundTruthDetections] = useState<FrameDetection[]>(FRAME_80_GROUND_TRUTH);
  
  // UI states
  const [activeTab, setActiveTab] = useState(0);
  
  // Boundary box control states
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [showSnapGrid, setShowSnapGrid] = useState(true);
  const [gridSize, setGridSize] = useState(20);
  const [showConfidence, setShowConfidence] = useState(true);
  const [showCoordinates, setShowCoordinates] = useState(false);
  const [showGroundTruth, setShowGroundTruth] = useState(true);
  const [highlightFrame80, setHighlightFrame80] = useState(true);
  const [enableDragAndDrop, setEnableDragAndDrop] = useState(true);
  const [debugMode, setDebugMode] = useState(false);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.6);
  const [selectedVRUTypes, setSelectedVRUTypes] = useState<string[]>(['pedestrian', 'cyclist']);

  // Generate detections for current frame
  const currentDetections = useMemo(() => {
    if (!currentVideo) return [];
    return generateMockDetections(currentVideo.id, currentFrame);
  }, [currentVideo, currentFrame]);

  // Update detections when frame changes
  React.useEffect(() => {
    setDetections(currentDetections);
  }, [currentDetections]);

  // Filter detections
  const filteredDetections = detections.filter(detection => 
    detection.confidence >= confidenceThreshold && 
    selectedVRUTypes.includes(detection.vruType)
  );

  const filteredGroundTruth = showGroundTruth ? groundTruthDetections.filter(detection =>
    selectedVRUTypes.includes(detection.vruType)
  ) : [];

  // Statistics
  const totalDetections = detections.length;
  const visibleDetections = filteredDetections.length;
  const pedestrianCount = filteredDetections.filter(d => d.vruType === 'pedestrian').length;

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
    setTestStarted(true);
    setCurrentVideo(TEST_VIDEOS[0]);
    setCurrentFrame(80); // Start at Frame 80
    addLog('Test started with boundary box visualization');
    addLog('Starting at Frame 80 - Pedestrian Detection Validation Frame');
  }, [addLog]);

  const handleVideoSelect = useCallback((video: VideoFile) => {
    setCurrentVideo(video);
    setCurrentFrame(80);
    addLog(`Selected video: ${video.name}`);
    addLog('Frame reset to 80 for pedestrian validation testing');
  }, [addLog]);

  const handleFrameChange = (newFrame: number) => {
    setCurrentFrame(newFrame);
    addLog(`Frame changed to ${newFrame}`);
    
    if (newFrame === 80) {
      addLog('Frame 80: Special pedestrian detection validation frame loaded');
    }
  };

  const handleBoundingBoxUpdate = useCallback((detection: FrameDetection, newBoundingBox: FrameDetection['boundingBox']) => {
    setDetections(prev => prev.map(det => 
      det.id === detection.id 
        ? { ...det, boundingBox: newBoundingBox }
        : det
    ));
    addLog(`Updated bounding box for ${detection.className} (${detection.id})`);
  }, [addLog]);

  const handleDetectionSelect = useCallback((detection: FrameDetection) => {
    addLog(`Selected detection: ${detection.className} (confidence: ${(detection.confidence * 100).toFixed(1)}%)`);
  }, [addLog]);

  const handleResetView = () => {
    setDetections(currentDetections);
    setCurrentFrame(80);
    addLog('View reset to original state');
  };

  const handleSaveSettings = () => {
    addLog('Boundary box settings saved');
  };

  const handleCenterView = () => {
    addLog('View centered on detections');
  };

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom>
        Video Test Component with Boundary Box Visualization
      </Typography>
      
      <Alert severity="info" sx={{ mb: 2 }}>
        This enhanced video test component includes interactive boundary box visualization. 
        Frame 80 contains special pedestrian detection validation data for testing.
      </Alert>

      {!testStarted ? (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              🎯 Boundary Box Visualization Test
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Test the SequentialVideoPlayer with interactive boundary box overlays, 
              snapping functionality, and Frame 80 pedestrian detection validation.
            </Typography>
            
            <Stack spacing={1} sx={{ mb: 2 }}>
              <Typography variant="subtitle2">Test Features:</Typography>
              <Chip label="Interactive Boundary Boxes" size="small" />
              <Chip label="Grid Snapping" size="small" />
              <Chip label="Frame 80 Validation" size="small" color="warning" />
              <Chip label="Drag & Drop Detection" size="small" />
              <Chip label="Confidence Filtering" size="small" />
              <Chip label="VRU Type Selection" size="small" />
            </Stack>
            
            <Button
              variant="contained"
              startIcon={<PlayIcon />}
              onClick={handleStartTest}
              size="large"
            >
              Start Boundary Box Test
            </Button>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {/* Main Video and Controls */}
          <Grid item xs={12} lg={8}>
            <Card>
              <CardContent>
                <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                  <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
                    <Tab label="Video Player" />
                    <Tab label="Test Logs" />
                  </Tabs>
                </Box>

                <TabPanel value={activeTab} index={0}>
                  {/* Video Selection */}
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Select Test Video:
                    </Typography>
                    <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                      {TEST_VIDEOS.map(video => (
                        <Button
                          key={video.id}
                          variant={currentVideo?.id === video.id ? "contained" : "outlined"}
                          size="small"
                          onClick={() => handleVideoSelect(video)}
                          startIcon={<VideoIcon />}
                        >
                          {video.name}
                        </Button>
                      ))}
                    </Stack>
                  </Box>

                  {/* Boundary Box Toggle */}
                  <FormControlLabel
                    control={
                      <Switch
                        checked={showBoundaryBoxes}
                        onChange={(e) => setShowBoundaryBoxes(e.target.checked)}
                      />
                    }
                    label="Show Boundary Boxes"
                    sx={{ mb: 2 }}
                  />

                  {/* Video Player Container */}
                  {currentVideo && (
                    <Box sx={{ position: 'relative', border: 1, borderColor: 'divider', display: 'inline-block' }}>
                      <SequentialVideoPlayer
                        videos={[currentVideo]}
                        onCurrentVideoChange={(video) => setCurrentVideo(video)}
                        onError={(error) => addError(error)}
                        autoPlay={false}
                      />
                      
                      {/* Boundary Box Overlay */}
                      {showBoundaryBoxes && (
                        <BoundaryBoxVisualizer
                          videoRef={videoRef}
                          videoUrl={currentVideo.url}
                          frameNumber={currentFrame}
                          detections={filteredDetections}
                          groundTruthDetections={filteredGroundTruth}
                          width={640}
                          height={480}
                          showSnapGrid={showSnapGrid}
                          snapToGrid={snapToGrid}
                          gridSize={gridSize}
                          onBoundingBoxUpdate={handleBoundingBoxUpdate}
                          onDetectionSelect={handleDetectionSelect}
                          highlightFrame80={highlightFrame80}
                          showConfidence={showConfidence}
                          showCoordinates={showCoordinates}
                          enableDragAndDrop={enableDragAndDrop}
                          debugMode={debugMode}
                        />
                      )}
                    </Box>
                  )}

                  {/* Frame Control */}
                  <Box sx={{ mt: 2 }}>
                    <Stack direction="row" spacing={2} alignItems="center">
                      <Button 
                        size="small" 
                        onClick={() => handleFrameChange(Math.max(1, currentFrame - 1))}
                      >
                        Previous Frame
                      </Button>
                      <Typography variant="body2">
                        Frame: {currentFrame}
                        {currentFrame === 80 && (
                          <Chip label="VALIDATION FRAME" color="warning" size="small" sx={{ ml: 1 }} />
                        )}
                      </Typography>
                      <Button 
                        size="small" 
                        onClick={() => handleFrameChange(currentFrame + 1)}
                      >
                        Next Frame
                      </Button>
                      <Button 
                        size="small" 
                        onClick={() => handleFrameChange(80)}
                        color="warning"
                      >
                        Go to Frame 80
                      </Button>
                    </Stack>
                  </Box>
                </TabPanel>

                <TabPanel value={activeTab} index={1}>
                  <Paper sx={{ p: 2, maxHeight: 400, overflow: 'auto' }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Test Logs:
                    </Typography>
                    <List dense>
                      {testLogs.map((log, index) => (
                        <ListItem key={index}>
                          <ListItemText 
                            primary={log}
                            primaryTypographyProps={{ 
                              variant: 'body2', 
                              fontFamily: 'monospace' 
                            }}
                          />
                        </ListItem>
                      ))}
                    </List>
                    
                    {errors.length > 0 && (
                      <>
                        <Typography variant="subtitle2" color="error" sx={{ mt: 2 }}>
                          Errors:
                        </Typography>
                        <List dense>
                          {errors.map((error, index) => (
                            <ListItem key={index}>
                              <ListItemText 
                                primary={error}
                                primaryTypographyProps={{ 
                                  variant: 'body2', 
                                  fontFamily: 'monospace',
                                  color: 'error'
                                }}
                              />
                            </ListItem>
                          ))}
                        </List>
                      </>
                    )}
                  </Paper>
                </TabPanel>
              </CardContent>
            </Card>
          </Grid>

          {/* Boundary Box Controls */}
          <Grid item xs={12} lg={4}>
            {showBoundaryBoxes && (
              <BoundaryBoxControls
                snapToGrid={snapToGrid}
                onSnapToGridChange={setSnapToGrid}
                showSnapGrid={showSnapGrid}
                onShowSnapGridChange={setShowSnapGrid}
                gridSize={gridSize}
                onGridSizeChange={setGridSize}
                showConfidence={showConfidence}
                onShowConfidenceChange={setShowConfidence}
                showCoordinates={showCoordinates}
                onShowCoordinatesChange={setShowCoordinates}
                showGroundTruth={showGroundTruth}
                onShowGroundTruthChange={setShowGroundTruth}
                highlightFrame80={highlightFrame80}
                onHighlightFrame80Change={setHighlightFrame80}
                currentFrame={currentFrame}
                enableDragAndDrop={enableDragAndDrop}
                onEnableDragAndDropChange={setEnableDragAndDrop}
                debugMode={debugMode}
                onDebugModeChange={setDebugMode}
                confidenceThreshold={confidenceThreshold}
                onConfidenceThresholdChange={setConfidenceThreshold}
                selectedVRUTypes={selectedVRUTypes}
                onVRUTypeSelectionChange={setSelectedVRUTypes}
                onResetView={handleResetView}
                onSaveSettings={handleSaveSettings}
                onCenterView={handleCenterView}
                totalDetections={totalDetections}
                visibleDetections={visibleDetections}
                pedestrianCount={pedestrianCount}
              />
            )}
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default VideoTestComponentWithBoundaryBoxes;