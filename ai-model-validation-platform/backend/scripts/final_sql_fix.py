#!/usr/bin/env python3
"""
Final SQLAlchemy fix for multi-line queries and complex patterns.
"""

import re
from pathlib import Path


def fix_multiline_queries(file_path):
    """Fix multi-line query patterns."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        original = content

        # Fix multiline .query().filter() patterns
        content = re.sub(
            r'(\w+)\.query\(([\w]+)\)\.filter\(\s*\n\s*([\w\s.=<>!()]+)\s*\n\s*\)',
            r'\1.execute(select(\2).where(\n            \3\n        )).scalars()',
            content,
            flags=re.MULTILINE
        )

        # Fix .query().delete() patterns
        content = re.sub(
            r'(\w+)\.query\(([\w]+)\)\.delete\(\)',
            r'\1.execute(delete(\2))',
            content
        )

        # Fix .query().filter().with_for_update().first()
        content = re.sub(
            r'(\w+)\.query\(([\w]+)\)\.filter\(([\w\s.=<>!]+)\)\.with_for_update\(\)\.first\(\)',
            r'\1.execute(select(\2).where(\3).with_for_update()).scalar_one_or_none()',
            content
        )

        # Fix .query().limit().all()
        content = re.sub(
            r'(\w+)\.query\(([\w]+)\)\.limit\((\d+)\)\.all\(\)',
            r'\1.execute(select(\2).limit(\3)).scalars().all()',
            content
        )

        # Fix .query().filter().count() with is_(None)
        content = re.sub(
            r'(\w+)\.query\(([\w]+)\)\.filter\(([\w.]+)\.is_\(None\)\)\.count\(\)',
            r'\1.execute(select(func.count()).select_from(\2).where(\3.is_(None))).scalar()',
            content
        )

        # Fix query with multiline filter for average
        content = re.sub(
            r'(\w+)\.query\(\s*\n\s*func\.(avg|sum|count|min|max)\(([\w.]+)\)',
            r'\1.execute(select(\n            func.\2(\3)',
            content,
            flags=re.MULTILINE
        )

        if content != original:
            with open(file_path, 'w') as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    test_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend/tests")

    # Get files with remaining issues
    import subprocess
    result = subprocess.run(
        ['grep', '-rl', r'\.query(', str(test_dir), '--include=*.py'],
        capture_output=True,
        text=True
    )

    files = [Path(f) for f in result.stdout.strip().split('\n') if f]
    print(f"Fixing {len(files)} files with remaining issues...")
    print("=" * 80)

    updated = 0
    for file_path in files:
        if 'mock' in str(file_path) or '__pycache__' in str(file_path):
            continue

        if fix_multiline_queries(file_path):
            print(f"✓ {file_path.relative_to(test_dir)}")
            updated += 1

    print("=" * 80)
    print(f"Updated: {updated} files")


if __name__ == "__main__":
    main()
