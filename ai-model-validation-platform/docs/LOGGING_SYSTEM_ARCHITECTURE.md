# Logging System Architecture

## Overview

This document describes the production-ready logging system designed to replace console.log statements throughout the AI Model Validation Platform.

## Architecture Components

### 1. Core Logger Service (`/frontend/src/services/logger.ts`)

**Key Features:**
- **Environment-aware**: Shows all logs in development, filters in production
- **Performance-optimized**: No-op when logging is disabled
- **Structured logging**: Consistent format with context and metadata
- **Component-scoped**: Each component gets its own logger instance
- **Remote logging ready**: Buffering and batch sending for external services

**Log Levels:**
```typescript
enum LogLevel {
  DEBUG = 0,  // Development debugging
  INFO = 1,   // General information
  WARN = 2,   // Warning conditions
  ERROR = 3,  // Error conditions
  NONE = 99   // Disable all logging
}
```

### 2. Configuration System (`/frontend/src/config/logging.config.ts`)

**Environment Detection:**
- Automatic environment detection (development/production/test)
- Debug mode detection from multiple sources
- Dynamic configuration overrides

**Performance Monitoring:**
- Sampling rate for performance data
- Memory usage tracking
- Slow operation detection

**Privacy & Security:**
- URL sanitization
- Sensitive data filtering
- Field exclusion rules

### 3. Utility Functions (`/frontend/src/utils/loggingUtils.ts`)

**ComponentLogger Class:**
- Specialized logging methods for different scenarios
- Performance tracking with timing
- User action logging
- API call logging with status codes
- WebSocket event logging
- Route change tracking

**Migration Helpers:**
- Direct console.log replacements
- Performance decorators
- Error boundary integration
- Batch migration utilities

## Environment Configuration

### Development (.env.development)
```bash
REACT_APP_LOG_LEVEL=debug
REACT_APP_LOG_CATEGORIES=*
REACT_APP_LOG_PERFORMANCE=true
REACT_APP_LOG_MEMORY_TRACKING=true
```

### Production (.env.production)
```bash
REACT_APP_LOG_LEVEL=error
REACT_APP_LOG_CATEGORIES=error,warn
REACT_APP_LOG_PERFORMANCE=false
REACT_APP_LOG_MEMORY_TRACKING=false
```

## Integration Examples

### Basic Component Integration

```typescript
import { ComponentLogger } from '../utils/loggingUtils';

const MyComponent: React.FC = () => {
  const logger = new ComponentLogger('MyComponent');
  
  useEffect(() => {
    logger.logLifecycle('mount');
    return () => logger.logLifecycle('unmount');
  }, []);
  
  const handleClick = () => {
    logger.logUserAction('click', 'submit-button', { formValid: true });
  };
  
  const fetchData = async () => {
    const startTime = performance.now();
    try {
      const response = await api.getData();
      const duration = performance.now() - startTime;
      logger.logApiCall('GET', '/api/data', duration, response.status);
      return response;
    } catch (error) {
      const duration = performance.now() - startTime;
      logger.logApiCall('GET', '/api/data', duration, 0, error);
      throw error;
    }
  };
};
```

### Performance Monitoring

```typescript
import { withPerformanceLogging } from '../utils/loggingUtils';

// Wrap functions for automatic performance logging
const optimizedFunction = withPerformanceLogging(
  expensiveOperation,
  'DataProcessor',
  'processLargeDataset'
);

// Manual performance tracking
const logger = new ComponentLogger('VideoProcessor');
const endTimer = logger.logger.time('video-processing');
// ... processing logic
endTimer();
```

### API Service Integration

```typescript
import { apiLogger } from '../utils/loggingUtils';

class ApiService {
  async request(method: string, url: string, data?: any) {
    const startTime = performance.now();
    
    try {
      const response = await fetch(url, { method, body: data });
      const duration = performance.now() - startTime;
      
      apiLogger.logApiCall(method, url, duration, response.status);
      return response;
    } catch (error) {
      const duration = performance.now() - startTime;
      apiLogger.logApiCall(method, url, duration, 0, error);
      throw error;
    }
  }
}
```

## Migration Guide

### Step 1: Replace Console.log Statements

**Before:**
```typescript
console.log('User clicked button', buttonId);
console.log('API response:', response);
console.error('Error processing data:', error);
```

**After:**
```typescript
const logger = new ComponentLogger('ButtonComponent');
logger.logUserAction('click', 'button', { buttonId });
logger.logApiCall('GET', '/api/data', duration, response.status);
logger.logger.error('Error processing data', { action: 'data_processing' }, error);
```

### Step 2: Add Component Lifecycle Logging

```typescript
useEffect(() => {
  logger.logLifecycle('mount', { initialProps: props });
  return () => logger.logLifecycle('unmount');
}, []);
```

