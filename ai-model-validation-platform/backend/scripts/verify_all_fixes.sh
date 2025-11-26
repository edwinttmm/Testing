#!/bin/bash
# Comprehensive Verification Script for All Bug Fixes
#
# This script verifies the following fixes:
# 1. GT Aggregation (41→257) - FIXED by previous agent
# 2. Duplicate Detection Sources - Being fixed by coder agent
# 3. Video 2 Timestamp Matching - Being fixed by coder agent
#
# Run from: /home/rigade/Testing/ai-model-validation-platform/backend

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Session ID for testing
TEST_SESSION_ID="e8e108b0-cb20-4cba-a2db-fc29f21efd16"
VIDEO2_ID="550e3cf8-2755-42df-8c3c-041300735f93"

echo "================================================================================"
echo "COMPREHENSIVE VERIFICATION SCRIPT FOR ALL FIXES"
echo "================================================================================"
echo "Test Session ID: $TEST_SESSION_ID"
echo "Video 2 ID: $VIDEO2_ID"
echo ""

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo -e "${RED}ERROR: Virtual environment not found${NC}"
    exit 1
fi

echo "================================================================================"
echo "1. DETECTION SOURCE VERIFICATION"
echo "================================================================================"
echo ""
echo "Expected: Only ONE detection source active (either 'labjack' OR 'dedicated_labjack_monitor')"
echo ""

python3 << 'EOF_SOURCE'
from sqlalchemy import create_engine, text
from config_settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    # Get all sources for this session
    sources = conn.execute(text("""
        SELECT source, COUNT(*) as count,
               MIN(timestamp) as first_ts,
               MAX(timestamp) as last_ts
        FROM detection_events
        WHERE test_session_id = :session_id
        GROUP BY source
        ORDER BY count DESC
    """), {"session_id": "e8e108b0-cb20-4cba-a2db-fc29f21efd16"}).fetchall()

    print("Detection Sources in Database:")
    print("-" * 80)

    total_detections = 0
    for source, count, first_ts, last_ts in sources:
        total_detections += count
        source_name = source or "(NULL)"
        print(f"  Source: {source_name}")
        print(f"  Count: {count}")
        print(f"  First: {first_ts:.3f}")
        print(f"  Last:  {last_ts:.3f}")
        print("")

    print(f"Total Detections: {total_detections}")
    print("")

    # PASS/FAIL criteria
    if len(sources) == 1:
        print("✅ PASS: Only ONE detection source is active")
        exit(0)
    elif len(sources) == 2 and all(s[1] == sources[0][1] for s in sources):
        print("❌ FAIL: TWO sources with EQUAL counts detected")
        print("   This indicates 100% duplication of detections")
        print(f"   Both sources wrote {sources[0][1]} detections")
        exit(1)
    elif len(sources) > 1:
        print("⚠️  WARNING: Multiple detection sources found")
        print("   Expected: 1 source")
        print(f"   Actual: {len(sources)} sources")
        exit(2)
    else:
        print("❌ FAIL: No detection sources found")
        exit(3)
EOF_SOURCE

SOURCE_CHECK=$?

echo ""
echo "================================================================================"
echo "2. GROUND TRUTH AGGREGATION VERIFICATION"
echo "================================================================================"
echo ""
echo "Expected: 257 total ground truth objects (across all videos in session)"
echo "  - Video 1: 131 GT objects"
echo "  - Video 2: 126 GT objects"
echo ""

python3 << 'EOF_GT'
from sqlalchemy import create_engine, text
from config_settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    # Get session's video(s)
    session = conn.execute(text("""
        SELECT id, video_id
        FROM test_sessions
        WHERE id = :session_id
    """), {"session_id": "e8e108b0-cb20-4cba-a2db-fc29f21efd16"}).fetchone()

    if not session:
        print("❌ FAIL: Session not found")
        exit(1)

    print(f"Session ID: {session[0]}")
    print(f"Primary Video ID: {session[1]}")
    print("")

    # Get all videos associated with this session
    videos = conn.execute(text("""
        SELECT DISTINCT svr.video_id
        FROM sequence_video_results svr
        JOIN video_test_sequences vts ON svr.video_sequence_id = vts.id
        WHERE vts.test_session_id = :session_id
        ORDER BY svr.video_id
    """), {"session_id": "e8e108b0-cb20-4cba-a2db-fc29f21efd16"}).fetchall()

    print(f"Videos in test session: {len(videos)}")

    # Count GT per video
    total_gt = 0
    for (video_id,) in videos:
        gt_count = conn.execute(text("""
            SELECT COUNT(*) FROM ground_truth_objects
            WHERE video_id = :video_id
        """), {"video_id": video_id}).scalar()

        print(f"  Video {video_id}: {gt_count} GT objects")
        total_gt += gt_count

    print("")
    print(f"Total GT Objects: {total_gt}")
    print("")

    # Check if session metrics reflect correct GT count
    session_metrics = conn.execute(text("""
        SELECT accuracy_f1_score, accuracy_precision, accuracy_recall
        FROM test_sessions
        WHERE id = :session_id
    """), {"session_id": "e8e108b0-cb20-4cba-a2db-fc29f21efd16"}).fetchone()

    print("Stored Session Metrics:")
    print(f"  F1 Score: {session_metrics[0]:.4f}")
    print(f"  Precision: {session_metrics[1]:.4f}")
    print(f"  Recall: {session_metrics[2]:.4f}")
    print("")

    # PASS/FAIL criteria
    if total_gt == 257:
        print("✅ PASS: GT count is 257 (correctly aggregated across all videos)")
        exit(0)
    elif total_gt == 131:
        print("❌ FAIL: GT count is 131 (only counting one video)")
        print("   BUG: Aggregation function not counting all videos")
        exit(1)
    else:
        print(f"⚠️  WARNING: Unexpected GT count: {total_gt}")
        print("   Expected: 257")
        exit(2)
