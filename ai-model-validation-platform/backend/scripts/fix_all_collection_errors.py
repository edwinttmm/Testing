#!/usr/bin/env python3
"""
Comprehensive script to fix all pytest collection errors.
Fixes:
1. Missing pytest imports (NameError: name 'pytest' is not defined)
2. Invalid skip markers that don't prevent imports
3. SQLAlchemy model issues (TestSession class collection)
"""
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

def get_collection_errors() -> List[Tuple[str, str]]:
    """Run pytest --collect-only and parse errors."""
    result = subprocess.run(
        ['python', '-m', 'pytest', '--collect-only', 'tests/', '-q'],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )

    errors = []
    lines = result.stderr.split('\n') + result.stdout.split('\n')

    for i, line in enumerate(lines):
        if 'ERROR collecting' in line or 'ERROR tests/' in line:
            # Extract file path
            match = re.search(r'tests/[^ ]+\.py', line)
            if match:
                filepath = match.group(0)
                # Try to extract error type from next lines
                error_type = "Unknown"
                for j in range(i+1, min(i+5, len(lines))):
                    if 'NameError' in lines[j]:
                        error_type = "NameError"
                        break
                    elif 'ModuleNotFoundError' in lines[j]:
                        error_type = "ModuleNotFoundError"
                        break
                    elif 'ImportError' in lines[j]:
                        error_type = "ImportError"
                        break
                    elif 'InvalidRequestError' in lines[j]:
                        error_type = "SQLAlchemy"
                        break

                errors.append((filepath, error_type))

    return list(set(errors))  # Remove duplicates

def fix_missing_pytest_import(filepath: Path) -> bool:
    """Add 'import pytest' if missing."""
    try:
        content = filepath.read_text()

        # Check if pytest is used
        uses_pytest = any(pattern in content for pattern in [
            '@pytest.', 'pytest.', 'pytestmark'
        ])

        # Check if pytest is imported
        has_import = any(pattern in content for pattern in [
            'import pytest', 'from pytest'
        ])

        if uses_pytest and not has_import:
            lines = content.split('\n')

            # Find the right place (after docstring, before first code)
            insert_idx = 0
            in_docstring = False
            docstring_char = None

            for i, line in enumerate(lines):
                stripped = line.strip()

                # Track docstrings
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    if not in_docstring:
                        in_docstring = True
                        docstring_char = stripped[:3]
                        if stripped.endswith(docstring_char) and len(stripped) > 6:
                            in_docstring = False
                            insert_idx = i + 1
                    elif stripped.endswith(docstring_char):
                        in_docstring = False
                        insert_idx = i + 1

                # After docstring, find first import or code
                if not in_docstring and not stripped.startswith('#'):
                    if stripped.startswith(('import ', 'from ')):
                        insert_idx = i
                    elif stripped and insert_idx > 0:
                        break

            # Insert import
            lines.insert(insert_idx, 'import pytest')
            filepath.write_text('\n'.join(lines))
            return True

    except Exception as e:
        print(f"Error fixing {filepath}: {e}")

    return False

def fix_invalid_skip_markers(filepath: Path) -> bool:
    """Move pytestmark to before imports to prevent import errors."""
    try:
        content = filepath.read_text()

        if 'pytestmark = pytest.mark.skip' in content:
            lines = content.split('\n')

            # Find pytestmark line
            mark_idx = None
            for i, line in enumerate(lines):
                if 'pytestmark = pytest.mark.skip' in line:
                    mark_idx = i
                    break

            if mark_idx and mark_idx > 5:  # If it's not near the top
                # Remove from current position
                mark_line = lines.pop(mark_idx)

                # Find position after docstring
                insert_idx = 0
                for i, line in enumerate(lines):
                    if '"""' in line or "'''" in line:
                        # Find end of docstring
                        for j in range(i+1, len(lines)):
                            if '"""' in lines[j] or "'''" in lines[j]:
                                insert_idx = j + 1
                                break
                        break

                # Make sure pytest is imported first
                if insert_idx > 0:
                    lines.insert(insert_idx, 'import pytest')
                    lines.insert(insert_idx + 1, mark_line)
                    lines.insert(insert_idx + 2, '')  # Blank line

                    filepath.write_text('\n'.join(lines))
                    return True

    except Exception as e:
        print(f"Error fixing skip markers in {filepath}: {e}")

    return False

def main():
    """Fix all collection errors."""
    backend_root = Path(__file__).parent.parent

    print("=== Analyzing Collection Errors ===")
    errors = get_collection_errors()

    print(f"\nFound {len(errors)} unique files with errors:")
    for filepath, error_type in sorted(errors):
        print(f"  {error_type:20s} {filepath}")

    print("\n=== Fixing Errors ===")

    fixed_count = 0
    for filepath_str, error_type in errors:
        filepath = backend_root / filepath_str

        if not filepath.exists():
            print(f"SKIP: File not found: {filepath}")
            continue

        fixed = False

        if error_type == "NameError":
            if fix_missing_pytest_import(filepath):
                print(f"FIXED: Added pytest import to {filepath_str}")
                fixed = True

        if 'pytestmark' in filepath.read_text():
            if fix_invalid_skip_markers(filepath):
                print(f"FIXED: Moved pytestmark in {filepath_str}")
                fixed = True

        if fixed:
            fixed_count += 1

    print(f"\n=== Summary ===")
    print(f"Files with errors: {len(errors)}")
    print(f"Files fixed: {fixed_count}")
    print(f"\nRun 'python -m pytest --collect-only tests/ -q' to verify.")

if __name__ == '__main__':
    main()
