# Environment Configuration Guide - Frontend-Backend Integration

## Overview

This guide provides comprehensive environment configuration for both frontend and backend services to ensure seamless integration.

---

## Backend Configuration

### Required Environment Variables

Create `/backend/.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/ai_model_validation
# Or for SQLite (development only):
# DATABASE_URL=sqlite:///./app.db

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3001"]
CORS_CREDENTIALS=true
CORS_METHODS=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
CORS_HEADERS=["*"]

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true  # Development only

# Security (if enabled)
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Monitoring & Logging
ENABLE_MONITORING=true
LOG_LEVEL=INFO
ALERT_EMAIL_TO=admin@example.com

# File Upload
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=524288000  # 500MB in bytes

# WebSocket
WEBSOCKET_CORS_ORIGINS=["http://localhost:3000"]

# Feature Flags
ENABLE_QUALITY_FEATURES=true
ENABLE_ADVANCED_METRICS=true
```

### Configuration Class

Backend uses `config.py` or `config_settings.py`:

```python
from pydantic import BaseSettings
from typing import List

class Settings(BaseSettings):
    database_url: str
    cors_origins: List[str]
    cors_credentials: bool = True
    cors_methods: List[str] = ["*"]
    cors_headers: List[str] = ["*"]

    class Config:
        env_file = ".env"

settings = Settings()
```

### Verifying Backend Configuration

```bash
# Start backend server
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate  # or validation_env/bin/activate
python main.py

# Check configuration
curl http://localhost:8000/health
curl http://localhost:8000/api/results

# Test CORS
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS \
     http://localhost:8000/api/results
```

---

## Frontend Configuration

### Required Environment Variables

Create `/frontend/.env` file:

```bash
# API Configuration
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WEBSOCKET_URL=http://localhost:8000

# Feature Flags
REACT_APP_ENABLE_QUALITY_FEATURES=true
REACT_APP_ENABLE_ADVANCED_METRICS=true
REACT_APP_DEBUG_MODE=false

# Optional: API Timeout
REACT_APP_API_TIMEOUT=30000

# Optional: Retry Configuration
REACT_APP_MAX_RETRIES=3
REACT_APP_RETRY_DELAY=1000
```

### Configuration Usage in Frontend

The frontend uses `configurationManager` (detected in `enhancedApiService.ts`):

```typescript
import { getConfigValueSync } from '../utils/configurationManager';

const baseURL = getConfigValueSync('REACT_APP_API_URL', 'http://localhost:8000');
```

### Verifying Frontend Configuration

```bash
# Start frontend server
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm install
npm start

# Frontend should be accessible at http://localhost:3000
# Check browser console for API configuration logs
```

---

## Production Configuration

### Backend Production `.env`

```bash
DATABASE_URL=postgresql://prod_user:secure_password@db-server:5432/ai_model_prod
CORS_ORIGINS=["https://your-production-domain.com"]
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false
SECRET_KEY=very-secure-production-secret-key
LOG_LEVEL=WARNING
ENABLE_MONITORING=true
```

### Frontend Production `.env`

```bash
REACT_APP_API_URL=https://api.your-production-domain.com
REACT_APP_WEBSOCKET_URL=wss://api.your-production-domain.com
REACT_APP_ENABLE_QUALITY_FEATURES=true
REACT_APP_DEBUG_MODE=false
```

### Build for Production

```bash
# Frontend
cd frontend
npm run build
# Serves from frontend/build/

# Backend
cd backend
# Use production WSGI server
gunicorn main:app --workers 4 --bind 0.0.0.0:8000
# Or with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Docker Configuration (Optional)

### Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATABASE_URL=postgresql://user:pass@db:5432/ai_model_validation
ENV CORS_ORIGINS='["http://frontend:3000"]'

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:18-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/ai_model_validation
      - CORS_ORIGINS=["http://localhost:3000"]
    depends_on:
      - db

  frontend:
    build:
      context: ./frontend
      args:
        - REACT_APP_API_URL=http://localhost:8000
    ports:
      - "3000:80"
    depends_on:
      - backend

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=ai_model_validation
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Troubleshooting

### CORS Issues

**Symptom**: Browser console shows CORS errors

**Solution**:
1. Verify backend `CORS_ORIGINS` includes frontend URL (including port)
2. Check CORS middleware is properly configured in `main.py`
3. Ensure preflight OPTIONS requests are allowed

```python
# Backend main.py - Verify this section exists
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### API Connection Failures

**Symptom**: Frontend cannot reach backend

**Solutions**:
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `REACT_APP_API_URL` matches backend URL
3. Verify no firewall blocking ports
4. Check browser network tab for actual request URL

### WebSocket Connection Issues

**Symptom**: Real-time updates not working

**Solutions**:
1. Verify WebSocket server is running (Socket.IO detected in backend)
2. Check `REACT_APP_WEBSOCKET_URL` configuration
3. Verify WebSocket CORS configuration in backend
4. Check browser console for WebSocket errors

### Environment Variables Not Loading

**Symptom**: App uses default values instead of `.env` values

**Solutions**:
1. Ensure `.env` file is in correct directory
2. Restart development servers after changing `.env`
3. For frontend, variables must start with `REACT_APP_`
4. For backend, verify `pydantic BaseSettings` loads `.env`
5. Check `.env` file is not in `.gitignore` (for local dev only)

---

## Security Best Practices

1. **Never commit `.env` files to git**
   - Add `.env` to `.gitignore`
   - Use `.env.example` for documentation

2. **Use different secrets for dev/prod**
   - Generate strong random secrets for production
   - Rotate secrets regularly

3. **Restrict CORS origins in production**
   - Never use `["*"]` in production
   - Only allow specific trusted domains

4. **Use HTTPS in production**
   - Enforce HTTPS for API calls
   - Use WSS for WebSocket connections

5. **Environment-specific configurations**
   - Use environment variables, not hardcoded values
   - Validate configuration on startup

---

## Configuration Checklist

### Development Setup

- [ ] Backend `.env` created with database URL
- [ ] Backend `.env` includes `CORS_ORIGINS=["http://localhost:3000"]`
- [ ] Frontend `.env` created with `REACT_APP_API_URL=http://localhost:8000`
- [ ] Backend server starts without errors
- [ ] Frontend server starts without errors
- [ ] Health check endpoint accessible: `curl http://localhost:8000/health`
- [ ] Frontend can make API calls (check browser network tab)
- [ ] CORS preflight requests succeed
- [ ] WebSocket connection establishes (if using real-time features)

### Production Setup

- [ ] Production database configured
- [ ] Strong SECRET_KEY generated
- [ ] CORS restricted to production domain only
- [ ] HTTPS/WSS configured
- [ ] Environment variables set in deployment platform
- [ ] Logging configured for production
- [ ] Monitoring enabled
- [ ] Health checks configured in load balancer
- [ ] Database connection pooling configured
- [ ] Static file serving configured (frontend)

---

## Next Steps

After configuration:
1. Run integration tests: `pytest backend/tests/integration/`
2. Verify API contracts: Review `/backend/docs/API_CONTRACT.md`
3. Test end-to-end data flow
4. Monitor logs for any configuration warnings
5. Load test API endpoints for performance

---

**Last Updated**: 2025-11-19
**Integration Agent**: Integration Specialist
