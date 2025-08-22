# Configuration Standards - Single Source of Truth

## ⚡ STANDARDIZED PORT CONFIGURATION

### Production Standard Ports
- **Frontend**: `3000` (React development server)
- **Backend API**: `8000` (FastAPI server) 
- **Database**: `5432` (PostgreSQL)
- **Redis**: `6379` (Cache/Sessions)
- **CVAT**: `8080` (Annotation server)

### Development Override Ports
- **Frontend**: `3001` (Avoids conflicts with other React apps)
- **Backend API**: `8001` (Avoids conflicts with other APIs)

## 📋 CONFIGURATION HIERARCHY

### 1. Primary Configuration Files
- `/ai-model-validation-platform/backend/config.py` - Backend settings
- `/ai-model-validation-platform/frontend/.env` - Frontend environment
- `/ai-model-validation-platform/docker-compose.yml` - Container orchestration

### 2. Documentation Files (Must match primary)
- `/README.md` - Main project documentation
- `/ai-model-validation-platform/README.md` - Platform documentation
- `/task-breakdown.md` - Development task tracking

### 3. Build Configuration
- Backend Dockerfile - Port exposure
- Frontend Dockerfile - Port exposure
- Package.json scripts - Development ports

## 🎯 STANDARDIZED VALUES

### Environment Variables (.env files)
```bash
# Backend (.env)
DATABASE_URL=postgresql://postgres:password@localhost:5432/vru_validation
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Frontend (.env)
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
PORT=3000
```

### Docker Configuration
```yaml
services:
  backend:
    ports:
      - "8000:8000"
  frontend:
    ports:
      - "3000:3000"
```

### Application Configuration
```python
# config.py
api_port: int = 8000
cors_origins: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]
```

## 🔧 MIGRATION PLAN

### Phase 1: Primary Configuration
1. Update backend/config.py - Set api_port=8000
2. Update backend/.env - Set correct database and CORS
3. Update frontend/.env - Set API_BASE_URL=localhost:8000, PORT=3000

### Phase 2: Docker & Build
1. Verify docker-compose.yml ports (8000:8000, 3000:3000)
2. Update Dockerfile EXPOSE statements
3. Update package.json PORT reference

### Phase 3: Documentation
1. Update README.md references
2. Update task-breakdown.md references
3. Update any other markdown documentation

### Phase 4: Validation
1. Test local development startup
2. Test Docker compose startup
3. Validate API connectivity
4. Check CORS functionality

## 📝 CHANGE LOG

### Issues Fixed:
- **AD-01**: Multi-file port chaos - 6 different port configurations
- Backend port mismatch: main.py(8001) vs docker-compose(8000)
- Frontend port mismatch: .env(3001) vs docker-compose(3000)
- CORS origins pointing to wrong frontend port
- Documentation showing inconsistent port numbers

### Standardization Applied:
- Single source of truth for all port configurations
- Consistent environment variable naming
- Aligned Docker and development configurations
- Updated all documentation to match standard ports
- Simplified CORS configuration

## ✅ VALIDATION CHECKLIST

- [ ] Backend starts on port 8000
- [ ] Frontend starts on port 3000
- [ ] API accessible at http://localhost:8000
- [ ] Frontend loads at http://localhost:3000
- [ ] CORS allows frontend to call API
- [ ] Docker compose works with standard ports
- [ ] All documentation shows correct ports
- [ ] No conflicting configurations remain

---

**Effective Date**: 2025-08-12  
**Last Updated**: Configuration standardization implementation  
**Status**: ✅ IMPLEMENTED