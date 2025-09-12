# CRUD Operations Refactoring for Many-to-Many Project-Video Relationships

## Overview
This document summarizes the comprehensive refactoring of CRUD operations to support the new many-to-many relationship structure between Projects and Videos, moving away from the previous one-to-many design.

## Problem Statement
The original CRUD operations assumed a one-to-many relationship where:
- Each Video belonged to exactly one Project
- Videos had a direct `project_id` foreign key
- Project deletion would cascade delete all videos

The new many-to-many structure requires:
- Videos can belong to multiple Projects
- Projects can contain multiple Videos
- Relationships managed through `VideoProjectLink` junction table
- Smarter cascade deletion to avoid orphaning shared videos

## Key Changes Made

### 1. Updated Video CRUD Operations

#### `create_video()` - Major Refactor
- **Before**: Required single `project_id` parameter
- **After**: Accepts optional `project_ids` list for multiple project assignments
- **New**: Creates video first, then assigns to projects via junction table
- **Backward Compatibility**: Added `create_video_legacy()` for single project assignment

#### `get_videos()` - Security-Enhanced
- **Before**: Joined directly with Project table via Video.project_id
- **After**: Joins through VideoProjectLink → Project for proper security filtering
- **Enhancement**: Added `distinct()` to prevent duplicates when video is in multiple projects

#### `get_video()` - Security-Enhanced
- **Before**: Direct Project join via Video.project_id
- **After**: VideoProjectLink → Project join chain for security validation

### 2. Enhanced Project CRUD Operations

#### `get_project()` - Flexible Loading
- **New Parameter**: `load_videos=False` controls whether to eagerly load associated videos
- **Performance**: Lightweight loading by default, explicit video loading when needed
- **Relationship**: Uses `joinedload()` for efficient video fetching via junction table

#### `delete_project()` - Smart Cascade Handling
- **Before**: Simple cascade delete of all project videos
- **After**: Intelligent deletion that only removes videos not in other projects
- **Safety**: Checks for shared videos before deletion
- **Cleanup**: Still handles physical file cleanup for orphaned videos

### 3. New Video-Project Assignment Functions

#### `assign_video_to_project()`
- Creates VideoProjectLink entries with metadata
- Prevents duplicate assignments
- Supports assignment reasons and confidence scoring
- Returns existing link if assignment already exists

#### `remove_video_from_project()`
- User security validation included
- Removes specific VideoProjectLink entries
- Returns boolean success indicator

#### `get_project_videos()` & `get_video_projects()`
- Efficient queries for relationship traversal
- Built-in user security filtering
- Pagination support for large datasets

### 4. Bulk Operations Support

#### `bulk_assign_videos_to_project()`
- Efficiently assigns multiple videos to a project
- User security validation for all operations
- Returns list of created VideoProjectLink objects

#### `bulk_remove_videos_from_project()`
- Mass removal with security checks
- Returns count of successfully removed videos
- Atomic operations with rollback on failure

### 5. Maintenance and Utility Functions

#### `get_orphaned_videos()`
- Identifies videos not assigned to any project
- User-scoped results for security
- Useful for cleanup and maintenance

#### `cleanup_orphaned_videos()`
- Removes orphaned videos and physical files
- User-safe operation with proper scoping
- Returns count of cleaned up videos

#### `migrate_legacy_video_relationships()`
- Handles migration from old direct relationship model
- Creates VideoProjectLink entries for existing Video.project_id values
- Clears legacy project_id fields after migration

#### `validate_project_video_relationships()`
- Comprehensive relationship integrity checking
- Returns detailed issue counts
- Identifies orphaned videos, invalid links, legacy relationships, and duplicates

### 6. Updated Security Model

#### Enhanced User Isolation
- All video access now requires joining through VideoProjectLink → Project
- Prevents users from accessing videos in other users' projects
- Maintains existing user_id-based security filtering

#### Dashboard Statistics
- Updated `get_dashboard_stats()` to use distinct video counting
- Accurately reflects unique videos across multiple projects
- Prevents inflated counts from shared videos

## API Compatibility

### Maintained Functions
- `get_projects()` - Unchanged interface, lightweight loading
- `get_test_sessions()` - Enhanced security filtering
- `get_ground_truth_objects()` - Updated security chain
- `get_detection_events()` - Unchanged (uses TestSession relationship)

### New Functions Available
- `assign_video_to_project()`
- `remove_video_from_project()`
- `get_project_videos()`
- `get_video_projects()`
- `bulk_assign_videos_to_project()`
- `bulk_remove_videos_from_project()`
- `cleanup_orphaned_videos()`
- `migrate_legacy_video_relationships()`
- `validate_project_video_relationships()`

### Legacy Support
- `create_video_legacy()` maintains old interface
- Existing API endpoints should work with minimal changes
- Migration function handles transition from old data

## Testing Coverage

Created comprehensive test suite in `/tests/test_crud_many_to_many.py`:
- Video creation with and without project assignments
- Project operations with video loading
- Security isolation between users
- Bulk operations
- Data integrity validation
- Dashboard statistics accuracy
- Utility functions verification

## Performance Considerations

### Optimizations Added
- Lazy loading by default, explicit eager loading when needed
- Efficient bulk operations to reduce database round trips
- Proper indexing support through junction table
- Distinct queries to prevent duplicate processing

### Potential Concerns
- Additional join required for video access (mitigated by proper indexing)
- More complex queries for relationship traversal
- Need for explicit video loading in some scenarios

## Migration Path

### For Existing Data
1. Run `migrate_legacy_video_relationships()` to create junction table entries
2. Validate relationships with `validate_project_video_relationships()`
3. Clean up orphaned data with `cleanup_orphaned_videos()`

### For API Clients
1. Update video creation calls to use new signature if needed
2. Consider using `get_project()` with `load_videos=True` when video data is needed
3. Utilize new bulk operations for better performance

## Next Steps

1. **API Endpoint Updates**: Review and update FastAPI endpoints to use new CRUD functions
2. **Frontend Integration**: Update frontend services to work with new video assignment model
3. **Migration Script**: Create Alembic migration script for production deployment
4. **Performance Testing**: Validate query performance with large datasets
5. **Documentation Updates**: Update API documentation to reflect new capabilities

## Files Modified

- `/backend/crud.py` - Comprehensive refactoring with new functions
- `/tests/test_crud_many_to_many.py` - Complete test suite

## Files Requiring Updates

- API endpoint files that use video CRUD operations
- Frontend service files for project/video management
- Migration scripts for schema changes
- Integration tests for end-to-end workflows

This refactoring provides a robust foundation for the many-to-many Project-Video relationship while maintaining security, performance, and backward compatibility where possible.