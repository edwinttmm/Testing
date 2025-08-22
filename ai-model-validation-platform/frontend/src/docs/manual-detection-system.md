# Manual Detection System Documentation

## Overview

This document describes the comprehensive manual detection system implementation that replaces automatic detection triggers in the Ground Truth Management interface.

## Components

### 1. DetectionControls Component (`/src/components/DetectionControls.tsx`)

**Purpose**: Provides manual controls for starting/stopping detection with comprehensive configuration options.

**Features**:
- **Start/Stop Buttons**: Manual trigger only - no automatic detection
- **Status Indicator**: Real-time progress tracking with visual feedback
- **Progress Bar**: Shows detection pipeline stages (Initializing → Processing → Analyzing → Saving)
- **Error Handling**: Comprehensive error display with retry mechanisms (up to 3 attempts)
- **Advanced Settings**: 
  - Model selection (YOLOv8 Nano/Small/Medium)
  - Confidence threshold slider (0.1-0.9)
  - NMS threshold slider (0.1-0.9) 
  - Target classes multi-select
- **Retry Logic**: Progressive retry strategy with different models and thresholds

**Key Props**:
```typescript
interface DetectionControlsProps {
  video: VideoFile;
  onDetectionStart: () => void;
  onDetectionComplete: (annotations: GroundTruthAnnotation[]) => void;
  onDetectionError: (error: string) => void;
  disabled?: boolean;
  initialConfig?: Partial<DetectionConfig>;
}
```

### 2. Updated GroundTruth Component (`/src/pages/GroundTruth.tsx`)

**Changes Made**:
- ✅ **Removed all automatic detection triggers**
- ✅ **Integrated DetectionControls component**
- ✅ **Removed WebSocket dependencies** (manual HTTP-only mode)
- ✅ **Enhanced state management** for manual detection workflow
- ✅ **Integrated DetectionResultsPanel** for results display
- ✅ **Proper detection lifecycle management**

**Key Features**:
- Manual detection controls in video player tab
- Real-time detection results display
- Proper annotation saving and tracking
- Error recovery and retry mechanisms
- Project context awareness

### 3. Enhanced VideoAnnotationPlayer (`/src/components/VideoAnnotationPlayer.tsx`)

**New Features**:
- **Optional detection controls support** via props
- **Detection overlay integration** when controls are enabled
- **Maintains existing annotation functionality** unchanged

**New Props**:
```typescript
interface VideoAnnotationPlayerProps {
  // ... existing props
  showDetectionControls?: boolean;
  detectionControlsComponent?: React.ReactNode;
}
```

### 4. Improved DetectionResultsPanel (`/src/components/DetectionResultsPanel.tsx`)

**Enhancements**:
- **Better empty state messaging** - guides users to use detection controls
- **Running state display** during detection
- **High confidence detection highlighting**
- **Improved result display** with better visual hierarchy

## Detection Workflow

### Manual-Only Detection Process

1. **User Navigation**: User opens video in Ground Truth interface
2. **Initial State**: No automatic detection runs - empty results panel shows guidance
3. **Manual Trigger**: User clicks "Start Detection" in DetectionControls
4. **Configuration**: User can adjust detection settings in advanced panel
5. **Execution**: Detection runs with real-time progress updates
6. **Results**: Detected objects are saved as annotations and displayed
7. **Integration**: Results appear in DetectionResultsPanel and video annotations

### Status Tracking

The detection system tracks these stages:
- `idle`: Ready to start
- `initializing`: Setting up detection pipeline (0-20%)
- `processing`: Analyzing video frames (20-70%)
- `analyzing`: Processing detection results (70-85%)
- `saving`: Saving annotations to backend (85-100%)
- `completed`: Detection finished successfully
- `error`: Detection failed with error details

### Error Handling

- **Automatic Retry**: Up to 3 retry attempts with progressive configuration changes
- **Model Fallback**: Tries different YOLO models (YOLOv8s → YOLOv8n)
- **Threshold Adjustment**: Lowers confidence threshold on retries
- **Fallback Detection**: Uses mock data if backend fails (for demo purposes)
- **User Feedback**: Clear error messages with actionable guidance

