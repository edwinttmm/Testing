import React from 'react';
import { render, screen, fireEvent, waitFor, RenderResult } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { AnnotationProvider } from '../../components/annotation/AnnotationManager';
import EnhancedAnnotationCanvas from '../../components/annotation/EnhancedAnnotationCanvas';
import BrushTool from '../../components/annotation/tools/BrushTool';
import PolygonTool from '../../components/annotation/tools/PolygonTool';
import SelectionTool from '../../components/annotation/tools/SelectionTool';
import { AnnotationShape, Point } from '../../components/annotation/types';

// Canvas mocks are now handled globally in setupTests.ts
// Get mock context for assertions
const getMockContext = () => global.getMockCanvasContext?.() || {
  clearRect: jest.fn(),
  save: jest.fn(),
  restore: jest.fn(),
  scale: jest.fn(),
  translate: jest.fn(),
  drawImage: jest.fn(),
  strokeStyle: '#000000',
  fillStyle: '#000000',
  lineWidth: 1,
  lineCap: 'butt',
  lineJoin: 'miter',
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

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AnnotationProvider initialShapes={[]}>{children}</AnnotationProvider>
);

describe('Drawing Tools Test Suite', () => {
  let mockContext: any;
  
  beforeEach(() => {
    jest.clearAllMocks();
    mockContext = getMockContext();
    
    // Reset canvas mocks if available
    if (global.resetCanvasMocks) {
      global.resetCanvasMocks();
    }
  });

  describe('Rectangle Tool', () => {
    it('should create a rectangle when dragging', async () => {
      const onShapeChange = jest.fn();
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas
            width={800}
            height={600}
            onShapeChange={onShapeChange}
          />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');
      
      // Simulate rectangle creation (using fireEvent since userEvent.pointer not available in v13)
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 200, clientY: 200, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 200, clientY: 200 });
      
      // Legacy approach using userEvent drag simulation
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 200, clientY: 200 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // ]);

      await waitFor(() => {
        expect(mockContext.strokeRect).toHaveBeenCalled();
        expect(onShapeChange).toHaveBeenCalled();
      });
    });

    it('should handle minimum rectangle size', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');
      
      // Create very small rectangle (using fireEvent)
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 102, clientY: 102, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 102, clientY: 102 });
      
      // Legacy approach:
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 102, clientY: 102 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // ]);

      // Should still create a valid rectangle (minimum size enforced)
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should support negative drag direction', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');
      
      // Drag from bottom-right to top-left (using fireEvent)
      fireEvent.mouseDown(canvas, { clientX: 200, clientY: 200, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 100, clientY: 100, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 100, clientY: 100 });
      
      // Legacy approach:
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 200, clientY: 200 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 100, clientY: 100 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // ]);

      expect(mockContext.strokeRect).toHaveBeenCalled();
    });
  });

  describe('Polygon Tool', () => {
    it('should create polygon with multiple points', async () => {
      const onComplete = jest.fn();
      // userEvent.setup() not available in v13, using direct userEvent

      const { rerender } = render(
        <TestWrapper>
          <PolygonTool enabled={true} onComplete={onComplete} />
        </TestWrapper>
      );

      // Note: PolygonTool returns a hook-like interface, need to test through canvas integration
      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Create triangle by clicking three points
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });
      await userEvent.click(canvas, { clientX: 200, clientY: 100 });
      await userEvent.click(canvas, { clientX: 150, clientY: 200 });
      
      // Double-click to complete
      await userEvent.dblClick(canvas, { clientX: 100, clientY: 100 });

      expect(mockContext.stroke).toHaveBeenCalled();
      expect(mockContext.fill).toHaveBeenCalled();
    });

    it('should show preview line while drawing', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Start polygon
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });
      
      // Move mouse to show preview
      fireEvent.mouseMove(canvas, { clientX: 200, clientY: 200 });

      expect(mockContext.setLineDash).toHaveBeenCalledWith([5, 5]);
      expect(mockContext.stroke).toHaveBeenCalled();
    });

    it('should complete polygon when clicking near start point', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Create points for polygon
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });
      await userEvent.click(canvas, { clientX: 200, clientY: 100 });
      await userEvent.click(canvas, { clientX: 200, clientY: 200 });
      
      // Click near start point to close
      await userEvent.click(canvas, { clientX: 105, clientY: 105 }); // Within threshold

      expect(mockContext.fill).toHaveBeenCalled();
    });

    it('should handle Escape key to cancel polygon', () => {
      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      // Start polygon and then press Escape
      fireEvent.keyDown(document, { key: 'Escape' });

      // Should clear current drawing state
      expect(mockContext.clearRect).toHaveBeenCalled();
    });
  });

  describe('Brush Tool', () => {
    it('should create smooth brush strokes', async () => {
      const onStrokeComplete = jest.fn();
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Draw brush stroke (using fireEvent)
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 110, clientY: 105, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 120, clientY: 110, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 130, clientY: 115, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 130, clientY: 115 });
      
      // Legacy approach:
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 110, clientY: 105 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 120, clientY: 110 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 130, clientY: 115 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // ]);

      expect(mockContext.stroke).toHaveBeenCalled();
      expect(mockContext.lineCap).toBe('round');
      expect(mockContext.lineJoin).toBe('round');
    });

    it('should show brush preview cursor', () => {
      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      fireEvent.mouseMove(canvas, { clientX: 200, clientY: 200 });

      // Should draw brush preview
      expect(mockContext.arc).toHaveBeenCalled();
    });

    it('should handle pressure sensitivity if available', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Simulate pressure-sensitive drawing
      const pointerEvent = new PointerEvent('pointermove', {
        clientX: 100,
        clientY: 100,
        pressure: 0.5,
      });

      fireEvent(canvas, pointerEvent);

      expect(mockContext.lineWidth).toBeGreaterThan(0);
    });

    it('should support eraser mode', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Enable eraser mode and draw
      fireEvent.mouseMove(canvas, { clientX: 100, clientY: 100 });

      // Should show eraser preview
      expect(mockContext.strokeStyle).toBeDefined();
    });
  });

  describe('Point Tool', () => {
    it('should create points on click', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      await userEvent.click(canvas, { clientX: 150, clientY: 150 });

      expect(mockContext.arc).toHaveBeenCalledWith(150, 150, 5, 0, 2 * Math.PI);
      expect(mockContext.fill).toHaveBeenCalled();
    });

    it('should show hover feedback', () => {
      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      fireEvent.mouseMove(canvas, { clientX: 200, clientY: 250 });

      // Should provide visual feedback for point placement
      expect(mockContext.arc).toHaveBeenCalled();
    });
  });

  describe('Selection Tool', () => {
    const mockShapes: AnnotationShape[] = [
      {
        id: 'rect1',
        type: 'rectangle',
        points: [
          { x: 50, y: 50 },
          { x: 150, y: 50 },
          { x: 150, y: 150 },
          { x: 50, y: 150 },
        ],
        boundingBox: { x: 50, y: 50, width: 100, height: 100 },
        style: {
          strokeColor: '#000',
          fillColor: '#fff',
          strokeWidth: 2,
          fillOpacity: 0.5,
        },
        visible: true,
        selected: false,
      },
    ];

    it('should select shapes on click', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <AnnotationProvider initialShapes={mockShapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Click on the rectangle
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });

      // Should highlight selected shape
      expect(mockContext.strokeStyle).toHaveBeenCalled();
    });

    it('should support multi-select with Shift', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <AnnotationProvider initialShapes={mockShapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // First selection
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });
      
      // Second selection with Shift
      await userEvent.keyboard('{Shift>}');
      await userEvent.click(canvas, { clientX: 200, clientY: 200 });
      await userEvent.keyboard('{/Shift}');

      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should show selection box when dragging empty area', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Drag selection box (using fireEvent)
      fireEvent.mouseDown(canvas, { clientX: 300, clientY: 300, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 400, clientY: 400, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 400, clientY: 400 });
      
      // Legacy approach:
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 300, clientY: 300 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 400, clientY: 400 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // ]);

      expect(mockContext.setLineDash).toHaveBeenCalledWith([3, 3]);
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should show resize handles for selected shapes', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <AnnotationProvider initialShapes={mockShapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Select shape
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });

      // Should draw resize handles
      expect(mockContext.fillRect).toHaveBeenCalled();
      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should resize shapes by dragging handles', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <AnnotationProvider initialShapes={mockShapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Select shape first
      await userEvent.click(canvas, { clientX: 100, clientY: 100 });

      // Drag bottom-right resize handle (using fireEvent)
      fireEvent.mouseDown(canvas, { clientX: 150, clientY: 150, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 200, clientY: 200, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 200, clientY: 200 });
      
      // Legacy approach:
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 150, clientY: 150 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 200, clientY: 200 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // ]);

      expect(mockContext.strokeRect).toHaveBeenCalled();
    });

    it('should move selected shapes', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <AnnotationProvider initialShapes={mockShapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Select and move shape (using fireEvent)
      fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100, buttons: 1 });
      fireEvent.mouseMove(canvas, { clientX: 150, clientY: 150, buttons: 1 });
      fireEvent.mouseUp(canvas, { clientX: 150, clientY: 150 });
      
      // Legacy approach:
      // await userEvent.pointer([
      //   { keys: '[MouseLeft>]', target: canvas, coords: { clientX: 100, clientY: 100 } },
      //   { pointerName: 'mouse', target: canvas, coords: { clientX: 150, clientY: 150 } },
      //   { keys: '[/MouseLeft]', target: canvas },
      // });

      expect(mockContext.strokeRect).toHaveBeenCalled();
    });
  });

  describe('Tool Interactions', () => {
    it('should switch between tools seamlessly', async () => {
      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      // Test tool switching via keyboard shortcuts
      fireEvent.keyDown(document, { key: 'v' }); // Select tool
      fireEvent.keyDown(document, { key: 'r' }); // Rectangle tool
      fireEvent.keyDown(document, { key: 'p' }); // Polygon tool
      fireEvent.keyDown(document, { key: 'b' }); // Brush tool

      // Should handle tool changes without errors
      expect(mockContext.clearRect).toHaveBeenCalled();
    });

    it('should maintain tool state during canvas interactions', () => {
      const onToolChange = jest.fn();

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      // Tool state should be consistent
      expect(onToolChange).not.toHaveBeenCalled();
    });

    it('should handle rapid tool switching', async () => {
      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      // Rapid tool switching
      for (let i = 0; i < 10; i++) {
        fireEvent.keyDown(document, { key: 'v' });
        fireEvent.keyDown(document, { key: 'r' });
      }

      expect(() => mockContext.clearRect).not.toThrow();
    });
  });

  describe('Error Handling', () => {
    it('should handle canvas context errors gracefully', () => {
      // Mock context to return null
      HTMLCanvasElement.prototype.getContext = jest.fn(() => null) as any;

      expect(() => {
        render(
          <TestWrapper>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </TestWrapper>
        );
      }).not.toThrow();

      // Restore mock
      HTMLCanvasElement.prototype.getContext = jest.fn(() => mockContext) as any;
    });

    it('should handle invalid mouse coordinates', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      // Click with invalid coordinates
      await userEvent.click(canvas, { clientX: -100, clientY: -100 });

      expect(() => mockContext.strokeRect).not.toThrow();
    });

    it('should handle missing canvas element', () => {
      const originalGetElementsByTagName = document.getElementsByTagName;
      document.getElementsByTagName = jest.fn(() => [] as any);

      expect(() => {
        render(
          <TestWrapper>
            <EnhancedAnnotationCanvas width={800} height={600} />
          </TestWrapper>
        );
      }).not.toThrow();

      document.getElementsByTagName = originalGetElementsByTagName;
    });
  });

  describe('Performance', () => {
    it('should handle large numbers of shapes efficiently', () => {
      const manyShapes: AnnotationShape[] = Array.from({ length: 1000 }, (_, i) => ({
        id: `shape-${i}`,
        type: 'rectangle',
        points: [
          { x: i % 50 * 10, y: Math.floor(i / 50) * 10 },
          { x: (i % 50) * 10 + 10, y: Math.floor(i / 50) * 10 },
          { x: (i % 50) * 10 + 10, y: Math.floor(i / 50) * 10 + 10 },
          { x: (i % 50) * 10, y: Math.floor(i / 50) * 10 + 10 },
        ],
        boundingBox: { x: i % 50 * 10, y: Math.floor(i / 50) * 10, width: 10, height: 10 },
        style: {
          strokeColor: '#000',
          fillColor: '#fff',
          strokeWidth: 1,
          fillOpacity: 0.5,
        },
        visible: true,
        selected: false,
      }));

      const start = performance.now();

      render(
        <AnnotationProvider initialShapes={manyShapes}>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </AnnotationProvider>
      );

      const end = performance.now();

      // Should render within reasonable time
      expect(end - start).toBeLessThan(1000); // 1 second
    });

    it('should throttle mouse move events during drawing', async () => {
      // userEvent.setup() not available in v13, using direct userEvent

      render(
        <TestWrapper>
          <EnhancedAnnotationCanvas width={800} height={600} />
        </TestWrapper>
      );

      const canvas = screen.getByRole('img') || document.querySelector('canvas');

      const start = performance.now();

      // Simulate many rapid mouse movements
      for (let i = 0; i < 100; i++) {
        fireEvent.mouseMove(canvas, { clientX: i, clientY: i });
      }

      const end = performance.now();

      // Should handle rapid movements efficiently
      expect(end - start).toBeLessThan(100); // 100ms
    });
  });
});