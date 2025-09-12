import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Switch,
  FormControlLabel,
  Slider,
  Box,
  Stack,
  Button,
  Chip,
  FormGroup,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  CenterFocusStrong as CenterIcon,
  RestartAlt as ResetIcon,
  Save as SaveIcon
} from '@mui/icons-material';

export interface BoundaryBoxControlsProps {
  // Grid and snapping controls
  snapToGrid: boolean;
  onSnapToGridChange: (value: boolean) => void;
  showSnapGrid: boolean;
  onShowSnapGridChange: (value: boolean) => void;
  gridSize: number;
  onGridSizeChange: (value: number) => void;

  // Display controls
  showConfidence: boolean;
  onShowConfidenceChange: (value: boolean) => void;
  showCoordinates: boolean;
  onShowCoordinatesChange: (value: boolean) => void;
  showGroundTruth: boolean;
  onShowGroundTruthChange: (value: boolean) => void;

  // Frame 80 specific controls
  highlightFrame80: boolean;
  onHighlightFrame80Change: (value: boolean) => void;
  currentFrame: number;

  // Interaction controls
  enableDragAndDrop: boolean;
  onEnableDragAndDropChange: (value: boolean) => void;
  debugMode: boolean;
  onDebugModeChange: (value: boolean) => void;

  // Filtering controls
  confidenceThreshold: number;
  onConfidenceThresholdChange: (value: number) => void;
  selectedVRUTypes: string[];
  onVRUTypeSelectionChange: (types: string[]) => void;

  // Action handlers
  onResetView: () => void;
  onSaveSettings: () => void;
  onCenterView: () => void;

  // Statistics
  totalDetections: number;
  visibleDetections: number;
  pedestrianCount: number;
}

const VRU_TYPES = [
  { value: 'pedestrian', label: 'Pedestrian', color: '#ff4444' },
  { value: 'cyclist', label: 'Cyclist', color: '#4444ff' },
  { value: 'motorcyclist', label: 'Motorcyclist', color: '#ff8800' },
  { value: 'wheelchair_user', label: 'Wheelchair', color: '#8844ff' },
  { value: 'scooter_rider', label: 'Scooter', color: '#44ff88' }
];

