#!/usr/bin/env python3
"""
Script to automatically fix missing type imports in test files.
Analyzes usage and adds appropriate typing imports.
"""

import os
import re
from pathlib import Path
from typing import Set, List, Tuple


def analyze_type_usage(content: str) -> Set[str]:
    """Analyze which typing types are used in the content."""
    needs = set()

    # Check for specific type usage patterns
    type_patterns = {
        'Any': r'\bAny\b',
        'Optional': r'\bOptional\[',
        'List': r'\bList\[',
        'Dict': r'\bDict\[',
        'Tuple': r'\bTuple\[',
        'Callable': r'\bCallable\[',
        'Union': r'\bUnion\[',
        'Type': r'\bType\[',
        'Set': r'\bSet\[',
        'Sequence': r'\bSequence\[',
        'Iterable': r'\bIterable\[',
        'AsyncIterator': r'\bAsyncIterator\[',
        'Awaitable': r'\bAwaitable\[',
    }

    for type_name, pattern in type_patterns.items():
        if re.search(pattern, content):
            needs.add(type_name)

    return needs


def get_current_typing_imports(content: str) -> Set[str]:
    """Extract currently imported typing types."""
    imported = set()

    # Match: from typing import X, Y, Z
    pattern = r'from\s+typing\s+import\s+([^\n]+)'
    matches = re.findall(pattern, content)

    for match in matches:
        # Split by comma and clean
        types = [t.strip().split()[0] for t in match.split(',')]
        imported.update(types)

    return imported


def check_other_imports(content: str) -> Tuple[bool, bool]:
    """Check if sys and os imports are needed but missing."""
    needs_sys = 'sys.' in content or 'sys.path' in content
    needs_os = 'os.' in content or 'os.path' in content

    has_sys = re.search(r'^import sys', content, re.MULTILINE) is not None
    has_os = re.search(r'^import os', content, re.MULTILINE) is not None

    return (needs_sys and not has_sys, needs_os and not has_os)


def find_insert_position(lines: List[str]) -> int:
    """Find the best position to insert imports (after module docstring, before other imports)."""
    in_docstring = False
    docstring_char = None
    insert_pos = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Start of module docstring
        if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
            docstring_char = '"""' if stripped.startswith('"""') else "'''"
            in_docstring = True
            # Check if it's a single-line docstring
            if stripped.count(docstring_char) >= 2:
                in_docstring = False
                insert_pos = i + 1
            continue

        # End of module docstring
        if in_docstring and docstring_char in stripped:
            in_docstring = False
            insert_pos = i + 1
            continue

        # Found an import line (not in docstring)
        if not in_docstring and (stripped.startswith('import ') or stripped.startswith('from ')):
            return i

        # Found actual code (not comment, not empty)
        if not in_docstring and stripped and not stripped.startswith('#'):
            return insert_pos if insert_pos > 0 else i

    return insert_pos


def fix_file_imports(filepath: Path) -> Tuple[bool, List[str]]:
    """Fix imports in a single file. Returns (modified, changes)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    changes = []
    modified = False

    # Analyze what's needed
    needed_types = analyze_type_usage(content)
    current_types = get_current_typing_imports(content)
    missing_types = needed_types - current_types

    needs_sys, needs_os = check_other_imports(content)

    if not missing_types and not needs_sys and not needs_os:
        return False, []

    # Find insertion point
    insert_pos = find_insert_position(lines)

    # Build new import lines
    new_imports = []

    if needs_sys:
        new_imports.append('import sys')
        changes.append('Added: import sys')
        modified = True

    if needs_os:
        new_imports.append('import os')
        changes.append('Added: import os')
        modified = True

    if missing_types:
        sorted_types = sorted(missing_types)
        import_line = f"from typing import {', '.join(sorted_types)}"
        new_imports.append(import_line)
        changes.append(f'Added: {import_line}')
        modified = True

    if modified:
        # Insert new imports
        for imp in reversed(new_imports):
            lines.insert(insert_pos, imp)

        # Write back
        new_content = '\n'.join(lines)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return modified, changes


def main():
    """Main execution function."""
    backend_dir = Path('/home/rigade/Testing/ai-model-validation-platform/backend')
    tests_dir = backend_dir / 'tests'

    if not tests_dir.exists():
        print(f"❌ Tests directory not found: {tests_dir}")
        return

    # Find all Python test files
    test_files = list(tests_dir.rglob('*.py'))

    print(f"🔍 Found {len(test_files)} test files")
    print("=" * 60)

    fixed_count = 0
    total_changes = 0

    for filepath in sorted(test_files):
        relative_path = filepath.relative_to(backend_dir)
        modified, changes = fix_file_imports(filepath)

        if modified:
            fixed_count += 1
            total_changes += len(changes)
            print(f"\n✅ Fixed: {relative_path}")
            for change in changes:
                print(f"   {change}")

    print("\n" + "=" * 60)
    print(f"📊 SUMMARY:")
    print(f"   Total test files: {len(test_files)}")
    print(f"   Files modified: {fixed_count}")
    print(f"   Total changes: {total_changes}")
    print("=" * 60)


if __name__ == '__main__':
    main()
