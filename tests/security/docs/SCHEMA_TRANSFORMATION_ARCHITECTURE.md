# Schema Transformation Architecture

## Overview

This document describes the implementation of an automatic snake_case to camelCase transformation layer that resolves the system-wide naming inconsistency between the backend (Python snake_case) and frontend (JavaScript camelCase).

## Problem Statement

### Before the Fix
- **Bloated Frontend Models**: Frontend had duplicate fields like `file_size` AND `fileSize`, `created_at` AND `createdAt`
- **Manual Maintenance**: Every schema required manual `Field(alias="...")` declarations
- **Inconsistent Naming**: Mix of snake_case and camelCase throughout the API
- **Error-Prone**: Easy to forget alias declarations leading to API inconsistencies

### After the Fix
- **Clean Frontend Models**: Only camelCase fields in JSON responses
- **Automatic Transformation**: No manual alias management required
- **Consistent API**: All endpoints return camelCase consistently
- **Backward Compatible**: Accepts both naming conventions for input

## Technical Implementation

### Core Components

#### 1. CamelCaseModel Base Class

```python
def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

class CamelCaseModel(BaseModel):
    """Base model that automatically converts snake_case fields to camelCase aliases for API serialization"""
    
    model_config = ConfigDict(
        # Generate camelCase aliases for all fields
        alias_generator=snake_to_camel,
        # Allow both snake_case and camelCase field names when parsing
        populate_by_name=True,
        # Enable serialization by alias (camelCase for frontend)
        by_alias=True,
        # Enable SQLAlchemy integration
        from_attributes=True
    )
```

#### 2. Schema Model Updates

**Before:**
```python
class ProjectResponse(BaseModel):
    camera_model: str = Field(alias="cameraModel")
    created_at: datetime = Field(alias="createdAt")
    owner_id: str = Field(alias="ownerId")
    
    class Config:
        populate_by_name = True
        from_attributes = True
```

**After:**
```python
class ProjectResponse(CamelCaseModel):
    camera_model: str
    created_at: datetime
    owner_id: str
    # No manual alias declarations needed!
    # No Config class needed!
```

#### 3. Automatic Transformations

| Python Field (snake_case) | JSON Output (camelCase) |
|---------------------------|-------------------------|
| `test_session_id` | `testSessionId` |
| `created_at` | `createdAt` |
| `ground_truth_generated` | `groundTruthGenerated` |
| `camera_model` | `cameraModel` |
| `file_size` | `fileSize` |
| `detection_count` | `detectionCount` |

## Usage Examples

### API Response Example

```python
# Backend code (snake_case)
project_data = {
    "id": "proj_123",
    "camera_model": "TestCam Pro",
    "created_at": datetime.now(),
    "owner_id": "user_123"
}

project = ProjectResponse(**project_data)

# JSON output (automatic camelCase for frontend)
json_response = project.model_dump(by_alias=True)
# Result: {
#   "id": "proj_123",
#   "cameraModel": "TestCam Pro", 
#   "createdAt": "2025-09-09T20:47:35",
#   "ownerId": "user_123"
# }
```

### Backward Compatibility

```python
# Accepts snake_case input
DetectionEvent(**{
    "test_session_id": "session_123",
    "class_label": "pedestrian"
})

# Also accepts camelCase input
DetectionEvent(**{
    "testSessionId": "session_456",
    "classLabel": "cyclist"  
})

# Both produce identical camelCase JSON output
```

## Migration Guide

### For Backend Developers

1. **Update Schema Inheritance:**
   ```python
   # Old
   class MySchema(BaseModel):
   
   # New  
   class MySchema(CamelCaseModel):
   ```

2. **Remove Manual Aliases:**
   ```python
   # Old
   field_name: str = Field(alias="fieldName")
   
   # New
   field_name: str
   ```

3. **Remove Config Classes:**
   ```python
   # Old
   class Config:
       populate_by_name = True
       from_attributes = True
   
   # New
   # Not needed - handled by CamelCaseModel
   ```

### For Frontend Developers

1. **Update Models:** Remove duplicate fields from TypeScript interfaces:
   ```typescript
   // Old
   interface Project {
     file_size: number;    // Remove this
     fileSize: number;     // Keep this
     created_at: string;   // Remove this  
     createdAt: string;    // Keep this
   }
   
   // New
   interface Project {
     fileSize: number;     // Only camelCase
     createdAt: string;    // Only camelCase
   }
   ```

2. **API Calls:** Use camelCase consistently:
   ```javascript
   // All API responses now use camelCase
   const response = await api.get('/projects/123');
   console.log(response.cameraModel);  // ✓ Works
   console.log(response.camera_model); // ✗ Undefined
   ```

## Testing and Validation

### Test Coverage
- ✅ snake_to_camel conversion function
- ✅ Schema serialization (camelCase output)
- ✅ Backward compatibility (accepts both formats)
- ✅ All existing schema models
- ✅ Integration with FastAPI

### Performance Impact
- **Minimal overhead:** Alias generation happens at class definition time
- **No runtime penalty:** Field mapping is cached by Pydantic
- **Memory efficient:** No duplicate field storage

## Benefits Achieved

### 1. Eliminated Duplicate Fields
- **Before:** Frontend models had both `file_size` and `fileSize`
- **After:** Only `fileSize` in JSON responses

### 2. Reduced Maintenance Overhead
- **Before:** 50+ manual `Field(alias="...")` declarations
- **After:** Zero manual alias declarations needed

### 3. Consistent API Responses
- **Before:** Mix of snake_case and camelCase in responses
- **After:** 100% camelCase in all JSON outputs

### 4. Backward Compatibility
- **Accepts:** Both `test_session_id` and `testSessionId` in requests
- **Returns:** Always `testSessionId` in responses

### 5. Type Safety
- **Maintains:** Full Pydantic validation and type checking
- **Preserves:** SQLAlchemy integration with `from_attributes=True`

## Future Considerations

### Extending the Pattern
```python
# Easy to extend for other transformations
class PascalCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_pascal,  # TestSessionId
        populate_by_name=True,
        by_alias=True
    )

class KebabCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_kebab,   # test-session-id
        populate_by_name=True, 
        by_alias=True
    )
```

### GraphQL Integration
```python
class GraphQLModel(CamelCaseModel):
    # Automatically compatible with GraphQL naming conventions
    pass
```

## Conclusion

The automatic schema transformation architecture successfully:

1. **Eliminates** frontend model duplication
2. **Maintains** clean separation between backend (snake_case) and frontend (camelCase)
3. **Reduces** maintenance overhead by removing manual alias management
4. **Ensures** backward compatibility with existing API clients
5. **Provides** consistent, predictable API responses

This solution scales automatically as new schemas are added, requiring zero additional configuration for standard snake_case to camelCase transformations.