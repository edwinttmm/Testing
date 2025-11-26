#!/usr/bin/env python3
"""
Detection Optimization Integration Test Script

Comprehensive test suite to verify detection optimization fixes:
- No hardcoded frame_number=0 in code
- >95% of detections have valid frame numbers
- Detection capture rate >95%
- Proper frame number calculation from video_relative_timestamp * fps

Usage:
    python3 scripts/test_detection_optimization.py <session_id>
    python3 scripts/test_detection_optimization.py --all
    python3 scripts/test_detection_optimization.py --verify-code

Author: Detection Optimization Integration Specialist
Date: 2025-11-20
"""

import sys
import os
import re
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import DetectionEvent, GroundTruthObject, TestSession, Video
from sqlalchemy import func, and_, or_

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetectionOptimizationTester:
    """Comprehensive test suite for detection optimization"""

    def __init__(self):
        self.db = SessionLocal()
        self.test_results = {
            'code_verification': None,
            'frame_calculation_test': None,
            'capture_rate_test': None,
            'regression_test': None,
            'timestamp': datetime.utcnow().isoformat()
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.close()

    def verify_code_fixes(self) -> Dict:
        """
        Test 1: Verify no hardcoded frame_number=0 in detection service
        """
        logger.info(f"\n{'='*80}")
        logger.info("TEST 1: CODE VERIFICATION")
        logger.info(f"{'='*80}\n")

        service_file = Path(__file__).parent.parent / 'services' / 'labjack_detection_service.py'

        if not service_file.exists():
            logger.error(f"❌ Service file not found: {service_file}")
            return {
                'passed': False,
                'error': 'Service file not found'
            }

        with open(service_file, 'r') as f:
            content = f.read()

        # Search for hardcoded frame_number=0 patterns
        hardcoded_patterns = [
            r'frame_number\s*=\s*0\s*[,\)]',  # frame_number=0,
            r'video_frame_number\s*=\s*0\s*[,\)]',  # video_frame_number=0,
        ]

        issues_found = []
        for pattern in hardcoded_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Get line number
                line_num = content[:match.start()].count('\n') + 1
                # Get context (5 lines around match)
                lines = content.split('\n')
                context_start = max(0, line_num - 3)
                context_end = min(len(lines), line_num + 2)
                context = '\n'.join(f"{i+1}: {lines[i]}" for i in range(context_start, context_end))

                issues_found.append({
                    'line': line_num,
                    'pattern': pattern,
                    'context': context
                })

        # Check for frame calculation implementation
        has_calculation = 'int(round(event.video_relative_timestamp * fps_used))' in content
        has_video_fps_query = 'video.fps' in content
        has_fallback = 'fps_used = 24.0' in content or 'fps = 24' in content

        logger.info("🔍 Code Analysis Results:")
        logger.info(f"  Hardcoded frame_number=0 found: {len(issues_found)} instances")
        logger.info(f"  Frame calculation implemented: {'✅' if has_calculation else '❌'}")
        logger.info(f"  Video FPS query implemented: {'✅' if has_video_fps_query else '❌'}")
        logger.info(f"  FPS fallback implemented: {'✅' if has_fallback else '❌'}")

        if issues_found:
            logger.warning(f"\n⚠️  Found {len(issues_found)} hardcoded frame_number=0 instances:")
            for issue in issues_found:
                logger.warning(f"\n  Line {issue['line']}:")
                logger.warning(f"  {issue['context']}")

        passed = (
            len(issues_found) == 0 and
            has_calculation and
            has_video_fps_query and
            has_fallback
        )

        result = {
            'passed': passed,
            'hardcoded_count': len(issues_found),
            'has_calculation': has_calculation,
            'has_video_fps_query': has_video_fps_query,
            'has_fallback': has_fallback,
            'issues': issues_found
        }

        logger.info(f"\n{'✅ PASSED' if passed else '❌ FAILED'}: Code Verification")
        self.test_results['code_verification'] = result
        return result

    def test_frame_calculation(self, session_id: str) -> Dict:
        """
        Test 2: Verify >95% of detections have valid frame numbers
        """
        logger.info(f"\n{'='*80}")
        logger.info("TEST 2: FRAME NUMBER CALCULATION")
        logger.info(f"{'='*80}\n")

        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            logger.error(f"❌ Session not found: {session_id}")
            return {'passed': False, 'error': 'Session not found'}

        detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).all()

        total_detections = len(detections)
        if total_detections == 0:
            logger.warning("⚠️ No detections found")
            return {'passed': False, 'error': 'No detections'}

        # Count detections with valid frame numbers
        valid_frame_count = 0
        null_frame_count = 0
        zero_frame_count = 0
        invalid_frame_count = 0

        frame_calculation_methods = {}

        for detection in detections:
            if detection.frame_number is None:
                null_frame_count += 1
            elif detection.frame_number == 0:
                zero_frame_count += 1
            elif detection.frame_number > 0:
                valid_frame_count += 1
            else:
                invalid_frame_count += 1

            # Track calculation method from metadata
            if detection.detection_metadata and isinstance(detection.detection_metadata, dict):
                frame_calc = detection.detection_metadata.get('frame_calculation', {})
                method = frame_calc.get('method', 'unknown')
                frame_calculation_methods[method] = frame_calculation_methods.get(method, 0) + 1

        valid_percentage = (valid_frame_count / total_detections * 100)

        logger.info(f"📊 Frame Number Analysis for session {session_id}:")
        logger.info(f"  Total Detections: {total_detections}")
        logger.info(f"  ✅ Valid Frame Numbers (>0): {valid_frame_count} ({valid_percentage:.1f}%)")
        logger.info(f"  ❌ NULL Frame Numbers: {null_frame_count}")
        logger.info(f"  ❌ Zero Frame Numbers: {zero_frame_count}")
        logger.info(f"  ❌ Invalid Frame Numbers (<0): {invalid_frame_count}")

        if frame_calculation_methods:
            logger.info(f"\n  Frame Calculation Methods:")
            for method, count in sorted(frame_calculation_methods.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"    {method}: {count} detections")

        # Check video-relative timestamp availability
        with_video_time = sum(1 for d in detections if d.video_relative_timestamp is not None)
        video_time_percentage = (with_video_time / total_detections * 100)

        logger.info(f"\n  Video-Relative Timestamps:")
        logger.info(f"    ✅ Available: {with_video_time} ({video_time_percentage:.1f}%)")
        logger.info(f"    ❌ Missing: {total_detections - with_video_time}")

        # Test passes if >95% have valid frame numbers
        passed = valid_percentage >= 95.0
        target = "95%"

        logger.info(f"\n  Target: {target}")
        logger.info(f"  Actual: {valid_percentage:.1f}%")
        logger.info(f"\n{'✅ PASSED' if passed else '❌ FAILED'}: Frame Calculation Test")

        result = {
            'passed': passed,
            'session_id': session_id,
            'total_detections': total_detections,
            'valid_frame_count': valid_frame_count,
            'null_frame_count': null_frame_count,
            'zero_frame_count': zero_frame_count,
            'invalid_frame_count': invalid_frame_count,
            'valid_percentage': valid_percentage,
            'video_time_percentage': video_time_percentage,
            'calculation_methods': frame_calculation_methods,
            'target': 95.0
        }

        self.test_results['frame_calculation_test'] = result
        return result

    def test_capture_rate(self, session_id: str) -> Dict:
        """
        Test 3: Verify detection capture rate >95%
        """
        logger.info(f"\n{'='*80}")
        logger.info("TEST 3: DETECTION CAPTURE RATE")
        logger.info(f"{'='*80}\n")

        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            logger.error(f"❌ Session not found: {session_id}")
            return {'passed': False, 'error': 'Session not found'}

        # Get detections with valid frame numbers
        detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.frame_number > 0
        ).all()

        detection_frame_numbers = {d.frame_number for d in detections}

        # Get ground truth frames
        gt_frames_query = self.db.query(
            GroundTruthObject.frame_number
        ).join(Video).filter(
            Video.project_id == session.project_id,
            GroundTruthObject.frame_number > 0
        ).group_by(
            GroundTruthObject.frame_number
        ).all()

        total_gt_frames = len(gt_frames_query)

        if total_gt_frames == 0:
            logger.warning("⚠️ No ground truth frames found")
            return {'passed': False, 'error': 'No GT frames'}

        gt_frame_numbers = {row[0] for row in gt_frames_query}
        matched_frames = gt_frame_numbers.intersection(detection_frame_numbers)
        unmatched_frames = gt_frame_numbers.difference(detection_frame_numbers)

        capture_rate = (len(matched_frames) / total_gt_frames * 100)

        logger.info(f"🎯 Detection-to-GT Matching for session {session_id}:")
        logger.info(f"  Total GT Frames: {total_gt_frames}")
        logger.info(f"  Total Detections with Frames: {len(detections)}")
        logger.info(f"  Unique Detection Frames: {len(detection_frame_numbers)}")
        logger.info(f"  ✅ Matched GT Frames: {len(matched_frames)} ({capture_rate:.1f}%)")
        logger.info(f"  ❌ Unmatched GT Frames: {len(unmatched_frames)}")

        # Sample matched and unmatched frames
        if matched_frames:
            sample_matched = sorted(list(matched_frames))[:10]
            logger.info(f"\n  Sample Matched Frames: {sample_matched}")

        if unmatched_frames:
            sample_unmatched = sorted(list(unmatched_frames))[:10]
            logger.info(f"  Sample Unmatched Frames: {sample_unmatched}")

        # Analyze why frames are unmatched
        if unmatched_frames:
            logger.info(f"\n  Analyzing Unmatched Frames:")
            # Check if detections exist but with NULL/0 frame numbers
            all_detections = self.db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).all()

            detections_missing_frames = sum(
                1 for d in all_detections
                if d.frame_number is None or d.frame_number == 0
            )

            if detections_missing_frames > 0:
                logger.info(f"    ⚠️  {detections_missing_frames} detections have NULL/0 frame numbers")
                logger.info(f"    This may explain {min(detections_missing_frames, len(unmatched_frames))} unmatched frames")

        # Test passes if capture rate >95%
        passed = capture_rate >= 95.0
        target = "95%"

        logger.info(f"\n  Target: {target}")
        logger.info(f"  Actual: {capture_rate:.1f}%")
        logger.info(f"\n{'✅ PASSED' if passed else '❌ FAILED'}: Capture Rate Test")

        result = {
            'passed': passed,
            'session_id': session_id,
            'total_gt_frames': total_gt_frames,
            'matched_frames': len(matched_frames),
            'unmatched_frames': len(unmatched_frames),
            'capture_rate': capture_rate,
            'target': 95.0
        }

        self.test_results['capture_rate_test'] = result
        return result

    def test_regression(self, session_id: str) -> Dict:
        """
        Test 4: Regression test - ensure no functionality broken
        """
        logger.info(f"\n{'='*80}")
        logger.info("TEST 4: REGRESSION TESTING")
        logger.info(f"{'='*80}\n")

        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            logger.error(f"❌ Session not found: {session_id}")
            return {'passed': False, 'error': 'Session not found'}

        detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).all()

        total_detections = len(detections)
        if total_detections == 0:
            logger.warning("⚠️ No detections found")
            return {'passed': False, 'error': 'No detections'}

        # Check essential fields are still populated
        checks = {
            'timestamp': 0,
            'detection_channel': 0,
            'labjack_voltage': 0,
            'source': 0,
            'detection_type': 0,
            'detection_metadata': 0
        }

        for detection in detections:
            if detection.timestamp is not None:
                checks['timestamp'] += 1
            if detection.detection_channel is not None:
                checks['detection_channel'] += 1
            if detection.labjack_voltage is not None:
                checks['labjack_voltage'] += 1
            if detection.source is not None:
                checks['source'] += 1
            if detection.detection_type is not None:
                checks['detection_type'] += 1
            if detection.detection_metadata is not None:
                checks['detection_metadata'] += 1

        logger.info(f"🔍 Field Validation for session {session_id}:")
        logger.info(f"  Total Detections: {total_detections}")

        all_passed = True
        for field, count in checks.items():
            percentage = (count / total_detections * 100)
            status = "✅" if percentage >= 95 else "❌"
            logger.info(f"  {status} {field}: {count}/{total_detections} ({percentage:.1f}%)")
            if percentage < 95:
                all_passed = False

        # Check metadata contains frame_calculation
        with_frame_calc_metadata = sum(
            1 for d in detections
            if d.detection_metadata and isinstance(d.detection_metadata, dict)
            and 'frame_calculation' in d.detection_metadata
        )
        frame_calc_percentage = (with_frame_calc_metadata / total_detections * 100)
        logger.info(f"\n  Metadata Quality:")
        logger.info(f"    Frame calculation metadata: {with_frame_calc_metadata} ({frame_calc_percentage:.1f}%)")

        logger.info(f"\n{'✅ PASSED' if all_passed else '❌ FAILED'}: Regression Test")

        result = {
            'passed': all_passed,
            'session_id': session_id,
            'total_detections': total_detections,
            'field_checks': {k: (v / total_detections * 100) for k, v in checks.items()},
            'frame_calc_metadata_percentage': frame_calc_percentage
        }

        self.test_results['regression_test'] = result
        return result

    def generate_summary_report(self) -> str:
        """Generate comprehensive test summary report"""
        logger.info(f"\n{'='*80}")
        logger.info("COMPREHENSIVE TEST SUMMARY")
        logger.info(f"{'='*80}\n")

        tests_run = sum(1 for v in self.test_results.values() if v is not None and isinstance(v, dict))
        tests_passed = sum(1 for v in self.test_results.values() if isinstance(v, dict) and v.get('passed', False))

        logger.info(f"Tests Run: {tests_run}")
        logger.info(f"Tests Passed: {tests_passed}")
        logger.info(f"Tests Failed: {tests_run - tests_passed}")

        logger.info(f"\n📋 Individual Test Results:")

        # Test 1: Code Verification
        code_result = self.test_results.get('code_verification')
        if code_result:
            status = "✅ PASS" if code_result.get('passed') else "❌ FAIL"
            logger.info(f"  {status} - Code Verification")
            if code_result.get('hardcoded_count', 0) > 0:
                logger.info(f"      Found {code_result['hardcoded_count']} hardcoded frame_number=0")

        # Test 2: Frame Calculation
        frame_result = self.test_results.get('frame_calculation_test')
        if frame_result:
            status = "✅ PASS" if frame_result.get('passed') else "❌ FAIL"
            logger.info(f"  {status} - Frame Number Calculation")
            logger.info(f"      {frame_result.get('valid_percentage', 0):.1f}% valid frame numbers (target: 95%)")

        # Test 3: Capture Rate
        capture_result = self.test_results.get('capture_rate_test')
        if capture_result:
            status = "✅ PASS" if capture_result.get('passed') else "❌ FAIL"
            logger.info(f"  {status} - Detection Capture Rate")
            logger.info(f"      {capture_result.get('capture_rate', 0):.1f}% capture rate (target: 95%)")

        # Test 4: Regression
        regression_result = self.test_results.get('regression_test')
        if regression_result:
            status = "✅ PASS" if regression_result.get('passed') else "❌ FAIL"
            logger.info(f"  {status} - Regression Testing")

        overall_passed = tests_passed == tests_run and tests_run > 0

        logger.info(f"\n{'='*80}")
        if overall_passed:
            logger.info("🎉 ALL TESTS PASSED - Detection optimization verified!")
            logger.info("✅ No hardcoded frame_number=0")
            logger.info("✅ >95% valid frame numbers")
            logger.info("✅ >95% detection capture rate")
            logger.info("✅ No regression in functionality")
        else:
            logger.info("❌ SOME TESTS FAILED - Review details above")
        logger.info(f"{'='*80}\n")

        return self.test_results

    def run_full_test_suite(self, session_id: str) -> Dict:
        """Run all tests for a session"""
        logger.info(f"\n{'='*80}")
        logger.info(f"DETECTION OPTIMIZATION INTEGRATION TEST")
        logger.info(f"Session: {session_id}")
        logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        logger.info(f"{'='*80}\n")

        # Run all tests
        self.verify_code_fixes()
        self.test_frame_calculation(session_id)
        self.test_capture_rate(session_id)
        self.test_regression(session_id)

        # Generate summary
        return self.generate_summary_report()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 scripts/test_detection_optimization.py <session_id>")
        print("  python3 scripts/test_detection_optimization.py --verify-code")
        print("  python3 scripts/test_detection_optimization.py --all")
        sys.exit(1)

    with DetectionOptimizationTester() as tester:
        if sys.argv[1] == '--verify-code':
            tester.verify_code_fixes()
        elif sys.argv[1] == '--all':
            # Find all completed sessions
            sessions = tester.db.query(TestSession).filter(
                TestSession.status.in_(['completed', 'running'])
            ).all()

            logger.info(f"Testing {len(sessions)} sessions...")
            for session in sessions:
                tester.run_full_test_suite(session.id)
                logger.info("\n")
        else:
            session_id = sys.argv[1]
            tester.run_full_test_suite(session_id)


if __name__ == '__main__':
    main()
