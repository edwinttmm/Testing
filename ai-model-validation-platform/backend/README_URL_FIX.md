# Database URL Fix Solution

## Problem

The backend database contains localhost URLs that break video playback in production:
- **Issue**: Video URLs stored as `http://localhost:8000/uploads/...` instead of production URL
- **Impact**: Videos fail to load in production frontend
- **Root Cause**: URL generation uses localhost during development/testing

## Solution Overview

A comprehensive database URL fix solution with:

1. **Migration Script**: Bulk URL updates with backup/rollback capability
2. **API Service**: RESTful endpoints for URL fix operations  
3. **Validation**: Comprehensive validation and error handling
4. **Cache Management**: Automatic cache invalidation
5. **Progress Tracking**: WebSocket progress updates

## Files Created

### Core Components
- `migrations/fix_localhost_urls.py` - Standalone migration script
- `services/url_fix_service.py` - URL fix service with caching 
- `main.py` - Added API endpoints (lines 2558-2734)

### Testing
- `tests/test_url_fix_solution.py` - Comprehensive test suite

## URL Transformation

```
FROM: http://localhost:8000/uploads/filename.mp4
TO:   http://155.138.239.131:8000/uploads/filename.mp4
```

## Affected Database Tables

| Table | Field | Description |
|-------|-------|-------------|
| `videos` | `file_path` | Video file URLs |
| `detection_events` | `screenshot_path` | Detection screenshot URLs |
| `detection_events` | `screenshot_zoom_path` | Zoomed screenshot URLs |

## API Endpoints

### 1. Scan for Issues
```bash
GET /api/videos/fix-urls/scan
```
**Purpose**: Preview what would be changed without making modifications

**Response**:
```json
{
  "status": "scan_complete",
  "total_records_found": 42,
  "affected_tables": {
    "videos": {"count": 25, "fields": ["file_path"]},
    "detection_events": {"count": 17, "fields": ["screenshot_path", "screenshot_zoom_path"]}
  },
  "recommendation": "fix_needed"
}
```

### 2. Execute Fix
```bash
POST /api/videos/fix-urls
```
**Purpose**: Perform bulk URL updates with backup creation

**Response**:
```json
{
  "status": "success",
  "message": "Updated 42 records successfully",
  "updated_count": 42,
  "backup_file": "backups/url_fix_backup_20250826_140532.json",
  "old_base_url": "http://localhost:8000",
  "new_base_url": "http://155.138.239.131:8000"
}
```

### 3. Get Status
```bash
GET /api/videos/fix-urls/status
```
**Purpose**: Check current status and available operations

### 4. Validate Fix
```bash
POST /api/videos/fix-urls/validate
```
**Purpose**: Verify that URL fixes were applied correctly

**Response**:
```json
{
  "status": "validation_complete",
  "validation_passed": true,
  "remaining_localhost_urls": {"videos": 0, "detection_events": 0},
  "total_remaining": 0,
  "message": "All URLs fixed successfully"
}
```

## Usage Instructions

### Option 1: API Endpoints (Recommended)

1. **First, scan to see what needs fixing**:
   ```bash
   curl -X GET http://155.138.239.131:8000/api/videos/fix-urls/scan
   ```

2. **Execute the fix**:
   ```bash
   curl -X POST http://155.138.239.131:8000/api/videos/fix-urls
   ```

3. **Validate the results**:
   ```bash
   curl -X POST http://155.138.239.131:8000/api/videos/fix-urls/validate
   ```

### Option 2: Direct Migration Script

1. **Dry run** (preview changes):
   ```bash
   cd backend
   python migrations/fix_localhost_urls.py --dry-run
   ```

2. **Execute** (apply changes):
   ```bash
   python migrations/fix_localhost_urls.py --execute
   ```

3. **Rollback** (if needed):
   ```bash
   python migrations/fix_localhost_urls.py --rollback backups/url_fix_backup_YYYYMMDD_HHMMSS.json
   ```

## Safety Features

### 1. Automatic Backup
- Every fix operation creates a timestamped backup
- JSON format with complete rollback data
- Stored in `backups/` directory

### 2. Dry Run Mode
- Preview all changes before execution
- No database modifications in dry run
- Detailed change summary

### 3. Validation
- Pre-fix scanning to identify issues
- Post-fix validation to ensure success
- Comprehensive error reporting

### 4. Transaction Safety
- All operations use database transactions
- Automatic rollback on any error
- Atomic operations ensure consistency

## Testing

Run the comprehensive test suite:

```bash
# Local tests only (no API calls)
python tests/test_url_fix_solution.py --local-test

# Full test suite (includes API testing)
python tests/test_url_fix_solution.py --backend-url http://155.138.239.131:8000
```

Test coverage includes:
- Migration script functionality
- API endpoint responses
- Database validation
- Error handling
- Rollback capability

## Error Handling

### Common Issues & Solutions

1. **"No localhost URLs found"**
   - Already fixed or URLs stored differently
   - Check with scan endpoint first

2. **"Database connection failed"**
   - Verify database is accessible
   - Check connection settings

3. **"Backup creation failed"**
   - Check file permissions
   - Ensure `backups/` directory exists

4. **"Validation failed after fix"**
   - Some URLs may not match expected pattern
   - Check logs for specific issues

### Logging
- All operations logged at INFO level
- Errors logged at ERROR level
- WebSocket notifications for progress tracking

## Monitoring

### WebSocket Updates
The fix operation emits progress updates via WebSocket:

```javascript
// Frontend can listen for progress
socket.on('url_fix_completed', (data) => {
  console.log(`Updated ${data.updated_count} records`);
  console.log(`Backup: ${data.backup_file}`);
});
```

### Cache Invalidation
Automatic cache invalidation for:
- `video_list:*`
- `video_details:*`  
- `project_videos:*`
- `detection_events:*`
- `detection_screenshots:*`

## Production Deployment

### Pre-deployment Checklist
- [ ] Backend is stopped for maintenance
- [ ] Database backup created
- [ ] Test environment validated
- [ ] Rollback plan confirmed

### Deployment Steps
1. **Scan first** to understand scope
2. **Execute fix** during maintenance window  
3. **Validate results** immediately
4. **Test video playback** in frontend
5. **Monitor for issues**

### Post-deployment
- Videos should load correctly in frontend
- URLs should point to production server
- All video-related functionality tested

## Rollback Plan

If issues occur after deployment:

1. **Immediate rollback**:
   ```bash
   python migrations/fix_localhost_urls.py --rollback backups/url_fix_backup_[timestamp].json
   ```

2. **Validate rollback**:
   ```bash
   curl -X POST http://155.138.239.131:8000/api/videos/fix-urls/validate
   ```

3. **Restart services** and verify functionality

## Support

### Debug Information
For troubleshooting, collect:
- Database scan results
- API response logs
- Backend server logs
- Frontend console errors

### Contact
- Check backend logs for detailed error messages
- Use validation endpoints to verify current state
- Test with single video before bulk operations

---

**Summary**: This solution provides a complete, safe, and validated approach to fixing localhost URLs in the database, enabling proper video playback in production.