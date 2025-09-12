# SPARC Root Cause Analysis: System Health Degradation

## Executive Summary

The AI Model Validation Platform is experiencing **CRITICAL** system degradation due to Docker/local development environment configuration mismatches. This analysis applies SPARC methodology to identify root causes and provide structured recommendations.

## 1. SPECIFICATION Phase

### Problem Definition
- **System Status**: NETWORK DEGRADED + FILESYSTEM DEGRADED
- **Primary Issue**: Services hardcoded for Docker containerized environment but running in local development
- **Impact**: Complete failure of health checks, Redis connectivity, and file system operations

### Requirements Analysis
1. **Environment Detection**: Dynamic detection of Docker vs local execution
2. **Configuration Adaptation**: Environment-aware service configuration
3. **Graceful Degradation**: Fallback mechanisms for service unavailability
4. **Path Resolution**: Dynamic path mapping based on runtime environment

## 2. PSEUDOCODE Phase

### Environment Detection Algorithm
```pseudocode
FUNCTION detect_environment():
    IF env_var("AIVALIDATION_DOCKER_MODE") EXISTS:
        RETURN parse_boolean(env_var("AIVALIDATION_DOCKER_MODE"))
    
    TRY:
        resolve_hostname("redis")
        resolve_hostname("postgres") 
        RETURN true  // Docker environment detected
    CATCH DNS_ERROR:
        RETURN false  // Local development environment
END FUNCTION

FUNCTION get_environment_config(is_docker):
    IF is_docker:
        RETURN {
            "redis_url": "redis://redis:6379",
            "postgres_url": "postgresql://user:pass@postgres:5432/db",
            "base_path": "/app"
        }
    ELSE:
        RETURN {
            "redis_url": "redis://localhost:6379", 
            "postgres_url": "sqlite:///./dev_database.db",
            "base_path": "."
        }
END FUNCTION
```

### Service Initialization Pattern
```pseudocode
FUNCTION initialize_services():
    environment = detect_environment()
    config = get_environment_config(environment.is_docker)
    
    FOR each_service IN [database, redis, filesystem]:
        TRY:
            initialize_service(each_service, config)
        CATCH CONNECTION_ERROR:
            log_warning("Service unavailable, using fallback")
            initialize_fallback_service(each_service)
END FUNCTION
```

## 3. ARCHITECTURE Phase

### Current Architecture Issues
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Health Check  │───▶│  Hardcoded URLs  │───▶│  DNS Failures   │
│   health_check  │    │  redis:6379      │    │  Connection     │
│                 │    │  postgres:5432   │    │  Timeouts       │
└─────────────────┘    └──────────────────┘    └─────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   File Systems  │───▶│  Hardcoded Paths │───▶│  Permission     │
│   Services      │    │  /app/uploads    │    │  Denied Errors  │
│                 │    │  /app/models     │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Proposed Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Environment     │───▶│ Configuration    │───▶│ Service         │
│ Detector        │    │ Factory          │    │ Initializers    │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Docker: redis   │    │ Local: localhost │    │ Graceful        │
│ /app paths      │    │ ./ paths         │    │ Degradation     │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Component Design

#### 1. Environment Detection Service
- **Purpose**: Detect runtime environment (Docker vs local)
- **Methods**: DNS resolution test, environment variables, filesystem indicators
- **Location**: `src/core/environment_detector.py`

#### 2. Configuration Factory
- **Purpose**: Provide environment-appropriate configurations  
- **Inputs**: Environment detection result
- **Outputs**: Connection strings, file paths, service endpoints
- **Location**: `src/core/config_factory.py`

#### 3. Health Check Enhancer
- **Purpose**: Environment-aware health checks with fallbacks
- **Features**: Graceful degradation, timeout handling, fallback reporting
- **Location**: `src/health/adaptive_health_check.py`

## 4. REFINEMENT Phase

### Critical File Modifications Required

#### A. Network Configuration Issues
**Files to Update:**
- `health_check.py:53` - Redis URL hardcoded
- `src/production_deployment_config.py:102` - Redis URL
- `health_endpoint.py:26` - Redis connection
- `docker-compose.yml` - Service definitions

**Refinement Strategy:**
```python
# Before (Hardcoded)
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')

# After (Environment Aware)  
from src.core.environment_detector import detect_environment
from src.core.config_factory import get_redis_config

environment = detect_environment()
redis_config = get_redis_config(environment)
redis_url = redis_config.connection_string
```

#### B. Filesystem Path Issues
**Files to Update:**
- `services/video_library_service.py:58,502` - Upload directory paths
- `services/detection_pipeline_service.py:418,514` - Screenshot and model paths  
- `services/fixed_detection_service.py:44` - Model loading path
- `production_config.json` - All hardcoded paths

**Refinement Strategy:**
```python
# Before (Hardcoded)
def __init__(self, base_upload_dir: str = "/app/uploads"):

# After (Environment Aware)
from src.core.config_factory import get_filesystem_config

def __init__(self, base_upload_dir: str = None):
    if base_upload_dir is None:
        fs_config = get_filesystem_config()
        base_upload_dir = fs_config.upload_directory
```

## 5. COMPLETION Phase

### Implementation Priority

#### Phase 1: Core Infrastructure (Critical - 1 day)
1. Create `EnvironmentDetector` class
2. Create `ConfigurationFactory` class  
3. Update `health_check.py` with environment detection
4. Test basic health checks in both environments

#### Phase 2: Service Adaptation (High - 2 days)
1. Update all service classes to use ConfigurationFactory
2. Modify database connection logic  
3. Update Redis connection handling
4. Create missing local directories programmatically

#### Phase 3: Configuration Management (Medium - 1 day)
1. Update environment files (`.env.development`, `.env.production`)
2. Add environment detection flags
3. Update production configuration JSON
4. Add logging for environment detection

#### Phase 4: Testing & Validation (High - 1 day)
1. Create integration tests for both environments
2. Test health check endpoints
3. Validate service initialization
4. Performance testing

### Success Criteria
- [ ] Health checks pass in local development (200 OK)
- [ ] Health checks pass in Docker environment (200 OK)  
- [ ] No hardcoded Docker hostnames in local development
- [ ] Services start successfully in both environments
- [ ] File operations work with appropriate paths
- [ ] Graceful degradation when services unavailable

### Risk Mitigation
- **Rollback Plan**: Keep current working configurations as fallbacks
- **Testing Strategy**: Parallel testing in both environments
- **Monitoring**: Enhanced logging during transition period
- **Documentation**: Clear environment setup instructions

## Recommended Immediate Actions

1. **CRITICAL**: Implement environment detection in health_check.py
2. **CRITICAL**: Create local development Redis/PostgreSQL fallbacks  
3. **HIGH**: Create missing directories with proper permissions
4. **HIGH**: Update service initialization with environment awareness
5. **MEDIUM**: Add comprehensive logging for troubleshooting

## Files for Immediate Review/Modification

### Network Issues (4 files)
- `/home/rigade/Testing/ai-model-validation-platform/backend/health_check.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/src/production_deployment_config.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/health_endpoint.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/docker-compose.yml`

### Filesystem Issues (6 files)
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_library_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_pipeline_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/fixed_detection_service.py`
- `/home/rigade/Testing/ai-model-validation-platform/backend/production_config.json`
- `/home/rigade/Testing/ai-model-validation-platform/backend/.env.development`
- `/home/rigade/Testing/ai-model-validation-platform/backend/.env.production`

This SPARC analysis provides a comprehensive roadmap for resolving the critical system health degradation issues through systematic environment detection and configuration management.