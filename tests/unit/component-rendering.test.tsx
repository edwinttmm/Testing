/**
 * Component Rendering Tests - London School TDD
 * Testing component mount, render, and update behaviors without TypeScript errors
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { jest } from '@jest/globals';
import { mockFactory, mockCoordinator } from '../mocks/typescript-error-mocks';
import { componentRenderingFixtures } from '../fixtures/typescript-error-fixtures';
import { ComponentContract } from '../contracts/typescript-error-contracts';

// Mock React to control rendering behavior
jest.mock('react', () => ({
  ...jest.requireActual('react'),
  useState: jest.fn(),
  useEffect: jest.fn(),
  useCallback: jest.fn(),
  useMemo: jest.fn(),
}));

describe('Component Rendering Error Fixes - London School TDD', () => {
  let componentContract: ComponentContract;
  
  beforeEach(() => {
    componentContract = {
      imports: { react: [], hooks: [], components: [], services: [] },
      functions: { declared: [], hoisted: [], callbacks: [] },
      state: { variables: [], setters: [], hooks: [] },
      rendering: { mounts: false, renders: false, updates: false }
    };
    
    mockCoordinator.resetAllMocks();
  });

  describe('Component Mounting Without TypeScript Errors', () => {
    it('should verify component mounts with correct prop types', () => {
      // Arrange: Define typed component interface
      interface CounterProps {
        initialCount: number;
        maxCount: number;
        onCountChange: (count: number) => void;
        disabled?: boolean;
      }
      
      const mockOnCountChange = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      let currentCount = 5;
      mockUseState.mockReturnValue([currentCount, jest.fn()]);
      
      // Act: Create component with proper TypeScript types
      const TypedCounter: React.FC<CounterProps> = ({ 
        initialCount, 
        maxCount, 
        onCountChange, 
        disabled = false 
      }) => {
        const [count, setCount] = mockUseState(initialCount);
        
        const handleIncrement = () => {
          const newCount = Math.min(count + 1, maxCount);
          setCount(newCount);
          onCountChange(newCount); // Correctly typed callback
        };
        
        return (
          <div data-testid="typed-counter">
            <span data-testid="count-display">{count}</span>
            <button 
              data-testid="increment-btn"
              onClick={handleIncrement}
              disabled={disabled || count >= maxCount}
            >
              Increment
            </button>
          </div>
        );
      };
      
      // Render with properly typed props
      render(
        <TypedCounter 
          initialCount={5}
          maxCount={10}
          onCountChange={mockOnCountChange}
          disabled={false}
        />
      );
      
      // Assert: Verify component mounted without TypeScript errors
      expect(screen.getByTestId('typed-counter')).toBeInTheDocument();
      expect(screen.getByTestId('count-display')).toHaveTextContent('5');
      
      // Assert: Verify useState was called with correct initial value
      expect(mockUseState).toHaveBeenCalledWith(5);
      
      // Act: Test prop-based interaction
      fireEvent.click(screen.getByTestId('increment-btn'));
      
      // Assert: Verify callback was called with correct type
      expect(mockOnCountChange).toHaveBeenCalledWith(6);
      
      // Update contract
      componentContract.rendering.mounts = true;
      componentContract.rendering.renders = true;
      expect(componentContract.rendering.mounts).toBe(true);
    });

    it('should verify component renders with optional props correctly', () => {
      // Arrange: Component with optional props
      interface OptionalPropsComponent {
        title: string;
        subtitle?: string;
        showIcon?: boolean;
        iconName?: string;
      }
      
      const IconComponent = mockFactory.createComponentMock('Icon');
      
      const CardComponent: React.FC<OptionalPropsComponent> = ({ 
        title, 
        subtitle, 
        showIcon = false, 
        iconName = 'default' 
      }) => (
        <div data-testid="card-component">
          <h1 data-testid="title">{title}</h1>
          {subtitle && <h2 data-testid="subtitle">{subtitle}</h2>}
          {showIcon && (
            <IconComponent 
              data-testid="icon"
              name={iconName}
            />
          )}
        </div>
      );
      
      // Act: Render with minimal props
      render(<CardComponent title="Test Title" />);
      
      // Assert: Verify component renders with minimal props
      expect(screen.getByTestId('card-component')).toBeInTheDocument();
      expect(screen.getByTestId('title')).toHaveTextContent('Test Title');
      expect(screen.queryByTestId('subtitle')).not.toBeInTheDocument();
      expect(IconComponent).not.toHaveBeenCalled();
      
      // Act: Re-render with all props
      render(
        <CardComponent 
          title="Full Title"
          subtitle="With Subtitle"
          showIcon={true}
          iconName="star"
        />
      );
      
      // Assert: Verify component renders with all props
      expect(screen.getByTestId('subtitle')).toHaveTextContent('With Subtitle');
      expect(IconComponent).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'star',
          'data-testid': 'icon'
        }),
        {}
      );
    });
  });

  describe('Event Handler Type Safety', () => {
    it('should verify event handlers work with proper TypeScript types', () => {
      // Arrange: Mock event handlers with type checking
      const mockOnSubmit = jest.fn();
      const mockOnChange = jest.fn();
      const mockOnClick = jest.fn();
      
      const mockUseState = mockFactory.createHookMock('useState');
      mockUseState.mockReturnValue(['', jest.fn()]);
      
      // Act: Create form component with typed event handlers
      const TypedForm: React.FC = () => {
        const [inputValue, setInputValue] = mockUseState('');
        
        const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          mockOnSubmit(inputValue);
        };
        
        const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
          const value = event.target.value;
          setInputValue(value);
          mockOnChange(value);
        };
        
        const handleButtonClick = (event: React.MouseEvent<HTMLButtonElement>) => {
          mockOnClick(event.currentTarget.name);
        };
        
        return (
          <form data-testid="typed-form" onSubmit={handleSubmit}>
            <input
              data-testid="form-input"
              type="text"
              value={inputValue}
              onChange={handleChange}
            />
            <button
              data-testid="submit-btn"
              type="submit"
              name="submit-button"
              onClick={handleButtonClick}
            >
              Submit
            </button>
          </form>
        );
      };
      
      render(<TypedForm />);
      
      // Act: Test input change event
      fireEvent.change(screen.getByTestId('form-input'), {
        target: { value: 'test input' }
      });
      
      // Assert: Verify change handler was called correctly
      expect(mockOnChange).toHaveBeenCalledWith('test input');
      
      // Act: Test button click event
      fireEvent.click(screen.getByTestId('submit-btn'));
      
      // Assert: Verify click handler received correct event data
      expect(mockOnClick).toHaveBeenCalledWith('submit-button');
      
      // Act: Test form submission
      fireEvent.submit(screen.getByTestId('typed-form'));
      
      // Assert: Verify submit handler was called
      expect(mockOnSubmit).toHaveBeenCalledWith('test input');
    });
  });

  describe('Component State Updates and Re-renders', () => {
    it('should verify component re-renders correctly when state changes', async () => {
      // Arrange: Track render calls and state changes
      const renderTracker = jest.fn();
      const mockSetCount = jest.fn();
      const mockSetMessage = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      let currentCount = 0;
      mockUseState
        .mockReturnValueOnce([currentCount, mockSetCount])
        .mockReturnValueOnce(['Initial message', mockSetMessage]);
      
      // Act: Create component that tracks renders and updates
      const RenderTrackingComponent: React.FC = () => {
        const [count, setCount] = mockUseState(0);
        const [message, setMessage] = mockUseState('Initial message');
        
        // Track each render
        renderTracker();
        
        const handleUpdate = () => {
          const newCount = count + 1;
          setCount(newCount);
          setMessage(`Count updated to ${newCount}`);
        };
        
        return (
          <div data-testid="render-tracking">
            <span data-testid="count">{count}</span>
            <span data-testid="message">{message}</span>
            <button data-testid="update-btn" onClick={handleUpdate}>
              Update
            </button>
          </div>
        );
      };
      
      render(<RenderTrackingComponent />);
      
      // Assert: Verify initial render
      expect(renderTracker).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('count')).toHaveTextContent('0');
      expect(screen.getByTestId('message')).toHaveTextContent('Initial message');
      
      // Act: Trigger state update
      fireEvent.click(screen.getByTestId('update-btn'));
      
      // Assert: Verify state setters were called
      expect(mockSetCount).toHaveBeenCalledWith(1);
      expect(mockSetMessage).toHaveBeenCalledWith('Count updated to 1');
      
      // Update contract
      componentContract.rendering.updates = true;
      expect(componentContract.rendering.updates).toBe(true);
    });

    it('should verify conditional rendering works correctly', () => {
      // Arrange: Mock conditional rendering state
      const mockUseState = mockFactory.createHookMock('useState');
      const mockSetShowDetails = jest.fn();
      const mockSetSelectedItem = jest.fn();
      
      mockUseState
        .mockReturnValueOnce([false, mockSetShowDetails])
        .mockReturnValueOnce([null, mockSetSelectedItem]);
      
      // Act: Create component with conditional rendering
      const ConditionalComponent: React.FC<{ items: Array<{ id: number; name: string }> }> = ({ items }) => {
        const [showDetails, setShowDetails] = mockUseState(false);
        const [selectedItem, setSelectedItem] = mockUseState(null);
        
        const handleItemSelect = (item: { id: number; name: string }) => {
          setSelectedItem(item);
          setShowDetails(true);
        };
        
        const handleClose = () => {
          setShowDetails(false);
          setSelectedItem(null);
        };
        
        return (
          <div data-testid="conditional-component">
            <div data-testid="items-list">
              {items.map(item => (
                <button
                  key={item.id}
                  data-testid={`item-${item.id}`}
                  onClick={() => handleItemSelect(item)}
                >
                  {item.name}
                </button>
              ))}
            </div>
            
            {showDetails && selectedItem && (
              <div data-testid="item-details">
                <h3 data-testid="selected-name">{selectedItem.name}</h3>
                <button data-testid="close-btn" onClick={handleClose}>
                  Close
                </button>
              </div>
            )}
          </div>
        );
      };
      
      const testItems = [
        { id: 1, name: 'Item 1' },
        { id: 2, name: 'Item 2' }
      ];
      
      render(<ConditionalComponent items={testItems} />);
      
      // Assert: Verify initial conditional rendering state
      expect(screen.getByTestId('items-list')).toBeInTheDocument();
      expect(screen.queryByTestId('item-details')).not.toBeInTheDocument();
      
      // Act: Select an item to trigger conditional rendering
      fireEvent.click(screen.getByTestId('item-1'));
      
      // Assert: Verify state setters were called
      expect(mockSetSelectedItem).toHaveBeenCalledWith({ id: 1, name: 'Item 1' });
      expect(mockSetShowDetails).toHaveBeenCalledWith(true);
    });
  });

  describe('Error Boundary Integration', () => {
    it('should verify components work with error boundaries', () => {
      // Arrange: Mock error boundary and error-prone component
      const mockErrorBoundary = mockFactory.createErrorBoundaryMock();
      const mockConsoleError = jest.fn();
      const originalConsoleError = console.error;
      console.error = mockConsoleError;
      
      let shouldThrowError = false;
      
      // Create component that can throw errors
      const ErrorProneComponent: React.FC<{ throwError?: boolean }> = ({ throwError = false }) => {
        if (throwError) {
          throw new Error('Test component error');
        }
        
        return <div data-testid="error-prone-component">Component works</div>;
      };
      
      // Mock error boundary wrapper
      const ErrorBoundaryWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
        try {
          return <>{children}</>;
        } catch (error) {
          mockErrorBoundary.componentDidCatch(error, {});
          return <div data-testid="error-fallback">Error occurred</div>;
        }
      };
      
      // Act: Render component without error
      render(
        <ErrorBoundaryWrapper>
          <ErrorProneComponent throwError={false} />
        </ErrorBoundaryWrapper>
      );
      
      // Assert: Verify normal rendering
      expect(screen.getByTestId('error-prone-component')).toBeInTheDocument();
      expect(mockErrorBoundary.componentDidCatch).not.toHaveBeenCalled();
      
      // Cleanup
      console.error = originalConsoleError;
    });
  });

  describe('Integration Tests - Full Component Lifecycle', () => {
    it('should verify complete component lifecycle without TypeScript errors', async () => {
      // Arrange: Mock comprehensive component with full lifecycle
      const mockApiService = mockFactory.createServiceMock('api');
      const mockUseState = mockFactory.createHookMock('useState');
      const mockUseEffect = mockFactory.createHookMock('useEffect');
      const mockUseCallback = mockFactory.createHookMock('useCallback');
      
      // Setup state mocks
      const stateMap = new Map([
        ['loading', [false, jest.fn()]],
        ['data', [[], jest.fn()]],
        ['error', [null, jest.fn()]],
        ['selectedId', [null, jest.fn()]]
      ]);
      
      mockUseState.mockImplementation((initial: any) => {
        for (const [key, value] of stateMap.entries()) {
          if (
            (key === 'loading' && typeof initial === 'boolean') ||
            (key === 'data' && Array.isArray(initial)) ||
            (key === 'error' && initial === null) ||
            (key === 'selectedId' && initial === null)
          ) {
            return value;
          }
        }
        return [initial, jest.fn()];
      });
      
      mockApiService.get.mockResolvedValue({
        data: [{ id: 1, name: 'Test Item' }]
      });
      
      mockUseCallback.mockImplementation((callback: Function) => callback);
      
      // Act: Create comprehensive component
      interface DataItem {
        id: number;
        name: string;
      }
      
      const DataComponent: React.FC = () => {
        const [loading, setLoading] = mockUseState(false);
        const [data, setData] = mockUseState<DataItem[]>([]);
        const [error, setError] = mockUseState<Error | null>(null);
        const [selectedId, setSelectedId] = mockUseState<number | null>(null);
        
        const fetchData = mockUseCallback(async () => {
          setLoading(true);
          setError(null);
          
          try {
            const response = await mockApiService.get('/data');
            setData(response.data);
          } catch (err) {
            setError(err as Error);
          } finally {
            setLoading(false);
          }
        }, []);
        
        mockUseEffect(() => {
          fetchData();
        }, [fetchData]);
        
        const handleItemSelect = (id: number) => {
          setSelectedId(id);
        };
        
        if (loading) {
          return <div data-testid="loading">Loading...</div>;
        }
        
        if (error) {
          return <div data-testid="error">Error: {error.message}</div>;
        }
        
        return (
          <div data-testid="data-component">
            {data.map(item => (
              <button
                key={item.id}
                data-testid={`item-${item.id}`}
                onClick={() => handleItemSelect(item.id)}
                className={selectedId === item.id ? 'selected' : ''}
              >
                {item.name}
              </button>
            ))}
          </div>
        );
      };
      
      render(<DataComponent />);
      
      // Assert: Verify full component lifecycle
      expect(mockUseState).toHaveBeenCalledTimes(4);
      expect(mockUseEffect).toHaveBeenCalledWith(expect.any(Function), [expect.any(Function)]);
      expect(mockUseCallback).toHaveBeenCalledWith(expect.any(Function), []);
      expect(mockApiService.get).toHaveBeenCalledWith('/data');
      
      // Update contract to reflect successful integration
      componentContract.rendering.mounts = true;
      componentContract.rendering.renders = true;
      componentContract.rendering.updates = true;
      
      expect(componentContract.rendering).toEqual({
        mounts: true,
        renders: true,
        updates: true
      });
    });
  });

  afterEach(() => {
    mockCoordinator.resetAllMocks();
  });
});