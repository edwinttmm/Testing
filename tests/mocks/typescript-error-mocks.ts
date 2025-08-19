/**
 * TypeScript Error Fix Mocks - London School TDD
 * Mock implementations for isolating units and testing interactions
 */

import { MockContract, MockFactoryContract } from '../contracts/typescript-error-contracts';

// React Hooks Mock Factory
export const createReactHooksMock = (): MockContract['reactHooks'] => ({
  useState: jest.fn().mockImplementation(<T>(initial: T) => [initial, jest.fn()]),
  useEffect: jest.fn().mockImplementation((effect: () => void, deps?: any[]) => {
    // Simulate immediate effect execution for testing
    if (!deps || deps.length === 0) {
      effect();
    }
  }),
  useCallback: jest.fn().mockImplementation((callback: Function, deps: any[]) => callback),
  useMemo: jest.fn().mockImplementation((factory: () => any, deps: any[]) => factory()),
});

// API Service Mock Factory
export const createApiServiceMock = (): MockContract['apiService'] => ({
  get: jest.fn().mockResolvedValue({ data: {}, status: 200 }),
  post: jest.fn().mockResolvedValue({ data: {}, status: 201 }),
  put: jest.fn().mockResolvedValue({ data: {}, status: 200 }),
  delete: jest.fn().mockResolvedValue({ data: {}, status: 204 }),
});

// WebSocket Service Mock Factory
export const createWebSocketServiceMock = (): MockContract['websocketService'] => ({
  connect: jest.fn().mockResolvedValue(true),
  disconnect: jest.fn().mockResolvedValue(true),
  emit: jest.fn().mockReturnValue(true),
  on: jest.fn().mockReturnValue(() => {}), // Returns unsubscribe function
});

// Error Boundary Mock Factory
export const createErrorBoundaryMock = (): MockContract['errorBoundary'] => ({
  componentDidCatch: jest.fn(),
  render: jest.fn().mockReturnValue(null),
});

// Component Mock Factory
export const createComponentMock = (name: string) => {
  const MockComponent = jest.fn().mockImplementation((props: any) => {
    // Track prop interactions
    MockComponent._lastProps = props;
    return <div data-testid={`mock-${name.toLowerCase()}`}>{name}</div>;
  });
  
  MockComponent.displayName = `Mock${name}`;
  MockComponent._lastProps = {};
  
  return MockComponent;
};

// Complete Mock Factory Implementation
export const mockFactory: MockFactoryContract = {
  createComponentMock: (name: string) => createComponentMock(name),
  
  createHookMock: (hookName: string) => {
    switch (hookName) {
      case 'useState':
        return createReactHooksMock().useState;
      case 'useEffect':
        return createReactHooksMock().useEffect;
      case 'useCallback':
        return createReactHooksMock().useCallback;
      case 'useMemo':
        return createReactHooksMock().useMemo;
      default:
        return jest.fn();
    }
  },
  
  createServiceMock: (serviceName: string) => {
    switch (serviceName) {
      case 'api':
        return createApiServiceMock();
      case 'websocket':
        return createWebSocketServiceMock();
      default:
        return {
          [serviceName]: jest.fn()
        };
    }
  },
  
  createErrorBoundaryMock: () => createErrorBoundaryMock() as any,
};

// Mock Coordination Helpers
export const mockCoordinator = {
  // Reset all mocks for clean test isolation
  resetAllMocks: () => {
    jest.clearAllMocks();
    jest.resetAllMocks();
  },
  
  // Verify interaction patterns
  verifyInteractionSequence: (mocks: jest.MockedFunction<any>[], expectedOrder: string[]) => {
    const callOrder = mocks.reduce((acc, mock, index) => {
      if (mock.mock.calls.length > 0) {
        acc.push({ index, name: expectedOrder[index], callCount: mock.mock.calls.length });
      }
      return acc;
    }, [] as Array<{index: number, name: string, callCount: number}>);
    
    return callOrder;
  },
  
  // Mock contract validation
  validateMockContract: (mock: any, contract: any) => {
    const mockMethods = Object.keys(mock);
    const contractMethods = Object.keys(contract);
    
    return {
      hasAllMethods: contractMethods.every(method => mockMethods.includes(method)),
      extraMethods: mockMethods.filter(method => !contractMethods.includes(method)),
      missingMethods: contractMethods.filter(method => !mockMethods.includes(method))
    };
  }
};

// Integration Test Mocks
export const integrationMocks = {
  // Full application context mock
  createAppContextMock: () => ({
    user: { id: '1', name: 'Test User' },
    projects: [{ id: '1', name: 'Test Project' }],
    notifications: [],
    theme: 'light',
    settings: { autoSave: true }
  }),
  
  // Router mock for navigation testing
  createRouterMock: () => ({
    navigate: jest.fn(),
    location: { pathname: '/', search: '', hash: '', state: null },
    params: {},
    query: {}
  }),
  
  // Global error handler mock
  createGlobalErrorHandlerMock: () => ({
    handleError: jest.fn(),
    reportError: jest.fn(),
    clearErrors: jest.fn()
  })
};