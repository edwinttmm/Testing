"""
Automated Codebase Updater for Quality Tracking Implementation

⚠️ WARNING: This script modifies source code files.
⚠️ ALWAYS review changes in version control before committing.
⚠️ Run in a test environment first.

Usage:
    python scripts/update_codebase.py --dry-run  # Preview changes
    python scripts/update_codebase.py --apply    # Apply changes
    python scripts/update_codebase.py --category detection  # Update specific category
"""

import re
import os
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
class FileChange:
    """Represents a single file change"""
    file_path: Path
    line_number: int
    old_line: str
    new_line: str
    category: str
    description: str


class CodebaseUpdater:
    """
    Systematically updates codebase with quality tracking improvements.
    """

    def __init__(self, backend_dir: str, dry_run: bool = True):
        self.backend_dir = Path(backend_dir)
        self.dry_run = dry_run
        self.changes: List[FileChange] = []
        self.errors: List[str] = []

        # Statistics
        self.stats = {
            'files_scanned': 0,
            'files_modified': 0,
            'changes_made': 0,
            'errors': 0
        }

    def find_detection_queries(self) -> List[Tuple[Path, int, str]]:
        """
        Find all DetectionEvent queries that need quality filtering.

        Returns:
            List of (file_path, line_number, line_content) tuples
        """
        logger.info("Scanning for DetectionEvent queries...")
        pattern = re.compile(r'db\.query\(DetectionEvent\)')
        results = []

        for py_file in self.backend_dir.rglob('*.py'):
            # Skip this script itself
            if py_file.name == 'update_codebase.py':
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            # Check if already has usable_for_validation
                            if 'usable_for_validation' not in line:
                                results.append((py_file, line_num, line.rstrip()))

                self.stats['files_scanned'] += 1

            except Exception as e:
                self.errors.append(f"Error reading {py_file}: {e}")
                self.stats['errors'] += 1

        logger.info(f"Found {len(results)} DetectionEvent queries needing updates")
        return results

    def add_quality_filter(self, file_path: Path, line_number: int, line_content: str) -> FileChange:
        """
        Generate a change to add quality filter to DetectionEvent query.

        Args:
            file_path: Path to the file
            line_number: Line number of the query
            line_content: Current line content

        Returns:
            FileChange object describing the modification
        """
        # Detect query pattern
        if '.filter(' in line_content:
            # Multi-filter query - add to existing filter
            new_line = re.sub(
                r'(\.filter\([^)]+)\)',
                r'\1,\n    DetectionEvent.usable_for_validation == True  # Quality filter added by migration\n)',
                line_content
            )
        else:
            # Single filter or no filter - add new filter call
            new_line = re.sub(
                r'(db\.query\(DetectionEvent\))',
                r'\1.filter(DetectionEvent.usable_for_validation == True)',
                line_content
            )

        return FileChange(
            file_path=file_path,
            line_number=line_number,
            old_line=line_content,
            new_line=new_line,
            category='detection_quality',
            description='Add usable_for_validation filter to DetectionEvent query'
        )

    def find_timing_calls(self) -> List[Tuple[Path, int, str]]:
        """
        Find all start_video_timing calls that need degradation handling.

        Returns:
            List of (file_path, line_number, line_content) tuples
        """
        logger.info("Scanning for start_video_timing calls...")
        pattern = re.compile(r'start_video_timing\(')
        results = []

        for py_file in self.backend_dir.rglob('*.py'):
            if py_file.name == 'update_codebase.py':
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')

                    for line_num, line in enumerate(lines, 1):
                        if pattern.search(line):
                            # Check if already has try/except for VideoTimingError
                            # Look at surrounding context
                            context_start = max(0, line_num - 5)
                            context_end = min(len(lines), line_num + 5)
                            context = '\n'.join(lines[context_start:context_end])

                            if 'VideoTimingError' not in context:
                                results.append((py_file, line_num, line.rstrip()))

            except Exception as e:
                self.errors.append(f"Error reading {py_file}: {e}")
                self.stats['errors'] += 1

        logger.info(f"Found {len(results)} start_video_timing calls needing updates")
        return results

    def add_timing_error_handling(self, file_path: Path, line_number: int, line_content: str) -> List[FileChange]:
        """
        Generate changes to add VideoTimingError handling.

        Returns:
            List of FileChange objects (may need multiple lines)
        """
        changes = []

        # This is complex - needs to wrap entire block in try/except
        # For now, just flag it for manual review
        change = FileChange(
            file_path=file_path,
            line_number=line_number,
            old_line=line_content,
            new_line=f"# TODO: Add VideoTimingError exception handling here\n{line_content}",
            category='timing_error_handling',
            description='MANUAL REVIEW REQUIRED: Add try/except for VideoTimingError'
        )
        changes.append(change)

        return changes

    def find_session_local_usage(self) -> List[Tuple[Path, int, str]]:
        """
        Find all direct SessionLocal() instantiations.

        Returns:
            List of (file_path, line_number, line_content) tuples
        """
        logger.info("Scanning for SessionLocal() usage...")
        pattern = re.compile(r'SessionLocal\(\)')
        results = []

        for py_file in self.backend_dir.rglob('*.py'):
            if py_file.name == 'update_codebase.py':
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern.search(line):
                            # Check if already using context manager
                            if 'with managed_db_session' not in line:
                                results.append((py_file, line_num, line.rstrip()))

            except Exception as e:
                self.errors.append(f"Error reading {py_file}: {e}")
                self.stats['errors'] += 1

        logger.info(f"Found {len(results)} SessionLocal() usages needing updates")
        return results

    def convert_to_context_manager(self, file_path: Path, line_number: int, line_content: str) -> FileChange:
        """
        Generate change to convert SessionLocal() to context manager.

        Returns:
            FileChange object
        """
        # This is also complex - needs structural changes
        # Flag for manual review
        return FileChange(
            file_path=file_path,
            line_number=line_number,
            old_line=line_content,
            new_line=f"# TODO: Convert to 'with managed_db_session() as db:'\n{line_content}",
            category='connection_management',
            description='MANUAL REVIEW REQUIRED: Convert to context manager'
        )

    def apply_changes(self, changes: List[FileChange]) -> None:
        """
        Apply changes to files.

        Args:
            changes: List of FileChange objects to apply
        """
        if self.dry_run:
            logger.info("DRY RUN: Would make the following changes:")
            self.print_changes(changes)
            return

        # Group changes by file
        changes_by_file: Dict[Path, List[FileChange]] = {}
        for change in changes:
            if change.file_path not in changes_by_file:
                changes_by_file[change.file_path] = []
            changes_by_file[change.file_path].append(change)

        # Apply changes file by file
        for file_path, file_changes in changes_by_file.items():
            try:
                self.apply_file_changes(file_path, file_changes)
                self.stats['files_modified'] += 1
                self.stats['changes_made'] += len(file_changes)
            except Exception as e:
                self.errors.append(f"Error applying changes to {file_path}: {e}")
                self.stats['errors'] += 1

    def apply_file_changes(self, file_path: Path, changes: List[FileChange]) -> None:
        """
        Apply all changes to a single file.

        Args:
            file_path: Path to the file
            changes: List of changes to apply
        """
        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Sort changes by line number (descending to preserve line numbers)
        changes.sort(key=lambda c: c.line_number, reverse=True)

        # Apply each change
        for change in changes:
            line_idx = change.line_number - 1
            if line_idx < len(lines):
                lines[line_idx] = change.new_line + '\n'

        # Create backup
        backup_path = file_path.with_suffix(f'.py.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(''.join(lines))

        # Write modified file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        logger.info(f"Modified {file_path} ({len(changes)} changes)")

    def print_changes(self, changes: List[FileChange]) -> None:
        """
        Print changes in a readable format.

        Args:
            changes: List of FileChange objects
        """
        for change in changes:
            print(f"\n{'=' * 80}")
            print(f"File: {change.file_path}")
            print(f"Line: {change.line_number}")
            print(f"Category: {change.category}")
            print(f"Description: {change.description}")
            print(f"\nOld:")
            print(f"  {change.old_line}")
            print(f"New:")
            print(f"  {change.new_line}")

    def generate_report(self) -> str:
        """
        Generate a summary report of all changes.

        Returns:
            Report as string
        """
        report = f"""
Codebase Update Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Mode: {'DRY RUN' if self.dry_run else 'APPLIED'}

Statistics:
-----------
Files Scanned:    {self.stats['files_scanned']}
Files Modified:   {self.stats['files_modified']}
Changes Made:     {self.stats['changes_made']}
Errors:           {self.stats['errors']}

Changes by Category:
-------------------
"""

        # Count by category
        category_counts = {}
        for change in self.changes:
            category_counts[change.category] = category_counts.get(change.category, 0) + 1

        for category, count in sorted(category_counts.items()):
            report += f"  {category}: {count}\n"

        if self.errors:
            report += "\nErrors:\n-------\n"
            for error in self.errors:
                report += f"  - {error}\n"

        return report

    def run_category_detection_quality(self) -> None:
        """Update Category 1: DetectionEvent quality filtering"""
        logger.info("Running Category 1: DetectionEvent Quality Filtering")

        queries = self.find_detection_queries()

        for file_path, line_num, line_content in queries:
            change = self.add_quality_filter(file_path, line_num, line_content)
            self.changes.append(change)

        self.apply_changes(self.changes)

    def run_category_timing_degradation(self) -> None:
        """Update Category 2: Timing degradation handling"""
        logger.info("Running Category 2: Timing Degradation Handling")

        timing_calls = self.find_timing_calls()

        for file_path, line_num, line_content in timing_calls:
            changes = self.add_timing_error_handling(file_path, line_num, line_content)
            self.changes.extend(changes)

        self.apply_changes(self.changes)

    def run_category_connection_management(self) -> None:
        """Update Category 4: Database connection management"""
        logger.info("Running Category 4: Connection Management")

        session_usages = self.find_session_local_usage()

        for file_path, line_num, line_content in session_usages:
            change = self.convert_to_context_manager(file_path, line_num, line_content)
            self.changes.append(change)

        self.apply_changes(self.changes)

    def run_all_categories(self) -> None:
        """Run all update categories"""
        self.run_category_detection_quality()
        self.run_category_timing_degradation()
        self.run_category_connection_management()


def main():
    parser = argparse.ArgumentParser(description='Update codebase for quality tracking')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply changes to files'
    )
    parser.add_argument(
        '--category',
        choices=['detection', 'timing', 'connection', 'all'],
        default='all',
        help='Which category to update'
    )
    parser.add_argument(
        '--backend-dir',
        default='/home/rigade/Testing/ai-model-validation-platform/backend',
        help='Path to backend directory'
    )

    args = parser.parse_args()

    # Default to dry-run if neither specified
    if not args.dry_run and not args.apply:
        args.dry_run = True
        logger.info("No mode specified, defaulting to --dry-run")

    updater = CodebaseUpdater(args.backend_dir, dry_run=args.dry_run)

    try:
        if args.category == 'detection':
            updater.run_category_detection_quality()
        elif args.category == 'timing':
            updater.run_category_timing_degradation()
        elif args.category == 'connection':
            updater.run_category_connection_management()
        else:
            updater.run_all_categories()

        # Generate and print report
        report = updater.generate_report()
        print(report)

        # Save report to file
        report_path = Path(args.backend_dir) / 'docs' / f'update_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(report_path, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to {report_path}")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
