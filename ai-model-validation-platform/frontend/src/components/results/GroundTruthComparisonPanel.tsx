import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Switch,
  FormControlLabel,
  Slider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  IconButton,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
  LinearProgress,
  Tab,
  Tabs,
  Divider
} from '@mui/material';
import {
  ExpandMore,
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  ZoomIn,
  ZoomOut,
  Visibility,
  VisibilityOff,
  Compare,
  Analytics,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  Cancel,
  Warning
} from '@mui/icons-material';

import { StatisticalValidationPanel } from './StatisticalValidationPanel';
import {
  GroundTruthComparison,
  FrameComparisonResult,
  DetectionMatch,
  FrameDetection,
  ComparisonViewMode,
  TemporalAnalysis,
  SpatialAnalysis
} from '../../types/enhanced-results';
import { DetectionOverlay } from './DetectionOverlay';
import { ComparisonMetricsCard } from './ComparisonMetricsCard';
import { TemporalAnalysisChart } from './TemporalAnalysisChart';
import { SpatialAnalysisView } from './SpatialAnalysisView';
import ErrorBoundary from '../ErrorBoundary';

interface GroundTruthComparisonPanelProps {
  comparison: GroundTruthComparison;
  videoUrl?: string;
  onFrameChange?: (frameNumber: number) => void;
  onDetectionSelect?: (detection: FrameDetection) => void;
  loading?: boolean;
  error?: string;
}