EOF_GT

GT_CHECK=$?

echo ""
echo "================================================================================"
echo "3. VIDEO 2 TIMESTAMP MATCHING VERIFICATION"
echo "================================================================================"
echo ""
echo "Expected: Improved matching coverage for Video 2 (126 GT objects)"
echo "Target: At least 20% coverage (25+ GT objects matched)"
echo ""

python3 << 'EOF_VIDEO2'
from sqlalchemy import create_engine, text
from config_settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    video2_id = "550e3cf8-2755-42df-8c3c-041300735f93"

    # Get Video 2 GT count
    gt_count = conn.execute(text("""
        SELECT COUNT(*) FROM ground_truth_objects
        WHERE video_id = :video_id
    """), {"video_id": video2_id}).scalar()

    print(f"Video 2 GT Objects: {gt_count}")

    # Get Video 2 matched count
    matched_count = conn.execute(text("""
        SELECT COUNT(DISTINCT gt.id) as matched_gt
        FROM detection_comparisons dc
        JOIN ground_truth_objects gt ON dc.ground_truth_id = gt.id
        WHERE gt.video_id = :video_id
        AND dc.match_type = 'TP'
    """), {"video_id": video2_id}).scalar()

    print(f"Video 2 GT Matched: {matched_count}")

    coverage = (matched_count / gt_count * 100) if gt_count > 0 else 0
    print(f"Video 2 Coverage: {coverage:.2f}%")
    print("")

    # Get sample of matched timestamps
    sample_matches = conn.execute(text("""
        SELECT gt.timestamp as gt_ts,
               de.timestamp as det_ts,
               ABS(gt.timestamp - de.timestamp) as offset_ms
        FROM detection_comparisons dc
        JOIN ground_truth_objects gt ON dc.ground_truth_id = gt.id
        JOIN detection_events de ON dc.detection_event_id = de.id
        WHERE gt.video_id = :video_id
        AND dc.match_type = 'TP'
        ORDER BY offset_ms
        LIMIT 5
    """), {"video_id": video2_id}).fetchall()

    if sample_matches:
        print("Sample Matched Timestamps (best 5):")
        print("-" * 80)
        for gt_ts, det_ts, offset in sample_matches:
            print(f"  GT: {gt_ts:.3f}s → Detection: {det_ts:.3f}s (offset: {offset:.3f}ms)")
        print("")

    # PASS/FAIL criteria
    if coverage >= 20:
        print("✅ PASS: Video 2 coverage >= 20%")
        exit(0)
    elif coverage > 5:
        print("⚠️  PARTIAL: Coverage improved but still below 20% target")
        print(f"   Current: {coverage:.2f}%")
        print(f"   Target: 20%")
        exit(1)
    elif coverage > 1:
        print("❌ FAIL: Coverage slightly improved but still inadequate")
        print(f"   Current: {coverage:.2f}%")
        print(f"   Previous: ~0.8%")
        exit(2)
    else:
        print("❌ FAIL: No improvement in Video 2 matching")
        exit(3)
EOF_VIDEO2

VIDEO2_CHECK=$?

echo ""
echo "================================================================================"
echo "4. OVERALL METRICS CALCULATION VERIFICATION"
echo "================================================================================"
echo ""
echo "Checking that session metrics are calculated correctly using:"
echo "  - Correct GT count (257, not 131)"
echo "  - Non-duplicate detections (167, not 334)"
echo "  - Proper matching across all videos"
echo ""

python3 << 'EOF_METRICS'
from sqlalchemy import create_engine, text
from config_settings import Settings

