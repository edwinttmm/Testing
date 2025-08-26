import React, { useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Box,
} from '@mui/material';
import { useAnnotation } from './AnnotationManager';
import { KeyboardShortcut } from './types';

interface KeyboardShortcutsProps {
  onToolChange?: (toolId: string) => void;
  onFrameNavigate?: (direction: 'prev' | 'next') => void;
  onPlayPause?: () => void;
  disabled?: boolean;
  showHelpDialog?: boolean;
  onHelpDialogClose?: () => void;
}

const KeyboardShortcuts: React.FC<KeyboardShortcutsProps> = ({
  onToolChange,
  onFrameNavigate,
  onPlayPause,
  disabled = false,
  showHelpDialog = false,
  onHelpDialogClose,
}) => {
  const { state, actions } = useAnnotation();
  const pressedKeysRef = useRef(new Set<string>());

  // Define all keyboard shortcuts - memoized to prevent re-creation
  const shortcuts: KeyboardShortcut[] = useMemo(() => [
    // Tool Selection
    { key: 'v', description: 'Select Tool', action: () => { actions.setActiveTool('select'); onToolChange?.('select'); } },
    { key: 'r', description: 'Rectangle Tool', action: () => { actions.setActiveTool('rectangle'); onToolChange?.('rectangle'); } },
    { key: 'p', description: 'Polygon Tool', action: () => { actions.setActiveTool('polygon'); onToolChange?.('polygon'); } },
    { key: 'b', description: 'Brush Tool', action: () => { actions.setActiveTool('brush'); onToolChange?.('brush'); } },
    { key: 't', description: 'Point Tool', action: () => { actions.setActiveTool('point'); onToolChange?.('point'); } },

    // Edit Operations
    { key: 'z', ctrlKey: true, description: 'Undo', action: () => actions.undo() },
    { key: 'y', ctrlKey: true, description: 'Redo', action: () => actions.redo() },
    { key: 'z', ctrlKey: true, shiftKey: true, description: 'Redo (Alt)', action: () => actions.redo() },
    { key: 'c', ctrlKey: true, description: 'Copy', action: () => {
      const selected = actions.getSelectedShapes();
      if (selected.length > 0) actions.copyShapes(selected);
    }},
    { key: 'v', ctrlKey: true, description: 'Paste', action: () => {
      if (state.clipboard.length > 0) actions.pasteShapes();
    }},
    { key: 'x', ctrlKey: true, description: 'Cut', action: () => {
      const selected = actions.getSelectedShapes();
      if (selected.length > 0) {
        actions.copyShapes(selected);
        actions.deleteShapes(selected.map(s => s.id));
      }
    }},
    { key: 'a', ctrlKey: true, description: 'Select All', action: () => {
      actions.selectShapes(state.shapes.map(s => s.id));
    }},
    { key: 'd', ctrlKey: true, description: 'Duplicate', action: () => {
      const selected = actions.getSelectedShapes();
      if (selected.length > 0) {
        actions.copyShapes(selected);
        actions.pasteShapes({ x: 10, y: 10 });
      }
    }},

    // Delete Operations
    { key: 'Delete', description: 'Delete Selected', action: () => {
      const selected = actions.getSelectedShapes();
      if (selected.length > 0) actions.deleteShapes(selected.map(s => s.id));
    }},
    { key: 'Backspace', description: 'Delete Selected', action: () => {
      const selected = actions.getSelectedShapes();
      if (selected.length > 0) actions.deleteShapes(selected.map(s => s.id));
    }},

    // Selection Operations
    { key: 'Escape', description: 'Clear Selection', action: () => actions.clearSelection() },

    // Navigation
    { key: 'ArrowLeft', description: 'Previous Frame', action: () => onFrameNavigate?.('prev') },
    { key: 'ArrowRight', description: 'Next Frame', action: () => onFrameNavigate?.('next') },
    { key: ' ', description: 'Play/Pause', action: () => onPlayPause?.() },

    // View Controls
    { key: '0', description: 'Zoom to Fit', action: () => actions.setTransform({ scale: 1, translateX: 0, translateY: 0 }) },
    { key: '=', description: 'Zoom In', action: () => {
      const newScale = Math.min(state.canvasTransform.scale * 1.2, 5);
      actions.setTransform({ scale: newScale });
    }},
    { key: '-', description: 'Zoom Out', action: () => {
      const newScale = Math.max(state.canvasTransform.scale / 1.2, 0.1);
      actions.setTransform({ scale: newScale });
    }},
    { key: '1', description: 'Zoom 100%', action: () => actions.setTransform({ scale: 1 }) },
    { key: '2', description: 'Zoom 200%', action: () => actions.setTransform({ scale: 2 }) },
    { key: '5', description: 'Zoom 50%', action: () => actions.setTransform({ scale: 0.5 }) },

    // Grid and Snap
    { key: 'g', description: 'Toggle Grid', action: () => {
      actions.updateSettings({ showGrid: !state.settings.showGrid });
    }},
    { key: 's', description: 'Toggle Snap to Grid', action: () => {
      actions.updateSettings({ snapToGrid: !state.settings.snapToGrid });
    }},

    // Label Assignment (1-9 for different VRU types or labels)
    { key: '1', shiftKey: true, description: 'Label: Pedestrian', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { label: 'pedestrian' });
      });
    }},
    { key: '2', shiftKey: true, description: 'Label: Cyclist', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { label: 'cyclist' });
      });
    }},
    { key: '3', shiftKey: true, description: 'Label: Motorcyclist', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { label: 'motorcyclist' });
      });
    }},
    { key: '4', shiftKey: true, description: 'Label: Wheelchair User', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { label: 'wheelchair_user' });
      });
    }},
    { key: '5', shiftKey: true, description: 'Label: Scooter Rider', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { label: 'scooter_rider' });
      });
    }},

    // Advanced Selection
    { key: 'Tab', description: 'Select Next Shape', action: () => {
      if (state.shapes.length === 0) return;
      
      const currentIndex = state.selectedShapeIds.length > 0 
        ? state.shapes.findIndex(s => s.id === state.selectedShapeIds[0])
        : -1;
      
      const nextIndex = (currentIndex + 1) % state.shapes.length;
      actions.selectShapes([state.shapes[nextIndex].id]);
    }},
    { key: 'Tab', shiftKey: true, description: 'Select Previous Shape', action: () => {
      if (state.shapes.length === 0) return;
      
      const currentIndex = state.selectedShapeIds.length > 0 
        ? state.shapes.findIndex(s => s.id === state.selectedShapeIds[0])
        : 0;
      
      const prevIndex = currentIndex > 0 ? currentIndex - 1 : state.shapes.length - 1;
      actions.selectShapes([state.shapes[prevIndex].id]);
    }},

    // Visibility and Locking
    { key: 'h', description: 'Hide/Show Selected', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { visible: !shape.visible });
      });
    }},
    { key: 'l', description: 'Lock/Unlock Selected', action: () => {
      const selected = actions.getSelectedShapes();
      selected.forEach(shape => {
        actions.updateShape(shape.id, { locked: !shape.locked });
      });
    }},

    // Help
    { key: 'F1', description: 'Show Shortcuts Help', action: () => {
      // This would be handled by parent component
    }},
    { key: '?', shiftKey: true, description: 'Show Shortcuts Help', action: () => {
      // This would be handled by parent component
    }},
  ], [actions, onFrameNavigate, onPlayPause, onToolChange, state.canvasTransform, state.settings, state.shapes]);

  // Check if key combination matches shortcut
  const matchesShortcut = useCallback((event: KeyboardEvent, shortcut: KeyboardShortcut): boolean => {
    const key = event.key.toLowerCase();
    const shortcutKey = shortcut.key.toLowerCase();
    
    return (
      key === shortcutKey &&
      !!event.ctrlKey === !!shortcut.ctrlKey &&
      !!event.shiftKey === !!shortcut.shiftKey &&
      !!event.altKey === !!shortcut.altKey
    );
  }, []);

  // Handle keydown events
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (disabled) return;

    // Skip if typing in input fields
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      return;
    }

    // Track pressed keys for multi-key combinations
    pressedKeysRef.current.add(event.key.toLowerCase());

    // Find matching shortcut
    for (const shortcut of shortcuts) {
      if (matchesShortcut(event, shortcut)) {
        event.preventDefault();
        event.stopPropagation();
        shortcut.action();
        break;
      }
    }
  }, [disabled, shortcuts, matchesShortcut]);

  // Handle keyup events
  const handleKeyUp = useCallback((event: KeyboardEvent) => {
    pressedKeysRef.current.delete(event.key.toLowerCase());
  }, []);

  // Set up keyboard event listeners
  useEffect(() => {
    if (disabled) return;

    document.addEventListener('keydown', handleKeyDown, true);
    document.addEventListener('keyup', handleKeyUp, true);

    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
      document.removeEventListener('keyup', handleKeyUp, true);
    };
  }, [handleKeyDown, handleKeyUp, disabled]);

  // Format key combination for display
  const formatKeyCombo = useCallback((shortcut: KeyboardShortcut): string => {
    const parts: string[] = [];
    
    if (shortcut.ctrlKey) parts.push('Ctrl');
    if (shortcut.shiftKey) parts.push('Shift');
    if (shortcut.altKey) parts.push('Alt');
    
    // Format special keys
    let key = shortcut.key;
    switch (key) {
      case ' ': key = 'Space'; break;
      case 'Delete': key = 'Del'; break;
      case 'Backspace': key = 'Backspace'; break;
      case 'Escape': key = 'Esc'; break;
      case 'ArrowLeft': key = '←'; break;
      case 'ArrowRight': key = '→'; break;
      case 'ArrowUp': key = '↑'; break;
      case 'ArrowDown': key = '↓'; break;
      default: key = key.length === 1 ? key.toUpperCase() : key;
    }
    
    parts.push(key);
    return parts.join(' + ');
  }, []);

  // Group shortcuts by category
  const shortcutGroups = [
    {
      title: 'Tools',
      shortcuts: shortcuts.filter(s => ['v', 'r', 'p', 'b', 't'].includes(s.key) && !s.ctrlKey && !s.shiftKey)
    },
    {
      title: 'Edit',
      shortcuts: shortcuts.filter(s => ['z', 'y', 'c', 'v', 'x', 'a', 'd'].includes(s.key) && s.ctrlKey)
    },
    {
      title: 'Selection',
      shortcuts: shortcuts.filter(s => ['Delete', 'Backspace', 'Escape', 'Tab', 'h', 'l'].includes(s.key))
    },
    {
      title: 'Navigation',
      shortcuts: shortcuts.filter(s => ['ArrowLeft', 'ArrowRight', ' '].includes(s.key))
    },
    {
      title: 'View',
      shortcuts: shortcuts.filter(s => ['0', '=', '-', '1', '2', '5', 'g', 's'].includes(s.key) && !s.shiftKey)
    },
    {
      title: 'Labels',
      shortcuts: shortcuts.filter(s => ['1', '2', '3', '4', '5'].includes(s.key) && s.shiftKey)
    },
  ];

  // Help Dialog Component
  const HelpDialog = () => (
    <Dialog
      open={showHelpDialog}
      onClose={onHelpDialogClose || (() => {})}
      maxWidth="md"
      fullWidth
      PaperProps={{ sx: { maxHeight: '80vh' } }}
    >
      <DialogTitle>
        <Typography variant="h5">Keyboard Shortcuts</Typography>
        <Typography variant="body2" color="text.secondary">
          Speed up your annotation workflow with these keyboard shortcuts
        </Typography>
      </DialogTitle>
      
      <DialogContent dividers>
        {shortcutGroups.map((group) => (
          <Box key={group.title} sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom color="primary">
              {group.title}
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Shortcut</TableCell>
                    <TableCell>Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {group.shortcuts.map((shortcut, index) => (
                    <TableRow key={index}>
                      <TableCell>
                        <Chip
                          label={formatKeyCombo(shortcut)}
                          size="small"
                          variant="outlined"
                          sx={{ fontFamily: 'monospace' }}
                        />
                      </TableCell>
                      <TableCell>{shortcut.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        ))}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onHelpDialogClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );

  return <HelpDialog />;
};

export default KeyboardShortcuts;