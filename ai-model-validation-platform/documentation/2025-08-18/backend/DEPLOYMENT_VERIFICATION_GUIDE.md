# Deployment Verification Guide for 155.138.239.131

## ✅ Configuration Verified

Your AI Model Validation Platform has been properly configured for external IP access. Here's how to verify deployment:

## 1. Pre-Deployment Checklist ✅

### Configuration Files Validated:
- ✅ **docker-compose.yml**: All ports bound to `155.138.239.131`
- ✅ **backend/config.py**: CORS origins include external IP
- ✅ **frontend/package.json**: HOST=0.0.0.0 for external access
- ✅ **frontend/Dockerfile**: Container configured for external binding
- ✅ **REACT_APP_API_URL**: Set to `http://155.138.239.131:8000`

### Port Mappings:
- Frontend: `155.138.239.131:3000` → React App
- Backend: `155.138.239.131:8000` → FastAPI + Socket.IO
- PostgreSQL: `155.138.239.131:5432` → Database
- Redis: `155.138.239.131:6379` → Cache/Sessions
- CVAT: `155.138.239.131:8080` → Annotation Tool

## 2. Deployment Commands

### On Your Server with Docker:
```bash
# Navigate to project directory
cd ai-model-validation-platform

# Pull latest changes
git pull origin v2

# Build and start services
docker compose up -d --build

# Or using docker-compose
docker-compose up -d --build
```

### Check Service Status:
```bash
docker compose ps
docker compose logs -f
```

## 3. Verification Steps

### Step 1: Test Network Connectivity
```bash
# From any machine, test if the server is reachable
curl -I http://155.138.239.131:8000/health
ping 155.138.239.131
```

### Step 2: Verify Backend API
```bash
# Health check
curl http://155.138.239.131:8000/health

# API root
curl http://155.138.239.131:8000/

# Dashboard stats
curl http://155.138.239.131:8000/api/dashboard/stats

# Projects endpoint
curl http://155.138.239.131:8000/api/projects
```

Expected Response:
```json
{
  "status": "healthy"
}
```

### Step 3: Test Frontend Access
Open in web browser:
```
http://155.138.239.131:3000
```

### Step 4: Verify Frontend-Backend Communication
1. Open browser dev tools (F12)
2. Go to Network tab
3. Load the frontend
4. Check for successful API calls to `155.138.239.131:8000`

### Step 5: Database Connectivity Test
```bash
# From server, test database connection
docker compose exec backend python -c "
from database import SessionLocal, engine
try:
    db = SessionLocal()
    db.execute('SELECT 1')
    print('✅ Database connection successful')
    db.close()
except Exception as e:
    print(f'❌ Database error: {e}')
"
```

## 4. Troubleshooting Common Issues

### Issue: "Connection Refused"
**Solutions:**
1. Ensure firewall allows ports 3000, 8000, 5432, 6379, 8080
2. Check if services are running: `docker compose ps`
3. Verify server IP configuration

### Issue: CORS Errors in Browser
**Solutions:**
1. Check backend logs: `docker compose logs backend`
2. Verify CORS origins in `backend/config.py`
3. Ensure API URL in frontend matches backend

### Issue: Frontend Shows "API Error"
**Solutions:**
1. Verify `REACT_APP_API_URL=http://155.138.239.131:8000`
2. Check backend health: `curl http://155.138.239.131:8000/health`
3. Check browser network tab for failed requests

### Issue: Database Connection Failed
**Solutions:**
1. Check PostgreSQL container: `docker compose logs postgres`
2. Verify database environment variables
3. Ensure database initialization completed

## 5. Service Health Monitoring

### Quick Health Check Script:
```bash
#!/bin/bash
echo "🔍 Checking AI Model Validation Platform Health..."

# Backend Health
if curl -f http://155.138.239.131:8000/health >/dev/null 2>&1; then
    echo "✅ Backend: Healthy"
else
    echo "❌ Backend: Down"
fi

# Frontend Access
if curl -f http://155.138.239.131:3000 >/dev/null 2>&1; then
    echo "✅ Frontend: Accessible"
else
    echo "❌ Frontend: Down"
fi

# Database Connection (requires docker access)
if docker compose exec -T backend python -c "from database import SessionLocal; db = SessionLocal(); db.execute('SELECT 1'); db.close()" >/dev/null 2>&1; then
    echo "✅ Database: Connected"
else
    echo "❌ Database: Connection failed"
fi
```

## 6. Expected Service URLs

After successful deployment, these URLs should be accessible:

### Main Application:
- **Frontend**: http://155.138.239.131:3000
- **Backend API**: http://155.138.239.131:8000
- **API Docs**: http://155.138.239.131:8000/docs
- **Health Check**: http://155.138.239.131:8000/health

### Database Access (Internal):
- **PostgreSQL**: 155.138.239.131:5432
- **Redis**: 155.138.239.131:6379

### Optional Tools:
- **CVAT Annotation**: http://155.138.239.131:8080

## 7. Performance Validation

### Load Testing (Optional):
```bash
# Install ab (apache bench)
sudo apt-get install apache2-utils

# Test backend performance
ab -n 100 -c 10 http://155.138.239.131:8000/api/dashboard/stats

# Test frontend serving
ab -n 50 -c 5 http://155.138.239.131:3000/
```

## 8. Security Checklist

- [ ] Firewall configured for required ports only
- [ ] Database passwords changed from defaults
- [ ] SSL/TLS certificates configured (if needed)
- [ ] API rate limiting enabled (if required)
- [ ] CORS origins properly restricted
- [ ] Container security best practices followed

## 9. Success Indicators

✅ **Full Success Criteria:**
1. Frontend loads at http://155.138.239.131:3000
2. Backend API responds at http://155.138.239.131:8000
3. No CORS errors in browser console
4. API endpoints return expected data
5. File upload functionality works
6. WebSocket connections establish successfully
7. Database queries execute without errors

## 10. Next Steps After Deployment

1. **Monitor Logs**: Set up log aggregation
2. **Backup Strategy**: Configure database backups
3. **SSL Setup**: Add HTTPS for production
4. **Performance Monitoring**: Set up metrics collection
5. **Update Process**: Establish CI/CD pipeline

---

Your application is now configured for external access on **155.138.239.131**!