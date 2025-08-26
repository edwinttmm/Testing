# Projects API 500 Error - Root Cause Analysis Report

**Investigation Date**: August 26, 2025  
**Issue**: `/api/projects` endpoint returning 500 Internal Server Error  
**Investigator**: Research Agent

## 🚨 ROOT CAUSE IDENTIFIED

### The Problem

The backend logs show validation errors for enum values:
```
2025-08-26 19:13:20,947 - main - ERROR - Unexpected database error: 2 validation errors:
{'type': 'enum', 'loc': ('response', 0, 'camera_view'), 'msg': "Input should be 'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior' or 'Multi-angle'", 'input': 'Mixed', 'ctx': {'expected': "'Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior' or 'Multi-angle'"}}
{'type': 'enum', 'loc': ('response', 0, 'signal_type'), 'msg': "Input should be 'GPIO', 'Network Packet', 'Serial' or 'CAN Bus'", 'input': 'Mixed', 'ctx': {'expected': "'GPIO', 'Network Packet', 'Serial' or 'CAN Bus'"}}
```

### 🎯 The Real Issue: Database Environment Mismatch

**KEY FINDING**: The application is **NOT** using the expected SQLite database. Instead, it was connecting to a **PostgreSQL database** that contains the problematic "Mixed" enum values.

#### Evidence:

1. **Backend Log Analysis** (`/backend/backend.log` line 8):
   ```
   Database: postgresql://postgres:***@postgres:5432/vru_validation
   ```

2. **Current Database State**:
   - SQLite databases (dev_database.db, fallback_database.db): ✅ **CLEAN** - No "Mixed" values found
   - PostgreSQL database: ❌ **CONTAINS** "Mixed" values causing validation failures

3. **Database Connection Logic** (from `/backend/database.py`):
   ```python
   # Line 17: DATABASE_URL = settings.database_url
   # Falls back to environment variables:
   # - DATABASE_URL
   # - AIVALIDATION_DATABASE_URL 
   # - Default: sqlite:///./test_database.db
   ```

### 🔍 Investigation Findings

#### Database Files Found:
- `dev_database.db` (704KB) - Currently in use, contains valid data
- `fallback_database.db` (663KB) - Clean
- `test_database.db` (544KB) - Clean
- Multiple other smaller DB files - All clean

#### Projects API Endpoint Analysis:
- **Endpoint**: `GET /api/projects` in `/backend/main.py:618`
- **Function**: `list_projects()` calls `get_projects(db=db, user_id="anonymous", skip=skip, limit=limit)`
- **CRUD Function**: `db.query(Project).offset(skip).limit(limit).all()` - Simple query, no filtering

#### Validation Schema:
Valid enum values defined in schemas:
- `camera_view`: "Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior", "Multi-angle"
- `signal_type`: "GPIO", "Network Packet", "Serial", "CAN Bus"

### 🛠️ Available Fix Scripts

The codebase already contains purpose-built fix scripts:

1. **PostgreSQL Fix**: `/backend/scripts/fix_postgresql_enum_values.sql`
   - Updates `camera_view = 'Mixed'` → `'Multi-angle'`
   - Updates `signal_type = 'Mixed'` → `'Network Packet'`

2. **Docker Environment Fix**: `/backend/scripts/docker_enum_fix.py`
   - Handles PostgreSQL connections in Docker environment
   - Includes verification and rollback capabilities

3. **Generic Enum Fixer**: `/backend/scripts/fix_enum_validation.py`
   - Works with SQLite databases
   - Includes backup, fix, and verify operations

### 📋 Resolution Strategy

#### Immediate Fix Options:

**Option A**: Fix PostgreSQL Database (if still accessible)
```bash
cd /backend
python scripts/docker_enum_fix.py --fix
# OR execute the SQL script directly
```

**Option B**: Force SQLite Usage (Current State)
```bash
# Ensure environment variables are not set
unset DATABASE_URL
unset AIVALIDATION_DATABASE_URL
# Backend will use SQLite which is already clean
```

**Option C**: Environment Configuration
```bash
# Set explicit SQLite database
export AIVALIDATION_DATABASE_URL="sqlite:///./dev_database.db"
```

#### Verification Steps:
1. Start the backend service
2. Test the `/api/projects` endpoint
3. Verify no validation errors in logs

### 🎯 Recommendations

1. **IMMEDIATE**: Verify current environment variables and database connection
2. **SHORT-TERM**: Apply the PostgreSQL enum fixes if that database is still being used
3. **LONG-TERM**: Implement database environment validation in startup to prevent this confusion

### 📊 Impact Assessment

- **Severity**: HIGH - API completely non-functional
- **Scope**: All project-related endpoints potentially affected
- **Data Integrity**: No data loss, only validation issues
- **Resolution Time**: < 30 minutes with proper database access

### 🔧 Next Steps

1. Determine current active database connection
2. Apply appropriate fix script
3. Restart backend service
4. Verify API functionality
5. Update deployment documentation to prevent recurrence

---

**Resolution Status**: Root cause identified, fix strategies available  
**Memory Key**: `projects-api-root-cause` - Complete analysis with fix options