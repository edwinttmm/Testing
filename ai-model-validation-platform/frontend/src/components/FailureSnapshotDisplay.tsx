import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardActions,
  Typography,
  IconButton,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  Alert,
  Skeleton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Paper,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Badge,
} from '@mui/material';
import {
  ZoomIn,
  ZoomOut,
  Fullscreen,
  Download,
  Error,
  Warning,
  AccessTime,
  Timeline,
  BugReport,
  Close,
  Refresh,
  FilterList,
  ViewList,
  ViewModule,
  Sort,
} from '@mui/icons-material';
import { 
  FailureSnapshotData, 
  SnapshotDisplaySettings, 
  ImageLoadingState, 
  ZoomModalState 
} from '../types/enhanced-results';

interface FailureSnapshotDisplayProps {
  failures: FailureSnapshotData[];
  loading?: boolean;
  error?: string;
  onRefresh?: () => void;
  showSettings?: boolean;
  maxDisplayCount?: number;
  baseUrl?: string;
  showComparisonView?: boolean;
  enableAutomaticCapture?: boolean;
  onCaptureFailure?: (eventId: string, failureType: string) => Promise<void>;
}

interface SnapshotImageProps {
  snapshot: FailureSnapshotData;
  settings: SnapshotDisplaySettings;
  onZoom: (snapshot: FailureSnapshotData) => void;
  baseUrl?: string;
}

