# AI Model Validation Platform - Quick Start Guide

## Prerequisites
- Docker Desktop installed and running
- Git installed

## 🚀 Run Complete Application (Recommended)

**This runs the full stack: Frontend + Backend + Database + AI Services**

1. **Clone the repository**
   ```bash
   git clone https://github.com/edwinttmm/Testing.git
   cd Testing/ai-model-validation-platform
   ```

2. **Start all services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the complete application**
   - **Frontend (Main App)**: http://localhost:3000
   - **Backend API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs
   - **Database**: PostgreSQL on port 5432
   - **Redis Cache**: port 6379

4. **Check service status**
   ```bash
   docker-compose ps
   ```

## Alternative: Frontend Only

If you only want to run the frontend:

1. **Clone and navigate to frontend**
   ```bash
   git clone https://github.com/edwinttmm/Testing.git
   cd Testing/ai-model-validation-platform/frontend
   ```

2. **Build and run frontend**
   ```bash
   docker build -t frontend-image .
   docker run -p 3000:3000 frontend-image
   ```

3. **Access frontend only**: http://localhost:3000

## Alternative: Local Development

For development with Node.js:

1. **Clone repository**
   ```bash
   git clone https://github.com/edwinttmm/Testing.git
   cd Testing/ai-model-validation-platform/frontend
   ```

2. **Install and run**
   ```bash
   npm install
   npm start
   ```

## Troubleshooting

- If you get "craco: not found" error, ensure you're using the latest Docker image
- If port 3000 is busy, change the port: `docker run -p 3001:3000 frontend-image`
- For Windows users, ensure Docker Desktop is running before executing Docker commands

## Project Structure
```
frontend/
├── public/          # Static assets
├── src/             # React source code
├── package.json     # Dependencies and scripts
├── Dockerfile       # Docker configuration
└── .dockerignore    # Docker ignore rules
```

## Features
- Modern React 19.1 with TypeScript
- Material-UI components
- Data visualization with Recharts
- Real-time updates with Socket.IO
- Responsive design for all devices