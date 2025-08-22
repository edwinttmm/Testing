# Deployment Guide

## Overview

This guide provides instructions for deploying the AI Model Validation Platform in various environments.

## Prerequisites

- Python 3.8+
- Node.js 18+
- PostgreSQL (for production) or SQLite (for development)
- Docker (optional)

## Backend Deployment

### Environment Variables

Create a `.env` file in the backend directory:

```bash
# Database
AIVALIDATION_DATABASE_URL=postgresql://user:password@localhost/aivalidation
AIVALIDATION_DATABASE_POOL_SIZE=10
AIVALIDATION_DATABASE_MAX_OVERFLOW=20

# API Configuration
AIVALIDATION_API_HOST=0.0.0.0
AIVALIDATION_API_PORT=8000
AIVALIDATION_API_DEBUG=False

# CORS
AIVALIDATION_CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# File Upload
AIVALIDATION_MAX_FILE_SIZE=104857600
AIVALIDATION_UPLOAD_DIRECTORY=/app/uploads

# Security
AIVALIDATION_SECRET_KEY=your-very-secure-secret-key-here

# Logging
AIVALIDATION_LOG_LEVEL=INFO
AIVALIDATION_LOG_FILE=/var/log/aivalidation/app.log
```

### Installation

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Initialize database:
```bash
python -c "from database import Base, engine; Base.metadata.create_all(bind=engine)"
```

3. Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Production Deployment

For production, use a process manager like systemd or supervisor:

```ini
# /etc/systemd/system/aivalidation.service
[Unit]
Description=AI Model Validation Platform API
After=network.target

[Service]
Type=simple
User=aivalidation
WorkingDirectory=/opt/aivalidation/backend
Environment=PATH=/opt/aivalidation/venv/bin
ExecStart=/opt/aivalidation/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

## Frontend Deployment

### Build for Production

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Build the application:
```bash
npm run build
```

3. Serve with a web server (nginx example):

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        root /opt/aivalidation/frontend/build;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Docker Deployment

### Using Docker Compose

```yaml
version: '3.8'

services:
  database:
    image: postgres:15
    environment:
      POSTGRES_DB: aivalidation
      POSTGRES_USER: aivalidation
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - AIVALIDATION_DATABASE_URL=postgresql://aivalidation:secure_password@database:5432/aivalidation
      - AIVALIDATION_SECRET_KEY=your-secure-secret-key
    volumes:
      - ./uploads:/app/uploads
    ports:
      - "8000:8000"
    depends_on:
      - database

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

### Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads logs data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:18-alpine as build

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Database Migrations

The application uses SQLAlchemy with automatic table creation. For production deployments, consider using Alembic for database migrations:

```bash
# Install Alembic
pip install alembic

# Initialize Alembic
alembic init alembic

# Generate migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

## Monitoring and Logging

### Health Checks

The API provides health check endpoints:
- `GET /health` - Basic health check
- `GET /api/dashboard/stats` - Application statistics

### Logging

Logs are configured through environment variables:
- Set `AIVALIDATION_LOG_LEVEL` to control verbosity
- Set `AIVALIDATION_LOG_FILE` to specify log file location

### Monitoring

Consider implementing:
- Application performance monitoring (APM)
- Database monitoring
- File system monitoring for uploads
- API endpoint monitoring

## Security Considerations

1. **SSL/TLS**: Use HTTPS in production
2. **Database**: Use strong passwords and restrict database access
3. **File Uploads**: Validate file types and sizes
4. **CORS**: Configure appropriate CORS origins
5. **Secrets**: Use environment variables for sensitive data
6. **Access Control**: Implement proper network security

## Scaling

### Horizontal Scaling

1. **Load Balancer**: Use nginx or HAProxy
2. **Multiple Backend Instances**: Run multiple API servers
3. **Database**: Use connection pooling and read replicas
4. **File Storage**: Consider object storage (S3, MinIO)

### Performance Optimization

1. **Database Indexes**: Ensure proper indexing (already implemented)
2. **Caching**: Implement Redis caching for frequently accessed data
3. **CDN**: Use CDN for static assets
4. **Compression**: Enable gzip compression

## Backup and Recovery

1. **Database**: Regular automated backups
2. **File Uploads**: Backup uploaded videos and generated data
3. **Configuration**: Version control all configuration files

## Troubleshooting

### Common Issues

1. **Database Connection**: Check database credentials and network connectivity
2. **File Upload Errors**: Verify file permissions and disk space
3. **CORS Errors**: Check CORS configuration in backend
4. **Performance Issues**: Monitor database queries and add indexes if needed

### Log Analysis

Check logs for:
- Database connection errors
- File upload failures
- API endpoint errors
- Authentication issues (if re-enabled)

### Health Check Failures

If health checks fail:
1. Check application logs
2. Verify database connectivity
3. Check file system permissions
4. Monitor system resources (CPU, memory, disk)

## Support

For issues and support:
1. Check application logs first
2. Verify configuration settings
3. Test with minimal configuration
4. Check network connectivity and firewall settings