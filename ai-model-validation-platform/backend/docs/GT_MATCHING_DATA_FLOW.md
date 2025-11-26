# Ground Truth Matching - Data Flow & Integration Points

## Visual Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                    GROUND TRUTH MATCHING SYSTEM                        │
│                         (Hungarian Algorithm)                          │
└────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA RETRIEVAL                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Database Query (Line 268-299)                                         │
│  ┌──────────────────────┐         ┌──────────────────────┐            │
│  │  detection_events    │         │  ground_truth_objects│            │
│  │  WHERE usable = TRUE │         │  WHERE validated=TRUE│            │
│  └──────────┬───────────┘         └──────────┬───────────┘            │
│             │                                 │                         │
│             │   Query Results:                │                         │
│             │   • 100 detections              │   • 95 GTs              │
│             │   • video_relative_timestamp    │   • timestamp           │
│             │   • video_id                    │   • video_id            │
│             │   • actual_latency_ms           │                         │
│             └─────────────┬───────────────────┘                         │
│                           │                                             │
└───────────────────────────┼─────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: TIMESTAMP EXTRACTION                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  extract_detection_video_time() (Line 108-146)                         │
│  ┌──────────────────────────────────────┐                              │
│  │ Priority Order:                      │                              │
│  │ 1. video_relative_timestamp ✓        │                              │
│  │ 2. video_frame_number / fps          │                              │
│  │ 3. timestamp - video_start_time      │                              │
│  │ 4. timestamp - session_start_time    │                              │
│  │ 5. timestamp (raw)                   │                              │
│  └──────────────┬───────────────────────┘                              │
│                 │                                                       │
│                 │   Normalized Timestamps:                             │
│                 │   det_times = [1.000, 1.050, 2.100, ...]  (seconds)  │
│                 │   gt_times  = [1.000, 2.000, 3.000, ...]  (seconds)  │
│                 │                                                       │
│                 └────────────────┬──────────────────────────────────────┤
│                                  │                                      │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: HUNGARIAN ALGORITHM (optimal_matching_service.py)             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Step 1: Build Cost Matrix (Line 248-259)                              │
│  ┌────────────────────────────────────────────────┐                    │
│  │ cost_matrix[i,j] = |det_time[j] - gt_time[i]| │                    │
│  │                                                │                    │
│  │        Det0   Det1   Det2   Det3              │                    │
│  │  GT0  0.000  0.050  1.100  2.000              │                    │
│  │  GT1  1.000  0.950  0.100  1.000              │                    │
│  │  GT2  2.000  1.950  0.900  ∞                  │                    │
│  │                                                │                    │
│  │  If time_diff > tolerance (100ms):            │                    │
│  │    cost_matrix[i,j] = ∞  (invalid match)      │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  Step 2: Optimal Assignment (Line 277)                                 │
│  ┌────────────────────────────────────────────────┐                    │
│  │ from scipy.optimize import linear_sum_assignment│                    │
│  │                                                │                    │
│  │ gt_indices, det_indices =                      │                    │
│  │   linear_sum_assignment(cost_matrix)           │                    │
│  │                                                │                    │
│  │ Result: [(GT0→Det0), (GT1→Det2), (GT2→unmatched)]                  │
│  │         Optimal global assignment!             │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  Step 3: Filter & Classify (Line 295-311)                              │
│  ┌────────────────────────────────────────────────┐                    │
│  │ True Positives (cost < ∞):                     │                    │
│  │   • (GT0, Det0, latency=0ms)                   │                    │
│  │   • (GT1, Det2, latency=100ms)                 │                    │
│  │                                                │                    │
│  │ False Positives (unmatched detections):        │                    │
│  │   • Det1 (no valid GT within tolerance)        │                    │
│  │   • Det3                                       │                    │
│  │                                                │                    │
│  │ False Negatives (unmatched GTs):               │                    │
│  │   • GT2 (no detection found)                   │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  Output: OptimalMatchResult                                            │
│  ┌────────────────────────────────────────────────┐                    │
│  │ true_positives: [(0,0,0.0), (1,2,100.0)]       │                    │
│  │ false_positives: [1, 3]                        │                    │
│  │ false_negatives: [2]                           │                    │
│  │ total_cost: 0.100 (seconds)                    │                    │
│  │ algorithm: 'hungarian'                         │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: VALIDATION (match_validator.py)                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  validate_matches() - Line 1062-1087                                   │
│  ┌────────────────────────────────────────────────┐                    │
│  │ Check 1: No duplicate detections ✓             │                    │
│  │   unique_detections = {Det0, Det2}             │                    │
│  │   duplicates = {} (empty - PASS)               │                    │
│  │                                                │                    │
│  │ Check 2: No duplicate ground truths ✓          │                    │
│  │   unique_gts = {GT0, GT1}                      │                    │
│  │   duplicates = {} (empty - PASS)               │                    │
│  │                                                │                    │
│  │ Check 3: One-to-one mapping ✓                  │                    │
│  │   Enforced by Hungarian algorithm              │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  validate_video_boundary_protection() - Line 885-920                   │
│  ┌────────────────────────────────────────────────┐                    │
│  │ For multi-video sequences:                     │                    │
│  │   if det.video_id != gt.video_id:              │                    │
│  │     reject_match()                             │                    │
│  │     reclassify_as_FN_and_FP()                  │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: DATABASE PERSISTENCE (Line 1120-1249)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  _populate_detection_comparisons()                                     │
│  ┌────────────────────────────────────────────────┐                    │
│  │ detection_comparisons table:                   │                    │
│  │                                                │                    │
│  │ INSERT INTO detection_comparisons:             │                    │
│  │   • (GT0, Det0, 'TP', latency=0ms)             │                    │
│  │   • (GT1, Det2, 'TP', latency=100ms)           │                    │
│  │   • (GT2, NULL, 'FN')                          │                    │
│  │   • (NULL, Det1, 'FP')                         │                    │
│  │   • (NULL, Det3, 'FP')                         │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  Update detection_events table (Line 1177-1233):                       │
│  ┌────────────────────────────────────────────────┐                    │
│  │ UPDATE detection_events                        │                    │
│  │ SET validation_result = 'TP',                  │                    │
│  │     actual_latency_ms = 0.0,                   │                    │
│  │     ground_truth_match_id = 'gt-uuid'          │                    │
│  │ WHERE id = 'det-uuid'                          │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 6: METRICS CALCULATION (Line 1251-1418)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  SessionMetrics:                                                       │
│  ┌────────────────────────────────────────────────┐                    │
│  │ true_positives: 2                              │                    │
│  │ false_positives: 2                             │                    │
│  │ false_negatives: 1                             │                    │
│  │ precision: 2/(2+2) = 0.50                      │                    │
│  │ recall: 2/(2+1) = 0.67                         │                    │
│  │ f1_score: 2*(0.50*0.67)/(0.50+0.67) = 0.57    │                    │
│  │ mean_latency_ms: (0 + 100)/2 = 50ms            │                    │
│  │ std_latency_ms: 50ms                           │                    │
│  │ max_latency_ms: 100ms                          │                    │
│  │ min_latency_ms: 0ms                            │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
 OPTION C INTEGRATION POINTS
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ HOOK POINT 1: TEMPORAL EXPANSION (Before Phase 3, Line 810)            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  CURRENT CODE:                                                         │
│  ┌────────────────────────────────────────────────┐                    │
│  │ for detection in detection_events:             │                    │
│  │     det_time = extract_detection_video_time()  │                    │
│  │     det_times.append(det_time)                 │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  OPTION C MODIFICATION:                                                │
│  ┌────────────────────────────────────────────────┐                    │
│  │ expanded_detections = []                       │                    │
│  │ expanded_det_times = []                        │                    │
│  │                                                │                    │
│  │ for detection in detection_events:             │                    │
│  │     base_time = extract_detection_video_time() │                    │
│  │                                                │                    │
│  │     # Create 12 virtual detections:            │                    │
│  │     for i in range(-6, 6):  # ±6 = 12 total    │                    │
│  │         virtual_time = base_time + (i * 0.040) │                    │
│  │         virtual_det = VirtualDetection(        │                    │
│  │             base_id=detection.id,              │                    │
│  │             virtual_index=i,                   │                    │
│  │             timestamp=virtual_time             │                    │
│  │         )                                      │                    │
│  │         expanded_detections.append(virtual_det)│                    │
│  │         expanded_det_times.append(virtual_time)│                    │
│  │                                                │                    │
│  │ # Pass to Hungarian (no changes needed):       │                    │
│  │ result = optimal_detection_matching(           │                    │
│  │     gt_times,                                  │                    │
│  │     expanded_det_times,  # 12x larger          │                    │
│  │     tolerance_seconds                          │                    │
│  │ )                                              │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  EXAMPLE:                                                              │
│  ┌────────────────────────────────────────────────┐                    │
│  │ Detection 1 (base_time = 2.100s):              │                    │
│  │   Virtual -6: 2.100 + (-6*0.040) = 1.860s      │                    │
│  │   Virtual -5: 1.900s                           │                    │
│  │   Virtual -4: 1.940s                           │                    │
│  │   Virtual -3: 1.980s                           │                    │
│  │   Virtual -2: 2.020s ← MATCHES GT at 2.000s! ✓│                    │
│  │   Virtual -1: 2.060s                           │                    │
│  │   Virtual  0: 2.100s (original)                │                    │
│  │   Virtual  1: 2.140s                           │                    │
│  │   Virtual  2: 2.180s                           │                    │
│  │   Virtual  3: 2.220s                           │                    │
│  │   Virtual  4: 2.260s                           │                    │
│  │   Virtual  5: 2.300s                           │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ HOOK POINT 2: MATCH COLLAPSE (After Phase 3, Before Phase 4)           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  collapse_virtual_matches()                                            │
│  ┌────────────────────────────────────────────────┐                    │
│  │ # Group virtual matches by base detection:     │                    │
│  │ virtual_matches = {                            │                    │
│  │   'det-1': [                                   │                    │
│  │     (GT1, Virtual-2, 20ms),  # Best match      │                    │
│  │     (GT1, Virtual-1, 60ms),                    │                    │
│  │   ],                                           │                    │
│  │   'det-2': [                                   │                    │
│  │     (GT2, Virtual0, 10ms),  # Best match       │                    │
│  │   ]                                            │                    │
│  │ }                                              │                    │
│  │                                                │                    │
│  │ # Select best match per base detection:        │                    │
│  │ collapsed_matches = []                         │                    │
│  │ for base_id, matches in virtual_matches.items():                    │
│  │     best = min(matches, key=lambda m: m.latency)│                    │
│  │     collapsed_matches.append(                  │                    │
│  │         MatchResult(                           │                    │
│  │             detection_event_id=base_id,        │                    │
│  │             ground_truth_id=best.gt_id,        │                    │
│  │             latency_ms=best.latency            │                    │
│  │         )                                      │                    │
│  │     )                                          │                    │
│  └────────────────────────────────────────────────┘                    │
│                                                                         │
│  RESULT: 1:1 mapping preserved (1 real detection → 1 GT)               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════
 PERFORMANCE IMPACT ANALYSIS
