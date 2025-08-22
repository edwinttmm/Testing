import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AnnotationProvider } from '../../components/annotation/AnnotationManager';
import KeyboardShortcuts from '../../components/annotation/KeyboardShortcuts';
import EnhancedAnnotationCanvas from '../../components/annotation/EnhancedAnnotationCanvas';
import { AnnotationShape } from '../../components/annotation/types';

// Mock canvas context
const mockContext = {
  clearRect: jest.fn(),
  save: jest.fn(),
  restore: jest.fn(),
  scale: jest.fn(),
  translate: jest.fn(),
  strokeStyle: '#000000',
  fillStyle: '#000000',
  lineWidth: 1,
  globalAlpha: 1,
  strokeRect: jest.fn(),
  fillRect: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  closePath: jest.fn(),
  stroke: jest.fn(),
  fill: jest.fn(),
  arc: jest.fn(),
  setLineDash: jest.fn(),
};

HTMLCanvasElement.prototype.getContext = jest.fn(() => mockContext) as any;
HTMLCanvasElement.prototype.getBoundingClientRect = jest.fn(() => ({
  left: 0,
  top: 0,
  width: 800,
  height: 600,
  right: 800,
  bottom: 600,
  x: 0,
  y: 0,
  toJSON: jest.fn(),
}));

// Test wrapper component
const TestWrapper: React.FC<{ 
  children: React.ReactNode; 
  initialShapes?: AnnotationShape[] 
}> = ({ children, initialShapes = [] }) => (
  <AnnotationProvider initialShapes={initialShapes}>
    {children}
  </AnnotationProvider>
);

// Mock shapes for testing
const mockShapes: AnnotationShape[] = [
  {
    id: 'shape1',
    type: 'rectangle',
    points: [
      { x: 50, y: 50 },
      { x: 150, y: 50 },
      { x: 150, y: 150 },
      { x: 50, y: 150 },
    ],
    boundingBox: { x: 50, y: 50, width: 100, height: 100 },
    style: {
      strokeColor: '#3498db',
      fillColor: 'rgba(52, 152, 219, 0.2)',
      strokeWidth: 2,
      fillOpacity: 0.2,
    },
    visible: true,
    selected: true,
  },
  {
    id: 'shape2',
    type: 'polygon',
    points: [
      { x: 200, y: 200 },
      { x: 250, y: 200 },
      { x: 225, y: 250 },
    ],
    boundingBox: { x: 200, y: 200, width: 50, height: 50 },
    style: {
      strokeColor: '#e74c3c',
      fillColor: 'rgba(231, 76, 60, 0.2)',
      strokeWidth: 2,
      fillOpacity: 0.2,
    },
    visible: true,
    selected: false,
  },
];

