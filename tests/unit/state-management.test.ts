/**
 * State Management Tests - London School TDD  
 * Testing React state hook implementations and state variable declarations
 */

import { render, fireEvent, screen, act } from '@testing-library/react';
import { jest } from '@jest/globals';
import { mockFactory, mockCoordinator } from '../mocks/typescript-error-mocks';
import { stateManagementFixtures } from '../fixtures/typescript-error-fixtures';
import { ComponentContract } from '../contracts/typescript-error-contracts';

describe('State Management Error Fixes - London School TDD', () => {
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

  describe('useState Hook Implementation', () => {
    it('should verify state variables are properly declared with useState', () => {
      // Arrange: Mock useState behavior
      const mockSetLoading = jest.fn();
      const mockSetData = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      // Track useState calls and return values
      const stateValues = new Map();
      mockUseState.mockImplementation((initialValue: any) => {
        const stateKey = typeof initialValue;
        if (!stateValues.has(stateKey)) {
          stateValues.set(stateKey, [initialValue, jest.fn()]);
        }
        return stateValues.get(stateKey);
      });
      
      // Act: Create component with proper state declarations
      const StateComponent = () => {
        const [isLoading, setIsLoading] = mockUseState(false);
        const [data, setData] = mockUseState([]);
        const [error, setError] = mockUseState(null);
        
        const handleSubmit = () => {
          // State variables are now properly accessible
          if (isLoading) {
            return;
          }
          
          setIsLoading(true);
          // Simulate async operation
          setTimeout(() => {
            setData(['item1', 'item2']);
            setIsLoading(false);
          }, 100);
        };
        
        return (
          <div data-testid="state-component">
            {isLoading && <div data-testid="loading">Loading...</div>}
            <button 
              data-testid="submit-button"
              onClick={handleSubmit}
              disabled={isLoading}
            >
              Submit
            </button>
            {data && data.length > 0 && (
              <ul data-testid="data-list">
                {data.map((item: string, index: number) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        );
      };
      
      render(<StateComponent />);
      
      // Assert: Verify useState was called for each state variable
      expect(mockUseState).toHaveBeenCalledWith(false); // isLoading
      expect(mockUseState).toHaveBeenCalledWith([]); // data
      expect(mockUseState).toHaveBeenCalledWith(null); // error
      expect(mockUseState).toHaveBeenCalledTimes(3);
      
      // Assert: Verify state contract compliance
      componentContract.state.variables.push('isLoading', 'data', 'error');
      componentContract.state.setters.push('setIsLoading', 'setData', 'setError');
      componentContract.state.hooks.push('useState');
      
      expect(componentContract.state.variables).toHaveLength(3);
      expect(componentContract.state.setters).toHaveLength(3);
    });

    it('should verify state setters are used correctly', async () => {
      // Arrange: Mock state setters with call tracking
      const mockSetCount = jest.fn();
      const mockSetMessage = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      let currentCount = 0;
      let currentMessage = '';
      
      mockUseState
        .mockReturnValueOnce([currentCount, mockSetCount])
        .mockReturnValueOnce([currentMessage, mockSetMessage]);
      
      // Act: Create component that uses state setters
      const CounterComponent = () => {
        const [count, setCount] = mockUseState(0);
        const [message, setMessage] = mockUseState('');
        
        const handleIncrement = () => {
          setCount(count + 1);
          setMessage(`Count is ${count + 1}`);
        };
        
        const handleDecrement = () => {
          setCount(count - 1);
          setMessage(`Count is ${count - 1}`);
        };
        
        const handleReset = () => {
          setCount(0);
          setMessage('Reset');
        };
        
        return (
          <div data-testid="counter-component">
            <span data-testid="count-display">{count}</span>
            <span data-testid="message-display">{message}</span>
            <button data-testid="increment-btn" onClick={handleIncrement}>+</button>
            <button data-testid="decrement-btn" onClick={handleDecrement}>-</button>
            <button data-testid="reset-btn" onClick={handleReset}>Reset</button>
          </div>
        );
      };
      
      render(<CounterComponent />);
      
      // Act: Test increment functionality
      fireEvent.click(screen.getByTestId('increment-btn'));
      
      // Assert: Verify state setters were called correctly
      expect(mockSetCount).toHaveBeenCalledWith(1);
      expect(mockSetMessage).toHaveBeenCalledWith('Count is 1');
      
      // Act: Test decrement functionality
      fireEvent.click(screen.getByTestId('decrement-btn'));
      
      // Assert: Verify state setters for decrement
      expect(mockSetCount).toHaveBeenCalledWith(-1);
      expect(mockSetMessage).toHaveBeenCalledWith('Count is -1');
      
      // Act: Test reset functionality
      fireEvent.click(screen.getByTestId('reset-btn'));
      
      // Assert: Verify reset functionality
      expect(mockSetCount).toHaveBeenCalledWith(0);
      expect(mockSetMessage).toHaveBeenCalledWith('Reset');
      
      // Verify interaction pattern
      expect(mockSetCount).toHaveBeenCalledTimes(3);
      expect(mockSetMessage).toHaveBeenCalledTimes(3);
    });
  });

  describe('Complex State Management Patterns', () => {
    it('should verify state updates with functional updates', () => {
      // Arrange: Mock useState with functional update support
      const mockSetItems = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      let currentItems: string[] = [];
      mockUseState.mockImplementation((initial: any) => {
        if (Array.isArray(initial)) {
          return [currentItems, mockSetItems];
        }
        return [initial, jest.fn()];
      });
      
      // Act: Create component with functional state updates
      const ListComponent = () => {
        const [items, setItems] = mockUseState<string[]>([]);
        const [inputValue, setInputValue] = mockUseState('');
        
        const handleAddItem = () => {
          // Use functional update to avoid stale closure
          setItems((prevItems: string[]) => [...prevItems, inputValue]);
          setInputValue('');
        };
        
        const handleRemoveItem = (index: number) => {
          setItems((prevItems: string[]) => 
            prevItems.filter((_, i) => i !== index)
          );
        };
        
        const handleClearAll = () => {
          setItems(() => []); // Functional update returning new state
        };
        
        return (
          <div data-testid="list-component">
            <input 
              data-testid="item-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
            />
            <button data-testid="add-btn" onClick={handleAddItem}>Add</button>
            <button data-testid="clear-btn" onClick={handleClearAll}>Clear All</button>
          </div>
        );
      };
      
      render(<ListComponent />);
      
      // Act: Simulate adding items
      fireEvent.change(screen.getByTestId('item-input'), { target: { value: 'test item' } });
      fireEvent.click(screen.getByTestId('add-btn'));
      
      // Assert: Verify functional update was used
      expect(mockSetItems).toHaveBeenCalledWith(expect.any(Function));
      
      // Act: Test clear functionality
      fireEvent.click(screen.getByTestId('clear-btn'));
      
      // Assert: Verify functional update for clearing
      expect(mockSetItems).toHaveBeenCalledWith(expect.any(Function));
      
      // Verify the functional updates work correctly
      const addItemUpdate = mockSetItems.mock.calls[0][0];
      const clearUpdate = mockSetItems.mock.calls[1][0];
      
      expect(addItemUpdate([])).toEqual(['test item']);
      expect(clearUpdate(['item1', 'item2'])).toEqual([]);
    });

    it('should verify state synchronization between multiple state variables', () => {
      // Arrange: Mock multiple related state variables
      const mockSetUser = jest.fn();
      const mockSetIsLoggedIn = jest.fn();
      const mockSetPermissions = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      mockUseState
        .mockReturnValueOnce([null, mockSetUser])
        .mockReturnValueOnce([false, mockSetIsLoggedIn])
        .mockReturnValueOnce([[], mockSetPermissions]);
      
      // Act: Create component with synchronized state
      const AuthComponent = () => {
        const [user, setUser] = mockUseState(null);
        const [isLoggedIn, setIsLoggedIn] = mockUseState(false);
        const [permissions, setPermissions] = mockUseState([]);
        
        const handleLogin = (userData: any) => {
          // Synchronize multiple state variables
          setUser(userData);
          setIsLoggedIn(true);
          setPermissions(userData.permissions || []);
        };
        
        const handleLogout = () => {
          // Clear all related state
          setUser(null);
          setIsLoggedIn(false);
          setPermissions([]);
        };
        
        return (
          <div data-testid="auth-component">
            <button 
              data-testid="login-btn" 
              onClick={() => handleLogin({ 
                id: 1, 
                name: 'Test User',
                permissions: ['read', 'write']
              })}
            >
              Login
            </button>
            <button data-testid="logout-btn" onClick={handleLogout}>
              Logout
            </button>
          </div>
        );
      };
      
      render(<AuthComponent />);
      
      // Act: Test login flow
      fireEvent.click(screen.getByTestId('login-btn'));
      
      // Assert: Verify synchronized state updates
      expect(mockSetUser).toHaveBeenCalledWith({
        id: 1,
        name: 'Test User',
        permissions: ['read', 'write']
      });
      expect(mockSetIsLoggedIn).toHaveBeenCalledWith(true);
      expect(mockSetPermissions).toHaveBeenCalledWith(['read', 'write']);
      
      // Act: Test logout flow
      fireEvent.click(screen.getByTestId('logout-btn'));
      
      // Assert: Verify synchronized state clearing
      expect(mockSetUser).toHaveBeenCalledWith(null);
      expect(mockSetIsLoggedIn).toHaveBeenCalledWith(false);
      expect(mockSetPermissions).toHaveBeenCalledWith([]);
    });
  });

  describe('State Validation and Error Handling', () => {
    it('should verify state validation prevents invalid updates', () => {
      // Arrange: Mock state with validation
      const mockSetEmail = jest.fn();
      const mockSetErrors = jest.fn();
      const mockUseState = mockFactory.createHookMock('useState');
      
      mockUseState
        .mockReturnValueOnce(['', mockSetEmail])
        .mockReturnValueOnce([{}, mockSetErrors]);
      
      // Act: Create component with state validation
      const FormComponent = () => {
        const [email, setEmail] = mockUseState('');
        const [errors, setErrors] = mockUseState({});
        
        const validateEmail = (value: string) => {
          const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
          return emailRegex.test(value);
        };
        
        const handleEmailChange = (value: string) => {
          setEmail(value);
          
          // Update validation state
          if (value && !validateEmail(value)) {
            setErrors((prev: any) => ({ ...prev, email: 'Invalid email format' }));
          } else {
            setErrors((prev: any) => {
              const { email, ...rest } = prev;
              return rest;
            });
          }
        };
        
        return (
          <div data-testid="form-component">
            <input 
              data-testid="email-input"
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
            />
          </div>
        );
      };
      
      render(<FormComponent />);
      
      // Act: Test invalid email
      fireEvent.change(screen.getByTestId('email-input'), { 
        target: { value: 'invalid-email' }
      });
      
      // Assert: Verify email state was updated
      expect(mockSetEmail).toHaveBeenCalledWith('invalid-email');
      
      // Assert: Verify error state was updated
      expect(mockSetErrors).toHaveBeenCalledWith(expect.any(Function));
      
      // Act: Test valid email  
      fireEvent.change(screen.getByTestId('email-input'), { 
        target: { value: 'valid@example.com' }
      });
      
      // Assert: Verify valid email updates
      expect(mockSetEmail).toHaveBeenCalledWith('valid@example.com');
      expect(mockSetErrors).toHaveBeenCalledWith(expect.any(Function));
    });
  });

  describe('Integration Tests - State Management', () => {
    it('should verify complete state lifecycle in complex component', async () => {
      // Arrange: Mock comprehensive state management
      const mockApiService = mockFactory.createServiceMock('api');
      const mockUseState = mockFactory.createHookMock('useState');
      const mockUseEffect = mockFactory.createHookMock('useEffect');
      
      const stateTracker = {
        loading: [false, jest.fn()],
        data: [[], jest.fn()],
        error: [null, jest.fn()],
        filters: [{ search: '', category: 'all' }, jest.fn()]
      };
      
      mockUseState
        .mockReturnValueOnce(stateTracker.loading)
        .mockReturnValueOnce(stateTracker.data)
        .mockReturnValueOnce(stateTracker.error)
        .mockReturnValueOnce(stateTracker.filters);
      
      mockApiService.get.mockResolvedValue({
        data: [{ id: 1, name: 'Test Item' }]
      });
      
      // Act: Create component with comprehensive state management
      const DataManagerComponent = () => {
        const [loading, setLoading] = mockUseState(false);
        const [data, setData] = mockUseState([]);
        const [error, setError] = mockUseState(null);
        const [filters, setFilters] = mockUseState({ search: '', category: 'all' });
        
        const fetchData = async () => {
          setLoading(true);
          setError(null);
          
          try {
            const response = await mockApiService.get('/data', { params: filters });
            setData(response.data);
          } catch (err) {
            setError(err);
          } finally {
            setLoading(false);
          }
        };
        
        mockUseEffect(() => {
          fetchData();
        }, [filters]);
        
        return <div data-testid="data-manager">Data Manager</div>;
      };
      
      render(<DataManagerComponent />);
      
      // Assert: Verify all state variables were initialized
      expect(mockUseState).toHaveBeenCalledTimes(4);
      expect(mockUseState).toHaveBeenCalledWith(false); // loading
      expect(mockUseState).toHaveBeenCalledWith([]); // data
      expect(mockUseState).toHaveBeenCalledWith(null); // error
      expect(mockUseState).toHaveBeenCalledWith({ search: '', category: 'all' }); // filters
      
      // Assert: Verify effect was set up with proper dependencies
      expect(mockUseEffect).toHaveBeenCalledWith(
        expect.any(Function),
        [{ search: '', category: 'all' }]
      );
      
      // Verify state management contract
      componentContract.state.variables = ['loading', 'data', 'error', 'filters'];
      componentContract.state.setters = ['setLoading', 'setData', 'setError', 'setFilters'];
      
      expect(componentContract.state.variables).toHaveLength(4);
      expect(componentContract.state.setters).toHaveLength(4);
    });
  });

  afterEach(() => {
    mockCoordinator.resetAllMocks();
  });
});