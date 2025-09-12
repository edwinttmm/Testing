#!/usr/bin/env python3
"""Check detection results and ground truth in database"""

import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('test_database.db')
cursor = conn.cursor()

print("=" * 80)
print("CHECKING TEST RESULTS AND DETECTION DATA")
print("=" * 80)

# Get recent test sessions
cursor.execute("""
    SELECT id, project_id, status, created_at, 
           accuracy, precision, recall, f1_score,
           true_positives, false_positives, false_negatives
    FROM test_sessions 
    ORDER BY created_at DESC 
    LIMIT 5
""")
sessions = cursor.fetchall()

print("\n📊 Recent Test Sessions:")
print("-" * 80)
for session in sessions:
    print(f"Session ID: {session[0]}")
    print(f"  Project: {session[1]}")
    print(f"  Status: {session[2]}")
    print(f"  Created: {session[3]}")
    print(f"  Metrics: Accuracy={session[4]}, Precision={session[5]}, Recall={session[6]}, F1={session[7]}")
    print(f"  Counts: TP={session[8]}, FP={session[9]}, FN={session[10]}")
    
    # Check detection events for this session
    cursor.execute("""
        SELECT COUNT(*) FROM detection_events 
        WHERE test_session_id = ?
    """, (session[0],))
    detection_count = cursor.fetchone()[0]
    print(f"  Detection Events: {detection_count}")
    print()

# Check detection events
print("\n🎯 Detection Events Summary:")
print("-" * 80)
cursor.execute("""
    SELECT test_session_id, COUNT(*) as count, 
           AVG(confidence) as avg_conf,
           MIN(confidence) as min_conf,
           MAX(confidence) as max_conf
    FROM detection_events 
    GROUP BY test_session_id
    ORDER BY test_session_id DESC
    LIMIT 10
""")
detections = cursor.fetchall()
for det in detections:
    print(f"Session {det[0]}: {det[1]} detections, Confidence: avg={det[2]:.2f if det[2] else 0}, min={det[3]:.2f if det[3] else 0}, max={det[4]:.2f if det[4] else 0}")

# Check ground truth objects
print("\n📐 Ground Truth Objects:")
print("-" * 80)
cursor.execute("""
    SELECT video_id, COUNT(*) as count
    FROM ground_truth_objects
    GROUP BY video_id
    LIMIT 10
""")
ground_truth = cursor.fetchall()
for gt in ground_truth:
    print(f"Video {gt[0]}: {gt[1]} ground truth objects")

# Check videos with ground truth
print("\n📹 Videos with Ground Truth:")
print("-" * 80)
cursor.execute("""
    SELECT v.id, v.filename, v.groundTruthGenerated,
           COUNT(DISTINCT gt.id) as gt_count
    FROM videos v
    LEFT JOIN ground_truth_objects gt ON v.id = gt.video_id
    WHERE v.groundTruthGenerated = 1
    GROUP BY v.id
    LIMIT 10
""")
videos = cursor.fetchall()
for video in videos:
    print(f"Video {video[0]}: {video[1]}")
    print(f"  Ground Truth Generated: {video[2]}")
    print(f"  Ground Truth Objects: {video[3]}")

# Check for any detection comparisons
print("\n🔍 Detection Comparisons:")
print("-" * 80)
cursor.execute("""
    SELECT COUNT(*) FROM detection_comparisons
""")
comparison_count = cursor.fetchone()[0]
print(f"Total detection comparisons in database: {comparison_count}")

if comparison_count > 0:
    cursor.execute("""
        SELECT test_session_id, match_type, COUNT(*) as count
        FROM detection_comparisons
        GROUP BY test_session_id, match_type
        ORDER BY test_session_id DESC
        LIMIT 20
    """)
    comparisons = cursor.fetchall()
    for comp in comparisons:
        print(f"  Session {comp[0]}: {comp[2]} {comp[1]} matches")

# Check test results
print("\n📈 Test Results:")
print("-" * 80)
cursor.execute("""
    SELECT test_session_id, accuracy, precision, recall, f1_score
    FROM test_results
    ORDER BY created_at DESC
    LIMIT 10
""")
results = cursor.fetchall()
for result in results:
    print(f"Session {result[0]}: Acc={result[1]:.2f if result[1] else 0}, Prec={result[2]:.2f if result[2] else 0}, Rec={result[3]:.2f if result[3] else 0}, F1={result[4]:.2f if result[4] else 0}")

conn.close()
print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)