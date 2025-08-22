# Video ID Fix Summary - Detection Pipeline

## 🎯 **Issue Fixed**
**Problem**: Detection pipeline was creating detection payloads missing the required `videoId` field, causing Pydantic validation failures when the data was processed by API endpoints expecting annotation-compatible formats.

**Error Details**:
- Video being processed: `690fff86-3a74-4d81-ac93-939c5c55de58.mp4`
- Pipeline creating detection IDs: `DET_PED_0001`, `DET_CYC_0001`, etc.
- Error: Pydantic validation failing because `videoId` field missing from request body

## 🔧 **Root Cause Analysis**

1. **Detection Pipeline Issue**: The `process_video` and `_process_video_sync` methods in `DetectionPipelineService` were creating detection dictionaries without including the video ID information.

2. **Schema Mismatch**: Detection data was being validated against `AnnotationCreate` schema (which requires `videoId`) instead of `DetectionEvent` schema.

3. **Missing Parameter Passing**: The `process_video_with_storage` method had the video ID but wasn't passing it to the underlying `process_video` method.

## ✅ **Fixes Implemented**

### 1. Detection Pipeline Service Updates (`services/detection_pipeline_service.py`)

**Updated Method Signatures**:
```python
# BEFORE
async def process_video(self, video_path: str, config: dict = None) -> List[Dict]:
def _process_video_sync(self, video_path: str, config: dict = None) -> List[Dict]:

# AFTER  
async def process_video(self, video_path: str, video_id: str = None, config: dict = None) -> List[Dict]:
def _process_video_sync(self, video_path: str, video_id: str = None, config: dict = None) -> List[Dict]:
```

**Fixed Parameter Passing**:
```python
# BEFORE
detections = await self.process_video(video_path, config)

# AFTER
detections = await self.process_video(video_path, video_id, config)
```

**Enhanced Detection Dictionary Creation**:
```python
# BEFORE
detection_dict = {
    "id": detection.detection_id or str(uuid.uuid4()),
    "frame_number": detection.frame_number,
    "timestamp": detection.timestamp,
    "class_label": detection.class_label,
    "confidence": detection.confidence,
    "bounding_box": detection.bounding_box.to_dict(),
    "vru_type": detection.class_label,
}

# AFTER
detection_dict = {
    "id": detection.detection_id or str(uuid.uuid4()),
    "frame_number": detection.frame_number,
    "timestamp": detection.timestamp,
    "class_label": detection.class_label,
    "confidence": detection.confidence,
    "bounding_box": detection.bounding_box.to_dict(),
    "vru_type": detection.class_label,
}

# Critical fix: Add video ID for Pydantic validation if available
if video_id:
    detection_dict["videoId"] = video_id  # For API/Pydantic validation
    detection_dict["video_id"] = video_id  # For database compatibility
```

### 2. Video ID Extraction Logic

**Enhanced Video ID Handling**:
```python
# Initialize timeline - Generate video_id if not provided
if not video_id:
    # Try to extract video ID from filename (format: uuid.ext)
    video_filename = Path(video_path).stem
    if len(video_filename.split('-')) == 5:  # UUID format check
        video_id = video_filename
        logger.info(f"📁 Extracted video ID from filename: {video_id}")
    else:
        video_id = str(uuid.uuid4())
        logger.info(f"🆔 Generated new video ID: {video_id}")
```

### 3. Fixed Detection Service Compatibility

The `FixedDetectionService` already had proper video ID handling:
```python
# Add video_id to each detection (FIX for database error)
for det in detections:
    det['videoId'] = video_id  # Critical fix!
    det['video_id'] = video_id  # Add both formats
```

## 🧪 **Testing & Validation**

Created `test_video_id_fix.py` to verify the fixes:

### Test Results:
- ✅ Video ID extraction from filename works for UUID format (`690fff86-3a74-4d81-ac93-939c5c55de58`)
- ✅ Detection payloads now include both `videoId` and `video_id` fields
- ✅ All required fields present in detection payloads
- ✅ API schema compatibility verified
- ✅ Detection pipeline initialization successful

## 📋 **API Compatibility**

### Detection Event Schema (main detection endpoint)
```python
class DetectionEvent(BaseModel):
    test_session_id: str = Field(alias="testSessionId")
    timestamp: float
    confidence: Optional[float] = None
    class_label: Optional[str] = Field(None, alias="classLabel")
    validation_result: Optional[str] = Field(None, alias="validationResult")
```

### Annotation Create Schema (annotation endpoints)
```python
class AnnotationCreate(BaseModel):
    video_id: str = Field(alias="videoId")  # REQUIRED
    detection_id: Optional[str] = Field(None, alias="detectionId")
    frame_number: int = Field(alias="frameNumber")
    timestamp: float
    vru_type: VRUTypeEnum = Field(alias="vruType")
    bounding_box: Dict[str, Any] = Field(alias="boundingBox")
    # ... other fields
```

## 🎯 **Video ID Resolution Strategy**

1. **Explicit Parameter**: Use `video_id` parameter if provided to `process_video_with_storage`
2. **Filename Extraction**: Extract UUID from filename if it matches UUID format (5 dash-separated segments)
3. **Fallback Generation**: Generate new UUID if no video ID available

## 🔄 **API Endpoints Affected**

### Fixed Endpoints:
- `POST /api/detection/pipeline/run` - Now properly includes videoId in all detection data
- Detection processing in background tasks
- Video processing with storage functionality

### Example Usage:
```bash
curl -X POST http://localhost:8000/api/detection/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"video_id": "690fff86-3a74-4d81-ac93-939c5c55de58", "confidence_threshold": 0.4, "model_name": "yolo11l"}'
```

## 📁 **Files Modified**

1. `/services/detection_pipeline_service.py`
   - Updated method signatures to accept video_id parameter
   - Enhanced detection dictionary creation with videoId field
   - Added video ID extraction from filename logic
   - Fixed parameter passing in `process_video_with_storage`

2. `/test_video_id_fix.py` (new)
   - Comprehensive test suite for video ID fixes
   - Validates extraction logic and API compatibility

## 🎉 **Resolution Status: COMPLETE** ✅

**The video ID issue is now fully resolved**:
- ✅ Detection payloads include required `videoId` field
- ✅ Video ID extraction from filename works correctly  
- ✅ API schema compatibility maintained
- ✅ Both `videoId` and `video_id` fields included for maximum compatibility
- ✅ Tested and validated with comprehensive test suite

**Impact**: Detection processing for video `690fff86-3a74-4d81-ac93-939c5c55de58.mp4` will now work correctly without Pydantic validation errors.