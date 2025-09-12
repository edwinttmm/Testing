# Development Tools Configuration

## Executive Summary

The AI Model Validation Platform provides a comprehensive development environment with sophisticated debugging tools, hot reload capabilities, advanced logging systems, comprehensive testing frameworks, and performance monitoring tools designed for optimal developer experience and productivity.

## Development Environment Configuration

### Environment Detection and Setup

```typescript
/**
 * Environment detection utility
 */
export class EnvironmentDetector {
  private detectEnvironment(): 'development' | 'production' | 'test' {
    if (process.env.NODE_ENV === 'test') return 'test';
    if (process.env.NODE_ENV === 'development') return 'development';
    if (process.env.NODE_ENV === 'production') return 'production';
    
    // Fallback detection
    if (typeof window !== 'undefined' && window.location) {
      if (window.location.hostname === 'localhost' || 
          window.location.hostname === '127.0.0.1' ||
          window.location.hostname.startsWith('192.168.')) {
        return 'development';
      }
    }
    
    return 'production';
  }
  
  private detectDebugMode(): boolean {
    // Check various debug indicators
    const envDebug = process.env.REACT_APP_DEBUG === 'true' || process.env.REACT_APP_LOG_LEVEL === 'debug';
    
    if (typeof window !== 'undefined') {
      const urlDebug = window.location?.search?.includes('debug=true') || window.location?.hash?.includes('debug');
      const storageDebug = localStorage?.getItem('debug') === 'true';
      return !!(envDebug || urlDebug || storageDebug);
    }
    
    return !!envDebug;
  }
}
```

**Environment Detection Features:**
- Automatic environment detection (development/production/test)
- Multiple debug mode triggers (env vars, URL params, localStorage)
- Hostname-based environment inference
- Fallback mechanisms for edge cases

## Hot Reload and Live Development

### Frontend Hot Reload Configuration (DISABLED)

```javascript
// CRACO Configuration - Hot Reload Prevention
if (env === 'development') {
  // CRITICAL: Remove ALL HMR-related plugins
  webpackConfig.plugins = webpackConfig.plugins.filter(plugin => {
    const pluginName = plugin.constructor.name;
    return !pluginName.includes('HotModuleReplacement') && 
           !pluginName.includes('HMR') &&
           !pluginName.includes('ReactRefresh');
  });
  
  // Ultra-aggressive WebSocket client elimination
  webpackConfig.plugins.push(
    new webpack.IgnorePlugin({
      resourceRegExp: /webpack-dev-server\/client/,
    }),
    new webpack.IgnorePlugin({
      resourceRegExp: /sockjs-client/,
    }),
    new webpack.IgnorePlugin({
      resourceRegExp: /webpack\/hot/,
    }),
    new webpack.IgnorePlugin({
      resourceRegExp: /react-refresh/,
    })
  );
}

// DevServer configuration
devServer: {
  host: 'localhost',
  port: 3000,
  compress: true,
  hot: false,        // Disabled for stability
  liveReload: false, // Disabled for stability
  allowedHosts: 'all',
  open: false,
  client: {
    webSocketTransport: 'ws',
    webSocketURL: 'auto://0.0.0.0:0/ws',
    overlay: false,
    logging: 'warn',
    progress: false,
    reconnect: true,
  }
}
```

**Hot Reload Strategy:**
- **Disabled by Design**: Hot reload is intentionally disabled for stability
- **Manual Refresh**: Developers must manually refresh for changes
- **Stability Focus**: Prevents chunk loading errors and HMR issues
- **WebSocket Blocking**: Aggressive prevention of webpack dev client

### Backend Live Reload

```python
# Backend development server configuration
if settings.api_reload and settings.app_environment == 'development':
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,          # Enable auto-reload
        reload_dirs=["./"],   # Watch current directory
        reload_excludes=[     # Exclude these paths
            "*.pyc",
            "__pycache__",
            "*.log",
            "uploads/*",
            "screenshots/*"
        ]
    )
```

**Backend Reload Features:**
- File system monitoring
- Automatic server restart on code changes
- Configurable watch directories
- Smart exclusions (logs, uploads, cache files)

## Logging System

### Comprehensive Logging Configuration

