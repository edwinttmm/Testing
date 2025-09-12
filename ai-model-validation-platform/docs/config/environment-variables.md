# Environment Variables Configuration Analysis

## Executive Summary

The AI Model Validation Platform uses a comprehensive environment variable system with multiple precedence levels, unified configuration across backend/frontend, and production-ready security settings.

## Environment Structure

### Configuration Hierarchy
1. **VRU_*** (High Priority - Unified naming convention)
2. **AIVALIDATION_*** (Medium Priority - Application specific)  
3. **Standard names** (Low Priority - Generic)
4. **Default values** (Fallback)

## Core Environment Files

### 1. Production Environment (.env.production.secure)
```bash
# Security Configuration (CRITICAL)
VRU_SECRET_KEY=kXg1JAQpPefZZxFaA6X1a_HeVdyICwHZQXCFzFro4tU
VRU_JWT_SECRET_KEY=kXg1JAQpPefZZxFaA6X1a_HeVdyICwHZQXCFzFro4tU

# Database Configuration
VRU_DATABASE_URL=postgresql://prod_user:CHANGE_ME@localhost:5432/ai_validation_prod
VRU_DATABASE_NAME=ai_validation_prod
VRU_DATABASE_USER=prod_user
VRU_DATABASE_PASSWORD=CHANGE_ME

# Redis Configuration
VRU_REDIS_URL=redis://:CHANGE_ME@localhost:6379/0
VRU_REDIS_PASSWORD=CHANGE_ME

# Environment Settings
APP_ENV=production
NODE_ENV=production

# CORS Security
AIVALIDATION_CORS_ORIGINS=["https://yourdomain.com"]

# SSL/Security Configuration
AIVALIDATION_SSL_ENABLED=true
AIVALIDATION_HSTS_ENABLED=true
AIVALIDATION_CSP_ENABLED=true

# Rate Limiting
AIVALIDATION_RATE_LIMIT_ENABLED=true
AIVALIDATION_MAX_REQUESTS_PER_MINUTE=100

# Session Configuration
JWT_EXPIRE_MINUTES=30
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Performance
AIVALIDATION_DATABASE_POOL_SIZE=20
AIVALIDATION_DATABASE_MAX_OVERFLOW=30
```

### 2. Development Environment (.env.development.backup)
```bash
# Environment Settings
ENVIRONMENT=development
NODE_ENV=development
APP_ENV=development

# Database Configuration
DATABASE_TYPE=sqlite
DATABASE_URL=sqlite:///./dev_database.db
AIVALIDATION_DATABASE_URL=sqlite:///./dev_database.db

# Redis Configuration
REDIS_PASSWORD=dev_redis_password
REDIS_URL=redis://:dev_redis_password@redis:6379
AIVALIDATION_REDIS_URL=redis://:dev_redis_password@redis:6379

# API Configuration
AIVALIDATION_SECRET_KEY=development-secret-key-not-for-production
AIVALIDATION_API_HOST=0.0.0.0
AIVALIDATION_API_PORT=8000
API_PORT=8000

# CORS Configuration (Development)
AIVALIDATION_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://0.0.0.0:3000"]
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://0.0.0.0:3000"]

# Frontend Configuration
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_SOCKETIO_URL=http://localhost:8001
REACT_APP_VIDEO_BASE_URL=http://localhost:8000
REACT_APP_ENVIRONMENT=development
REACT_APP_DEBUG=true
REACT_APP_LOG_LEVEL=debug

# Performance Settings
UVICORN_WORKERS=1
UVICORN_WORKER_TIMEOUT=300

# Docker Development
AIVALIDATION_DOCKER_MODE=true
DOCKER=true
CI=false

# Logging
LOG_LEVEL=DEBUG
GENERATE_SOURCEMAP=true

# Health Checks
HEALTH_CHECK_INTERVAL=15s
HEALTH_CHECK_TIMEOUT=5s
HEALTH_CHECK_RETRIES=2
HEALTH_CHECK_START_PERIOD=30s

# Resource Limits
BACKEND_CPU_LIMIT=1.0
BACKEND_MEMORY_LIMIT=1G
FRONTEND_CPU_LIMIT=0.5
FRONTEND_MEMORY_LIMIT=512M
```

