# Video Popup Feature - Testing Guide

## Quick Test Instructions

### 1. Start the Application

```bash
# Terminal 1: Start Backend
cd /home/rigade/Testing/ai-model-validation-platform/backend
python main.py

# Terminal 2: Start Frontend
cd /home/rigade/Testing/ai-model-validation-platform/frontend
npm start
```

### 2. Navigate to HIL Results Page

1. Open browser to `http://localhost:3000`
2. Go to any completed HIL test session
3. Navigate to the HIL Results page

### 3. Test Basic Click Functionality

**Expected Behavior:**
- Click any row in the Detection Events table
- Video popup dialog should open
- Video should load and start playing
- Video should seek to the detection timestamp automatically

**Visual Indicators:**
- Row has hover effect (background color changes)
- Cursor changes to pointer on hover
- Dialog appears as full-screen overlay
- Close button (X) in top-right corner

### 4. Verify Dialog Content

**Dialog Header Should Show:**
- Title: "Video Playback - Detection at {timestamp}s"
- Latency value
- Voltage value
- Pass/Fail result

**Example:**
```
Video Playback - Detection at 12.345s
Latency: 45.2ms • Voltage: 3.30V • Result: PASS
```

### 5. Test Video Playback

**Verify:**
- [ ] Video loads within 2-3 seconds
- [ ] Video starts playing automatically
- [ ] Video starts at the correct timestamp
- [ ] Video controls work (play/pause/seek/volume)
- [ ] Fullscreen button works
- [ ] Video quality is good

### 6. Test Dialog Close

**Methods to Close:**
- [ ] Click X button in top-right
- [ ] Click outside the dialog (on backdrop)
- [ ] Press ESC key
- [ ] All methods should close dialog and stop video

### 7. Test Multiple Detections

**Steps:**
1. Click detection row #1
2. Verify video opens
3. Close dialog
4. Click detection row #2
5. Verify different video/timestamp opens
6. Repeat for 3-4 different detections

**Verify:**
- Dialog reuses same component (no memory leaks)
- Video URL changes correctly
- Timestamp changes correctly
- Previous video stops playing

### 8. Test Multi-Video Scenarios (if applicable)

**For Video Sequences:**
1. Select Video 1 from dropdown
2. Click detection from Video 1
3. Verify Video 1 plays
4. Close dialog
5. Select Video 2 from dropdown
6. Click detection from Video 2
7. Verify Video 2 plays

### 9. Test Error Handling

**Scenario: Missing Video URL**

Try to trigger a detection with no video URL:
- Should show warning message
- Should display "Video Not Available" alert
- Should provide clear error message

**Expected Warning:**
```
⚠ Video Not Available
Unable to load video for this detection. The video file may not be accessible.
```

### 10. Performance Testing

**Check:**
- [ ] Dialog opens quickly (<500ms)
- [ ] Video loads within 3 seconds
- [ ] No lag when clicking multiple detections
- [ ] No memory leaks (check browser dev tools)
- [ ] Page remains responsive while video plays

---

## Browser Compatibility Testing

### Chrome/Edge (Chromium)
- [ ] Video popup works
- [ ] Auto-play works
- [ ] Timestamp seeking works
- [ ] Close button works

### Firefox
- [ ] Video popup works
- [ ] Auto-play works
- [ ] Timestamp seeking works
- [ ] Close button works

### Safari (Mac only)
- [ ] Video popup works
- [ ] Auto-play works (may require user interaction first)
- [ ] Timestamp seeking works
- [ ] Close button works

---

## Console Debugging

### Expected Console Logs

When clicking a detection, you should see:

```
🎬 Detection clicked: { id: "...", timestamp: 12.345, ... }
🎬 Opening video at URL: http://localhost:8000/uploads/video.mp4 timestamp: 12.345
```

### Check for Errors

Open browser DevTools (F12) and check Console tab for:
- ❌ Red error messages
- ⚠ Yellow warning messages
- Network errors (Failed to load video)

---

## Common Issues & Solutions

### Issue 1: Video Doesn't Load
**Symptoms:** Black screen, no playback
**Solutions:**
1. Check video URL in console log
2. Verify video file exists on server
3. Check network tab for 404 errors
4. Try opening video URL directly in browser

### Issue 2: Video Doesn't Seek to Timestamp
**Symptoms:** Video starts at beginning (0:00)
**Solutions:**
1. Check console for timestamp value
2. Verify `detection.timestamp` exists
3. Check video metadata loads (`loadedmetadata` event)
4. Try manually seeking with video controls

