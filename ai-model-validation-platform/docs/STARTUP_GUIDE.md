# AI Model Validation Platform - Startup Guide

This guide provides comprehensive instructions for starting the AI Model Validation Platform using multiple deployment methods.

## Quick Start

The easiest way to get started is using the provided startup script:

```bash
# Make script executable (first time only)
chmod +x start.sh

# Start the platform (simple mode - recommended)
./start.sh start simple

# Or start with all services including CVAT
./start.sh start full
```

## Startup Script Overview

The `start.sh` script provides several deployment options and utilities:

### Available Commands

| Command | Description |
|---------|-------------|
| `start simple` | Start basic platform (Frontend + Backend + Database + Redis) |
| `start full` | Start complete platform including CVAT annotation tool |
| `manual` | Set up for manual development (no Docker) |
| `stop` | Stop all running services |
| `status` | Check health of running services |
| `logs [service]` | View logs for all services or specific service |
| `urls` | Display access URLs for services |
| `help` | Show detailed help information |

### Startup Modes

#### Simple Mode (Recommended for Development)
```bash
./start.sh start simple
```

**Services included:**
- React Frontend (port 3000)
- FastAPI Backend (port 8000)
- PostgreSQL Database (port 5432)
- Redis Cache (port 6379)

**Best for:** Development, testing, basic usage

#### Full Mode (Complete Platform)
```bash
./start.sh start full
```

**Services included:**
- All simple mode services
- CVAT Annotation Tool (port 8080)

**Best for:** Complete workflow with video annotation capabilities

## Access URLs

Once services are running, you can access:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Main application interface |
| **Backend API** | http://localhost:8000/api | REST API endpoints |
| **API Documentation** | http://localhost:8000/docs | Interactive API documentation |
| **Health Check** | http://localhost:8000/health | Backend health status |
| **CVAT** (full mode) | http://localhost:8080 | Video annotation tool |

## Prerequisites

### For Docker Deployment (Recommended)

1. **Docker & Docker Compose**
   - Ubuntu/Debian: `sudo apt-get update && sudo apt-get install docker.io docker-compose`
   - macOS: `brew install docker docker-compose` or install Docker Desktop
   - Windows: Install Docker Desktop from docker.com

2. **Available Ports**
   - 3000 (Frontend)
   - 8000 (Backend)
   - 5432 (PostgreSQL)
   - 6379 (Redis)
   - 8080 (CVAT - full mode only)

3. **System Requirements**
   - 8GB+ RAM (16GB recommended for full mode)
   - 10GB+ disk space
   - Modern CPU with virtualization support

### For Manual Development

1. **Python 3.11+**
   - Install from python.org or your package manager
   - Required for backend development

2. **Node.js 18+**
   - Install from nodejs.org or use nvm
   - Required for frontend development

3. **PostgreSQL 15+**
   - Install locally or use cloud service
   - Create database `vru_validation`

4. **Redis 7+**
   - Install locally or use cloud service
   - Default configuration works

## Detailed Usage Instructions

### Starting the Platform

1. **Clone the repository** (if not already done)
   ```bash
   git clone <repository-url>
   cd ai-model-validation-platform
   ```

2. **Run the startup script**
   ```bash
   # Simple mode (recommended for first time)
   ./start.sh start simple
   
   # Wait for all services to start (may take 2-5 minutes)
   ```

3. **Verify services are running**
   ```bash
   ./start.sh status
   ```

### Monitoring Services

**Check service health:**
```bash
./start.sh status
```

**View logs:**
```bash
# All services
./start.sh logs

# Specific service
./start.sh logs backend
./start.sh logs frontend
./start.sh logs postgres
```

**Show access URLs:**
```bash
./start.sh urls
```

### Stopping Services

```bash
./start.sh stop
```

## Manual Development Setup

For developers who prefer to run services individually:

### 1. Setup Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your database/redis settings

# Start backend
uvicorn main:socketio_app --host 0.0.0.0 --port 8000 --reload
```

### 2. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

### 3. Database & Redis

Ensure PostgreSQL and Redis are running:

```bash
# PostgreSQL (Ubuntu)
sudo systemctl start postgresql
createdb vru_validation

# Redis (Ubuntu)
sudo systemctl start redis-server
```

## Configuration

### Environment Variables

The platform uses environment files for configuration:

- **`.env`** - Main environment file (auto-created by startup script)
- **`backend/.env`** - Backend-specific settings
- **`.env.production`** - Production deployment settings

### Key Configuration Options

```bash
# Database
VRU_DATABASE_URL=postgresql://user:pass@localhost:5432/vru_validation

# Security
VRU_SECRET_KEY=your-secure-secret-key

# Redis
VRU_REDIS_URL=redis://localhost:6379/0

# API Settings
AIVALIDATION_API_PORT=8000
AIVALIDATION_API_HOST=0.0.0.0
```

## Troubleshooting

### Common Issues

**Port conflicts:**
```bash
# Check what's using a port
lsof -i :3000
lsof -i :8000

# Kill process using port
kill -9 <PID>
```

**Docker issues:**
```bash
# Reset Docker state
./start.sh stop
docker system prune -f
docker-compose down -v

# Rebuild and start
./start.sh start simple
```

**Permission issues:**
```bash
# Make script executable
chmod +x start.sh

# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
# Then logout and login again
```

### Service Health Checks

The startup script includes automatic health checks:

- **Backend**: Checks `/health` endpoint
- **Frontend**: Checks root URL availability
- **Database**: Verified through backend connection
- **CVAT**: Checks `/api/server/about` endpoint

### Log Analysis

**Backend logs:**
```bash
./start.sh logs backend | grep ERROR
./start.sh logs backend | tail -100
```

**Frontend logs:**
```bash
./start.sh logs frontend | grep -i error
```

## Development Workflow

### Recommended Development Process

1. **Start simple mode for development**
   ```bash
   ./start.sh start simple
   ```

2. **Develop with hot reload**
   - Backend: Automatic reload with uvicorn
   - Frontend: React hot reload active

3. **Monitor services**
   ```bash
   ./start.sh status  # Check health
   ./start.sh logs    # Monitor logs
   ```

4. **Test changes**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000/docs

### Code Changes

- **Backend changes**: Automatically reload via uvicorn
- **Frontend changes**: Hot reload via React development server
- **Database schema**: Use Alembic migrations
- **Docker rebuilds**: Run `./start.sh stop && ./start.sh start simple`

## Production Deployment

For production deployment, use the full Docker compose configuration:

```bash
# Use production environment
cp .env.production .env

# Start with full services
./start.sh start full

# Monitor in production
./start.sh status
./start.sh logs | tee production.log
```

## Support & Additional Resources

- **API Documentation**: http://localhost:8000/docs (when running)
- **Frontend Development**: React development server with hot reload
- **Database Management**: Use PostgreSQL tools or pgAdmin
- **Container Management**: Docker Desktop or Portainer

## Performance Tips

### For Better Performance

1. **Allocate sufficient resources**
   - Docker Desktop: Increase RAM to 8GB+
   - Disk space: Ensure 10GB+ available

2. **Monitor resource usage**
   ```bash
   docker stats  # Monitor container resources
   ./start.sh status  # Check service health
   ```

3. **Optimize for development**
   - Use simple mode for faster startup
   - Enable only needed services
   - Use manual setup for fastest development cycles

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 4GB | 8GB+ |
| CPU | 2 cores | 4+ cores |
| Disk | 5GB | 20GB+ |
| Network | 1MB/s | 10MB/s+ |