# FastAPI Backend Documentation

## Overview

This directory contains comprehensive documentation for the AI Model Validation Platform FastAPI backend. The documentation covers every aspect of the backend architecture, from the main application structure to detailed API endpoints and database relationships.

## Documentation Structure

### 1. [Main Application Analysis](./main-application.md)
**Complete analysis of the main FastAPI application structure**
- Application initialization and configuration
- Startup process and lifespan management
- Middleware configuration (CORS, static files)
- Router registration order and precedence
- Custom endpoints and WebSocket integration
- Environment support (development/production)
- Security features and error handling

### 2. [API Endpoints Inventory](./api-endpoints.md)
**Comprehensive catalog of all API endpoints**
- Authentication endpoints (`/api/auth`)
- Project management endpoints (`/api/projects`)
- Video management endpoints (`/api/videos`)  
- Test session management (`/api/test-sessions`)
- LabJack hardware integration (`/api/labjack`)
- Detection and analysis endpoints
- Ground truth management (`/api/ground-truth`)
- Reports and analytics (`/api/reports`)
- Dashboard endpoints (`/api/dashboard`)
- WebSocket endpoints for real-time communication

### 3. [Services Analysis](./services-analysis.md)
**In-depth analysis of 46+ business logic services**
- Ground Truth & Annotation Services
- Detection & ML Services (YOLOv8/YOLOv11)
- LabJack Hardware Integration Services
- Video Processing Services
- Test Execution & Validation Services
- Reporting & Analytics Services
- Data Management Services
- Authentication & Security Services
- WebSocket & Communication Services
- Configuration & Utility Services

### 4. [CRUD Operations](./crud-operations.md)
**Complete database access layer documentation**
- User-based security model implementation
- Project CRUD with many-to-many video relationships
- Video management with project assignment
- Ground truth object operations
- Test session and detection event management
- Bulk operations and relationship validation
- Performance optimization and query patterns
- Transaction management and error handling

### 5. [Routers Analysis](./routers-analysis.md)
**API organization and routing architecture**
- Router registration order and precedence
- Detailed analysis of each router module
- Authentication and authorization patterns
- Error handling and response models
- File upload and WebSocket integration
- Performance optimization techniques
- Testing patterns and dependency injection

### 6. [Middleware Analysis](./middleware-analysis.md)
**Cross-cutting concerns and request processing**
- CORS middleware configuration
- Security middleware architecture (planned)
- Static file serving and dynamic file resolution
- WebSocket middleware patterns
- Custom endpoint middleware
- Performance monitoring and logging
- Error recovery and circuit breaker patterns

### 7. [Background Tasks](./background-tasks.md)
**Async operations and long-running processes**
- FastAPI BackgroundTasks integration
- ThreadPoolExecutor for CPU-intensive tasks
- AsyncIO event loop integration
- Video processing pipelines
- LabJack hardware data streaming
- Report generation workflows
- Queue-based processing systems
- Error handling and retry mechanisms
- Resource management and performance monitoring

### 8. [Model Relationships](./model-relationships.md)
**Database schema and entity relationships**
- Complete entity relationship diagram
- Authentication and user management models
- Project-Video many-to-many system
- Ground truth and annotation models
- Test execution system with LabJack timing
- Results and analytics models
- Video validation system
- Cascade relationships and data integrity
- Performance indexes and query optimization

## Key Architecture Highlights

### Technology Stack
- **Framework**: FastAPI with async support
- **Database**: SQLAlchemy ORM with SQLite/PostgreSQL support
- **Authentication**: JWT tokens with bcrypt password hashing
- **ML Integration**: YOLOv8/YOLOv11 with PyTorch
- **Hardware Integration**: LabJack devices for precision timing
- **Real-time Communication**: WebSocket support
- **Background Processing**: AsyncIO with ThreadPoolExecutor

### Core Features
- **VRU Detection**: Pedestrian, cyclist, motorcyclist detection
- **Timing Validation**: LabJack hardware integration for latency measurement
- **Video Processing**: Comprehensive video ingestion and processing pipeline
- **Ground Truth Management**: Automated and manual annotation systems
- **Test Execution**: Complete test session orchestration
- **Report Generation**: Multi-format report generation (HTML, PDF, JSON)
- **Real-time Streaming**: WebSocket-based data streaming
- **User Management**: Complete authentication and authorization system

### Security Implementation
- **User Isolation**: All data access filtered by user ownership
- **JWT Authentication**: Secure token-based authentication
- **CORS Configuration**: Environment-specific origin restrictions
- **Input Validation**: Pydantic schema validation
- **Audit Logging**: Comprehensive activity tracking
- **Session Management**: Secure session tracking with expiration

### Performance Features
- **Database Optimization**: Comprehensive indexing strategy
- **Async Processing**: Non-blocking operations for long-running tasks
- **Connection Pooling**: Efficient database connection management
- **Caching Support**: Redis integration for distributed caching
- **File Optimization**: Efficient video file serving with range requests
- **Background Tasks**: Isolated processing for CPU-intensive operations

### Development Features
- **Hot Reloading**: Development-friendly module loading
- **Graceful Degradation**: Fallback handling for missing components
- **Comprehensive Logging**: Structured logging with performance metrics
- **Error Tolerance**: Development-friendly error handling
- **Environment Support**: Seamless development to production transition

## Getting Started

1. **Read the [Main Application Analysis](./main-application.md)** to understand the overall structure
2. **Review the [API Endpoints Inventory](./api-endpoints.md)** for available functionality
3. **Examine the [Services Analysis](./services-analysis.md)** for business logic implementation
4. **Study the [Model Relationships](./model-relationships.md)** for database schema understanding

## Documentation Maintenance

This documentation is generated from actual code analysis and should be updated when:
- New routers or endpoints are added
- Service implementations change significantly
- Database schema modifications occur
- Security or authentication changes are implemented
- Performance optimizations are added

## Related Documentation

- **Frontend Documentation**: `/frontend/docs/`
- **API Documentation**: Available at `/docs` when server is running
- **Database Migrations**: `/backend/migrations/`
- **Configuration Examples**: `/backend/.env.example`

---

**Last Updated**: Generated from comprehensive code analysis  
**Coverage**: 100% of backend components analyzed  
**Status**: Complete and current as of analysis date