```typescript
export const createLoggingConfig = (): LoggingConfig => {
  const env = EnvironmentDetector.getInstance();
  
  const baseConfig: LoggingConfig = {
    defaultLevel: env.isDevelopment ? LogLevel.DEBUG : LogLevel.WARN,
    enabledCategories: env.isDevelopment ? ['*'] : ['error', 'warn'],
    componentLevels: {
      'api': env.isDevelopment ? LogLevel.DEBUG : LogLevel.ERROR,
      'websocket': env.isDevelopment ? LogLevel.INFO : LogLevel.ERROR,
      'auth': LogLevel.WARN,
      'router': env.isDevelopment ? LogLevel.INFO : LogLevel.ERROR,
      'performance': env.isDevelopment ? LogLevel.DEBUG : LogLevel.NONE,
      'video': env.isDevelopment ? LogLevel.DEBUG : LogLevel.WARN,
      'annotation': env.isDevelopment ? LogLevel.DEBUG : LogLevel.WARN,
      'detection': env.isDevelopment ? LogLevel.INFO : LogLevel.ERROR
    },
    
    development: {
      showColors: true,
      showTimestamps: true,
      showPerformance: true,
      bufferSize: 50
    },
    
    performance: {
      enabled: env.isDevelopment || env.isDebugEnabled,
      sampleRate: env.isDevelopment ? 1.0 : 0.1,
      memoryTracking: env.isDevelopment,
      slowThreshold: 1000 // 1 second
    },
    
    features: {
      apiCalls: env.isDevelopment || env.isDebugEnabled,
      userActions: env.isDevelopment,
      errorBoundaries: true,
      performanceMetrics: env.isDevelopment || env.isDebugEnabled,
      websocketEvents: env.isDevelopment,
      routeChanges: env.isDevelopment,
      componentLifecycle: false, // Only enable for specific debugging
      stateChanges: false // Only enable for specific debugging
    }
  };
}
```

### Development Logging Features

**Component-Level Logging:**
- **API Calls**: Debug level logging for all API interactions
- **WebSocket Events**: Info level logging for real-time communications
- **Performance Metrics**: Debug level performance tracking
- **Video Processing**: Debug level video handling logs
- **Authentication**: Warning level security logs
- **Router**: Info level navigation logs

**Visual Enhancements:**
- **Color-coded** log levels (error: red, warn: yellow, info: blue)
- **Timestamps** on all log entries
- **Performance data** embedded in relevant logs
- **Component categorization** for filtered viewing

**Privacy and Security:**
```typescript
privacy: {
  sanitizeUrls: env.isProduction,
  sanitizeUserData: true,
  excludeFields: ['password', 'token', 'secret', 'key', 'auth'],
  hashSensitiveData: env.isProduction
}
```

## Testing Framework

### Pytest Configuration

```ini
[tool:pytest]
# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output formatting
addopts = 
    -v
    --tb=short
    --strict-markers
    --strict-config
    --color=yes

# Markers
markers =
    sequential: Sequential video processing tests
    frontend: Frontend integration tests  
    automation: End-to-end automation tests
    specific: Specific video files tests
    workflow: Workflow validation tests
    integration: Integration tests
    performance: Performance tests
    slow: Tests that take a long time to run

# Test timeout (in seconds)
timeout = 300

# Async support
asyncio_mode = auto

# Minimum version
minversion = 6.0
```

### Frontend Testing Configuration

```json
{
  "scripts": {
    // Testing Scripts
    "test": "craco test",
    "test:docker": "craco test --watchAll=false --passWithNoTests",
    "test:coverage": "craco test --coverage --watchAll=false",
    
    // Specialized Test Scripts
    "test:labjack": "jest tests/labjack-*.test.ts --verbose --detectOpenHandles --forceExit",
    "test:labjack-api": "jest tests/labjack-api-validation.test.ts --verbose",
    "test:labjack-integration": "jest tests/labjack-hardware-integration.test.ts --verbose",
    "test:labjack-legacy": "jest tests/labjack-integration-validation.test.ts --verbose",
    "test:labjack-all": "node -r ts-node/register tests/run-labjack-tests.ts",
    
    "test:video": "jest tests/video-*.test.tsx --verbose --detectOpenHandles --forceExit --testTimeout=30000",
    "test:video-comprehensive": "jest tests/video-playback-comprehensive.test.tsx --verbose --coverage",
    "test:video-browser-compat": "jest tests/video-browser-compatibility.test.tsx --verbose",
    "test:video-performance": "jest tests/video-performance-benchmarks.test.tsx --verbose",
    "test:video-labjack": "jest tests/video-labjack-integration.test.tsx --verbose"
  }
}
```

**Testing Features:**
- **Component-specific test suites**: LabJack, Video, API, Integration
- **Performance benchmarking**: Video playback, browser compatibility
- **Timeout management**: 30-second timeouts for complex tests
- **Coverage reporting**: Comprehensive test coverage analysis
- **Parallel execution**: Multiple test runners for different categories