## Integration Points

### State Management

```typescript
// Detection state in GroundTruth component
const [detectionResults, setDetectionResults] = useState<GroundTruthAnnotation[]>([]);
const [detectionError, setDetectionError] = useState<string | null>(null);
const [isDetectionRunning, setIsDetectionRunning] = useState(false);

// Detection control handlers
const handleDetectionStart = () => {
  setIsDetectionRunning(true);
  setDetectionError(null);
  setDetectionResults([]);
};

const handleDetectionComplete = (newAnnotations: GroundTruthAnnotation[]) => {
  setIsDetectionRunning(false);
  setAnnotations(newAnnotations);
  setDetectionResults(newAnnotations);
  setSuccessMessage(`Detection completed! Found ${newAnnotations.length} objects.`);
};

const handleDetectionError = (error: string) => {
  setIsDetectionRunning(false);
  setDetectionError(error);
  setError(`Detection failed: ${error}`);
};
```

### Service Integration

The detection system integrates with:
- **DetectionService**: HTTP-only detection pipeline
- **API Service**: Annotation saving and retrieval
- **Detection ID Manager**: Tracking and statistics

## Key Benefits

### 1. User Control
- **Manual Trigger Only**: Users decide when to run detection
- **No Surprise Processing**: No automatic resource consumption
- **Configuration Control**: Users can adjust detection parameters

### 2. Transparency
- **Real-time Progress**: Users see exactly what's happening
- **Clear Status**: Stage-by-stage progress indication
- **Error Visibility**: Detailed error messages with recovery options

### 3. Reliability
- **Retry Mechanisms**: Automatic retry with different configurations
- **Fallback Options**: Demo mode if backend unavailable
- **Error Recovery**: Users can manually retry with different settings

### 4. Performance
- **On-Demand Processing**: Only runs when requested
- **Configurable Quality**: Users can balance speed vs accuracy
- **Progress Tracking**: Users know how long to wait

## Testing

### Integration Tests
- **Manual Detection Workflow**: End-to-end manual detection process
- **Component Integration**: DetectionControls + DetectionResultsPanel + VideoAnnotationPlayer
- **Error Scenarios**: Network failures, invalid configurations, retry logic
- **State Management**: Proper state transitions and cleanup

### Test Coverage
- ✅ Manual trigger functionality
- ✅ Advanced configuration options
- ✅ Results display integration
- ✅ Error handling and recovery
- ✅ Component prop interfaces

## Migration Notes

### Removed Features
- ❌ **Automatic detection on video load**
- ❌ **WebSocket connections for detection**
- ❌ **Background processing triggers**
- ❌ **Surprise detection workflows**

### Maintained Features
- ✅ **All annotation functionality**
- ✅ **Video playback controls**
- ✅ **Export capabilities**
- ✅ **Project context management**
- ✅ **Detection result quality**

## Future Enhancements

### Potential Improvements
1. **Batch Detection**: Process multiple videos simultaneously
2. **Background Processing**: Optional background detection with notifications
3. **Detection Presets**: Save and load detection configurations
4. **Performance Analytics**: Track detection accuracy and timing
5. **Custom Models**: Support for user-uploaded detection models

### Technical Debt
- Consider moving detection state to React Context for complex workflows
- Add detection job persistence across page refreshes
- Implement detection queue management for multiple videos
- Add detection result caching

## Usage Examples

### Basic Manual Detection
```typescript
// User opens video → sees empty results
// User clicks "Start Detection" → detection runs
// User sees progress → results appear
// User can retry if needed
```

### Advanced Configuration
```typescript
// User clicks "Advanced" → configuration panel opens
// User adjusts model, thresholds, target classes
// User starts detection with custom settings
// System uses user preferences for detection
```

### Error Recovery
```typescript
// Detection fails → error shown with retry button
// User clicks retry → system tries with different config
// If still fails → user can manually adjust settings
// Maximum 3 retries → clear failure state
```

This manual detection system provides complete user control while maintaining all the functionality of the previous automatic system, with enhanced error handling and user feedback.