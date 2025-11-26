#!/usr/bin/env python3
"""
Manual fixes for SQLAlchemy syntax issues that require more sophisticated replacements.
"""

import re
from pathlib import Path


def fix_test_database_integration():
    """Fix test_database_integration.py specifically."""
    file_path = Path("/home/rigade/Testing/ai-model-validation-platform/backend/tests/test_database_integration.py")

    with open(file_path, 'r') as f:
        content = f.read()

    # Fix lines where 'session' was used instead of 'db_session'
    content = content.replace(
        'assert session.execute(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.test_session_id == test_session.id)).scalar() == 3',
        'assert db_session.execute(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.test_session_id == test_session.id)).scalar() == 3'
    )

    content = content.replace(
        'assert session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar() == 2',
        'assert db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar() == 2'
    )

    content = content.replace(
        'assert session.execute(select(func.count()).select_from(Video).where(Video.project_id == test_project.id)).scalar() == 0',
        'assert db_session.execute(select(func.count()).select_from(Video).where(Video.project_id == test_project.id)).scalar() == 0'
    )

    content = content.replace(
        'assert session.execute(select(func.count()).select_from(TestSession).where(TestSession.project_id == test_project.id)).scalar() == 0',
        'assert db_session.execute(select(func.count()).select_from(TestSession).where(TestSession.project_id == test_project.id)).scalar() == 0'
    )

    content = content.replace(
        'assert session.execute(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.test_session_id == test_session.id)).scalar() == 0',
        'assert db_session.execute(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.test_session_id == test_session.id)).scalar() == 0'
    )

    content = content.replace(
        'assert session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar() == 0',
        'assert db_session.execute(select(func.count()).select_from(GroundTruthObject).where(GroundTruthObject.video_id == test_video.id)).scalar() == 0'
    )

    # Fix more complex patterns
    content = re.sub(
        r'lambda: session\.execute\(select\(func\.count\(\)\)\.select_from\(GroundTruthObject\)\.where\((.*?)\)\)\.scalar\(\)',
        r'lambda: db_session.execute(select(func.count()).select_from(GroundTruthObject).where(\1)).scalar()',
        content
    )

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"✓ Fixed: {file_path}")


def fix_remaining_query_patterns():
    """Fix remaining patterns across all test files."""
    test_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend/tests")

    for file_path in test_dir.rglob("*.py"):
        try:
            with open(file_path, 'r') as f:
                content = f.read()

            original = content

            # Fix .like() patterns
            content = re.sub(
                r'\.query\(([\w]+)\)\.filter\(([\w.]+)\.like\((.*?)\)\)',
                r'.execute(select(\1).where(\2.like(\3))).scalars()',
                content
            )

            # Fix count() for TestSession
            content = re.sub(
                r'(\w+)_count = session\.execute\(select\(func\.count\(\)\)\.select_from\(TestSession\)\)\.scalar\(\)',
                r'\1_count = db_session.execute(select(func.count()).select_from(TestSession)).scalar()',
                content
            )

            content = re.sub(
                r'(\w+)_count = session\.execute\(select\(func\.count\(\)\)\.select_from\(GroundTruthObject\)\)\.scalar\(\)',
                r'\1_count = db_session.execute(select(func.count()).select_from(GroundTruthObject)).scalar()',
                content
            )

            if content != original:
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"✓ Fixed additional patterns: {file_path}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")


def main():
    print("Applying manual SQLAlchemy fixes...")
    print("=" * 60)

    fix_test_database_integration()
    fix_remaining_query_patterns()

    print("=" * 60)
    print("Manual fixes complete!")


if __name__ == "__main__":
    main()