## Backend Configuration Variables (config.py)

### Database Configuration
- **VRU_DATABASE_URL** / DATABASE_URL / AIVALIDATION_DATABASE_URL
  - Default: `sqlite:///./dev_database.db`
  - Production: PostgreSQL connection string
  - Purpose: Primary database connection

- **AIVALIDATION_TEST_DATABASE_URL**
  - Default: `sqlite:///./test.db`
  - Purpose: Testing database isolation

- **AIVALIDATION_DATABASE_POOL_SIZE**
  - Default: 10
  - Production: 20
  - Purpose: Connection pool size

- **AIVALIDATION_DATABASE_MAX_OVERFLOW**
  - Default: 20
  - Production: 30
  - Purpose: Additional connections beyond pool

- **DATABASE_SSLMODE**
  - Default: `prefer`
  - Purpose: PostgreSQL SSL mode

### API Configuration
- **AIVALIDATION_API_HOST** / API_HOST
  - Default: `0.0.0.0`
  - Purpose: Server bind address

- **AIVALIDATION_API_PORT** / API_PORT
  - Default: 8000
  - Purpose: Server port

- **AIVALIDATION_API_DEBUG**
  - Default: false
  - Purpose: Enable debug mode

- **AIVALIDATION_API_BASE_URL**
  - Default: `http://localhost:{port}`
  - Purpose: Base URL for API references

### Security Configuration
- **VRU_SECRET_KEY** / AIVALIDATION_SECRET_KEY / SECRET_KEY
  - Default: `INSECURE-DEFAULT-CHANGE-ME`
  - **CRITICAL**: Must be changed in production
  - Purpose: Application secret key for signing

- **VRU_JWT_SECRET_KEY** / AIVALIDATION_JWT_SECRET_KEY / JWT_SECRET_KEY
  - Default: Uses secret_key value
  - Purpose: JWT token signing

- **AIVALIDATION_JWT_ALGORITHM**
  - Default: `HS256`
  - Purpose: JWT signing algorithm

- **ACCESS_TOKEN_EXPIRE_MINUTES**
  - Default: 30
  - Purpose: JWT token expiration

### CORS Configuration
- **AIVALIDATION_CORS_ORIGINS**
  - Default: `["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8001", "http://127.0.0.1:8001"]`
  - Production: Restricted to specific domains
  - Purpose: Cross-origin request permissions

### Redis Configuration
- **VRU_REDIS_URL** / AIVALIDATION_REDIS_URL / REDIS_URL
  - Default: None (Redis optional)
  - Purpose: Redis connection string

- **VRU_REDIS_PASSWORD** / AIVALIDATION_REDIS_PASSWORD / REDIS_PASSWORD
  - Default: None
  - Purpose: Redis authentication

### File Upload Configuration
- **AIVALIDATION_MAX_FILE_SIZE** / MAX_UPLOAD_SIZE
  - Default: 100MB (100 * 1024 * 1024)
  - Purpose: Maximum file upload size

- **AIVALIDATION_ALLOWED_VIDEO_EXTENSIONS**
  - Default: `.mp4,.avi,.mov,.mkv,.webm`
  - Purpose: Allowed video file types

- **AIVALIDATION_UPLOAD_DIRECTORY** / UPLOAD_DIRECTORY
  - Default: `uploads`
  - Purpose: File upload storage directory

### Logging Configuration
- **AIVALIDATION_LOG_LEVEL** / LOG_LEVEL
  - Default: `INFO`
  - Values: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Purpose: Application logging level

- **AIVALIDATION_LOG_FILE**
  - Default: None (console logging)
  - Purpose: Log file path

### Security Headers
- **AIVALIDATION_SECURITY_HEADERS_ENABLED**
  - Default: true
  - Purpose: Enable security headers

- **AIVALIDATION_HSTS_ENABLED**
  - Default: false (true in production)
  - Purpose: HTTP Strict Transport Security