### Test Markers and Categories

```python
# Test Markers
@pytest.mark.sequential      # Sequential video processing tests
@pytest.mark.frontend        # Frontend integration tests  
@pytest.mark.automation      # End-to-end automation tests
@pytest.mark.specific        # Specific video files tests
@pytest.mark.workflow        # Workflow validation tests
@pytest.mark.integration     # Integration tests
@pytest.mark.performance     # Performance tests
@pytest.mark.slow           # Tests that take a long time to run
```

## Debugging Tools

### Browser Developer Tools Integration

```typescript
// Global error handling
if (typeof window !== 'undefined') {
  window.addEventListener('error', (event) => {
    const logger = LoggerFactory.getInstance().getLogger('global');
    logger.error('Uncaught error', {
      action: 'global_error',
      metadata: {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno
      }
    }, event.error);
  });
  
  window.addEventListener('unhandledrejection', (event) => {
    const logger = LoggerFactory.getInstance().getLogger('global');
    logger.error('Unhandled promise rejection', {
      action: 'promise_rejection',
      metadata: {
        reason: event.reason
      }
    });
  });
}
```

### Debug Mode Activation

```typescript
/**
 * Set debug mode dynamically
 */
public setDebugMode(enabled: boolean): void {
  if (enabled) {
    this._config.defaultLevel = LogLevel.DEBUG;
    this._config.enabledCategories = ['*'];
    this._config.performance.enabled = true;
  } else {
    const env = EnvironmentDetector.getInstance();
    this._config.defaultLevel = env.isDevelopment ? LogLevel.INFO : LogLevel.WARN;
    this._config.enabledCategories = env.isDevelopment ? ['*'] : ['error', 'warn'];
    this._config.performance.enabled = env.isDevelopment;
  }
  this.applyConfiguration();
}
```

**Debug Activation Methods:**
1. **Environment Variable**: `REACT_APP_DEBUG=true`
2. **URL Parameter**: `?debug=true`
3. **Local Storage**: `localStorage.setItem('debug', 'true')`
4. **Hash Parameter**: `#debug`

### Development Console Features

```javascript
// Development console enhancements
if (process.env.NODE_ENV === 'development') {
  // Expose debugging utilities
  window.__DEBUG__ = {
    logger: LoggerFactory.getInstance(),
    config: LoggingConfigManager.getInstance(),
    environment: EnvironmentDetector.getInstance(),
    
    // Helper functions
    enableDebug: () => LoggingConfigManager.getInstance().setDebugMode(true),
    disableDebug: () => LoggingConfigManager.getInstance().setDebugMode(false),
    showPerformance: () => LoggingConfigManager.getInstance().setPerformanceMonitoring(true),
    hidePerformance: () => LoggingConfigManager.getInstance().setPerformanceMonitoring(false),
    
    // Component inspection
    inspectComponent: (name) => LoggerFactory.getInstance().getLogger(name),
    listCategories: () => LoggingConfigManager.getInstance().getConfig().enabledCategories,
    
    // Memory debugging
    gc: () => window.gc && window.gc(),
    memory: () => (performance as any).memory
  };
  
  console.info('🔧 Debug utilities available at window.__DEBUG__');
}
```

## Performance Monitoring

### Real-time Performance Tracking

```typescript
performance: {
  enabled: env.isDevelopment || env.isDebugEnabled,
  sampleRate: env.isDevelopment ? 1.0 : 0.1,
  memoryTracking: env.isDevelopment,
  slowThreshold: 1000 // milliseconds
}

/**
 * Should log performance data for this sample
 */
public shouldLogPerformance(): boolean {
  return this._config.performance.enabled && 
         Math.random() < this._config.performance.sampleRate;
}
```

### Memory Usage Monitoring

```typescript
// Memory tracking utilities
const trackMemoryUsage = () => {
  if (typeof performance !== 'undefined' && (performance as any).memory) {
    const memory = (performance as any).memory;
    return {
      usedJSHeapSize: memory.usedJSHeapSize,
      totalJSHeapSize: memory.totalJSHeapSize,
      jsHeapSizeLimit: memory.jsHeapSizeLimit,
      percentage: (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100
    };
  }
  return null;
};
```

### Component Performance Profiling

