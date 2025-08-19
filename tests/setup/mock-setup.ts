/**
 * Mock Setup for TypeScript Error Fix Tests
 * London School TDD Mock Configuration
 */

import { jest } from '@jest/globals';

// Global Mock Store for Cross-Test Communication
global.mockStore = new Map();

// React Mock Configuration
jest.mock('react', () => {
  const actualReact = jest.requireActual('react');
  
  return {
    ...actualReact,
    useState: jest.fn().mockImplementation((initial: any) => [initial, jest.fn()]),
    useEffect: jest.fn().mockImplementation((effect: Function) => effect()),
    useContext: jest.fn().mockImplementation((context: any) => context._defaultValue || {}),
    useReducer: jest.fn().mockImplementation((reducer: Function, initial: any) => [initial, jest.fn()]),
    useCallback: jest.fn().mockImplementation((callback: Function) => callback),
    useMemo: jest.fn().mockImplementation((factory: Function) => factory()),
    useRef: jest.fn().mockImplementation((initial: any) => ({ current: initial })),
    useImperativeHandle: jest.fn(),
    useLayoutEffect: jest.fn().mockImplementation((effect: Function) => effect()),
    useDebugValue: jest.fn()
  };
});

// React DOM Mock
jest.mock('react-dom', () => ({
  render: jest.fn(),
  createPortal: jest.fn((children: any) => children),
  findDOMNode: jest.fn(),
  unmountComponentAtNode: jest.fn()
}));

// React Router Mock
jest.mock('react-router-dom', () => ({
  useNavigate: jest.fn(() => jest.fn()),
  useLocation: jest.fn(() => ({
    pathname: '/',
    search: '',
    hash: '',
    state: null,
    key: 'default'
  })),
  useParams: jest.fn(() => ({})),
  useSearchParams: jest.fn(() => [new URLSearchParams(), jest.fn()]),
  Link: ({ children, to, ...props }: any) => 
    actualReact.createElement('a', { href: to, ...props }, children),
  NavLink: ({ children, to, ...props }: any) => 
    actualReact.createElement('a', { href: to, ...props }, children),
  BrowserRouter: ({ children }: any) => children,
  Routes: ({ children }: any) => children,
  Route: ({ element }: any) => element
}));

// Material-UI Mock (if using MUI)
jest.mock('@mui/material', () => {
  const actualMui = jest.requireActual('@mui/material');
  
  return new Proxy(actualMui, {
    get(target, prop) {
      if (target[prop]) {
        return target[prop];
      }
      
      // Return mock component for any missing MUI component
      return jest.fn(({ children, ...props }) => 
        actualReact.createElement('div', { 
          ...props, 
          'data-testid': `mock-mui-${String(prop).toLowerCase()}` 
        }, children)
      );
    }
  });
});

// API Service Mock
jest.mock('../services/api', () => ({
  apiService: {
    get: jest.fn().mockResolvedValue({ data: {}, status: 200 }),
    post: jest.fn().mockResolvedValue({ data: {}, status: 201 }),
    put: jest.fn().mockResolvedValue({ data: {}, status: 200 }),
    delete: jest.fn().mockResolvedValue({ data: {}, status: 204 }),
    patch: jest.fn().mockResolvedValue({ data: {}, status: 200 })
  }
}));

// WebSocket Service Mock
jest.mock('../services/websocketService', () => ({
  websocketService: {
    connect: jest.fn().mockResolvedValue(true),
    disconnect: jest.fn().mockResolvedValue(true),
    emit: jest.fn().mockReturnValue(true),
    on: jest.fn().mockImplementation((event: string, handler: Function) => {
      // Store handler for later triggering in tests
      global.mockStore.set(`websocket_${event}`, handler);
      return () => global.mockStore.delete(`websocket_${event}`);
    }),
    off: jest.fn()
  }
}));

// Error Reporting Service Mock
jest.mock('../services/errorReporting', () => ({
  errorReporting: {
    captureException: jest.fn(),
    captureMessage: jest.fn(),
    setUser: jest.fn(),
    setTag: jest.fn(),
    setContext: jest.fn(),
    addBreadcrumb: jest.fn()
  }
}));

// Performance Monitor Mock
jest.mock('../utils/performanceMonitor', () => ({
  performanceMonitor: {
    mark: jest.fn(),
    measure: jest.fn(),
    getEntries: jest.fn().mockReturnValue([]),
    clearMarks: jest.fn(),
    clearMeasures: jest.fn()
  }
}));

// File System Mock (for Node.js testing)
jest.mock('fs', () => ({
  readFile: jest.fn(),
  writeFile: jest.fn(),
  readFileSync: jest.fn(),
  writeFileSync: jest.fn(),
  existsSync: jest.fn().mockReturnValue(true),
  mkdirSync: jest.fn(),
  promises: {
    readFile: jest.fn(),
    writeFile: jest.fn(),
    mkdir: jest.fn(),
    access: jest.fn()
  }
}));