═══════════════════════════════════════════════════════════════════════════

┌────────────────────────────┬──────────────┬─────────────┬───────────────┐
│ Test Size                  │ Current Time │ Option C    │ Algorithm     │
├────────────────────────────┼──────────────┼─────────────┼───────────────┤
│ 100 detections × 95 GTs    │ ~10ms        │ ~500ms      │ Hungarian     │
│ 500 detections × 480 GTs   │ ~200ms       │ ~15s        │ GREEDY        │
│ 1000 detections × 950 GTs  │ ~2s          │ TIMEOUT     │ GREEDY        │
└────────────────────────────┴──────────────┴─────────────┴───────────────┘

RECOMMENDATION: Reduce Hungarian threshold from 1000 to 100 for Option C.

═══════════════════════════════════════════════════════════════════════════
 CRITICAL PRESERVATION POINTS
═══════════════════════════════════════════════════════════════════════════

✅ NO CHANGES NEEDED:
  • Hungarian algorithm (optimal_matching_service.py)
  • Cost matrix construction logic
  • Match validation functions
  • Database schema (DetectionEvent, GroundTruthObject)
  • API response formats (SessionMetrics)

⚠️ CHANGES REQUIRED:
  • Detection list preparation (expansion before matching)
  • Match result collapse (after matching)
  • Performance threshold tuning

═══════════════════════════════════════════════════════════════════════════