```typescript
// Performance profiler for React components
export const withPerformanceMonitoring = <P extends object>(
  Component: React.ComponentType<P>,
  componentName: string
) => {
  return React.memo((props: P) => {
    const startTime = performance.now();
    
    React.useEffect(() => {
      const endTime = performance.now();
      const renderTime = endTime - startTime;
      
      if (renderTime > loggingConfig.getPerformanceConfig().slowThreshold) {
        const logger = LoggerFactory.getInstance().getLogger('performance');
        logger.warn('Slow component render detected', {
          action: 'slow_render',
          metadata: {
            component: componentName,
            renderTime: renderTime,
            threshold: loggingConfig.getPerformanceConfig().slowThreshold
          }
        });
      }
    });
    
    return <Component {...props} />;
  });
};
```

## Code Quality Tools

### ESLint Configuration

```json
{
  "eslintConfig": {
    "extends": [
      "react-app",
      "react-app/jest"
    ],
    "rules": {
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          "argsIgnorePattern": "^_"
        }
      ],
      "no-console": [
        "warn",
        {
          "allow": [
            "error",
            "warn",
            "info"
          ]
        }
      ],
      "prefer-const": "warn",
      "no-debugger": "warn"
    },
    "overrides": [
      {
        "files": [
          "src/**/*.{ts,tsx}"
        ],
        "rules": {
          "no-console": [
            "warn",
            {
              "allow": [
                "error",
                "warn",
                "info"
              ]
            }
          ]
        }
      }
    ]
  }
}
```

### Linting Scripts

```json
{
  "scripts": {
    "lint": "eslint src --ext .ts,.tsx --max-warnings 0",
    "lint:dev": "eslint src --ext .ts,.tsx --max-warnings 50",
    "lint:prod": "eslint src --ext .ts,.tsx -c .eslintrc.production.js --max-warnings 0 --ignore-pattern '**/*.test.*' --ignore-pattern '**/*.spec.*'",
    "lint:fix": "eslint src --ext .ts,.tsx --fix",
    "lint:analyze": "npm run lint:dev && npm run logger-analysis",
    "logger-analysis": "node scripts/logger-usage-check.js"
  }
}
```

**Linting Features:**
- **Development Mode**: More permissive (50 warnings allowed)
- **Production Mode**: Strict (0 warnings allowed)
- **Test Exclusions**: Tests excluded from production linting
- **Auto-fix**: Automatic code formatting fixes
- **Custom Analysis**: Logger usage analysis

### TypeScript Configuration

```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": [
      "dom",
      "dom.iterable",
      "es6"
    ],
    "allowJs": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "noFallthroughCasesInSwitch": true,
    "module": "esnext",
    "moduleResolution": "node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  }
}
```

**TypeScript Scripts:**
```json
{
  "typecheck": "tsc --noEmit --project .",
  "typecheck:tests": "tsc --noEmit --project tsconfig.test.json"
}
```

## Development Server Configuration

### Frontend Development Server

```javascript
// CRACO DevServer Configuration
devServer: {
  host: 'localhost',
  port: 3000,
  compress: true,
  hot: false,        // Disabled for stability
  liveReload: false, // Disabled for stability
  allowedHosts: 'all',
  open: false,       // Don't auto-open browser
  
  client: {
    webSocketTransport: 'ws',
    webSocketURL: 'auto://0.0.0.0:0/ws',
    overlay: false,    // Disable error overlay
    logging: 'warn',   // Minimal logging
    progress: false,   // No progress reporting
    reconnect: true,   // Auto-reconnect WebSocket
  },
  
  // Static file serving
  static: {
    directory: path.resolve(__dirname, 'public'),
    publicPath: '/',
    serveIndex: false,
    watch: {
      ignored: ['**/node_modules/**', '**/.git/**'],
      usePolling: false,
    }
  },
  
  // History API fallback
  historyApiFallback: {
    disableDotRule: true,
    index: '/index.html',
    rewrites: [
      { from: /^\/static\/.*$/, to: function(context) {
        return context.parsedUrl.pathname;
      }},
      { from: /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|json)$/, to: function(context) {
        return context.parsedUrl.pathname;
      }}
    ]
  }
}
```

### Backend Development Server

```python
# FastAPI development configuration
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        reload_dirs=["./"] if settings.api_reload else None,
        reload_excludes=[
            "*.pyc",
            "__pycache__",
            "*.log",
            "uploads/*",
            "screenshots/*",
            "venv/*",
            ".git/*"
        ],
        log_level=settings.log_level.lower(),
        access_log=True,
        server_header=False,
        date_header=False
    )
```

## Database Development Tools

### Database Migrations

```python
# Alembic configuration for development
from alembic import command
from alembic.config import Config

def run_migrations():
    """Run database migrations in development"""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

def create_migration(message: str):
    """Create new migration"""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, message=message, autogenerate=True)
```

