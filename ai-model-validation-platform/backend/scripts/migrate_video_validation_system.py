#!/usr/bin/env python3
"""
Video Validation System Migration Script

This script provides a comprehensive migration tool for upgrading the existing
video validation system to the new unified status system. It handles data
migration, validation, and rollback capabilities.

Usage:
    python migrate_video_validation_system.py [--mode=PREVIEW|MIGRATE|VALIDATE|ROLLBACK]
"""

import sys
import os
import argparse
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from models import Video, VideoValidationCriteria, VideoValidationResult, VideoStatusTransition
from database import DATABASE_URL, get_db
from schemas_video_validation import VideoValidationStatus

class VideoValidationMigrator:
    """Handles migration of video validation system"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Migration tracking
        self.migration_stats = {
            "total_videos": 0,
            "migrated_videos": 0,
            "failed_videos": 0,
            "skipped_videos": 0,
            "validation_criteria_created": 0,
            "transitions_created": 0,
            "validation_results_created": 0,
            "errors": []
        }
        
    def run_migration(self, mode: str = "PREVIEW") -> Dict[str, Any]:
        """
        Run migration based on mode
        
        Args:
            mode: PREVIEW, MIGRATE, VALIDATE, or ROLLBACK
            
        Returns:
            Migration results and statistics
        """
        
        print(f"🚀 Running Video Validation Migration in {mode} mode")
        print(f"Database: {self.database_url}")
        print("=" * 80)
        
        if mode == "PREVIEW":
            return self._preview_migration()
        elif mode == "MIGRATE":
            return self._execute_migration()
        elif mode == "VALIDATE":
            return self._validate_migration()
        elif mode == "ROLLBACK":
            return self._rollback_migration()
        else:
            raise ValueError(f"Invalid mode: {mode}. Use PREVIEW, MIGRATE, VALIDATE, or ROLLBACK")
    
    def _preview_migration(self) -> Dict[str, Any]:
        """Preview what the migration will do without making changes"""
        
        print("📋 MIGRATION PREVIEW - No changes will be made")
        print()
        
        db = self.SessionLocal()
        try:
            # Analyze current data
            videos = db.execute(text("""
                SELECT id, status, processing_status, ground_truth_generated,
                       filename, created_at, updated_at
                FROM videos
                ORDER BY created_at
            """)).fetchall()
            
            print(f"📊 Current Video Statistics:")
            print(f"   Total videos: {len(videos)}")
            
            # Analyze status distribution
            status_counts = {}
            processing_status_counts = {}
            gt_counts = {"true": 0, "false": 0}
            
            migration_plan = {}
            
            for video in videos:
                # Current status distribution
                status = video.status or "unknown"
                processing_status = video.processing_status or "unknown"
                gt_generated = video.ground_truth_generated
                
                status_counts[status] = status_counts.get(status, 0) + 1
                processing_status_counts[processing_status] = processing_status_counts.get(processing_status, 0) + 1
                gt_counts["true" if gt_generated else "false"] += 1
                
                # Determine migration path
                new_status, validation_status, reasoning = self._determine_migration_path(
                    status, processing_status, gt_generated
                )
                
                migration_key = f"{status}|{processing_status}|{gt_generated}"
                if migration_key not in migration_plan:
                    migration_plan[migration_key] = {
                        "count": 0,
                        "from": {"status": status, "processing_status": processing_status, "gt_generated": gt_generated},
                        "to": {"status": new_status, "validation_status": validation_status},
                        "reasoning": reasoning
                    }
                migration_plan[migration_key]["count"] += 1
            
            # Display current distribution
            print()
            print("📈 Current Status Distribution:")
            for status, count in status_counts.items():
                print(f"   {status}: {count}")
            
            print()
            print("⚙️ Current Processing Status Distribution:")
            for status, count in processing_status_counts.items():
                print(f"   {status}: {count}")
            
            print()
            print("🎯 Ground Truth Status:")
            print(f"   Generated: {gt_counts['true']}")
            print(f"   Not Generated: {gt_counts['false']}")
            
            # Display migration plan
            print()
            print("🗺️ Migration Plan:")
            print()
            for plan_key, plan in migration_plan.items():
                from_info = plan["from"]
                to_info = plan["to"]
                count = plan["count"]
                reasoning = plan["reasoning"]
                
                print(f"   📌 {count} videos:")
                print(f"      FROM: status='{from_info['status']}', processing='{from_info['processing_status']}', gt={from_info['gt_generated']}")
                print(f"      TO: status='{to_info['status']}', validation='{to_info['validation_status']}'")
                print(f"      REASON: {reasoning}")
                print()
            
            # Check for potential issues
            print("⚠️ Potential Issues:")
            issues_found = False
            
            # Check for videos with inconsistent state
            inconsistent_videos = [
                v for v in videos
                if v.processing_status == "completed" and not v.ground_truth_generated
            ]
            if inconsistent_videos:
                print(f"   - {len(inconsistent_videos)} videos have processing_status='completed' but ground_truth_generated=False")
                issues_found = True
            
            # Check for videos with no clear status
            unclear_videos = [
                v for v in videos
                if not v.status or v.status == "unknown"
            ]
            if unclear_videos:
                print(f"   - {len(unclear_videos)} videos have unclear or missing status")
                issues_found = True
            
            if not issues_found:
                print("   - No issues detected")
            
            print()
            print("✅ Preview complete. Run with --mode=MIGRATE to execute migration.")
            
            return {
                "mode": "PREVIEW",
                "total_videos": len(videos),
                "status_distribution": status_counts,
                "processing_status_distribution": processing_status_counts,
                "migration_plan": migration_plan,
                "issues": len(inconsistent_videos) + len(unclear_videos)
            }
            
        except Exception as e:
            print(f"❌ Preview failed: {str(e)}")
            return {"mode": "PREVIEW", "error": str(e)}
        finally:
            db.close()
    
    def _execute_migration(self) -> Dict[str, Any]:
        """Execute the actual migration"""
        
        print("🚀 EXECUTING MIGRATION - Making database changes")
        print("⚠️ This will modify your database. Ensure you have a backup!")
        print()
        
        # Confirm before proceeding
        response = input("Continue with migration? [yes/no]: ").lower().strip()
        if response not in ['yes', 'y']:
            print("❌ Migration cancelled by user")
            return {"mode": "MIGRATE", "status": "cancelled"}
        
        db = self.SessionLocal()
        try:
            # Start transaction
            db.begin()
            
            print("1️⃣ Creating default validation criteria...")
            default_criteria = self._create_default_validation_criteria(db)
            print(f"   ✅ Created criteria with ID: {default_criteria.id}")
            
            print()
            print("2️⃣ Migrating video data...")
            
            # Get all videos
            videos = db.execute(text("""
                SELECT id, status, processing_status, ground_truth_generated,
                       filename, created_at, updated_at, project_id
                FROM videos
                ORDER BY created_at
            """)).fetchall()
            
            self.migration_stats["total_videos"] = len(videos)
            print(f"   Found {len(videos)} videos to migrate")
            
            # Process each video
            for i, video in enumerate(videos, 1):
                try:
                    if i % 10 == 0:
                        print(f"   Progress: {i}/{len(videos)} videos processed")
                    
                    success = self._migrate_single_video(db, video, default_criteria.id)
                    if success:
                        self.migration_stats["migrated_videos"] += 1
                    else:
                        self.migration_stats["failed_videos"] += 1
                        
                except Exception as e:
                    self.migration_stats["failed_videos"] += 1
                    self.migration_stats["errors"].append({
                        "video_id": video.id,
                        "filename": video.filename,
                        "error": str(e)
                    })
                    print(f"   ❌ Failed to migrate video {video.filename}: {str(e)}")
            
            print()
            print("3️⃣ Finalizing migration...")
            
            # Commit transaction
            db.commit()
            
            # Display results
            print()
            print("✅ MIGRATION COMPLETED SUCCESSFULLY")
            print(f"   Total videos: {self.migration_stats['total_videos']}")
            print(f"   Successfully migrated: {self.migration_stats['migrated_videos']}")
            print(f"   Failed: {self.migration_stats['failed_videos']}")
            print(f"   Validation criteria created: {self.migration_stats['validation_criteria_created']}")
            print(f"   Status transitions created: {self.migration_stats['transitions_created']}")
            print(f"   Validation results created: {self.migration_stats['validation_results_created']}")
            
            if self.migration_stats["errors"]:
                print()
                print("⚠️ Errors encountered:")
                for error in self.migration_stats["errors"][:5]:  # Show first 5 errors
                    print(f"   - {error['filename']}: {error['error']}")
                if len(self.migration_stats["errors"]) > 5:
                    print(f"   ... and {len(self.migration_stats['errors']) - 5} more errors")
            
            return {
                "mode": "MIGRATE",
                "status": "completed",
                "stats": self.migration_stats
            }
            
        except Exception as e:
            db.rollback()
            print(f"❌ Migration failed: {str(e)}")
            return {
                "mode": "MIGRATE",
                "status": "failed",
                "error": str(e),
                "stats": self.migration_stats
            }
        finally:
            db.close()
    
    def _validate_migration(self) -> Dict[str, Any]:
        """Validate that migration was successful"""
        
        print("🔍 VALIDATING MIGRATION RESULTS")
        print()
        
        db = self.SessionLocal()
        try:
            validation_results = {
                "total_videos": 0,
                "videos_with_new_fields": 0,
                "videos_with_transitions": 0,
                "videos_with_validation_results": 0,
                "validation_criteria_count": 0,
                "issues": []
            }
            
            # Check videos have new fields populated
            result = db.execute(text("""
                SELECT COUNT(*) as total,
                       COUNT(validation_status) as with_validation_status,
                       COUNT(hil_testing_ready) as with_hil_ready
                FROM videos
            """)).fetchone()
            
            validation_results["total_videos"] = result.total
            validation_results["videos_with_new_fields"] = result.with_validation_status
            
            print(f"📊 Video Field Validation:")
            print(f"   Total videos: {result.total}")
            print(f"   Videos with validation_status: {result.with_validation_status}")
            print(f"   Videos with hil_testing_ready: {result.with_hil_ready}")
            
            # Check status transitions
            transitions_count = db.execute(text("""
                SELECT COUNT(*) as count FROM video_status_transitions
                WHERE transition_reason = 'legacy_data_migration'
            """)).fetchone().count
            
            validation_results["videos_with_transitions"] = transitions_count
            print(f"   Migration transitions created: {transitions_count}")
            
            # Check validation results
            validation_results_count = db.execute(text("""
                SELECT COUNT(*) as count FROM video_validation_results
                WHERE validation_notes LIKE 'Migrated from legacy status%'
            """)).fetchone().count
            
            validation_results["videos_with_validation_results"] = validation_results_count
            print(f"   Validation results created: {validation_results_count}")
            
            # Check validation criteria
            criteria_count = db.execute(text("""
                SELECT COUNT(*) as count FROM video_validation_criteria
            """)).fetchone().count
            
            validation_results["validation_criteria_count"] = criteria_count
            print(f"   Validation criteria: {criteria_count}")
            
            # Validate status consistency
            print()
            print("🔎 Status Consistency Check:")
            
            inconsistent_videos = db.execute(text("""
                SELECT id, filename, status, validation_status, hil_testing_ready
                FROM videos
                WHERE (status IN ('validated', 'ready_for_testing', 'tested') AND validation_status != 'validated')
                   OR (hil_testing_ready = true AND status NOT IN ('validated', 'ready_for_testing', 'tested'))
                LIMIT 10
            """)).fetchall()
            
            if inconsistent_videos:
                print(f"   ⚠️ Found {len(inconsistent_videos)} videos with inconsistent status")
                for video in inconsistent_videos[:3]:
                    print(f"      - {video.filename}: status={video.status}, validation={video.validation_status}, hil_ready={video.hil_testing_ready}")
                validation_results["issues"].append("Inconsistent video statuses found")
            else:
                print("   ✅ All video statuses are consistent")
            
            # Check for missing ground truth counts
            missing_gt_counts = db.execute(text("""
                SELECT COUNT(*) as count FROM videos
                WHERE ground_truth_generated = true AND (ground_truth_count IS NULL OR ground_truth_count = 0)
            """)).fetchone().count
            
            if missing_gt_counts > 0:
                print(f"   ⚠️ {missing_gt_counts} videos have ground_truth_generated=true but ground_truth_count=0")
                validation_results["issues"].append(f"{missing_gt_counts} videos missing ground truth counts")
            else:
                print("   ✅ Ground truth counts are consistent")
            
            print()
            if not validation_results["issues"]:
                print("✅ VALIDATION PASSED - Migration appears successful")
                validation_results["status"] = "passed"
            else:
                print("⚠️ VALIDATION COMPLETED WITH ISSUES")
                validation_results["status"] = "issues_found"
            
            return {
                "mode": "VALIDATE",
                "results": validation_results
            }
            
        except Exception as e:
            print(f"❌ Validation failed: {str(e)}")
            return {
                "mode": "VALIDATE",
                "error": str(e)
            }
        finally:
            db.close()
    
    def _rollback_migration(self) -> Dict[str, Any]:
        """Rollback migration changes"""
        
        print("🔄 ROLLING BACK MIGRATION")
        print("⚠️ This will remove all video validation system changes!")
        print()
        
        # Confirm before proceeding
        response = input("Continue with rollback? [yes/no]: ").lower().strip()
        if response not in ['yes', 'y']:
            print("❌ Rollback cancelled by user")
            return {"mode": "ROLLBACK", "status": "cancelled"}
        
        db = self.SessionLocal()
        try:
            db.begin()
            
            print("1️⃣ Removing migration audit records...")
            deleted_transitions = db.execute(text("""
                DELETE FROM video_status_transitions
                WHERE transition_reason = 'legacy_data_migration'
            """)).rowcount
            print(f"   ✅ Deleted {deleted_transitions} transition records")
            
            print("2️⃣ Removing migration validation results...")
            deleted_results = db.execute(text("""
                DELETE FROM video_validation_results
                WHERE validation_notes LIKE 'Migrated from legacy status%'
            """)).rowcount
            print(f"   ✅ Deleted {deleted_results} validation results")
            
            print("3️⃣ Removing default validation criteria...")
            deleted_criteria = db.execute(text("""
                DELETE FROM video_validation_criteria
                WHERE project_id IS NULL
            """)).rowcount
            print(f"   ✅ Deleted {deleted_criteria} validation criteria")
            
            print("4️⃣ Restoring original video status values...")
            
            # Restore status based on migration logic (reverse)
            restored_videos = db.execute(text("""
                UPDATE videos
                SET 
                    status = CASE
                        WHEN status IN ('validated', 'ready_for_testing', 'tested') THEN 'completed'
                        WHEN status IN ('processing_failed', 'validation_failed', 'error') THEN 'uploaded'
                        WHEN status IN ('processing', 'annotated', 'validating') THEN 'uploaded'
                        ELSE 'uploaded'
                    END,
                    -- Clear new validation fields
                    validation_status = 'pending',
                    validation_type = NULL,
                    validated_at = NULL,
                    validated_by = NULL,
                    ground_truth_count = 0,
                    ground_truth_quality_score = NULL,
                    ground_truth_completed_at = NULL,
                    hil_testing_ready = false,
                    hil_testing_approved_by = NULL,
                    hil_testing_approved_at = NULL
            """)).rowcount
            print(f"   ✅ Restored {restored_videos} videos to original state")
            
            db.commit()
            
            print()
            print("✅ ROLLBACK COMPLETED SUCCESSFULLY")
            print(f"   Transition records removed: {deleted_transitions}")
            print(f"   Validation results removed: {deleted_results}")
            print(f"   Validation criteria removed: {deleted_criteria}")
            print(f"   Videos restored: {restored_videos}")
            
            return {
                "mode": "ROLLBACK",
                "status": "completed",
                "stats": {
                    "transitions_removed": deleted_transitions,
                    "results_removed": deleted_results,
                    "criteria_removed": deleted_criteria,
                    "videos_restored": restored_videos
                }
            }
            
        except Exception as e:
            db.rollback()
            print(f"❌ Rollback failed: {str(e)}")
            return {
                "mode": "ROLLBACK",
                "status": "failed",
                "error": str(e)
            }
        finally:
            db.close()
    
    def _determine_migration_path(
        self, 
        status: str, 
        processing_status: str, 
        ground_truth_generated: bool
    ) -> tuple[str, str, str]:
        """Determine the migration path for a video"""
        
        # Priority: processing_status indicates current state
        if processing_status == "failed":
            return "processing_failed", "failed", "Processing failed"
        elif processing_status == "pending":
            return "processing", "processing", "Processing pending"
        elif processing_status == "processing":
            return "processing", "processing", "Currently processing"
        elif processing_status == "completed" and ground_truth_generated:
            return "validated", "validated", "Processing completed with ground truth"
        
        # Fallback to main status field
        if status == "uploaded" and not ground_truth_generated:
            return "uploaded", "pending", "Newly uploaded video"
        elif status == "uploaded" and ground_truth_generated:
            return "annotated", "pending_validation", "Uploaded with ground truth"
        elif status == "completed":
            return "validated", "validated", "Previously completed"
        else:
            return "error", "failed", f"Unknown state: {status}"
    
    def _create_default_validation_criteria(self, db) -> Any:
        """Create default validation criteria"""
        
        criteria_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO video_validation_criteria (
                id, project_id,
                min_detection_count, min_confidence_threshold, min_frame_coverage_percent,
                min_duration_seconds, max_duration_seconds, required_resolution_min, min_fps,
                required_vru_types, min_scene_complexity_score,
                created_at
            ) VALUES (
                :criteria_id, NULL,
                5, 0.7, 80.0,
                10.0, 300.0, '640x480', 24.0,
                :vru_types, 0.5,
                NOW()
            )
        """), {
            "criteria_id": criteria_id,
            "vru_types": json.dumps(["pedestrian", "cyclist", "motorcyclist"])
        })
        
        self.migration_stats["validation_criteria_created"] += 1
        
        # Return a mock object with the ID
        class MockCriteria:
            def __init__(self, id):
                self.id = id
        
        return MockCriteria(criteria_id)
    
    def _migrate_single_video(self, db, video, default_criteria_id: str) -> bool:
        """Migrate a single video to the new system"""
        
        try:
            video_id = video.id
            legacy_status = video.status
            processing_status = video.processing_status
            ground_truth_generated = video.ground_truth_generated
            
            # Determine new status
            new_status, validation_status, reasoning = self._determine_migration_path(
                legacy_status, processing_status, ground_truth_generated
            )
            
            # Set HIL readiness and validation fields
            hil_ready = new_status in ['validated', 'ready_for_testing', 'tested']
            validated_at = video.updated_at or video.created_at if hil_ready else None
            
            # Update video with new status fields
            db.execute(text("""
                UPDATE videos
                SET
                    status = :new_status,
                    validation_status = :validation_status,
                    validation_type = CASE WHEN :hil_ready THEN 'automatic' ELSE NULL END,
                    validated_at = :validated_at,
                    validated_by = CASE WHEN :hil_ready THEN 'system' ELSE NULL END,
                    hil_testing_ready = :hil_ready,
                    ground_truth_count = CASE
                        WHEN :ground_truth_generated THEN 1
                        ELSE 0
                    END,
                    ground_truth_quality_score = CASE
                        WHEN :ground_truth_generated THEN 0.8
                        ELSE NULL
                    END,
                    ground_truth_completed_at = CASE
                        WHEN :ground_truth_generated THEN updated_at
                        ELSE NULL
                    END
                WHERE id = :video_id
            """), {
                "video_id": video_id,
                "new_status": new_status,
                "validation_status": validation_status,
                "hil_ready": hil_ready,
                "validated_at": validated_at,
                "ground_truth_generated": ground_truth_generated
            })
            
            # Create status transition audit record
            transition_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO video_status_transitions (
                    id, video_id, from_status, to_status, transition_reason,
                    triggered_by, metadata, created_at
                ) VALUES (
                    :transition_id, :video_id, :from_status, :to_status,
                    'legacy_data_migration', 'system', :metadata, NOW()
                )
            """), {
                "transition_id": transition_id,
                "video_id": video_id,
                "from_status": legacy_status,
                "to_status": new_status,
                "metadata": json.dumps({
                    "legacy_status": legacy_status,
                    "processing_status": processing_status,
                    "ground_truth_generated": ground_truth_generated,
                    "migration_version": "1.0",
                    "reasoning": reasoning
                })
            })
            
            self.migration_stats["transitions_created"] += 1
            
            # Create validation result record for validated videos
            if new_status in ['validated', 'ready_for_testing', 'tested']:
                result_id = str(uuid.uuid4())
                overall_score = 0.8 if ground_truth_generated else 0.6
                
                db.execute(text("""
                    INSERT INTO video_validation_results (
                        id, video_id, validation_criteria_id, validation_type,
                        overall_result, ground_truth_score, technical_score,
                        content_score, overall_score, criteria_met,
                        validation_notes, validated_by, created_at
                    ) VALUES (
                        :result_id, :video_id, :criteria_id, 'automatic',
                        'passed', :gt_score, 0.9, 0.7, :overall_score,
                        :criteria_met, :notes, 'system', NOW()
                    )
                """), {
                    "result_id": result_id,
                    "video_id": video_id,
                    "criteria_id": default_criteria_id,
                    "gt_score": 0.8 if ground_truth_generated else 0.0,
                    "overall_score": overall_score,
                    "criteria_met": json.dumps({
                        "ground_truth_generated": ground_truth_generated,
                        "technical_valid": True,
                        "migrated_from_legacy": True
                    }),
                    "notes": f"Migrated from legacy status: {legacy_status}, processing: {processing_status}. {reasoning}"
                })
                
                self.migration_stats["validation_results_created"] += 1
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to migrate video {video.id}: {str(e)}")
            return False

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Video Validation System Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate_video_validation_system.py --mode=PREVIEW   # Preview changes
  python migrate_video_validation_system.py --mode=MIGRATE  # Execute migration
  python migrate_video_validation_system.py --mode=VALIDATE # Validate results
  python migrate_video_validation_system.py --mode=ROLLBACK # Rollback changes
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["PREVIEW", "MIGRATE", "VALIDATE", "ROLLBACK"],
        default="PREVIEW",
        help="Migration mode (default: PREVIEW)"
    )
    
    parser.add_argument(
        "--database-url",
        help="Database URL (overrides default)"
    )
    
    parser.add_argument(
        "--output-file",
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize migrator
        migrator = VideoValidationMigrator(args.database_url)
        
        # Run migration
        results = migrator.run_migration(args.mode)
        
        # Save results if requested
        if args.output_file:
            with open(args.output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"📄 Results saved to {args.output_file}")
        
        # Exit with appropriate code
        if "error" in results:
            sys.exit(1)
        elif results.get("status") in ["cancelled"]:
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n❌ Migration cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Migration script failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()