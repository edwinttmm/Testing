/**
 * TypeScript Error Fix Contracts - London School TDD
 * Defines behavioral contracts for validating TypeScript error fixes
 */

export interface ComponentContract {
  // Import Resolution Contract
  imports: {
    react: string[];
    hooks: string[];
    components: string[];
    services: string[];
  };
  
  // Function Declaration Contract
  functions: {
    declared: string[];
    hoisted: string[];
    callbacks: string[];
  };
  
  // State Management Contract
  state: {
    variables: string[];
    setters: string[];
    hooks: string[];
  };
  
  // Rendering Contract
  rendering: {
    mounts: boolean;
    renders: boolean;
    updates: boolean;
  };
}

export interface MockContract {
  // External Dependencies
  reactHooks: {
    useState: jest.MockedFunction<any>;
    useEffect: jest.MockedFunction<any>;
    useCallback: jest.MockedFunction<any>;
    useMemo: jest.MockedFunction<any>;
  };
  
  // API Services
  apiService: {
    get: jest.MockedFunction<any>;
    post: jest.MockedFunction<any>;
    put: jest.MockedFunction<any>;
    delete: jest.MockedFunction<any>;
  };
  
  // WebSocket Service
  websocketService: {
    connect: jest.MockedFunction<any>;
    disconnect: jest.MockedFunction<any>;
    emit: jest.MockedFunction<any>;
    on: jest.MockedFunction<any>;
  };
  
  // Error Boundary
  errorBoundary: {
    componentDidCatch: jest.MockedFunction<any>;
    render: jest.MockedFunction<any>;
  };
}

export interface TestScenarioContract {
  setup: () => Promise<void>;
  teardown: () => Promise<void>;
  verifyInteractions: () => void;
  assertExpectations: () => void;
}

// Contract Validation Patterns
export const CONTRACT_PATTERNS = {
  IMPORT_RESOLUTION: /^import\s+.*\s+from\s+['"].*['"]$/,
  FUNCTION_DECLARATION: /^(const|function|async function)\s+\w+/,
  STATE_HOOK: /useState<.*>\(/,
  CALLBACK_HOOK: /useCallback\(/,
  EFFECT_HOOK: /useEffect\(/,
  TYPE_ANNOTATION: /:\s*\w+(\[\]|\<.*\>)?/,
} as const;

// Mock Factory Contracts
export interface MockFactoryContract {
  createComponentMock: (name: string) => React.ComponentType<any>;
  createHookMock: (hookName: string) => jest.MockedFunction<any>;
  createServiceMock: (serviceName: string) => Record<string, jest.MockedFunction<any>>;
  createErrorBoundaryMock: () => React.ComponentType<any>;
}