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

## Getting Started

1. Clone the repository
2. Run `docker-compose up` to start all services
3. Access the frontend at `http://localhost:3000`
4. Access the API documentation at `http://localhost:8000/docs`

## Development

- Frontend: `cd frontend && npm start`
- Backend: `cd backend && uvicorn main:app --reload`
- Database: PostgreSQL on port 5432