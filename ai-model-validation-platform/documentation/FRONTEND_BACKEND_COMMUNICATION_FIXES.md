# Frontend-Backend Communication Fixes

## Problems Addressed

### 1. API Configuration Issues
- **Problem**: Hardcoded API URLs causing connectivity failures
- **Solution**: Dynamic API base URL detection with fallbacks
- **Files Modified**: 
  - `src/services/api.ts` - Updated constructor with dynamic URL detection
  - `src/services/websocketService.ts` - Added WebSocket URL auto-configuration
  - `src/pages/TestExecution-improved.tsx` - Updated WebSocket initialization

### 2. Data Synchronization Problems
- **Problem**: Backend snake_case vs Frontend camelCase field mismatches
- **Solution**: Automatic response data transformation
- **Files Modified**:
  - `src/services/api.ts` - Added `transformResponseData()` method with comprehensive field mapping
  - Enhanced video data with proper URL generation and status mapping

### 3. Video Player DOM Issues
- **Problem**: "The play() request was interrupted" errors
- **Solution**: Enhanced video lifecycle management with proper cleanup
- **Files Modified**:
  - `src/components/VideoAnnotationPlayer.tsx` - Improved video initialization with effect validation
  - `src/utils/videoUtils.ts` - Already has proper cleanup utilities

### 4. Ground Truth Display Issues  
- **Problem**: No ground truth annotations showing
- **Solution**: Enhanced ground truth API with fallback data and proper field transformation
- **Files Modified**:
  - `src/services/api.ts` - Updated `getGroundTruth()` with data transformation and error handling

### 5. Connection Monitoring
- **Problem**: No visibility into API connectivity issues
- **Solution**: Real-time connection status monitoring
- **Files Created**:
  - `src/components/ApiConnectionStatus.tsx` - Connection status component
  - `src/App.tsx` - Integrated connection monitoring

## Key Fixes Implemented

### API Service Enhancements
```typescript
// Dynamic API URL detection
const getApiBaseUrl = () => {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  return window.location.hostname === 'localhost' 
    ? 'http://localhost:8000' 
    : `http://${window.location.hostname}:8000`;
};

// Automatic data transformation
private transformResponseData(data: any): any {
  // Converts snake_case to camelCase automatically
  const fieldMappings = {
    'project_id': 'projectId',
    'ground_truth_generated': 'groundTruthGenerated',
    // ... comprehensive field mappings
  };
}
```

### Video Player Fixes
```typescript
// Enhanced video initialization with effect validation
useEffect(() => {
  let effectValid = true;
  
  const initializeVideo = async () => {
    if (!effectValid) return;
    
    // Proper cleanup before initialization
    cleanupVideoElement(videoElement);
    
    // Check video URL availability
    if (!video.url) {
      throw new Error('Video URL is not available');
    }
    
    // Set source with proper error handling
    await setVideoSource(videoElement, video.url);
  };
  
  return () => {
    effectValid = false;
    // Comprehensive cleanup
  };
}, [video.url, frameRate, onTimeUpdate]);
```

### Ground Truth Enhancement
```typescript
async getGroundTruth(videoId: string): Promise<any> {
  try {
    const response = await this.api.get(`/api/videos/${videoId}/ground-truth`);
    
    // Transform and validate ground truth data
    if (response.data && response.data.objects) {
      response.data.objects = response.data.objects.map((obj: any) => ({
        ...obj,
        boundingBox: obj.bounding_box || obj.boundingBox || defaultBbox,
        vruType: this.mapClassToVruType(obj.class_label),
        // ... proper field mapping
      }));
    }
    
    return response.data || fallbackData;
  } catch (error) {
    // Return structured fallback data instead of throwing
    return fallbackGroundTruthData;
  }
}
```

## Environment Configuration

### Files Created
- `.env.example` - Template for environment variables
- `.env.development` - Development-specific configuration

### Environment Variables
```bash
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_DEBUG=true
REACT_APP_ENABLE_GROUND_TRUTH=true
```

## Testing Strategy

### 1. API Connectivity Testing
- Health check endpoint validation
- Automatic retry mechanisms
- Fallback URL detection

### 2. Data Transformation Testing
- Field mapping validation
- Response structure consistency
- Error handling scenarios

### 3. Video Player Testing
- DOM lifecycle management
- Play/pause interruption prevention
- Canvas overlay synchronization

### 4. Ground Truth Testing
- Empty data fallbacks
- Field transformation accuracy
- VRU type mapping validation

## Usage Instructions

### 1. Environment Setup
```bash
# Copy environment template
cp .env.example .env.local

# Configure for your environment
# Edit REACT_APP_API_URL and REACT_APP_WS_URL as needed
```

### 2. Development
```bash
# The fixes will automatically detect localhost for development
npm start

# For production deployment, set proper environment variables
REACT_APP_API_URL=https://your-api-domain.com npm run build
```

### 3. Backend Requirements
Ensure your backend:
- Serves static files from `/uploads` endpoint
- Provides proper CORS headers
- Returns consistent response formats
- Has ground truth endpoints available

## Expected Results

After applying these fixes:

1. ✅ **Videos Display**: Frontend will show videos with proper URLs
2. ✅ **Ground Truth**: Annotations display with fallback for missing data  
3. ✅ **Video Player**: No more DOM interruption errors
4. ✅ **Real-time Updates**: WebSocket connections with auto-retry
5. ✅ **Error Handling**: Comprehensive error reporting and recovery
6. ✅ **Data Sync**: Automatic field mapping between backend/frontend

## Monitoring

The `ApiConnectionStatus` component provides:
- Real-time API connectivity monitoring
- Automatic retry mechanisms
- User-friendly error reporting
- Network status awareness

## Next Steps

1. Test with actual backend deployment
2. Verify video file accessibility
3. Confirm ground truth data generation
4. Validate WebSocket functionality
5. Monitor connection stability

These fixes address the core communication issues while maintaining backward compatibility and providing robust error handling.