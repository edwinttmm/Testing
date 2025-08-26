# Database URL Migration Guide

## Overview
This guide provides step-by-step instructions for migrating localhost URLs to production URLs in your backend database. The migration system ensures data integrity with backup and rollback capabilities.

## Quick Start

### 1. Check Current Status
```bash
# Using CLI
npm run migrate status

# Using API
curl http://155.138.239.131:8000/api/migrations/status
```

### 2. Run Dry Run (Preview Changes)
```bash
# Using CLI
npm run migrate dry-run

# Using API
curl -X POST http://155.138.239.131:8000/api/migrations/execute \
  -H "Content-Type: application/json" \
  -d '{"dryRun": true}'
```

### 3. Execute Migration
```bash
# Using CLI (with confirmation)
npm run migrate execute

# Using CLI (skip confirmation)
npm run migrate execute --force

# Using API
curl -X POST http://155.138.239.131:8000/api/migrations/execute \
  -H "Content-Type: application/json" \
  -d '{"migrationName": "001_fix_localhost_urls", "dryRun": false}'
```

### 4. Validate Results
```bash
# Using CLI
npm run migrate validate

# Using API
curl -X POST http://155.138.239.131:8000/api/migrations/validate
```

## Detailed Workflow

### Phase 1: Analysis and Planning

#### 1.1 Analyze Database Schema
Identify all tables and columns containing localhost URLs:

```bash
npm run migrate analyze
```

**Expected Output:**
```
📊 SCHEMA ANALYSIS RESULTS
==========================
URL Columns Found: 2

1. Table: videos
   Column: url
   Type: TEXT
   Sample: http://localhost:8000/uploads/video1.mp4

2. Table: videos
   Column: thumbnail_url
   Type: TEXT
   Sample: http://localhost:8000/uploads/thumb1.jpg

📋 Affected Tables: videos
```

#### 1.2 Review Current Status
Get comprehensive status overview:

```bash
npm run migrate status
```

**Expected Output:**
```
📊 MIGRATION STATUS
==================
Last Migration: None
Status: Not initialized
URL Columns Found: 2
Localhost URLs: 150
Production URLs: 0

📋 URL COLUMNS DETECTED
=======================
videos.url: http://localhost:8000/uploads/video1.mp4...
videos.thumbnail_url: http://localhost:8000/uploads/thumb1.jpg...

⚠️  MIGRATION REQUIRED
```

### Phase 2: Safety Preparations

#### 2.1 Create Manual Backup
Create a backup before proceeding:

```bash
npm run migrate backup pre_migration_backup
```

#### 2.2 Run Dry Run
Preview what the migration will do:

```bash
npm run migrate dry-run
```

**Expected Output:**
```
✅ DRY RUN SUCCESSFUL
===================
Migration: 001_fix_localhost_urls
Backup File: backup_001_fix_localhost_urls_2025-08-26.sql

📋 Migration Preview:
---------------------
-- Migration: Fix localhost URLs to production URLs
-- Version: 001
-- Description: Update all localhost URLs to production server URLs

UPDATE videos 
SET url = REPLACE(
    REPLACE(url, 'http://localhost:8000', 'http://155.138.239.131:8000'),
    'http://127.0.0.1:8000', 'http://155.138.239.131:8000'
)
WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%';

💡 Run with "execute" command to apply changes
```

### Phase 3: Migration Execution

#### 3.1 Execute Migration
Apply the migration changes:

```bash
npm run migrate execute
```

**Interactive Process:**
```
🚀 Executing migration: 001_fix_localhost_urls

⚠️  This will modify your database. Make sure you have a backup!
   Use --force flag to skip this warning

Continue? (y/N): y
```

**Expected Output:**
```
✅ MIGRATION COMPLETED
=====================
Migration: 001_fix_localhost_urls
Execution Time: 1250ms
Affected Rows: 150
Backup File: backup_001_fix_localhost_urls_2025-08-26T14-05-17.sql

🔍 Validating results...
✅ Validation passed - all URLs migrated successfully
```

#### 3.2 Validate Migration Results
Verify the migration was successful:

```bash
npm run migrate validate
```

**Expected Output:**
```
📊 VALIDATION RESULTS
====================
Total URLs: 150
Production URLs: 150
Localhost URLs: 0
Status: ✅ PASSED

📋 TABLE BREAKDOWN
==================
videos:
  Total URLs: 100
  Localhost URLs: 0
  Production URLs: 100

📈 MIGRATION STATISTICS
=======================
videos.url: 100 records (completed)
videos.thumbnail_url: 50 records (completed)
```

### Phase 4: Verification and Testing

#### 4.1 Test Application Functionality
1. Restart your backend server
2. Test video playback functionality
3. Verify thumbnail loading
4. Check API responses for correct URLs

#### 4.2 Sample API Test
```bash
# Test a video endpoint to verify URLs
curl http://155.138.239.131:8000/api/videos/1

# Expected response with production URLs:
{
  "id": 1,
  "title": "Sample Video",
  "url": "http://155.138.239.131:8000/uploads/video1.mp4",
  "thumbnail_url": "http://155.138.239.131:8000/uploads/thumb1.jpg"
}
```

