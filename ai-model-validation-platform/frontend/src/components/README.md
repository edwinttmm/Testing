# Annotation Validation Interface Components

This directory contains the complete implementation of PRD Module 1.3 - Annotation Validation Interface.

## Components Overview

### 1. AnnotationValidationInterface.tsx
**Main component** implementing all PRD Module 1.3 requirements:
- Large central video viewport with HTML5 video player
- Interactive timeline with annotation markers  
- Direct bounding box manipulation (click, resize, move)
- Object management with VRU type correction
- VRU ID merge/split functionality
- Frame-by-frame navigation controls
- Validation workflow (mark as "Validated")

**Key Features:**
- Real video file support (no dummy data)
- PRD-aligned variable names from GLOBAL_VARIABLES_REFERENCE.md
- Keyboard navigation (← → for frame navigation, Space for play/pause)
- Zoom controls and fullscreen mode
- Real-time bounding box overlay on video

### 2. VideoViewport.tsx
**Large central video viewport** component with:
- HTML5 video element with custom controls
- Canvas overlay for bounding box rendering
- Direct manipulation handlers (drag, resize)
- Zoom and fullscreen functionality
- Frame-by-frame precision controls

### 3. InteractiveTimeline.tsx
**Interactive timeline** with annotation markers:
- Visual timeline with progress tracking
- Annotation markers color-coded by VRU type
- Click-to-jump navigation
- Frame and time input controls
- VRU type distribution display
- Validation progress indicators

### 4. ObjectManagementPanel.tsx
**VRU object management** with:
- Current frame object listing
- VRU type correction dropdowns
- Merge/split mode toggles
- Bulk validation operations
- Object filtering and selection
- Validation status indicators

### 5. ValidationWorkflowPanel.tsx
**Validation workflow** panel with:
- Comprehensive validation statistics
- Quality score calculation
- Validation requirements checklist
- Progress tracking and reporting
- Export validated annotations
- Final validation confirmation dialog

## PRD Module 1.3 Requirements Coverage

✅ **Large central video viewport**
- HTML5 video player with custom controls
- Real video file streaming support
- Canvas overlay for annotations

✅ **Interactive timeline with annotation markers**  
- Visual timeline with frame markers
- Color-coded VRU type indicators
- Click navigation and frame jumping

✅ **Direct bounding box manipulation**
- Click to select objects
- Drag to move bounding boxes
- Resize handles on corners
- Real-time visual feedback

✅ **Object management capabilities**
- Correct mislabeled objects (VRU type changes)
- Create new annotations for missed detections
- Delete false positives
- Bulk operations support

✅ **VRU ID merge/split functionality**
- Merge multiple IDs that track same VRU
- Split single ID tracking multiple VRUs
- Persistent VRU ID management

✅ **Frame-by-frame navigation**
- Previous/next frame buttons
- Keyboard arrow key support
- Direct frame number input
- Time-based navigation

✅ **Validation workflow**
- Mark video annotations as "Validated"
- Lock annotations after validation
- Progress tracking and statistics
- Export validated annotations

## Technical Implementation

### Data Flow
1. **Video Loading**: Loads real video files from backend API
2. **Annotation Loading**: Fetches existing ground truth objects
3. **Real-time Manipulation**: Direct bounding box editing with API sync
4. **Validation Process**: Multi-step validation with requirements checking

### API Integration
- Uses real `apiService` calls (no mocks)
- Syncs all changes to backend database
- Handles video streaming and metadata
- Supports annotation CRUD operations

### Performance Features
- Canvas-based rendering for smooth interactions
- Debounced API calls during manipulation
- Efficient re-rendering with React hooks
- Memory management for video playback

## Usage

### Navigation
```typescript
// Access via routing
/annotation-validation/:videoId

// Or programmatically
navigate('/annotation-validation/video-123');
```

### Integration with Ground Truth Page
The interface integrates with the existing Ground Truth management page, accessible via the "Edit" button on validated videos.

### Keyboard Shortcuts
- `←` `→`: Frame navigation
- `Space`: Play/pause video
- `F`: Toggle fullscreen
- `Esc`: Exit fullscreen

## Variable Naming Compliance

All components use exact variable names from `GLOBAL_VARIABLES_REFERENCE.md`:
- `groundTruthObjects` instead of `annotations`
- `vruId` for persistent VRU tracking
- `timestampMs` for millisecond precision
- `boundingBox` with exact bbox structure
- `videoId`, `projectId` for entity relationships

## File Organization

```
src/components/
├── AnnotationValidationInterface.tsx     # Main interface
├── VideoViewport.tsx                     # Large video player
├── InteractiveTimeline.tsx               # Timeline with markers
├── ObjectManagementPanel.tsx             # VRU management
├── ValidationWorkflowPanel.tsx           # Validation workflow
└── README.md                             # This documentation
```

## Next Steps

The annotation validation interface is now complete and ready for:
1. Integration testing with real video files
2. User acceptance testing
3. Performance optimization if needed
4. Integration with LabJack hardware (Module 3)

This implementation fully satisfies PRD Module 1.3 requirements with production-ready code and no placeholder/dummy data.