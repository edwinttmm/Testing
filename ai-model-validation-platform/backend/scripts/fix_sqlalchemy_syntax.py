#!/usr/bin/env python3
"""
Script to fix SQLAlchemy 1.x query syntax to SQLAlchemy 2.0 syntax in test files.

This script performs the following transformations:
1. Adds missing imports (select, delete, update, func)
2. Converts session.query(Model) to select(Model)
3. Wraps with session.execute()
4. Updates result retrieval methods
"""

import re
import os
from pathlib import Path


def add_sqlalchemy_imports(content):
    """Add required SQLAlchemy 2.0 imports if missing."""

    # Check if sqlalchemy is already imported
    if 'from sqlalchemy import' in content:
        # Find the import line
        import_pattern = r'from sqlalchemy import ([^\n]+)'
        match = re.search(import_pattern, content)

        if match:
            current_imports = match.group(1)

            # Check what's missing
            needed_imports = []
            if 'select' not in current_imports:
                needed_imports.append('select')
            if 'delete' not in current_imports:
                needed_imports.append('delete')
            if 'update' not in current_imports:
                needed_imports.append('update')
            if 'func' not in current_imports:
                needed_imports.append('func')

            if needed_imports:
                # Add missing imports
                new_imports = current_imports.strip()
                for imp in needed_imports:
                    if not new_imports.endswith(','):
                        new_imports += ','
                    new_imports += f' {imp},'

                new_imports = new_imports.rstrip(',')
                content = re.sub(import_pattern, f'from sqlalchemy import {new_imports}', content)

    return content


def fix_query_syntax(content):
    """Convert old query syntax to new select syntax."""

    # Pattern 1: session.query(Model).filter(...).count()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.filter\(([\w\s.==<>!]+)\)\.count\(\)',
        r'session.execute(select(func.count()).select_from(\2).where(\3)).scalar()',
        content
    )

    # Pattern 2: session.query(Model).filter(...).first()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.filter\(([\w\s.==<>!]+)\)\.first\(\)',
        r'\1.execute(select(\2).where(\3)).scalar_one_or_none()',
        content
    )

    # Pattern 3: session.query(Model).filter(...).all()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.filter\(([\w\s.==<>!]+)\)\.all\(\)',
        r'\1.execute(select(\2).where(\3)).scalars().all()',
        content
    )

    # Pattern 4: session.query(Model).filter_by(...).count()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.filter_by\(([\w\s=,]+)\)\.count\(\)',
        r'\1.execute(select(func.count()).select_from(\2).filter_by(\3)).scalar()',
        content
    )

    # Pattern 5: session.query(Model).filter_by(...).first()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.filter_by\(([\w\s=,]+)\)\.first\(\)',
        r'\1.execute(select(\2).filter_by(\3)).scalar_one_or_none()',
        content
    )

    # Pattern 6: session.query(Model).filter_by(...).all()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.filter_by\(([\w\s=,]+)\)\.all\(\)',
        r'\1.execute(select(\2).filter_by(\3)).scalars().all()',
        content
    )

    # Pattern 7: session.query(Model).count()
    content = re.sub(
        r'(\w+)\.query\((\w+)\)\.count\(\)',
        r'\1.execute(select(func.count()).select_from(\2)).scalar()',
        content
    )

    return content


def process_file(file_path):
    """Process a single test file."""
    print(f"Processing: {file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content

    # Add imports
    content = add_sqlalchemy_imports(content)

    # Fix query syntax
    content = fix_query_syntax(content)

    # Write back if changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✓ Updated: {file_path}")
        return True
    else:
        print(f"  - No changes: {file_path}")
        return False


def main():
    """Main function to process all test files."""
    test_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend/tests")

    test_files = list(test_dir.rglob("*.py"))

    print(f"Found {len(test_files)} test files")
    print("=" * 60)

    updated_count = 0
    for test_file in test_files:
        if process_file(test_file):
            updated_count += 1

    print("=" * 60)
    print(f"\nSummary:")
    print(f"  Total files: {len(test_files)}")
    print(f"  Updated: {updated_count}")
    print(f"  Unchanged: {len(test_files) - updated_count}")


if __name__ == "__main__":
    main()
