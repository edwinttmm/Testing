# Error Boundaries Implementation Guide

## Overview

The AI Model Validation Platform frontend implements comprehensive React Error Boundaries to improve error handling and user experience. This guide explains how to use the error boundary components and utilities throughout the application.

## Key Features

- **Comprehensive Error Categorization**: Network, API, WebSocket, Component, and Chunk loading errors
- **Automatic Retry Mechanisms**: Configurable retry logic with exponential backoff
- **User-Friendly Error Messages**: Context-aware error messages for different error types
- **Error Reporting Integration**: Automatic error logging and reporting
- **Development Tools**: Debug information and error details in development mode
- **Multiple Error Boundary Types**: App-level, page-level, and component-level boundaries

## Components

### 1. ErrorBoundary (Main Component)

The primary error boundary component with full functionality.

```tsx
import { ErrorBoundary } from '../components/ui/ErrorBoundary';

<ErrorBoundary
  level="component"
  context="user-profile"
  enableRetry={true}
  maxRetries={3}
  onError={(error, errorInfo, errorType) => {
    // Custom error handling
  }}
>
  <UserProfileComponent />
</ErrorBoundary>
```

**Props:**
- `level`: 'app' | 'page' | 'component' - Error boundary level
- `context`: string - Context identifier for debugging
- `enableRetry`: boolean - Enable retry functionality
- `maxRetries`: number - Maximum retry attempts
- `onError`: callback - Custom error handler
- `fallback`: ReactNode - Custom fallback UI

### 2. WebSocketErrorBoundary

Specialized error boundary for WebSocket connections.

```tsx
import { WebSocketErrorBoundary } from '../components/ui/WebSocketErrorBoundary';

<WebSocketErrorBoundary
  connectionStatus="disconnected"
  reconnectAction={() => reconnectWebSocket()}
>
  <RealTimeDataComponent />
</WebSocketErrorBoundary>
```

### 3. AsyncErrorBoundary

Error boundary for asynchronous operations with loading states.

```tsx
import { AsyncErrorBoundary } from '../components/ui/AsyncErrorBoundary';

<AsyncErrorBoundary
  asyncOperation={async () => await fetchData()}
  dependencies={[userId]}
  loadingComponent={<CustomLoader />}
  errorComponent={(error, retry) => <CustomError error={error} onRetry={retry} />}
>
  <DataDisplayComponent />
</AsyncErrorBoundary>
```

## Hooks

### 1. useErrorBoundary

Manual error boundary functionality for event handlers and async operations.

```tsx
import { useErrorBoundary } from '../hooks/useErrorBoundary';

const { captureError, clearError, throwError, error, hasError } = useErrorBoundary();

const handleButtonClick = () => {
  try {
    riskyOperation();
  } catch (error) {
    captureError(error, 'button-click-handler');
  }
};
```

### 2. useApiError

Specialized hook for API error handling.

```tsx
import { useApiError } from '../hooks/useErrorBoundary';

const { handleApiError } = useApiError();

const fetchUserData = async () => {
  try {
    const response = await api.getUser(userId);
    setUser(response.data);
  } catch (error) {
    handleApiError(error, 'fetch-user-data');
  }
};
```

### 3. useWebSocketError

Hook for WebSocket error handling.

```tsx
import { useWebSocketError } from '../hooks/useErrorBoundary';

const { handleWebSocketError } = useWebSocketError();

useEffect(() => {
  const ws = new WebSocket(WS_URL);
  
  ws.onerror = (event) => {
    handleWebSocketError(event, 'realtime-connection');
  };
}, []);
```

## Higher-Order Component Pattern

Use the `withErrorBoundary` HOC to wrap components with error boundaries.

```tsx
import { withErrorBoundary } from '../components/ui/ErrorBoundary';

const MyComponent = () => {
  return <div>Component content</div>;
};

const SafeComponent = withErrorBoundary(MyComponent, {
  level: 'component',
  context: 'my-component',
  enableRetry: true,
});
```

## Error Types and Categorization

The system automatically categorizes errors for appropriate handling:

### Network Errors
- Connection failures
- Timeout errors
- DNS resolution failures

### API Errors
- HTTP 4xx/5xx responses
- Authentication failures
- Validation errors

### WebSocket Errors
- Connection drops
- Protocol errors
- Reconnection failures

### Component Errors
- Rendering failures
- State management issues
- Prop validation errors