- **AIVALIDATION_CSP_ENABLED**
  - Default: true
  - Purpose: Content Security Policy

- **AIVALIDATION_SSL_ENABLED**
  - Default: false (true in production)
  - Purpose: SSL/TLS configuration

### Feature Flags
- **AIVALIDATION_ENABLE_GROUND_TRUTH_SERVICE**
  - Default: false
  - Purpose: Enable ground truth processing

- **AIVALIDATION_ENABLE_VALIDATION_SERVICE**
  - Default: false
  - Purpose: Enable validation service

- **AIVALIDATION_ENABLE_ASYNC_PROCESSING**
  - Default: false
  - Purpose: Enable asynchronous processing

- **AIVALIDATION_ENABLE_CACHING**
  - Default: false
  - Purpose: Enable caching layer

### Docker Configuration
- **AIVALIDATION_DOCKER_MODE**
  - Default: false
  - Purpose: Docker deployment mode

- **AIVALIDATION_CONTAINER_NAME**
  - Default: `ai-validation-backend`
  - Purpose: Container identification

### Health Check Configuration
- **AIVALIDATION_HEALTH_CHECK_ENABLED**
  - Default: true
  - Purpose: Enable health check endpoint

- **AIVALIDATION_METRICS_ENABLED**
  - Default: false
  - Purpose: Enable metrics collection

## Frontend Environment Variables

### API Endpoints
- **REACT_APP_API_URL**
  - Default: `http://localhost:8000`
  - Purpose: Backend API base URL

- **REACT_APP_WS_URL**
  - Default: `ws://localhost:8000`
  - Purpose: WebSocket connection URL

- **REACT_APP_SOCKETIO_URL**
  - Default: `http://localhost:8001`
  - Purpose: Socket.IO connection URL

- **REACT_APP_VIDEO_BASE_URL**
  - Default: `http://localhost:8000`
  - Purpose: Video serving base URL

### Environment Configuration
- **REACT_APP_ENVIRONMENT**
  - Default: `development`
  - Values: development, production
  - Purpose: Frontend environment mode

- **REACT_APP_DEBUG**
  - Default: true (development)
  - Purpose: Enable debug features

- **REACT_APP_LOG_LEVEL**
  - Default: `debug` (development)
  - Purpose: Frontend logging level

### Build Configuration
- **NODE_ENV**
  - Default: `development`
  - Values: development, production
  - Purpose: Node.js environment

- **GENERATE_SOURCEMAP**
  - Default: false (production), true (development)
  - Purpose: Generate source maps for debugging

- **CI**
  - Default: false
  - Purpose: Continuous Integration mode

- **DOCKER**
  - Default: true (when in container)
  - Purpose: Docker deployment mode

## Docker Compose Environment Integration

### Database Service (postgres)
```yaml
environment:
  POSTGRES_DB: ${VRU_DATABASE_NAME}
  POSTGRES_USER: ${VRU_DATABASE_USER}
  POSTGRES_PASSWORD: ${VRU_DATABASE_PASSWORD}
```

### Redis Service
```yaml
command: redis-server --requirepass ${VRU_REDIS_PASSWORD} --appendonly yes
```

### Backend Service
```yaml
environment:
  # Security
  - AIVALIDATION_SECRET_KEY=${VRU_SECRET_KEY}
  - SECRET_KEY=${VRU_SECRET_KEY}
  # Database
  - AIVALIDATION_DATABASE_URL=${VRU_DATABASE_URL}
  - DATABASE_URL=${VRU_DATABASE_URL}
  # Redis
  - AIVALIDATION_REDIS_URL=${VRU_REDIS_URL}
  - REDIS_URL=${VRU_REDIS_URL}
  # API Configuration
  - AIVALIDATION_API_PORT=${VRU_API_PORT}
  - AIVALIDATION_API_HOST=${VRU_API_HOST}
  # CORS
  - AIVALIDATION_CORS_ORIGINS=${VRU_CORS_ORIGINS}
  - ALLOWED_ORIGINS=${VRU_CORS_ORIGINS}
```