export const BoundaryBoxControls: React.FC<BoundaryBoxControlsProps> = ({
  snapToGrid,
  onSnapToGridChange,
  showSnapGrid,
  onShowSnapGridChange,
  gridSize,
  onGridSizeChange,
  showConfidence,
  onShowConfidenceChange,
  showCoordinates,
  onShowCoordinatesChange,
  showGroundTruth,
  onShowGroundTruthChange,
  highlightFrame80,
  onHighlightFrame80Change,
  currentFrame,
  enableDragAndDrop,
  onEnableDragAndDropChange,
  debugMode,
  onDebugModeChange,
  confidenceThreshold,
  onConfidenceThresholdChange,
  selectedVRUTypes,
  onVRUTypeSelectionChange,
  onResetView,
  onSaveSettings,
  onCenterView,
  totalDetections,
  visibleDetections,
  pedestrianCount
}) => {

  const handleVRUTypeChange = (event: any) => {
    const value = event.target.value;
    onVRUTypeSelectionChange(typeof value === 'string' ? value.split(',') : value);
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SettingsIcon />
          Boundary Box Controls
        </Typography>

        {/* Statistics Section */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>Detection Statistics</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Chip label={`Total: ${totalDetections}`} size="small" color="primary" />
            <Chip label={`Visible: ${visibleDetections}`} size="small" color="secondary" />
            <Chip label={`Pedestrians: ${pedestrianCount}`} size="small" color="success" />
            {currentFrame === 80 && (
              <Chip label="FRAME 80" size="small" color="warning" />
            )}
          </Stack>
        </Box>

        {/* Grid and Snapping Controls */}
        <Typography variant="subtitle1" gutterBottom>Grid & Snapping</Typography>
        <Box sx={{ mb: 3 }}>
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={snapToGrid}
                  onChange={(e) => onSnapToGridChange(e.target.checked)}
                  color="primary"
                />
              }
              label="Enable Grid Snapping"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={showSnapGrid}
                  onChange={(e) => onShowSnapGridChange(e.target.checked)}
                  disabled={!snapToGrid}
                  color="primary"
                />
              }
              label="Show Grid Lines"
            />
          </FormGroup>

          <Box sx={{ mt: 2 }}>
            <Typography gutterBottom>Grid Size: {gridSize}px</Typography>
            <Slider
              value={gridSize}
              onChange={(_, value) => onGridSizeChange(value as number)}
              min={5}
              max={50}
              step={5}
              disabled={!snapToGrid}
              marks={[
                { value: 10, label: '10' },
                { value: 20, label: '20' },
                { value: 30, label: '30' },
                { value: 40, label: '40' },
              ]}
            />
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Display Controls */}
        <Typography variant="subtitle1" gutterBottom>Display Options</Typography>
        <Box sx={{ mb: 3 }}>
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={showConfidence}
                  onChange={(e) => onShowConfidenceChange(e.target.checked)}
                  color="primary"
                />
              }
              label="Show Confidence Scores"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={showCoordinates}
                  onChange={(e) => onShowCoordinatesChange(e.target.checked)}
                  color="primary"
                />
              }
              label="Show Coordinates"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={showGroundTruth}
                  onChange={(e) => onShowGroundTruthChange(e.target.checked)}
                  color="success"
                />
              }
              label="Show Ground Truth"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={highlightFrame80}
                  onChange={(e) => onHighlightFrame80Change(e.target.checked)}
                  color="warning"
                />
              }
              label="Highlight Frame 80"
            />
          </FormGroup>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Interaction Controls */}
        <Typography variant="subtitle1" gutterBottom>Interaction</Typography>
        <Box sx={{ mb: 3 }}>
          <FormGroup>
            <FormControlLabel
              control={
                <Switch
                  checked={enableDragAndDrop}
                  onChange={(e) => onEnableDragAndDropChange(e.target.checked)}
                  color="primary"
                />
              }
              label="Enable Drag & Drop"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={debugMode}
                  onChange={(e) => onDebugModeChange(e.target.checked)}
                  color="secondary"
                />
              }
              label="Debug Mode"
            />
          </FormGroup>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Filtering Controls */}
        <Typography variant="subtitle1" gutterBottom>Filtering</Typography>
        <Box sx={{ mb: 3 }}>
          <Box sx={{ mb: 2 }}>
            <Typography gutterBottom>
              Confidence Threshold: {Math.round(confidenceThreshold * 100)}%
            </Typography>
            <Slider
              value={confidenceThreshold}
              onChange={(_, value) => onConfidenceThresholdChange(value as number)}
              min={0}
              max={1}
              step={0.1}
              marks={[
                { value: 0.5, label: '50%' },
                { value: 0.7, label: '70%' },
                { value: 0.9, label: '90%' },
              ]}
              valueLabelDisplay="auto"
              valueLabelFormat={(value) => `${Math.round(value * 100)}%`}
            />
          </Box>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>VRU Types</InputLabel>
            <Select
              multiple
              value={selectedVRUTypes}
              onChange={handleVRUTypeChange}
              label="VRU Types"
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {(selected as string[]).map((value) => {
                    const vruType = VRU_TYPES.find(type => type.value === value);
                    return (
                      <Chip
                        key={value}
                        label={vruType?.label || value}
                        size="small"
                        sx={{ bgcolor: vruType?.color, color: 'white' }}
                      />
                    );
                  })}
                </Box>
              )}
            >
              {VRU_TYPES.map((type) => (
                <MenuItem key={type.value} value={type.value}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        bgcolor: type.color,
                        borderRadius: '50%'
                      }}
                    />
                    {type.label}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Action Buttons */}
        <Typography variant="subtitle1" gutterBottom>Actions</Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ gap: 1 }}>
          <Tooltip title="Reset to original view">
            <Button
              variant="outlined"
              size="small"
              startIcon={<ResetIcon />}
              onClick={onResetView}
            >
              Reset
            </Button>
          </Tooltip>

          <Tooltip title="Center view on detections">
            <Button
              variant="outlined"
              size="small"
              startIcon={<CenterIcon />}
              onClick={onCenterView}
            >
              Center
            </Button>
          </Tooltip>

          <Tooltip title="Save current settings">
            <Button
              variant="contained"
              size="small"
              startIcon={<SaveIcon />}
              onClick={onSaveSettings}
              color="primary"
            >
              Save
            </Button>
          </Tooltip>
        </Stack>

        {/* Frame 80 Special Notice */}
        {currentFrame === 80 && (
          <Box sx={{ mt: 3, p: 2, bgcolor: 'warning.light', borderRadius: 1 }}>
            <Typography variant="subtitle2" color="warning.dark" gutterBottom>
              🎯 Frame 80 - Validation Frame
            </Typography>
            <Typography variant="body2" color="warning.dark">
              This frame contains special pedestrian detection validation data for testing purposes.
            </Typography>
          </Box>
        )}

        {/* Debug Information */}
        {debugMode && (
          <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>Debug Information</Typography>
            <Typography variant="caption" component="div">
              Frame: {currentFrame}
            </Typography>
            <Typography variant="caption" component="div">
              Total Detections: {totalDetections}
            </Typography>
            <Typography variant="caption" component="div">
              Visible Detections: {visibleDetections}
            </Typography>
            <Typography variant="caption" component="div">
              Grid Size: {gridSize}px
            </Typography>
            <Typography variant="caption" component="div">
              Confidence Threshold: {Math.round(confidenceThreshold * 100)}%
            </Typography>
            <Typography variant="caption" component="div">
              Selected VRU Types: {selectedVRUTypes.join(', ')}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default BoundaryBoxControls;