### Issue 3: Dialog Doesn't Open
**Symptoms:** Click does nothing
**Solutions:**
1. Check if `onClick` handler is attached
2. Verify `handleDetectionClick` function exists
3. Check console for JavaScript errors
4. Verify state variables are initialized

### Issue 4: Multiple Dialogs Open
**Symptoms:** Dialogs stack on top of each other
**Solutions:**
1. Check `videoDialogOpen` state management
2. Verify dialog closes properly
3. Restart application

### Issue 5: Auto-Play Blocked
**Symptoms:** Video loads but doesn't play
**Solutions:**
1. This is browser auto-play policy
2. Click play button manually
3. Check browser auto-play settings
4. Try with `muted` attribute (if applicable)

---

## Test Data Verification

### Required Data in Detection Event

Each detection should have:
```typescript
{
  id: string,
  timestamp: number,  // Required for seek
  real_latency_ms: number,  // For display
  voltage: number,  // For display
  passed: boolean,  // For display
  video_id?: string  // For video lookup
}
```

### Required Data in Available Videos

Each video in `availableVideos` should have:
```typescript
{
  id: string,
  filename: string,  // For URL construction
  url: string  // Direct video URL
}
```

---

## Advanced Testing

### Test Video Formats
- [ ] MP4 format
- [ ] WebM format (if supported)
- [ ] Different resolutions (720p, 1080p)
- [ ] Different frame rates (24fps, 30fps, 60fps)

### Test Edge Cases
- [ ] Video with no audio
- [ ] Very short video (<1 second)
- [ ] Very long video (>1 hour)
- [ ] Detection at timestamp 0.000s
- [ ] Detection at end of video
- [ ] Detection with very high latency (>1000ms)

### Test Accessibility
- [ ] Tab navigation works
- [ ] ESC key closes dialog
- [ ] Enter key opens video (if row focused)
- [ ] Screen reader announces dialog
- [ ] Focus trap inside dialog

---

## Regression Testing

After confirming video popup works, verify these existing features still work:

- [ ] Detection table displays correctly
- [ ] Ground truth comparison shows
- [ ] Timeline visualization renders
- [ ] Video sequence selector works
- [ ] Real-time updates work (if enabled)
- [ ] Export functionality works
- [ ] Page navigation works

---

## Performance Benchmarks

### Target Metrics
- Dialog open time: <500ms
- Video load time: <3 seconds
- Timestamp seek time: <1 second
- Dialog close time: <200ms
- Memory usage: <50MB increase

### How to Measure
1. Open Chrome DevTools
2. Go to Performance tab
3. Click "Record"
4. Click detection row
5. Wait for video to load
6. Close dialog
7. Stop recording
8. Review timeline for bottlenecks

---

## Reporting Issues

If you find bugs, report with:

1. **Steps to Reproduce**
2. **Expected Behavior**
3. **Actual Behavior**
4. **Console Logs**
5. **Screenshots/Video**
6. **Browser & Version**
7. **Operating System**

Example:
```
BUG: Video doesn't seek to timestamp

Steps:
1. Click detection at timestamp 12.345s
2. Dialog opens
3. Video plays

Expected: Video starts at 12.345s
Actual: Video starts at 0.000s

Console: No errors
Browser: Chrome 120
OS: Windows 11
```

---

## Success Criteria

### Feature is considered working if:
- [ ] ✅ Clicking detection row opens dialog
- [ ] ✅ Video loads and plays automatically
- [ ] ✅ Video seeks to correct timestamp
- [ ] ✅ Dialog shows correct detection info
- [ ] ✅ Close button works
- [ ] ✅ No console errors
- [ ] ✅ Works in Chrome/Firefox/Safari
- [ ] ✅ Works for single and multi-video tests
- [ ] ✅ Error handling works for missing videos
- [ ] ✅ Performance is acceptable (<3s load time)

---

## Next Steps After Testing

1. ✅ Mark issues as resolved
2. Document any workarounds
3. Create user documentation if needed
4. Consider enhancements (see below)

## Potential Enhancements

Based on testing feedback, consider:

1. **Playback Speed Control** - Add 0.5x, 1x, 2x speed buttons
2. **Frame-by-Frame** - Add frame step buttons
3. **Video Preloading** - Preload video on row hover
4. **Keyboard Shortcuts** - Space = play/pause, arrows = seek
5. **Detection Markers** - Visual overlay at detection point
6. **Multi-Detection View** - Show all detections for current video
7. **Export Clip** - Save short clip around detection
8. **Picture-in-Picture** - Continue watching while reviewing other data

---

Good luck with testing! 🚀
