# AI Model Validation Platform - Quick Start

## 🚀 Start the Platform (30 seconds)

```bash
# 1. Make script executable (first time only)
chmod +x start.sh

# 2. Start the platform
./start.sh start simple

# 3. Wait for services to start (~2-3 minutes)
# The script will show progress and final URLs
```

## 📱 Access Your Platform

Once started, access these URLs:

| Service | URL | Purpose |
|---------|-----|---------|
| **🖥️ Frontend** | http://localhost:3000 | Main application |
| **🔗 Backend API** | http://localhost:8000/api | REST API |
| **📚 API Docs** | http://localhost:8000/docs | Interactive docs |
| **❤️ Health Check** | http://localhost:8000/health | Status |

## ⚡ Common Commands

```bash
# Check if services are running
./start.sh status

# View logs
./start.sh logs

# Stop all services
./start.sh stop

# Start with annotation tool
./start.sh start full

# Get help
./start.sh help
```

## 🔧 Quick Troubleshooting

**Services not starting?**
```bash
# Check ports are free
./start.sh stop
# Wait 30 seconds, then try again
./start.sh start simple
```

**Need help?**
```bash
./start.sh help
# Or see full guide: docs/STARTUP_GUIDE.md
```

## 📋 Prerequisites

- **Docker & Docker Compose** installed
- **Ports available**: 3000, 8000, 5432, 6379
- **8GB+ RAM recommended**

## 🎯 Two Deployment Options

### Simple Mode (Recommended)
- ✅ Frontend + Backend + Database + Redis
- ✅ Perfect for development and testing
- ✅ Fast startup (~2-3 minutes)

### Full Mode
- ✅ All simple mode services
- ✅ CVAT annotation tool (port 8080)
- ✅ Complete workflow capabilities
- ⏱️ Longer startup (~5-7 minutes)

---

**Need more details?** See the complete guide: [`docs/STARTUP_GUIDE.md`](docs/STARTUP_GUIDE.md)