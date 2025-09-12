# Project-Video Many-to-Many Migration Execution Guide

## Overview

This guide provides step-by-step instructions for executing the comprehensive Project-Video many-to-many relationship migration. This migration transforms the existing one-to-many relationship between Projects and Videos into a flexible many-to-many relationship while preserving all existing data.

## Migration Components

### 📁 Files Included

1. **`data_backup_script.py`** - Creates comprehensive backup before migration
2. **`0004_project_video_many_to_many.py`** - Main Alembic migration script
3. **`data_integrity_validator.py`** - Validates data integrity after migration
4. **`migration_test_runner.py`** - Tests migration with sample data
5. **`MIGRATION_EXECUTION_GUIDE.md`** - This execution guide

### 🔄 Migration Changes

#### **New Structure:**
- **project_videos** junction table (many-to-many relationships)
- **Videos** table gets new fields: `camera_model`, `camera_view`, `lens_type`, `video_resolution`, `frame_rate`, `signal_type`
- **Projects** table removes deprecated fields: `camera_model`, `camera_view`, `lens_type`, `resolution`, `frame_rate`, `signal_type`
- Enhanced performance indexes for query optimization

#### **Data Migration:**
- Existing project-video relationships preserved in new junction table
- Project technical specifications migrated to individual video records
- All foreign key relationships updated
- Zero data loss guaranteed

## Pre-Migration Checklist

### 🛡️ Safety Requirements

- [ ] **Database backup created** (automatic via backup script)
- [ ] **Application downtime scheduled** (recommended 15-30 minutes)
- [ ] **Database connection pool drained** (stop all API services)
- [ ] **Disk space verified** (at least 2x current database size available)
- [ ] **Rollback plan prepared** (migration includes automatic rollback)

### 📋 Environment Verification

```bash
# Verify Python environment
python --version  # Should be 3.8+

# Verify required packages
pip install sqlalchemy alembic

# Verify database accessibility
sqlite3 /path/to/your/database.db ".tables"

# Check current migration state
alembic current
```

## Step-by-Step Execution

### Step 1: Pre-Migration Validation

```bash
# Navigate to migration directory
cd /path/to/migrations/

# Run pre-migration data integrity check
python data_integrity_validator.py

# Expected output: Overall score should be >80%
```

### Step 2: Create Data Backup

```bash
# Create comprehensive backup
python data_backup_script.py

# Verify backup creation
ls -la ./migration_backups/

# Expected files:
# - database_backup_YYYYMMDD_HHMMSS.db
# - projects_backup_YYYYMMDD_HHMMSS.json  
# - videos_backup_YYYYMMDD_HHMMSS.json
# - project_video_relationships_YYYYMMDD_HHMMSS.json
# - backup_metadata_YYYYMMDD_HHMMSS.json
```

### Step 3: Stop Application Services

```bash
# Stop backend services
sudo systemctl stop your-api-service

# Stop any database connection pools
# (Application-specific commands)

# Verify no active connections
sudo netstat -tulpn | grep :5432  # PostgreSQL
# OR for SQLite: ensure no processes have database file open
sudo lsof /path/to/database.db
```

### Step 4: Run Migration

#### Option A: Using Alembic (Recommended)

```bash
# Navigate to project root with alembic.ini
cd /path/to/project/backend/

# Run the migration
alembic upgrade head

# Expected output:
# INFO [alembic.runtime.migration] Running upgrade 0003 -> 0004, Project-Video Many-to-Many Relationship Migration
# INFO [migration_script] Starting Project-Video many-to-many migration...
# INFO [migration_script] Creating project_videos junction table...
# INFO [migration_script] Adding new fields to videos table...
# INFO [migration_script] Migrating existing project-video relationships...
# INFO [migration_script] Found N existing relationships to migrate
# INFO [migration_script] Data migration completed successfully
# INFO [migration_script] Removing old project_id foreign key from videos table...
# INFO [migration_script] Removing deprecated fields from projects table...
# INFO [migration_script] Creating performance optimization indexes...
# INFO [migration_script] Migration completed successfully!
```

