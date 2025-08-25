# External IP Deployment Guide - Vultr Server 155.138.239.131

This guide provides instructions for deploying the AI Model Validation Platform on Vultr server with external IP access.

## 🎯 Quick Setup

### 1. Start with External IP Support
```bash
# Make scripts executable
chmod +x start-with-external-ip.sh
chmod +x test-cors-external-ip.py
chmod +x verify-external-ip-config.py

# Start all services with external IP configuration
./start-with-external-ip.sh
```

### 2. Verify Configuration
```bash
# Check all configuration files
python3 verify-external-ip-config.py

# Test CORS and connectivity
python3 test-cors-external-ip.py
```

## 🌐 Access URLs

Once deployed, the platform will be accessible at:

- **Frontend**: http://155.138.239.131:3000
- **Backend API**: http://155.138.239.131:8000
- **API Documentation**: http://155.138.239.131:8000/docs
- **Database**: 155.138.239.131:5432
- **Redis**: 155.138.239.131:6379

## 🔧 Configuration Summary

### CORS Configuration
The following origins are configured for CORS access:
- `http://localhost:3000` (development)
- `http://127.0.0.1:3000` (development)
- `http://155.138.239.131:3000` (production)
- `https://155.138.239.131:3000` (production HTTPS)

### Environment Variables

#### Backend (.env, .env.production)
```bash
AIVALIDATION_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000
AIVALIDATION_API_HOST=0.0.0.0
AIVALIDATION_API_PORT=8000
```

#### Frontend (.env, .env.production)
```bash
REACT_APP_API_URL=http://155.138.239.131:8000
REACT_APP_WS_URL=ws://155.138.239.131:8000
REACT_APP_SOCKETIO_URL=http://155.138.239.131:8001
REACT_APP_VIDEO_BASE_URL=http://155.138.239.131:8000
```

#### Docker Compose
```yaml
services:
  backend:
    ports:
      - "0.0.0.0:8000:8000"
    environment:
      - AIVALIDATION_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000
      - ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000
  
  frontend:
    ports:
      - "0.0.0.0:3000:3000"
    environment:
      - REACT_APP_API_URL=http://155.138.239.131:8000
      - REACT_APP_WS_URL=ws://155.138.239.131:8000
```

## 🔍 Testing & Verification

### 1. Automatic Configuration Check
```bash
python3 verify-external-ip-config.py
```

### 2. CORS and API Testing
```bash
python3 test-cors-external-ip.py
```

### 3. Manual Testing

#### Test Backend Health
```bash
curl -H "Origin: http://155.138.239.131:3000" http://155.138.239.131:8000/health
```

#### Test CORS Preflight
```bash
curl -X OPTIONS \
  -H "Origin: http://155.138.239.131:3000" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Content-Type" \
  http://155.138.239.131:8000/health
```

#### Test Frontend Access
```bash
curl http://155.138.239.131:3000
```

## 🚀 Deployment Commands

### Standard Docker Compose Deployment
```bash
# Using production environment file
docker-compose --env-file .env.production up -d --build

# Or using the startup script (recommended)
./start-with-external-ip.sh
```

### Manual Environment Setup
```bash
export BACKEND_HOST=155.138.239.131
export FRONTEND_HOST=155.138.239.131
export APP_ENV=production
export NODE_ENV=production
export AIVALIDATION_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000"

docker-compose up -d --build
```

## 🔧 Troubleshooting

### CORS Issues
1. Check CORS configuration in backend logs:
   ```bash
   docker-compose logs backend | grep -i cors
   ```

2. Test CORS headers:
   ```bash
   curl -I -H "Origin: http://155.138.239.131:3000" http://155.138.239.131:8000/health
   ```

3. Verify environment variables in container:
   ```bash
   docker exec ai_validation_backend env | grep CORS
   ```

### Connection Issues
1. Check if services are running:
   ```bash
   docker-compose ps
   ```

2. Check service logs:
   ```bash
   docker-compose logs -f backend
   docker-compose logs -f frontend
   ```

3. Test internal connectivity:
   ```bash
   docker exec ai_validation_backend curl http://localhost:8000/health
   ```

### Firewall Configuration
Ensure the following ports are open on the Vultr server:
- `3000` (Frontend)
- `8000` (Backend API)
- `5432` (PostgreSQL - if external access needed)
- `6379` (Redis - if external access needed)

## 📝 Monitoring

### Check Service Health
```bash
# All services
docker-compose ps

# Backend health
curl http://155.138.239.131:8000/health

# Frontend accessibility
curl http://155.138.239.131:3000
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific services
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

## 🛑 Stop Services
```bash
docker-compose down
```

## 🔐 Security Considerations

1. **Change Default Passwords**: Update all default passwords in `.env.production`
2. **HTTPS Setup**: Consider setting up SSL/TLS certificates for HTTPS access
3. **Firewall Rules**: Implement proper firewall rules
4. **Database Security**: Secure PostgreSQL and Redis access
5. **Secret Keys**: Generate strong secret keys for production

## 📊 Performance Monitoring

The platform includes built-in monitoring capabilities. Access them at:
- Health endpoint: `http://155.138.239.131:8000/health`
- Metrics endpoint: `http://155.138.239.131:8000/metrics` (if enabled)

## ✅ Verification Checklist

- [ ] All services start successfully
- [ ] Frontend accessible at http://155.138.239.131:3000
- [ ] Backend API accessible at http://155.138.239.131:8000
- [ ] CORS headers allow external IP origins
- [ ] WebSocket connections work
- [ ] Video upload and processing functional
- [ ] Database connections stable
- [ ] No CORS errors in browser console

## 🆘 Support

If you encounter issues:
1. Run the verification script: `python3 verify-external-ip-config.py`
2. Run the CORS test: `python3 test-cors-external-ip.py`
3. Check logs: `docker-compose logs -f`
4. Verify network connectivity and firewall settings