### Step 3: Performance Monitoring

```typescript
// Wrap expensive operations
const processData = withPerformanceLogging(
  originalProcessData,
  'DataProcessor',
  'processUserData'
);

// Manual timing for async operations
const processVideoAsync = async () => {
  const endTimer = logger.logger.time('video-processing-async');
  try {
    const result = await processVideo();
    return result;
  } finally {
    endTimer();
  }
};
```

## Remote Logging Setup

### Configuration
```bash
REACT_APP_LOG_ENDPOINT=https://your-logging-service.com/api/logs
REACT_APP_LOG_API_KEY=your-api-key
REACT_APP_LOG_REMOTE_ENABLED=true
REACT_APP_LOG_BATCH_SIZE=25
REACT_APP_LOG_FLUSH_INTERVAL=60000
```

### Implementation
The logger automatically batches logs and sends them to the remote endpoint when:
- Batch size is reached
- Flush interval expires
- Critical errors occur (immediate send)
- Application is unloading

## Performance Optimizations

### 1. Conditional Execution
```typescript
// Logs are only processed if level is enabled
if (shouldLog(LogLevel.DEBUG)) {
  // Expensive serialization only happens when needed
  logger.debug('Complex object', { data: expensiveSerialize(obj) });
}
```

### 2. Lazy Evaluation
```typescript
// Message formatting deferred until needed
logger.debug(() => `Expensive calculation: ${calculateExpensive()}`);
```

### 3. Memory Management
- Circular buffer for log entries
- Automatic buffer cleanup
- Memory usage monitoring

## Security Features

### Data Sanitization
- URL parameter removal
- Sensitive field redaction
- PII filtering

### Privacy Compliance
```typescript
const sanitizedData = loggingConfig.sanitizeData({
  email: 'user@example.com',
  password: 'secret',
  url: 'https://api.com/users?token=abc123'
});
// Result: { email: '[REDACTED]', password: '[REDACTED]', url: 'https://api.com/users' }
```

## Monitoring and Alerting

### Key Metrics
- Error rates by component
- Performance degradation
- Memory usage trends
- API response times

### Production Dashboards
- Real-time error tracking
- Performance trend analysis
- User journey insights
- System health monitoring

## Best Practices

### 1. Component Naming
```typescript
// Use consistent component names
const logger = new ComponentLogger('VideoPlayer');  // ✅ Good
const logger = new ComponentLogger('video_player'); // ❌ Inconsistent
```

### 2. Context Information
```typescript
// Include relevant context
logger.logUserAction('video_play', 'play-button', {
  videoId: 'abc123',
  timestamp: Date.now(),
  userAgent: navigator.userAgent.substring(0, 50)
});
```

### 3. Error Handling
```typescript
// Always include error objects for proper stack traces
try {
  riskyOperation();
} catch (error) {
  logger.logger.error('Operation failed', { action: 'risky_operation' }, error);
}
```

### 4. Performance Considerations
```typescript
// Use appropriate log levels
logger.logger.debug('Detailed debug info');  // Development only
logger.logger.info('User action');           // Important events
logger.logger.warn('Potential issue');       // Warning conditions
logger.logger.error('Critical error');       // Always logged
```

## Testing

### Unit Testing
```typescript
// Mock logger in tests
jest.mock('../utils/loggingUtils', () => ({
  ComponentLogger: jest.fn().mockImplementation(() => ({
    logger: {
      debug: jest.fn(),
      info: jest.fn(),
      warn: jest.fn(),
      error: jest.fn()
    },
    logUserAction: jest.fn(),
    logApiCall: jest.fn()
  }))
}));
```

### Integration Testing
- Verify log levels work correctly
- Test environment detection
- Validate remote logging batching
- Check performance impact

## Troubleshooting

### Common Issues
1. **Logs not appearing**: Check log level configuration
2. **Performance impact**: Verify production settings
3. **Remote logging fails**: Check endpoint configuration
4. **Memory leaks**: Monitor buffer sizes

### Debug Mode
Enable debug mode for additional logging:
```bash
localStorage.setItem('debug', 'true');
# or
?debug=true
```

## Future Enhancements

### Planned Features
- Structured query interface
- Advanced filtering
- Custom log formatters
- Integration with external APM tools
- Automated anomaly detection

### Roadmap
- Q1: Enhanced remote logging with retry logic
- Q2: Real-time log streaming
- Q3: Machine learning-based error prediction
- Q4: Advanced analytics dashboard

---

## Support

For questions or issues with the logging system:
1. Check the configuration in `/frontend/src/config/logging.config.ts`
2. Review component examples in `/frontend/src/utils/loggingUtils.ts`
3. Test with development environment settings
4. Consult this documentation for best practices