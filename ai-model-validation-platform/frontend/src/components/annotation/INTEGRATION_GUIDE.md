# Integration Guide: Enhanced Annotation System

This guide shows how to integrate the enhanced annotation system into the existing AI Model Validation Platform.

## 🔄 Updating GroundTruth.tsx

### Step 1: Import Enhanced Components

```tsx
// Add these imports to GroundTruth.tsx
import { 
  EnhancedVideoAnnotationPlayer,
  AnnotationProvider,
  createAnnotationShape,
  convertToLabelStudio,
  convertFromLabelStudio,
  VRU_TYPE_COLORS
} from '../components/annotation';
```

### Step 2: Replace VideoAnnotationPlayer

Replace the existing VideoAnnotationPlayer usage in the dialog:

```tsx
// OLD: Basic VideoAnnotationPlayer
<VideoAnnotationPlayer
  video={selectedVideo}
  annotations={annotations}
  onAnnotationSelect={setSelectedAnnotation}
  onTimeUpdate={handleTimeUpdate}
  onCanvasClick={handleCanvasClick}
  annotationMode={annotationMode}
  selectedAnnotation={selectedAnnotation}
  frameRate={frameRate}
/>

// NEW: Enhanced VideoAnnotationPlayer
<EnhancedVideoAnnotationPlayer
  video={selectedVideo}
  annotations={annotations}
  onAnnotationSelect={setSelectedAnnotation}
  onTimeUpdate={handleTimeUpdate}
  onCanvasClick={handleCanvasClick}
  annotationMode={annotationMode}
  selectedAnnotation={selectedAnnotation}
  frameRate={frameRate}
  onAnnotationCreate={handleAnnotationCreate}
  onAnnotationUpdate={handleAnnotationUpdate}
  onAnnotationDelete={handleAnnotationDelete}
/>
```

### Step 3: Update State Management

Add enhanced annotation state:

```tsx
// Add to GroundTruth component state
const [enhancedAnnotationMode, setEnhancedAnnotationMode] = useState(true);
const [annotationShapes, setAnnotationShapes] = useState<AnnotationShape[]>([]);
const [annotationHistory, setAnnotationHistory] = useState<AnnotationAction[]>([]);

// Convert existing annotations to shapes
const convertAnnotationsToShapes = useCallback((annotations: GroundTruthAnnotation[]) => {
  return annotations.map(annotation => createAnnotationShape(
    'rectangle',
    [
      { x: annotation.boundingBox.x, y: annotation.boundingBox.y },
      { x: annotation.boundingBox.x + annotation.boundingBox.width, y: annotation.boundingBox.y },
      { x: annotation.boundingBox.x + annotation.boundingBox.width, y: annotation.boundingBox.y + annotation.boundingBox.height },
      { x: annotation.boundingBox.x, y: annotation.boundingBox.y + annotation.boundingBox.height },
    ],
    {
      strokeColor: VRU_TYPE_COLORS[annotation.vruType] || '#607d8b',
      fillColor: `${VRU_TYPE_COLORS[annotation.vruType] || '#607d8b'}20`,
    }
  ));
}, []);

// Update annotations when they change
useEffect(() => {
  setAnnotationShapes(convertAnnotationsToShapes(annotations));
}, [annotations, convertAnnotationsToShapes]);
```

### Step 4: Add Mode Toggle

Add a toggle to switch between classic and enhanced modes:

```tsx
// Add to the dialog header area
<FormControlLabel
  control={
    <Switch
      checked={enhancedAnnotationMode}
      onChange={(e) => setEnhancedAnnotationMode(e.target.checked)}
    />
  }
  label="Enhanced Annotation Mode"
/>
```

### Step 5: Update Export Functions

Enhance the export functionality:

