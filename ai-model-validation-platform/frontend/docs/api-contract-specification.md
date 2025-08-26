# API Contract Specification: Annotation Creation

## Overview
This document defines the expected API contract for the POST `/api/videos/{id}/annotations` endpoint to ensure consistent data format between frontend and backend.

## Endpoint Details
- **URL**: `POST /api/videos/{video_id}/annotations`
- **Content-Type**: `application/json`
- **Purpose**: Create a new ground truth annotation for a video

## Request Format

### Expected Payload Structure

```json
{
  "detection_id": "string (optional)",
  "frame_number": 123,
  "timestamp": 45.67,
  "end_timestamp": 48.23,
  "vru_type": "pedestrian",
  "bounding_box": {
    "x": 100.5,
    "y": 200.3,
    "width": 150.0,
    "height": 200.0,
    "confidence": 0.85,
    "label": "pedestrian"
  },
  "occluded": false,
  "truncated": false,
  "difficult": false,
  "notes": "Optional annotation notes",
  "annotator": "user@example.com",
  "validated": false
}
```

### Field Specifications

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `detection_id` | string | No | Optional detection ID for tracking | UUID format |
| `frame_number` | integer | Yes | Video frame number | >= 0 |
| `timestamp` | number | Yes | Timestamp in seconds | >= 0 |
| `end_timestamp` | number | No | End timestamp for temporal annotations | >= 0 |
| `vru_type` | string | Yes | VRU type classification | Enum: "pedestrian", "cyclist", "motorcyclist", "wheelchair_user", "scooter_rider" |
| `bounding_box` | object | Yes | Bounding box coordinates | See BoundingBox specification |
| `occluded` | boolean | No | Whether object is occluded | Default: false |
| `truncated` | boolean | No | Whether object is truncated | Default: false |
| `difficult` | boolean | No | Whether detection is difficult | Default: false |
| `notes` | string | No | Optional notes about annotation | Max length: 2000 chars |
| `annotator` | string | No | Annotator identifier | Email or username |
| `validated` | boolean | No | Validation status | Default: false |

### BoundingBox Object Specification

```json
{
  "x": 100.5,        // X coordinate (top-left corner, >= 0)
  "y": 200.3,        // Y coordinate (top-left corner, >= 0) 
  "width": 150.0,    // Width of bounding box (> 0)
  "height": 200.0,   // Height of bounding box (> 0)
  "confidence": 0.85, // Optional confidence score (0.0-1.0)
  "label": "pedestrian" // Optional object label
}
```

## Response Format

### Success Response (201 Created)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "videoId": "video-uuid",
  "detectionId": "detection-uuid",
  "frameNumber": 123,
  "timestamp": 45.67,
  "endTimestamp": 48.23,
  "vruType": "pedestrian",
  "boundingBox": {
    "x": 100.5,
    "y": 200.3,
    "width": 150.0,
    "height": 200.0,
    "confidence": 0.85,
    "label": "pedestrian"
  },
  "occluded": false,
  "truncated": false,
  "difficult": false,
  "notes": "Optional annotation notes",
  "annotator": "user@example.com",
  "validated": false,
  "createdAt": "2025-08-26T10:00:00.000Z",
  "updatedAt": "2025-08-26T10:00:00.000Z"
}
```

### Error Responses

#### 400 Bad Request
```json
{
  "detail": [
    {
      "loc": ["body", "bounding_box", "x"],
      "msg": "ensure this value is greater than or equal to 0",
      "type": "value_error.number.not_ge",
      "ctx": {"limit_value": 0}
    }
  ]
}
```

#### 404 Not Found
```json
{
  "detail": "Video with id {video_id} not found"
}
```

## Field Name Mapping

The API uses alias mapping to support both camelCase (frontend) and snake_case (backend) field names:

| Frontend (camelCase) | Backend (snake_case) | Database Column |
|---------------------|---------------------|-----------------|
| `detectionId` | `detection_id` | `detection_id` |
| `frameNumber` | `frame_number` | `frame_number` |
| `endTimestamp` | `end_timestamp` | `end_timestamp` |
| `vruType` | `vru_type` | `vru_type` |
| `boundingBox` | `bounding_box` | `bounding_box` (JSON) |
| `createdAt` | `created_at` | `created_at` |
| `updatedAt` | `updated_at` | `updated_at` |

## Database Storage

The `bounding_box` field is stored as a JSON column in the database with the following structure:

```sql
-- annotations table
bounding_box JSON NOT NULL -- {"x": 100.5, "y": 200.3, "width": 150.0, "height": 200.0, "confidence": 0.85, "label": "pedestrian"}
```

## Validation Rules

1. **Video Existence**: The `video_id` in the URL must reference an existing video
2. **Coordinate Validation**: All bounding box coordinates must be non-negative numbers
3. **Dimension Validation**: Width and height must be positive numbers
4. **Enum Validation**: `vru_type` must be one of the allowed enumeration values
5. **Timestamp Validation**: All timestamps must be non-negative and logical (end_timestamp >= timestamp if provided)

## Common Integration Issues

### Issue 1: Field Name Inconsistency
- **Problem**: Frontend sends `boundingBox` but backend expects `bounding_box`
- **Solution**: Use proper alias configuration in Pydantic schemas
- **Status**: ✅ Resolved with alias mapping

### Issue 2: Nested Object Serialization
- **Problem**: BoundingBox object not properly serialized
- **Solution**: Ensure proper JSON serialization of nested objects
- **Status**: ⚠️ Monitor for serialization errors

### Issue 3: VRU Type Enumeration
- **Problem**: Frontend and backend VRU type values don't match
- **Solution**: Standardize enumeration values across frontend and backend
- **Status**: ✅ Standardized

## Testing Scenarios

### Valid Requests
1. **Minimal annotation**: Only required fields
2. **Full annotation**: All fields populated
3. **Temporal annotation**: With end_timestamp
4. **High precision coordinates**: Decimal coordinates

### Invalid Requests
1. **Missing required fields**: Should return 400
2. **Invalid coordinates**: Negative values should return 400
3. **Invalid VRU type**: Unknown enum value should return 400
4. **Non-existent video**: Should return 404
5. **Invalid bounding box**: Width/height <= 0 should return 400

## Implementation Status

- ✅ Backend schema validation implemented
- ✅ Frontend API service configured
- ✅ Field name aliasing configured  
- ⚠️ Monitor for serialization edge cases
- 🔄 Integration testing recommended

## Recommendations

1. **Implement comprehensive integration tests** covering all field combinations
2. **Add frontend validation** to catch errors before API calls
3. **Monitor API error logs** for serialization issues
4. **Consider API versioning** for future contract changes
5. **Document coordinate system** (pixel coordinates, coordinate origin, etc.)