### Database Inspection Tools

```python
# Development database utilities
@app.get("/api/dev/db/inspect")
async def inspect_database(db: Session = Depends(get_db)):
    """Inspect database schema (development only)"""
    if not settings.api_debug:
        raise HTTPException(status_code=404, detail="Not available in production")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    schema_info = {}
    
    for table in tables:
        columns = inspector.get_columns(table)
        schema_info[table] = {
            'columns': [{'name': col['name'], 'type': str(col['type'])} for col in columns],
            'row_count': db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        }
    
    return schema_info
```

## API Development Tools

### API Documentation

```python
# Enhanced OpenAPI configuration
app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.api_debug,
    docs_url="/api/docs" if settings.api_debug else None,
    redoc_url="/api/redoc" if settings.api_debug else None,
    openapi_url="/api/openapi.json" if settings.api_debug else None
)
```

### Request/Response Logging

```python
# Development request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    if settings.api_debug:
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url}")
        
        response = await call_next(request)
        
        # Log response
        duration = time.time() - start_time
        logger.info(f"Response: {response.status_code} ({duration:.3f}s)")
        
        return response
    
    return await call_next(request)
```

## Error Handling and Recovery

### Development Error Pages

```typescript
// Error boundary for development
export class DevelopmentErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error; errorInfo?: React.ErrorInfo }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ error, errorInfo });
    
    // Log to development console
    console.group('🚨 React Error Boundary');
    console.error('Error:', error);
    console.error('Component Stack:', errorInfo.componentStack);
    console.groupEnd();
    
    // Log to logging system
    const logger = LoggerFactory.getInstance().getLogger('error-boundary');
    logger.error('React error boundary triggered', {
      action: 'error_boundary',
      metadata: {
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack
      }
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', border: '1px solid red', margin: '10px' }}>
          <h2>🚨 Development Error</h2>
          <details>
            <summary>Error Details</summary>
            <pre>{this.state.error?.stack}</pre>
            <pre>{this.state.errorInfo?.componentStack}</pre>
          </details>
          <button onClick={() => window.location.reload()}>
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

## Development Workflow Integration

### Git Hooks Integration

```json
{
  "husky": {
    "hooks": {
      "pre-commit": "npm run lint:prod && npm run typecheck",
      "pre-push": "npm run test:coverage"
    }
  }
}
```

### Development Scripts

```json
{
  "scripts": {
    "dev": "npm run start:dev",
    "dev:debug": "REACT_APP_DEBUG=true npm run start:dev",
    "dev:performance": "REACT_APP_LOG_LEVEL=debug npm run start:dev",
    "dev:clean": "rm -rf node_modules/.cache && npm start",
    "dev:analyze": "npm run build && npx webpack-bundle-analyzer build/static/js/*.js"
  }
}
```

## Monitoring and Analytics

### Development Analytics

```typescript
// Development-only analytics
if (process.env.NODE_ENV === 'development') {
  // Track component render times
  const originalCreateElement = React.createElement;
  React.createElement = function(type, props, ...children) {
    if (typeof type === 'function' && type.name) {
      const start = performance.now();
      const element = originalCreateElement.call(this, type, props, ...children);
      const end = performance.now();
      
      if (end - start > 1) { // Log slow renders
        console.log(`Slow render: ${type.name} took ${(end - start).toFixed(2)}ms`);
      }
      
      return element;
    }
    
    return originalCreateElement.call(this, type, props, ...children);
  };
}
```

### Performance Metrics Collection

```typescript
// Development performance monitoring
export const DevPerformanceMonitor = {
  trackPageLoad: () => {
    if (typeof window !== 'undefined' && window.performance) {
      window.addEventListener('load', () => {
        const timing = window.performance.timing;
        const loadTime = timing.loadEventEnd - timing.navigationStart;
        
        console.log(`Page load time: ${loadTime}ms`);
        
        const logger = LoggerFactory.getInstance().getLogger('performance');
        logger.info('Page load completed', {
          action: 'page_load',
          metadata: {
            loadTime,
            domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
            firstPaint: timing.responseStart - timing.navigationStart
          }
        });
      });
    }
  },
  
  trackUserInteraction: (action: string, element: string) => {
    const logger = LoggerFactory.getInstance().getLogger('user-interaction');
    logger.debug('User interaction', {
      action: 'user_interaction',
      metadata: { action, element }
    });
  }
};
```

This comprehensive development tools configuration provides a robust, feature-rich development environment optimized for productivity, debugging, and quality assurance.