// Path Mock
jest.mock('path', () => ({
  join: jest.fn((...args: string[]) => args.join('/')),
  resolve: jest.fn((...args: string[]) => args.join('/')),
  dirname: jest.fn((path: string) => path.split('/').slice(0, -1).join('/')),
  basename: jest.fn((path: string) => path.split('/').pop()),
  extname: jest.fn((path: string) => {
    const lastDot = path.lastIndexOf('.');
    return lastDot > 0 ? path.substring(lastDot) : '';
  })
}));

// Crypto Mock
jest.mock('crypto', () => ({
  randomUUID: jest.fn(() => 'mock-uuid-' + Date.now()),
  randomBytes: jest.fn((size: number) => Buffer.alloc(size, 'mock')),
  createHash: jest.fn(() => ({
    update: jest.fn().mockReturnThis(),
    digest: jest.fn(() => 'mock-hash')
  }))
}));

// Date Mock for Consistent Testing
const mockDate = new Date('2023-01-01T00:00:00.000Z');
jest.spyOn(global, 'Date').mockImplementation(() => mockDate);
Date.now = jest.fn(() => mockDate.getTime());

// Timeout Mocks
global.setTimeout = jest.fn((callback: Function, delay?: number) => {
  callback();
  return 'mock-timeout-id' as any;
});

global.clearTimeout = jest.fn();
global.setInterval = jest.fn((callback: Function, delay?: number) => {
  return 'mock-interval-id' as any;
});

global.clearInterval = jest.fn();

// Promise Mock Utilities
export const mockPromiseUtilities = {
  // Create a controllable promise for testing
  createControllablePromise: <T>() => {
    let resolve: (value: T) => void;
    let reject: (reason?: any) => void;
    
    const promise = new Promise<T>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    
    return {
      promise,
      resolve: resolve!,
      reject: reject!
    };
  },
  
  // Wait for all pending promises
  flushPromises: () => new Promise(resolve => setTimeout(resolve, 0)),
  
  // Create mock rejected promise
  createRejectedPromise: (error: Error) => Promise.reject(error),
  
  // Create mock resolved promise
  createResolvedPromise: <T>(value: T) => Promise.resolve(value)
};

// Mock Implementation Helpers
export const mockHelpers = {
  // Create a mock with call tracking
  createTrackedMock: (name: string) => {
    const mock = jest.fn();
    mock.mockName(name);
    
    // Store in global mock store for cross-test access
    global.mockStore.set(name, mock);
    
    return mock;
  },
  
  // Reset all tracked mocks
  resetTrackedMocks: () => {
    for (const [key, value] of global.mockStore.entries()) {
      if (jest.isMockFunction(value)) {
        value.mockReset();
      }
    }
  },
  
  // Get mock by name
  getMock: (name: string) => global.mockStore.get(name),
  
  // Create mock with specific return pattern
  createMockWithPattern: (pattern: 'resolve' | 'reject' | 'throw') => {
    switch (pattern) {
      case 'resolve':
        return jest.fn().mockResolvedValue('mock-result');
      case 'reject':
        return jest.fn().mockRejectedValue(new Error('mock-error'));
      case 'throw':
        return jest.fn().mockImplementation(() => {
          throw new Error('mock-throw-error');
        });
      default:
        return jest.fn();
    }
  }
};

// Contract Validation Helpers
export const contractHelpers = {
  // Validate mock implements required methods
  validateMockImplementation: (mock: any, requiredMethods: string[]) => {
    const mockMethods = Object.keys(mock);
    const missingMethods = requiredMethods.filter(method => !mockMethods.includes(method));
    
    if (missingMethods.length > 0) {
      throw new Error(`Mock is missing required methods: ${missingMethods.join(', ')}`);
    }
    
    return true;
  },
  
  // Validate mock call patterns
  validateCallPattern: (mock: jest.MockedFunction<any>, pattern: any[]) => {
    const calls = mock.mock.calls;
    
    if (calls.length !== pattern.length) {
      throw new Error(`Expected ${pattern.length} calls, but got ${calls.length}`);
    }
    
    for (let i = 0; i < pattern.length; i++) {
      expect(calls[i]).toEqual(pattern[i]);
    }
    
    return true;
  },
  
  // Validate interaction sequence
  validateInteractionSequence: (mocks: jest.MockedFunction<any>[], expectedOrder: string[]) => {
    const callTimes = mocks.map((mock, index) => ({
      name: expectedOrder[index],
      callTime: mock.mock.invocationCallOrder[0] || Infinity
    }));
    
    const sortedByCallTime = [...callTimes].sort((a, b) => a.callTime - b.callTime);
    const actualOrder = sortedByCallTime.map(item => item.name);
    
    expect(actualOrder).toEqual(expectedOrder);
    return true;
  }
};

// Export mock utilities for use in tests
export {
  mockPromiseUtilities,
  mockHelpers,
  contractHelpers
};