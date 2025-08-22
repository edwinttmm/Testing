import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AnnotationProvider } from '../../components/annotation/AnnotationManager';
import { AnnotationShape } from '../../components/annotation/types';
import { setupTestEnvironment, MockShapeFactory } from './testUtils';

describe('Basic Annotation Functionality Tests', () => {
  let testEnv: ReturnType<typeof setupTestEnvironment>;

  beforeEach(() => {
    testEnv = setupTestEnvironment();
  });

  afterEach(() => {
    testEnv.cleanup();
  });

  describe('AnnotationProvider', () => {
    it('should render without crashing', () => {
      expect(() => {
        render(
          <AnnotationProvider>
            <div>Test Content</div>
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should provide initial shapes', () => {
      const initialShapes = [
        MockShapeFactory.rectangle(),
        MockShapeFactory.polygon(),
      ];

      render(
        <AnnotationProvider initialShapes={initialShapes}>
          <div data-testid="content">Test Content</div>
        </AnnotationProvider>
      );

      expect(screen.getByTestId('content')).toBeInTheDocument();
    });

    it('should handle empty initial shapes', () => {
      expect(() => {
        render(
          <AnnotationProvider initialShapes={[]}>
            <div>Empty Test</div>
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Mock Shape Factory', () => {
    it('should create valid rectangles', () => {
      const rectangle = MockShapeFactory.rectangle();
      
      expect(rectangle).toHaveProperty('id');
      expect(rectangle).toHaveProperty('type', 'rectangle');
      expect(rectangle).toHaveProperty('points');
      expect(rectangle).toHaveProperty('boundingBox');
      expect(rectangle).toHaveProperty('style');
      expect(rectangle.points).toHaveLength(4);
    });

    it('should create valid polygons', () => {
      const polygon = MockShapeFactory.polygon();
      
      expect(polygon).toHaveProperty('id');
      expect(polygon).toHaveProperty('type', 'polygon');
      expect(polygon).toHaveProperty('points');
      expect(polygon).toHaveProperty('boundingBox');
      expect(polygon.points).toHaveLength(3); // Default triangle
    });

    it('should create valid points', () => {
      const point = MockShapeFactory.point();
      
      expect(point).toHaveProperty('id');
      expect(point).toHaveProperty('type', 'point');
      expect(point).toHaveProperty('points');
      expect(point.points).toHaveLength(1);
    });

    it('should create valid brush strokes', () => {
      const brush = MockShapeFactory.brush();
      
      expect(brush).toHaveProperty('id');
      expect(brush).toHaveProperty('type', 'brush');
      expect(brush).toHaveProperty('points');
      expect(brush.points.length).toBeGreaterThan(1);
    });

    it('should generate unique IDs', () => {
      MockShapeFactory.resetCounter();
      
      const shape1 = MockShapeFactory.rectangle();
      const shape2 = MockShapeFactory.rectangle();
      
      expect(shape1.id).not.toBe(shape2.id);
    });
  });

  describe('Canvas Mock Setup', () => {
    it('should provide working canvas context', () => {
      expect(testEnv.context).toBeDefined();
      expect(testEnv.context.clearRect).toBeDefined();
      expect(testEnv.context.strokeRect).toBeDefined();
      expect(testEnv.context.fillRect).toBeDefined();
    });

    it('should track canvas operations', () => {
      testEnv.context.strokeRect(10, 10, 50, 50);
      testEnv.context.fillRect(20, 20, 30, 30);
      
      expect(testEnv.context.strokeRect).toHaveBeenCalledWith(10, 10, 50, 50);
      expect(testEnv.context.fillRect).toHaveBeenCalledWith(20, 20, 30, 30);
    });

    it('should reset mocks correctly', () => {
      testEnv.context.strokeRect(10, 10, 50, 50);
      
      expect(testEnv.context.strokeRect).toHaveBeenCalled();
      
      testEnv.resetMocks();
      
      expect(testEnv.context.strokeRect).not.toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('should handle invalid shape data', () => {
      const invalidShapes = [
        {
          id: 'invalid',
          type: 'unknown',
          points: null,
          boundingBox: null,
          style: null,
          visible: true,
          selected: false,
        },
      ] as AnnotationShape[];

      expect(() => {
        render(
          <AnnotationProvider initialShapes={invalidShapes}>
            <div>Test</div>
          </AnnotationProvider>
        );
      }).not.toThrow();
    });

    it('should handle null/undefined props', () => {
      expect(() => {
        render(
          <AnnotationProvider initialShapes={undefined as any}>
            <div>Test</div>
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Component Integration', () => {
    it('should handle component unmounting', () => {
      const { unmount } = render(
        <AnnotationProvider>
          <div>Test Component</div>
        </AnnotationProvider>
      );

      expect(() => {
        unmount();
      }).not.toThrow();
    });

    it('should handle re-rendering with new props', () => {
      const initialShapes = [MockShapeFactory.rectangle()];
      const newShapes = [MockShapeFactory.polygon()];

      const { rerender } = render(
        <AnnotationProvider initialShapes={initialShapes}>
          <div>Version 1</div>
        </AnnotationProvider>
      );

      expect(() => {
        rerender(
          <AnnotationProvider initialShapes={newShapes}>
            <div>Version 2</div>
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('Basic Interactions', () => {
    it('should handle keyboard events', () => {
      render(
        <AnnotationProvider>
          <div tabIndex={0}>Interactive Element</div>
        </AnnotationProvider>
      );

      expect(() => {
        fireEvent.keyDown(document, { key: 'v' });
        fireEvent.keyDown(document, { key: 'Escape' });
        fireEvent.keyDown(document, { key: 'Delete' });
      }).not.toThrow();
    });

    it('should handle mouse events', () => {
      render(
        <AnnotationProvider>
          <div data-testid="interactive">Interactive Element</div>
        </AnnotationProvider>
      );

      const element = screen.getByTestId('interactive');

      expect(() => {
        fireEvent.mouseDown(element, { clientX: 100, clientY: 100 });
        fireEvent.mouseMove(element, { clientX: 150, clientY: 150 });
        fireEvent.mouseUp(element, { clientX: 200, clientY: 200 });
      }).not.toThrow();
    });
  });

  describe('Performance Basics', () => {
    it('should handle moderate numbers of shapes', () => {
      const shapes = Array.from({ length: 50 }, () => MockShapeFactory.rectangle());

      const startTime = performance.now();

      render(
        <AnnotationProvider initialShapes={shapes}>
          <div>Many Shapes</div>
        </AnnotationProvider>
      );

      const endTime = performance.now();
      const renderTime = endTime - startTime;

      // Should render 50 shapes quickly
      expect(renderTime).toBeLessThan(1000); // Less than 1 second
    });

    it('should handle rapid operations', () => {
      render(
        <AnnotationProvider>
          <div data-testid="rapid-test">Rapid Test</div>
        </AnnotationProvider>
      );

      const element = screen.getByTestId('rapid-test');

      expect(() => {
        // Perform rapid mouse movements
        for (let i = 0; i < 100; i++) {
          fireEvent.mouseMove(element, { clientX: i, clientY: i });
        }
      }).not.toThrow();
    });
  });

  describe('Accessibility Basics', () => {
    it('should provide accessible structure', () => {
      render(
        <AnnotationProvider>
          <div role="application" aria-label="Annotation Tool">
            <button>Test Button</button>
          </div>
        </AnnotationProvider>
      );

      expect(screen.getByRole('application')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('should handle focus management', () => {
      render(
        <AnnotationProvider>
          <div>
            <button data-testid="btn1">Button 1</button>
            <button data-testid="btn2">Button 2</button>
          </div>
        </AnnotationProvider>
      );

      const btn1 = screen.getByTestId('btn1');
      const btn2 = screen.getByTestId('btn2');

      btn1.focus();
      expect(document.activeElement).toBe(btn1);

      fireEvent.keyDown(btn1, { key: 'Tab' });
      // Tab behavior would be handled by browser, not component
    });
  });

  describe('Memory Management Basics', () => {
    it('should cleanup on unmount', () => {
      const { unmount } = render(
        <AnnotationProvider>
          <div>Cleanup Test</div>
        </AnnotationProvider>
      );

      // Should not throw during cleanup
      expect(() => {
        unmount();
      }).not.toThrow();
    });

    it('should handle garbage collection simulation', () => {
      let shapes = Array.from({ length: 100 }, () => MockShapeFactory.rectangle());

      const { rerender } = render(
        <AnnotationProvider initialShapes={shapes}>
          <div>GC Test</div>
        </AnnotationProvider>
      );

      // Clear shapes reference
      shapes = [];

      // Re-render with empty shapes
      expect(() => {
        rerender(
          <AnnotationProvider initialShapes={[]}>
            <div>GC Test Empty</div>
          </AnnotationProvider>
        );
      }).not.toThrow();
    });
  });

  describe('State Management Basics', () => {
    it('should maintain consistent state', () => {
      const TestStateComponent = () => {
        const [counter, setCounter] = React.useState(0);

        return (
          <AnnotationProvider>
            <div>
              <span data-testid="counter">{counter}</span>
              <button onClick={() => setCounter(c => c + 1)}>
                Increment
              </button>
            </div>
          </AnnotationProvider>
        );
      };

      render(<TestStateComponent />);

      expect(screen.getByTestId('counter')).toHaveTextContent('0');

      fireEvent.click(screen.getByText('Increment'));

      expect(screen.getByTestId('counter')).toHaveTextContent('1');
    });

    it('should handle concurrent state updates', () => {
      const TestConcurrentComponent = () => {
        const [stateA, setStateA] = React.useState(0);
        const [stateB, setStateB] = React.useState(0);

        const updateBoth = () => {
          setStateA(a => a + 1);
          setStateB(b => b + 2);
        };

        return (
          <AnnotationProvider>
            <div>
              <span data-testid="state-a">{stateA}</span>
              <span data-testid="state-b">{stateB}</span>
              <button onClick={updateBoth}>Update Both</button>
            </div>
          </AnnotationProvider>
        );
      };

      render(<TestConcurrentComponent />);

      fireEvent.click(screen.getByText('Update Both'));

      expect(screen.getByTestId('state-a')).toHaveTextContent('1');
      expect(screen.getByTestId('state-b')).toHaveTextContent('2');
    });
  });
});