### Frontend Service
```yaml
environment:
  - REACT_APP_API_URL=${REACT_APP_API_URL}
  - REACT_APP_WS_URL=${REACT_APP_WS_URL}
  - REACT_APP_ML_ENGINE_URL=${REACT_APP_ML_ENGINE_URL}
  - REACT_APP_VIDEO_BASE_URL=${REACT_APP_VIDEO_BASE_URL}
  - REACT_APP_ENVIRONMENT=${REACT_APP_ENVIRONMENT}
  - REACT_APP_DEBUG=${REACT_APP_DEBUG}
  - NODE_ENV=${NODE_ENV}
  - GENERATE_SOURCEMAP=${GENERATE_SOURCEMAP}
```

## Security Implications

### Critical Security Variables
1. **VRU_SECRET_KEY**: Application signing key - MUST be secure in production
2. **VRU_JWT_SECRET_KEY**: JWT token signing - MUST be different from application key
3. **VRU_DATABASE_PASSWORD**: Database access - MUST be complex
4. **VRU_REDIS_PASSWORD**: Redis access - MUST be secure

### Production Security Checklist
- [ ] Secret keys are 32+ characters and cryptographically secure
- [ ] Database passwords are complex and unique
- [ ] CORS origins are restricted to actual domains
- [ ] SSL/TLS is enabled (AIVALIDATION_SSL_ENABLED=true)
- [ ] HSTS is enabled (AIVALIDATION_HSTS_ENABLED=true)
- [ ] Rate limiting is enabled (AIVALIDATION_RATE_LIMIT_ENABLED=true)
- [ ] Security headers are enabled (AIVALIDATION_SECURITY_HEADERS_ENABLED=true)

## Performance Configuration

### Database Performance
- Connection pooling: AIVALIDATION_DATABASE_POOL_SIZE=20
- Overflow connections: AIVALIDATION_DATABASE_MAX_OVERFLOW=30
- SSL mode: DATABASE_SSLMODE=prefer

### Application Performance
- Worker processes: UVICORN_WORKERS=1 (dev), higher in production
- Worker timeout: UVICORN_WORKER_TIMEOUT=300
- Request timeout: 30 seconds (hardcoded)

### Frontend Performance
- Source maps: GENERATE_SOURCEMAP=false (production)
- Memory limit: NODE_OPTIONS=--max_old_space_size=4096
- Bundle optimization: Enabled in production builds

## Troubleshooting Guide

### Common Issues

1. **Database Connection Issues**
   - Check VRU_DATABASE_URL format
   - Verify database service is running
   - Confirm credentials are correct

2. **CORS Errors**
   - Verify AIVALIDATION_CORS_ORIGINS includes frontend URL
   - Check protocol matching (http/https)
   - Confirm port numbers are correct

3. **Authentication Issues**
   - Ensure VRU_SECRET_KEY is set and secure
   - Check JWT expiration settings
   - Verify Redis connection for session storage

4. **File Upload Issues**
   - Check AIVALIDATION_MAX_FILE_SIZE setting
   - Verify upload directory permissions
   - Confirm allowed extensions configuration

5. **SSL/TLS Issues**
   - Verify certificate file paths
   - Check SSL enabled flag
   - Confirm HTTPS redirect settings

### Environment Validation
The system includes built-in validation that checks:
- Secret key security
- Database configuration
- CORS settings
- SSL/TLS configuration in production
- File size limits
- Log level validity

## Best Practices

1. **Development**
   - Use SQLite for local development
   - Enable debug logging
   - Use insecure defaults (clearly marked)
   - Enable source maps

2. **Production**
   - Use PostgreSQL for database
   - Implement secure secrets management
   - Enable SSL/TLS
   - Restrict CORS origins
   - Disable debug features
   - Enable security headers

3. **Environment Management**
   - Use .env files for local development
   - Use container environment variables for deployment
   - Never commit .env files with real secrets
   - Use environment-specific configurations

4. **Monitoring**
   - Enable health checks
   - Configure appropriate log levels
   - Set up metrics collection
   - Monitor database connections