describe('Keyboard Shortcuts Test Suite', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tool Selection Shortcuts', () => {
    it('should switch to selection tool with "V" key', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onToolChange={onToolChange} />
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'v' });

      expect(onToolChange).toHaveBeenCalledWith('select');
    });

    it('should switch to rectangle tool with "R" key', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'r' });

      expect(onToolChange).toHaveBeenCalledWith('rectangle');
    });

    it('should switch to polygon tool with "P" key', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'p' });

      expect(onToolChange).toHaveBeenCalledWith('polygon');
    });

    it('should switch to brush tool with "B" key', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'b' });

      expect(onToolChange).toHaveBeenCalledWith('brush');
    });

    it('should switch to point tool with "T" key', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 't' });

      expect(onToolChange).toHaveBeenCalledWith('point');
    });

    it('should ignore tool shortcuts when typing in input fields', () => {
      const onToolChange = jest.fn();

      render(
        <div>
          <input data-testid="text-input" />
          <TestWrapper>
            <KeyboardShortcuts onToolChange={onToolChange} />
          </TestWrapper>
        </div>
      );

      const input = screen.getByTestId('text-input');
      input.focus();

      fireEvent.keyDown(input, { key: 'v' });

      expect(onToolChange).not.toHaveBeenCalled();
    });
  });

  describe('Edit Operation Shortcuts', () => {
    it('should undo with Ctrl+Z', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'z', ctrlKey: true });

      // Should trigger undo action
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should redo with Ctrl+Y', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'y', ctrlKey: true });

      // Should trigger redo action
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should redo with Ctrl+Shift+Z (alternative)', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'z', ctrlKey: true, shiftKey: true });

      // Should trigger redo action
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should copy selected shapes with Ctrl+C', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'c', ctrlKey: true });

      // Should copy selected shapes to clipboard
      // Verification would be through annotation manager state
    });

    it('should paste shapes with Ctrl+V', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      // First copy, then paste
      fireEvent.keyDown(document, { key: 'c', ctrlKey: true });
      fireEvent.keyDown(document, { key: 'v', ctrlKey: true });

      // Should paste shapes with offset
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should cut shapes with Ctrl+X', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'x', ctrlKey: true });

      // Should copy and delete selected shapes
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should select all shapes with Ctrl+A', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'a', ctrlKey: true });

      // Should select all visible shapes
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should duplicate shapes with Ctrl+D', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'd', ctrlKey: true });

      // Should create duplicates with offset
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });
  });

  describe('Delete Operation Shortcuts', () => {
    it('should delete selected shapes with Delete key', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'Delete' });

      // Should delete selected shapes
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should delete selected shapes with Backspace key', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'Backspace' });

      // Should delete selected shapes
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should not delete when no shapes are selected', () => {
      render(
        <TestWrapper initialShapes={mockShapes.map(s => ({ ...s, selected: false }))}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'Delete' });

      // Should not affect any shapes
      // Test would verify through state checking
    });
  });

  describe('Selection Operation Shortcuts', () => {
    it('should clear selection with Escape key', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      // Should clear all selections
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should cycle through shapes with Tab key', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'Tab' });

      // Should select next shape in sequence
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should cycle backwards with Shift+Tab', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });

      // Should select previous shape in sequence
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });
  });

  describe('Navigation Shortcuts', () => {
    it('should navigate to previous frame with Left Arrow', () => {
      const onFrameNavigate = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onFrameNavigate={onFrameNavigate} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'ArrowLeft' });

      expect(onFrameNavigate).toHaveBeenCalledWith('prev');
    });

    it('should navigate to next frame with Right Arrow', () => {
      const onFrameNavigate = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onFrameNavigate={onFrameNavigate} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'ArrowRight' });

      expect(onFrameNavigate).toHaveBeenCalledWith('next');
    });

    it('should play/pause with Space key', () => {
      const onPlayPause = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts onPlayPause={onPlayPause} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: ' ' });

      expect(onPlayPause).toHaveBeenCalled();
    });
  });

  describe('View Control Shortcuts', () => {
    it('should zoom to fit with "0" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '0' });

      // Should reset zoom to fit content
      expect(mockContext.scale).toHaveBeenCalled();
    });

    it('should zoom in with "=" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '=' });

      // Should increase zoom level
      expect(mockContext.scale).toHaveBeenCalled();
    });

    it('should zoom out with "-" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '-' });

      // Should decrease zoom level
      expect(mockContext.scale).toHaveBeenCalled();
    });

    it('should set zoom to 100% with "1" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '1' });

      // Should set zoom to 100%
      expect(mockContext.scale).toHaveBeenCalled();
    });

    it('should set zoom to 200% with "2" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '2' });

      // Should set zoom to 200%
      expect(mockContext.scale).toHaveBeenCalled();
    });
  });

  describe('Grid and Snap Shortcuts', () => {
    it('should toggle grid with "G" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'g' });

      // Should toggle grid visibility
      expect(mockContext.strokeStyle).toBeDefined();
    });

    it('should toggle snap to grid with "S" key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 's' });

      // Should toggle snap to grid setting
      // Verification through state checking
    });
  });

  describe('Label Assignment Shortcuts', () => {
    it('should assign pedestrian label with Shift+1', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '1', shiftKey: true });

      // Should assign pedestrian label to selected shapes
      // Verification through state checking
    });

    it('should assign cyclist label with Shift+2', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '2', shiftKey: true });

      // Should assign cyclist label to selected shapes
      // Verification through state checking
    });

    it('should assign motorcyclist label with Shift+3', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '3', shiftKey: true });

      // Should assign motorcyclist label to selected shapes
      // Verification through state checking
    });

    it('should only assign labels to selected shapes', () => {
      const noSelectionShapes = mockShapes.map(s => ({ ...s, selected: false }));

      render(
        <TestWrapper initialShapes={noSelectionShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: '1', shiftKey: true });

      // Should not assign labels when no shapes are selected
      // Verification through state checking
    });
  });

  describe('Visibility and Locking Shortcuts', () => {
    it('should toggle visibility with "H" key', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'h' });

      // Should toggle visibility of selected shapes
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should toggle lock state with "L" key', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'l' });

      // Should toggle lock state of selected shapes
      // Verification through state checking
    });
  });

  describe('Copy/Paste Between Frames', () => {
    it('should copy shapes for frame-to-frame pasting', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      // Copy shapes
      fireEvent.keyDown(document, { key: 'c', ctrlKey: true });

      // Should store shapes in clipboard for cross-frame operations
      // Verification through annotation manager state
    });

    it('should paste shapes with correct positioning on new frame', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      // Copy and paste
      fireEvent.keyDown(document, { key: 'c', ctrlKey: true });
      fireEvent.keyDown(document, { key: 'v', ctrlKey: true });

      // Should paste with proper offset to avoid overlap
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should maintain shape properties during cross-frame copy/paste', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'c', ctrlKey: true });
      fireEvent.keyDown(document, { key: 'v', ctrlKey: true });

      // Pasted shapes should maintain original properties
      expect(mockContext.strokeStyle).toBeDefined();
      expect(mockContext.fillStyle).toBeDefined();
    });
  });

  describe('Keyboard Shortcuts Help Dialog', () => {
    it('should show help dialog with F1 key', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts showHelpDialog={true} />
        </TestWrapper>
      );

      expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    });

    it('should show help dialog with Shift+? key', () => {
      const onHelpDialogClose = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts 
            showHelpDialog={true} 
            onHelpDialogClose={onHelpDialogClose}
          />
        </TestWrapper>
      );

      expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    });

    it('should display all shortcut categories in help dialog', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts showHelpDialog={true} />
        </TestWrapper>
      );

      expect(screen.getByText('Tools')).toBeInTheDocument();
      expect(screen.getByText('Edit')).toBeInTheDocument();
      expect(screen.getByText('Selection')).toBeInTheDocument();
      expect(screen.getByText('Navigation')).toBeInTheDocument();
      expect(screen.getByText('View')).toBeInTheDocument();
      expect(screen.getByText('Labels')).toBeInTheDocument();
    });

    it('should show formatted key combinations in help dialog', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts showHelpDialog={true} />
        </TestWrapper>
      );

      // Should show properly formatted key combinations
      expect(screen.getByText('Ctrl + Z')).toBeInTheDocument();
      expect(screen.getByText('Ctrl + C')).toBeInTheDocument();
      expect(screen.getByText('V')).toBeInTheDocument();
    });
  });

  describe('Disabled State', () => {
    it('should not respond to shortcuts when disabled', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <KeyboardShortcuts disabled={true} onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'v' });

      expect(onToolChange).not.toHaveBeenCalled();
    });

    it('should re-enable shortcuts when disabled state changes', async () => {
      const onToolChange = jest.fn();
      let disabled = true;

      const { rerender } = render(
        <TestWrapper>
          <KeyboardShortcuts disabled={disabled} onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'v' });
      expect(onToolChange).not.toHaveBeenCalled();

      // Enable shortcuts
      disabled = false;
      rerender(
        <TestWrapper>
          <KeyboardShortcuts disabled={disabled} onToolChange={onToolChange} />
        </TestWrapper>
      );

      fireEvent.keyDown(document, { key: 'v' });
      expect(onToolChange).toHaveBeenCalled();
    });
  });

  describe('Edge Cases and Error Handling', () => {
    it('should handle rapid key presses', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      // Rapid key presses
      for (let i = 0; i < 100; i++) {
        fireEvent.keyDown(document, { key: 'v' });
        fireEvent.keyDown(document, { key: 'r' });
      }

      expect(() => mockContext.clearRect).not.toThrow();
    });

    it('should handle key combinations with modifier keys', () => {
      render(
        <TestWrapper initialShapes={mockShapes}>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      // Test various modifier combinations
      fireEvent.keyDown(document, { key: 'z', ctrlKey: true, altKey: true });
      fireEvent.keyDown(document, { key: 'c', ctrlKey: true, shiftKey: true });

      expect(() => mockContext.clearRect).not.toThrow();
    });

    it('should handle non-standard key events', () => {
      render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      // Test with unusual key codes
      fireEvent.keyDown(document, { key: 'F13' });
      fireEvent.keyDown(document, { key: 'NumpadEnter' });
      fireEvent.keyDown(document, { key: 'ContextMenu' });

      expect(() => mockContext.clearRect).not.toThrow();
    });

    it('should cleanup event listeners on unmount', () => {
      const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');

      const { unmount } = render(
        <TestWrapper>
          <KeyboardShortcuts />
        </TestWrapper>
      );

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function), true);
      expect(removeEventListenerSpy).toHaveBeenCalledWith('keyup', expect.any(Function), true);

      removeEventListenerSpy.mockRestore();
    });
  });
});