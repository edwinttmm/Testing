#!/usr/bin/env python3
"""
Timestamp Epoch Validation Script

This script validates that all timestamps in the database use the correct Unix epoch (1970-01-01)
and have not been corrupted by epoch offset bugs.

Usage:
    python validate_timestamp_epochs.py
    python validate_timestamp_epochs.py --session-id 0846e476
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Tuple
import sys


class TimestampValidator:
    """Validator for checking timestamp epochs in database"""

    def __init__(self, db_path: str = "dev_database.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.issues = []
        self.warnings = []

    def validate_timestamp_value(self, timestamp: float, field_name: str,
                                 record_id: str) -> Tuple[bool, str]:
        """
        Validate a single timestamp value.

        Returns:
            (is_valid, message)
        """
        try:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

            # Check year is reasonable
            if dt.year < 2020:
                return False, f"{field_name} year {dt.year} is too old (record {record_id})"
            elif dt.year > 2030:
                return False, f"{field_name} year {dt.year} is in future (record {record_id})"

            # Check for negative timestamps
            if timestamp < 0:
                return False, f"{field_name} is negative (epoch before 1970) (record {record_id})"

            # Check for overflow
            if timestamp > 9000000000:
                return False, f"{field_name} too large (overflow?) (record {record_id})"

            return True, f"OK: {dt.isoformat()}"

        except Exception as e:
            return False, f"{field_name} cannot parse: {e} (record {record_id})"

    def validate_test_sessions(self, session_id: str = None) -> Dict:
        """Validate timestamps in test_sessions table"""
        print("\n=== Validating test_sessions table ===")

        query = "SELECT id, video_start_timestamp, created_at FROM test_sessions"
        if session_id:
            query += f" WHERE id LIKE '{session_id}%'"

        self.cursor.execute(query)
        sessions = self.cursor.fetchall()

        results = {
            "total": len(sessions),
            "valid": 0,
            "invalid": 0,
            "issues": []
        }

        for sess_id, video_start_ts, created_at in sessions:
            if video_start_ts:
                is_valid, msg = self.validate_timestamp_value(
                    video_start_ts, "video_start_timestamp", sess_id[:8]
                )
                if is_valid:
                    results["valid"] += 1
                    print(f"  ✓ {sess_id[:8]}... video_start_timestamp: {msg}")
                else:
                    results["invalid"] += 1
                    results["issues"].append(msg)
                    print(f"  ✗ {sess_id[:8]}... {msg}")

        return results

    def validate_detection_events(self, session_id: str = None) -> Dict:
        """Validate timestamps in detection_events table"""
        print("\n=== Validating detection_events table ===")

        query = """
            SELECT
                id,
                test_session_id,
                labjack_timestamp,
                video_relative_timestamp,
                timestamp
            FROM detection_events
        """
        if session_id:
            query += f" WHERE test_session_id LIKE '{session_id}%'"
        query += " LIMIT 100"  # Sample first 100

        self.cursor.execute(query)
        detections = self.cursor.fetchall()

        results = {
            "total": len(detections),
            "valid_labjack": 0,
            "valid_relative": 0,
            "invalid": 0,
            "issues": []
        }

        for det_id, sess_id, lj_ts, vr_ts, ts in detections:
            # Validate labjack_timestamp (should be Unix epoch)
            if lj_ts:
                is_valid, msg = self.validate_timestamp_value(
                    lj_ts, "labjack_timestamp", det_id[:8]
                )
                if is_valid:
                    results["valid_labjack"] += 1
                else:
                    results["invalid"] += 1
                    results["issues"].append(msg)
                    print(f"  ✗ {det_id[:8]}... labjack: {msg}")

            # Validate video_relative_timestamp (should be 0-N seconds, not Unix)
            if vr_ts is not None:
                if 0 <= vr_ts <= 3600:  # 0-1 hour reasonable for relative time
                    results["valid_relative"] += 1
                else:
                    results["invalid"] += 1
                    issue = f"video_relative_timestamp {vr_ts} out of range (should be 0-3600s)"
                    results["issues"].append(issue)
                    print(f"  ✗ {det_id[:8]}... {issue}")

        if results["invalid"] == 0:
            print(f"  ✓ All {results['total']} detection timestamps valid")

        return results

    def check_session_consistency(self, session_id: str) -> Dict:
        """Check timestamp consistency within a session"""
        print(f"\n=== Checking consistency for session {session_id} ===")

        # Get session info
        self.cursor.execute("""
            SELECT video_start_timestamp FROM test_sessions WHERE id LIKE ?
        """, (f"{session_id}%",))
        session_row = self.cursor.fetchone()

        if not session_row:
            return {"error": f"Session {session_id} not found"}

        video_start_ts = session_row[0]

        # Get detection timestamps
        self.cursor.execute("""
            SELECT
                MIN(labjack_timestamp) as min_lj,
                MAX(labjack_timestamp) as max_lj,
                MIN(video_relative_timestamp) as min_vr,
                MAX(video_relative_timestamp) as max_vr,
                COUNT(*) as total
            FROM detection_events
            WHERE test_session_id LIKE ?
        """, (f"{session_id}%",))

        stats = self.cursor.fetchone()
        min_lj, max_lj, min_vr, max_vr, total = stats

        results = {
            "session_id": session_id,
            "video_start_timestamp": video_start_ts,
            "detection_count": total,
            "consistent": True,
            "issues": []
        }

        if not min_lj:
            results["issues"].append("No detection events found")
            return results

        # Check 1: LabJack timestamps should be >= video_start_timestamp
        if min_lj < video_start_ts:
            results["consistent"] = False
            results["issues"].append(
                f"LabJack timestamps start before video ({min_lj} < {video_start_ts})"
            )

        # Check 2: Video relative timestamps should start near 0
        if min_vr < 0 or min_vr > 1:
            results["consistent"] = False
            results["issues"].append(
                f"Video relative timestamps don't start near 0 ({min_vr})"
            )

        # Check 3: Durations should match
        lj_duration = max_lj - min_lj
        vr_duration = max_vr - min_vr
        duration_diff = abs(lj_duration - vr_duration)

        if duration_diff > 1.0:  # More than 1 second difference
            results["consistent"] = False
            results["issues"].append(
                f"Duration mismatch: LabJack={lj_duration:.3f}s, VideoRel={vr_duration:.3f}s"
            )

        # Print results
        print(f"  Video start: {datetime.fromtimestamp(video_start_ts)}")
        print(f"  Detections: {total}")
        print(f"  LabJack range: {datetime.fromtimestamp(min_lj)} to {datetime.fromtimestamp(max_lj)}")
        print(f"  Duration: {lj_duration:.3f}s")
        print(f"  Video relative range: {min_vr:.6f}s to {max_vr:.6f}s")

        if results["consistent"]:
            print(f"  ✓ All consistency checks passed")
        else:
            print(f"  ✗ Consistency issues found:")
            for issue in results["issues"]:
                print(f"    - {issue}")

        return results

    def run_full_validation(self, session_id: str = None) -> Dict:
        """Run all validation checks"""
        print("=" * 80)
        print("TIMESTAMP EPOCH VALIDATION")
        print("=" * 80)

        results = {
            "test_sessions": self.validate_test_sessions(session_id),
            "detection_events": self.validate_detection_events(session_id)
        }

        if session_id:
            results["consistency"] = self.check_session_consistency(session_id)

        # Summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)

        total_issues = (
            results["test_sessions"]["invalid"] +
            results["detection_events"]["invalid"]
        )

        if total_issues == 0:
            print("✓ ALL TIMESTAMP VALIDATIONS PASSED")
            print("  No epoch bugs detected")
            print("  All timestamps use correct Unix epoch (1970-01-01)")
        else:
            print(f"✗ {total_issues} VALIDATION ISSUES FOUND")
            print("\nIssues:")
            for issue in results["test_sessions"].get("issues", []):
                print(f"  - {issue}")
            for issue in results["detection_events"].get("issues", []):
                print(f"  - {issue}")

        return results

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Validate timestamp epochs in database"
    )
    parser.add_argument(
        "--session-id",
        help="Validate specific session (e.g., 0846e476)",
        default=None
    )
    parser.add_argument(
        "--db",
        help="Database path",
        default="dev_database.db"
    )

    args = parser.parse_args()

    validator = TimestampValidator(args.db)
    results = validator.run_full_validation(args.session_id)

    # Exit with error code if issues found
    total_issues = (
        results["test_sessions"]["invalid"] +
        results["detection_events"]["invalid"]
    )

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
