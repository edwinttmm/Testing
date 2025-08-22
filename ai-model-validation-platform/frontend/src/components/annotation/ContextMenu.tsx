import React, { useState, useCallback, useEffect } from 'react';
import {
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Typography,
  MenuList,
} from '@mui/material';
import {
  Edit,
  Delete,
  ContentCopy,
  ContentPaste,
  Visibility,
  VisibilityOff,
  Lock,
  LockOpen,
  ColorLens,
  SwapHoriz,
  ArrowUpward,
  ArrowDownward,
  CropFree,
  Timeline,
  Place,
  Brush,
  Label,
  Info,
} from '@mui/icons-material';
import { useAnnotation } from './AnnotationManager';
import { AnnotationShape, ContextMenuItem, Point } from './types';

interface ContextMenuProps {
  anchorPosition?: { top: number; left: number } | null;
  onClose: () => void;
  targetShape?: AnnotationShape | null;
  clickPoint?: Point;
  onShapeEdit?: (shape: AnnotationShape) => void;
  onLabelEdit?: (shape: AnnotationShape) => void;
  onPropertiesEdit?: (shape: AnnotationShape) => void;
}

const ContextMenu: React.FC<ContextMenuProps> = ({
  anchorPosition,
  onClose,
  targetShape,
  clickPoint,
  onShapeEdit,
  onLabelEdit,
  onPropertiesEdit,
}) => {
  const { state, actions } = useAnnotation();
  const [isOpen, setIsOpen] = useState(!!anchorPosition);

  const selectedShapes = actions.getSelectedShapes();
  const hasSelection = selectedShapes.length > 0;
  const hasClipboard = state.clipboard.length > 0;
  const multipleSelected = selectedShapes.length > 1;

  useEffect(() => {
    setIsOpen(!!anchorPosition);
  }, [anchorPosition]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    onClose();
  }, [onClose]);

  // Menu action handlers
  const handleEdit = useCallback(() => {
    if (targetShape && onShapeEdit) {
      onShapeEdit(targetShape);
    }
    handleClose();
  }, [targetShape, onShapeEdit, handleClose]);

  const handleDelete = useCallback(() => {
    if (targetShape) {
      actions.deleteShapes([targetShape.id]);
    } else if (hasSelection) {
      actions.deleteShapes(selectedShapes.map(s => s.id));
    }
    handleClose();
  }, [targetShape, hasSelection, selectedShapes, actions, handleClose]);

  const handleCopy = useCallback(() => {
    const shapesToCopy = targetShape ? [targetShape] : selectedShapes;
    if (shapesToCopy.length > 0) {
      actions.copyShapes(shapesToCopy);
    }
    handleClose();
  }, [targetShape, selectedShapes, actions, handleClose]);

  const handlePaste = useCallback(() => {
    if (hasClipboard && clickPoint) {
      actions.pasteShapes(clickPoint);
    } else if (hasClipboard) {
      actions.pasteShapes();
    }
    handleClose();
  }, [hasClipboard, clickPoint, actions, handleClose]);

  const handleDuplicate = useCallback(() => {
    const shapesToDuplicate = targetShape ? [targetShape] : selectedShapes;
    if (shapesToDuplicate.length > 0) {
      actions.copyShapes(shapesToDuplicate);
      actions.pasteShapes({ x: 10, y: 10 });
    }
    handleClose();
  }, [targetShape, selectedShapes, actions, handleClose]);

  const handleVisibilityToggle = useCallback(() => {
    const shapesToToggle = targetShape ? [targetShape] : selectedShapes;
    shapesToToggle.forEach(shape => {
      actions.updateShape(shape.id, { visible: !shape.visible });
    });
    handleClose();
  }, [targetShape, selectedShapes, actions, handleClose]);

  const handleLockToggle = useCallback(() => {
    const shapesToToggle = targetShape ? [targetShape] : selectedShapes;
    shapesToToggle.forEach(shape => {
      actions.updateShape(shape.id, { locked: !shape.locked });
    });
    handleClose();
  }, [targetShape, selectedShapes, actions, handleClose]);

  const handleBringToFront = useCallback(() => {
    // Implement z-order manipulation
    // This would require extending the annotation system to support z-index
    handleClose();
  }, [handleClose]);

  const handleSendToBack = useCallback(() => {
    // Implement z-order manipulation
    handleClose();
  }, [handleClose]);

  const handleConvertShape = useCallback((newType: 'rectangle' | 'polygon' | 'point' | 'brush') => {
    if (!targetShape) return;

    // Convert shape to different type
    let newShape: Partial<AnnotationShape> = {
      type: newType,
    };

    switch (newType) {
      case 'rectangle':
        if (targetShape.type !== 'rectangle') {
          // Convert to rectangle using bounding box
          const bbox = targetShape.boundingBox;
          newShape.points = [
            { x: bbox.x, y: bbox.y },
            { x: bbox.x + bbox.width, y: bbox.y },
            { x: bbox.x + bbox.width, y: bbox.y + bbox.height },
            { x: bbox.x, y: bbox.y + bbox.height },
          ];
        }
        break;
      case 'point':
        // Convert to point at center of bounding box
        const center = {
          x: targetShape.boundingBox.x + targetShape.boundingBox.width / 2,
          y: targetShape.boundingBox.y + targetShape.boundingBox.height / 2,
        };
        newShape.points = [center];
        newShape.boundingBox = {
          x: center.x - 5,
          y: center.y - 5,
          width: 10,
          height: 10,
        };
        break;
      case 'polygon':
        if (targetShape.type === 'rectangle') {
          // Keep existing points for rectangle
          newShape.points = targetShape.points;
        }
        break;
    }

    actions.updateShape(targetShape.id, newShape);
    handleClose();
  }, [targetShape, actions, handleClose]);

  const handleSetLabel = useCallback((label: string) => {
    const shapesToLabel = targetShape ? [targetShape] : selectedShapes;
    shapesToLabel.forEach(shape => {
      actions.updateShape(shape.id, { label });
    });
    handleClose();
  }, [targetShape, selectedShapes, actions, handleClose]);

  const handleEditLabel = useCallback(() => {
    if (targetShape && onLabelEdit) {
      onLabelEdit(targetShape);
    }
    handleClose();
  }, [targetShape, onLabelEdit, handleClose]);

  const handleShowProperties = useCallback(() => {
    if (targetShape && onPropertiesEdit) {
      onPropertiesEdit(targetShape);
    }
    handleClose();
  }, [targetShape, onPropertiesEdit, handleClose]);

  // Generate menu items based on context
  const getMenuItems = useCallback((): ContextMenuItem[] => {
    const items: ContextMenuItem[] = [];

    // Shape-specific actions
    if (targetShape) {
      items.push({
        id: 'edit',
        label: 'Edit Shape',
        icon: <Edit />,
        action: handleEdit,
        disabled: targetShape.locked,
      });

      items.push({
        id: 'edit-label',
        label: 'Edit Label',
        icon: <Label />,
        action: handleEditLabel,
      });

      items.push({
        id: 'properties',
        label: 'Properties',
        icon: <Info />,
        action: handleShowProperties,
      });

      items.push({ id: 'divider1', label: '', separator: true, action: () => {} });
    }

    // Edit actions
    if (hasSelection || targetShape) {
      items.push({
        id: 'copy',
        label: `Copy${multipleSelected ? ` (${selectedShapes.length})` : ''}`,
        icon: <ContentCopy />,
        shortcut: 'Ctrl+C',
        action: handleCopy,
      });

      items.push({
        id: 'duplicate',
        label: `Duplicate${multipleSelected ? ` (${selectedShapes.length})` : ''}`,
        icon: <SwapHoriz />,
        shortcut: 'Ctrl+D',
        action: handleDuplicate,
      });

      items.push({
        id: 'delete',
        label: `Delete${multipleSelected ? ` (${selectedShapes.length})` : ''}`,
        icon: <Delete />,
        shortcut: 'Del',
        action: handleDelete,
      });

      items.push({ id: 'divider2', label: '', separator: true, action: () => {} });
    }

    // Paste action
    if (hasClipboard) {
      items.push({
        id: 'paste',
        label: `Paste (${state.clipboard.length})`,
        icon: <ContentPaste />,
        shortcut: 'Ctrl+V',
        action: handlePaste,
      });
    }

    // Visibility and locking
    if (targetShape || hasSelection) {
      const shape = targetShape || selectedShapes[0];
      const allVisible = (targetShape ? [targetShape] : selectedShapes).every(s => s.visible !== false);
      const allLocked = (targetShape ? [targetShape] : selectedShapes).every(s => s.locked);

      items.push({
        id: 'visibility',
        label: allVisible ? 'Hide' : 'Show',
        icon: allVisible ? <VisibilityOff /> : <Visibility />,
        shortcut: 'H',
        action: handleVisibilityToggle,
      });

      items.push({
        id: 'lock',
        label: allLocked ? 'Unlock' : 'Lock',
        icon: allLocked ? <LockOpen /> : <Lock />,
        shortcut: 'L',
        action: handleLockToggle,
      });

      items.push({ id: 'divider3', label: '', separator: true, action: () => {} });
    }

    // Shape conversion (only for single shapes)
    if (targetShape && !multipleSelected) {
      items.push({
        id: 'convert-submenu',
        label: 'Convert To',
        icon: <SwapHoriz />,
        action: () => {}, // Handled by submenu
      });
    }

    // Z-order (only if multiple shapes exist)
    if (state.shapes.length > 1 && (targetShape || hasSelection)) {
      items.push({
        id: 'bring-front',
        label: 'Bring to Front',
        icon: <ArrowUpward />,
        action: handleBringToFront,
      });

      items.push({
        id: 'send-back',
        label: 'Send to Back',
        icon: <ArrowDownward />,
        action: handleSendToBack,
      });
    }

    // Label assignment submenu
    if (targetShape || hasSelection) {
      items.push({ id: 'divider4', label: '', separator: true, action: () => {} });
      
      const vruTypes = [
        { id: 'pedestrian', label: 'Pedestrian' },
        { id: 'cyclist', label: 'Cyclist' },
        { id: 'motorcyclist', label: 'Motorcyclist' },
        { id: 'wheelchair_user', label: 'Wheelchair User' },
        { id: 'scooter_rider', label: 'Scooter Rider' },
      ];

      vruTypes.forEach(type => {
        items.push({
          id: `label-${type.id}`,
          label: `Label as ${type.label}`,
          action: () => handleSetLabel(type.id),
        });
      });
    }

    return items;
  }, [
    targetShape, hasSelection, multipleSelected, selectedShapes, hasClipboard, state.clipboard.length, state.shapes.length,
    handleEdit, handleEditLabel, handleShowProperties, handleCopy, handleDuplicate, handleDelete, handlePaste,
    handleVisibilityToggle, handleLockToggle, handleBringToFront, handleSendToBack, handleSetLabel
  ]);

  const menuItems = getMenuItems();

  if (!isOpen || !anchorPosition) {
    return null;
  }

  return (
    <Menu
      open={isOpen}
      onClose={handleClose}
      anchorReference="anchorPosition"
      anchorPosition={anchorPosition}
      PaperProps={{
        style: {
          maxHeight: 400,
          minWidth: 200,
        },
      }}
    >
      <MenuList dense>
        {menuItems.map((item) => {
          if (item.separator) {
            return <Divider key={item.id} />;
          }

          return (
            <MenuItem
              key={item.id}
              onClick={item.action}
              disabled={item.disabled}
              sx={{
                minHeight: 36,
                '&:hover': !item.disabled ? {
                  backgroundColor: 'action.hover',
                } : undefined,
              }}
            >
              {item.icon && (
                <ListItemIcon sx={{ minWidth: 36 }}>
                  {item.icon}
                </ListItemIcon>
              )}
              
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{
                  variant: 'body2',
                  fontWeight: item.id.startsWith('label-') ? 500 : 400,
                }}
              />
              
              {item.shortcut && (
                <Typography variant="caption" color="text.secondary" sx={{ ml: 2 }}>
                  {item.shortcut}
                </Typography>
              )}
            </MenuItem>
          );
        })}

        {/* Shape conversion submenu */}
        {targetShape && !multipleSelected && (
          <>
            <Divider />
            <MenuItem disabled>
              <ListItemText
                primary="Convert To:"
                primaryTypographyProps={{
                  variant: 'caption',
                  color: 'text.secondary',
                  fontWeight: 600,
                }}
              />
            </MenuItem>
            
            {targetShape.type !== 'rectangle' && (
              <MenuItem onClick={() => handleConvertShape('rectangle')} sx={{ pl: 4 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <CropFree fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Rectangle" />
              </MenuItem>
            )}
            
            {targetShape.type !== 'polygon' && (
              <MenuItem onClick={() => handleConvertShape('polygon')} sx={{ pl: 4 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <Timeline fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Polygon" />
              </MenuItem>
            )}
            
            {targetShape.type !== 'point' && (
              <MenuItem onClick={() => handleConvertShape('point')} sx={{ pl: 4 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <Place fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Point" />
              </MenuItem>
            )}
          </>
        )}

        {menuItems.length === 0 && (
          <MenuItem disabled>
            <ListItemText
              primary="No actions available"
              primaryTypographyProps={{
                color: 'text.secondary',
                style: { fontStyle: 'italic' }
              }}
            />
          </MenuItem>
        )}
      </MenuList>
    </Menu>
  );
};

export default ContextMenu;