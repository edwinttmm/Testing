#!/usr/bin/env python3
"""
Quick script to check for duplicate detection entries with different latencies
"""
import sys
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')

from database import SessionLocal
from models import DetectionEvent
from sqlalchemy import func

db = SessionLocal()

session_id = '9048a1b0-10a7-40b7-b1fc-1c95064cbb5f'

# Check for duplicates by frame number
print("=" * 80)
print(f"Checking for duplicate detections in session {session_id}")
print("=" * 80)

# Query detections grouped by frame
frames_with_duplicates = db.query(
    DetectionEvent.frame_number,
    func.count(DetectionEvent.id).label('count')
).filter(
    DetectionEvent.test_session_id == session_id
).group_by(
    DetectionEvent.frame_number
).having(
    func.count(DetectionEvent.id) > 1
).all()

print(f"\nFrames with duplicate entries: {len(frames_with_duplicates)}")
for frame_num, count in frames_with_duplicates:
    print(f"  Frame {frame_num}: {count} entries")

# Show ALL detections sorted by actual_latency_ms
print("\n" + "=" * 80)
print("ALL DETECTIONS SORTED BY LATENCY")
print("=" * 80)

all_detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id
).order_by(DetectionEvent.actual_latency_ms, DetectionEvent.timestamp).all()

print(f"\nFound {len(all_detections)} total detections")
print("\nGrouping by actual_latency_ms:")

from collections import defaultdict
latency_groups = defaultdict(list)
for det in all_detections:
    latency_groups[det.actual_latency_ms].append(det)

for latency_ms in sorted(latency_groups.keys()):
    dets = latency_groups[latency_ms]
    print(f"\n  Latency {latency_ms}ms: {len(dets)} detections")
    if latency_ms in [10000.0, 12.0, 13.3, 17.9, 19.0]:  # Values from UI
        for det in dets[:3]:  # Show first 3
            print(f"    - ID: {det.id[:12]}... voltage: {det.voltage_level}, result: {det.validation_result}")
            print(f"      video_relative_timestamp: {det.video_relative_timestamp}")
            print(f"      timestamp: {det.timestamp}")

# Check detection_comparison table
print("\n" + "=" * 80)
print("CHECKING DETECTION COMPARISON TABLE")
print("=" * 80)

from models import DetectionComparison

# Get all comparisons for this session
comparisons = db.query(DetectionComparison).join(
    DetectionEvent,
    DetectionComparison.detection_event_id == DetectionEvent.id
).filter(
    DetectionEvent.test_session_id == session_id
).all()

print(f"\nFound {len(comparisons)} detection_comparison entries")

# Group by detection_event_id to find duplicates
from collections import defaultdict
comp_by_detection = defaultdict(list)
for comp in comparisons:
    comp_by_detection[comp.detection_event_id].append(comp)

duplicates = {k: v for k, v in comp_by_detection.items() if len(v) > 1}
print(f"\nDetections with multiple comparison entries: {len(duplicates)}")

for det_id, comps in list(duplicates.items())[:5]:  # Show first 5
    print(f"\n  Detection {det_id[:12]}... has {len(comps)} comparison entries:")
    for comp in comps:
        print(f"    - match_type: {comp.match_type}, latency: {comp.actual_latency_ms}ms")

# Check for 10000ms FP marker specifically
fp_markers = [comp for comp in comparisons if comp.actual_latency_ms == 10000.0]
print(f"\n10000ms (FP_LATENCY_MARKER) entries: {len(fp_markers)}")

db.close()