### Chunk Loading Errors
- Dynamic import failures
- Code splitting issues
- Resource loading problems

## Error Reporting

The system includes comprehensive error reporting:

```tsx
import errorReporting from '../services/errorReporting';

// Manual error reporting
errorReporting.reportError({
  message: 'Custom error occurred',
  level: 'component',
  context: 'user-action',
  additionalData: { userId, action: 'button-click' }
});
```

## Configuration

Configure error reporting in your environment:

```env
REACT_APP_ERROR_REPORTING_ENDPOINT=https://api.example.com/errors
REACT_APP_ERROR_REPORTING_API_KEY=your-api-key
REACT_APP_ENABLE_ERROR_REPORTING=true
```

## Best Practices

### 1. Error Boundary Placement

```tsx
// ✅ Good - Multiple levels of error boundaries
<ErrorBoundary level="app" context="application-root">
  <App>
    <ErrorBoundary level="page" context="dashboard">
      <Dashboard>
        <ErrorBoundary level="component" context="chart">
          <ChartComponent />
        </ErrorBoundary>
      </Dashboard>
    </ErrorBoundary>
  </App>
</ErrorBoundary>
```

### 2. Context Naming

Use descriptive, hierarchical context names:

```tsx
// ✅ Good
context="dashboard-analytics-chart"
context="user-profile-avatar-upload"
context="project-settings-permissions"

// ❌ Avoid
context="component"
context="error"
context="test"
```

### 3. Retry Configuration

Configure retries based on error type:

```tsx
// Network/API errors - enable retry
<ErrorBoundary enableRetry={true} maxRetries={3}>
  <ApiDataComponent />
</ErrorBoundary>

// UI/Component errors - disable retry
<ErrorBoundary enableRetry={false}>
  <StaticUIComponent />
</ErrorBoundary>
```

### 4. Custom Error Messages

Provide context-specific error handling:

```tsx
const handleCustomError = (error, errorInfo, errorType) => {
  if (errorType === 'network') {
    showNotification('Connection issue. Please check your internet.');
  } else if (errorType === 'api') {
    showNotification('Server temporarily unavailable.');
  }
};

<ErrorBoundary onError={handleCustomError}>
  <DataComponent />
</ErrorBoundary>
```

## Testing Error Boundaries

Use the provided test utilities for error boundary testing:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from '../components/ui/ErrorBoundary';

// Component that throws an error
const ThrowError = ({ shouldThrow = true }) => {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>Success</div>;
};

test('renders error UI when child component throws', () => {
  render(
    <ErrorBoundary>
      <ThrowError />
    </ErrorBoundary>
  );

  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
});
```

## Implementation Examples

See `/src/examples/ErrorBoundaryExamples.tsx` for comprehensive implementation examples including:

- Basic error boundary usage
- API error handling
- WebSocket error boundaries
- Async error boundaries
- HOC patterns
- Manual error reporting

## Troubleshooting

### Common Issues

1. **Error boundaries not catching errors in event handlers**
   - Use `useErrorBoundary` hook for manual error capture

2. **Async errors not being caught**
   - Use `AsyncErrorBoundary` or manual error capture

3. **Development vs Production behavior**
   - Error boundaries show different UI in development/production
   - Use `process.env.NODE_ENV` checks for environment-specific behavior

### Debug Information

In development mode, error boundaries provide detailed debug information:

- Error ID for tracking
- Error type categorization
- Component stack trace
- Additional context data

## Migration Guide

### From Basic Error Handling

```tsx
// Before
try {
  await apiCall();
} catch (error) {
  console.error(error);
  setError(error.message);
}

// After
const { handleApiError } = useApiError();

try {
  await apiCall();
} catch (error) {
  handleApiError(error, 'api-call-context');
}
```

### From Component-Level Error Handling

```tsx
// Before
class MyComponent extends React.Component {
  componentDidCatch(error, errorInfo) {
    console.error(error);
  }
}

// After
const SafeMyComponent = withErrorBoundary(MyComponent, {
  level: 'component',
  context: 'my-component',
});
```

## Performance Considerations

- Error boundaries are lightweight and don't impact performance
- Error reporting is throttled and batched to prevent spam
- Debug information is only collected in development mode
- Failed network requests use exponential backoff to prevent cascading failures

## Security Considerations

- Error messages are sanitized before display
- Sensitive information is filtered from error reports
- Stack traces are only shown in development mode
- Error IDs are generated securely without exposing system information