export const GroundTruthComparisonPanel: React.FC<GroundTruthComparisonPanelProps> = ({
  comparison,
  videoUrl,
  onFrameChange,
  onDetectionSelect,
  loading = false,
  error
}) => {
  // Early return for missing comparison data
  if (!comparison && !loading && !error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">
            <Typography variant="h6">No Comparison Data</Typography>
            <Typography>No comparison data available to display.</Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }
  // State management
  const [currentFrame, setCurrentFrame] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [selectedTab, setSelectedTab] = useState(0);
  const [viewMode, setViewMode] = useState<ComparisonViewMode>({
    layout: 'side_by_side',
    showGroundTruth: true,
    showPredictions: true,
    highlightMismatches: true,
    overlayOpacity: 0.7,
    frameSync: true,
    playbackSpeed: 1
  });
  const [selectedClass, setSelectedClass] = useState<string>('all');
  const [confidenceFilter, setConfidenceFilter] = useState<[number, number]>([0, 1]);
  const [showOnlyMismatches, setShowOnlyMismatches] = useState(false);

  // Derived data
  const currentFrameData = useMemo(() => {
    if (!comparison?.comparisonResults || !Array.isArray(comparison.comparisonResults)) {
      return null;
    }
    return comparison.comparisonResults.find(result => 
      result.frameNumber === currentFrame
    ) || null;
  }, [comparison?.comparisonResults, currentFrame]);

  const availableClasses = useMemo(() => {
    const classes = new Set<string>();
    if (!comparison?.comparisonResults || !Array.isArray(comparison.comparisonResults)) {
      return ['all'];
    }
    comparison.comparisonResults.forEach(frame => {
      if (frame?.groundTruthDetections && Array.isArray(frame.groundTruthDetections)) {
        frame.groundTruthDetections.forEach(det => det?.vruType && classes.add(det.vruType));
      }
      if (frame?.testDetections && Array.isArray(frame.testDetections)) {
        frame.testDetections.forEach(det => det?.vruType && classes.add(det.vruType));
      }
    });
    return ['all', ...Array.from(classes)];
  }, [comparison?.comparisonResults]);

  const filteredFrames = useMemo(() => {
    if (!comparison?.comparisonResults || !Array.isArray(comparison.comparisonResults)) {
      return [];
    }
    return comparison.comparisonResults.filter(frame => {
      if (!frame) return false;
      
      if (showOnlyMismatches && frame.matches?.length === frame.groundTruthDetections?.length) {
        return false;
      }
      
      if (selectedClass !== 'all') {
        const hasClass = (frame.groundTruthDetections?.some(det => det?.vruType === selectedClass) || false) ||
                        (frame.testDetections?.some(det => det?.vruType === selectedClass) || false);
        if (!hasClass) return false;
      }

      return true;
    });
  }, [comparison?.comparisonResults, showOnlyMismatches, selectedClass]);

  const frameMetrics = useMemo(() => {
    if (!currentFrameData || !currentFrameData.frameMetrics) return null;
    
    const metrics = currentFrameData.frameMetrics;
    const gtLength = currentFrameData.groundTruthDetections?.length || 0;
    const testLength = currentFrameData.testDetections?.length || 0;
    const matchesLength = currentFrameData.matches?.length || 0;
    
    const detectionCounts = {
      groundTruth: gtLength,
      predictions: testLength,
      matches: matchesLength,
      falsePositives: Math.max(0, testLength - matchesLength),
      falseNegatives: Math.max(0, gtLength - matchesLength)
    };

    return { ...metrics, detectionCounts };
  }, [currentFrameData]);

  // Playback control
  const handlePlayPause = useCallback(() => {
    setIsPlaying(prev => !prev);
  }, []);

  const handleFrameChange = useCallback((frameNumber: number) => {
    setCurrentFrame(frameNumber);
    onFrameChange?.(frameNumber);
  }, [onFrameChange]);

  const goToNextFrame = useCallback(() => {
    if (currentFrame < (comparison?.totalFrames || 0) - 1) {
      handleFrameChange(currentFrame + 1);
    }
  }, [currentFrame, comparison.totalFrames, handleFrameChange]);

  const goToPreviousFrame = useCallback(() => {
    if (currentFrame > 0) {
      handleFrameChange(currentFrame - 1);
    }
  }, [currentFrame, handleFrameChange]);

  // Auto-advance frames when playing
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentFrame(prev => {
        const nextFrame = prev + 1;
        if (nextFrame >= (comparison?.totalFrames || 0)) {
          setIsPlaying(false);
          return prev;
        }
        onFrameChange?.(nextFrame);
        return nextFrame;
      });
    }, 1000 / viewMode.playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, viewMode.playbackSpeed, comparison.totalFrames, onFrameChange]);

  // Render detection matches table
  const renderMatchesTable = () => {
    if (!currentFrameData) return null;

    return (
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Ground Truth</TableCell>
              <TableCell>Prediction</TableCell>
              <TableCell>IoU Score</TableCell>
              <TableCell>Confidence</TableCell>
              <TableCell>Class Match</TableCell>
              <TableCell>Spatial Error</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(currentFrameData?.matches || []).map((match, index) => (
              <TableRow key={index} hover>
                <TableCell>
                  <Box>
                    <Typography variant="subtitle2">
                      {match.groundTruthDetection.className}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Frame {match.groundTruthDetection.frameNumber}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Box>
                    <Typography variant="subtitle2">
                      {match.testDetection.className}
                    </Typography>
                    <Chip
                      label={`${(match.testDetection.confidence * 100).toFixed(1)}%`}
                      color={match.testDetection.confidence > 0.8 ? 'success' : 
                             match.testDetection.confidence > 0.5 ? 'warning' : 'error'}
                      size="small"
                    />
                  </Box>
                </TableCell>
                <TableCell>
                  <Typography
                    color={match.iouScore > 0.7 ? 'success.main' : 
                           match.iouScore > 0.5 ? 'warning.main' : 'error.main'}
                    fontWeight="bold"
                  >
                    {(match.iouScore * 100).toFixed(1)}%
                  </Typography>
                </TableCell>
                <TableCell>
                  {(match.confidenceScore * 100).toFixed(1)}%
                </TableCell>
                <TableCell>
                  {match.classMatch ? (
                    <CheckCircle color="success" />
                  ) : (
                    <Cancel color="error" />
                  )}
                </TableCell>
                <TableCell>
                  <Typography variant="caption">
                    Center: {match.spatialError.centerDistancePixels.toFixed(1)}px<br/>
                    Area: {(match.spatialError.areaRatio * 100).toFixed(1)}%
                  </Typography>
                </TableCell>
                <TableCell>
                  <Tooltip title="View Detection">
                    <IconButton
                      size="small"
                      onClick={() => onDetectionSelect?.(match.groundTruthDetection)}
                    >
                      <Visibility />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            
            {/* Unmatched ground truth detections */}
            {(currentFrameData?.unmatched?.groundTruth || []).map((detection, index) => (
              <TableRow key={`unmatched-gt-${index}`} sx={{ backgroundColor: 'error.light', opacity: 0.7 }}>
                <TableCell>
                  <Box>
                    <Typography variant="subtitle2">
                      {detection.className}
                    </Typography>
                    <Typography variant="caption" color="error">
                      False Negative
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>-</TableCell>
                <TableCell>-</TableCell>
                <TableCell>-</TableCell>
                <TableCell>-</TableCell>
                <TableCell>-</TableCell>
                <TableCell>
                  <Tooltip title="View Detection">
                    <IconButton
                      size="small"
                      onClick={() => onDetectionSelect?.(detection)}
                    >
                      <Visibility />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}

            {/* Unmatched test detections */}
            {(currentFrameData?.unmatched?.test || []).map((detection, index) => (
              <TableRow key={`unmatched-test-${index}`} sx={{ backgroundColor: 'warning.light', opacity: 0.7 }}>
                <TableCell>-</TableCell>
                <TableCell>
                  <Box>
                    <Typography variant="subtitle2">
                      {detection.className}
                    </Typography>
                    <Typography variant="caption" color="warning.main">
                      False Positive
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>-</TableCell>
                <TableCell>
                  {(detection.confidence * 100).toFixed(1)}%
                </TableCell>
                <TableCell>-</TableCell>
                <TableCell>-</TableCell>
                <TableCell>
                  <Tooltip title="View Detection">
                    <IconButton
                      size="small"
                      onClick={() => onDetectionSelect?.(detection)}
                    >
                      <Visibility />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <LinearProgress sx={{ flexGrow: 1 }} />
            <Typography variant="body2">Loading comparison data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">
            <Typography variant="h6">Comparison Error</Typography>
            <Typography>{error}</Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Control Panel */}
      <Card>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            {/* Playback Controls */}
            <Grid item xs={12} md={4}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <IconButton onClick={goToPreviousFrame} disabled={currentFrame === 0}>
                  <SkipPrevious />
                </IconButton>
                <IconButton onClick={handlePlayPause}>
                  {isPlaying ? <Pause /> : <PlayArrow />}
                </IconButton>
                <IconButton 
                  onClick={goToNextFrame} 
                  disabled={currentFrame >= (comparison?.totalFrames || 0) - 1}
                >
                  <SkipNext />
                </IconButton>
                <Typography variant="body2" sx={{ ml: 1 }}>
                  Frame {currentFrame + 1} of {comparison?.totalFrames || 0}
                </Typography>
              </Box>
              <Slider
                value={currentFrame}
                min={0}
                max={Math.max(0, (comparison?.totalFrames || 1) - 1)}
                onChange={(_, value) => handleFrameChange(value as number)}
                size="small"
                sx={{ mt: 1 }}
              />
            </Grid>

            {/* View Mode Controls */}
            <Grid item xs={12} md={4}>
              <FormControl size="small" fullWidth>
                <InputLabel>View Mode</InputLabel>
                <Select
                  value={viewMode.layout}
                  label="View Mode"
                  onChange={(e) => setViewMode(prev => ({ 
                    ...prev, 
                    layout: e.target.value as ComparisonViewMode['layout']
                  }))}
                >
                  <MenuItem value="side_by_side">Side by Side</MenuItem>
                  <MenuItem value="overlay">Overlay</MenuItem>
                  <MenuItem value="difference_map">Difference Map</MenuItem>
                  <MenuItem value="timeline_sync">Timeline Sync</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {/* Filter Controls */}
            <Grid item xs={12} md={4}>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={showOnlyMismatches}
                      onChange={(e) => setShowOnlyMismatches(e.target.checked)}
                      size="small"
                    />
                  }
                  label="Mismatches Only"
                />
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Class</InputLabel>
                  <Select
                    value={selectedClass}
                    label="Class"
                    onChange={(e) => setSelectedClass(e.target.value)}
                  >
                    {availableClasses.map(cls => (
                      <MenuItem key={cls} value={cls}>
                        {cls.charAt(0).toUpperCase() + cls.slice(1)}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Tab Navigation */}
      <Card>
        <Tabs
          value={selectedTab}
          onChange={(_, newValue) => setSelectedTab(newValue)}
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab label="Frame Analysis" icon={<Compare />} />
          <Tab label="Overall Metrics" icon={<Analytics />} />
          <Tab label="Statistical Analysis" icon={<TrendingUp />} />
          <Tab label="Temporal Analysis" icon={<TrendingDown />} />
          <Tab label="Spatial Analysis" icon={<ZoomIn />} />
        </Tabs>
      </Card>

      {/* Tab Content */}
      {selectedTab === 0 && (
        <Grid container spacing={2}>
          {/* Visual Comparison */}
          <Grid item xs={12} lg={8}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Visual Comparison - Frame {currentFrame + 1}
                </Typography>
                {videoUrl && currentFrameData && (
                  <DetectionOverlay
                    videoUrl={videoUrl}
                    frameNumber={currentFrame}
                    groundTruthDetections={currentFrameData.groundTruthDetections}
                    testDetections={currentFrameData.testDetections}
                    matches={currentFrameData.matches}
                    viewMode={viewMode}
                    onDetectionSelect={onDetectionSelect}
                  />
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Frame Metrics */}
          <Grid item xs={12} lg={4}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Frame Metrics
                </Typography>
                {frameMetrics && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <ComparisonMetricsCard metrics={frameMetrics} />
                    
                    <Divider />
                    
                    <Typography variant="subtitle2">Detection Counts</Typography>
                    <Grid container spacing={1}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Ground Truth: {frameMetrics.detectionCounts.groundTruth}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Predictions: {frameMetrics.detectionCounts.predictions}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="success.main">
                          Matches: {frameMetrics.detectionCounts.matches}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="error.main">
                          FP: {frameMetrics.detectionCounts.falsePositives}
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="body2" color="warning.main">
                          FN: {frameMetrics.detectionCounts.falseNegatives}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Detection Matches Table */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Detection Matches - Frame {currentFrame + 1}
                </Typography>
                {renderMatchesTable()}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {selectedTab === 1 && (
        <Grid container spacing={2}>
          {/* Overall Metrics */}
          <Grid item xs={12} md={6}>
            {comparison?.overallMetrics && (
              <ComparisonMetricsCard 
                metrics={comparison.overallMetrics} 
                title="Overall Performance"
              />
            )}
          </Grid>

          {/* Per-Class Metrics */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Per-Class Performance
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Class</TableCell>
                        <TableCell align="right">Precision</TableCell>
                        <TableCell align="right">Recall</TableCell>
                        <TableCell align="right">F1 Score</TableCell>
                        <TableCell align="right">Avg IoU</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(comparison?.perClassMetrics || {}).map(([className, metrics]) => (
                        <TableRow key={className}>
                          <TableCell>
                            <Typography variant="subtitle2">
                              {className.replace('_', ' ')}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography
                              color={metrics.precision > 0.8 ? 'success.main' : 
                                     metrics.precision > 0.6 ? 'warning.main' : 'error.main'}
                            >
                              {(metrics.precision * 100).toFixed(1)}%
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography
                              color={metrics.recall > 0.8 ? 'success.main' : 
                                     metrics.recall > 0.6 ? 'warning.main' : 'error.main'}
                            >
                              {(metrics.recall * 100).toFixed(1)}%
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography
                              color={metrics.f1Score > 0.8 ? 'success.main' : 
                                     metrics.f1Score > 0.6 ? 'warning.main' : 'error.main'}
                            >
                              {(metrics.f1Score * 100).toFixed(1)}%
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            {(metrics.averageIou * 100).toFixed(1)}%
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {selectedTab === 2 && (
        <ErrorBoundary>
          <TemporalAnalysisChart 
            temporalAnalysis={comparison?.temporalAnalysis}
            comparisonResults={comparison?.comparisonResults || []}
            currentFrame={currentFrame}
            onFrameSelect={handleFrameChange}
          />
        </ErrorBoundary>
      )}

      {selectedTab === 3 && (
        <ErrorBoundary>
          <SpatialAnalysisView 
            spatialAnalysis={comparison?.spatialAnalysis}
            comparisonResults={comparison?.comparisonResults || []}
            videoUrl={videoUrl}
          />
        </ErrorBoundary>
      )}
    </Box>
  );
};