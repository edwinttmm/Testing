# External Access Configuration Guide

## Summary

This configuration enables the AI Model Validation Platform to be accessible from both localhost (127.0.0.1) and the external Vultr server IP (155.138.239.131) while maintaining security for database services.

## Changes Made

### 1. Docker Compose Configuration (`docker-compose.yml`)

**Port Bindings Updated:**
- **Frontend**: `0.0.0.0:3000:3000` (accessible externally)
- **Backend**: `0.0.0.0:8000:8000` (accessible externally)  
- **PostgreSQL**: `127.0.0.1:5432:5432` (internal access only)
- **Redis**: `127.0.0.1:6379:6379` (internal access only)
- **CVAT**: `0.0.0.0:8080:8080` (accessible externally)

**Environment Variables:**
- Updated frontend environment to use external IP for API calls
- CORS origins configured for external access

### 2. Environment Configuration

**Root `.env` file:**
```env
BACKEND_HOST=155.138.239.131
FRONTEND_HOST=155.138.239.131
CVAT_HOST=155.138.239.131
DATABASE_HOST=127.0.0.1  # Internal only
REDIS_HOST=127.0.0.1     # Internal only
```

**Backend `.env` file:**
```env
AIVALIDATION_API_HOST=0.0.0.0
AIVALIDATION_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,http://0.0.0.0:3000
```

**Frontend `.env` file:**
```env
REACT_APP_API_URL=http://155.138.239.131:8000
REACT_APP_WS_URL=ws://155.138.239.131:8000
HOST=0.0.0.0
```

## Security Considerations

### ✅ Secure (Internal Access Only)
- **PostgreSQL**: Port 5432 bound to 127.0.0.1 only
- **Redis**: Port 6379 bound to 127.0.0.1 only

### ⚠️ External Access (Required for Functionality)
- **Frontend**: Port 3000 accessible from internet
- **Backend**: Port 8000 accessible from internet
- **CVAT**: Port 8080 accessible from internet

### 🔒 Security Recommendations
1. Configure firewall to restrict access to specific IPs if needed
2. Enable SSL/TLS for production (currently disabled)
3. Use strong passwords for database services
4. Monitor access logs regularly
5. Consider using a reverse proxy (nginx) for additional security

## Deployment Steps

### 1. Stop Current Services
```bash
cd /home/user/Testing/ai-model-validation-platform
docker-compose down
```

### 2. Update Configuration (Already Done)
- All configuration files have been updated
- Port bindings configured for external access
- CORS settings updated

### 3. Rebuild and Start Services
```bash
# Remove old images to force rebuild
docker-compose build --no-cache

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

### 4. Test External Access
```bash
# Run the connectivity test
./scripts/test-external-access.sh

# Or manually test:
curl http://155.138.239.131:8000/health
curl http://155.138.239.131:3000
```

## Access URLs

### From Internet (External Access)
- **Frontend**: http://155.138.239.131:3000
- **Backend API**: http://155.138.239.131:8000
- **API Documentation**: http://155.138.239.131:8000/docs
- **CVAT Annotation Tool**: http://155.138.239.131:8080

### From Localhost (Internal Access)
- **Frontend**: http://127.0.0.1:3000
- **Backend API**: http://127.0.0.1:8000
- **PostgreSQL**: 127.0.0.1:5432 (containers only)
- **Redis**: 127.0.0.1:6379 (containers only)

## Troubleshooting

### Common Issues

**1. Connection Refused**
```bash
# Check if containers are running
docker-compose ps

# Check logs
docker-compose logs frontend
docker-compose logs backend
```

**2. CORS Errors**
- Verify CORS origins in backend/.env include the client IP
- Check browser developer tools for specific CORS errors

**3. Database Connection Issues**
```bash
# Test database connection from backend container
docker-compose exec backend python -c "import database; print('DB Connected')"
```

### Network Diagnostics
```bash
# Check port bindings
netstat -tulpn | grep -E ':(3000|8000|5432|6379)'

# Test connectivity
curl -I http://155.138.239.131:8000/health
curl -I http://127.0.0.1:8000/health

# Check Docker networks
docker network inspect vru_validation_network
```

### Firewall Configuration (If Needed)
```bash
# Allow specific ports (Ubuntu/Debian)
sudo ufw allow 3000/tcp  # Frontend
sudo ufw allow 8000/tcp  # Backend
sudo ufw allow 8080/tcp  # CVAT

# Block database ports externally (should be default)
sudo ufw deny 5432/tcp   # PostgreSQL
sudo ufw deny 6379/tcp   # Redis
```

## Monitoring

### Health Checks
- Frontend: http://155.138.239.131:3000
- Backend: http://155.138.239.131:8000/health
- Database connectivity tested internally

### Log Monitoring
```bash
# Real-time logs
docker-compose logs -f

# Service-specific logs
docker-compose logs backend
docker-compose logs frontend
```

## Next Steps

1. **Test thoroughly** - Verify all functionality works from external access
2. **Monitor performance** - Check for any latency issues
3. **Security audit** - Review firewall and access controls
4. **SSL/TLS** - Configure HTTPS for production
5. **Backup strategy** - Ensure data persistence and backup

## Configuration Files Modified

- `/docker-compose.yml` - Port bindings and environment variables
- `/.env` - Host configuration
- `/backend/.env` - CORS and API host settings
- `/frontend/.env` - API endpoints
- `/scripts/test-external-access.sh` - Testing script

All changes maintain backward compatibility with localhost access while enabling external connectivity.