#### Option B: Direct Script Execution (Testing Only)

```bash
# For testing purposes only - DO NOT USE IN PRODUCTION
python migration_test_runner.py
```

### Step 5: Post-Migration Validation

```bash
# Run comprehensive data integrity validation
python data_integrity_validator.py

# Expected results:
# ✅ Database Accessible: 100%
# ✅ Table Structures: 100% 
# ✅ Data Counts: 100%
# ✅ Relationships: 100%
# ✅ Data Quality: 100%
# ✅ Indexes: 100%
# ✅ Foreign Keys: 100%
# Overall Integrity Score: >90%
```

### Step 6: Verify Migration Success

```bash
# Connect to database and verify structure
sqlite3 /path/to/database.db

# Check new table exists
.tables
-- Should show: project_videos table

# Check project_videos structure
.schema project_videos
-- Should show junction table with proper foreign keys

# Verify data migration
SELECT COUNT(*) FROM project_videos;
SELECT COUNT(*) FROM videos WHERE camera_model IS NOT NULL;

# Check indexes
.indexes project_videos

# Exit database
.exit
```

### Step 7: Update Application Code

#### Required Code Changes:

**Before Migration (One-to-Many):**
```python
# Old relationship
class Project(Base):
    videos = relationship("Video", back_populates="project")

class Video(Base):
    project_id = Column(String(36), ForeignKey("projects.id"))
    project = relationship("Project", back_populates="videos")
```

**After Migration (Many-to-Many):**
```python
# New relationship
class Project(Base):
    # Many-to-many relationship through junction table
    videos = relationship("Video", secondary="project_videos", back_populates="projects")

class Video(Base):
    # Many-to-many relationship through junction table
    projects = relationship("Project", secondary="project_videos", back_populates="videos")
    
    # New fields from project migration
    camera_model = Column(String)
    camera_view = Column(String) 
    lens_type = Column(String)
    video_resolution = Column(String)
    frame_rate = Column(Integer)
    signal_type = Column(String)

# Junction table model (optional, for direct access)
class ProjectVideo(Base):
    __tablename__ = "project_videos"
    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"))
    video_id = Column(String(36), ForeignKey("videos.id"))
    created_at = Column(DateTime(timezone=True))
```

### Step 8: Update API Endpoints

```python
# Update project creation to handle video assignments
@app.post("/projects/{project_id}/videos/{video_id}")
async def assign_video_to_project(project_id: str, video_id: str):
    # Create junction table entry
    project_video = ProjectVideo(
        project_id=project_id,
        video_id=video_id
    )
    db.add(project_video)
    db.commit()

# Update queries to use new relationship
@app.get("/projects/{project_id}/videos")
async def get_project_videos(project_id: str):
    project = db.query(Project).filter(Project.id == project_id).first()
    return project.videos  # Now uses junction table

# Video can belong to multiple projects
@app.get("/videos/{video_id}/projects") 
async def get_video_projects(video_id: str):
    video = db.query(Video).filter(Video.id == video_id).first()
    return video.projects  # Returns all associated projects
```

### Step 9: Restart Application Services

```bash
# Start backend services
sudo systemctl start your-api-service

# Verify service health
curl http://localhost:8000/health

# Check API endpoints
curl http://localhost:8000/projects
curl http://localhost:8000/videos
```

### Step 10: Production Validation

```bash
# Run application-specific tests
# Test project-video assignments
# Verify existing data accessibility
# Check performance of new queries

# Monitor error logs
tail -f /var/log/your-app/error.log

# Monitor application metrics
# - Response times for project/video queries
# - Database query performance
# - Memory usage
```

## Rollback Procedure

### If Migration Fails

```bash
# Immediate rollback using Alembic
alembic downgrade 0003

# OR restore from backup
python data_backup_script.py --restore

# Verify rollback success
python data_integrity_validator.py
```

### Manual Rollback Steps

1. **Stop application services**
2. **Restore database from backup:**
   ```bash
   cp ./migration_backups/database_backup_YYYYMMDD_HHMMSS.db /path/to/database.db
   ```
