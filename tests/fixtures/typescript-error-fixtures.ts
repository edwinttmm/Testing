/**
 * TypeScript Error Fix Test Fixtures - London School TDD
 * Test data and scenarios for validating TypeScript error fixes
 */

// Import Resolution Test Fixtures
export const importResolutionFixtures = {
  // Missing React hooks import
  missingHooksImport: {
    before: `
import React from 'react';

const MyComponent = () => {
  const [state, setState] = useState(false);
  return <div>{state ? 'On' : 'Off'}</div>;
};
    `,
    after: `
import React, { useState } from 'react';

const MyComponent = () => {
  const [state, setState] = useState(false);
  return <div>{state ? 'On' : 'Off'}</div>;
};
    `,
    expectedImports: ['useState'],
    expectedError: "Cannot find name 'useState'"
  },
  
  // Missing component import
  missingComponentImport: {
    before: `
import React from 'react';

const ParentComponent = () => {
  return (
    <div>
      <ChildComponent />
    </div>
  );
};
    `,
    after: `
import React from 'react';
import ChildComponent from './ChildComponent';

const ParentComponent = () => {
  return (
    <div>
      <ChildComponent />
    </div>
  );
};
    `,
    expectedImports: ['ChildComponent'],
    expectedError: "Cannot find name 'ChildComponent'"
  }
};

// Function Declaration Test Fixtures
export const functionDeclarationFixtures = {
  // Function used before declaration
  functionHoistingIssue: {
    before: `
const MyComponent = () => {
  const handleClick = () => {
    processData();
  };
  
  const processData = () => {
    console.log('Processing...');
  };
  
  return <button onClick={handleClick}>Click</button>;
};
    `,
    after: `
const MyComponent = () => {
  const processData = () => {
    console.log('Processing...');
  };
  
  const handleClick = () => {
    processData();
  };
  
  return <button onClick={handleClick}>Click</button>;
};
    `,
    expectedFunctions: ['processData', 'handleClick'],
    expectedError: "Cannot access 'processData' before initialization"
  },
  
  // Missing useCallback dependency
  missingCallbackDependency: {
    before: `
const MyComponent = ({ data }) => {
  const [filter, setFilter] = useState('');
  
  const handleFilter = useCallback(() => {
    return data.filter(item => item.includes(filter));
  }, []); // Missing filter dependency
  
  return <div>{/* component */}</div>;
};
    `,
    after: `
const MyComponent = ({ data }) => {
  const [filter, setFilter] = useState('');
  
  const handleFilter = useCallback(() => {
    return data.filter(item => item.includes(filter));
  }, [data, filter]); // Added dependencies
  
  return <div>{/* component */}</div>;
};
    `,
    expectedDependencies: ['data', 'filter'],
    expectedWarning: "React Hook useCallback has missing dependencies"
  }
};

// State Management Test Fixtures
export const stateManagementFixtures = {
  // Undeclared state variable
  undeclaredState: {
    before: `
const MyComponent = () => {
  const handleSubmit = () => {
    if (isLoading) {
      return;
    }
    // ... submit logic
  };
  
  return <form onSubmit={handleSubmit}>{/* form */}</form>;
};
    `,
    after: `
const MyComponent = () => {
  const [isLoading, setIsLoading] = useState(false);
  
  const handleSubmit = () => {
    if (isLoading) {
      return;
    }
    // ... submit logic
  };
  
  return <form onSubmit={handleSubmit}>{/* form */}</form>;
};
    `,
    expectedStateVariables: ['isLoading'],
    expectedSetters: ['setIsLoading'],
    expectedError: "Cannot find name 'isLoading'"
  }
};

// Component Rendering Test Fixtures
export const componentRenderingFixtures = {
  // Type mismatch in props
  propTypeMismatch: {
    before: `
interface Props {
  count: number;
  onUpdate: (value: number) => void;
}

const Counter: React.FC<Props> = ({ count, onUpdate }) => {
  return (
    <div>
      <span>{count}</span>
      <button onClick={() => onUpdate('increment')}>+</button>
    </div>
  );
};
    `,
    after: `
interface Props {
  count: number;
  onUpdate: (value: number) => void;
}

const Counter: React.FC<Props> = ({ count, onUpdate }) => {
  return (
    <div>
      <span>{count}</span>
      <button onClick={() => onUpdate(count + 1)}>+</button>
    </div>
  );
};
    `,
    expectedProps: ['count', 'onUpdate'],
    expectedError: "Argument of type 'string' is not assignable to parameter of type 'number'"
  }
};

// Integration Test Fixtures
export const integrationTestFixtures = {
  // Component interaction scenario
  componentInteraction: {
    parentComponent: `
const ParentComponent = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await apiService.get('/data');
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  return (
    <div>
      <ChildComponent data={data} loading={loading} onRefresh={fetchData} />
    </div>
  );
};
    `,
    childComponent: `
interface ChildProps {
  data: any[];
  loading: boolean;
  onRefresh: () => void;
}

const ChildComponent: React.FC<ChildProps> = ({ data, loading, onRefresh }) => {
  if (loading) {
    return <div>Loading...</div>;
  }
  
  return (
    <div>
      <button onClick={onRefresh}>Refresh</button>
      {data.map(item => <div key={item.id}>{item.name}</div>)}
    </div>
  );
};
    `,
    expectedInteractions: ['apiService.get', 'setData', 'setLoading'],
    expectedProps: ['data', 'loading', 'onRefresh']
  }
};

// Error Scenarios for Testing
export const errorScenarios = {
  // Network error handling
  networkError: {
    mockResponse: {
      error: new Error('Network Error'),
      status: 500
    },
    expectedErrorHandling: ['catch block', 'error logging', 'user notification']
  },
  
  // Validation error
  validationError: {
    invalidData: {
      email: 'invalid-email',
      password: ''
    },
    expectedValidation: ['email format', 'password required']
  },
  
  // State update error
  stateUpdateError: {
    scenario: 'Component unmounted during async operation',
    expectedSafeguards: ['cleanup effect', 'mounted check']
  }
};

// Mock Data Fixtures
export const mockDataFixtures = {
  user: {
    id: '1',
    name: 'Test User',
    email: 'test@example.com',
    role: 'admin'
  },
  
  project: {
    id: '1',
    name: 'Test Project',
    description: 'A test project',
    createdAt: '2023-01-01T00:00:00Z',
    updatedAt: '2023-01-01T00:00:00Z'
  },
  
  apiResponse: {
    success: {
      data: { message: 'Success' },
      status: 200,
      statusText: 'OK'
    },
    error: {
      error: { message: 'Bad Request' },
      status: 400,
      statusText: 'Bad Request'
    }
  }
};