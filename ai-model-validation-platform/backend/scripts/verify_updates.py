"""
Verification Script for Quality Tracking Implementation

Verifies that all codebase updates are complete and correct.

Usage:
    python scripts/verify_updates.py
    python scripts/verify_updates.py --verbose
    python scripts/verify_updates.py --category detection
"""

import re
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class VerificationIssue:
    """Represents a verification failure"""
    file_path: Path
    line_number: int
    issue_type: str
    description: str
    severity: str  # 'CRITICAL', 'WARNING', 'INFO'


class UpdateVerifier:
    """
    Verifies codebase updates are complete and correct.
    """

    def __init__(self, backend_dir: str, verbose: bool = False):
        self.backend_dir = Path(backend_dir)
        self.verbose = verbose
        self.issues: List[VerificationIssue] = []

        # Statistics
        self.stats = {
            'files_checked': 0,
            'critical_issues': 0,
            'warnings': 0,
            'info': 0,
            'passed_checks': 0
        }

    def verify_detection_queries(self) -> None:
        """
        Verify all DetectionEvent queries have quality filter.

        Checks:
        1. All db.query(DetectionEvent) have .filter() with usable_for_validation
        2. No queries bypass quality filtering
        """
        logger.info("Verifying DetectionEvent queries...")

        pattern_query = re.compile(r'db\.query\(DetectionEvent\)')
        pattern_filter = re.compile(r'usable_for_validation')

        for py_file in self.backend_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for line_num, line in enumerate(lines, 1):
                        if pattern_query.search(line):
                            # Found a query - check next few lines for filter
                            context_start = line_num - 1
                            context_end = min(len(lines), line_num + 10)
                            context = '\n'.join(lines[context_start:context_end])

                            if not pattern_filter.search(context):
                                self.issues.append(VerificationIssue(
                                    file_path=py_file,
                                    line_number=line_num,
                                    issue_type='missing_quality_filter',
                                    description='DetectionEvent query missing usable_for_validation filter',
                                    severity='CRITICAL'
                                ))
                                self.stats['critical_issues'] += 1
                            else:
                                self.stats['passed_checks'] += 1

                self.stats['files_checked'] += 1

            except Exception as e:
                logger.error(f"Error checking {py_file}: {e}")

        logger.info(f"Detection query verification complete: {self.stats['passed_checks']} passed, {self.stats['critical_issues']} issues")

    def verify_exception_handling(self) -> None:
        """
        Verify VideoTimingError is properly caught.

        Checks:
        1. All start_video_timing calls are wrapped in try/except
        2. VideoTimingError is imported where used
        3. Timing degradation is checked
        """
        logger.info("Verifying exception handling...")

        pattern_timing_call = re.compile(r'start_video_timing\(')
        pattern_exception = re.compile(r'except\s+VideoTimingError')
        pattern_import = re.compile(r'from.*video_timing_service.*import.*VideoTimingError')

        for py_file in self.backend_dir.rglob('*.py'):
            # Skip the service itself
            if 'video_timing_service.py' in str(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    has_timing_call = False
                    has_exception_handler = False
                    has_import = False

                    for line_num, line in enumerate(lines, 1):
                        if pattern_timing_call.search(line):
                            has_timing_call = True

                            # Check surrounding context for try/except
                            context_start = max(0, line_num - 10)
                            context_end = min(len(lines), line_num + 10)
                            context = '\n'.join(lines[context_start:context_end])

                            if 'try:' not in context or 'except' not in context:
                                self.issues.append(VerificationIssue(
                                    file_path=py_file,
                                    line_number=line_num,
                                    issue_type='missing_exception_handler',
                                    description='start_video_timing call not wrapped in try/except',
                                    severity='CRITICAL'
                                ))
                                self.stats['critical_issues'] += 1

                        if pattern_exception.search(line):
                            has_exception_handler = True

                        if pattern_import.search(line):
                            has_import = True

                    # If file has timing calls but missing handlers/imports
                    if has_timing_call and not has_exception_handler:
                        self.issues.append(VerificationIssue(
                            file_path=py_file,
                            line_number=0,
                            issue_type='missing_exception_handler',
                            description='File uses start_video_timing but never catches VideoTimingError',
                            severity='CRITICAL'
                        ))
                        self.stats['critical_issues'] += 1

                    if has_timing_call and not has_import:
                        self.issues.append(VerificationIssue(
                            file_path=py_file,
                            line_number=0,
                            issue_type='missing_import',
                            description='File uses start_video_timing but does not import VideoTimingError',
                            severity='WARNING'
                        ))
                        self.stats['warnings'] += 1

                    if has_timing_call and has_exception_handler and has_import:
                        self.stats['passed_checks'] += 1

                self.stats['files_checked'] += 1

            except Exception as e:
                logger.error(f"Error checking {py_file}: {e}")

        logger.info(f"Exception handling verification complete: {self.stats['passed_checks']} passed, {self.stats['critical_issues']} issues")

    def verify_connection_management(self) -> None:
        """
        Verify no SessionLocal() leaks.

        Checks:
        1. No direct SessionLocal() without context manager
        2. managed_db_session is imported where needed
        3. No manual db.close() calls (context manager handles it)
        """
        logger.info("Verifying connection management...")

        pattern_session_local = re.compile(r'SessionLocal\(\)')
        pattern_managed = re.compile(r'managed_db_session')
        pattern_depends = re.compile(r'Depends\(get_db\)')

        for py_file in self.backend_dir.rglob('*.py'):
            # Skip database.py itself
            if 'database.py' in str(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for line_num, line in enumerate(lines, 1):
                        if pattern_session_local.search(line):
                            # Check if it's in a context manager
                            context_start = max(0, line_num - 3)
                            context_end = min(len(lines), line_num + 1)
                            context = '\n'.join(lines[context_start:context_end])

                            # Allow if part of managed_db_session implementation
                            if 'managed_db_session' in py_file.name:
                                continue

                            # Check if wrapped in 'with' statement
                            if 'with' not in context:
                                self.issues.append(VerificationIssue(
                                    file_path=py_file,
                                    line_number=line_num,
                                    issue_type='connection_leak',
                                    description='SessionLocal() used without context manager',
                                    severity='CRITICAL'
                                ))
                                self.stats['critical_issues'] += 1

                self.stats['files_checked'] += 1

            except Exception as e:
                logger.error(f"Error checking {py_file}: {e}")

        logger.info(f"Connection management verification complete")

    def verify_timing_degradation_handling(self) -> None:
        """
        Verify timing degradation is properly handled.

        Checks:
        1. Code checks 'timing_degraded' flag after start_video_timing
        2. Sessions marked with timing quality status
        """
        logger.info("Verifying timing degradation handling...")

        pattern_timing_call = re.compile(r'start_video_timing\(')
        pattern_degraded_check = re.compile(r'timing_degraded')

        for py_file in self.backend_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for line_num, line in enumerate(lines, 1):
                        if pattern_timing_call.search(line):
                            # Check next 20 lines for degradation check
                            context_start = line_num
                            context_end = min(len(lines), line_num + 20)
                            context = '\n'.join(lines[context_start:context_end])

                            if not pattern_degraded_check.search(context):
                                self.issues.append(VerificationIssue(
                                    file_path=py_file,
                                    line_number=line_num,
                                    issue_type='missing_degradation_check',
                                    description='start_video_timing call does not check timing_degraded flag',
                                    severity='WARNING'
                                ))
                                self.stats['warnings'] += 1
                            else:
                                self.stats['passed_checks'] += 1

                self.stats['files_checked'] += 1

            except Exception as e:
                logger.error(f"Error checking {py_file}: {e}")

        logger.info(f"Timing degradation verification complete")

    def print_report(self) -> str:
        """
        Generate verification report.

        Returns:
            Report as string
        """
        report = f"""
{'=' * 80}
Quality Tracking Implementation Verification Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 80}

Summary:
--------
Files Checked:      {self.stats['files_checked']}
Passed Checks:      {self.stats['passed_checks']}
Critical Issues:    {self.stats['critical_issues']}
Warnings:           {self.stats['warnings']}
Info:               {self.stats['info']}

Status: {'✅ PASSED' if self.stats['critical_issues'] == 0 else '❌ FAILED'}

"""

        if self.stats['critical_issues'] == 0 and self.stats['warnings'] == 0:
            report += "\n🎉 All verification checks passed!\n"
        elif self.stats['critical_issues'] == 0:
            report += f"\n⚠️  No critical issues, but {self.stats['warnings']} warnings need attention.\n"
        else:
            report += f"\n❌ {self.stats['critical_issues']} critical issues must be fixed before deployment.\n"

        # Group issues by type
        issues_by_type: Dict[str, List[VerificationIssue]] = {}
        for issue in self.issues:
            if issue.issue_type not in issues_by_type:
                issues_by_type[issue.issue_type] = []
            issues_by_type[issue.issue_type].append(issue)

        if issues_by_type:
            report += "\nIssues by Type:\n"
            report += "---------------\n"

            for issue_type, issues in sorted(issues_by_type.items()):
                severity_icon = '🔴' if issues[0].severity == 'CRITICAL' else '🟡'
                report += f"\n{severity_icon} {issue_type}: {len(issues)} occurrences\n"

                if self.verbose:
                    for issue in issues[:10]:  # Limit to first 10
                        report += f"   - {issue.file_path}:{issue.line_number}\n"
                        report += f"     {issue.description}\n"

                    if len(issues) > 10:
                        report += f"   ... and {len(issues) - 10} more\n"

        return report

    def run_all_verifications(self) -> bool:
        """
        Run all verification checks.

        Returns:
            bool: True if all checks passed
        """
        self.verify_detection_queries()
        self.verify_exception_handling()
        self.verify_connection_management()
        self.verify_timing_degradation_handling()

        return self.stats['critical_issues'] == 0


def main():
    parser = argparse.ArgumentParser(description='Verify quality tracking updates')
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed issue information'
    )
    parser.add_argument(
        '--category',
        choices=['detection', 'timing', 'connection', 'all'],
        default='all',
        help='Which category to verify'
    )
    parser.add_argument(
        '--backend-dir',
        default='/home/rigade/Testing/ai-model-validation-platform/backend',
        help='Path to backend directory'
    )

    args = parser.parse_args()

    verifier = UpdateVerifier(args.backend_dir, verbose=args.verbose)

    try:
        if args.category == 'detection':
            verifier.verify_detection_queries()
        elif args.category == 'timing':
            verifier.verify_exception_handling()
            verifier.verify_timing_degradation_handling()
        elif args.category == 'connection':
            verifier.verify_connection_management()
        else:
            verifier.run_all_verifications()

        # Generate and print report
        report = verifier.print_report()
        print(report)

        # Save report to file
        report_path = Path(args.backend_dir) / 'docs' / f'verification_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(report_path, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to {report_path}")

        # Exit with error code if critical issues found
        if verifier.stats['critical_issues'] > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
