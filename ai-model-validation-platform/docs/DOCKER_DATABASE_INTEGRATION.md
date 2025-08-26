# Docker Database Integration Guide

## Overview

The AI Model Validation Platform now supports proper Docker integration with the working SQLite database (`dev_database.db`). This ensures that the application runs with the same data in Docker containers as it does locally.

## Database Status

- **Working Database**: `backend/dev_database.db` (688KB)
- **Content**: 6 projects, 1 video, 11 database tables
- **Status**: ✅ Fully functional with all existing data preserved

## Integration Architecture

### Development Mode (SQLite)
- Uses the existing working `dev_database.db`
- Database mounted as volume for persistence
- Optimized for development workflow
- All existing data preserved

### Production Mode (PostgreSQL)
- Uses PostgreSQL for scalability
- Requires data migration (separate process)
- Configured for high-performance production workloads

## Usage Instructions

### 1. Development with SQLite (Recommended)

```bash
# Use SQLite with working data
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml up

# Background mode
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml up -d

# View logs
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml logs -f backend
```

### 2. Production with PostgreSQL

```bash
# Use PostgreSQL for production
docker-compose up

# Background mode
docker-compose up -d
```

### 3. Verification Commands

```bash
# Test database connectivity
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml exec backend python -c "import database; print('✅ Database connection OK')"

# Check database contents
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml exec backend python -c "
import sqlite3
conn = sqlite3.connect('./dev_database.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM projects')
print(f'Projects: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM videos')  
print(f'Videos: {cursor.fetchone()[0]}')
conn.close()
"

# Verify API health
curl http://localhost:8000/health
```

## Key Features

### Database Persistence
- Database changes persist across container restarts
- Volume mount: `./backend/dev_database.db:/app/dev_database.db`
- Automatic backup creation before Docker operations

### Environment Configuration
- SQLite mode: `AIVALIDATION_DATABASE_URL=sqlite:///./dev_database.db`
- PostgreSQL mode: Full connection string with pool configuration
- Automatic detection and configuration

### Safety Features
- Automatic backup creation before integration
- Database connectivity testing
- Permission verification
- Content validation

## File Structure

```
/home/user/Testing/ai-model-validation-platform/
├── backend/
│   ├── dev_database.db                    # Working SQLite database (688KB)
│   ├── dev_database.db.docker_backup_*    # Automatic backups
│   └── database.py                        # Database configuration
├── docker-compose.yml                     # Main compose file (PostgreSQL)
├── docker-compose.sqlite.yml              # SQLite override
├── scripts/
│   └── docker-sqlite-integration.sh       # Integration verification
└── docs/
    └── DOCKER_DATABASE_INTEGRATION.md     # This documentation
```

## Configuration Details

### SQLite Override Configuration
The `docker-compose.sqlite.yml` file provides:
- SQLite database URL override
- Volume mounting for database persistence
- Disables PostgreSQL service
- Maintains Redis for caching

### Database Connection Logic
The application automatically detects the database type:
1. Checks for `AIVALIDATION_DATABASE_URL` environment variable
2. Falls back to `DATABASE_URL`
3. Uses SQLite connection parameters for `.db` files
4. Uses PostgreSQL pool configuration for `postgresql://` URLs

## Troubleshooting

### Database Not Found
```bash
# Check if database exists
ls -la backend/dev_database.db

# Run integration script
./scripts/docker-sqlite-integration.sh
```

### Permission Issues
```bash
# Fix database permissions
chmod 664 backend/dev_database.db
chown $USER:$USER backend/dev_database.db
```

### Container Connection Issues
```bash
# Check container logs
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml logs backend

# Restart containers
docker-compose -f docker-compose.yml -f docker-compose.sqlite.yml restart backend
```

### Database Corruption
```bash
# Use automatic backup
cp backend/dev_database.db.docker_backup_* backend/dev_database.db

# Verify database integrity
sqlite3 backend/dev_database.db "PRAGMA integrity_check;"
```

## Migration Path (SQLite → PostgreSQL)

For production deployment with PostgreSQL:

1. Export SQLite data:
```bash
sqlite3 backend/dev_database.db .dump > data_export.sql
```

2. Adapt SQL for PostgreSQL:
```bash
# Modify data_export.sql for PostgreSQL compatibility
# Handle differences in data types, syntax, etc.
```

3. Import to PostgreSQL:
```bash
docker-compose exec postgres psql -U postgres -d vru_validation -f /tmp/data_export.sql
```

## Integration Verification

Run the integration script to verify everything is working:

```bash
./scripts/docker-sqlite-integration.sh
```

This script:
- ✅ Verifies database file exists and is readable
- ✅ Checks database contents (projects, videos, tables)
- ✅ Tests database connectivity
- ✅ Creates automatic backup
- ✅ Validates Docker configuration files
- ✅ Provides usage instructions

## Security Notes

- Database file permissions are set to 664 (read/write for user/group)
- Automatic backups created before any operations
- No sensitive data exposed in Docker environment variables
- SQLite file is mounted read-write for full functionality

## Performance Considerations

- SQLite is suitable for development and small-scale deployments
- For high-concurrency production use, migrate to PostgreSQL
- Database file is on host filesystem (fast access)
- Redis still used for caching and session management

---

**Status**: ✅ Integration Complete  
**Database**: dev_database.db (688KB, 6 projects, 1 video)  
**Last Updated**: 2025-08-26  
**Integration Agent**: Docker Database Integration Agent