```tsx
const handleExportAnnotations = useCallback(async (format: 'coco' | 'yolo' | 'pascal' | 'json' | 'labelstudio') => {
  if (!selectedVideo) return;

  try {
    let exportData;
    
    if (format === 'labelstudio') {
      // Export as Label Studio format
      exportData = convertToLabelStudio(annotationShapes);
    } else {
      // Use existing export API
      exportData = await apiService.exportAnnotations(selectedVideo.id, format);
    }
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `${selectedVideo.filename}_annotations.${format === 'labelstudio' ? 'json' : format}`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    
    setSuccessMessage(`Annotations exported as ${format.toUpperCase()}`);
  } catch (err) {
    setError(`Failed to export annotations: ${getErrorMessage(err)}`);
  }
}, [selectedVideo, annotationShapes]);

// Add Label Studio export button
<Button 
  variant="outlined" 
  startIcon={<GetApp />}
  onClick={() => handleExportAnnotations('labelstudio')}
>
  Export Label Studio
</Button>
```

## 🎯 Advanced Integration Features

### Custom Annotation Tools

Create project-specific annotation tools:

```tsx
// Custom VRU-specific tool
const VRUAnnotationTool = ({ vruType, onComplete }) => {
  const { actions } = useAnnotation();
  
  const createVRUAnnotation = useCallback((point: Point) => {
    const shape = createAnnotationShape('rectangle', [
      point,
      { x: point.x + 50, y: point.y },
      { x: point.x + 50, y: point.y + 100 },
      { x: point.x, y: point.y + 100 },
    ], {
      strokeColor: VRU_TYPE_COLORS[vruType],
      fillColor: `${VRU_TYPE_COLORS[vruType]}20`,
    });
    
    shape.label = vruType;
    actions.addShape(shape);
    onComplete?.(shape);
  }, [vruType, actions, onComplete]);
  
  return {
    createVRUAnnotation,
    // ... tool implementation
  };
};
```

### Batch Operations

Add bulk annotation operations:

```tsx
// Bulk label assignment
const handleBulkLabelAssignment = useCallback((vruType: string) => {
  const selectedShapes = actions.getSelectedShapes();
  selectedShapes.forEach(shape => {
    actions.updateShape(shape.id, { 
      label: vruType,
      style: {
        ...shape.style,
        strokeColor: VRU_TYPE_COLORS[vruType],
        fillColor: `${VRU_TYPE_COLORS[vruType]}20`,
      }
    });
  });
}, [actions]);

// Bulk validation
const handleBulkValidation = useCallback((validated: boolean) => {
  const selectedAnnotations = annotations.filter(ann => 
    annotationShapes.some(shape => shape.id === ann.id)
  );
  
  const updatePromises = selectedAnnotations.map(ann =>
    apiService.validateAnnotation(ann.id, validated)
  );
  
  Promise.all(updatePromises)
    .then(() => {
      setSuccessMessage(`${selectedAnnotations.length} annotations ${validated ? 'validated' : 'invalidated'}`);
      loadAnnotations(selectedVideo.id);
    })
    .catch(err => setError(`Bulk validation failed: ${getErrorMessage(err)}`));
}, [annotations, annotationShapes, selectedVideo]);
```

### Quality Assurance Features

Add QA workflow integration:

```tsx
// Annotation quality metrics
const getAnnotationQuality = useCallback((annotation: GroundTruthAnnotation) => {
  const metrics = {
    confidence: annotation.boundingBox.confidence || 0,
    size: annotation.boundingBox.width * annotation.boundingBox.height,
    aspectRatio: annotation.boundingBox.width / annotation.boundingBox.height,
    validated: annotation.validated,
  };
  
  // Quality score calculation
  let score = 0;
  if (metrics.confidence > 0.8) score += 30;
  if (metrics.size > 1000) score += 20;
  if (metrics.aspectRatio > 0.3 && metrics.aspectRatio < 3) score += 25;
  if (metrics.validated) score += 25;
  
  return { metrics, score };
}, []);

// Quality dashboard
const QualityDashboard = ({ annotations }) => {
  const qualityData = annotations.map(getAnnotationQuality);
  const avgScore = qualityData.reduce((sum, q) => sum + q.score, 0) / qualityData.length;
  
  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Typography variant="h6" gutterBottom>Quality Metrics</Typography>
      <Grid container spacing={2}>
        <Grid item xs={3}>
          <Chip label={`Avg Score: ${avgScore.toFixed(0)}`} color="primary" />
        </Grid>
        <Grid item xs={3}>
          <Chip label={`Validated: ${qualityData.filter(q => q.metrics.validated).length}`} color="success" />
        </Grid>
        <Grid item xs={3}>
          <Chip label={`High Confidence: ${qualityData.filter(q => q.metrics.confidence > 0.8).length}`} color="info" />
        </Grid>
        <Grid item xs={3}>
          <Chip label={`Total: ${annotations.length}`} variant="outlined" />
        </Grid>
      </Grid>
    </Paper>
  );
};
```