## API Endpoints

### Base URL: `http://155.138.239.131:8000/api/migrations`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Get migration system status |
| POST | `/analyze` | Analyze database schema |
| POST | `/execute` | Execute migration |
| POST | `/validate` | Validate migration results |
| POST | `/rollback` | Rollback migration |
| GET | `/history` | Get migration history |
| POST | `/backup` | Create manual backup |
| GET | `/health` | Health check |
| GET | `/docs` | API documentation |

### API Usage Examples

#### Execute Migration via API
```bash
curl -X POST http://155.138.239.131:8000/api/migrations/execute \
  -H "Content-Type: application/json" \
  -d '{
    "migrationName": "001_fix_localhost_urls",
    "dryRun": false
  }'
```

#### Get Migration Status
```bash
curl http://155.138.239.131:8000/api/migrations/status | jq
```

#### Validate Results
```bash
curl -X POST http://155.138.239.131:8000/api/migrations/validate | jq
```

## Rollback Procedures

### If Migration Needs to be Reversed

#### 1. Check Migration History
```bash
npm run migrate history
```

#### 2. Rollback Migration
```bash
npm run migrate rollback 001_fix_localhost_urls
```

**Expected Output:**
```
✅ ROLLBACK COMPLETED
====================
Migration 001_fix_localhost_urls rolled back successfully
Backup File: backup_001_fix_localhost_urls_2025-08-26T14-05-17.sql
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Migration already executed"
**Solution:** Check if migration is actually needed:
```bash
npm run migrate status
```
If URLs are already migrated, no action needed.

#### Issue: "Backup creation failed"
**Solution:** Check disk space and permissions:
```bash
ls -la backend/backups/
df -h
```

#### Issue: "Some URLs not migrated"
**Solution:** 
1. Check validation output for specific issues
2. Review migration logs
3. Run schema analysis to find missed columns

#### Issue: "Migration takes too long"
**Solution:**
1. Check database size and indexes
2. Consider running during maintenance window
3. Monitor system resources during execution

### Advanced Troubleshooting

#### Check Migration Logs
```sql
-- Connect to database and check logs
SELECT * FROM migration_logs 
WHERE migration_name = '001_fix_localhost_urls' 
ORDER BY executed_at DESC;
```

#### Manually Check URLs
```sql
-- Check for remaining localhost URLs
SELECT id, url FROM videos 
WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%'
LIMIT 10;
```

## Security Considerations

### API Key Protection (Optional)
To secure migration endpoints, set an API key:

```bash
# Set environment variable
export MIGRATION_API_KEY="your-secure-api-key"

# Use in API calls
curl -X POST http://155.138.239.131:8000/api/migrations/execute \
  -H "X-API-Key: your-secure-api-key" \
  -H "Content-Type: application/json" \
  -d '{"dryRun": true}'
```

### Database Backup Storage
- Backups are stored in `backend/backups/`
- Ensure this directory has appropriate permissions
- Consider encrypting backups for sensitive data
- Implement backup retention policies

## Performance Optimization

### Large Database Considerations
For databases with many URLs (>10,000):

1. **Run during maintenance window**
2. **Monitor system resources**
3. **Consider batch processing**
4. **Enable database logging**

### Monitoring Migration Progress
```bash
# Monitor database activity during migration
watch -n 1 'ps aux | grep sqlite'

# Check migration logs in real-time
tail -f backend/logs/migration.log
```

## Integration with Existing Systems

### Adding to Express.js Application
```javascript
// In your main server file
const migrationRoutes = require('./routes/migrations');

// Initialize with your database connection
app.use('/api/migrations', migrationRoutes(database));
```

### Package.json Scripts
Add these scripts to your `package.json`:

```json
{
  "scripts": {
    "migrate": "node backend/scripts/migration-cli.js",
    "migrate:status": "node backend/scripts/migration-cli.js status",
    "migrate:dry-run": "node backend/scripts/migration-cli.js dry-run",
    "migrate:execute": "node backend/scripts/migration-cli.js execute",
    "migrate:validate": "node backend/scripts/migration-cli.js validate"
  }
}
```

## Post-Migration Checklist

- [ ] All localhost URLs converted to production URLs
- [ ] Application functionality tested
- [ ] API endpoints returning correct URLs
- [ ] Video playback working
- [ ] Thumbnail loading functional
- [ ] Migration logs reviewed
- [ ] Backup files secured
- [ ] Frontend URL fixing code removed (if applicable)
- [ ] Documentation updated
- [ ] Team notified of changes

## Support and Maintenance

### Regular Monitoring
Set up periodic checks to prevent localhost URLs from being re-introduced:

```bash
# Add to cron job for weekly checks
0 2 * * 0 cd /path/to/project && npm run migrate validate
```

### Log Management
- Monitor migration logs for issues
- Set up alerts for failed migrations
- Archive old backups periodically

## Conclusion

This migration system provides a safe, reliable way to convert localhost URLs to production URLs in your database. The combination of CLI and API interfaces, comprehensive validation, and rollback capabilities ensures data integrity throughout the process.

For additional support or custom migration needs, refer to the API documentation endpoint: `GET /api/migrations/docs`