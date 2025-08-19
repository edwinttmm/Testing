/**
 * TypeScript Integration Tests - London School TDD
 * End-to-end validation of TypeScript error fixes across component interactions
 */

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { jest } from '@jest/globals';
import { mockFactory, mockCoordinator, integrationMocks } from '../mocks/typescript-error-mocks';
import { integrationTestFixtures } from '../fixtures/typescript-error-fixtures';
import { ComponentContract } from '../contracts/typescript-error-contracts';

// Mock external dependencies
jest.mock('react-router-dom', () => ({
  useNavigate: () => integrationMocks.createRouterMock().navigate,
  useLocation: () => integrationMocks.createRouterMock().location,
  useParams: () => integrationMocks.createRouterMock().params,
}));

describe('TypeScript Integration Tests - London School TDD', () => {
  let appContext: any;
  let routerMock: any;
  let errorHandlerMock: any;
  
  beforeEach(() => {
    // Arrange: Set up integration environment
    appContext = integrationMocks.createAppContextMock();
    routerMock = integrationMocks.createRouterMock();
    errorHandlerMock = integrationMocks.createGlobalErrorHandlerMock();
    
    mockCoordinator.resetAllMocks();
  });

  describe('Component Data Flow Integration', () => {
    it('should verify data flows correctly between parent and child components', async () => {
      // Arrange: Mock API service and React hooks
      const mockApiService = mockFactory.createServiceMock('api');
      const mockWebSocketService = mockFactory.createServiceMock('websocket');
      const mockUseState = mockFactory.createHookMock('useState');
      const mockUseEffect = mockFactory.createHookMock('useEffect');
      const mockUseCallback = mockFactory.createHookMock('useCallback');
      
      // Setup state management mocks
      const parentStates = {
        data: [[], jest.fn()],
        loading: [false, jest.fn()],
        error: [null, jest.fn()],
        filters: [{ search: '', category: 'all' }, jest.fn()]
      };
      
      mockUseState
        .mockReturnValueOnce(parentStates.data)
        .mockReturnValueOnce(parentStates.loading)
        .mockReturnValueOnce(parentStates.error)
        .mockReturnValueOnce(parentStates.filters);
      
      mockApiService.get.mockResolvedValue({
        data: [
          { id: 1, name: 'Item 1', category: 'tech' },
          { id: 2, name: 'Item 2', category: 'science' }
        ]
      });
      
      mockUseCallback.mockImplementation((callback: Function, deps: any[]) => callback);
      
      let effectCallback: Function;
      mockUseEffect.mockImplementation((callback: Function, deps: any[]) => {
        effectCallback = callback;
      });
      
      // Act: Create integrated parent-child component system
      interface DataItem {
        id: number;
        name: string;
        category: string;
      }
      
      interface ChildComponentProps {
        data: DataItem[];
        loading: boolean;
        error: Error | null;
        onRefresh: () => void;
        onFilter: (filters: any) => void;
      }
      
      const ChildComponent: React.FC<ChildComponentProps> = ({
        data,
        loading,
        error,
        onRefresh,
        onFilter
      }) => {
        if (loading) {
          return <div data-testid="child-loading">Loading...</div>;
        }
        
        if (error) {
          return <div data-testid="child-error">Error: {error.message}</div>;
        }
        
        return (
          <div data-testid="child-component">
            <button data-testid="refresh-btn" onClick={onRefresh}>
              Refresh
            </button>
            <select 
              data-testid="filter-select"
              onChange={(e) => onFilter({ category: e.target.value })}
            >
              <option value="all">All Categories</option>
              <option value="tech">Tech</option>
              <option value="science">Science</option>
            </select>
            <div data-testid="items-list">
              {data.map(item => (
                <div key={item.id} data-testid={`item-${item.id}`}>
                  {item.name} ({item.category})
                </div>
              ))}
            </div>
          </div>
        );
      };
      
      const ParentComponent: React.FC = () => {
        const [data, setData] = mockUseState<DataItem[]>([]);
        const [loading, setLoading] = mockUseState(false);
        const [error, setError] = mockUseState<Error | null>(null);
        const [filters, setFilters] = mockUseState({ search: '', category: 'all' });
        
        const fetchData = mockUseCallback(async () => {
          setLoading(true);
          setError(null);
          
          try {
            const response = await mockApiService.get('/data', { params: filters });
            setData(response.data);
          } catch (err) {
            setError(err as Error);
          } finally {
            setLoading(false);
          }
        }, [filters]);
        
        mockUseEffect(() => {
          fetchData();
        }, [fetchData]);
        
        const handleFilter = mockUseCallback((newFilters: any) => {
          setFilters(prev => ({ ...prev, ...newFilters }));
        }, []);
        
        return (
          <div data-testid="parent-component">
            <h1>Data Manager</h1>
            <ChildComponent
              data={data}
              loading={loading}
              error={error}
              onRefresh={fetchData}
              onFilter={handleFilter}
            />
          </div>
        );
      };
      
      render(<ParentComponent />);
      
      // Assert: Verify initial component integration
      expect(screen.getByTestId('parent-component')).toBeInTheDocument();
      expect(screen.getByTestId('child-component')).toBeInTheDocument();
      
      // Act: Trigger data fetching effect
      await act(async () => {
        if (effectCallback) {
          await effectCallback();
        }
      });
      
      // Assert: Verify API integration
      expect(mockApiService.get).toHaveBeenCalledWith('/data', { 
        params: { search: '', category: 'all' } 
      });
      
      // Act: Test child-to-parent communication
      fireEvent.change(screen.getByTestId('filter-select'), {
        target: { value: 'tech' }
      });
      
      // Assert: Verify parent state was updated via child callback
      expect(mockUseCallback).toHaveBeenCalledWith(expect.any(Function), []);
      
      // Act: Test refresh functionality
      fireEvent.click(screen.getByTestId('refresh-btn'));
      
      // Assert: Verify refresh triggered data fetch
      expect(mockApiService.get).toHaveBeenCalledTimes(2);
    });
  });

  describe('WebSocket Integration with Component State', () => {
    it('should verify WebSocket integration works with component state management', async () => {
      // Arrange: Mock WebSocket service and component state
      const mockWebSocketService = mockFactory.createServiceMock('websocket');
      const mockUseState = mockFactory.createHookMock('useState');
      const mockUseEffect = mockFactory.createHookMock('useEffect');
      
      const connectionStates = {
        connected: [false, jest.fn()],
        messages: [[], jest.fn()],
        status: ['disconnected', jest.fn()]
      };
      
      mockUseState
        .mockReturnValueOnce(connectionStates.connected)
        .mockReturnValueOnce(connectionStates.messages)
        .mockReturnValueOnce(connectionStates.status);
      
      // Mock WebSocket events
      const mockEventHandlers = new Map();
      mockWebSocketService.on.mockImplementation((event: string, handler: Function) => {
        mockEventHandlers.set(event, handler);
        return () => mockEventHandlers.delete(event);
      });
      
      mockWebSocketService.connect.mockResolvedValue(true);
      mockWebSocketService.emit.mockReturnValue(true);
      
      let effectCleanup: Function;
      mockUseEffect.mockImplementation((callback: Function, deps: any[]) => {
        const cleanup = callback();
        if (cleanup) {
          effectCleanup = cleanup;
        }
      });
      
      // Act: Create WebSocket-integrated component
      interface Message {
        id: string;
        text: string;
        timestamp: number;
      }
      
      const WebSocketComponent: React.FC = () => {
        const [connected, setConnected] = mockUseState(false);
        const [messages, setMessages] = mockUseState<Message[]>([]);
        const [status, setStatus] = mockUseState('disconnected');
        
        mockUseEffect(() => {
          const connect = async () => {
            setStatus('connecting');
            try {
              await mockWebSocketService.connect();
              setConnected(true);
              setStatus('connected');
            } catch (error) {
              setStatus('error');
            }
          };
          
          connect();
          
          // Setup message handler
          const messageHandler = (message: Message) => {
            setMessages(prev => [...prev, message]);
          };
          
          const unsubscribe = mockWebSocketService.on('message', messageHandler);
          
          return () => {
            unsubscribe();
            mockWebSocketService.disconnect();
            setConnected(false);
            setStatus('disconnected');
          };
        }, []);
        
        const sendMessage = (text: string) => {
          const message: Message = {
            id: Date.now().toString(),
            text,
            timestamp: Date.now()
          };
          
          mockWebSocketService.emit('message', message);
        };
        
        return (
          <div data-testid="websocket-component">
            <div data-testid="connection-status">{status}</div>
            <div data-testid="messages-container">
              {messages.map(msg => (
                <div key={msg.id} data-testid={`message-${msg.id}`}>
                  {msg.text}
                </div>
              ))}
            </div>
            <button 
              data-testid="send-btn"
              onClick={() => sendMessage('Test message')}
              disabled={!connected}
            >
              Send Message
            </button>
          </div>
        );
      };
      
      render(<WebSocketComponent />);
      
      // Assert: Verify WebSocket connection was initiated
      expect(mockWebSocketService.connect).toHaveBeenCalled();
      expect(mockWebSocketService.on).toHaveBeenCalledWith('message', expect.any(Function));
      
      // Act: Simulate incoming WebSocket message
      const messageHandler = mockEventHandlers.get('message');
      if (messageHandler) {
        await act(async () => {
          messageHandler({
            id: '1',
            text: 'Incoming message',
            timestamp: Date.now()
          });
        });
      }
      
      // Assert: Verify message was processed
      expect(connectionStates.messages[1]).toHaveBeenCalledWith(expect.any(Function));
      
      // Act: Test sending message
      fireEvent.click(screen.getByTestId('send-btn'));
      
      // Assert: Verify message was sent
      expect(mockWebSocketService.emit).toHaveBeenCalledWith('message', expect.objectContaining({
        text: 'Test message'
      }));
    });
  });

  describe('Error Handling Integration', () => {
    it('should verify error boundaries work across component hierarchy', async () => {
      // Arrange: Mock error boundary and error-prone components
      const mockErrorBoundary = mockFactory.createErrorBoundaryMock();
      const mockApiService = mockFactory.createServiceMock('api');
      const mockUseState = mockFactory.createHookMock('useState');
      
      // Setup error scenario
      mockApiService.get.mockRejectedValue(new Error('Network error'));
      
      const errorStates = {
        error: [null, jest.fn()],
        hasError: [false, jest.fn()]
      };
      
      mockUseState
        .mockReturnValueOnce(errorStates.error)
        .mockReturnValueOnce(errorStates.hasError);
      
      // Act: Create error-prone component hierarchy
      const ErrorProneChild: React.FC = () => {
        const [error, setError] = mockUseState<Error | null>(null);
        
        const triggerError = async () => {
          try {
            await mockApiService.get('/failing-endpoint');
          } catch (err) {
            setError(err as Error);
            throw err; // Re-throw to trigger error boundary
          }
        };
        
        if (error) {
          return <div data-testid="child-error">Child Error: {error.message}</div>;
        }
        
        return (
          <div data-testid="error-prone-child">
            <button data-testid="trigger-error-btn" onClick={triggerError}>
              Trigger Error
            </button>
          </div>
        );
      };
      
      const ErrorBoundaryParent: React.FC = () => {
        const [hasError, setHasError] = mockUseState(false);
        
        const handleError = (error: Error, errorInfo: any) => {
          mockErrorBoundary.componentDidCatch(error, errorInfo);
          setHasError(true);
          errorHandlerMock.handleError(error);
        };
        
        if (hasError) {
          return (
            <div data-testid="error-fallback">
              <p>Something went wrong</p>
              <button 
                data-testid="retry-btn"
                onClick={() => setHasError(false)}
              >
                Retry
              </button>
            </div>
          );
        }
        
        try {
          return (
            <div data-testid="error-boundary-parent">
              <ErrorProneChild />
            </div>
          );
        } catch (error) {
          handleError(error as Error, {});
          return null;
        }
      };
      
      render(<ErrorBoundaryParent />);
      
      // Assert: Verify normal rendering initially
      expect(screen.getByTestId('error-boundary-parent')).toBeInTheDocument();
      expect(screen.getByTestId('error-prone-child')).toBeInTheDocument();
      
      // Act: Trigger error
      await act(async () => {
        try {
          fireEvent.click(screen.getByTestId('trigger-error-btn'));
        } catch {
          // Expected to throw
        }
      });
      
      // Assert: Verify error was handled
      expect(mockApiService.get).toHaveBeenCalledWith('/failing-endpoint');
      expect(errorHandlerMock.handleError).toHaveBeenCalledWith(expect.any(Error));
    });
  });

  describe('Form Validation Integration', () => {
    it('should verify complex form validation with TypeScript types', async () => {
      // Arrange: Mock form validation and submission
      const mockApiService = mockFactory.createServiceMock('api');
      const mockUseState = mockFactory.createHookMock('useState');
      const mockUseCallback = mockFactory.createHookMock('useCallback');
      
      interface FormData {
        email: string;
        password: string;
        confirmPassword: string;
      }
      
      interface ValidationErrors {
        email?: string;
        password?: string;
        confirmPassword?: string;
      }
      
      const formStates = {
        formData: [{ email: '', password: '', confirmPassword: '' }, jest.fn()],
        errors: [{}, jest.fn()],
        isSubmitting: [false, jest.fn()],
        isValid: [false, jest.fn()]
      };
      
      mockUseState
        .mockReturnValueOnce(formStates.formData)
        .mockReturnValueOnce(formStates.errors)
        .mockReturnValueOnce(formStates.isSubmitting)
        .mockReturnValueOnce(formStates.isValid);
      
      mockApiService.post.mockResolvedValue({ data: { success: true } });
      mockUseCallback.mockImplementation((callback: Function) => callback);
      
      // Act: Create integrated form component
      const FormComponent: React.FC = () => {
        const [formData, setFormData] = mockUseState<FormData>({
          email: '',
          password: '',
          confirmPassword: ''
        });
        
        const [errors, setErrors] = mockUseState<ValidationErrors>({});
        const [isSubmitting, setIsSubmitting] = mockUseState(false);
        const [isValid, setIsValid] = mockUseState(false);
        
        const validateField = mockUseCallback((field: keyof FormData, value: string): string | null => {
          switch (field) {
            case 'email':
              const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
              return emailRegex.test(value) ? null : 'Invalid email format';
            
            case 'password':
              return value.length >= 8 ? null : 'Password must be at least 8 characters';
            
            case 'confirmPassword':
              return value === formData.password ? null : 'Passwords do not match';
            
            default:
              return null;
          }
        }, [formData.password]);
        
        const handleInputChange = mockUseCallback((field: keyof FormData, value: string) => {
          setFormData(prev => ({ ...prev, [field]: value }));
          
          const error = validateField(field, value);
          setErrors(prev => ({ ...prev, [field]: error }));
          
          // Update validation status
          const hasErrors = Object.values(errors).some(error => error !== null);
          const hasValues = Object.values({ ...formData, [field]: value }).every(val => val.length > 0);
          setIsValid(hasValues && !hasErrors);
        }, [formData, errors, validateField]);
        
        const handleSubmit = async (e: React.FormEvent) => {
          e.preventDefault();
          
          if (!isValid || isSubmitting) {
            return;
          }
          
          setIsSubmitting(true);
          
          try {
            await mockApiService.post('/register', formData);
            // Handle success
          } catch (error) {
            errorHandlerMock.handleError(error);
          } finally {
            setIsSubmitting(false);
          }
        };
        
        return (
          <form data-testid="validation-form" onSubmit={handleSubmit}>
            <input
              data-testid="email-input"
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              placeholder="Email"
            />
            {errors.email && (
              <div data-testid="email-error">{errors.email}</div>
            )}
            
            <input
              data-testid="password-input"
              type="password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              placeholder="Password"
            />
            {errors.password && (
              <div data-testid="password-error">{errors.password}</div>
            )}
            
            <input
              data-testid="confirm-password-input"
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
              placeholder="Confirm Password"
            />
            {errors.confirmPassword && (
              <div data-testid="confirm-password-error">{errors.confirmPassword}</div>
            )}
            
            <button 
              data-testid="submit-btn"
              type="submit" 
              disabled={!isValid || isSubmitting}
            >
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </button>
          </form>
        );
      };
      
      render(<FormComponent />);
      
      // Assert: Verify form renders correctly
      expect(screen.getByTestId('validation-form')).toBeInTheDocument();
      expect(screen.getByTestId('submit-btn')).toBeDisabled();
      
      // Act: Test form validation
      fireEvent.change(screen.getByTestId('email-input'), {
        target: { value: 'invalid-email' }
      });
      
      fireEvent.change(screen.getByTestId('password-input'), {
        target: { value: 'short' }
      });
      
      // Assert: Verify validation callbacks were triggered
      expect(mockUseCallback).toHaveBeenCalledWith(expect.any(Function), [expect.any(String)]);
      
      // Act: Test valid form submission
      fireEvent.change(screen.getByTestId('email-input'), {
        target: { value: 'valid@example.com' }
      });
      
      fireEvent.change(screen.getByTestId('password-input'), {
        target: { value: 'validpassword123' }
      });
      
      fireEvent.change(screen.getByTestId('confirm-password-input'), {
        target: { value: 'validpassword123' }
      });
      
      // Submit form
      fireEvent.submit(screen.getByTestId('validation-form'));
      
      // Assert: Verify form submission
      await waitFor(() => {
        expect(mockApiService.post).toHaveBeenCalledWith('/register', {
          email: 'valid@example.com',
          password: 'validpassword123',
          confirmPassword: 'validpassword123'
        });
      });
    });
  });

  afterEach(() => {
    mockCoordinator.resetAllMocks();
  });
});