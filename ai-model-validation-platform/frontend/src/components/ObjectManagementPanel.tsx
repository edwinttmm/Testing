import React, { useState, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Button,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Stack,
  Alert,
  ButtonGroup,
  Divider,
} from '@mui/material';
import {
  Edit,
  Delete,
  Check,
  CallMerge,
  CallSplit,
  Visibility,
  VisibilityOff,
  Add,
  ContentCopy,
  SwapHoriz,
  FilterList,
  CheckCircle,
  Cancel,
  Info,
} from '@mui/icons-material';
import { GroundTruthObject, VRUType } from '../services/types';

interface ObjectManagementPanelProps {
  groundTruthObjects: GroundTruthObject[];
  currentFrame: number;
  selectedVruId: string | null;
  onObjectSelect: (vruId: string) => void;
  onObjectUpdate: (objectId: string, updates: Partial<GroundTruthObject>) => void;
  onObjectDelete: (objectId: string) => void;
  onObjectValidate: (objectId: string, validated: boolean) => void;
  onObjectCreate: (vruType: VRUType, position?: { x: number; y: number }) => void;
  onVRUMerge: (vruIds: string[]) => void;
  onVRUSplit: (vruId: string, splitData: any) => void;
  onBulkValidate: (objectIds: string[]) => void;
}

