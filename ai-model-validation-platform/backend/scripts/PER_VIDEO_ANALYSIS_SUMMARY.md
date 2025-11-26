# PER-VIDEO DETECTION BREAKDOWN ANALYSIS

**Session ID:** fa204ef2-9d8b-4480-9692-86e338c1218a

## EXECUTIVE SUMMARY

This session tested 2 videos in sequence. **BOTH videos failed**, but Video 2 performed slightly better than Video 1.

## SESSION OVERVIEW

- **Status:** Completed
- **Result:** FAIL (0/2 videos passed)
- **Overall Detection Rate:** 33.9%
- **Total True Positives:** 87
- **Total False Negatives:** 170
- **Total False Positives:** 9

## PER-VIDEO BREAKDOWN

### VIDEO 1: child_test_video_20251031_144012.mp4

| Metric | Value |
|--------|-------|
| Total GT Events | 131 |
| Detections Captured (TP) | 36 |
| **Detection Rate** | **27.5%** |
| Frame Range | 1 - 121 |
| Missing Frames | 87 / 121 (71.9%) |
| Average Detection Gap | 3.3 frames |

**Missing Frame Pattern:**
- 87 out of 121 frames with GT events have NO detections
- Detections occur sporadically with ~3.3 frame gaps on average
- Sample detected frames: [6, 8, 10, 11, 15, 24, 58, 59, 60, 64...]

### VIDEO 2: Child_20251031_143523.mp4

| Metric | Value |
|--------|-------|
| Total GT Events | 126 |
| Detections Captured (TP) | 51 |
| **Detection Rate** | **40.5%** |
| Frame Range | 1 - 121 |
| Missing Frames | 121 / 121 (100%) |
| Average Detection Gap | 3.2 frames |

**Missing Frame Pattern:**
- **ALL 121 frames** with GT events have NO detections at their exact frame number
- Detections occur at DIFFERENT frame numbers (129, 131, 135, 137...)
- This suggests a frame numbering mismatch or offset between GT and detections

## COMPARISON

### Detection Rate Comparison
- **Video 1:** 27.5%
- **Video 2:** 40.5%
- **Difference:** 13.0 percentage points

### Are Both Videos Equally Affected?
**NO** - Video 2 performs 13% better than Video 1, though both are below 50% detection rate.

### Pattern Consistency
- **Video 1:** 71.9% frames missing
- **Video 2:** 100% frames missing (but detections exist at different frame numbers)

## KEY FINDINGS

### 1. Frame Numbering Issue (Critical)
**Video 2 shows a severe frame numbering mismatch:**
- Ground truth uses frames 1-121
- Detections use frames 129-242 (approx)
- This suggests video playback started at a different frame offset

### 2. Frame Skipping Pattern
**Both videos show sparse detection patterns:**
- Average 3.2-3.3 frame gap between detections
- Ground truth may be annotated at every frame (or near-continuous)
- Model appears to output detections every 3-4 frames on average

### 3. Detection Rate Difference
**Video 2 outperforms Video 1 by 13%:**
- Possible reasons:
  - Better video characteristics (lighting, contrast, motion)
  - Different pedestrian behavior or positions
  - Less occlusion in Video 2

## HYPOTHESIS

### Why Both Videos Show Low Detection Rates (<50%)

1. **Frame Skipping in Model Inference**
   - Model processes every 3-4 frames instead of every frame
   - Ground truth annotated at higher frequency than model output

2. **Frame Numbering Offset** (especially Video 2)
   - Detections use different frame numbering than ground truth
   - Video playback may have started at wrong frame
   - Timestamp-based matching failed to account for frame offset

3. **Temporal Filtering Too Aggressive**
   - Model may be filtering out valid detections as duplicates
   - Inter-frame suppression removing consecutive detections

4. **Ground Truth Granularity Mismatch**
   - GT annotated at fine-grained level (every frame)
   - Model designed to output detections at coarser intervals

5. **Confidence Threshold Issues**
   - Some valid detections filtered out by confidence threshold
   - Model less confident in certain frames

## RECOMMENDATIONS

### Immediate Actions

1. **Fix Frame Numbering**
   - Investigate why Video 2 detections start at frame 129 instead of frame 1
   - Verify video playback start point synchronization
   - Check if ground truth and detection use same frame numbering convention

2. **Analyze Frame Processing Rate**
   - Confirm model inference rate (every frame vs every Nth frame)
   - If model skips frames by design, adjust ground truth expectations
   - Consider interpolating model output to match GT granularity

3. **Review Temporal Filtering**
   - Check if duplicate suppression is too aggressive
   - Consider allowing detections in consecutive frames
   - Adjust IoU threshold for temporal filtering

### Long-term Improvements

1. **Ground Truth Alignment**
   - Ensure GT annotation frequency matches model output design
   - If model outputs every 3 frames, don't expect 100% frame coverage

2. **Frame Synchronization**
   - Implement robust frame synchronization between video playback and model
   - Use timestamps AND frame numbers for validation
   - Add frame offset detection and correction

3. **Detection Rate Expectations**
   - Set realistic detection rate targets based on model design
   - If model processes every 4 frames, max detection rate is 25% of per-frame GT

## DETAILED FRAME ANALYSIS

### Video 1 - Missing Frames (Sample)
**First 15 missing:** [1, 2, 3, 4, 5, 7, 9, 12, 13, 14, 16, 17, 18, 19, 20]
**Last 15 missing:** [94, 97, 101, 102, 103, 105, 106, 107, 110, 113, 115, 116, 118, 120, 121]

### Video 2 - Missing Frames
**All frames 1-121 missing** (detections occur at frames 129+)

## CONCLUSION

Both videos show low detection rates due to a combination of:
1. **Frame numbering mismatch** (especially Video 2)
2. **Model frame skipping** (3-4 frame intervals)
3. **Ground truth at finer granularity** than model output

**The core issue is NOT that the model is failing to detect pedestrians, but rather:**
- **Frame alignment issues** between GT and detections
- **Expectation mismatch** between GT annotation rate and model output rate

### Next Steps
1. Fix frame numbering offset in Video 2
2. Confirm if model is designed to process every frame or every Nth frame
3. Adjust validation criteria to match model design specifications
4. Re-evaluate pass/fail thresholds based on model architecture