const SnapshotImage: React.FC<SnapshotImageProps> = ({ 
  snapshot, 
  settings, 
  onZoom, 
  baseUrl = '' 
}) => {
  const [loadingState, setLoadingState] = useState<ImageLoadingState>({
    loading: false,
    loaded: false,
    retryCount: 0
  });

  const imageUrl = useMemo(() => {
    if (!snapshot.screenshot_path) return '';
    return snapshot.screenshot_path.startsWith('http') 
      ? snapshot.screenshot_path 
      : `${baseUrl}${snapshot.screenshot_path}`;
  }, [snapshot.screenshot_path, baseUrl]);

  const zoomImageUrl = useMemo(() => {
    if (!snapshot.screenshot_zoom_path) return imageUrl;
    return snapshot.screenshot_zoom_path.startsWith('http') 
      ? snapshot.screenshot_zoom_path 
      : `${baseUrl}${snapshot.screenshot_zoom_path}`;
  }, [snapshot.screenshot_zoom_path, baseUrl, imageUrl]);

  const handleImageLoad = useCallback(() => {
    setLoadingState(prev => ({ ...prev, loading: false, loaded: true, error: undefined }));
  }, []);

  const handleImageError = useCallback(() => {
    setLoadingState(prev => ({
      ...prev,
      loading: false,
      error: `Failed to load image after ${prev.retryCount + 1} attempts`,
      retryCount: prev.retryCount + 1
    }));
  }, []);

  const handleRetry = useCallback(() => {
    if (loadingState.retryCount < 3) {
      setLoadingState(prev => ({ ...prev, loading: true, error: undefined }));
    }
  }, [loadingState.retryCount]);

  const getFailureTypeIcon = (type: string) => {
    switch (type) {
      case 'timing': return <AccessTime />;
      case 'accuracy': return <Timeline />;
      case 'detection': return <Warning />;
      case 'system': return <BugReport />;
      default: return <Error />;
    }
  };

  const getFailureTypeColor = (type: string): 'error' | 'warning' | 'info' | 'default' => {
    switch (type) {
      case 'timing': return 'error';
      case 'accuracy': return 'warning';
      case 'detection': return 'info';
      case 'system': return 'error';
      default: return 'default';
    }
  };

  useEffect(() => {
    if (imageUrl && !loadingState.loaded && !loadingState.loading) {
      setLoadingState(prev => ({ ...prev, loading: true }));
    }
  }, [imageUrl, loadingState.loaded, loadingState.loading]);

  if (!imageUrl) {
    return (
      <Alert severity="info" sx={{ m: 1 }}>
        No screenshot available for this failure
      </Alert>
    );
  }

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="subtitle2" noWrap>
              Frame {snapshot.frameNumber}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(snapshot.timestamp).toLocaleTimeString()}
            </Typography>
          </Box>
          <Chip
            icon={getFailureTypeIcon(snapshot.failure_type)}
            label={snapshot.failure_type}
            color={getFailureTypeColor(snapshot.failure_type)}
            size="small"
          />
        </Box>

        {/* Image Container */}
        <Box 
          sx={{ 
            position: 'relative',
            width: '100%',
            height: settings.showThumbnails ? 200 : 300,
            bgcolor: 'grey.100',
            borderRadius: 1,
            overflow: 'hidden',
            cursor: settings.enableZoom ? 'zoom-in' : 'default',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          onClick={settings.enableZoom ? () => onZoom(snapshot) : undefined}
        >
          {loadingState.loading && (
            <Skeleton 
              variant="rectangular" 
              width="100%" 
              height="100%" 
              animation="wave"
            />
          )}
          
          {loadingState.error ? (
            <Box sx={{ textAlign: 'center', p: 2 }}>
              <Error color="error" sx={{ fontSize: 40, mb: 1 }} />
              <Typography variant="body2" color="error" gutterBottom>
                {loadingState.error}
              </Typography>
              {loadingState.retryCount < 3 && (
                <Button 
                  size="small" 
                  onClick={handleRetry}
                  startIcon={<Refresh />}
                >
                  Retry
                </Button>
              )}
            </Box>
          ) : (
            <img
              src={imageUrl}
              alt={`Failure snapshot for frame ${snapshot.frameNumber}`}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                display: loadingState.loaded ? 'block' : 'none'
              }}
              onLoad={handleImageLoad}
              onError={handleImageError}
              loading={settings.lazyLoading ? 'lazy' : 'eager'}
            />
          )}

          {/* Zoom overlay */}
          {settings.enableZoom && loadingState.loaded && !loadingState.error && (
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                bgcolor: 'rgba(0, 0, 0, 0.7)',
                borderRadius: 1,
                p: 0.5
              }}
            >
              <ZoomIn sx={{ color: 'white', fontSize: 16 }} />
            </Box>
          )}
        </Box>

        {/* Failure Details */}
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.primary" gutterBottom>
            <strong>Reason:</strong> {snapshot.failure_reason}
          </Typography>
          
          {snapshot.expected_value !== undefined && snapshot.actual_value !== undefined && (
            <Box sx={{ mt: 1, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="caption" display="block">
                Expected: {snapshot.expected_value}
                {snapshot.threshold && ` (threshold: ${snapshot.threshold})`}
              </Typography>
              <Typography variant="caption" display="block" color="error.main">
                Actual: {snapshot.actual_value}
              </Typography>
            </Box>
          )}

          {snapshot.confidence !== undefined && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
              Confidence: {(snapshot.confidence * 100).toFixed(1)}%
            </Typography>
          )}
        </Box>
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', pt: 0 }}>
        <Tooltip title="Download snapshot">
          <IconButton 
            size="small"
            onClick={() => {
              const link = document.createElement('a');
              link.href = imageUrl;
              link.download = `failure_snapshot_frame_${snapshot.frameNumber}.jpg`;
              link.click();
            }}
          >
            <Download />
          </IconButton>
        </Tooltip>

        {settings.enableZoom && (
          <Tooltip title="View full size">
            <IconButton size="small" onClick={() => onZoom(snapshot)}>
              <Fullscreen />
            </IconButton>
          </Tooltip>
        )}
      </CardActions>
    </Card>
  );
};