const ObjectManagementPanel: React.FC<ObjectManagementPanelProps> = ({
  groundTruthObjects,
  currentFrame,
  selectedVruId,
  onObjectSelect,
  onObjectUpdate,
  onObjectDelete,
  onObjectValidate,
  onObjectCreate,
  onVRUMerge,
  onVRUSplit,
  onBulkValidate,
}) => {
  // UI state
  const [mergeMode, setMergeMode] = useState(false);
  const [splitMode, setSplitMode] = useState(false);
  const [showValidatedOnly, setShowValidatedOnly] = useState(false);
  const [showAllFrames, setShowAllFrames] = useState(false);
  const [filterVRUType, setFilterVRUType] = useState<VRUType | 'all'>('all');
  
  // Selection state
  const [mergeSelection, setMergeSelection] = useState<Set<string>>(new Set());
  const [selectedObjects, setSelectedObjects] = useState<Set<string>>(new Set());
  
  // Dialog state
  const [createDialog, setCreateDialog] = useState(false);
  const [mergeDialog, setMergeDialog] = useState(false);
  const [splitDialog, setSplitDialog] = useState(false);
  const [editDialog, setEditDialog] = useState(false);
  const [editingObject, setEditingObject] = useState<GroundTruthObject | null>(null);
  
  // Form state
  const [newVRUType, setNewVRUType] = useState<VRUType>(VRUType.PEDESTRIAN);
  const [editVRUType, setEditVRUType] = useState<VRUType>(VRUType.PEDESTRIAN);
  const [editVRUId, setEditVRUId] = useState('');
  
  // Filter and display objects
  const filteredObjects = useMemo(() => {
    let objects = groundTruthObjects;
    
    // Frame filter
    if (!showAllFrames) {
      objects = objects.filter(obj => obj.frameNumber === currentFrame);
    }
    
    // Validation filter
    if (showValidatedOnly) {
      objects = objects.filter(obj => obj.validated);
    }
    
    // VRU type filter
    if (filterVRUType !== 'all') {
      objects = objects.filter(obj => obj.vruType === filterVRUType);
    }
    
    // Sort by frame number, then by VRU ID
    return objects.sort((a, b) => {
      if (a.frameNumber !== b.frameNumber) {
        return a.frameNumber - b.frameNumber;
      }
      return a.vruId.localeCompare(b.vruId);
    });
  }, [groundTruthObjects, currentFrame, showAllFrames, showValidatedOnly, filterVRUType]);
  
  // Object statistics
  const stats = useMemo(() => {
    const total = filteredObjects.length;
    const validated = filteredObjects.filter(obj => obj.validated).length;
    const byType = filteredObjects.reduce((acc, obj) => {
      acc[obj.vruType] = (acc[obj.vruType] || 0) + 1;
      return acc;
    }, {} as Record<VRUType, number>);
    
    const currentFrameCount = groundTruthObjects.filter(obj => obj.frameNumber === currentFrame).length;
    
    return { total, validated, byType, currentFrameCount };
  }, [filteredObjects, groundTruthObjects, currentFrame]);
  
  // VRU color mapping
  const getVRUColor = (vruType: VRUType): string => {
    const colors = {
      pedestrian: '#ff5722',
      cyclist: '#2196f3',
      motorcyclist: '#ff9800',
      wheelchair: '#9c27b0',
      scooter: '#4caf50',
    };
    return colors[vruType] || '#607d8b';
  };
  
  // Event handlers
  const handleObjectClick = useCallback((obj: GroundTruthObject) => {
    if (mergeMode) {
      const newSelection = new Set(mergeSelection);
      if (newSelection.has(obj.vruId)) {
        newSelection.delete(obj.vruId);
      } else {
        newSelection.add(obj.vruId);
      }
      setMergeSelection(newSelection);
    } else {
      onObjectSelect(obj.vruId);
    }
  }, [mergeMode, mergeSelection, onObjectSelect]);
  
  const handleVRUTypeChange = useCallback(async (objectId: string, newType: VRUType) => {
    onObjectUpdate(objectId, { vruType: newType });
  }, [onObjectUpdate]);
  
  const handleEditObject = useCallback((obj: GroundTruthObject) => {
    setEditingObject(obj);
    setEditVRUType(obj.vruType);
    setEditVRUId(obj.vruId);
    setEditDialog(true);
  }, []);
  
  const handleSaveEdit = useCallback(() => {
    if (editingObject) {
      onObjectUpdate(editingObject.id, {
        vruType: editVRUType,
        vruId: editVRUId,
      });
      setEditDialog(false);
      setEditingObject(null);
    }
  }, [editingObject, editVRUType, editVRUId, onObjectUpdate]);
  
  const handleCreateObject = useCallback(() => {
    onObjectCreate(newVRUType);
    setCreateDialog(false);
  }, [newVRUType, onObjectCreate]);
  
  const handleMergeVRUs = useCallback(() => {
    if (mergeSelection.size >= 2) {
      onVRUMerge(Array.from(mergeSelection));
      setMergeSelection(new Set());
      setMergeMode(false);
      setMergeDialog(false);
    }
  }, [mergeSelection, onVRUMerge]);
  
  const handleSplitVRU = useCallback(() => {
    if (selectedVruId) {
      onVRUSplit(selectedVruId, {});
      setSplitMode(false);
      setSplitDialog(false);
    }
  }, [selectedVruId, onVRUSplit]);
  
  const handleBulkValidateSelected = useCallback(() => {
    const objectIds = filteredObjects
      .filter(obj => selectedObjects.has(obj.id))
      .map(obj => obj.id);
    
    if (objectIds.length > 0) {
      onBulkValidate(objectIds);
      setSelectedObjects(new Set());
    }
  }, [filteredObjects, selectedObjects, onBulkValidate]);
  
  const handleSelectAll = useCallback(() => {
    const allIds = new Set(filteredObjects.map(obj => obj.id));
    setSelectedObjects(allIds);
  }, [filteredObjects]);
  
  const handleDeselectAll = useCallback(() => {
    setSelectedObjects(new Set());
  }, []);
  
  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">VRU Object Management</Typography>
          <Button
            size="small"
            startIcon={<Add />}
            onClick={() => setCreateDialog(true)}
            variant="outlined"
          >
            Create
          </Button>
        </Box>
        
        {/* Statistics */}
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip label={`${stats.total} objects`} size="small" />
            <Chip 
              label={`${stats.validated} validated`} 
              size="small" 
              color="success"
              variant={stats.validated > 0 ? 'filled' : 'outlined'}
            />
            <Chip 
              label={`${stats.currentFrameCount} in frame`} 
              size="small" 
              color="primary"
            />
          </Stack>
        </Box>
        
        {/* Controls */}
        <Box sx={{ mb: 2 }}>
          <Stack spacing={2}>
            {/* Mode buttons */}
            <ButtonGroup size="small" fullWidth>
              <Button
                variant={mergeMode ? 'contained' : 'outlined'}
                onClick={() => {
                  setMergeMode(!mergeMode);
                  setSplitMode(false);
                  setMergeSelection(new Set());
                }}
                startIcon={<CallMerge />}
              >
                Merge
              </Button>
              
              <Button
                variant={splitMode ? 'contained' : 'outlined'}
                onClick={() => {
                  setSplitMode(!splitMode);
                  setMergeMode(false);
                  setMergeSelection(new Set());
                }}
                startIcon={<CallSplit />}
              >
                Split
              </Button>
              
              <Button
                variant={showValidatedOnly ? 'contained' : 'outlined'}
                onClick={() => setShowValidatedOnly(!showValidatedOnly)}
                startIcon={showValidatedOnly ? <CheckCircle /> : <FilterList />}
              >
                {showValidatedOnly ? 'All' : 'Validated'}
              </Button>
            </ButtonGroup>
            
            {/* Additional filters */}
            <Stack direction="row" spacing={1}>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>VRU Type</InputLabel>
                <Select
                  value={filterVRUType}
                  label="VRU Type"
                  onChange={(e) => setFilterVRUType(e.target.value as VRUType | 'all')}
                >
                  <MenuItem value="all">All Types</MenuItem>
                  <MenuItem value="pedestrian">Pedestrian</MenuItem>
                  <MenuItem value="cyclist">Cyclist</MenuItem>
                  <MenuItem value="motorcyclist">Motorcyclist</MenuItem>
                  <MenuItem value="wheelchair">Wheelchair</MenuItem>
                  <MenuItem value="scooter">Scooter</MenuItem>
                </Select>
              </FormControl>
              
              <Button
                size="small"
                variant={showAllFrames ? 'contained' : 'outlined'}
                onClick={() => setShowAllFrames(!showAllFrames)}
                startIcon={showAllFrames ? <Visibility /> : <VisibilityOff />}
              >
                {showAllFrames ? 'All Frames' : 'Current Frame'}
              </Button>
            </Stack>
            
            {/* Bulk actions */}
            {selectedObjects.size > 0 && (
              <Box sx={{ p: 1, backgroundColor: '#e3f2fd', borderRadius: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2">
                    {selectedObjects.size} selected
                  </Typography>
                  <Button size="small" onClick={handleBulkValidateSelected}>
                    Validate Selected
                  </Button>
                  <Button size="small" onClick={handleDeselectAll}>
                    Deselect All
                  </Button>
                </Stack>
              </Box>
            )}
          </Stack>
        </Box>
        
        {/* Object List */}
        <Typography variant="subtitle2" gutterBottom>
          Objects ({filteredObjects.length})
          {!showAllFrames && (
            <Chip label={`Frame ${currentFrame}`} size="small" sx={{ ml: 1 }} />
          )}
        </Typography>
        
        <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
          <List dense>
            {filteredObjects.map((obj) => (
              <ListItem
                key={obj.id}
                sx={{
                  border: obj.vruId === selectedVruId ? '2px solid #2196f3' : '1px solid #ddd',
                  borderRadius: 1,
                  mb: 1,
                  backgroundColor: mergeSelection.has(obj.vruId) 
                    ? 'rgba(33, 150, 243, 0.1)' 
                    : selectedObjects.has(obj.id)
                    ? 'rgba(76, 175, 80, 0.1)'
                    : 'transparent',
                  cursor: 'pointer',
                }}
                onClick={() => handleObjectClick(obj)}
              >
                <Box sx={{ mr: 1 }}>
                  {(mergeMode || selectedObjects.size > 0) && (
                    <input
                      type="checkbox"
                      checked={mergeMode ? mergeSelection.has(obj.vruId) : selectedObjects.has(obj.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        if (mergeMode) {
                          const newSelection = new Set(mergeSelection);
                          if (e.target.checked) {
                            newSelection.add(obj.vruId);
                          } else {
                            newSelection.delete(obj.vruId);
                          }
                          setMergeSelection(newSelection);
                        } else {
                          const newSelection = new Set(selectedObjects);
                          if (e.target.checked) {
                            newSelection.add(obj.id);
                          } else {
                            newSelection.delete(obj.id);
                          }
                          setSelectedObjects(newSelection);
                        }
                      }}
                    />
                  )}
                </Box>
                
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip
                        label={obj.vruType}
                        size="small"
                        sx={{ 
                          backgroundColor: getVRUColor(obj.vruType), 
                          color: 'white',
                          minWidth: 80,
                        }}
                      />
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {obj.vruId}
                      </Typography>
                      {obj.validated && <CheckCircle color="success" fontSize="small" />}
                      {showAllFrames && (
                        <Chip 
                          label={`F${obj.frameNumber}`} 
                          size="small" 
                          variant="outlined"
                        />
                      )}
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="caption">
                        Confidence: {(obj.confidence * 100).toFixed(1)}%
                      </Typography>
                      <br />
                      <Typography variant="caption">
                        BBox: ({obj.bbox.x.toFixed(0)}, {obj.bbox.y.toFixed(0)}, 
                        {obj.bbox.width.toFixed(0)}×{obj.bbox.height.toFixed(0)})
                      </Typography>
                      {showAllFrames && (
                        <>
                          <br />
                          <Typography variant="caption">
                            Time: {(obj.timestampMs / 1000).toFixed(2)}s
                          </Typography>
                        </>
                      )}
                    </Box>
                  }
                />
                
                <ListItemSecondaryAction>
                  <Box sx={{ display: 'flex', gap: 0.5 }}>
                    <FormControl size="small" sx={{ minWidth: 100 }}>
                      <Select
                        value={obj.vruType}
                        onChange={(e) => handleVRUTypeChange(obj.id, e.target.value as VRUType)}
                        size="small"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MenuItem value="pedestrian">Pedestrian</MenuItem>
                        <MenuItem value="cyclist">Cyclist</MenuItem>
                        <MenuItem value="motorcyclist">Motorcyclist</MenuItem>
                        <MenuItem value="wheelchair">Wheelchair</MenuItem>
                        <MenuItem value="scooter">Scooter</MenuItem>
                      </Select>
                    </FormControl>
                    
                    <Tooltip title="Edit Object">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditObject(obj);
                        }}
                      >
                        <Edit />
                      </IconButton>
                    </Tooltip>
                    
                    <Tooltip title={obj.validated ? 'Mark as Pending' : 'Validate'}>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          onObjectValidate(obj.id, !obj.validated);
                        }}
                        color={obj.validated ? 'success' : 'default'}
                      >
                        <Check />
                      </IconButton>
                    </Tooltip>
                    
                    <Tooltip title="Delete Object">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          onObjectDelete(obj.id);
                        }}
                        color="error"
                      >
                        <Delete />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
            
            {filteredObjects.length === 0 && (
              <ListItem>
                <ListItemText
                  primary="No objects found"
                  secondary={
                    showAllFrames 
                      ? "No objects match the current filters"
                      : "No objects in current frame"
                  }
                  sx={{ textAlign: 'center' }}
                />
              </ListItem>
            )}
          </List>
        </Box>
        
        {/* Merge/Split Action Panels */}
        {mergeMode && mergeSelection.size > 1 && (
          <Box sx={{ mt: 2, p: 2, border: '1px solid #2196f3', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Merge {mergeSelection.size} VRUs
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Selected: {Array.from(mergeSelection).join(', ')}
            </Typography>
            <Button
              variant="contained"
              size="small"
              onClick={() => setMergeDialog(true)}
              startIcon={<CallMerge />}
            >
              Merge Selected
            </Button>
          </Box>
        )}
        
        {splitMode && selectedVruId && (
          <Box sx={{ mt: 2, p: 2, border: '1px solid #ff9800', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Split VRU: {selectedVruId}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Click on the bounding box to create split points, then confirm split
            </Typography>
            <Button
              variant="contained"
              size="small"
              onClick={() => setSplitDialog(true)}
              startIcon={<CallSplit />}
            >
              Confirm Split
            </Button>
          </Box>
        )}
        
        {/* Bulk selection actions */}
        {!mergeMode && !splitMode && selectedObjects.size > 0 && (
          <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
            <Button size="small" onClick={handleSelectAll}>
              Select All
            </Button>
            <Button size="small" onClick={handleBulkValidateSelected}>
              Validate Selected ({selectedObjects.size})
            </Button>
          </Box>
        )}
      </CardContent>
      
      {/* Create Object Dialog */}
      <Dialog open={createDialog} onClose={() => setCreateDialog(false)}>
        <DialogTitle>Create New Object</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>VRU Type</InputLabel>
            <Select
              value={newVRUType}
              label="VRU Type"
              onChange={(e) => setNewVRUType(e.target.value as VRUType)}
            >
              <MenuItem value="pedestrian">Pedestrian</MenuItem>
              <MenuItem value="cyclist">Cyclist</MenuItem>
              <MenuItem value="motorcyclist">Motorcyclist</MenuItem>
              <MenuItem value="wheelchair">Wheelchair</MenuItem>
              <MenuItem value="scooter">Scooter</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateObject} variant="contained">
            Create
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Edit Object Dialog */}
      <Dialog open={editDialog} onClose={() => setEditDialog(false)}>
        <DialogTitle>Edit Object</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="VRU ID"
              value={editVRUId}
              onChange={(e) => setEditVRUId(e.target.value)}
              fullWidth
            />
            <FormControl fullWidth>
              <InputLabel>VRU Type</InputLabel>
              <Select
                value={editVRUType}
                label="VRU Type"
                onChange={(e) => setEditVRUType(e.target.value as VRUType)}
              >
                <MenuItem value="pedestrian">Pedestrian</MenuItem>
                <MenuItem value="cyclist">Cyclist</MenuItem>
                <MenuItem value="motorcyclist">Motorcyclist</MenuItem>
                <MenuItem value="wheelchair">Wheelchair</MenuItem>
                <MenuItem value="scooter">Scooter</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialog(false)}>Cancel</Button>
          <Button onClick={handleSaveEdit} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Merge Confirmation Dialog */}
      <Dialog open={mergeDialog} onClose={() => setMergeDialog(false)}>
        <DialogTitle>Confirm VRU Merge</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Are you sure you want to merge these VRUs?
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Selected VRUs: {Array.from(mergeSelection).join(', ')}
          </Typography>
          <Alert severity="warning" sx={{ mt: 2 }}>
            This action will combine all selected VRUs into a single persistent ID. 
            This cannot be undone.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMergeDialog(false)}>Cancel</Button>
          <Button onClick={handleMergeVRUs} variant="contained" color="warning">
            Merge VRUs
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Split Confirmation Dialog */}
      <Dialog open={splitDialog} onClose={() => setSplitDialog(false)}>
        <DialogTitle>Confirm VRU Split</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Split VRU: {selectedVruId}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            This will create a new VRU with a separate tracking ID.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSplitDialog(false)}>Cancel</Button>
          <Button onClick={handleSplitVRU} variant="contained" color="warning">
            Split VRU
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  );
};

export default ObjectManagementPanel;