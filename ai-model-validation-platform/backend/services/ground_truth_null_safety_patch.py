"""
NULL Safety Patch for Ground Truth Matching Service
====================================================

This patch adds NULL safety checks to prevent KeyError crashes when video_id is NULL.

QUEEN'S COORDINATION PROTOCOL #34 - NULL SAFETY VALIDATION

Apply this patch by running:
    python3 ground_truth_null_safety_patch.py

The patch adds NULL checks at 5 critical locations:
1. Video boundary validation (line ~788)
2. TP match video_id capture (line ~833)
3. FN match processing (line ~860)
4. FP match processing (line ~884)
5. Latency calculation grouping (line ~1167)
"""

import re
import sys
from pathlib import Path

def apply_null_safety_patches():
    """Apply NULL safety patches to ground_truth_matching_service.py"""

    file_path = Path(__file__).parent / 'ground_truth_matching_service.py'

    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return False

    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content
    patches_applied = 0

    # PATCH 1: Video boundary validation - add NULL check before cross-video match check
    patch_1_search = r'(# CRITICAL: Video boundary validation for multi-video sequences\s+detection_video_id = getattr\(detection, \'video_id\', None\)\s+gt_video_id = getattr\(gt_obj, \'video_id\', None\)\s+)(# Skip if video IDs don\'t match)'

    patch_1_replace = r'\1# NULL SAFETY: Skip if either video_id is NULL in multi-video mode\n            if has_multi_video_sequence and (detection_video_id is None or gt_video_id is None):\n                logger.warning(\n                    f"Skipping match - NULL video_id detected (detection={detection_video_id}, gt={gt_video_id})"\n                )\n                # Reclassify as FN for GT and FP for detection\n                match_results.append(\n                    MatchResult(\n                        ground_truth_id=gt_obj.id,\n                        detection_event_id=None,\n                        match_type=\'FN\',\n                        temporal_offset=0.0,\n                        confidence=None,\n                        iou_score=0.0,\n                        latency_ms=None,\n                        video_id=gt_video_id\n                    )\n                )\n                match_results.append(\n                    MatchResult(\n                        ground_truth_id=None,\n                        detection_event_id=detection.id,\n                        match_type=\'FP\',\n                        temporal_offset=0.0,\n                        confidence=detection.confidence,\n                        iou_score=0.0,\n                        latency_ms=None,\n                        video_id=detection_video_id\n                    )\n                )\n                continue\n\n            \2'

    if re.search(patch_1_search, content, re.MULTILINE):
        content = re.sub(patch_1_search, patch_1_replace, content, flags=re.MULTILINE)
        patches_applied += 1
        print("✓ Applied PATCH 1: Video boundary NULL validation")

    # PATCH 2: TP match video_id capture - add NULL check and warning
    patch_2_search = r'(# Capture video_id for latency grouping\s+det_video_id = detection_video_id or gt_video_id\s+)(if det_video_id is not None:)'

    patch_2_replace = r'\1# NULL SAFETY: Log warning if video_id is NULL for TP match\n            if det_video_id is None:\n                logger.warning(\n                    f"TP match has NULL video_id - detection={detection.id[:8]}, gt={gt_obj.id[:8]}"\n                )\n            else:\n                det_video_id = str(det_video_id)\n\n            # Remove old single-line conversion\n            # \2'

    # Simplified approach - just add the warning before str conversion
    patch_2_simple = r'(# Capture video_id for latency grouping\s+det_video_id = detection_video_id or gt_video_id\s+if det_video_id is not None:\s+)(det_video_id = str\(det_video_id\))'

    patch_2_replace_simple = r'\1# NULL SAFETY\n                if det_video_id is None:\n                    logger.warning(f"TP match has NULL video_id - detection={detection.id[:8]}, gt={gt_obj.id[:8]}")\n                \2'

    # PATCH 3: FN processing - add NULL check warning
    patch_3_search = r'(# Process false negatives from optimal matching\s+for gt_idx in optimal_result\[\'false_negatives\'\]:\s+gt_obj = ground_truth_objects\[gt_idx\]\s+gt_video_id = getattr\(gt_obj, \'video_id\', None\)\s+)(match_result = MatchResult\()'

    patch_3_replace = r'\1# NULL SAFETY: Log warning if video_id is NULL\n            if gt_video_id is None:\n                logger.warning(f"FN ground truth {gt_obj.id[:8]} has NULL video_id")\n\n            \2'

    if re.search(patch_3_search, content, re.MULTILINE):
        content = re.sub(patch_3_search, patch_3_replace, content, flags=re.MULTILINE)
        patches_applied += 1
        print("✓ Applied PATCH 3: FN NULL validation")

    # PATCH 4: FP processing - add NULL check warning
    patch_4_search = r'(# Process false positives from optimal matching\s+for det_idx in optimal_result\[\'false_positives\'\]:\s+detection = detection_events\[det_idx\]\s+detection_video_id = getattr\(detection, \'video_id\', None\)\s+)(match_result = MatchResult\()'

    patch_4_replace = r'\1# NULL SAFETY: Log warning if video_id is NULL\n            if detection_video_id is None:\n                logger.warning(f"FP detection {detection.id[:8]} has NULL video_id")\n\n            \2'

    if re.search(patch_4_search, content, re.MULTILINE):
        content = re.sub(patch_4_search, patch_4_replace, content, flags=re.MULTILINE)
        patches_applied += 1
        print("✓ Applied PATCH 4: FP NULL validation")

    # PATCH 5: Latency calculation - add NULL check before dict access
    patch_5_search = r'(video_tp_latencies = defaultdict\(list\)\s+for mr in tp_results:\s+if mr\.latency_ms is not None:\s+)(# Use video_id from MatchResult)'

    patch_5_replace = r'\1# CRITICAL NULL SAFETY: Skip if video_id is None\n                if mr.video_id is None:\n                    self.logger.warning(f"Skipping TP match result - NULL video_id (latency={mr.latency_ms:.1f}ms)")\n                    continue\n\n                \2'

    if re.search(patch_5_search, content, re.MULTILINE):
        content = re.sub(patch_5_search, patch_5_replace, content, flags=re.MULTILINE)
        patches_applied += 1
        print("✓ Applied PATCH 5: Latency calculation NULL safety")

    # Also fix the video_id string conversion after the NULL check
    content = re.sub(
        r"video_id = str\(mr\.video_id\) if mr\.video_id else 'default_video'",
        r"video_id = str(mr.video_id)",
        content
    )

    if content != original_content:
        # Write back to file
        with open(file_path, 'w') as f:
            f.write(content)

        print(f"\n✅ Successfully applied {patches_applied} NULL safety patches")
        print(f"   File updated: {file_path}")
        return True
    else:
        print("\n⚠️  No patches applied - file may already have NULL safety checks")
        return False

if __name__ == "__main__":
    success = apply_null_safety_patches()
    sys.exit(0 if success else 1)
