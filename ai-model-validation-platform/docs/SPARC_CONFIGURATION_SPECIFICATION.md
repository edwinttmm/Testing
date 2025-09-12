# SPARC Configuration Issues Specification
## AI Model Validation Platform - Complete Configuration Analysis

**Date:** 2025-08-27  
**Phase:** SPARC Specification  
**Scope:** External IP Configuration Issues Analysis

---

## 1. SPECIFICATION OVERVIEW

### 1.1 Requirements Analysis
**Primary Objective:** Identify and document all configuration mismatches between frontend expectations and backend reality for external IP deployment (155.138.239.131).

**Key Requirements:**
- FR-001: Frontend must successfully connect to backend API endpoints
- FR-002: WebSocket connections must be established correctly
- FR-003: CORS configuration must allow legitimate requests
- FR-004: Port configurations must be consistent across services
- FR-005: Environment variables must be properly configured

### 1.2 Scope Boundaries
- **In Scope:** All configuration files, environment variables, API endpoints, CORS settings
- **Out of Scope:** Database schema changes, business logic modifications

---

## 2. CONFIGURATION ISSUES IDENTIFIED

### 2.1 CRITICAL CONFIGURATION MISMATCHES

#### 2.1.1 External IP Usage (155.138.239.131)
**Files Affected:** 184 files contain hardcoded external IP references

**Key Configuration Files:**
- `/frontend/src/config/appConfig.ts` (Lines 81, 86, 94, 160)
- `/frontend/.env.production`
- `/backend/config.py` (Line 31)
- `/backend/.env.production`
- `/frontend/public/config.js`

**Issue:** Hardcoded IP addresses throughout configuration files create deployment inflexibility.

#### 2.1.2 Port Configuration Inconsistencies

| Service | Expected Port | Configured Port | Status |
|---------|--------------|----------------|--------|
| Backend API | 8000 | 8000 | ✅ Consistent |
| WebSocket | 8000 | 8000 | ✅ Consistent |
| SocketIO | 8001 | 8001 | ✅ Consistent |
| Frontend | 3000 | 3000 | ✅ Consistent |

#### 2.1.3 CORS Configuration Issues

**Backend CORS Origins (config.py:31):**
```python
cors_origins: List[str] = os.getenv('AIVALIDATION_CORS_ORIGINS', 
    'http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000').split(',')
```

**Issues Found:**
1. Missing HTTPS origins for production
2. Inconsistent CORS origin formats across different files
3. Some files use arrays, others use comma-separated strings

### 2.2 ENVIRONMENT VARIABLE MISMATCHES

#### 2.2.1 Frontend Environment Variables
**File:** `/frontend/.env.production`
```bash
REACT_APP_API_URL=http://155.138.239.131:8000
REACT_APP_WS_URL=ws://155.138.239.131:8000
REACT_APP_SOCKETIO_URL=http://155.138.239.131:8000  # Should be :8001
```

**Issue:** SocketIO URL points to wrong port (8000 instead of 8001)

#### 2.2.2 Backend Environment Variables
**File:** `/backend/.env.production`
```bash
CORS_ORIGINS=["http://155.138.239.131:3000", "https://155.138.239.131:3000"]
AIVALIDATION_CORS_ORIGINS=http://155.138.239.131:3000,https://155.138.239.131:3000
```

**Issues:**
1. Duplicate CORS configuration variables
2. Mixed array and string formats
3. Missing localhost origins for development

### 2.3 API CONFIGURATION MISMATCHES

#### 2.3.1 Frontend API Configuration
**File:** `/frontend/src/config/appConfig.ts`

**Issues:**
- Line 81: Hardcoded localhost check redirects to external IP
- Line 94: Fallback hardcoded to external IP
- Runtime configuration override logic may conflict with build-time config

#### 2.3.2 WebSocket Configuration
**File:** `/frontend/src/config/appConfig.ts` (Lines 98-107)

**Issue:** WebSocket URL generation depends on API URL, creating cascading configuration dependencies

---

## 3. ACCEPTANCE CRITERIA

### 3.1 Functional Requirements Validation

#### FR-001: API Connectivity
**Acceptance Criteria:**
- [ ] Frontend can connect to backend at http://155.138.239.131:8000
- [ ] API endpoints return valid responses
- [ ] Error handling works for connection failures

