# PostgreSQL Enum Value Fix

This directory contains scripts to fix invalid enum values in the PostgreSQL database running in Docker.

## Problem

The PostgreSQL database has invalid enum values:
- `camera_view`: "Mixed" should be "Multi-angle"
- `signal_type`: "Mixed" should be "Network Packet"

## Solution Scripts

### 1. `fix_postgresql_enum_values.sql`
Direct SQL script to fix the enum values. Can be executed directly against the database.

### 2. `fix_postgresql_enums.py`
Python script that can run from the host machine. Requires `psycopg2` to be installed.

### 3. `docker_enum_fix.py`
Docker-optimized Python script designed to run inside the backend container.

### 4. `run_enum_fix.sh`
Bash script that provides multiple ways to run the fix.

## Quick Fix Options

### Option 1: Run from Docker container (Recommended)
```bash
cd /home/user/Testing/ai-model-validation-platform
docker-compose exec backend python scripts/docker_enum_fix.py
```

### Option 2: Use the automated runner
```bash
cd /home/user/Testing/ai-model-validation-platform/backend/scripts
./run_enum_fix.sh docker
```

### Option 3: Direct SQL execution
```bash
cd /home/user/Testing/ai-model-validation-platform
docker-compose exec postgres psql -U postgres -d vru_validation -f /dev/stdin < backend/scripts/fix_postgresql_enum_values.sql
```

## What the fix does

1. **Updates camera_view values**:
   - Changes all `camera_view = 'Mixed'` to `camera_view = 'Multi-angle'`

2. **Updates signal_type values**:
   - Changes all `signal_type = 'Mixed'` to `signal_type = 'Network Packet'`

3. **Verifies the changes**:
   - Checks that no invalid enum values remain
   - Shows the distribution of current enum values

## Safety Features

- **Transaction safety**: All changes are wrapped in transactions
- **Rollback on error**: If anything fails, changes are automatically rolled back
- **Verification**: The script verifies that fixes were applied correctly
- **Detailed logging**: Shows exactly what was changed and how many records were affected

## Prerequisites

- Docker containers must be running (`docker-compose up`)
- PostgreSQL container must be healthy
- For host-based scripts: `psycopg2-binary` Python package

## Expected Output

```
PostgreSQL Enum Value Fix Script (Docker Version)
=======================================================
Started at: 2025-01-XX XX:XX:XX

=== CHECKING FOR INVALID ENUM VALUES ===
Found X projects with invalid camera_view='Mixed'
Found Y projects with invalid signal_type='Mixed'

=== FIXING ENUM VALUES ===
Fixing camera_view values...
Updated X camera_view records from 'Mixed' to 'Multi-angle'
Fixing signal_type values...
Updated Y signal_type records from 'Mixed' to 'Network Packet'

✅ Committed changes to database.

=== VERIFYING FIXES ===
Remaining invalid camera_view values: 0
Remaining invalid signal_type values: 0

🎉 ALL ENUM VALUES SUCCESSFULLY FIXED!
Total records updated: X+Y
```