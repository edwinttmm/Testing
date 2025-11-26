#!/usr/bin/env python3
"""
Automated fix for missing pytest imports in test files.

This script adds 'import pytest' to test files that use pytest decorators
or markers but don't have the import statement.
"""

import re
from pathlib import Path
from typing import List

# List of affected files from CRITICAL_TEST_FAILURES.md
AFFECTED_FILES = [
    "tests/services/test_callback_memory_leak.py",
    "tests/services/test_clock_sync_service.py",
    "tests/services/test_drift_integration.py",
    "tests/services/test_drift_measurement_service.py",
    "tests/services/test_timestamp_compensation_service.py",
    "tests/integration/test_end_to_end_timing_fixes.py",
    "tests/integration/test_video_lifecycle_e2e.py",
    "tests/unit/test_drift_measurement_service.py",
    "tests/hil-detection-pipeline/test_labjack_connection.py",
    "tests/hil-detection-pipeline/test_stream_mode_integration.py",
    "tests/hil-detection-pipeline/test_websocket_events.py",
    "tests/hil_labjack/test_monitoring_service_isolation.py",
    "tests/hil_labjack/test_realtime_monitoring.py",
    "tests/hil_labjack/test_session_integration.py",
    "tests/deprecated/test_integration_production_fixes.py",
    "tests/deprecated/test_latency_validation_service.py",
    "tests/test_performance_benchmarks.py",
    "tests/test_performance_compatibility.py",
    "tests/test_phase4_solves_all_issues.py",
    "tests/test_session_completion_logic.py",
    "tests/test_timing_fixes_integration.py",
    "tests/test_timing_integration.py",
    "tests/test_unified_latency_field.py",
    "tests/test_validation_engine.py",
    "tests/test_video_sequence_orchestrator.py",
]


def needs_pytest_import(content: str) -> bool:
    """Check if file uses pytest but doesn't import it."""
    uses_pytest = bool(
        re.search(r'@pytest\.(fixture|mark)', content) or
        re.search(r'pytest\.', content)
    )
    has_import = bool(
        re.search(r'^import pytest', content, re.MULTILINE) or
        re.search(r'^from pytest import', content, re.MULTILINE)
    )
    return uses_pytest and not has_import


def add_pytest_import(content: str) -> str:
    """Add 'import pytest' to file content."""
    lines = content.split('\n')
    insert_pos = 0
    in_docstring = False
    docstring_quote = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
            docstring_quote = '"""' if stripped.startswith('"""') else "'''"
            if stripped.endswith(docstring_quote) and len(stripped) > 3:
                insert_pos = i + 1
            else:
                in_docstring = True
        elif in_docstring and docstring_quote in line:
            in_docstring = False
            insert_pos = i + 1
        elif not in_docstring and stripped and not stripped.startswith('#'):
            if not stripped.startswith('import') and not stripped.startswith('from'):
                break
            elif stripped.startswith('import') or stripped.startswith('from'):
                insert_pos = i + 1

    lines.insert(insert_pos, 'import pytest')
    return '\n'.join(lines)


def fix_file(file_path: Path) -> bool:
    """Fix a single file by adding missing pytest import."""
    try:
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            return False

        content = file_path.read_text()

        if not needs_pytest_import(content):
            print(f"✓ {file_path.name} - Already has pytest import or doesn't need it")
            return False

        fixed_content = add_pytest_import(content)
        file_path.write_text(fixed_content)
        print(f"✅ {file_path.name} - Added 'import pytest'")
        return True

    except Exception as e:
        print(f"❌ {file_path.name} - Error: {e}")
        return False


def main():
    """Main function to fix all affected files."""
    backend_root = Path(__file__).parent.parent
    print(f"Backend root: {backend_root}")
    print(f"Fixing {len(AFFECTED_FILES)} files...\n")

    fixed_count = 0
    skipped_count = 0
    error_count = 0

    for file_rel_path in AFFECTED_FILES:
        file_path = backend_root / file_rel_path
        result = fix_file(file_path)
        if result is True:
            fixed_count += 1
        elif result is False:
            if file_path.exists():
                skipped_count += 1
            else:
                error_count += 1

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  ✅ Fixed: {fixed_count} files")
    print(f"  ⏭️  Skipped: {skipped_count} files (already have import)")
    print(f"  ❌ Errors: {error_count} files (not found or other error)")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
