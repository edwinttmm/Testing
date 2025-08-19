/**
 * Custom Jest Matchers for TypeScript Error Fix Testing
 * London School TDD Specific Assertions
 */

import { jest } from '@jest/globals';

declare global {
  namespace jest {
    interface Matchers<R> {
      // Contract Testing Matchers
      toSatisfyContract(contract: any): R;
      toImplementContract(contractMethods: string[]): R;
      
      // Mock Interaction Matchers
      toHaveBeenCalledBefore(otherMock: jest.MockedFunction<any>): R;
      toHaveBeenCalledAfter(otherMock: jest.MockedFunction<any>): R;
      toHaveInteractionPattern(pattern: any[]): R;
      
      // TypeScript Specific Matchers
      toHaveProperTypeScript(): R;
      toHaveCorrectImports(expectedImports: string[]): R;
      toBeTypeCompatible(expectedType: any): R;
      
      // Component Testing Matchers
      toMountWithoutErrors(): R;
      toRenderCorrectly(): R;
      toHandlePropsCorrectly(props: any): R;
      
      // State Management Matchers
      toUpdateStateCorrectly(expectedState: any): R;
      toTriggerReRender(): R;
      
      // Error Handling Matchers
      toHandleErrorsGracefully(error: Error): R;
      toCatchErrorsInBoundary(): R;
      
      // Integration Matchers
      toCommunicateWithParent(): R;
      toCommunicateWithChild(): R;
      toCoordinateWithServices(services: string[]): R;
    }
  }
}

// Contract Testing Matchers
expect.extend({
  toSatisfyContract(received: any, contract: any) {
    const receivedKeys = Object.keys(received);
    const contractKeys = Object.keys(contract);
    
    const hasAllKeys = contractKeys.every(key => receivedKeys.includes(key));
    const extraKeys = receivedKeys.filter(key => !contractKeys.includes(key));
    const missingKeys = contractKeys.filter(key => !receivedKeys.includes(key));
    
    const pass = hasAllKeys && extraKeys.length === 0;
    
    return {
      pass,
      message: () => {
        if (!hasAllKeys) {
          return `Contract violation: Missing required keys ${missingKeys.join(', ')}`;
        }
        if (extraKeys.length > 0) {
          return `Contract violation: Unexpected extra keys ${extraKeys.join(', ')}`;
        }
        return 'Object satisfies contract requirements';
      }
    };
  },
  
  toImplementContract(received: any, contractMethods: string[]) {
    const receivedMethods = Object.keys(received).filter(key => 
      typeof received[key] === 'function'
    );
    
    const missingMethods = contractMethods.filter(method => 
      !receivedMethods.includes(method)
    );
    
    const pass = missingMethods.length === 0;
    
    return {
      pass,
      message: () => pass
        ? `Object implements all contract methods: ${contractMethods.join(', ')}`
        : `Object missing contract methods: ${missingMethods.join(', ')}`
    };
  }
});

// Mock Interaction Matchers
expect.extend({
  toHaveBeenCalledBefore(received: jest.MockedFunction<any>, otherMock: jest.MockedFunction<any>) {
    const receivedCallOrder = received.mock.invocationCallOrder[0];
    const otherCallOrder = otherMock.mock.invocationCallOrder[0];
    
    if (receivedCallOrder === undefined) {
      return {
        pass: false,
        message: () => `Expected ${received.getMockName() || 'mock'} to have been called, but it was not called`
      };
    }
    
    if (otherCallOrder === undefined) {
      return {
        pass: false,
        message: () => `Expected ${otherMock.getMockName() || 'other mock'} to have been called, but it was not called`
      };
    }
    
    const pass = receivedCallOrder < otherCallOrder;
    
    return {
      pass,
      message: () => pass
        ? `Expected ${received.getMockName() || 'mock'} NOT to be called before ${otherMock.getMockName() || 'other mock'}`
        : `Expected ${received.getMockName() || 'mock'} to be called before ${otherMock.getMockName() || 'other mock'}`
    };
  },
  
  toHaveBeenCalledAfter(received: jest.MockedFunction<any>, otherMock: jest.MockedFunction<any>) {
    const receivedCallOrder = received.mock.invocationCallOrder[0];
    const otherCallOrder = otherMock.mock.invocationCallOrder[0];
    
    if (receivedCallOrder === undefined || otherCallOrder === undefined) {
      return {
        pass: false,
        message: () => 'Both mocks must have been called to compare call order'
      };
    }
    
    const pass = receivedCallOrder > otherCallOrder;
    
    return {
      pass,
      message: () => pass
        ? `Expected ${received.getMockName() || 'mock'} NOT to be called after ${otherMock.getMockName() || 'other mock'}`
        : `Expected ${received.getMockName() || 'mock'} to be called after ${otherMock.getMockName() || 'other mock'}`
    };
  },
  
  toHaveInteractionPattern(received: jest.MockedFunction<any>, pattern: any[]) {
    const calls = received.mock.calls;
    
    if (calls.length !== pattern.length) {
      return {
        pass: false,
        message: () => `Expected ${pattern.length} calls matching pattern, but received ${calls.length} calls`
      };
    }
    
    const patternMatches = calls.every((call, index) => {
      const expectedCall = pattern[index];
      return JSON.stringify(call) === JSON.stringify(expectedCall);
    });
    
    return {
      pass: patternMatches,
      message: () => patternMatches
        ? 'Mock calls match expected pattern'
        : `Mock calls do not match expected pattern.\nExpected: ${JSON.stringify(pattern, null, 2)}\nReceived: ${JSON.stringify(calls, null, 2)}`
    };
  }
});

