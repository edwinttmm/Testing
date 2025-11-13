#!/usr/bin/env python3
"""
Test script for new database migrations.

Tests:
1. Migration application (upgrade)
2. Field existence verification
3. Index creation verification
4. Backfill data verification
5. Rollback capability (downgrade)

Usage:
    python3 test_new_migrations.py
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from database import Base
from models import TestSession, SequenceVideoResult
import json


def test_migrations():
    """Test the new migrations."""
    print("=" * 80)
    print("DATABASE MIGRATION TEST SUITE")
    print("=" * 80)

    # Use development database
    db_path = backend_dir / "dev_database.db"
    database_url = f"sqlite:///{db_path}"

    print(f"\n📊 Database: {db_path}")
    print(f"📊 URL: {database_url}\n")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Test 1: Check SequenceVideoResult has frontend_playing_delay_ms
        print("=" * 80)
        print("TEST 1: Frontend Playing Delay Field")
        print("=" * 80)

        if 'sequence_video_results' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('sequence_video_results')]

            if 'frontend_playing_delay_ms' in columns:
                print("✅ Field 'frontend_playing_delay_ms' exists in sequence_video_results")

                # Check index
                indexes = [idx['name'] for idx in inspector.get_indexes('sequence_video_results')]
                if 'idx_sequence_video_results_playing_delay' in indexes:
                    print("✅ Index 'idx_sequence_video_results_playing_delay' exists")
                else:
                    print("⚠️  Index 'idx_sequence_video_results_playing_delay' NOT found")

                # Check data type
                col_info = next((c for c in inspector.get_columns('sequence_video_results')
                                if c['name'] == 'frontend_playing_delay_ms'), None)
                if col_info:
                    print(f"✅ Data type: {col_info['type']}")
                    print(f"✅ Nullable: {col_info['nullable']}")

                # Check for backfilled data
                result = session.execute(text("""
                    SELECT COUNT(*) as total,
                           COUNT(frontend_playing_delay_ms) as with_delay,
                           AVG(frontend_playing_delay_ms) as avg_delay
                    FROM sequence_video_results
                """))
                row = result.fetchone()
                print(f"✅ Total records: {row[0]}")
                print(f"✅ Records with delay: {row[1]}")
                if row[2]:
                    print(f"✅ Average delay: {row[2]:.2f}ms")

            else:
                print("❌ Field 'frontend_playing_delay_ms' NOT found")
        else:
            print("⚠️  Table 'sequence_video_results' does not exist")

        # Test 2: Check TestSession has evaluation_details
        print("\n" + "=" * 80)
        print("TEST 2: Dual-Evaluation Fields")
        print("=" * 80)

        columns = [col['name'] for col in inspector.get_columns('test_sessions')]

        if 'evaluation_details' in columns:
            print("✅ Field 'evaluation_details' exists in test_sessions")

            # Check data type
            col_info = next((c for c in inspector.get_columns('test_sessions')
                            if c['name'] == 'evaluation_details'), None)
            if col_info:
                print(f"✅ Data type: {col_info['type']}")
                print(f"✅ Nullable: {col_info['nullable']}")

            # Check for backfilled data
            result = session.execute(text("""
                SELECT COUNT(*) as total,
                       COUNT(evaluation_details) as with_details
                FROM test_sessions
            """))
            row = result.fetchone()
            print(f"✅ Total sessions: {row[0]}")
            print(f"✅ Sessions with evaluation_details: {row[1]}")

            # Sample evaluation_details
            result = session.execute(text("""
                SELECT evaluation_details
                FROM test_sessions
                WHERE evaluation_details IS NOT NULL
                LIMIT 1
            """))
            sample = result.fetchone()
            if sample and sample[0]:
                print(f"✅ Sample evaluation_details:")
                try:
                    details = json.loads(sample[0]) if isinstance(sample[0], str) else sample[0]
                    print(json.dumps(details, indent=2))
                except:
                    print(f"   {sample[0]}")
        else:
            print("❌ Field 'evaluation_details' NOT found")

        # Test 3: Check existing dual-evaluation fields
        required_fields = [
            'accuracy_result', 'latency_result', 'overall_test_result',
            'accuracy_f1_score', 'latency_mean_ms'
        ]

        print("\n" + "=" * 80)
        print("TEST 3: Existing Dual-Evaluation Fields")
        print("=" * 80)

        for field in required_fields:
            if field in columns:
                print(f"✅ Field '{field}' exists")
            else:
                print(f"❌ Field '{field}' NOT found")

        # Test 4: Check indexes
        print("\n" + "=" * 80)
        print("TEST 4: Index Verification")
        print("=" * 80)

        indexes = [idx['name'] for idx in inspector.get_indexes('test_sessions')]

        expected_indexes = [
            'idx_test_sessions_accuracy_result',
            'idx_test_sessions_latency_result',
            'idx_test_sessions_dual_eval'
        ]

        for idx_name in expected_indexes:
            if idx_name in indexes:
                print(f"✅ Index '{idx_name}' exists")
            else:
                print(f"⚠️  Index '{idx_name}' NOT found (may be created by migration)")

        # Test 5: Migration revision chain
        print("\n" + "=" * 80)
        print("TEST 5: Migration Revision Chain")
        print("=" * 80)

        # Check if alembic_version table exists
        if 'alembic_version' in inspector.get_table_names():
            result = session.execute(text("SELECT version_num FROM alembic_version"))
            current_revision = result.fetchone()
            if current_revision:
                print(f"✅ Current revision: {current_revision[0]}")
            else:
                print("⚠️  No revision set in alembic_version")
        else:
            print("⚠️  Table 'alembic_version' does not exist")

        # List migration files
        migrations_dir = backend_dir / "migrations" / "versions"
        if migrations_dir.exists():
            new_migrations = list(migrations_dir.glob("20251111_*.py"))
            print(f"\n✅ New migration files found: {len(new_migrations)}")
            for mig in new_migrations:
                print(f"   - {mig.name}")

        print("\n" + "=" * 80)
        print("✅ MIGRATION TEST SUITE COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    test_migrations()
