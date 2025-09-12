# API Serialization Integration Guide

## 🎯 Problem Solved

This serialization system fixes the **snake_case/camelCase inconsistency** between:
- **Backend** (Python): Uses `snake_case` field names (`project_id`, `file_size`, `created_at`)
- **Frontend** (TypeScript/JavaScript): Expects `camelCase` field names (`projectId`, `fileSize`, `createdAt`)

## 🚀 Quick Start

### 1. Import the Serializers

```python
from serializers import (
    ProjectSerializer, VideoSerializer, AnnotationSerializer,
    create_single_response, create_list_response, serialize_for_frontend
)
```

### 2. Update FastAPI Endpoints

#### Before (Inconsistent field names):
```python
@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = await db.get_project(project_id)
    # Returns snake_case fields that break frontend
    return {"id": project.id, "project_id": project.project_id, "created_at": project.created_at}
```

#### After (Consistent camelCase):
```python
@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    project = await db.get_project(project_id)  # snake_case from DB
    
    # Automatic camelCase conversion
    return create_single_response(
        item=project,
        model_class=ProjectSerializer,
        message="Project retrieved successfully"
    )
    # Returns: {"success": true, "data": {"id": "...", "projectId": "...", "createdAt": "..."}}
```

## 📋 Field Name Conversions

| Database (snake_case) | Frontend (camelCase) | Status |
|----------------------|---------------------|---------|
| `project_id` | `projectId` | ✅ Fixed |
| `video_id` | `videoId` | ✅ Fixed |
| `file_size` | `fileSize` | ✅ Fixed |
| `created_at` | `createdAt` | ✅ Fixed |
| `updated_at` | `updatedAt` | ✅ Fixed |
| `frame_rate` | `frameRate` | ✅ Fixed |
| `camera_model` | `cameraModel` | ✅ Fixed |
| `bounding_box` | `boundingBox` | ✅ Fixed |
| `detection_count` | `detectionCount` | ✅ Fixed |
| `processing_status` | `processingStatus` | ✅ Fixed |
| `ground_truth_generated` | `groundTruthGenerated` | ✅ Fixed |

## 🔧 Integration Patterns

### Pattern 1: Full Endpoint Rewrite (Recommended)

```python
from serializers import VideoSerializer, create_single_response

@router.get("/videos/{video_id}", response_model=dict)
async def get_video(video_id: str):
    video = await video_service.get_by_id(video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Automatic snake_case to camelCase conversion
    return create_single_response(
        item=video,
        model_class=VideoSerializer,
        message="Video retrieved successfully"
    )
```

### Pattern 2: Gradual Migration (For existing endpoints)

```python
from serializers import serialize_for_frontend

@router.get("/videos/{video_id}")
async def get_video_legacy(video_id: str):
    video = await video_service.get_by_id(video_id)
    
    # Convert existing dict/model to camelCase
    camel_case_data = serialize_for_frontend(
        data=video.__dict__,  # or video.dict() if Pydantic
        include_snake_case=True  # Maintain backward compatibility
    )
    
    return {"success": True, "data": camel_case_data}
```

### Pattern 3: Collection Endpoints

```python
from serializers import create_paginated_response, ProjectSerializer

@router.get("/projects")
async def list_projects(page: int = 1, limit: int = 10):
    projects, total = await project_service.get_paginated(page, limit)
    
    return create_paginated_response(
        items=projects,
        model_class=ProjectSerializer,
        page=page,
        per_page=limit,
        total=total
    )
```

## 🔄 Response Format Examples

### Single Item Response:
```json
{
  "success": true,
  "data": {
    "id": "proj_123",
    "projectId": "proj_123",  // ← camelCase for frontend
    "name": "VRU Detection Project",
    "cameraModel": "FLIR Blackfly",  // ← was camera_model
    "createdAt": "2024-01-15T10:30:00Z",  // ← was created_at
    "fileSize": 125829120  // ← was file_size
  },
  "message": "Project retrieved successfully"
}
```

### List Response:
```json
{
  "success": true,
  "data": [
    {"id": "vid_1", "projectId": "proj_123", "fileName": "video1.mp4"},
    {"id": "vid_2", "projectId": "proj_123", "fileName": "video2.mp4"}
  ],
  "count": 2,
  "message": "Videos retrieved successfully"
}
```

### Paginated Response:
```json
{
  "success": true,
  "data": [...],
  "meta": {
    "page": 1,
    "perPage": 10,
    "total": 50,
    "pages": 5,
    "hasNext": true,
    "hasPrev": false
  }
}
```

## 🔄 Backward Compatibility

For gradual migration, you can include both formats:

```python
# Include snake_case for backward compatibility
response = serialize_for_frontend(data, include_snake_case=True)
```

This produces:
```json
{
  "projectId": "proj_123",    // ← New camelCase (frontend)
  "project_id": "proj_123",   // ← Old snake_case (compatibility)
  "createdAt": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## 📝 Specific Entity Usage

### Projects:
```python
from serializers import ProjectSerializer, create_single_response

return create_single_response(project, ProjectSerializer)
```

### Videos:
```python
from serializers import VideoSerializer, create_list_response

return create_list_response(videos, VideoSerializer)
```

### Annotations:
```python
from serializers import AnnotationSerializer

annotation_data = AnnotationSerializer.model_validate(db_annotation)
return annotation_data.model_dump(by_alias=True)  # camelCase output
```

### Bounding Boxes:
```python
from serializers import BoundingBoxSerializer

bbox = BoundingBoxSerializer.model_validate({
    "x": 100.5, "y": 200.3, "width": 85.2, "height": 120.8, "confidence": 0.95
})
# Automatically includes computed fields: area, centerX, centerY
```

## 🛠️ Testing the Integration

### 1. Run the examples:
```bash
cd backend
python serializer_examples.py
```

### 2. Test endpoint conversion:
```python
# Before
curl http://localhost:8000/api/projects/123
# {"id": "123", "project_id": "123", "created_at": "..."}  ← Inconsistent

# After  
curl http://localhost:8000/api/projects/123
# {"success": true, "data": {"id": "123", "projectId": "123", "createdAt": "..."}}  ← Consistent
```

## 🎯 Migration Checklist

- [ ] Import serializers in your route files
- [ ] Update project endpoints to use `ProjectSerializer`
- [ ] Update video endpoints to use `VideoSerializer` 
- [ ] Update annotation endpoints to use `AnnotationSerializer`
- [ ] Replace manual dict construction with `create_single_response()`
- [ ] Replace manual list responses with `create_list_response()`
- [ ] Add pagination with `create_paginated_response()`
- [ ] Test frontend integration with new camelCase fields
- [ ] Remove backward compatibility after frontend is updated

## 🚨 Breaking Changes

After updating your API endpoints:

1. **Frontend TypeScript interfaces** will now work correctly
2. **Field names** will be consistent (camelCase everywhere)
3. **Response format** will be standardized with `success`, `data`, `message`

## 💡 Pro Tips

1. **Use `populate_by_name=True`** to accept both snake_case and camelCase in request bodies
2. **Use `include_snake_case=True`** during migration for backward compatibility
3. **Always validate with Pydantic models** to catch type errors early
4. **Use response wrapper functions** for consistent API responses
5. **Test both formats** during the migration period

## 🏃‍♂️ Next Steps

1. Update your existing API endpoints one by one
2. Test with frontend to confirm camelCase fields work
3. Update TypeScript interfaces to match new response format
4. Remove backward compatibility flags once migration is complete
5. Update API documentation to reflect new field names