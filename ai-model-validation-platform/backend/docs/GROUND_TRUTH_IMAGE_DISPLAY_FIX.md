# GROUND TRUTH PAGE - AI DETECTION IMAGE DISPLAY FIX

## ROOT CAUSE ANALYSIS - 5 WHY

### WHY 1: Why are AI detection images not showing with bounding boxes in Ground Truth page?
→ Because the Ground Truth page is using basic `VideoAnnotationPlayer` in Classic mode by default

### WHY 2: Why is Classic mode being used instead of Enhanced mode?
→ Because `enhancedAnnotationMode` is set to `false` by default in line 180 of GroundTruth.tsx

### WHY 3: Why doesn't Classic mode show bounding boxes?
→ Because `VideoAnnotationPlayer` is a basic component that just shows a plain video element with no overlay canvas for bounding boxes

### WHY 4: Why aren't AI detections being displayed even if loaded?
→ Because the Classic mode doesn't have the rendering logic for drawing bounding boxes or showing detection images

### WHY 5: Why does the system have two modes if one doesn't work?
→ Because Enhanced mode was developed to add bounding box support but wasn't made the default

## IDENTIFIED ISSUES

1. **Wrong Default Mode**: Classic mode is default but doesn't support bounding boxes
2. **No Bounding Box Rendering**: Classic `VideoAnnotationPlayer` has no canvas overlay
3. **Missing Detection Display**: No component showing AI detection images in Classic mode
4. **URL Path Issue**: Frontend was double-processing screenshot paths (already fixed)

## SOLUTIONS IMPLEMENTED

### 1. Frontend URL Fix (Already Applied)
- **File**: `/frontend/src/components/RealDetectionPanel.tsx`
- **Change**: Use API paths directly instead of extracting filename
- **Before**: `src={/screenshots/${detection.screenshot_path?.split('/').pop()}`
- **After**: `src={detection.screenshot_path || '/placeholder-image.png'}`

### 2. Required Changes for Ground Truth Page

#### Option A: Enable Enhanced Mode by Default
```typescript
// Line 180 in GroundTruth.tsx
const [enhancedAnnotationMode, setEnhancedAnnotationMode] = useState(true); // Change to true
```

#### Option B: Add Detection Display to Classic Mode
- Import and use `RealDetectionPanel` in Classic mode
- Add canvas overlay to `VideoAnnotationPlayer` for bounding boxes

## CURRENT STATE

### What's Working:
- ✅ Backend API returns 264 AI detections with screenshot paths
- ✅ Screenshot files exist (2400+ files in /screenshots/)
- ✅ Static file serving works (HTTP 200 for all images)
- ✅ API returns proper URL format: `/screenshots/detection_123.jpg`
- ✅ RealDetectionPanel component fixed to use correct URLs

### What's Not Working:
- ❌ Ground Truth page defaults to Classic mode (no bounding boxes)
- ❌ Classic mode VideoAnnotationPlayer doesn't render detections
- ❌ User needs to manually toggle to Enhanced mode

## USER INSTRUCTIONS

### To See AI Detection Images with Bounding Boxes:

1. **Navigate to Ground Truth Page**
   - Go to `http://localhost:3000/ground-truth`

2. **Select a Video**
   - Choose a video that has AI detections

3. **IMPORTANT: Enable Enhanced Mode**
   - Look for "Enhanced Annotation Mode" toggle
   - Click to enable it (should turn ON/blue)

4. **View AI Detections**
   - Bounding boxes should appear on video
   - Detection panel should show confidence scores
   - Images should be visible with visual evidence

### Alternative: Use HIL Test Execution Page
- Navigate to `http://localhost:3000/test-execution`
- This page uses `RealDetectionPanel` which properly shows AI detection images

## PERMANENT FIX RECOMMENDATION

Change line 180 in `/frontend/src/pages/GroundTruth.tsx`:
```typescript
const [enhancedAnnotationMode, setEnhancedAnnotationMode] = useState(true);
```

This will make Enhanced mode the default, ensuring users see bounding boxes and AI detections immediately.