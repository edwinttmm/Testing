# AI Model Validation Platform for Vehicle VRU Detection

A comprehensive, web-based enterprise system for validating the performance of vehicle-mounted cameras in detecting Vulnerable Road Users (VRUs) and monitoring driver behavior.

## Architecture

- **Frontend**: React with TypeScript
- **Backend**: FastAPI with Python
- **Database**: PostgreSQL
- **AI Model**: YOLOv8 integration
- **Annotation**: CVAT integration
- **Hardware Interface**: REST API for Raspberry Pi

## Project Structure

```
ai-model-validation-platform/
├── frontend/                 # React TypeScript frontend
├── backend/                  # FastAPI Python backend
├── database/                 # Database schemas and migrations
├── models/                   # AI model configurations
├── docs/                     # Documentation
├── scripts/                  # Deployment and utility scripts
└── docker-compose.yml        # Container orchestration
```

## Core Features

1. **Project & Camera Configuration**
2. **Ground Truth Management**
3. **Test Execution & Monitoring Interface**
4. **Real-time Signal Ingestion & Comparison**
5. **Results, Reporting, and Analytics**
6. **Dataset Management & Annotation Workflow**
7. **Comprehensive Audit & Activity Logging**

## 🚀 Quick Start

### Development Environment (Localhost)

```bash
# 1. Clone the repository
git clone <repository-url>
cd ai-model-validation-platform

# 2. Install frontend dependencies
cd frontend
npm install

# 3. Start backend server
cd ../backend
python main.py
# Backend will run on http://localhost:8000

# 4. Start frontend development server
cd ../frontend
npm start
# Frontend will run on http://localhost:3000

# 5. Verify everything is working
# Open http://localhost:3000 and check Configuration Validator
```

### Production Environment (155.138.239.131)

```bash
# 1. Build for production
cd frontend
NODE_ENV=production npm run build

# 2. Start backend on production server
cd ../backend
cp .env.production .env
python main.py

# 3. Serve frontend
npx serve -s build -p 3000

# 4. Access at http://155.138.239.131:3000
```

### Custom Environment Setup

```bash
# 1. Create local configuration
cp frontend/.env.local.example frontend/.env.local
cp backend/.env.local.example backend/.env.local

# 2. Edit .env.local files with your URLs
# Frontend: REACT_APP_API_URL=http://your-server:8000
# Backend: API_HOST=0.0.0.0

# 3. Start normally
npm start
```

## 🔧 Environment Configuration

The platform now features **bulletproof environment separation**:

- **Automatic environment detection**
- **Smart URL generation with fallbacks**
- **Runtime configuration validation**
- **Cross-environment video handling**
- **Real-time connectivity monitoring**

### Environment Files

```
frontend/
├── .env                     # Base configuration
├── .env.development         # Development (localhost:8000)
├── .env.production         # Production (155.138.239.131:8000)
└── .env.local              # Local overrides (git-ignored)

backend/
├── .env                     # Base configuration
├── .env.development         # Development settings
├── .env.production         # Production settings  
└── .env.local              # Local overrides (git-ignored)
```

### Configuration Validator

Add real-time environment monitoring to your app:

```tsx
import ConfigurationValidator from './components/ConfigurationValidator';

<ConfigurationValidator 
  showDetails={true}
  autoRefresh={true}
  refreshInterval={30000}
/>
```

## 📖 Documentation

- **[Environment Setup Guide](docs/ENVIRONMENT_SETUP.md)** - Comprehensive configuration guide
- **[Troubleshooting Guide](docs/TROUBLESHOOTING_GUIDE.md)** - Solutions for common issues
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs

## 🐛 Troubleshooting

### Common Issues

❌ **"API connection failed"**
```bash
# Check if backend is running
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

❌ **"Video URL not loading"**
```bash
# Check video files exist
ls -la backend/uploads/
# Test video URL
curl -I http://localhost:8000/uploads/video-id.mp4
```

❌ **"Configuration validation errors"**
- Enable debug mode: `REACT_APP_DEBUG=true`
- Check Configuration Validator component
- Review environment file syntax

**📞 For detailed troubleshooting**: See [Troubleshooting Guide](docs/TROUBLESHOOTING_GUIDE.md)

## 🛠️ Development

### Frontend Development
```bash
cd frontend
npm start                    # Development server (localhost:3000)
npm test                     # Run tests
npm run build               # Production build
npm run build:analyze       # Bundle analysis
```

### Backend Development
```bash
cd backend
python main.py              # Development server (localhost:8000)
python -m pytest           # Run tests
uvicorn main:app --reload  # Alternative startup
```

### Environment Testing
```bash
# Test API connectivity
curl http://localhost:8000/health

# Test WebSocket (if applicable)
curl http://localhost:8001/socket.io/

# Test video endpoint
curl -I http://localhost:8000/uploads/test.mp4
```