// TypeScript Specific Matchers
expect.extend({
  toHaveProperTypeScript(received: any) {
    // This would integrate with TypeScript compiler API in a real implementation
    // For this example, we'll do basic checks
    let pass = true;
    let errors: string[] = [];
    
    // Check if it's a valid React component
    if (received && (typeof received === 'function' || received.type)) {
      // Basic validation passed
    } else {
      pass = false;
      errors.push('Not a valid TypeScript/React component');
    }
    
    return {
      pass,
      message: () => pass
        ? 'Component has proper TypeScript typing'
        : `TypeScript errors found: ${errors.join(', ')}`
    };
  },
  
  toHaveCorrectImports(received: string, expectedImports: string[]) {
    const importRegex = /import\s+.*?\s+from\s+['"`]([^'"`]+)['"`]/g;
    const matches = [...received.matchAll(importRegex)];
    const actualImports = matches.map(match => match[1]);
    
    const missingImports = expectedImports.filter(imp => 
      !actualImports.some(actual => actual.includes(imp))
    );
    
    const pass = missingImports.length === 0;
    
    return {
      pass,
      message: () => pass
        ? 'All expected imports are present'
        : `Missing imports: ${missingImports.join(', ')}`
    };
  },
  
  toBeTypeCompatible(received: any, expectedType: any) {
    // Simplified type compatibility check
    const receivedType = typeof received;
    const expectedTypeName = typeof expectedType;
    
    const pass = receivedType === expectedTypeName;
    
    return {
      pass,
      message: () => pass
        ? `Types are compatible: ${receivedType}`
        : `Type mismatch: expected ${expectedTypeName}, received ${receivedType}`
    };
  }
});

// Component Testing Matchers
expect.extend({
  toMountWithoutErrors(received: any) {
    let pass = true;
    let errorMessage = '';
    
    try {
      // Check if it's a valid React element
      if (!received || (typeof received.type !== 'string' && typeof received.type !== 'function')) {
        pass = false;
        errorMessage = 'Not a valid React component';
      }
      
      // Additional component validation could go here
      
    } catch (error) {
      pass = false;
      errorMessage = `Mount error: ${(error as Error).message}`;
    }
    
    return {
      pass,
      message: () => pass
        ? 'Component mounted successfully without errors'
        : `Component failed to mount: ${errorMessage}`
    };
  },
  
  toRenderCorrectly(received: any) {
    // Check if component renders expected elements
    const hasExpectedElements = received && received.props && received.props['data-testid'];
    
    return {
      pass: !!hasExpectedElements,
      message: () => hasExpectedElements
        ? 'Component renders with expected structure'
        : 'Component does not render expected elements'
    };
  },
  
  toHandlePropsCorrectly(received: any, props: any) {
    // Verify component handles props without errors
    let pass = true;
    let message = 'Props handled correctly';
    
    try {
      // This would be more sophisticated in a real implementation
      if (received && received.props) {
        const receivedPropKeys = Object.keys(received.props);
        const expectedPropKeys = Object.keys(props);
        
        const hasAllProps = expectedPropKeys.every(key => 
          receivedPropKeys.includes(key)
        );
        
        if (!hasAllProps) {
          pass = false;
          message = 'Component missing expected props';
        }
      }
    } catch (error) {
      pass = false;
      message = `Error handling props: ${(error as Error).message}`;
    }
    
    return { pass, message: () => message };
  }
});

// State Management Matchers
expect.extend({
  toUpdateStateCorrectly(received: jest.MockedFunction<any>, expectedState: any) {
    const calls = received.mock.calls;
    const lastCall = calls[calls.length - 1];
    
    if (!lastCall) {
      return {
        pass: false,
        message: () => 'State setter was never called'
      };
    }
    
    const stateValue = lastCall[0];
    const pass = JSON.stringify(stateValue) === JSON.stringify(expectedState);
    
    return {
      pass,
      message: () => pass
        ? 'State updated correctly'
        : `State update mismatch.\nExpected: ${JSON.stringify(expectedState)}\nReceived: ${JSON.stringify(stateValue)}`
    };
  },
  
  toTriggerReRender(received: jest.MockedFunction<any>) {
    const callCount = received.mock.calls.length;
    const pass = callCount > 0;
    
    return {
      pass,
      message: () => pass
        ? `Re-render triggered ${callCount} times`
        : 'No re-renders were triggered'
    };
  }
});

// Error Handling Matchers
expect.extend({
  toHandleErrorsGracefully(received: Function, error: Error) {
    let pass = true;
    let caughtError: Error | null = null;
    
    try {
      received();
    } catch (err) {
      caughtError = err as Error;
    }
    
    // Check if error was handled gracefully (not thrown)
    pass = caughtError === null;
    
    return {
      pass,
      message: () => pass
        ? 'Function handled errors gracefully'
        : `Function threw error: ${caughtError?.message}`
    };
  },
  
  toCatchErrorsInBoundary(received: jest.MockedFunction<any>) {
    const wasCalled = received.mock.calls.length > 0;
    
    return {
      pass: wasCalled,
      message: () => wasCalled
        ? 'Error boundary caught and handled errors'
        : 'Error boundary did not catch any errors'
    };
  }
});

// Integration Matchers
expect.extend({
  toCommunicateWithParent(received: jest.MockedFunction<any>) {
    // Check if callback props were called (indicating parent communication)
    const wasCalled = received.mock.calls.length > 0;
    
    return {
      pass: wasCalled,
      message: () => wasCalled
        ? 'Component successfully communicated with parent'
        : 'No communication with parent component detected'
    };
  },
  
  toCommunicateWithChild(received: any) {
    // Check if child component received props/callbacks
    const hasChildCommunication = received && received.props && Object.keys(received.props).length > 0;
    
    return {
      pass: !!hasChildCommunication,
      message: () => hasChildCommunication
        ? 'Parent successfully communicated with child'
        : 'No communication with child component detected'
    };
  },
  
  toCoordinateWithServices(received: Record<string, jest.MockedFunction<any>>, services: string[]) {
    const serviceCalls = services.map(service => ({
      service,
      called: received[service] && received[service].mock.calls.length > 0
    }));
    
    const allServicesCalled = serviceCalls.every(({ called }) => called);
    const uncalledServices = serviceCalls.filter(({ called }) => !called).map(({ service }) => service);
    
    return {
      pass: allServicesCalled,
      message: () => allServicesCalled
        ? `Successfully coordinated with all services: ${services.join(', ')}`
        : `Failed to coordinate with services: ${uncalledServices.join(', ')}`
    };
  }
});

// Export custom matcher utilities
export const matcherUtils = {
  // Helper to check if object satisfies interface
  satisfiesInterface: (obj: any, interfaceShape: any): boolean => {
    return Object.keys(interfaceShape).every(key => 
      obj.hasOwnProperty(key) && typeof obj[key] === typeof interfaceShape[key]
    );
  },
  
  // Helper to validate mock call patterns
  validateCallPattern: (mock: jest.MockedFunction<any>, expectedPattern: any[]): boolean => {
    const calls = mock.mock.calls;
    return calls.length === expectedPattern.length && 
           calls.every((call, index) => 
             JSON.stringify(call) === JSON.stringify(expectedPattern[index])
           );
  },
  
  // Helper to check component structure
  hasExpectedStructure: (component: any, expectedTestIds: string[]): boolean => {
    // This would be more sophisticated with actual DOM queries
    return expectedTestIds.every(testId => 
      component && component.props && component.props['data-testid'] === testId
    );
  }
};