# Database Migration Tools

This directory contains database migration tools for the AI Model Validation Platform.

## Quick Start

```bash
# Run migration to fix schema issues
python run_migration.py

# Test that migration worked
python test_migration.py

# Initialize fresh database (optional)
python migrations/init_database.py
```

## Migration Scripts

### 1. `add_missing_columns.py`
**Purpose**: Adds missing database columns that exist in models but not in the actual database.

**What it does**:
- Verifies all model columns exist in database
- Safely adds missing columns with proper defaults
- Creates indexes for performance
- Provides detailed logging

**Safe to run**: ✅ Non-destructive, only adds missing columns

### 2. `rollback_migration.py`
**Purpose**: Rollback mechanism for migration changes.

**What it does**:
- Removes columns added by migration (if needed)
- Drops migration-created indexes
- Provides safety net for production

**Use when**: You need to undo migration changes

### 3. `init_database.py`
**Purpose**: Fresh database initialization from models.

**What it does**:
- Creates all tables from SQLAlchemy models
- Verifies complete schema
- Adds initial test data
- Comprehensive validation

**Use when**: Setting up new database instance

## Utility Scripts

### `run_migration.py`
User-friendly migration runner with error handling.

### `test_migration.py`
Comprehensive migration testing and verification.

## Migration History

### 2025-08-19: Schema Alignment Fix
**Issue**: `ground_truth_status` field referenced in schemas but missing from models
**Fix**: 
- Updated schemas to use `processing_status` (actual model field)
- Fixed API endpoints to return correct field names  
- Verified all database columns exist

**Result**: ✅ Complete schema alignment achieved

## Usage Examples

### Run Migration
```bash
cd /path/to/backend
python migrations/add_missing_columns.py
```

### Test Results
```bash
python test_migration.py
```

### Rollback (if needed)
```bash
python migrations/rollback_migration.py
```

## Production Deployment

1. **Backup database** before running migration
2. **Test migration** on staging environment first
3. **Run migration** during maintenance window
4. **Verify results** with test script
5. **Monitor application** for any issues

## Safety Features

- ✅ **Non-destructive**: Only adds missing columns
- ✅ **Rollback available**: Emergency reversal capability  
- ✅ **Verification**: Comprehensive post-migration testing
- ✅ **Logging**: Detailed activity logs
- ✅ **Error handling**: Graceful failure management

## Database Compatibility

- ✅ **SQLite**: Primary development database
- ✅ **PostgreSQL**: Production database (with minor index syntax differences)
- ⚠️ **MySQL**: Untested (may require query modifications)

## Support

For issues with migrations:
1. Check logs for error details
2. Verify database connectivity
3. Ensure proper permissions
4. Use rollback if needed
5. Contact development team