#!/usr/bin/env python3
"""
Comprehensive SQLAlchemy 2.0 syntax fix script.
Handles all edge cases and complex patterns.
"""

import re
from pathlib import Path


def fix_file(file_path):
    """Fix a single file with comprehensive pattern matching."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        original = content
        changes_made = []

        # 1. Add imports if needed
        if 'from sqlalchemy import' in content:
            import_match = re.search(r'from sqlalchemy import ([^\n]+)', content)
            if import_match:
                current_imports = import_match.group(1)
                needed = []
                if 'select' not in current_imports:
                    needed.append('select')
                if 'delete' not in current_imports:
                    needed.append('delete')
                if 'update' not in current_imports:
                    needed.append('update')
                if 'func' not in current_imports:
                    needed.append('func')

                if needed:
                    new_imports = current_imports.strip().rstrip(',') + ', ' + ', '.join(needed)
                    content = re.sub(
                        r'from sqlalchemy import ([^\n]+)',
                        f'from sqlalchemy import {new_imports}',
                        content
                    )
                    changes_made.append('Added imports')

        # 2. Fix patterns with variable names
        # db.query(Model).filter(...).all()
        pattern = r'(\w+)\.query\((\w+)\)\.filter\(([^)]+)\)\.all\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2).where(\3)).scalars().all()',
                content
            )
            changes_made.append('Fixed .query().filter().all()')

        # db.query(Model).filter(...).first()
        pattern = r'(\w+)\.query\((\w+)\)\.filter\(([^)]+)\)\.first\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2).where(\3)).scalar_one_or_none()',
                content
            )
            changes_made.append('Fixed .query().filter().first()')

        # db.query(Model).filter(...).count()
        pattern = r'(\w+)\.query\((\w+)\)\.filter\(([^)]+)\)\.count\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(func.count()).select_from(\2).where(\3)).scalar()',
                content
            )
            changes_made.append('Fixed .query().filter().count()')

        # db.query(Model).filter(...).delete()
        pattern = r'(\w+)\.query\((\w+)\)\.filter\(([^)]+)\)\.delete\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(delete(\2).where(\3))',
                content
            )
            changes_made.append('Fixed .query().filter().delete()')

        # db.query(Model).filter_by(...).all()
        pattern = r'(\w+)\.query\((\w+)\)\.filter_by\(([^)]+)\)\.all\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2).filter_by(\3)).scalars().all()',
                content
            )
            changes_made.append('Fixed .query().filter_by().all()')

        # db.query(Model).filter_by(...).first()
        pattern = r'(\w+)\.query\((\w+)\)\.filter_by\(([^)]+)\)\.first\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2).filter_by(\3)).scalar_one_or_none()',
                content
            )
            changes_made.append('Fixed .query().filter_by().first()')

        # db.query(Model).filter_by(...).count()
        pattern = r'(\w+)\.query\((\w+)\)\.filter_by\(([^)]+)\)\.count\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(func.count()).select_from(\2).filter_by(\3)).scalar()',
                content
            )
            changes_made.append('Fixed .query().filter_by().count()')

        # db.query(Model).all()
        pattern = r'(\w+)\.query\((\w+)\)\.all\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2)).scalars().all()',
                content
            )
            changes_made.append('Fixed .query().all()')

        # db.query(Model).first()
        pattern = r'(\w+)\.query\((\w+)\)\.first\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2)).scalar_one_or_none()',
                content
            )
            changes_made.append('Fixed .query().first()')

        # db.query(Model).count()
        pattern = r'(\w+)\.query\((\w+)\)\.count\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(func.count()).select_from(\2)).scalar()',
                content
            )
            changes_made.append('Fixed .query().count()')

        # db.query(Model).join(...).first()
        pattern = r'(\w+)\.query\((\w+)\)\.join\((\w+)\)\.first\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(\2).join(\3)).scalar_one_or_none()',
                content
            )
            changes_made.append('Fixed .query().join().first()')

        # db.query(Model).join(...).distinct().count()
        pattern = r'(\w+)\.query\((\w+)\)\.join\((\w+)\)\.distinct\(\)\.count\(\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                r'\1.execute(select(func.count(func.distinct(\2.id))).select_from(\2).join(\3)).scalar()',
                content
            )
            changes_made.append('Fixed .query().join().distinct().count()')

        # Write back if changed
        if content != original:
            with open(file_path, 'w') as f:
                f.write(content)
            return True, changes_made
        return False, []

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, []


def main():
    test_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend/tests")
    files = list(test_dir.rglob("*.py"))

    print(f"Processing {len(files)} files...")
    print("=" * 80)

    updated_files = []
    for file_path in files:
        changed, changes = fix_file(file_path)
        if changed:
            updated_files.append((file_path, changes))
            print(f"✓ {file_path.relative_to(test_dir)}")
            for change in changes:
                print(f"    - {change}")

    print("=" * 80)
    print(f"\nSummary:")
    print(f"  Total files: {len(files)}")
    print(f"  Updated: {len(updated_files)}")
    print(f"  Unchanged: {len(files) - len(updated_files)}")


if __name__ == "__main__":
    main()