**Test Cases:**
```gherkin
Scenario: Successful API connection
  Given the backend is running on 155.138.239.131:8000
  When the frontend makes an API request
  Then the request should succeed
  And the response should be valid JSON
```

#### FR-002: WebSocket Connectivity
**Acceptance Criteria:**
- [ ] WebSocket connects to ws://155.138.239.131:8000
- [ ] Real-time updates are received
- [ ] Connection resilience handles failures

#### FR-003: CORS Compliance
**Acceptance Criteria:**
- [ ] CORS allows http://155.138.239.131:3000
- [ ] CORS allows https://155.138.239.131:3000
- [ ] CORS rejects unauthorized origins
- [ ] Preflight requests succeed

### 3.2 Non-Functional Requirements

#### NFR-001: Configuration Flexibility
- Configuration should support environment-based overrides
- No hardcoded values in production builds
- Runtime configuration should be possible

#### NFR-002: Security Requirements
- HTTPS origins should be preferred in production
- CORS should not use wildcard (*) in production
- Secure headers should be enabled

---

## 4. EDGE CASES AND SCENARIOS

### 4.1 Network Scenarios
- **Scenario 1:** External IP changes
- **Scenario 2:** Port conflicts
- **Scenario 3:** Firewall restrictions
- **Scenario 4:** DNS resolution failures

### 4.2 Environment Scenarios
- **Scenario 1:** Development vs Production mismatches
- **Scenario 2:** Environment variable precedence conflicts
- **Scenario 3:** Missing environment variables
- **Scenario 4:** Invalid configuration values

---

## 5. CONSTRAINTS AND DEPENDENCIES

### 5.1 Technical Constraints
- External IP 155.138.239.131 is fixed
- HTTP protocol required (no SSL certificate)
- Single server deployment
- Limited port range availability

### 5.2 Configuration Dependencies
- Frontend build process requires compile-time environment variables
- Backend CORS configuration affects all frontend requests
- Docker compose files must match environment configurations
- Runtime configuration overrides must be loaded before API initialization

---

## 6. SUCCESS METRICS

### 6.1 Configuration Consistency Metrics
- **Target:** 100% configuration file consistency
- **Current:** ~70% consistency identified
- **Gaps:** Port mismatches, CORS origin variations

### 6.2 Deployment Success Metrics
- **API Availability:** 99.9% uptime on 155.138.239.131:8000
- **WebSocket Connection Success Rate:** >95%
- **CORS Preflight Success Rate:** 100%

---

## 7. IMMEDIATE ACTION ITEMS

### 7.1 Critical Fixes Required
1. **Fix SocketIO Port Mismatch**
   - File: `/frontend/.env.production`
   - Change: `REACT_APP_SOCKETIO_URL=http://155.138.239.131:8001`

2. **Standardize CORS Configuration**
   - Consolidate duplicate CORS variables
   - Ensure consistent format across files

3. **Validate All Environment Files**
   - Check all `.env*` files for consistency
   - Verify Docker compose configurations

### 7.2 Configuration Validation Tests
1. **Unit Tests:** Environment variable validation
2. **Integration Tests:** Cross-service communication
3. **E2E Tests:** Full user workflow validation

---

## 8. CONFIGURATION FILE INVENTORY

### 8.1 Primary Configuration Files
| File | Type | Status | Issues |
|------|------|--------|--------|
| `/frontend/src/config/appConfig.ts` | TypeScript | ⚠️ Issues | Hardcoded IPs |
| `/frontend/.env.production` | Environment | ⚠️ Issues | Port mismatch |
| `/backend/config.py` | Python | ✅ OK | Minor inconsistencies |
| `/backend/.env.production` | Environment | ⚠️ Issues | Duplicate vars |
| `/frontend/public/config.js` | JavaScript | ✅ OK | Runtime override |

### 8.2 Docker Configuration Files
- `docker-compose.production.yml`
- `docker-compose.vultr.yml`
- `docker-compose.unified.yml`

---

## 9. RECOMMENDATIONS

### 9.1 Short-term Fixes
1. Fix immediate port mismatches
2. Standardize CORS configuration
3. Validate all environment files

### 9.2 Long-term Improvements
1. Implement configuration management system
2. Add configuration validation at startup
3. Create deployment-specific configuration templates
4. Implement health checks for all configuration endpoints

---

**Specification Status:** COMPLETE  
**Next Phase:** SPARC Pseudocode - Configuration Fix Implementation Plan