engine = create_engine(Settings().database_url)
with engine.connect() as conn:
    # Get stored metrics
    session = conn.execute(text("""
        SELECT
            id,
            accuracy_f1_score,
            accuracy_precision,
            accuracy_recall
        FROM test_sessions
        WHERE id = :session_id
    """), {"session_id": "e8e108b0-cb20-4cba-a2db-fc29f21efd16"}).fetchone()

    print("Stored Session Metrics:")
    print(f"  F1 Score:  {session[1]:.4f}")
    print(f"  Precision: {session[2]:.4f}")
    print(f"  Recall:    {session[3]:.4f}")
    print("")

    # Calculate expected metrics from database
    # Get match statistics and total ground truth count
    session_id_to_check = "e8e108b0-cb20-4cba-a2db-fc29f21efd16"
    
    stats_query = text("""
        SELECT
            SUM(CASE WHEN dc.match_type = 'TP' THEN 1 ELSE 0 END) as tp,
            SUM(CASE WHEN dc.match_type = 'FP' THEN 1 ELSE 0 END) as fp,
            SUM(CASE WHEN dc.match_type = 'FN' THEN 1 ELSE 0 END) as fn_explicit
        FROM detection_comparisons dc
        WHERE dc.test_session_id = :session_id
    """)
    stats_result = conn.execute(stats_query, {"session_id": session_id_to_check}).fetchone()

    tp = stats_result[0] or 0
    fp = stats_result[1] or 0
    fn_explicit = stats_result[2] or 0 # Explicitly stored FN comparisons

    total_gt_query = text("""
        SELECT COUNT(*) FROM ground_truth_objects
        WHERE video_id IN (
            SELECT DISTINCT svr.video_id
            FROM sequence_video_results svr
            JOIN video_test_sequences vts ON svr.video_sequence_id = vts.id
            WHERE vts.test_session_id = :session_id
        )
    """)
    total_gt = conn.execute(total_gt_query, {"session_id": session_id_to_check}).scalar() or 0

    # Calculate actual false negatives based on total ground truth
    fn_calculated = total_gt - tp if total_gt > tp else 0

    print("Match Statistics:")
    print(f"  True Positives:  {tp}")
    print(f"  False Positives: {fp}")
    print(f"  False Negatives (Calculated from total GT): {fn_calculated}")
    print(f"  Total Ground Truth: {total_gt}")
    print("")

    # Calculate metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / total_gt if total_gt > 0 else 0 # Use total_gt for recall calculation
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("Calculated Metrics:")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print("")

    # Check if stored metrics match calculated
    f1_diff = abs(session[1] - f1)
    precision_diff = abs(session[2] - precision)
    recall_diff = abs(session[3] - recall)

    print("Differences (stored vs calculated):")
    print(f"  F1 Score:  {f1_diff:.6f}")
    print(f"  Precision: {precision_diff:.6f}")
    print(f"  Recall:    {recall_diff:.6f}")
    print("")

    # PASS/FAIL criteria
    tolerance = 0.001  # Allow 0.1% difference
    if f1_diff < tolerance and precision_diff < tolerance and recall_diff < tolerance:
        print("✅ PASS: Metrics calculated correctly")
        exit(0)
    else:
        print("⚠️  WARNING: Metrics may need recalculation")
        print("   Run force_rematch=True to recalculate")
        exit(1)
EOF_METRICS

METRICS_CHECK=$?

echo ""
echo "================================================================================"
echo "VERIFICATION SUMMARY"
echo "================================================================================"
echo ""

# Function to print status
print_status() {
    case $1 in
        0) echo -e "${GREEN}✅ PASS${NC}" ;;
        1) echo -e "${RED}❌ FAIL${NC}" ;;
        2) echo -e "${YELLOW}⚠️  WARNING${NC}" ;;
        *) echo -e "${RED}❌ ERROR${NC}" ;;
    esac
}

echo "1. Detection Source Check:     $(print_status $SOURCE_CHECK)"
echo "2. GT Aggregation Check:       $(print_status $GT_CHECK)"
echo "3. Video 2 Matching Check:     $(print_status $VIDEO2_CHECK)"
echo "4. Metrics Calculation Check:  $(print_status $METRICS_CHECK)"
echo ""

# Overall status
if [ $SOURCE_CHECK -eq 0 ] && [ $GT_CHECK -eq 0 ] && [ $VIDEO2_CHECK -eq 0 ] && [ $METRICS_CHECK -eq 0 ]; then
    echo -e "${GREEN}================================================================================"
    echo "ALL FIXES VERIFIED SUCCESSFULLY!"
    echo -e "================================================================================${NC}"
    exit 0
else
    echo -e "${YELLOW}================================================================================"
    echo "SOME ISSUES DETECTED - SEE DETAILS ABOVE"
    echo -e "================================================================================${NC}"
    exit 1
fi
