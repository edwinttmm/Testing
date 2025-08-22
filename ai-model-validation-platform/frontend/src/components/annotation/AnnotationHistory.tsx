import React, { useRef, useCallback, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  Chip,
  Stack,
} from '@mui/material';
import {
  Undo,
  Redo,
  History,
  Add,
  Edit,
  Delete,
  DriveFileMove,
  ContentCopy,
  Visibility,
  VisibilityOff,
} from '@mui/icons-material';
import { useAnnotation } from './AnnotationManager';
import { AnnotationAction, AnnotationShape } from './types';

interface AnnotationHistoryProps {
  maxHistorySize?: number;
  showHistoryPanel?: boolean;
}

const AnnotationHistory: React.FC<AnnotationHistoryProps> = ({
  maxHistorySize = 100,
  showHistoryPanel = false,
}) => {
  const { state, actions } = useAnnotation();
  
  // History state
  const historyRef = useRef<AnnotationAction[]>([]);
  const historyIndexRef = useRef(-1);
  const shapesHistoryRef = useRef<AnnotationShape[][]>([]);

  // Generate unique ID for actions
  const generateActionId = useCallback(() => {
    return `action_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
  }, []);

  // Create action record
  const createAction = useCallback((
    type: AnnotationAction['type'],
    description: string,
    shapeIds: string[],
    before?: any,
    after?: any
  ): AnnotationAction => {
    return {
      id: generateActionId(),
      type,
      timestamp: Date.now(),
      description,
      shapeIds,
      before,
      after,
    };
  }, [generateActionId]);

  // Add action to history
  const addToHistory = useCallback((action: AnnotationAction, currentShapes: AnnotationShape[]) => {
    const history = historyRef.current;
    const shapesHistory = shapesHistoryRef.current;
    const currentIndex = historyIndexRef.current;

    // Remove future history if we're not at the end
    if (currentIndex < history.length - 1) {
      historyRef.current = history.slice(0, currentIndex + 1);
      shapesHistoryRef.current = shapesHistory.slice(0, currentIndex + 1);
    }

    // Add new action and shapes state
    historyRef.current.push(action);
    shapesHistoryRef.current.push([...currentShapes]);

    // Limit history size
    if (historyRef.current.length > maxHistorySize) {
      historyRef.current = historyRef.current.slice(-maxHistorySize);
      shapesHistoryRef.current = shapesHistoryRef.current.slice(-maxHistorySize);
    }

    historyIndexRef.current = historyRef.current.length - 1;
  }, [maxHistorySize]);

  // Track shape changes and record history
  useEffect(() => {
    const lastShapesState = shapesHistoryRef.current[shapesHistoryRef.current.length - 1] || [];
    const currentShapes = state.shapes;

    // Skip if shapes haven't changed
    if (JSON.stringify(lastShapesState) === JSON.stringify(currentShapes)) {
      return;
    }

    // Analyze what changed
    const addedShapes = currentShapes.filter(shape => 
      !lastShapesState.find(oldShape => oldShape.id === shape.id)
    );
    
    const removedShapes = lastShapesState.filter(oldShape => 
      !currentShapes.find(shape => shape.id === oldShape.id)
    );
    
    const modifiedShapes = currentShapes.filter(shape => {
      const oldShape = lastShapesState.find(oldShape => oldShape.id === shape.id);
      return oldShape && JSON.stringify(oldShape) !== JSON.stringify(shape);
    });

    // Create appropriate action
    let action: AnnotationAction | null = null;

    if (addedShapes.length > 0 && removedShapes.length === 0 && modifiedShapes.length === 0) {
      // Pure addition
      action = createAction(
        'create',
        `Created ${addedShapes.length} shape(s)`,
        addedShapes.map(s => s.id),
        undefined,
        addedShapes
      );
    } else if (removedShapes.length > 0 && addedShapes.length === 0 && modifiedShapes.length === 0) {
      // Pure deletion
      action = createAction(
        'delete',
        `Deleted ${removedShapes.length} shape(s)`,
        removedShapes.map(s => s.id),
        removedShapes,
        undefined
      );
    } else if (modifiedShapes.length > 0 && addedShapes.length === 0 && removedShapes.length === 0) {
      // Pure modification
      const beforeShapes = modifiedShapes.map(shape => 
        lastShapesState.find(oldShape => oldShape.id === shape.id)
      ).filter(Boolean);
      
      action = createAction(
        'update',
        `Updated ${modifiedShapes.length} shape(s)`,
        modifiedShapes.map(s => s.id),
        beforeShapes,
        modifiedShapes
      );
    } else if (addedShapes.length > 0 && removedShapes.length > 0) {
      // Possible copy/paste or complex operation
      action = createAction(
        'create',
        `Complex operation: +${addedShapes.length} -${removedShapes.length}`,
        [...addedShapes.map(s => s.id), ...removedShapes.map(s => s.id)],
        removedShapes,
        addedShapes
      );
    }

    // Add to history if we have a valid action
    if (action) {
      addToHistory(action, currentShapes);
    }
  }, [state.shapes, createAction, addToHistory]);

  // Undo operation
  const performUndo = useCallback(() => {
    if (historyIndexRef.current <= 0) return false;

    historyIndexRef.current--;
    const targetShapes = shapesHistoryRef.current[historyIndexRef.current] || [];
    actions.setShapes(targetShapes);
    
    return true;
  }, [actions]);

  // Redo operation
  const performRedo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return false;

    historyIndexRef.current++;
    const targetShapes = shapesHistoryRef.current[historyIndexRef.current] || [];
    actions.setShapes(targetShapes);
    
    return true;
  }, [actions]);

  // Enhanced undo with action-specific logic
  const enhancedUndo = useCallback(() => {
    if (historyIndexRef.current <= 0) return;

    const currentAction = historyRef.current[historyIndexRef.current];
    
    // Apply reverse operation based on action type
    switch (currentAction.type) {
      case 'create':
        if (currentAction.after && Array.isArray(currentAction.after)) {
          const shapeIds = currentAction.after.map((shape: AnnotationShape) => shape.id);
          actions.deleteShapes(shapeIds);
        }
        break;
        
      case 'delete':
        if (currentAction.before && Array.isArray(currentAction.before)) {
          currentAction.before.forEach((shape: AnnotationShape) => {
            actions.addShape(shape);
          });
        }
        break;
        
      case 'update':
        if (currentAction.before && Array.isArray(currentAction.before)) {
          currentAction.before.forEach((shape: AnnotationShape) => {
            actions.updateShape(shape.id, shape);
          });
        }
        break;
        
      case 'move':
        // For moves, we need to calculate reverse delta
        if (currentAction.before && currentAction.after) {
          // This would require storing position deltas
          performUndo();
          return;
        }
        break;
        
      default:
        performUndo();
        return;
    }

    historyIndexRef.current--;
  }, [actions, performUndo]);

  // Enhanced redo with action-specific logic
  const enhancedRedo = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;

    historyIndexRef.current++;
    const actionToRedo = historyRef.current[historyIndexRef.current];
    
    // Apply action
    switch (actionToRedo.type) {
      case 'create':
        if (actionToRedo.after && Array.isArray(actionToRedo.after)) {
          actionToRedo.after.forEach((shape: AnnotationShape) => {
            actions.addShape(shape);
          });
        }
        break;
        
      case 'delete':
        if (actionToRedo.before && Array.isArray(actionToRedo.before)) {
          const shapeIds = actionToRedo.before.map((shape: AnnotationShape) => shape.id);
          actions.deleteShapes(shapeIds);
        }
        break;
        
      case 'update':
        if (actionToRedo.after && Array.isArray(actionToRedo.after)) {
          actionToRedo.after.forEach((shape: AnnotationShape) => {
            actions.updateShape(shape.id, shape);
          });
        }
        break;
        
      default:
        performRedo();
        return;
    }
  }, [actions, performRedo]);

  // Jump to specific point in history
  const jumpToHistoryPoint = useCallback((index: number) => {
    if (index < 0 || index >= shapesHistoryRef.current.length) return;

    historyIndexRef.current = index;
    const targetShapes = shapesHistoryRef.current[index] || [];
    actions.setShapes(targetShapes);
  }, [actions]);

  // Clear history
  const clearHistory = useCallback(() => {
    historyRef.current = [];
    shapesHistoryRef.current = [state.shapes];
    historyIndexRef.current = 0;
  }, [state.shapes]);

  // Get action icon
  const getActionIcon = useCallback((action: AnnotationAction) => {
    switch (action.type) {
      case 'create': return <Add />;
      case 'update': return <Edit />;
      case 'delete': return <Delete />;
      case 'move': return <DriveFileMove />;
      default: return <History />;
    }
  }, []);

  // Get action color
  const getActionColor = useCallback((action: AnnotationAction) => {
    switch (action.type) {
      case 'create': return 'success';
      case 'update': return 'info';
      case 'delete': return 'error';
      case 'move': return 'warning';
      default: return 'default';
    }
  }, []);

  // Format time for display
  const formatTime = useCallback((timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  }, []);

  // Get history stats
  const historyStats = {
    totalActions: historyRef.current.length,
    currentPosition: historyIndexRef.current + 1,
    canUndo: historyIndexRef.current > 0,
    canRedo: historyIndexRef.current < historyRef.current.length - 1,
    actionsAhead: historyRef.current.length - historyIndexRef.current - 1,
  };

  // Expose undo/redo functions to parent
  useEffect(() => {
    // Override the default undo/redo with enhanced versions
    const originalUndo = actions.undo;
    const originalRedo = actions.redo;

    // Replace with enhanced versions
    (actions as any).undo = enhancedUndo;
    (actions as any).redo = enhancedRedo;

    return () => {
      // Restore original functions on cleanup
      (actions as any).undo = originalUndo;
      (actions as any).redo = originalRedo;
    };
  }, [actions, enhancedUndo, enhancedRedo]);

  if (!showHistoryPanel) {
    // Just provide the functionality without UI
    return null;
  }

  return (
    <Paper elevation={2} sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h6">History</Typography>
        <Stack direction="row" spacing={1}>
          <Tooltip title={`Undo (${historyStats.canUndo ? 'Available' : 'Nothing to undo'})`}>
            <span>
              <IconButton
                size="small"
                onClick={enhancedUndo}
                disabled={!historyStats.canUndo}
              >
                <Undo />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={`Redo (${historyStats.canRedo ? `${historyStats.actionsAhead} ahead` : 'Nothing to redo'})`}>
            <span>
              <IconButton
                size="small"
                onClick={enhancedRedo}
                disabled={!historyStats.canRedo}
              >
                <Redo />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Stack>

      {/* History Stats */}
      <Box sx={{ mb: 2 }}>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          <Chip
            label={`${historyStats.currentPosition}/${historyStats.totalActions}`}
            size="small"
            variant="outlined"
          />
          {historyStats.totalActions > 0 && (
            <Chip
              label={`${historyStats.actionsAhead} ahead`}
              size="small"
              color={historyStats.actionsAhead > 0 ? 'warning' : 'default'}
            />
          )}
        </Stack>
      </Box>

      {/* History List */}
      <Box sx={{ flex: 1, overflowY: 'auto' }}>
        <List dense>
          {historyRef.current.map((action, index) => (
            <ListItem
              key={action.id}
              sx={{
                cursor: 'pointer',
                borderRadius: 1,
                mb: 0.5,
                bgcolor: index === historyIndexRef.current ? 'primary.light' : 
                         index > historyIndexRef.current ? 'action.disabled' : 'transparent',
                opacity: index > historyIndexRef.current ? 0.5 : 1,
                '&:hover': {
                  bgcolor: index === historyIndexRef.current ? 'primary.light' : 'action.hover'
                }
              }}
              onClick={() => jumpToHistoryPoint(index)}
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                <Box sx={{ 
                  color: getActionColor(action) === 'default' ? 'text.secondary' : `${getActionColor(action)}.main` 
                }}>
                  {getActionIcon(action)}
                </Box>
              </ListItemIcon>
              
              <ListItemText
                primary={action.description}
                secondary={
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Typography variant="caption">
                      {formatTime(action.timestamp)}
                    </Typography>
                    {action.shapeIds.length > 0 && (
                      <Chip
                        label={`${action.shapeIds.length} shape${action.shapeIds.length !== 1 ? 's' : ''}`}
                        size="small"
                        variant="outlined"
                        sx={{ height: 16, fontSize: '0.65rem' }}
                      />
                    )}
                  </Stack>
                }
                primaryTypographyProps={{ 
                  variant: 'body2',
                  color: index > historyIndexRef.current ? 'text.disabled' : 'text.primary'
                }}
                secondaryTypographyProps={{
                  component: 'div'
                }}
              />
              
              {index === historyIndexRef.current && (
                <Box sx={{ 
                  position: 'absolute', 
                  left: 0, 
                  top: 0, 
                  bottom: 0, 
                  width: 3, 
                  bgcolor: 'primary.main',
                  borderRadius: '0 2px 2px 0'
                }} />
              )}
            </ListItem>
          ))}
          
          {historyRef.current.length === 0 && (
            <ListItem>
              <ListItemText
                primary="No history yet"
                secondary="Actions will appear here as you make changes"
                sx={{ textAlign: 'center', py: 2 }}
                primaryTypographyProps={{ color: 'text.secondary' }}
                secondaryTypographyProps={{ color: 'text.secondary' }}
              />
            </ListItem>
          )}
        </List>
      </Box>

      {/* Clear History Button */}
      {historyRef.current.length > 0 && (
        <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Tooltip title="Clear all history (cannot be undone)">
            <IconButton
              onClick={clearHistory}
              size="small"
              color="error"
              sx={{ width: '100%' }}
            >
              <Delete />
              <Typography variant="caption" sx={{ ml: 1 }}>
                Clear History
              </Typography>
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Paper>
  );
};

export default AnnotationHistory;