const ZoomModal: React.FC<{
  state: ZoomModalState;
  onClose: () => void;
  snapshot?: FailureSnapshotData;
  baseUrl?: string;
}> = ({ state, onClose, snapshot, baseUrl = '' }) => {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const imageUrl = useMemo(() => {
    if (!snapshot) return '';
    const url = snapshot.screenshot_zoom_path || snapshot.screenshot_path;
    if (!url) return '';
    return url.startsWith('http') ? url : `${baseUrl}${url}`;
  }, [snapshot, baseUrl]);

  const handleZoomIn = () => setZoom(prev => Math.min(prev * 1.5, 5));
  const handleZoomOut = () => setZoom(prev => Math.max(prev / 1.5, 0.5));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <Dialog
      open={state.isOpen}
      onClose={onClose}
      maxWidth={false}
      fullWidth
      PaperProps={{
        sx: {
          width: '90vw',
          height: '90vh',
          maxWidth: 'none',
          maxHeight: 'none'
        }
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h6">
              Failure Snapshot - Frame {snapshot?.frameNumber}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {snapshot?.failure_reason}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <IconButton onClick={handleZoomOut} disabled={zoom <= 0.5}>
              <ZoomOut />
            </IconButton>
            <Button size="small" onClick={handleReset}>
              Reset
            </Button>
            <IconButton onClick={handleZoomIn} disabled={zoom >= 5}>
              <ZoomIn />
            </IconButton>
            <IconButton onClick={onClose}>
              <Close />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ p: 0, overflow: 'hidden', position: 'relative' }}>
        <Box
          sx={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            cursor: zoom > 1 ? 'grab' : 'default'
          }}
        >
          {imageUrl && (
            <img
              src={imageUrl}
              alt={`Failure snapshot for frame ${snapshot?.frameNumber}`}
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)`,
                transition: 'transform 0.2s ease-in-out',
                objectFit: 'contain'
              }}
            />
          )}
        </Box>

        {/* Zoom level indicator */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 16,
            left: 16,
            bgcolor: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            px: 2,
            py: 1,
            borderRadius: 1
          }}
        >
          {(zoom * 100).toFixed(0)}%
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export const FailureSnapshotDisplay: React.FC<FailureSnapshotDisplayProps> = ({
  failures,
  loading = false,
  error,
  onRefresh,
  showSettings = true,
  maxDisplayCount = 50,
  baseUrl = '',
  showComparisonView = true,
  enableAutomaticCapture = true,
  onCaptureFailure
}) => {
  const [settings, setSettings] = useState<SnapshotDisplaySettings>({
    showThumbnails: true,
    enableZoom: true,
    lazyLoading: true,
    imageQuality: 'high',
    maxWidth: 400,
    maxHeight: 300,
    groupByType: false,
    sortBy: 'timestamp',
    filterByType: undefined
  });
  
  const [snapshotStats, setSnapshotStats] = useState<any>(null);
  const [captureInProgress, setCaptureInProgress] = useState<Set<string>>(new Set());

  const [zoomModal, setZoomModal] = useState<ZoomModalState>({
    isOpen: false
  });

  const [selectedSnapshot, setSelectedSnapshot] = useState<FailureSnapshotData>();
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const handleZoomSnapshot = useCallback((snapshot: FailureSnapshotData) => {
    setSelectedSnapshot(snapshot);
    setZoomModal({ isOpen: true });
  }, []);

  const closeZoomModal = useCallback(() => {
    setZoomModal({ isOpen: false });
    setSelectedSnapshot(undefined);
  }, []);
  
  const handleCaptureFailure = useCallback(async (eventId: string, failureType: string) => {
    if (!onCaptureFailure || captureInProgress.has(eventId)) return;
    
    setCaptureInProgress(prev => new Set(prev).add(eventId));
    
    try {
      await onCaptureFailure(eventId, failureType);
      // Refresh snapshots after capture
      if (onRefresh) {
        onRefresh();
      }
    } catch (error) {
      console.error('Failed to capture failure snapshot:', error);
    } finally {
      setCaptureInProgress(prev => {
        const newSet = new Set(prev);
        newSet.delete(eventId);
        return newSet;
      });
    }
  }, [onCaptureFailure, onRefresh, captureInProgress]);
  
  const fetchSnapshotStats = useCallback(async () => {
    try {
      const response = await fetch(`${baseUrl}/api/snapshots/stats`);
      if (response.ok) {
        const data = await response.json();
        setSnapshotStats(data.data);
      }
    } catch (error) {
      console.error('Failed to fetch snapshot statistics:', error);
    }
  }, [baseUrl]);
  
  // Fetch stats on component mount and when failures change
  React.useEffect(() => {
    fetchSnapshotStats();
  }, [fetchSnapshotStats, failures.length]);

  const filteredFailures = useMemo(() => {
    let filtered = [...failures];

    // Apply type filter
    if (settings.filterByType && settings.filterByType.length > 0) {
      filtered = filtered.filter(f => settings.filterByType!.includes(f.failure_type));
    }

    // Apply sorting
    switch (settings.sortBy) {
      case 'timestamp':
        filtered.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        break;
      case 'frame':
        filtered.sort((a, b) => b.frameNumber - a.frameNumber);
        break;
      case 'severity':
        const severityOrder = { 'system': 4, 'timing': 3, 'accuracy': 2, 'detection': 1 };
        filtered.sort((a, b) => severityOrder[b.failure_type] - severityOrder[a.failure_type]);
        break;
    }

    return filtered.slice(0, maxDisplayCount);
  }, [failures, settings.filterByType, settings.sortBy, maxDisplayCount]);

  const groupedFailures = useMemo(() => {
    if (!settings.groupByType) return { all: filteredFailures };

    return filteredFailures.reduce((groups, failure) => {
      const type = failure.failure_type;
      if (!groups[type]) groups[type] = [];
      groups[type].push(failure);
      return groups;
    }, {} as Record<string, FailureSnapshotData[]>);
  }, [filteredFailures, settings.groupByType]);

  const failureTypeCounts = useMemo(() => {
    return failures.reduce((counts, failure) => {
      counts[failure.failure_type] = (counts[failure.failure_type] || 0) + 1;
      return counts;
    }, {} as Record<string, number>);
  }, [failures]);

  if (loading) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>Loading Failure Snapshots...</Typography>
        <Grid container spacing={2}>
          {[...Array(6)].map((_, i) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={i}>
              <Card>
                <Skeleton variant="rectangular" height={200} />
                <CardContent>
                  <Skeleton variant="text" />
                  <Skeleton variant="text" width="60%" />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ m: 2 }}>
        <Typography variant="h6">Failed to Load Snapshots</Typography>
        <Typography>{error}</Typography>
        {onRefresh && (
          <Button onClick={onRefresh} sx={{ mt: 1 }} startIcon={<Refresh />}>
            Retry
          </Button>
        )}
      </Alert>
    );
  }

  if (failures.length === 0) {
    return (
      <Alert severity="success" sx={{ m: 2 }}>
        <Typography variant="h6">No Failures Found</Typography>
        <Typography>All tests passed successfully - no failure snapshots to display.</Typography>
      </Alert>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            Failure Snapshots ({failures.length} failures)
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {onRefresh && (
              <IconButton onClick={onRefresh}>
                <Refresh />
              </IconButton>
            )}
            
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={settings.sortBy}
                label="Sort By"
                onChange={(e) => setSettings(prev => ({ ...prev, sortBy: e.target.value as any }))}
              >
                <MenuItem value="timestamp">Timestamp</MenuItem>
                <MenuItem value="frame">Frame Number</MenuItem>
                <MenuItem value="severity">Severity</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Filter Type</InputLabel>
              <Select
                value={settings.filterByType?.join(',') || 'all'}
                label="Filter Type"
                onChange={(e) => {
                  const value = e.target.value;
                  setSettings(prev => ({
                    ...prev,
                    filterByType: value === 'all' ? undefined : value.split(',') as any
                  }));
                }}
              >
                <MenuItem value="all">All Types</MenuItem>
                <MenuItem value="timing">Timing Only</MenuItem>
                <MenuItem value="accuracy">Accuracy Only</MenuItem>
                <MenuItem value="detection">Detection Only</MenuItem>
                <MenuItem value="system">System Only</MenuItem>
              </Select>
            </FormControl>

            <IconButton
              onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
              color={viewMode === 'grid' ? 'primary' : 'default'}
            >
              {viewMode === 'grid' ? <ViewModule /> : <ViewList />}
            </IconButton>
          </Box>
        </Box>

        {/* Enhanced failure type summary with statistics */}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
          {Object.entries(failureTypeCounts).map(([type, count]) => (
            <Badge badgeContent={count} color="error" key={type}>
              <Chip
                icon={type === 'timing' ? <AccessTime /> : 
                     type === 'accuracy' ? <Timeline /> :
                     type === 'detection' ? <Warning /> : <BugReport />}
                label={type}
                color={type === 'timing' ? 'error' : 
                       type === 'accuracy' ? 'warning' : 'info'}
                variant="outlined"
                size="small"
              />
            </Badge>
          ))}
          
          {snapshotStats && (
            <Paper sx={{ px: 2, py: 1, ml: 2, bgcolor: 'info.light' }}>
              <Typography variant="caption" color="info.contrastText">
                📊 Storage: {snapshotStats.total_size_mb}MB | 
                📸 Total: {snapshotStats.total_snapshots} snapshots |
                🔍 Types: {Object.keys(snapshotStats.failure_type_breakdown || {}).length}
              </Typography>
            </Paper>
          )}
        </Box>

        {/* Settings */}
        {showSettings && (
          <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableZoom}
                    onChange={(e) => setSettings(prev => ({ ...prev, enableZoom: e.target.checked }))}
                  />
                }
                label="Enable Zoom"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.lazyLoading}
                    onChange={(e) => setSettings(prev => ({ ...prev, lazyLoading: e.target.checked }))}
                  />
                }
                label="Lazy Loading"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.groupByType}
                    onChange={(e) => setSettings(prev => ({ ...prev, groupByType: e.target.checked }))}
                  />
                }
                label="Group by Type"
              />
              
              {showComparisonView && (
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.enableZoom}
                      onChange={(e) => setSettings(prev => ({ ...prev, enableZoom: e.target.checked }))}
                    />
                  }
                  label="Show Comparisons"
                />
              )}
              
              {enableAutomaticCapture && (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={fetchSnapshotStats}
                  startIcon={<Refresh />}
                  sx={{ ml: 2 }}
                >
                  Update Stats
                </Button>
              )}
            </Box>
          </Box>
        )}
      </Paper>

      {/* Content */}
      {viewMode === 'grid' ? (
        <Box>
          {settings.groupByType ? (
            Object.entries(groupedFailures).map(([type, typeFailures]) => (
              <Box key={type} sx={{ mb: 4 }}>
                <Typography variant="h6" gutterBottom sx={{ textTransform: 'capitalize' }}>
                  {type} Failures ({typeFailures.length})
                </Typography>
                <Grid container spacing={2}>
                  {typeFailures.map((failure) => (
                    <Grid item xs={12} sm={6} md={4} lg={3} key={failure.id}>
                      <SnapshotImage
                        snapshot={failure}
                        settings={settings}
                        onZoom={handleZoomSnapshot}
                        baseUrl={baseUrl}
                      />
                    </Grid>
                  ))}
                </Grid>
              </Box>
            ))
          ) : (
            <Grid container spacing={2}>
              {filteredFailures.map((failure) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={failure.id}>
                  <SnapshotImage
                    snapshot={failure}
                    settings={settings}
                    onZoom={handleZoomSnapshot}
                    baseUrl={baseUrl}
                  />
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      ) : (
        <Paper>
          <List>
            {filteredFailures.map((failure, index) => (
              <React.Fragment key={failure.id}>
                <ListItem>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                    <Box
                      sx={{
                        width: 80,
                        height: 60,
                        bgcolor: 'grey.100',
                        borderRadius: 1,
                        overflow: 'hidden',
                        cursor: settings.enableZoom ? 'pointer' : 'default'
                      }}
                      onClick={settings.enableZoom ? () => handleZoomSnapshot(failure) : undefined}
                    >
                      <img
                        src={failure.screenshot_path?.startsWith('http') 
                          ? failure.screenshot_path 
                          : `${baseUrl}${failure.screenshot_path}`}
                        alt={`Failure ${failure.frameNumber}`}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    </Box>
                    
                    <ListItemText
                      primary={`Frame ${failure.frameNumber} - ${failure.failure_type} failure`}
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            {failure.failure_reason}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(failure.timestamp).toLocaleString()}
                          </Typography>
                        </Box>
                      }
                    />
                    
                    <ListItemSecondaryAction>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip
                          label={failure.failure_type}
                          size="small"
                          color={failure.failure_type === 'timing' ? 'error' : 
                                 failure.failure_type === 'accuracy' ? 'warning' : 'info'}
                        />
                        {settings.enableZoom && (
                          <IconButton size="small" onClick={() => handleZoomSnapshot(failure)}>
                            <ZoomIn />
                          </IconButton>
                        )}
                      </Box>
                    </ListItemSecondaryAction>
                  </Box>
                </ListItem>
                {index < filteredFailures.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        </Paper>
      )}

      {/* Show count limitation message */}
      {failures.length > maxDisplayCount && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Showing first {maxDisplayCount} of {failures.length} failures. 
          Use filters to refine the results.
        </Alert>
      )}

      {/* Zoom Modal */}
      <ZoomModal
        state={zoomModal}
        onClose={closeZoomModal}
        snapshot={selectedSnapshot}
        baseUrl={baseUrl}
      />
    </Box>
  );
};

export default FailureSnapshotDisplay;