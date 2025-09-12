# Detection Error Boundary

A comprehensive React Error Boundary component specifically designed for handling errors in AI model validation and detection systems.

## Features

- **Comprehensive Error Handling**: Catches React component errors during render, lifecycle, and constructor phases
- **Error Categorization**: Automatically categorizes errors into Network, Rendering, Processing, Hardware, Authentication, Permission, and Validation types
- **Severity-Based Responses**: Provides appropriate UI responses based on error severity (Low, Medium, High, Critical)
- **Frame 80 Specific Handling**: Special handling for Frame 80 detection failures common in video processing
- **Auto-Recovery**: Configurable automatic retry mechanisms with exponential backoff
- **User-Friendly UI**: Professional error displays with recovery instructions
- **Error Reporting**: Integration with external error reporting services
- **Development Support**: Detailed debugging information in development mode
- **Error Throttling**: Prevents error spam from repeated identical errors

## Basic Usage

```tsx
import { DetectionErrorBoundary } from './components/detection/DetectionErrorBoundary';

function App() {
  return (
    <DetectionErrorBoundary
      onError={(error) => console.log('Error caught:', error)}
      maxRetries={3}
      enableAutoRecovery={true}
    >
      <YourDetectionComponent />
    </DetectionErrorBoundary>
  );
}
```

## Advanced Usage

### With Error Reporting Service

```tsx
import { 
  DetectionErrorBoundary, 
  createErrorReportingService 
} from './components/detection/DetectionErrorBoundary';

const errorService = createErrorReportingService(
  'https://api.example.com/error-reports',
  'your-api-key'
);

function App() {
  return (
    <DetectionErrorBoundary
      errorReportingService={errorService}
      userId="user-123"
      sessionId="session-456"
      environment="production"
      maxRetries={3}
      autoRetryDelay={5000}
      enableAutoRecovery={true}
      onError={(error, errorInfo) => {
        // Custom error handling
        console.error('Detection error:', error);
      }}
    >
      <VideoDetectionComponent />
    </DetectionErrorBoundary>
  );
}
```

### Using Higher-Order Component

```tsx
import { withDetectionErrorBoundary } from './components/detection/DetectionErrorBoundary';

const SafeVideoComponent = withDetectionErrorBoundary(
  VideoProcessingComponent,
  {
    maxRetries: 2,
    enableAutoRecovery: true,
    autoRetryDelay: 3000
  }
);

function App() {
  return <SafeVideoComponent />;
}
```

## Error Categories

The component automatically categorizes errors based on error messages and stack traces:

### Network Errors
- API failures
- Connection timeouts
- Fetch/XHR errors
- **Auto-recovery**: Enabled by default
- **Severity**: High

### Rendering Errors
- Canvas context failures
- WebGL errors
- Graphics rendering issues
- **Auto-recovery**: Limited
- **Severity**: High

### Processing Errors
- Video decode errors
- Frame processing failures
- Algorithm timeouts
- **Auto-recovery**: Enabled for certain types
- **Severity**: High

### Hardware Errors
- Device connection failures
- LabJack USB errors
- GPU issues
- **Auto-recovery**: Disabled
- **Severity**: Critical

### Frame 80 Specific
- Special handling for Frame 80 detection failures
- Common in video processing workflows
- **Auto-recovery**: Enabled with frame skipping
- **Severity**: High

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `children` | `ReactNode` | - | Components to wrap with error boundary |
| `fallback` | `ReactNode` | - | Custom fallback UI when errors occur |
| `onError` | `(error, errorInfo) => void` | - | Callback when error occurs |
| `errorReportingService` | `ErrorReportingService` | - | External error reporting service |
| `maxRetries` | `number` | `3` | Maximum retry attempts |
| `autoRetryDelay` | `number` | `5000` | Delay between auto-retries (ms) |
| `enableAutoRecovery` | `boolean` | `false` | Enable automatic recovery attempts |
| `sessionId` | `string` | - | Session identifier for error tracking |
| `userId` | `string` | - | User identifier for error tracking |
| `environment` | `'development' \| 'staging' \| 'production'` | `'development'` | Environment for error context |

## Error Reporting Service

Create a custom error reporting service:

```tsx
import { createErrorReportingService } from './DetectionErrorBoundary';

const errorService = createErrorReportingService(
  '/api/error-reports',
  'your-api-key'
);

// Or create a custom service
const customErrorService = {
  reportError: async (error) => {
    await fetch('/custom-endpoint', {
      method: 'POST',
      body: JSON.stringify(error)
    });
  }
};
```

## Recovery Instructions

The component provides context-aware recovery instructions:

- **Network Errors**: Check connection, verify endpoints, clear cache
- **Rendering Errors**: Update drivers, try different browser, disable hardware acceleration
- **Processing Errors**: Check video format, system memory, process smaller segments
- **Hardware Errors**: Check connections, update drivers, restart devices
- **Frame 80 Errors**: Skip frame, check video encoding quality

## Development Features

In development mode, the component provides:

- Detailed error stack traces
- Component stack information
- Error categorization details
- Performance metrics
- Memory usage information

## Testing

The component includes comprehensive test coverage:

```bash
npm test DetectionErrorBoundary.test.tsx
```

## Performance Considerations

- Error throttling prevents performance issues from repeated errors
- Memory usage tracking in development mode
- Automatic cleanup of timeouts and intervals
- Efficient error categorization using regex patterns

## Browser Compatibility

- Modern browsers with ES2020 support
- WebGL context detection for rendering errors
- Clipboard API support for error copying
- Performance API for memory tracking

## Integration Tips

1. **Wrap at Component Level**: Place boundaries around individual detection components
2. **Configure Per Environment**: Use different settings for development/production
3. **Monitor Error Patterns**: Use error reporting to identify common failure modes
4. **Test Error Scenarios**: Simulate different error types during development
5. **Custom Recovery Logic**: Implement domain-specific recovery strategies

## Example Error Types

The component handles these common detection system errors:

```tsx
// Network errors
throw new Error('Network request failed: Connection timeout');

// Canvas rendering errors
throw new Error('Canvas rendering context failed: WebGL not supported');

// Video processing errors
throw new Error('Detection failure at frame 80: Processing timeout exceeded');

// Hardware errors
throw new Error('Hardware device not found: LabJack USB connection failed');
```

## Support

For issues or questions about the DetectionErrorBoundary component, check the test files for usage examples or refer to the comprehensive example component.