## 🔧 Migration Checklist

### Pre-Migration

- [ ] Backup existing annotations
- [ ] Test enhanced components in isolation
- [ ] Verify TypeScript compatibility
- [ ] Check performance with large datasets

### During Migration

- [ ] Update import statements
- [ ] Replace VideoAnnotationPlayer with EnhancedVideoAnnotationPlayer
- [ ] Add AnnotationProvider wrapper
- [ ] Update state management
- [ ] Test keyboard shortcuts
- [ ] Verify export functionality

### Post-Migration

- [ ] Test all annotation tools
- [ ] Verify undo/redo functionality
- [ ] Check copy/paste operations
- [ ] Test zoom and pan
- [ ] Validate data integrity
- [ ] Performance testing
- [ ] User acceptance testing

### Rollback Plan

Keep the original VideoAnnotationPlayer as fallback:

```tsx
const useEnhancedMode = useState(true);

return (
  <Box>
    <FormControlLabel
      control={<Switch checked={useEnhancedMode} onChange={setUseEnhancedMode} />}
      label="Enhanced Mode"
    />
    
    {useEnhancedMode ? (
      <EnhancedVideoAnnotationPlayer {...props} />
    ) : (
      <VideoAnnotationPlayer {...props} />
    )}
  </Box>
);
```

## 📊 Performance Considerations

### Memory Management

```tsx
// Limit annotation history
<AnnotationProvider maxHistorySize={50}>
  <EnhancedVideoAnnotationPlayer />
</AnnotationProvider>

// Cleanup on unmount
useEffect(() => {
  return () => {
    // Clear large annotation datasets
    actions.clearAll();
  };
}, []);
```

### Rendering Optimization

```tsx
// Use React.memo for heavy components
const MemoizedAnnotationCanvas = React.memo(EnhancedAnnotationCanvas);

// Debounce rapid updates
const debouncedUpdateAnnotation = useCallback(
  debounce((updates) => {
    onAnnotationUpdate(updates);
  }, 300),
  [onAnnotationUpdate]
);
```

### Large Dataset Handling

```tsx
// Paginate annotations
const [annotationPage, setAnnotationPage] = useState(0);
const ANNOTATIONS_PER_PAGE = 100;

const paginatedAnnotations = useMemo(() => {
  const start = annotationPage * ANNOTATIONS_PER_PAGE;
  return annotations.slice(start, start + ANNOTATIONS_PER_PAGE);
}, [annotations, annotationPage]);

// Virtual scrolling for shape list
import { FixedSizeList } from 'react-window';

const ShapeListItem = ({ index, style, data }) => (
  <div style={style}>
    <ShapeItem shape={data[index]} />
  </div>
);

<FixedSizeList
  height={300}
  itemCount={annotationShapes.length}
  itemSize={50}
  itemData={annotationShapes}
>
  {ShapeListItem}
</FixedSizeList>
```

## 🐛 Common Issues & Solutions

### Issue: Tools not working
**Solution**: Ensure AnnotationProvider wraps the components and annotationMode is enabled.

### Issue: Performance degradation
**Solution**: Limit history size, use shape visibility, implement virtual scrolling for large datasets.

### Issue: Keyboard shortcuts conflicts
**Solution**: Check for input field focus, implement proper event handling priority.

### Issue: Export format incompatibility
**Solution**: Use conversion utilities, validate data structure before export.

This integration guide provides a comprehensive approach to upgrading the existing annotation system while maintaining backward compatibility and ensuring smooth user experience.