3. **Verify data integrity**
4. **Restart application services**
5. **Investigate migration failure**

## Performance Optimization

### New Query Patterns

```sql
-- Find all videos for a project (optimized)
SELECT v.* 
FROM videos v
INNER JOIN project_videos pv ON v.id = pv.video_id  
WHERE pv.project_id = ?;

-- Find all projects for a video (new capability)
SELECT p.*
FROM projects p
INNER JOIN project_videos pv ON p.id = pv.project_id
WHERE pv.video_id = ?;

-- Find videos by technical specifications (new capability)
SELECT * FROM videos 
WHERE camera_model = ? 
  AND camera_view = ?
  AND frame_rate >= ?;
```

### Index Utilization

The migration creates these performance indexes:
- `idx_project_videos_project_id` - Fast project → videos lookup
- `idx_project_videos_video_id` - Fast video → projects lookup  
- `idx_project_videos_project_video` - Unique constraint index
- `idx_videos_camera_model` - Technical specification filtering
- `idx_videos_camera_view` - Camera view filtering
- `idx_videos_processing_status` - Processing status queries

## Monitoring and Maintenance

### Health Checks

```bash
# Daily integrity check
python data_integrity_validator.py

# Weekly relationship audit  
SELECT 
  (SELECT COUNT(*) FROM projects) as total_projects,
  (SELECT COUNT(*) FROM videos) as total_videos,
  (SELECT COUNT(*) FROM project_videos) as total_relationships,
  (SELECT COUNT(DISTINCT project_id) FROM project_videos) as projects_with_videos,
  (SELECT COUNT(DISTINCT video_id) FROM project_videos) as videos_with_projects;
```

### Performance Monitoring

```sql
-- Monitor query performance
EXPLAIN QUERY PLAN 
SELECT p.name, COUNT(pv.video_id) as video_count
FROM projects p
LEFT JOIN project_videos pv ON p.id = pv.project_id
GROUP BY p.id, p.name;

-- Check index usage
PRAGMA index_info(idx_project_videos_project_id);
```

## Troubleshooting

### Common Issues

#### Issue: "Table project_videos already exists"
**Solution:** Check if migration was partially completed
```bash
alembic current
alembic history
```

#### Issue: "Foreign key constraint failed"
**Solution:** Check for orphaned records before migration
```bash
python data_integrity_validator.py
```

#### Issue: "Out of disk space during migration"
**Solution:** Free up space and restore from backup
```bash
df -h
cp ./migration_backups/database_backup_*.db /path/to/database.db
```

#### Issue: "Migration takes too long"
**Solution:** Migration is designed for large datasets, but consider:
- Running during low-traffic periods
- Increasing database connection timeouts
- Monitoring system resources

### Getting Help

1. **Check migration logs** in migration script output
2. **Review data integrity validation** results
3. **Examine backup files** for data recovery
4. **Test rollback procedure** in development environment
5. **Contact development team** with specific error messages

## Success Criteria

Migration is successful when:

- [ ] **All services restart without errors**
- [ ] **Data integrity validation passes** (>90% score)
- [ ] **Application functionality verified** (CRUD operations work)
- [ ] **Performance tests pass** (query response times acceptable)
- [ ] **No data loss detected** (row counts match pre-migration)
- [ ] **New many-to-many relationships work** (videos can belong to multiple projects)

## Post-Migration Benefits

### New Capabilities
- **Videos can belong to multiple projects** (shared video library)
- **Enhanced video metadata** (camera specifications per video)
- **Flexible project organization** (projects as logical groupings)
- **Better performance** (optimized indexes for common queries)

### Architecture Improvements
- **Normalized data model** (technical specifications at video level)
- **Reduced data duplication** (camera specs stored once per video)
- **Enhanced scalability** (supports complex project hierarchies)
- **Better data integrity** (foreign key constraints maintained)

---

**📞 Support Contact:** development-team@yourcompany.com
**📚 Documentation:** [Link to full API documentation]
**🔧 Troubleshooting:** [Link to troubleshooting guide]