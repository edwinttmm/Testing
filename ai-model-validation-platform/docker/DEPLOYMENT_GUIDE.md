# 🚀 VRU Platform Deployment Guide

## Quick Start

### 1. **Production Deployment (Recommended)**
```bash
# Navigate to project root
cd /home/rigade/Testing/ai-model-validation-platform

# Run the quick deployment script
./docker/quick-deploy.sh
```

### 2. **Development Mode**
```bash
# Start development environment with hot reload
./docker/dev-mode.sh
```

### 3. **Manual Deployment**
```bash
# Using the unified compose file
docker compose -f docker/docker-compose.unified-fixed.yml --env-file .env.production up -d
```

## 🔧 Configuration Files Overview

### Core Files (Use These):
- `docker/docker-compose.unified-fixed.yml` - **MAIN** compose file
- `docker/Dockerfile.backend-optimized` - Optimized backend image
- `docker/Dockerfile.frontend-optimized` - Optimized frontend image
- `.env.production` - Production environment variables

### Deployment Scripts:
- `docker/quick-deploy.sh` - Automated production deployment
- `docker/dev-mode.sh` - Development environment setup

## 🌐 Service Access

After successful deployment:

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://155.138.239.131:3000 | Main web interface |
| Backend API | http://155.138.239.131:8000/docs | API documentation |
| Health Check | http://155.138.239.131:8000/health | System health |
| Local Frontend | http://localhost:3000 | Local access |
| Local API | http://localhost:8000 | Local API access |

## 📋 Pre-Deployment Checklist

- [ ] Docker and Docker Compose installed
- [ ] At least 5GB free disk space
- [ ] Port 3000 and 8000 available
- [ ] `.env.production` file configured
- [ ] All old containers stopped

## 🛠️ Troubleshooting

### Common Issues:

**Build Failures:**
```bash
# Clean Docker cache
docker system prune -a
docker buildx prune

# Rebuild with no cache
docker compose -f docker/docker-compose.unified-fixed.yml build --no-cache
```

**Port Conflicts:**
```bash
# Check what's using ports
sudo netstat -tulpn | grep :3000
sudo netstat -tulpn | grep :8000

# Stop conflicting services
sudo systemctl stop apache2  # If using Apache
sudo systemctl stop nginx    # If using Nginx
```

**Permission Issues:**
```bash
# Fix ownership
sudo chown -R $USER:$USER .
chmod +x docker/*.sh
```

**Service Health Issues:**
```bash
# Check individual service logs
docker compose -f docker/docker-compose.unified-fixed.yml logs backend
docker compose -f docker/docker-compose.unified-fixed.yml logs frontend
docker compose -f docker/docker-compose.unified-fixed.yml logs postgres
```

### Advanced Debugging:

**Container Shell Access:**
```bash
# Backend container
docker exec -it vru_backend_unified bash

# Frontend container  
docker exec -it vru_frontend_unified sh

# Database container
docker exec -it vru_postgres_unified psql -U vru_user -d vru_validation
```

**Network Issues:**
```bash
# Check network connectivity
docker network ls
docker network inspect vru_unified_network

# Test internal connectivity
docker exec vru_backend_unified ping postgres
docker exec vru_frontend_unified ping backend
```

## 📊 Monitoring

### Service Status:
```bash
# Check all services
docker compose -f docker/docker-compose.unified-fixed.yml ps

# Monitor resource usage
docker stats

# Check logs in real-time
docker compose -f docker/docker-compose.unified-fixed.yml logs -f
```

### Health Checks:
```bash
# Test all endpoints
curl -f http://localhost:8000/health
curl -f http://localhost:3000/health
curl -f http://localhost:8000/docs
```

## 🔒 Security Considerations

### Production Security:
1. **Change default passwords** in `.env.production`
2. **Use HTTPS** with SSL certificates
3. **Limit network exposure** (use 127.0.0.1 for internal services)
4. **Regular updates** of base images
5. **Monitor logs** for suspicious activity

### Environment Variables:
Ensure these are set securely in `.env.production`:
- `VRU_SECRET_KEY` - Change from default
- `VRU_DATABASE_PASSWORD` - Strong password
- `VRU_REDIS_PASSWORD` - Strong password
- `JWT_SECRET_KEY` - Strong secret

## 🚧 Migration from Old Setup

### Archive Old Files:
```bash
# Create archive directory
mkdir -p docker/archive

# Move old compose files
mv docker-compose*.yml docker/archive/ 2>/dev/null || true
mv backend/docker-compose.yml docker/archive/backend-compose.yml 2>/dev/null || true

# Keep only the unified file
cp docker/docker-compose.unified-fixed.yml docker-compose.yml
```

### Update Scripts:
```bash
# Update any existing scripts that reference old compose files
find . -name "*.sh" -exec sed -i 's/docker-compose\.yml/docker\/docker-compose\.unified-fixed\.yml/g' {} \;
```

## 📈 Performance Optimization

### Production Optimization:
- Enable Docker BuildKit: `export DOCKER_BUILDKIT=1`
- Use multi-stage builds (already implemented)
- Optimize resource limits in compose file
- Use production-optimized base images

### Development Optimization:
- Use volume mounts for hot reload
- Reduce worker counts
- Enable debug logging
- Use lighter development images

## 🔄 Updates and Maintenance

### Update Process:
1. **Backup data**: `docker compose -f docker/docker-compose.unified-fixed.yml exec postgres pg_dump`
2. **Stop services**: `docker compose -f docker/docker-compose.unified-fixed.yml down`
3. **Pull updates**: `git pull origin main`
4. **Rebuild**: `docker compose -f docker/docker-compose.unified-fixed.yml up --build -d`
5. **Verify health**: Check all endpoints

### Regular Maintenance:
```bash
# Clean unused resources (weekly)
docker system prune -f

# Update base images (monthly)
docker compose -f docker/docker-compose.unified-fixed.yml pull
docker compose -f docker/docker-compose.unified-fixed.yml up -d

# Backup database (daily)
docker compose -f docker/docker-compose.unified-fixed.yml exec postgres pg_dump -U vru_user vru_validation > backup.sql
```

---

## 🎉 Success Indicators

Your deployment is successful when:
- ✅ All containers show "healthy" status
- ✅ Frontend loads at http://155.138.239.131:3000
- ✅ Backend API docs accessible at http://155.138.239.131:8000/docs
- ✅ Health checks pass: `curl -f http://localhost:8000/health`
- ✅ No error messages in logs
- ✅ Database connections established
- ✅ File uploads work correctly

**Congratulations! Your VRU AI Model Validation Platform is now running! 🚀**